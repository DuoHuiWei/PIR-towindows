
use std::fs::File;
use std::fs::OpenOptions;
use std::env;
use std::io::Read;
use std::io::Write;
use std::net::TcpStream;
use std::ops::DerefMut;
use memmap::MmapMut;
use std::time::Instant;

mod libs;
use libs::*;

const HINT_READ_PROGRESS_INTERVAL: usize = 32 * 1024 * 1024;

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

        if filled % HINT_READ_PROGRESS_INTERVAL == 0 || filled == buffer.len()
        {
            println!("{label}: {filled}/{} bytes", buffer.len());
        }
    }
}

fn main()
{
    let db_name = env::args().nth(1).expect("usage: pirex_uprep <db_name>");
    let connect_addr = env::args().nth(2).expect("usage: pirex_uprep <db_name> <connect_addr>");
    initialize_runtime("pirex", &db_name);
    initialize_network_address(&connect_addr);
    ensure_state_dir();
    println!("uprep: connecting to {}", server_address());

    let mut stream = TcpStream::connect(server_address()).expect("stream fail");
    let crypto = Crypto::new();
    println!("uprep: connected, creating local files");

    let mut fs_key = File::create(state_path("kset")).expect("init kset fail");
    let mut fs_par = OpenOptions::new()
        .read(true)
        .write(true)
        .create(true)
        .open(state_path("hint")).expect("init hint fail");

    fs_par.set_len((BSIZE * HSIZE) as u64).expect("error hint size");

    let mut kset = vec![0u8; KSIZE * HSIZE];
    let mut disk = unsafe { MmapMut::map_mut(& fs_par).expect("map fail") };
    let hint = disk.deref_mut();

    let start = Instant::now();

    crypto.os_random(& mut kset);
    println!("uprep: generated random kset ({} bytes)", kset.len());
    stream.write_all(& kset).expect("request fail");
    println!("uprep: sent kset, waiting for hint ({} bytes)", hint.len());
    read_exact_with_progress(&mut stream, hint, "uprep hint");
    println!("uprep: received hint");
    
    let finis = Instant::now();

    let mut file = OpenOptions::new()
        .create(true)
        .append(true)
        .open(state_path("client_prep_auto")).unwrap();

    file.write_all(format!("client prep elapse {:?} \n", finis - start).as_bytes()).unwrap();
    
    fs_key.write_all(& kset).expect("write keys fail");
    fs_key.flush().expect("flush kset fail");
    println!("uprep: persisted kset");
    fs_par.flush().expect("flush fail");
    println!("uprep: persisted hint");
    println!("uprep: completed successfully");
}
