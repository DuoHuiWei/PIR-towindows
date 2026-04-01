
use std::fs::File;
use std::fs::OpenOptions;
use std::io::Read;
use std::io::Seek;
use std::io::Write;
use std::net::TcpStream;
use std::time::Instant;
use std::ops::DerefMut;
use memmap::MmapMut;
use std::convert::TryInto;

mod libs;
use libs::*;

const HINT_READ_PROGRESS_INTERVAL: usize = 32 * 1024 * 1024;
const ENCRYPT_PROGRESS_INTERVAL: usize = 256;
const KEY : [u8; 16] = [0x77; 16];
const DEBUG_BABY_RANGE: u32 = 134217728;

extern "C"
{
    fn set_key_and_bid(input: *const u8, size: usize, bid: u32);

    fn set_input_encryption(input: *const u8, size: usize);

    fn set_input_decryption(input: *const u8, size: usize);

    fn get_output_encryption(input: *mut u8, size: usize);

    fn get_output_decryption(input: *mut u8, size: usize);

    fn load_table();

    fn free_table();

    fn thread_encrypt();

    fn thread_decrypt();
}

fn preview_words(block: &[u8]) -> Vec<u32>
{
    block
        .chunks_exact(MSIZE)
        .take(8)
        .map(|chunk| {
            let chunk: [u8; MSIZE] = chunk.try_into().expect("preview word fail");
            u32::from_be_bytes(chunk)
        })
        .collect()
}

fn preview_words_normalized(block: &[u8]) -> Vec<u32>
{
    block
        .chunks_exact(MSIZE)
        .take(8)
        .map(|chunk| {
            let chunk: [u8; MSIZE] = chunk.try_into().expect("preview word fail");
            u32::from_be_bytes(chunk).wrapping_sub(DEBUG_BABY_RANGE)
        })
        .collect()
}

fn preview_bytes(block: &[u8]) -> Vec<u8>
{
    block.iter().take(16).copied().collect()
}

fn encrypt_block(bid: usize, block: &[u8]) -> Vec<u8>
{
    let mut enc = vec![0u8; ESIZE];

    unsafe {
        set_key_and_bid(KEY.as_ptr(), KEY.len(), bid as u32);
        set_input_encryption(block.as_ptr(), block.len());
        thread_encrypt();
        get_output_encryption(enc.as_mut_ptr(), enc.len());
    }

    enc
}

fn decrypt_block(bid: usize, enc: &[u8]) -> Vec<u8>
{
    let mut block = vec![0u8; BSIZE];

    unsafe {
        set_key_and_bid(KEY.as_ptr(), KEY.len(), bid as u32);
        set_input_decryption(enc.as_ptr(), enc.len());
        thread_decrypt();
        get_output_decryption(block.as_mut_ptr(), block.len());
    }

    block
}

fn read_ehint_block(index: usize) -> Vec<u8>
{
    let mut file = File::open(state_path("ehint")).expect("open ehint fail");
    let mut block = vec![0u8; ESIZE];

    file.seek(std::io::SeekFrom::Start((index * ESIZE) as u64)).expect("seek ehint fail");
    file.read_exact(&mut block).expect("read ehint fail");

    block
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

    ensure_state_dir();

    let mut fs_key = File::create(state_path("kset")).expect("init kset fail");
    let mut fs_pos = File::create(state_path("ppos")).expect("init ppos fail");

    let mut kset = vec![0u8; KSIZE * HSIZE];
    let mut ppos = vec![0u8; 2 * HSIZE];
    
    let fs_par = OpenOptions::new()
        .read(true)
        .write(true)
        .create(true)
        .open(state_path("hint")).expect("init hint fail");

    fs_par.set_len((BSIZE * HSIZE) as u64).expect("error hint size");

    let mut disk = unsafe { MmapMut::map_mut(& fs_par).expect("map fail") };
    let hint = disk.deref_mut();

    let start = Instant::now();

    crypto.os_random(& mut kset);
    println!("uprep: generated random kset ({} bytes)", kset.len());

    stream.write_all(& kset).expect("request fail");
    println!("uprep: sent kset, waiting for hint ({} bytes)", hint.len());
    read_exact_with_progress(&mut stream, hint, "uprep hint");
    println!("uprep: received hint, starting encryption");

    let mut nonzero_blocks = 0usize;
    let mut first_nonzero_block = None;
    let mut first_zero_block = None;
    for (index, block) in hint.chunks(BSIZE).enumerate()
    {
        if block.iter().any(|byte| *byte != 0)
        {
            nonzero_blocks += 1;
            if first_nonzero_block.is_none()
            {
                first_nonzero_block = Some((index, preview_words(block)));
            }
        }
        else if first_zero_block.is_none()
        {
            first_zero_block = Some(index);
        }
    }

    println!("uprep: hint nonzero block count {}", nonzero_blocks);
    match &first_nonzero_block
    {
        Some((index, preview)) => println!("uprep: first nonzero hint block {} words {:?}", index, preview),
        None => println!("uprep: all hint blocks are zero"),
    }
    match first_zero_block
    {
        Some(index) => println!("uprep: first zero hint block {}", index),
        None => println!("uprep: no zero hint block found"),
    }

    let mut self_check_enc = None;

    if first_nonzero_block.is_some() || first_zero_block.is_some()
    {
        unsafe { load_table() };

        if let Some((index, _preview)) = first_nonzero_block
        {
            let block = &hint[index * BSIZE .. (index + 1) * BSIZE];
            println!("uprep: running local roundtrip self-check for nonzero hint block {}", index);

            let enc = encrypt_block(index, block);
            let dec = decrypt_block(index, &enc);

            println!("uprep: self-check nonzero plain words {:?}", preview_words(block));
            println!("uprep: self-check nonzero dec words {:?}", preview_words(&dec));
            println!("uprep: self-check nonzero dec words_minus_baby_range {:?}", preview_words_normalized(&dec));

            self_check_enc = Some((index, enc));
        }

        if let Some(index) = first_zero_block
        {
            let block = &hint[index * BSIZE .. (index + 1) * BSIZE];
            println!("uprep: running local roundtrip self-check for zero hint block {}", index);

            let enc = encrypt_block(index, block);
            let dec = decrypt_block(index, &enc);

            println!("uprep: self-check zero plain words {:?}", preview_words(block));
            println!("uprep: self-check zero dec words {:?}", preview_words(&dec));
            println!("uprep: self-check zero dec words_minus_baby_range {:?}", preview_words_normalized(&dec));
        }

        unsafe { free_table() };
    }

    for (iter, block) in hint.chunks(BSIZE).enumerate()
    {
        let enc = encrypt_block(iter, block);
    
        stream.write_all(& enc).expect("send parity fail");

        if (iter + 1) % ENCRYPT_PROGRESS_INTERVAL == 0 || iter + 1 == HSIZE
        {
            println!("uprep: encrypted and sent {}/{} hint blocks", iter + 1, HSIZE);
        }
    }

    println!("uprep: finished sending encrypted parity");
    let mut acknown = [0u8; 1];
    stream.read_exact(&mut acknown).expect("wait encrypted parity ack fail");
    println!("uprep: server acknowledged encrypted parity");

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

    let mut wdet = File::create(state_path("detw")).expect("init detw fail");

    wdet.write_all(& (0 as u16).to_be_bytes()).expect("save detw");
    wdet.flush().expect("flush detw fail");
    println!("uprep: persisted detw");

    if let Some((index, local_enc)) = self_check_enc
    {
        let remote_enc = read_ehint_block(index);
        let same = local_enc == remote_enc;

        println!("uprep: self-check remote ehint[{}] matches local enc {}", index, same);
        println!("uprep: self-check local enc first_bytes {:?}", preview_bytes(&local_enc));
        println!("uprep: self-check remote enc first_bytes {:?}", preview_bytes(&remote_enc));
    }

    println!("uprep: completed successfully");
}
