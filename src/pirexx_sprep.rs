
#![allow(dead_code)]

use std::fs::OpenOptions;
use std::io::Read;
use std::io::Write;
use std::net::TcpStream;
use std::net::TcpListener;
use std::thread;
use std::time::Duration;
use std::time::Instant;
use std::ops::DerefMut;
use memmap::MmapMut;

mod libs;
use libs::*;

const THREAD_PROGRESS_INTERVAL: usize = 256;
const NETWORK_PROGRESS_INTERVAL: usize = 64 * 1024 * 1024;

fn process_thread(it: usize, kset: Vec<u8>) -> (Duration, Vec<u8>)
{
    let mut storage = StoragePlus::new();

    let mut hint = vec![0u8; BSIZE * REGION];

    println!("thread {it} starts");

    let start = Instant::now();

    for i in 0 .. REGION
    {
        let key = & kset[i * KSIZE .. (i + 1) * KSIZE];
        let pos = & mut hint[i * BSIZE .. (i + 1) * BSIZE];
        let val = & storage.prep(& key);

        // println!("hint: {:?}", val);
        
        pos.copy_from_slice(val);

        if (i + 1) % THREAD_PROGRESS_INTERVAL == 0 || i + 1 == REGION
        {
            println!("thread {it} progress {}/{}", i + 1, REGION);
        }
    }

    let finis = Instant::now();

    println!("thread {it}: {:?}", finis - start);

    return (finis - start, hint);
}

fn read_exact_with_progress(stream: &mut TcpStream, buffer: &mut [u8], label: &str)
{
    let mut filled = 0usize;

    while filled < buffer.len()
    {
        let read = stream.read(&mut buffer[filled ..]).expect(label);
        if read == 0
        {
            panic!("{label}: connection closed at {filled}/{} bytes", buffer.len());
        }

        filled += read;

        if filled % NETWORK_PROGRESS_INTERVAL == 0 || filled == buffer.len()
        {
            println!("{label}: {filled}/{} bytes", buffer.len());
        }
    }
}

fn handle_client(mut stream: TcpStream)
{    
    println!("sprep: accepted client, receiving {THREAD} kset regions");
    let mut handles = vec![];
    
    for i in 0 .. THREAD
    {
        let mut kset = vec![0u8; KSIZE * REGION];
        
        stream.read_exact(& mut kset).expect("request fail");
        println!("sprep: received kset region {}/{}", i + 1, THREAD);
        
        let handle = thread::spawn(move || {
            return process_thread(i, kset);
        });
        
        handles.push((i, handle));
    }

    let mut result: [Vec<u8>; THREAD] = Default::default();
    let mut total = [Duration::from_secs(0); 3];

    for (i, handle) in handles
    {
        let (xx, res) = handle.join().unwrap();
        result[i] = res;
        total[0] += xx;
        println!("sprep: thread {i} joined");
    }

    println!("sprep: all threads completed, sending {} hint regions", THREAD);
    for i in 0 .. THREAD
    {
        stream.write_all(& result[i]).expect("response fail");
        println!("sprep: sent hint region {}/{}", i + 1, THREAD);
    }

    // ----- START RECEIVING ENCRYPTED PARITY -----

    let mut pfile = OpenOptions::new()
        .read(true)
        .write(true)
        .create(true)
        .open(state_path("ehint")).expect("init hint fail");
    let acknown = [0u8; 1];

    let len_buffer = HSIZE * ESIZE * 2;
    let recv_len = len_buffer / 2;

    pfile.set_len(len_buffer as u64).expect("error hint size");

    let mut mount = unsafe { MmapMut::map_mut(& pfile).expect("map fail") };
    let ehint = mount.deref_mut();

    println!("sprep: waiting for encrypted parity, total {} bytes (initial half {})", len_buffer, recv_len);
    read_exact_with_progress(&mut stream, &mut ehint[.. recv_len], "sprep encrypted parity");
    ehint[recv_len ..].fill(0);

    mount.flush().expect("flush ehint mmap fail");
    pfile.flush().expect("flush fail");
    stream.write_all(&acknown).expect("encrypted parity ack fail");
    stream.flush().expect("encrypted parity ack flush fail");
    println!("sprep: encrypted parity persisted to ehint (second half zero-initialized)");

    // ----- FINISH RECEIVING ENCRYPTED PARITY -----

    let mut file = OpenOptions::new()
        .create(true)
        .append(true)
        .open("server_prep_auto").unwrap();

    let xx = format!("server XX prep elapse: {:?} \n", total[0] / (THREAD as u32));

    file.write_all(xx.as_bytes()).unwrap();
}

fn main()
{
    ensure_state_dir();
    let listener = TcpListener::bind(SERVER_ADDRESS).expect("error binding");
    println!("sprep: listening on {SERVER_ADDRESS}");

    loop {
        match listener.accept() {
            
            Ok((stream, _)) => handle_client(stream),
            
            Err(e) => println!("error connection: {e}")
        }
    }
}
