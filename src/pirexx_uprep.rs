
use std::fs::File;
use std::fs::OpenOptions;
use std::io::Read;
use std::io::Write;
use std::net::TcpStream;
use std::time::Instant;
use std::ops::DerefMut;
use memmap::MmapMut;

mod libs;
use libs::*;

mod elgamal;
use elgamal::*;

use crate::elgamal::parallel_encrypt;

const HINT_READ_PROGRESS_INTERVAL: usize = 32 * 1024 * 1024;
const ENCRYPT_PROGRESS_INTERVAL: usize = 256;

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
    println!("uprep: connecting to {SERVER_ADDRESS}");
    let mut stream = TcpStream::connect(SERVER_ADDRESS).expect("stream fail");
    let crypto = Crypto::new();
    println!("uprep: connected, creating local files");

    let mut fs_key = File::create("kset").expect("init kset fail");
    let mut fs_pos = File::create("ppos").expect("init ppos fail");

    let mut kset = vec![0u8; KSIZE * HSIZE];
    let mut ppos = vec![0u8; 2 * HSIZE];
    
    let fs_par = OpenOptions::new()
        .read(true)
        .write(true)
        .create(true)
        .open("hint").expect("init hint fail");

    fs_par.set_len((BSIZE * HSIZE) as u64).expect("error hint size");

    let mut disk = unsafe { MmapMut::map_mut(& fs_par).expect("map fail") };
    let hint = disk.deref_mut();

    let mut ahe_secret = [0u8; 32];

    crypto.os_random(& mut ahe_secret);
    
    let ahe = AHE::new(ahe_secret);

    let start = Instant::now();

    crypto.os_random(& mut kset);
    println!("uprep: generated random kset ({} bytes)", kset.len());

    stream.write_all(& kset).expect("request fail");
    println!("uprep: sent kset, waiting for hint ({} bytes)", hint.len());
    read_exact_with_progress(&mut stream, hint, "uprep hint");
    println!("uprep: received hint, starting encryption");

    for (iter, block) in hint.chunks(BSIZE).enumerate()
    {
        let (enc, _time) = parallel_encrypt(&ahe, iter, & block);
    
        stream.write_all(& enc).expect("send parity fail");

        if (iter + 1) % ENCRYPT_PROGRESS_INTERVAL == 0 || iter + 1 == HSIZE
        {
            println!("uprep: encrypted and sent {}/{} hint blocks", iter + 1, HSIZE);
        }
    }

    println!("uprep: finished sending encrypted parity");
    
    let finis = Instant::now();

    let mut file = OpenOptions::new()
        .create(true)
        .append(true)
        .open("client_prep_auto").unwrap();

    file.write_all(format!("client prep elapse {:?} \n", finis - start).as_bytes()).unwrap();
    
    fs_key.write_all(& kset).expect("write keys fail");
    fs_key.flush().expect("flush kset fail");
    println!("uprep: persisted kset");

    for (i, each) in ppos.chunks_mut(2).enumerate()
    {
        each.copy_from_slice(& (i as u16).to_be_bytes());
    }

    fs_pos.write_all(& ppos).expect("write ppos fail");
    fs_pos.flush().expect("flush ppos fail");
    println!("uprep: persisted ppos");


    let mut elgamal_key = File::create("ekey").expect("init ekey fail");

    elgamal_key.write_all(& ahe_secret).expect("save elgamal keys");
    elgamal_key.flush().expect("flush ekey fail");
    println!("uprep: persisted ekey");

    let mut wdet = File::create("detw").expect("init detw fail");

    wdet.write_all(& (0 as u16).to_be_bytes()).expect("save detw");
    wdet.flush().expect("flush detw fail");
    println!("uprep: persisted detw");
    println!("uprep: completed successfully");
}
