
#![allow(dead_code)]

use std::env;
use std::fs::File;
use std::fs::OpenOptions;
use std::fs::copy;
use std::fs::hard_link;
use std::fs::remove_file;
use std::io::Write;
use std::ops::DerefMut;
use std::path::PathBuf;
use std::time::Duration;
use std::time::Instant;
use rand::Rng;
use rand::RngCore;
use rand::rngs::OsRng;
use memmap::Mmap;
use memmap::MmapMut;

mod libs;
use libs::*;

fn source_data_path() -> PathBuf
{
    env::var("PIREXX_SOURCE_DATA")
        .map(PathBuf::from)
        .unwrap_or_else(|_| PathBuf::from("data"))
}

fn reset_state_file(name: &str)
{
    let path = state_path(name);
    if path.exists()
    {
        remove_file(&path).expect("remove stale state file fail");
    }
}

fn init_state_dir()
{
    ensure_state_dir();

    let source = source_data_path();
    let target = state_path("data");

    if target.exists()
    {
        remove_file(&target).expect("remove existing state data fail");
    }

    if source != target
    {
        match hard_link(&source, &target)
        {
            Ok(_) => println!("helper: hard-linked data from {:?} to {:?}", source, target),
            Err(_) => {
                copy(&source, &target).expect("copy source data into state dir fail");
                println!("helper: copied data from {:?} to {:?}", source, target);
            }
        }
    }

    for name in ["hint", "ehint", "kset", "ppos", "detw", "item"]
    {
        reset_state_file(name);
    }

    println!("helper: state dir prepared at {:?}", state_dir());
}


fn test_read() -> Duration
{
    let mut array = Vec::new();
    let mut urand = rand::thread_rng();

    for i in 0 .. 2 * SSIZE 
    {
        let v: usize = urand.gen_range(0 .. SSIZE);
        array.push((i % SSIZE) * SSIZE + v);
    }

    let mut store = Storage::new();

    let start = Instant::now();

    for each in array
    {
        store.select(each);
    }

    let finis = Instant::now();

    return finis - start;
}


fn init_data()
{
    ensure_state_dir();
    let mut file = OpenOptions::new()
    .read(true)
    .write(true)
    .create(true)
    .open(data_path()).expect("init data fail");

    file.set_len((BSIZE * NSIZE) as u64).expect("error file size");

    // let mut disk = unsafe { MmapMut::map_mut(&file).expect("memory fail") };
    // let data = disk.deref_mut();

    // let mut rando = [0u8, 1];
    // OsRng.fill_bytes(& mut rando);

    // let batch = BUNIT * NSIZE;

    // for i in 0 .. USIZE
    // {
    //     let pos = & mut data[i * batch .. (i + 1) * batch];
    //     pos.fill_with(|| rando[0]);
    //     println!("init batch {}", i);
    // }

    file.flush().expect("flush fail");
}


fn db_read()
{
    let file = File::open(data_path()).expect("open data fail");
    let data = unsafe { Mmap::map(& file).expect("map fail") };

    let indice = 12482;
    let record = & data[indice * BSIZE .. (indice + 1) * BSIZE];

    println!("{:?}", record);
}


fn init_hint_remote()
{
    ensure_state_dir();
    let mut pfile = OpenOptions::new()
        .read(true)
        .write(true)
        .create(true)
        .open(state_path("ehint")).expect("init hint fail");

    let len_buffer = HSIZE * ESIZE * 2;

    pfile.set_len(len_buffer as u64).expect("error hint size");

    pfile.flush().expect("flush fail");
}

fn init_hint_local()
{
    ensure_state_dir();
    let mut pfile = OpenOptions::new()
        .read(true)
        .write(true)
        .create(true)
        .open(state_path("hint")).expect("init hint fail");

    pfile.set_len((HSIZE * BSIZE) as u64).expect("error hint size");

    let mut disk = unsafe { MmapMut::map_mut(& pfile).expect("memory fail") };
    let mut data = disk.deref_mut();

    OsRng.fill_bytes(& mut data);

    pfile.flush().expect("flush fail");


    let mut pkey = OpenOptions::new()
        .read(true)
        .write(true)
        .create(true)
        .open(state_path("kset")).expect("init kset fail");

    pkey.set_len((HSIZE * KSIZE) as u64).expect("error kset size");

    disk = unsafe { MmapMut::map_mut(& pkey).expect("memory fail") };
    data = disk.deref_mut();

    OsRng.fill_bytes(& mut data);

    pkey.flush().expect("flush fail");


    let mut fs_pos = File::create(state_path("ppos")).expect("init ppos fail");
    let mut ppos = vec![0u8; 2 * HSIZE];

    for (i, each) in ppos.chunks_mut(2).enumerate()
    {
        each.copy_from_slice(& (i as u16).to_be_bytes());
    }
    fs_pos.write_all(& ppos).expect("write ppos fail");
}


fn init_wdet()
{
    ensure_state_dir();
    let mut wdet = File::create(state_path("detw")).expect("init detw fail");

    wdet.write_all(& (0 as u16).to_be_bytes()).expect("save detw");
}


fn init_ppos()
{
    ensure_state_dir();
    let mut fs_pos = File::create(state_path("ppos")).expect("init ppos fail");

    let mut ppos = vec![0u8; 2 * HSIZE];

    for (i, each) in ppos.chunks_mut(2).enumerate()
    {
        each.copy_from_slice(& (i as u16).to_be_bytes());
    }

    fs_pos.write_all(& ppos).expect("write ppos fail");
}


extern "C" {
    fn xor_byte_arrays(arr1: *mut u8, arr2: *const u8, size: usize);
}


fn test_xor()
{    
    let mut arr1 = vec![117u8; 262144 * 32];
    let arr2 = & [223u8; 262144 * 32];
    
    let size = arr1.len();

    let start = Instant::now();
    
    for _ in 0 .. 9216
    {
        unsafe {
            xor_byte_arrays(arr1.as_mut_ptr(), arr2.as_ptr(), size)
        };
    }
    let finis = Instant::now();

    println!("xor result: {:?}", & arr1[.. 10]);

    println!("xor timing: {:?}", finis - start);
}



extern "C" {
    fn add_byte_arrays(arr1: *mut u8, arr2: *const u8, size: usize);
}


fn test_add()
{    
    let mut arr1 = vec![123u8; 65536];
    let arr2 = & [111u8; 65536];
    
    let size = arr1.len();

    let start = Instant::now();
    
    for _ in 0 .. 4096
    {
        unsafe {
            add_byte_arrays(arr1.as_mut_ptr(), arr2.as_ptr(), size)
        };
    }

    let finis = Instant::now();

    println!("add result: {:?}", & arr1[.. 4]);

    println!("add timing: {:?}", finis - start);
}



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


fn test_external_elgamal()
{
    let inp = vec![0x77u8; 4096];

    let mut key = vec![0x01u8; 16];

    OsRng.fill_bytes(& mut key);

    let mut out = vec![0x00u8; 4096];

    unsafe {
        set_key_and_bid(key.as_ptr(), key.len(), 777);

        set_input_encryption(inp.as_ptr(), inp.len());

        load_table();

        thread_encrypt();

        thread_decrypt();

        get_output_decryption(out.as_mut_ptr(), out.len());

        free_table();
    }

    for i in 0 .. 20
    {
        print!("{:02X} ", out[i]);
    }
}


fn main()
{
    let mut args = env::args().skip(1);

    match args.next().as_deref()
    {
        Some("init-state") => init_state_dir(),
        Some("init-all") | None => {
            init_data();
            init_hint_local();
            init_wdet();
            init_hint_remote();
        },
        Some(other) => panic!("unknown helper command: {}", other),
    }
}
