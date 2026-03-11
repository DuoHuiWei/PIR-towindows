# Pirexx Multi-File Dataset MVP

## 1. Scope

This plan defines the smallest practical layer above the current `pirexx` implementation so that:

- multiple real files can belong to one database snapshot
- the snapshot is packed into one `data` file
- one state directory is generated for that snapshot
- files can later be restored by filename through block-index lookup

This does **not** change the PIR protocol itself.
It keeps the current compile-time geometry unchanged.

## 2. Current Fixed Geometry

From [`src/libs.rs`](E:\pir-worktrees\main-debug\src\libs.rs):

- block size: `BSIZE = 4096` bytes
- block count: `NSIZE = 262144`
- total database size: `4096 * 262144 = 1073741824` bytes = `1 GiB`

Implication:

- every packed snapshot must fit in at most `262144` logical blocks
- each source file is split into 4096-byte blocks
- partial tail blocks must be zero-padded during packing

## 3. Dataset Model

One dataset snapshot corresponds to one directory tree:

```text
datasets/
  demo_a/
    input/
      report.pdf
      notes.txt
      image.bin
    manifest.json
    data
    state/
      hint
      ehint
      kset
      ppos
      detw
      item
```

Meaning:

- `input/`: original files to pack
- `manifest.json`: file-to-block mapping and integrity metadata
- `data`: packed database image used by the PIR code
- `state/`: runtime state directory for this snapshot

Important semantic rule:

- one dataset snapshot => one `data`
- one `data` => one corresponding state directory
- not one state directory per small file

If we want to run the same snapshot in two independent experiments, we should create two separate state directories, for example:

```text
datasets/demo_a/state.baseline/
datasets/demo_a/state.run1/
datasets/demo_a/state.run2/
```

because online reads update state such as `detw`, `item`, and related files.

## 4. Manifest MVP

Recommended top-level shape:

```json
{
  "format_version": 1,
  "block_size": 4096,
  "block_count": 262144,
  "data_size_bytes": 1073741824,
  "used_blocks": 57,
  "padding_policy": "zero-fill-tail-and-unused-blocks",
  "files": [
    {
      "file_id": "report.pdf",
      "relative_path": "report.pdf",
      "size_bytes": 149203,
      "sha256": "...",
      "start_block": 0,
      "block_count": 37,
      "end_block_exclusive": 37,
      "tail_valid_bytes": 1747
    }
  ]
}
```

Required per-file fields:

- `file_id`
  - stable logical identifier
  - for the MVP this can equal the relative path
- `relative_path`
  - path inside `input/`
- `size_bytes`
  - exact original file size
- `sha256`
  - integrity check for reconstructed output
- `start_block`
  - first logical block index in `data`
- `block_count`
  - number of 4096-byte blocks reserved for this file
- `end_block_exclusive`
  - convenience field for range reconstruction
- `tail_valid_bytes`
  - valid bytes in the last block
  - use `4096` when the file size is an exact multiple of block size

Optional future fields, not needed in the MVP:

- `mime_type`
- `mtime`
- `tags`
- per-block checksums

## 5. Packing Rules

MVP packing should be simple and deterministic.

Rule set:

1. Enumerate files under `input/` in a stable order.
   - recommended order: lexicographic by relative path
2. For each file:
   - read bytes in order
   - split into `4096`-byte blocks
   - zero-pad the last block if needed
   - append blocks contiguously into `data`
3. After the last file:
   - zero-fill all remaining unused blocks in `data`
4. Record one manifest entry per file with block ranges and integrity metadata

Why contiguous placement is the right MVP:

- trivial to reason about
- trivial to reconstruct
- easy to debug against current `pirexx_uread`
- no extra indirection table is needed

Block count formula:

- `block_count = ceil(size_bytes / 4096)`
- `tail_valid_bytes = size_bytes % 4096`, except store `4096` when remainder is `0` and `block_count > 0`

Capacity check:

- if total required blocks exceeds `262144`, packing must fail early

## 6. Filename -> Block Index Rule

This is the lookup layer that sits above PIR.

For a requested file:

1. open `manifest.json`
2. locate the target file entry by `file_id` or `relative_path`
3. compute its logical block range:
   - `[start_block, end_block_exclusive)`
4. query `pirexx_uread` once per block index in that range
5. concatenate returned blocks in order
6. trim the final block to `tail_valid_bytes`
7. reconstruct original file bytes

Example:

```text
report.pdf
  start_block = 0
  block_count = 37
  end_block_exclusive = 37
```

Then the read sequence is:

```text
0, 1, 2, ..., 36
```

No protocol change is required.
We are only translating a filename into a list of block indices.

## 7. Minimal Validation Flow

The first complete practical validation should be:

### A. Build dataset snapshot

- choose 2 to 5 small real files
- pack them into `data`
- generate `manifest.json`

Expected output:

- `data` size is exactly `1073741824` bytes
- `manifest.json` exists and each file has a valid block range

### B. Prepare isolated state

Commands:

```powershell
$env:PIREXX_STATE_DIR = "datasets\\demo_a\\state"
$env:PIREXX_SOURCE_DATA = "datasets\\demo_a\\data"
cargo run --bin helper -- init-state
```

Expected output:

- helper reports hard-link or copy into `datasets\demo_a\state\data`
- stale state files are removed

### C. Run PIR preprocess and server

Commands:

```powershell
$env:PIREXX_STATE_DIR = "datasets\\demo_a\\state"
cargo run --bin pirexx_sprep
cargo run --bin pirexx_uprep
cargo run --bin pirexx_sread
```

Expected output:

- preprocess completes successfully
- server preview block can be set to a known file block if needed

### D. Restore one file through block reads

Procedure:

- pick one file entry from `manifest.json`
- read all indices in its block range
- concatenate blocks
- trim to `size_bytes`
- compute SHA-256 of reconstructed bytes

Success condition:

- reconstructed SHA-256 equals manifest SHA-256

### E. Repeat for all files in the snapshot

Success condition:

- every file round-trips correctly from filename to reconstructed bytes

## 8. MVP Tool Split

The next implementation step should be two small helper tools or scripts.

Tool 1: dataset packer

- input: dataset `input/` directory
- output:
  - `data`
  - `manifest.json`

Responsibilities:

- stable file enumeration
- block packing
- capacity check
- SHA-256 calculation
- manifest generation

Implementation status:

- now implemented as `utils/pirexx_dataset_packer.py`
- validated on `tmp/multifile-demo`
- generated a `1 GiB` `data` file plus a matching manifest, then verified file reconstruction directly from packed block ranges

Tool 2: dataset restorer / verifier

- input:
  - `manifest.json`
  - dataset `state/`
  - target file id or "all"
- output:
  - reconstructed files in an output directory
  - verification report

Responsibilities:

- translate file name to block indices
- drive repeated `uread`
- reassemble bytes
- verify SHA-256

Implementation status:

- an offline baseline restorer is now implemented as `utils/pirexx_dataset_restore.py`
- current version reads directly from packed `data` using manifest block ranges
- validated on `tmp/multifile-demo` for both:
  - verify-only mode
  - restore-to-output mode

Bridge status:

- PIR-backed reader mode is now implemented
- it drives repeated `pirexx_uread` execution per block range using:
  - `PIREXX_TEST_INDICES`
  - `PIREXX_N_TEST=1`
  - `PIREXX_ITEM_RAW_PATH`
- validated end-to-end on `tmp/multifile-demo`:
  - snapshot pack
  - state init
  - `pirexx_sprep`
  - `pirexx_uprep`
  - `pirexx_sread`
  - manifest-driven file restore through `--reader pir`
  - final hash comparison against original input files

## 9. Why This Is the Right First Cut

This MVP deliberately avoids:

- changing `BSIZE`
- changing `NSIZE`
- changing `HSIZE`
- changing FFI geometry
- changing the PIR protocol

It gives us a practical workflow first:

- real files in
- one snapshot out
- one state directory per snapshot run
- file-level restore verification

That is the safest bridge from current debug success to real usability.
