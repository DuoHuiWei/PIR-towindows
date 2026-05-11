# PIREXX Debug Notes

## Scope

Current target is `pirexx_*` on `main-debug`.
Trusted Linux reference is `E:\pir-baselines\linux-clean`.
Untrusted baseline is `C:\Users\34596\Downloads\CE-PIR-feature-move_towindows`.

## Confirmed Findings

- `data[12482]` is non-zero in the current workspace and starts with repeated `0x01020304`.
- `data -> hint` is working in fresh `uprep` runs.
- Fresh `uprep` consistently reports non-zero hint blocks and a non-zero first hint block.
- The active `pirexx_*` path uses C++ FFI in `utils/helper.cpp` for both encryption and decryption.
- `src/elgamal.rs` is not used by the active `pirexx_*` execution chain.
- `ekey` is not used by the active `pirexx_*` execution chain; related code in `src/pirexx_uread.rs` is commented out.
- The `2 * ehint` layout is intentional in current code:
  first half is populated during `sprep`,
  second half is zero-initialized,
  later writes target `counter` and `counter + HSIZE`.
- Fresh first online read already fails before any historical rewrite state can explain it.

## Fresh Reproduction Summary

Fresh cycle used:

1. `pirexx_sprep`
2. `pirexx_uprep`
3. `pirexx_sread`
4. `pirexx_uread`

Observed on fresh first read:

- `search hit` uses `hint_index == ppos`
- `current_parity - BABY_RANGE == 0`
- `q0_result[0] == 0`
- `q0_result[1] == 0`
- `q1_result[1] == 0`
- recovered item is all zero

## New Narrowing Result

The latest probe added local decrypt logging in `pirexx_uread`.
That showed:

- local decrypt of `ehint[hint_index]` is already zero after subtracting `BABY_RANGE`
- network-returned `x_parity` and `y_parity` decrypt to the same zero result

This narrows the first loss point to:

- `hint (plain) -> ehint (encrypted)` generation, or
- the matching decrypt path in `utils/helper.cpp` / `secp256k1`

and makes the upper online XOR-PIR composition much less likely as the primary root cause.

## Newer Finding After Local Round-Trip Probe

`pirexx_uprep` was patched to locally round-trip the first non-zero hint block.
That local self-check succeeded:

- plain words were `16909060`
- decrypted words were also `16909060`

So the raw ElGamal encode/decode path can work correctly for that block in-process.

The next run then revealed a transport/persistence issue:

- `pirexx_sprep` panicked while receiving encrypted parity with Windows error `10054`
- the connection was reset before the server finished reading the full encrypted hint upload

This is now the strongest explanation for corrupted or zero `ehint` contents after preprocessing.

Next fix under test:

- add an explicit completion `ack` from `sprep` to `uprep`
- keep `uprep` alive until the server confirms the full encrypted hint upload

## Current Working Hypothesis

The most suspicious layer is the encryption/decryption encoding path:

- `src/pirexx_uprep.rs`
- `utils/helper.cpp`
- `secp256k1/src/secp256k1.c`

especially byte order / scalar encoding / reverse handling around:

- `secp256k1_elgamal_encryption`
- `secp256k1_elgamal_decryption`
- `reverse(&DEC[counter * INP_LEN], &DEC[(counter + 1) * INP_LEN])`

## Next Planned Check

Run `pirexx_uprep` with a local round-trip self-check on the first non-zero hint block.
If that self-check already decodes to zero, root cause is fully below the network layer.

## Later Finding: Debug Probe Regression In `uprep`

While adding a remote `ehint` verification probe, `pirexx_uprep` was briefly left in a bad state:

- after receiving the server ack, it tried to decrypt `remote_ehint` again
- that probe ran after the earlier local round-trip had already freed the discrete-log table
- `uprep` therefore exited before persisting `kset`, `ppos`, and `detw`
- symptom during `uread`: panic mapping `kset`, with zero-length `kset` / `ppos`

This was a regression introduced during debugging, not the original protocol bug.

Fix applied:

- keep the local round-trip self-check
- keep the `remote ehint == local enc` raw-byte comparison
- remove the extra remote decrypt step from `uprep`
- verify `uprep` now logs:
  - `persisted kset`
  - `persisted ppos`
  - `persisted detw`
  - `completed successfully`

## Fresh Run 3 Result

Fresh cycle:

1. `pirexx_sprep`
2. `pirexx_uprep`
3. `pirexx_sread`
4. `pirexx_uread`

Observed:

- `uprep` logged `server acknowledged encrypted parity`
- `uprep` logged `self-check remote ehint[...] matches local enc true`
- `local_ehint[hint_index]_dec` was non-zero and matched the injected pattern
- `x_parity_dec` and `y_parity_dec` individually decoded to `BABY_RANGE`
- XORing them via `current_parity` produced the correct non-zero block
- `data_item` matched the expected non-zero block
- final log: `data check ok: recovered block matches data[12482]`

Conclusion:

- the earlier “online read always recovers all zero” symptom does not reproduce on the current tree after the transport ack fix and after removing the bad debug normalization path

## Root Cause Of The Last Mismatch

After the transport fix, the remaining mismatch was not in PIR recovery itself.
It came from a debug-only post-processing step in `src/pirexx_uread.rs`:

- `data_item` was already correct
- code then applied `wrapping_sub(BABY_RANGE)` to every 32-bit word
- `0x01020304` became `0xF9020304`
- the first byte changed from `1` to `249`, creating a false mismatch report

Fix applied:

- stop normalizing `data_item` before `report_data_match`
- stop writing the normalized version to `item`

Current verified state:

- first fresh online read of `data[12482]` succeeds end-to-end
- `item` begins with `1, 2, 3, 4, ...`

## Remaining Open Question

Still worth validating separately:

- second and later online reads after rewrite
- whether the `x_parity_dec == BABY_RANGE` / `y_parity_dec == BABY_RANGE` behavior is the intended ciphertext-combination semantics or just an implementation quirk

## Later Validation: Restart And Long Sequence

Additional validations were run on the current `main-debug` tree after the earlier fresh-read recovery fix.

### Restart `sread` Only

Sequence:

1. fresh preprocess
2. start `pirexx_sread`
3. run `pirexx_uread` for two accesses
4. stop `pirexx_sread`
5. restart `pirexx_sread`
6. run `pirexx_uread` again for two more accesses

Observed:

- accesses 1 through 4 all logged `data check ok`
- `ppos` advanced as expected across the restart
- server `handle_write` continued receiving non-zero encrypted rewrite payloads

### Full Process Restart

Sequence:

1. fresh preprocess
2. stop all `pirexx_*` processes
3. start fresh `pirexx_sread` + run `pirexx_uread`
4. stop all `pirexx_*` processes again
5. start fresh `pirexx_sread` + run `pirexx_uread` again

Observed:

- accesses 1 through 4 all logged `data check ok`
- `ppos` progressed `63 -> 9216 -> 9217 -> 9218`
- `detw` progressed `0 -> 1 -> 2 -> 3 -> 4`

Conclusion:

- rewrite state survives not only a server-read restart, but also a full stop/start of all relevant `pirexx_*` processes in the current workflow

### Long Sequence Same-Block Validation

The same non-zero block was accessed 8 times in one fresh run.

Observed:

- all 8 accesses logged `data check ok`
- `ppos` progressed continuously:
  `39 -> 9216 -> 9217 -> 9218 -> 9219 -> 9220 -> 9221 -> 9222`
- `detw` progressed continuously from `0` to `8`
- no server errors were logged

Conclusion:

- for the tested block (`data[12482]`), the current `main-debug` path is stable over at least 8 consecutive accesses

### New Most Valuable Next Step

The highest-value remaining check is no longer "does rewrite work at all?"
It is now:

- do other non-zero blocks behave the same way, or is this stability specific to the current injected sample block?

## Current Regression Sample Set

The current working tree now intentionally keeps a small non-zero regression sample set in `data`.

Blocks and patterns:

- `12482` -> repeated `0x01020304`
- `1000` -> repeated `0x02030405`
- `50000` -> repeated `0x04050607`
- `200000` -> repeated `0x0708090A`

Supporting backup:

- original contents for the three injected sample blocks are stored in
  `tmp/multi-sample-block-backup.json`

Current recommendation:

- keep these four sample blocks in place for future regression testing
- use them as the default non-zero validation set unless a later test specifically needs a clean one-sample dataset

## Multi-Sample Long Sequence Validation

Using the current regression sample set:

- `12482`
- `1000`
- `50000`
- `200000`

one fresh run was executed with:

- `PIREXX_TEST_INDICES=12482,1000,50000,200000`
- `PIREXX_N_TEST=8`

Observed:

- total accesses: `32`
- total successful validations: `32`
- total mismatches: `0`
- no `sprep` / `sread` error output

Per-sample outcome:

- `12482`: 8 / 8 successful
- `1000`: 8 / 8 successful
- `50000`: 8 / 8 successful
- `200000`: 8 / 8 successful

State progression also remained consistent:

- `detw` advanced continuously up to `32`
- each sample block's `ppos` advanced monotonically after each rewrite

Current conclusion:

- on the current `main-debug` tree, the earlier "non-zero online read collapses back to zero" problem is no longer reproducible on the current regression sample set

## Initial Debug Closure

The original debug target for this phase is considered complete.

### Final conclusion for the initial debug phase

- the earlier symptom "non-zero block passes zero-block tests but online non-zero recovery collapses back to zero" is not reproducible on the current `main-debug` tree
- the current working implementation has been validated on:
  - fresh first read
  - second read after rewrite
  - restart of `sread`
  - full stop/start of all relevant `pirexx_*` processes
  - long same-block access sequences
  - multi-sample non-zero regression blocks

### Most important stabilized findings

- `data -> hint` is working on the current tree
- `sprep/uprep` encrypted hint transfer is stable with the current ACK-based completion handling
- `rewrite` is active and functioning in the current `main-debug` path
- the previous false mismatch caused by incorrect `BABY_RANGE` normalization in `uread` has been removed
- the current regression sample set is sufficient for repeated non-zero regression checks

### Recommended next phase

The next phase is no longer "find where the non-zero block becomes zero".
It is now one or both of:

1. codebase cleanup / consolidation
2. protocol-level comparison against `linux-clean` and the paper, to identify which current deviations are acceptable engineering substitutions and which should be realigned

### Practical status

- treat the current branch as a validated working implementation for the tested regression set
- treat `linux-clean` as the primary semantic / design reference
- treat further work as cleanup and reconciliation, not as continuation of the original zero-recovery incident

## Next Branch Focus

The branch created after this initial debug closure is intended for practical hardening work rather than incident debugging.

Planned focus areas:

1. performance / acceleration experiments
2. robustness improvements
3. exercising encryption / decryption against real multiple files rather than only the current synthetic regression sample set
4. making block size, database size (`N`), and related parameters easier to vary and test
5. evaluating which current implementation assumptions can be generalized into more practical workflows

## Practical Hardening Progress

### First implemented practical enhancement

The first low-risk practical enhancement in this branch is state-directory support.

New environment-controlled inputs:

- `PIREXX_STATE_DIR`
  - controls where state files are read/written
  - intended to isolate different working datasets
- `PIREXX_DATA_PATH`
  - still supported
  - now defaults to `<STATE_DIR>/data` when not explicitly set
- `PIREXX_DEBUG_INDEX`
  - controls which block `pirexx_sread` previews at startup

State files now routed through `STATE_DIR` in the active `pirexx` path:

- `hint`
- `ehint`
- `kset`
- `ppos`
- `detw`
- `item`

### Why this was chosen first

This change is lower risk than immediately parameterizing:

- block size
- `N`
- `HSIZE`
- FFI chunk geometry

because those deeper parameters are still tightly coupled to compile-time constants across `libs.rs` and `helper.cpp`.

### Smoke-test result

A lightweight smoke test was run with:

- `PIREXX_STATE_DIR=tmp/state_alt`
- `PIREXX_DEBUG_INDEX=1000`

and a separate state directory containing hard-linked `data` / `ehint`.

Observed startup output from `pirexx_sread`:

- `server data[1000] first_words [33752069, ...]`

which matches the injected regression pattern:

- `0x02030405` repeated

Conclusion:

- state-directory switching is functioning for the tested `pirexx` server read path
- this creates a practical base for later real-file / multi-dataset workflows

### Second practical enhancement

Added a lightweight `helper init-state` command to reduce manual setup mistakes when switching datasets.

Current behavior:

- reads `PIREXX_STATE_DIR`
- reads optional `PIREXX_SOURCE_DATA`
- prepares `<STATE_DIR>/data` from the source data file
- prefers hard-linking, falls back to copying
- removes stale state artifacts before a fresh run:
  - `hint`
  - `ehint`
  - `kset`
  - `ppos`
  - `detw`
  - `item`

Why this matters:

- avoids reusing stale per-dataset state by accident
- makes isolated multi-dataset testing much easier
- stays outside the `sprep/uprep/sread/uread` protocol logic, so risk is comparatively low

Validation summary:

- prepared `tmp/state_auto` via `helper init-state`
- reran `pirexx_sprep -> pirexx_uprep -> pirexx_sread -> pirexx_uread`
- verified regression samples in the isolated state directory still pass
