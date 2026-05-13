
use std::convert::TryInto;
use std::fs::File;
use std::fs::OpenOptions;
use std::fs::write;
use std::io::Read;
use std::io::Seek;
use std::io::SeekFrom;
use std::io::Write;
use std::net::TcpStream;
use std::ops::DerefMut;
use std::env;
use std::time::Duration;
use std::time::Instant;
use memmap::MmapMut;

mod libs;
use libs::*;


pub const KEY : [u8; 16] = [0x77; 16];


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


pub struct Client {
    crypto: Crypto,
    item: File,
    data: File,
    kset: MmapMut,
    ppos: MmapMut,
    wdet: u16,
    wfile: File
}

impl Client
{
    const DEBUG_BABY_RANGE: u32 = 134217728;

    fn log_words(label: &str, block: &[u8])
    {
        let preview: Vec<u32> = block
            .chunks_exact(MSIZE)
            .take(8)
            .map(|chunk| {
                let chunk: [u8; MSIZE] = chunk.try_into().expect("preview word fail");
                u32::from_be_bytes(chunk)
            })
            .collect();

        println!("{label} first_words {:?}", preview);
    }

    fn log_words_delta_from_baby_range(label: &str, block: &[u8])
    {
        let preview: Vec<i64> = block
            .chunks_exact(MSIZE)
            .take(8)
            .map(|chunk| {
                let chunk: [u8; MSIZE] = chunk.try_into().expect("preview word fail");
                i64::from(u32::from_be_bytes(chunk)) - i64::from(Self::DEBUG_BABY_RANGE)
            })
            .collect();

        println!("{label} first_words_delta_from_baby_range {:?}", preview);
    }

    fn log_enc_words(label: &str, block: &[u8])
    {
        let preview: Vec<u32> = block
            .chunks_exact(33)
            .take(4)
            .map(|chunk| {
                let head: [u8; 4] = chunk[.. 4].try_into().expect("enc preview word fail");
                u32::from_be_bytes(head)
            })
            .collect();

        println!("{label} enc_head_words {:?}", preview);
    }

    fn export_raw_block(index: usize, block: &[u8])
    {
        ensure_raw_item_export_dir();
        let path = raw_item_export_path(index);
        write(&path, block).expect("write raw item fail");
        println!("raw block exported: index={index}, path={:?}, nbytes={}", path, block.len());
    }

    pub fn new() -> Self
    {
        let crypto = Crypto::new();
        ensure_state_dir();
        
        // let mut elgamal_key = File::open("ekey").expect("open fail");
        
        // let mut raw_sk = [0u8; 32];
        
        // elgamal_key.read_exact(&mut raw_sk).expect("read sk fail");

        let mut wfile = OpenOptions::new()
            .read(true)
            .write(true)
            .open(state_path("detw")).expect("init detw fail");

        let detw_len = wfile.metadata().expect("detw metadata fail").len();

        if detw_len == 0
        {
            println!("warning: detw is empty, repairing to 0x0000");
            wfile.write_all(& (0u16).to_be_bytes()).expect("repair detw fail");
            wfile.flush().expect("flush repaired detw fail");
            wfile.seek(SeekFrom::Start(0)).expect("seek repaired detw fail");
        }
        else if detw_len != 2
        {
            panic!("detw length invalid: expected 2 bytes, got {} bytes", detw_len);
        }

        let mut raw_det = [0u8; 2];

        wfile.read_exact(&mut raw_det).expect("read detw fail");

        let wdet = u16::from_be_bytes(raw_det);

        wfile.seek(SeekFrom::Start(0)).expect("seek detw fail");


        let item = File::create(state_path("item")).expect("init item file fail");
        let data = File::open(data_path()).expect("open data fail");

        let key_file = OpenOptions::new()
            .read(true)
            .write(true)
            .open(state_path("kset")).expect("init kset fail");

        let pos_file = OpenOptions::new()
            .read(true)
            .write(true)
            .open(state_path("ppos")).expect("init ppos fail");

        let kset = unsafe { MmapMut::map_mut(& key_file).expect("map kset fail") };
        let ppos = unsafe { MmapMut::map_mut(& pos_file).expect("map ppos fail") };

        println!("client storage nbytes {:?}", kset.len() + ppos.len());

        Self {crypto, item, data, kset, ppos, wdet, wfile}
    }

    pub fn search(& self, pk: usize, offset: B_OFFSET) -> (&[u8], Vec<u8>, Vec<u8>, usize, Duration)
    {
        let mut t_comp = Duration::from_secs(0);

        for i in 0 .. HSIZE
        {
            let key = & self.kset[i * KSIZE .. (i + 1) * KSIZE];

            let (test, t_val) = self.crypto.key_val(key, pk);
            t_comp += t_val;

            if offset == test {

                let pos = & self.ppos[i * 2 .. (i + 1) * 2];
                let pos = u16::from_be_bytes(pos.try_into().unwrap()) as usize;

                let start = Instant::now();
                let (str_a, str_b, _t_gen) = self.crypto.gen_pir(pos);
                t_comp += Instant::now() - start;

                println!("search hit: pk={pk}, hint_index={i}, ppos={pos}");
                
                return (key, str_a, str_b, i, t_comp);
            }
        }

        println!("search hint fail");

        return (&[0], vec![0; 0], vec![0; 0], 0, t_comp)
    }

    pub fn newkey(& self, pk: usize, offset: B_OFFSET) -> (B_KEYSET, bool)
    {
        let mut key = Z_KEYSET;
        loop {
            self.crypto.os_random(& mut key);

            let (res, _t) = self.crypto.key_val(& key, pk);

            if offset ==  res {
                return (key, (key[0] & 1 != 0))
            }
        }
    }

    pub fn patch(& self, pk: usize, key: &[u8], away: bool) -> (TSUB, TSUB, Duration)
    {        
        let (par0, par1, zeta, t_gen) = self.crypto.gen_ppr(pk);
        
        let mut rset = vec![0u8; IV_SQRT];
        self.crypto.os_random(& mut rset);

        let start = Instant::now();

        let mut sset = self.crypto.key_set(key);
        sset[pk * ISQRT .. (pk + 1) * ISQRT].copy_from_slice(& zeta);
    
        let sub0 = (sset, par0);
        let sub1 = (rset, par1); // zeta in par1, so it goes with rset

        let finis = Instant::now();

        if away 
        {
            return (sub0, sub1, finis - start + t_gen); 
        }
        else {
            return (sub1, sub0, finis - start + t_gen);
        }
        
    }
    
    pub fn request(& self, address: &str, data_query: TSUB, refresh_query: TSUB, first_bitvec: &[u8], second_bitvec: &[u8]) -> ([Vec<u8>; 2], [Vec<u8>; 2], Vec<u8>, Vec<u8>)
    {
        let mut stream = TcpStream::connect(address).expect("stream fail");

        let list : [& [u8]; 4] = [
            & data_query.0, 
            & data_query.1, 
            & refresh_query.0, 
            & refresh_query.1
        ];

        let mut acknown = [0u8; 1];
        let mut first_bitvec_result = vec![0u8; ESIZE];
        let mut second_bitvec_result = vec![0u8; ESIZE];
        let mut dat_0 = vec![0u8; BSIZE];
        let mut dat_1 = vec![0u8; BSIZE];
        let mut new_0 = vec![0u8; BSIZE];
        let mut new_1 = vec![0u8; BSIZE];

        let start_1 = Instant::now();
        stream.write_all(& first_bitvec).unwrap();
        stream.read_exact(& mut acknown).unwrap();
        let finis_1 = Instant::now();

        let start_2 = Instant::now();
        stream.write_all(& second_bitvec).unwrap();
        stream.read_exact(& mut acknown).unwrap();
        let finis_2 = Instant::now();
        
        println!("xorpir request delay {:?} (real measure)", (finis_2 - start_2) + (finis_1 - start_1));


        for i in 0 .. 4
        {
            let mut request_buffer = vec![0u8; 0];
            let length = (list[i].len() as u32).to_be_bytes();
            request_buffer.extend_from_slice(& length);
            request_buffer.extend_from_slice(list[i]);
            
            stream.write_all(& request_buffer).unwrap();
            stream.flush().unwrap();
        }
        
        stream.read_exact(& mut acknown).unwrap();
        
        let start_3 = Instant::now();
        stream.read_exact(& mut dat_0).unwrap();
        stream.read_exact(& mut dat_1).unwrap();
        stream.read_exact(& mut new_0).unwrap();
        stream.read_exact(& mut new_1).unwrap();
        let finis_3 = Instant::now();
        println!("pirex bandwidth delay {:?} (real measure)", finis_3 - start_3);

        stream.read_exact(& mut first_bitvec_result).unwrap();
        stream.write_all(& acknown).unwrap();

        stream.read_exact(& mut second_bitvec_result).unwrap();
        stream.write_all(& acknown).unwrap();

    
        return ([dat_0, dat_1], [new_0, new_1], first_bitvec_result, second_bitvec_result);
    }


    pub fn parity(& self, _bid: usize, half_a: & [u8], half_b: &[u8]) -> Vec<u8>
    {
        assert_eq!(half_a.len(), ESIZE, "half_a length invalid");
        assert_eq!(half_b.len(), ESIZE, "half_b length invalid");

        let mut enc = vec![0u8; ESIZE];
        let mut block = vec![0u8; BSIZE];

        let start = Instant::now();

        for i in 0 .. ESIZE
        {
            enc[i] = half_a[i] ^ half_b[i]
        }

        let finis = Instant::now();

        println!("recover parity delay {:?}", finis - start);

        unsafe {
            set_key_and_bid(KEY.as_ptr(), KEY.len(), _bid as u32);
            set_input_decryption(enc.as_ptr(), enc.len());
            thread_decrypt();
            get_output_decryption(block.as_mut_ptr(), block.len());
        }

        return block;
    }

    pub fn decrypt_enc_block(& self, bid: usize, enc: &[u8]) -> Vec<u8>
    {
        assert_eq!(enc.len(), ESIZE, "enc length invalid");

        let mut block = vec![0u8; BSIZE];

        unsafe {
            set_key_and_bid(KEY.as_ptr(), KEY.len(), bid as u32);
            set_input_decryption(enc.as_ptr(), enc.len());
            thread_decrypt();
            get_output_decryption(block.as_mut_ptr(), block.len());
        }

        block
    }

    pub fn local_ehint_block(& self, index: usize) -> Vec<u8>
    {
        let mut file = File::open(state_path("ehint")).expect("open ehint fail");
        let mut block = vec![0u8; ESIZE];

        file.seek(SeekFrom::Start((index * ESIZE) as u64)).expect("seek ehint fail");
        file.read_exact(&mut block).expect("read ehint fail");

        block
    }

    pub fn expected_block(& mut self, index: usize) -> Vec<u8>
    {
        let mut block = vec![0u8; BSIZE];
        self.data.seek(SeekFrom::Start((index * BSIZE) as u64)).expect("seek data fail");
        self.data.read_exact(&mut block).expect("read data fail");
        block
    }

    pub fn report_data_match(& mut self, index: usize, data_item: &[u8])
    {
        let expected = self.expected_block(index);

        let mut mismatch_count = 0usize;
        let mut first_mismatch = None;

        for (offset, (actual, expected)) in data_item.iter().zip(expected.iter()).enumerate()
        {
            if actual != expected
            {
                mismatch_count += 1;

                if first_mismatch.is_none()
                {
                    first_mismatch = Some((offset, *actual, *expected));
                }
            }
        }

        let expected_is_zero = expected.iter().all(|value| *value == 0);

        if mismatch_count == 0
        {
            println!("data check ok: recovered block matches data[{index}]");

            if expected_is_zero
            {
                println!("data check note: data[{index}] is all-zero, likely sparse/set_len initialized");
            }
        }
        else
        {
            let (offset, actual, expected) = first_mismatch.expect("missing mismatch detail");
            println!(
                "data check mismatch: data[{index}] differs at byte {offset}, actual={actual}, expected={expected}, total_mismatches={mismatch_count}"
            );

            if expected_is_zero
            {
                println!("data check note: expected block is all-zero, so non-zero recovery suggests protocol/correctness bug");
            }
        }
    }

    
    pub fn access(& mut self, x: INDX)
    {
        // prepare the queries

        let (partition_index, offset) = self.crypto.ppr_val(x);
        let (new_key, _id) = self.newkey(partition_index, offset);
        
        let (current_key, x_bitvec, y_bitvec, hint_index, time_search) = self.search(partition_index, offset);
        let (query_0, query_1, time_patch_query) = self.patch(partition_index, current_key, true); // server id is set to 1
        let (refresh_0, refresh_1, time_patch_refresh) = self.patch(partition_index, & new_key, true); // server id is neg to 0

        // end prepare

        // prepare oblivios write

        // new key value to local

        let kset = self.kset.deref_mut();
        let new_key_storage = & mut kset[hint_index * KSIZE .. (hint_index + 1) * KSIZE];
        new_key_storage.copy_from_slice(& new_key);


        // get position for oblivious write in left buffer

        let counter = self.wdet as usize;
        let left_pos = & mut self.ppos[counter * 2 .. (counter + 1) * 2];
        let pos = u16::from_be_bytes(left_pos.try_into().unwrap()) as usize;
        left_pos.copy_from_slice(& self.wdet.to_be_bytes());

        let (a_bitvec, b_bitvec, time_gen) = self.crypto.gen_pir(pos);

        // set position for oblivious write in right buffer

        let righ_pos = & mut self.ppos[hint_index * 2 .. (hint_index + 1) * 2];
        righ_pos.copy_from_slice(& ((counter + HSIZE) as u16).to_be_bytes());

        // end prepare

        println!("generate query delay {:?}", time_gen + time_search + time_patch_query + time_patch_refresh);
    
        let current_address = server_address();
        let (q0_result, r0_result, x_parity, a_parity) = self.request(&current_address, query_0, refresh_0, & x_bitvec, & a_bitvec);
        let (q1_result, r1_result, y_parity, b_parity) = self.request(&current_address, query_1, refresh_1, & y_bitvec, & b_bitvec);

        let local_ehint = self.local_ehint_block(hint_index);
        let local_ehint_dec = self.decrypt_enc_block(hint_index, &local_ehint);
        let x_parity_dec = self.decrypt_enc_block(hint_index, &x_parity);
        let y_parity_dec = self.decrypt_enc_block(hint_index, &y_parity);

        let current_parity = self.parity(hint_index, & x_parity, & y_parity);
        let rewrite_parity = self.parity(counter, & a_parity, & b_parity);

        Self::log_words("local_ehint[hint_index]_dec", &local_ehint_dec);
        Self::log_words_delta_from_baby_range("local_ehint[hint_index]_dec", &local_ehint_dec);
        Self::log_words("x_parity_dec", &x_parity_dec);
        Self::log_words_delta_from_baby_range("x_parity_dec", &x_parity_dec);
        Self::log_words("y_parity_dec", &y_parity_dec);
        Self::log_words_delta_from_baby_range("y_parity_dec", &y_parity_dec);
        Self::log_words("current_parity", &current_parity);
        Self::log_words_delta_from_baby_range("current_parity", &current_parity);
        Self::log_words("rewrite_parity", &rewrite_parity);
        Self::log_words_delta_from_baby_range("rewrite_parity", &rewrite_parity);
        Self::log_words("q0_result[0]", &q0_result[0]);
        Self::log_words("q0_result[1]", &q0_result[1]);
        Self::log_words("q1_result[1]", &q1_result[1]);


        let (data_item, t_rec) = self.recover_dbitem([& q0_result[0], & q0_result[1], & current_parity, & q1_result[1]]);
        let (refresh_parity, t_ref) = self.refresh_parity([& r0_result[0], & r0_result[1], & data_item, & r1_result[1]]);

        Self::log_words("data_item", &data_item);
        Self::log_words_delta_from_baby_range("data_item", &data_item);
        Self::log_words("refresh_parity", &refresh_parity);
        Self::log_words_delta_from_baby_range("refresh_parity", &refresh_parity);

        println!("recover dbitem delay {:?}", t_rec + t_ref);
        self.rewrite(rewrite_parity, counter, refresh_parity, hint_index);
        self.report_data_match(x as usize, &data_item);
        Self::export_raw_block(x as usize, &data_item);


        let view = format!("{:?}", data_item);
        self.item.write_all(view.as_bytes()).unwrap();
    }

    pub fn rewrite(& mut self, rewrite_parity: Vec<u8>, counter: usize, refresh_parity: Vec<u8>, hint_index: usize)
    {   
        let mut stream = TcpStream::connect(server_address()).expect("stream fail");

        let mut enc_left = vec![0u8; ESIZE];
        let mut enc_righ = vec![0u8; ESIZE];

        unsafe {
            set_key_and_bid(KEY.as_ptr(), KEY.len(), counter as u32);
            set_input_encryption(rewrite_parity.as_ptr(), rewrite_parity.len());
            thread_encrypt();
            get_output_encryption(enc_left.as_mut_ptr(), enc_left.len());
        }

        unsafe {
            set_key_and_bid(KEY.as_ptr(), KEY.len(), hint_index as u32);
            set_input_encryption(refresh_parity.as_ptr(), refresh_parity.len());
            thread_encrypt();
            get_output_encryption(enc_righ.as_mut_ptr(), enc_righ.len());
        }

        Self::log_words("rewrite plain left", &rewrite_parity);
        Self::log_words("rewrite plain right", &refresh_parity);
        Self::log_enc_words("rewrite enc left", &enc_left);
        Self::log_enc_words("rewrite enc right", &enc_righ);
        
        let write_data = [self.wdet.to_be_bytes().to_vec(), enc_left, enc_righ].concat();
        stream.write_all(& write_data).expect("oblivious write fail");

        println!("oblivious write nbytes {:?}", ESIZE * 2);
        println!("oblivious write takes {:?}ms (in 40 Mbps)", ESIZE * 2 / 5000);
        println!("oblivious write sent for counter={counter}, hint_index={hint_index}");


        self.wdet = (((self.wdet + 1) as usize) % HSIZE) as u16;
        self.wfile.seek(SeekFrom::Start(0)).expect("seek detw fail");
        self.wfile.write_all(& self.wdet.to_be_bytes()).expect("next pos");
        self.wfile.flush().expect("flush detw fail");
        println!("oblivious write local detw persisted as {}", self.wdet);
    }

    pub fn recover_dbitem(& self, input: [& [u8]; 4]) -> (Vec<u8>, Duration)
    {
        // println!("input {:?}", input);

        let mut block = vec![0u8; BSIZE];
        let mut regis : [PINT; BSIZE / MSIZE] = [0; BSIZE / MSIZE];

        let mut t_comp = Duration::from_secs(0);
        
        for i in [2, 3]
        {
            for (j, chunk) in input[i].chunks(MSIZE).enumerate()
            {
                let chunk : [u8; MSIZE] = chunk.try_into().unwrap();
                let temp = PINT::from_be_bytes(chunk);

                let start = Instant::now();
                regis[j] = regis[j].wrapping_add(temp);
                t_comp += Instant::now() - start;
            }
        }

        for i in [0, 1]
        {
            for (j, chunk) in input[i].chunks(MSIZE).enumerate()
            {
                let chunk : [u8; MSIZE] = chunk.try_into().unwrap();
                let temp = PINT::from_be_bytes(chunk);

                let start = Instant::now();
                regis[j] = regis[j].wrapping_sub(temp);
                t_comp += Instant::now() - start;
            }
        }

        for (i, chunk) in block.chunks_exact_mut(MSIZE).enumerate()
        {
            chunk.copy_from_slice(& regis[i].to_be_bytes());
        }

        return (block, t_comp);
    }

    pub fn refresh_parity(& self, input: [& [u8]; 4]) -> (Vec<u8>, Duration)
    {
        // println!("input {:?}", input);

        let mut block = vec![0u8; BSIZE];
        let mut regis : [PINT; BSIZE / MSIZE] = [0; BSIZE / MSIZE];
        
        let mut t_comp = Duration::from_secs(0);
        
        for i in [0, 1, 2]
        {
            for (j, chunk) in input[i].chunks(MSIZE).enumerate()
            {
                let chunk : [u8; MSIZE] = chunk.try_into().unwrap();
                let temp = PINT::from_be_bytes(chunk);

                let start = Instant::now();
                regis[j] = regis[j].wrapping_add(temp);
                t_comp += Instant::now() - start;
            }
        }

        for i in [3]
        {
            for (j, chunk) in input[i].chunks(MSIZE).enumerate()
            {
                let chunk : [u8; MSIZE] = chunk.try_into().unwrap();
                let temp = PINT::from_be_bytes(chunk);

                let start = Instant::now();
                regis[j] = regis[j].wrapping_sub(temp);
                t_comp += Instant::now() - start;
            }
        }

        for (i, chunk) in block.chunks_exact_mut(MSIZE).enumerate()
        {
            chunk.copy_from_slice(& regis[i].to_be_bytes());
        }

        return (block, t_comp);
    }
}

fn main()
{
    let db_name = env::args().nth(1).expect("usage: pirexx_uread <db_name>");
    let connect_addr = env::args().nth(2).expect("usage: pirexx_uread <db_name> <connect_addr>");
    initialize_runtime("pirexx", &db_name);
    initialize_network_address(&connect_addr);
    let load_start = Instant::now();
    println!("\nLoading Table ...");

    unsafe {load_table()}

    println!("Loading Table done in {:?}", Instant::now() - load_start);

    println!("===== PIREX+ (Per Client Cost) Test DB: 2^{:?} entries {:?} KB", LSIZE * 2, BSIZE / 1024);

    let client_init_start = Instant::now();
    let mut client = Client::new();
    println!("Client::new done in {:?}", Instant::now() - client_init_start);

    let indices: Vec<INDX> = env::var("PIREXX_TEST_INDICES")
        .ok()
        .map(|value| {
            value
                .split(',')
                .filter_map(|part| part.trim().parse::<usize>().ok())
                .map(|index| (index % NSIZE) as INDX)
                .collect::<Vec<_>>()
        })
        .filter(|indices| !indices.is_empty())
        .unwrap_or_else(|| vec![(12482 % NSIZE) as INDX]);

    let n_test = env::var("PIREXX_N_TEST")
        .ok()
        .and_then(|value| value.parse::<usize>().ok())
        .filter(|value| *value > 0)
        .unwrap_or(2);

    println!("Test indices {:?}, n_test {}", indices, n_test);

    for index in indices
    {
        for iter in 0 .. n_test
        {
            println!("===== client access begin index={} iter={}/{} =====", index, iter + 1, n_test);
            let access_start = Instant::now();
            client.access(index);
            println!("client access done in {:?}", Instant::now() - access_start);
        }
    }

    unsafe {free_table()}
    println!("free_table done");
}
