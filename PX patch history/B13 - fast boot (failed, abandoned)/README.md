# B13 - Fast boot and boot tracing (failed, abandoned)

Technical handover for the abandoned B13 optimization and diagnostic investigations. Neither produced a successfully booting hardware candidate or a demonstrated boot-speed improvement. B13 is excluded from the working firmware chain.

**Firmware:** `2.2.2.1.3` (withdrawn fast-manifest build); `2.2.2.1.1` (later .1.15-based boot-trace package, distinguished by filename/hash).

**Hardware: FAIL:** The fast-manifest and full boot-trace candidates failed normal boot despite passing host checks. Diagnostic control/bisect variants were not hardware-tested. Root causes remain unconfirmed.

## Original goal and fast-manifest implementation

**Patch location:** QNX application (x86-64) for both abandoned attempts; PIC and FPGA behavior remain inherited.

**Patch size:** Withdrawn .1.3 optimization: 390 helper-code bytes at [0xF9240,0xF93C6), 108 unwind bytes, and 458 actual changed application bytes (461 package bytes); no image-length growth. Later boot-trace attempt: 1,056 helper-code bytes plus hooks/unwind/index edits and 256 added runtime-state bytes. These are separate failed candidates, not cumulative release changes.

The optimization targeted full sample-group manifest parsing during startup. The v3 helper and its host harness are retained, but the real-library audit found that v3 fell back to stock parsing for all 927 supplied manifests; its projected speedup did not apply to that library.

The revised v4 helper reads a bounded complete header and skips full preload parsing only when UUID is absent **and at least one of Mono Pitch/Mono Collapse is absent**. Missing stock columns default to token position 15, so absence of UUID alone cannot prove that a row will never reach the UUID converter. Ambiguous, incomplete, UUID-bearing and unreadable headers fall back to stock parsing. Full group parsing is deferred until first instrument use; folder/location indexing remains separate, and no background warmer is added.

All 927 supplied manifests met the v4 condition and matched the stock 17-byte UUID output in the retained audit. The UUID dictionary rejects GUIDs containing any zero byte; these groups produced zero UUIDs. This is host/content evidence, not proof that real QNX initialization succeeds.

## Withdrawn package - 2.2.2.1.3

The hardware candidate used exact B9 `.1.2`. It changed only the QNX application and application revision/checksum metadata; the complete PIC and FPGA records stayed unchanged, with PIC revision `.1.2` retained.

| Artifact | SHA-256 |
|---|---|
| Known-good `.1.2` baseline package | `3e844a73a9f29bf0f1dc24929c989e0cb3946c9a307cab948e6af4c0928b5029` |
| **Withdrawn `.1.3` package** | `52d27173142479dfe84bb019b551f946ef3ae09b579b82fef719d8a1e17b857a` |
| Failed QNX application | `9b1662cfdff70e76b9ba38c6de9ee78f07f1f782a07d1e311cabc26583bd4b20` |
| Known-good `.1.2` application | `a0ee95328e908b4d1aadff6e71ca34e44d1845418bb1e8204372667ed99d62bf` |

Helper code occupies `[0xF9240,0xF93C6)` and unwind data `[0xFA528,0xFA594)` in this exact ELF. Application length is 1,039,304 bytes; package length is 3,151,848 bytes. ELF size/mappings remain inherited. The recorded diff is 458 application bytes and 461 package bytes. These are historical placements, not authorization to reuse those ranges in another baseline.

The withdrawn `.1.3` package was subsequently recovered and its whole-package SHA-256 matches the table above exactly. It remains private and withdrawn; recovery of its bytes does not change the hardware failure result.

### Hardware failure and recovery evidence

Installation succeeded, but normal boot repeatedly hung after the completed progress bar, with no visible speed improvement. SysEx recovery did not restore operation; a known-good SSD swap restored boot. The completed bar did not identify the failing stage or prove that manifest preload had completed.

Read-only SSD forensics found the same failed application in both `ProphetX` and `ProphetXBackup`. Stock `startup.sh` copies applications to `/tmp`, launches ProphetX, waits five seconds and checks process existence. A hung but live application can therefore replace its backup. This explains how both copies could become failed versions, rather than establishing the cause of the original hang.

The exported boot image matched known-good SHA-256 `6a5124d8ee0eb6ad7561bf394e3c7469115dc6184e397d34ea7e3b72f8f6fccc`, and `startup.sh` matched stock behavior. Both on-disk application files were subsequently replaced with known-good `.1.2` bytes; final repaired-file hashes and a boot test of that repaired SSD were not recorded in the supplied reports.

The [SSD application recovery procedure](../../RECOVERY.md) records the Windows/QEMU steps used to inspect the SSD and replace both application copies, plus readback verification steps. This recovered the SSD-resident application; the boot partition was verified unchanged and did not require rewriting. Final repaired-file hashes and a hardware boot confirmation remain unrecorded in the supplied evidence.

### SSD postmortem: persistence mechanism and repair boundary

The affected drive was a Crucial CT480M500SSD1, 480,103,979,008 bytes, with an MBR layout. Windows Disk 2 and QNX `hd2` were identifiers in that historical setup, not portable device selections. The proven maintenance topology used `hd0` for the service image, `hd1` for a snapshot-backed known-good backup, and `hd2` for the physical failed SSD. Always identify devices again before access; keep the physical disk offline in Windows and mount QNX filesystems read-only during evidence collection.

The stock startup logic was:

```sh
# /bin/bash
cp /hd/ProphetX /tmp/
cp /hd/ProphetXBackup /tmp/
chmod 777 /tmp/ProphetX
chmod 777 /tmp/ProphetXBackup
/tmp/ProphetX &
sleep 5
if pidin -p ProphetX | grep ProphetX ; then
   rm /hd/ProphetXBackup
   cp /hd/ProphetX /hd/ProphetXBackup
else
   /tmp/ProphetXBackup &
   rm /hd/ProphetX
   cp /hd/ProphetXBackup /hd/ProphetX
fi
```

This checks whether a process exists after five seconds, rather than whether startup completed or audio/UI works. A still-running hung process can therefore overwrite the good backup. Finding the failed B13 application in both on-disk copies supports this persistence mechanism; it does not identify the original hang's cause.

The postmortem called for preserving `ProphetX`, `ProphetXBackup`, `startup.sh` and `/.boot/x86_64-generic.bin` before repair, recording sizes/timestamps, and comparing hashes and byte equality outside QNX if necessary. The known boot image is 9,278,800 bytes with SHA-256 `6a5124d8ee0eb6ad7561bf394e3c7469115dc6184e397d34ea7e3b72f8f6fccc`. The observed application/boot-script/boot-image findings are recorded above; comprehensive filesystem health and absence of changes elsewhere were not established by those checks.

The decoded factory SysEx recovery payload contains PIC application/preset-related data, with no identified raw QNX application ELF. Its failure to repair this SSD application hang is therefore consistent with the observed failure location and does not establish PIC bootloader damage. Booting normally with a known-good replacement SSD further localizes the failure to SSD-resident state, without proving which QNX operation failed.

After preserving evidence, the repair replaced both application files with the same known-good .1.2 executable, preserved executable permissions, synchronized and cleanly unmounted the filesystem. The unchanged boot partition did not require rewriting. A verified full-disk restore remains the fallback for broader damage. Use the separate [SSD application recovery procedure](../../RECOVERY.md) for the executable Windows/QEMU workflow and readback checks, and the [SSD expansion guide](../../SSD%20expansion/README.md) for the maintenance-image setup. The original postmortem's proposed .1.2 instrumentation baseline was superseded by the later exact-.1.15 diagnostic design described below; neither attempt is retained firmware.

### Saved host evidence

The retained tools/reports cover the 927 manifest comparisons, worker/dictionary projections across 1/2/4 partitions, helper fallbacks, ELF structure, cache callers, checksums, preserved payloads and version gates. Post-failure probes exercised stock full parsing, cache insertion, initial SwitchSampleGroup and five four-thread trials across all 927 manifests. They passed with Linux I/O and stubbed QNX scheduling/locking.

Static helper/call/stack checks found no definite defect. Stock workers are detached and completion is polled. PIC waits for reply `0x4013`; absence of that reply is consistent with a crash or stall and does not distinguish them. Hardware FAIL takes precedence over the host PASS results.

## Diagnostic pivot and second hardware failure

**Patch location and size:** QNX; 1,056 helper-code bytes plus hook/unwind/index edits. Runtime timestamp storage adds 256 bytes to RW memory, separate from code size. This failed diagnostic is separate from the .1.3 optimization.

The next goal was measurement of normal startup stages with existing semantics preserved. The `.1.15` design proposal maps main entry, constructor, indexing, preload, initial group selection, FPGA setup, disk/audio workers, streaming and one-time main-loop entry. Those semantic addresses alone do not establish safe hook windows or target runtime behavior.

The later report records a built trace candidate, `PxUpdate_V2.2.2.1.1_boottrace.bin`, SHA-256 `9c0d96a7cc12a70a679c656ff62441f6bc5ab1b72456814481d67d841a2d0040`. Despite its `.1.1` filename, it is based on exact `.1.15`; it is unrelated to the B9 `.1.1` artifact. It hung at boot with **“Cannot reach audio processor”**. Sysex recovery did not resolve the issue, but restoring the SSD successfully resolved the issue.

No control or bisect build was reported tested. Revision mismatch was not established as the cause. An earlier diagnostic filename using `.1.17` was invalid for faithful four-bit final-component display reporting; it was not a validated alternative.

### Trace baseline and reported edits

| Input | Size | SHA-256 |
|---|---:|---|
| `.1.15` package | 3,187,784 | `ebb2aebbd0decdadce92ed40d257e0cb03ebbf7aecf3e05749d9533fd5603450` |
| `.1.15` ELF | 1,075,240 | `dd9efbcd2804e02cc4599e72d2ee90f996facce1fa06f1815a0078270566a2fa` |

The trace report describes unchanged ELF file size and PIC/FPGA records, with these application changes:

- RW LOAD `p_memsz` increases from `0x13F08` to `0x14008`, adding 256 bytes of intended timestamp storage at `0x2B21C0`. `p_filesz`, addresses, offsets and permissions remain unchanged. Target page size/mapping behavior was not verified.
- 1,056 helper bytes at `[0x1016D0,0x101AF0)` implement timestamps, wrappers and a flush to `/hd/px_boot_trace.bin`.
- Thirteen call-site windows: `0x7D5E`, `0x7E25`, `0x7E2C`, `0x7E7F`, `0x7EE3`, `0x7F70`, `0x7F81`, `0x7F89`, `0x7F97`, `0x161A3`, `0x16353`, `0x1636A`, `0x163B3`.
- Fourteen new FDEs at `[0x10277C,0x10293C)` and an unwind index growing from 909 to 923 entries; GNU_EH_FRAME size grows from `0x1C74` to `0x1CE4`.

The reported file schema is a 64-byte little-endian header (`PXBTRACE`, schema 1, 20 markers, raw baseline SHA-256 and build text), followed by 20 unsigned 64-bit nanosecond values. Zero means a marker was not recorded. No recovered hardware trace or validated decoder is available here.

### What the diagnostic checks established

A Linux/stubbed-QNX harness reported 194 checks passing for registers, stack alignment, original-call arguments/results, errno and trace contents. It did not exercise the QNX loader, expanded mapping, real file I/O or target unwind behavior.

The later static report found no direct branch/relocation into a patched window, checked hook-site stack alignment, preserved original exception call-site endings, and found the 923-entry unwind index sorted and consistent. These are reported checks. The trace implementation, build reports and candidate binary were subsequently recovered and their supplied artifact hashes checked; the original behavioral/static test suite was not independently rerun here.

The main unresolved design issue is file I/O at `0x7F97`, after streaming/audio-worker startup and before the first ProcessLoop. The message thread waits for object byte `+0x2FFC`, set only when ProcessLoop runs; blocking before then can prevent the PIC handshake. This makes flush placement a plausible cause, **not a confirmed diagnosis**. Target `clock_gettime`/open constants, page size, loader behavior and effects of delaying initial FPGA service also remain unverified.

No later trace redesign or successful diagnostic boot is recorded. There is no measured startup-stage timing on which to base a validated optimization.

### Original diagnostic proposal and its limits

The original diagnostic design used the exact .1.15 baseline identified above. Its package parsed correctly, with application/PIC revisions .1.15 and FPGA revision 0.0.0.1.0. Payload identities were:

| Payload | Bytes | SHA-256 |
|---|---:|---|
| Application | 1,075,240 | `dd9efbcd2804e02cc4599e72d2ee90f996facce1fa06f1815a0078270566a2fa` |
| FPGA | 1,581,716 | `54c70b9969c7bc6004c7ceb257a15ff1581ef82b1c3c1ad1eba185eacf15ad2b` |
| PIC | 530,784 | `be8eb8ac823a639f3024b97e01b017ef0cef5f33d086eaa71dfe55d4b0e34622` |

The proposal was design evidence, not an implemented or hardware-validated logger. In particular, its per-event records, CRCs, exclusive-create policy and per-event fsync strategy below differ from the later implemented 64-byte-header/20-timestamp format. Do not attribute those proposed durability properties to the failed trace candidate. The physical SSD executable was not independently identified at the proposal checkpoint.

Names such as `main.txt` and `preload.txt` below identify the original bounded disassembly evidence, held privately rather than distributed here. The exact .1.15 addresses and semantic findings are preserved for investigation; they do not approve reuse in another build.

### Verified hook map

Addresses below are ELF virtual addresses from direct disassembly of the exact .15 payload, not runtime absolute addresses or file offsets. Ghidra's current database uses a +0x100000 image base and contains inherited patches; its decompilation was used for orientation only. The saved exact-image assembly is authoritative. Hook boundaries are semantic proposals, not approved overwrite ranges: instruction relocation, incoming branches, live registers and unwind handling still need implementation review.

| Stage | Proposed event boundary | Verified meaning / evidence |
|---|---|---|
| Application entry | `main` starts `0x7d30`; practical early call boundary `0x7d5e` after stack/canary setup | Before first `procmgr_ability`. ELF `_start` is `0x81a0`, so label this MAIN_ENTRY, not kernel/process entry. `main.txt`, `entry.txt`. |
| Early serial setup | Before call `0x7e25`, after `0x7e2a`; optionally extend through RTS return `0x7e31` | `COMPort_Open` at `0x4a090`, then `COMPort_SetRTS(false)`. This precedes folder creation and construction. It is not a verified complete PIC handshake. `main.txt`, `serial_open.txt`. |
| Audio-loop construction | Call `0x7e7f`, return `0x7e84`; constructor starts `0x15f90` | Brackets the whole constructor. An optional constructor-entry event would distinguish call boundary from body entry; likely redundant in a coarse first pass. `main.txt`, `constructor_start.txt`. |
| Directory indexing | Call `0x161a3`, return `0x161a8` | `CSampleGroups::IndexSampleGroupFiles(-1,-1)` at `0x33db0`: releases old index, traverses `/hd` with `DSI_FTW`, then computes folder sizes for groups 1–64. Retain the whole operation. `constructor_start.txt`, `index.txt`. |
| Cache/dictionary setup | `0x16353` through `0x1636a` | Cache singleton acquisition then dictionary creation. Keep as an optional extra start marker so setup cost is not confused with parsing. `constructor_start.txt`, `cache_setup.txt`. |
| Manifest preload | Call `0x1636a`, return `0x1636f` | `CSampleGroup::CacheSampleGroups` at `0x356b0`: launches per-CPU workers and polls until all report completion, restores priority, frees temporary arrays. Worker `0x350e0` calls `GetGroupFileInfo` at `0x3527c` and populates the instrument dictionary. Thus the outer bracket includes actual parallel preload completion. No worker/per-manifest hooks proposed. `preload.txt`, `parse_worker.txt`. |
| Initial group selection | `0x1636f` through `0x163ae` | Entire nested loop: folder `(0,0,0)`, four `SwitchSampleGroup` calls (`0x16396`), cache lookup in `SwitchSampleGroup` at `0x35860`. Do not instrument the inner loop. This is constructor default group selection, not proof that the eventual panel-selected preset is ready. `constructor_start.txt`, `switch_group.txt`. |
| Hardware/engine preparation | `0x7e84` through `0x7f7e` | Acquires FPGA manager/synchronizer, initializes RAM-file support and disk scheduler, opens FPGA manager, creates message thread, starts disk-scheduler service. Several independent waits may lie within this span. `main.txt`. |
| FPGA manager open | Indirect call `0x7ee6`, return `0x7ee8` | Vtable slot 0 resolves to `CFPGAManager::Open`, `0x442c0`: PCI device attachment/configuration, mappings, DMA/descriptors and interrupt setup. Record original return value without changing its test. This is application interaction with existing hardware, not a firmware modification. `elf_layout_vtable.txt`, `fpga_open.txt`. |
| Disk scheduler start | Indirect call `0x7f73`, return `0x7f76` | Scheduler vtable slot +8 invoked with argument 1; retain original return test. Use neutral event naming until concrete scheduler method is separately resolved. `main.txt`. |
| Audio workers launch | Call `0x7f81`, return `0x7f86` | `StartAudioProcessThreads`, `0x18710`, creates two pre-LPF workers and one post-LPF worker with channels/connections. Return proves launch function completion, not worker readiness. `audio_threads.txt`. |
| Streaming enable/wait | Indirect call `0x7f8c`, return `0x7f8f` | Vtable +0x10 resolves to `StartStreaming`, `0x42e00`. It enables hardware streaming then polls a mapped status bit without timeout. A begin marker without end would localize a hang here. Preserve this wait exactly. `elf_layout_vtable.txt`, `stream_start.txt`. |
| Enter normal main loop | `0x7f97` on successful start, before loop target `0x7fa0` | One-time fall-through through an existing nine-byte NOP; the loop backedges target `0x7fa0`, so a hook at `0x7f97` need not run every audio block. Distinguish LOOP_ENTER from full UI readiness. `main.txt`. |

The shared boundary `0x1636f` can encode PRELOAD_END_SELECTION_BEGIN in one event. Likewise constructor return and hardware-preparation begin can share an event. Coarse trace: about 20 records, fewer than 1 KiB with the format below.

### Normal operation and progress-bar limits

PASS: main waits for streamed data via vtable +0x18 (`WaitForStreamedData`, `0x439c0`), then runs `ProcessLoop` or `NullProcessLoop`. The first `ProcessLoop` call site is `0x7fe5`.

PASS: .15 already redirects `ProcessLoop` at `0x1b49e` to `0x4a071`, which locks `startup_mutex` and returns to `0x1b4a9` to set object byte +0x2ffc. The message thread polls that byte at `0x1d5f2`/`0x1d60a`; after it opens the message interface it calls `HandleMessage(0x4013,0)` at `0x1d648`, then enters its receive loop. Preserve this inherited synchronization. Do not assume constructor return means message initialization is finished.

NOT VERIFIED: final boot-bar event, complete PIC handshake, user-ready preset completion, first audible/DAC-ready sample. `shutdown_progress` is a shutdown stub and is not evidence of boot progress. The first pass should avoid speculative progress markers. A later one-shot marker at the first processing call or initial message-handler return can resolve the post-loop gap, but logging in those concurrent paths needs its own reviewed ownership design; it is excluded from the main-thread-only helper proposed here.

Bootloader, IFS device bring-up/mounting and loader/static constructors occur before MAIN_ENTRY. These cannot be timed by this main-only trace. Do not subtract monotonic uptime and call the result application startup time; use event differences. No IFS changes are needed.

### Proposed shared helper

Use QNX `clock_gettime(CLOCK_MONOTONIC, &ts)` through existing PLT `0x7510`. Existing application calls pass clock ID 2; compile-time target headers must verify CLOCK_MONOTONIC and the 64-bit `timespec` layout rather than importing host/Linux constants. Also already imported: `open` (`0x75a0`), `write`, `fsync` (`0x72c0`), `close` (`0x7810`), and `__get_errno_ptr`. No new import dependency is needed.

One main-thread-owned static descriptor/state, no heap allocations, text formatting, strings built at runtime, background thread, mutex, per-file logging, priority change or change to existing work order. Header includes magic, schema version, record size, baseline application hash and diagnostic build identity (when assigned). Store explicit little-endian fields; do not dump native structs with unspecified padding.

Proposed 32-byte record: event ID u32, sequence u32, monotonic nanoseconds u64, previous helper's completion timestamp u64, CRC32 u32, status/flags u32. Header and a maximum of 64 records stay below 3 KiB. CRC and sequence let the offline decoder reject a torn/truncated tail; they are corruption detection, not a claim of atomic SSD writes.

At earliest main hook, capture entry time before opening the file. Open `/hd/px_boot_trace.bin` once with target-header O_WRONLY|O_CREAT|O_EXCL, mode 0600. An existing trace disables tracing for this boot, preserving hang evidence; retrieve/rename it before another deliberate test. Do not truncate it automatically, and do not put it in `/tmp`. Emit a second TRACE_READY event after header/entry persistence to expose open/header overhead. The main-entry timestamp is captured after the prologue and does not include `_start` or static initialization.

Recommended recovery policy for the first diagnostic test: one fixed-size write followed by `fsync(fd)` per coarse event. `write` alone only establishes acceptance into filesystem buffers; `close` at successful startup cannot protect a trace from an earlier hang. Avoid redundant O_SYNC plus fsync, and avoid global `sync`, which would flush unrelated activity. Durability has overhead: measure it, do not describe it as free or constant-time.

Take a timestamp immediately before persistence and another after write/fsync completes; carry completion in the next record. For adjacent events A and B, B.timestamp minus A.timestamp is raw elapsed time; B.timestamp minus B.previous_completion estimates intervening application work, excluding A's helper I/O. Report both and the measured I/O cost. This accounts for direct helper cost, not cache/scheduling perturbation, so coarse intervals remain observational estimates. The last marker's persistence overhead is unavailable if there is no next record. A missing end marker means only that the next marker was not durably observed; it does not by itself distinguish an application hang from blocked trace I/O.

Save/restore errno and all site-live GPRs, flags, vector/FP state and original call return values as required. Maintain x86-64 ABI stack alignment, relocate complete instructions and RIP-relative operands, preserve existing exception/unwind behavior, and keep injected helper code nonthrowing. Call wrappers must execute the original target exactly once with unchanged arguments and return behavior. Selection boundary has live registers; return-site hooks precede tests, so flags/results cannot be casually clobbered. No approved patch ranges or helper placement are implied by this proposal.

On open/clock/write/fsync error, disable tracing and continue original startup. A short write may be completed with a strictly bounded retry budget; disable after failure rather than an unbounded retry loop. Close once where possible; no retries or sleeps. This bounds helper logic, not filesystem syscall latency: synchronous disk I/O itself can block. Stop recording after LOOP_ENTER and close at that one-time boundary; do not introduce ongoing audio-loop logging.

### Recovery evidence and remaining checks

QNX documentation confirms the monotonic clock is not adjustable and that fsync forces delayed-write blocks out. It also distinguishes filesystem cache flushing from storage-device cache/power-loss behavior. Therefore records whose fsync returned are the intended recoverable prefix after an application-only hang; power-cut survival on this particular SSD/driver/filesystem is NOT VERIFIED. A kernel/storage hang can also prevent persistence. Retain the failed SSD and recover read-only after the test.

The proposal called for the following checks before implementation: inspect actual `/hd` filesystem, mount/commit settings, storage flush support, target headers and helper syscall latency in the maintenance environment; verify intended hook byte ranges and placement against exact .15; review the inherited startup-mutex path. Nothing here authorizes changing the mount, IFS or rollback script. A host model cannot establish crash durability. The proposal required any later package to keep the complete .15 PIC and FPGA records byte-identical, including their revision fields, unless that constraint was explicitly changed.

Sources:
- https://www.qnx.com/developers/docs/6.5.0SP1/neutrino/lib_ref/c/clock_gettime.html
- https://qnx.com/developers/docs/6.5.0SP1.update/com.qnx.doc.neutrino_utilities/i/io-blk.so.html
- https://qnx.com/developers/docs/6.5.0SP1.update/com.qnx.doc.neutrino_utilities/f/fs-qnx6.so.html

## Source availability and historical packaging path

`support/` retains v3/v4 helper source, host tests, integration tools, `.1.2`-based packaging/verification and post-failure probes. The source explains what was attempted; none of these tools creates an accepted release.

The `.1.3` path applies the v4 helper to a private exact `.1.2` ELF using the integration contract, then `support/B13_on_1.2/build_package.py` sets the application header and embedded revision bytes to `.1.3`, recalculates its little-endian word checksum and preserves complete FPGA/PIC records. `verify_package.py` and the recorded final report audit the output. The original scripts contain private/absolute paths, expected generated objects and original upload layouts; they require adaptation and exact input identity checks for offline investigation. The copied integration applicator's default object path also needs checking against the retained sibling `B13_v4_review/` directory.

The diagnostic source and packager were recovered from `boottrace_everything.zip` during the version-history audit. The authored NASM helper, hash include, ELF/container builders, three build reports and Linux host harness are now in `support/boottrace/`. The supplied full trace package matches the recorded SHA-256 `9c0d96a7cc12a70a679c656ff62441f6bc5ab1b72456814481d67d841a2d0040`. Firmware, original disassembly, helper listing and overlapping narrative reports remain in the private archive. The separately recovered [decode_trace.py](support/boottrace/decode_trace.py) matches the actual embedded header and marker IDs; its [compatibility report](support/boottrace/decoder_validation.json) records synthetic round-trip, missing-marker and malformed-input checks. No hardware trace output was supplied.

The archive also contains three **untested** diagnostic variants: `CONTROL_unpatched`, `BISECT_noop` and `BISECT_stamps`, all named `.1.1` but derived from `.1.15`. Their existence is not evidence they booted. `noop` still includes helper/unwind/memory-map changes; it omits call-site patches, so it is not the unpatched control. `stamps` excludes the final LOOP_ENTER flush hook.

For historical offline reproduction, the trace builders accept `--workspace PATH` and mode `full`, `stamps` or `noop`. Supply exact .1.15 inputs as `in/voice.elf` and `in/pkg.bin` beneath that private workspace; generated outputs go to `work/`. NASM loads `trace.asm` and `sha.inc` from the source directory. The Linux harness generator accepts `--work-dir PATH` containing assembled `stubs.bin`. These tools use QNX stubs and cannot establish target boot behavior; see the supporting-script inputs below. No builder for the separate `CONTROL_unpatched` package was found.

Firmware, ELF/PIC/FPGA payloads, compiled objects, helper binaries, SSD images and sample manifests are excluded. Rebuilding or flashing withdrawn packages is not part of this handover task. Any renewed work needs a separately requested investigation; no failure cause or safe replacement build is claimed here.

## Complete supporting-file inventory

Every retained file is linked below. The original proposal and SSD postmortem are integrated above; supporting technical audit documents remain linked below; overlapping progress handovers and historical flashing checklists are archived privately. [inventory.json](inventory.json) records public paths, sizes and hashes; [SHA256SUMS](SHA256SUMS) covers the handover, inventory and support files.

### Technical reference documents

| File | Purpose |
|---|---|
| [RECOVERY.md](../../RECOVERY.md) | Windows/QEMU SSD application recovery procedure, evidence export and readback verification. |

### Original v3 implementation and tests

| File | Purpose |
|---|---|
| [support/B13_implementation_v3/VALIDATION_OUTPUT.txt](support/B13_implementation_v3/VALIDATION_OUTPUT.txt) | Captured host/static validation output. |
| [support/B13_implementation_v3/b13_fast_uuid_v3.S](support/B13_implementation_v3/b13_fast_uuid_v3.S) | Fast-manifest helper assembly source. |
| [support/B13_implementation_v3/build_b13_uuid_v3_candidate.py](support/B13_implementation_v3/build_b13_uuid_v3_candidate.py) | Historical builder, verifier, decoder or host probe; private inputs required. |
| [support/B13_implementation_v3/test_b13_uuid_v3.c](support/B13_implementation_v3/test_b13_uuid_v3.c) | Host harness or stock-call wrappers. |
| [support/B13_implementation_v3/validate_b13_uuid_v3_candidate.py](support/B13_implementation_v3/validate_b13_uuid_v3_candidate.py) | Historical builder, verifier, decoder or host probe; private inputs required. |

### Revised v4 implementation and real-manifest audit

| File | Purpose |
|---|---|
| [support/B13_v4_review/audit_real_manifests.py](support/B13_v4_review/audit_real_manifests.py) | Historical builder, verifier, decoder or host probe; private inputs required. |
| [support/B13_v4_review/b13_fast_uuid_v4.S](support/B13_v4_review/b13_fast_uuid_v4.S) | Fast-manifest helper assembly source. |
| [support/B13_v4_review/build_b13_uuid_v4_candidate.py](support/B13_v4_review/build_b13_uuid_v4_candidate.py) | Historical builder, verifier, decoder or host probe; private inputs required. |
| [support/B13_v4_review/build_validation.txt](support/B13_v4_review/build_validation.txt) | Captured host/static validation output. |
| [support/B13_v4_review/readme_B13_v4_audit.md](support/B13_v4_review/readme_B13_v4_audit.md) | Historical technical findings/design; abandoned status above is authoritative. |
| [support/B13_v4_review/host_validation.txt](support/B13_v4_review/host_validation.txt) | Captured host/static validation output. |
| [support/B13_v4_review/real_audit_wrappers.c](support/B13_v4_review/real_audit_wrappers.c) | Host harness or stock-call wrappers. |
| [support/B13_v4_review/real_manifest_v3_results.json](support/B13_v4_review/real_manifest_v3_results.json) | Saved contract, identity, validation or real-manifest audit evidence. |
| [support/B13_v4_review/real_manifest_v4_results.json](support/B13_v4_review/real_manifest_v4_results.json) | Saved contract, identity, validation or real-manifest audit evidence. |
| [support/B13_v4_review/structural_validation.txt](support/B13_v4_review/structural_validation.txt) | Captured host/static validation output. |
| [support/B13_v4_review/test_b13_uuid_v4.c](support/B13_v4_review/test_b13_uuid_v4.c) | Host harness or stock-call wrappers. |
| [support/B13_v4_review/validate_b13_uuid_v4_candidate.py](support/B13_v4_review/validate_b13_uuid_v4_candidate.py) | Historical builder, verifier, decoder or host probe; private inputs required. |

### Integration contracts and host checks

| File | Purpose |
|---|---|
| [support/B13_integration_prep/apply_b13_to_elf.py](support/B13_integration_prep/apply_b13_to_elf.py) | Historical builder, verifier, decoder or host probe; private inputs required. |
| [support/B13_integration_prep/cache_caller_results.json](support/B13_integration_prep/cache_caller_results.json) | Saved contract, identity, validation or real-manifest audit evidence. |
| [support/B13_integration_prep/check_cache_callers.py](support/B13_integration_prep/check_cache_callers.py) | Historical builder, verifier, decoder or host probe; private inputs required. |
| [support/B13_integration_prep/check_startup_dictionary.py](support/B13_integration_prep/check_startup_dictionary.py) | Historical builder, verifier, decoder or host probe; private inputs required. |
| [support/B13_integration_prep/integration_contract.json](support/B13_integration_prep/integration_contract.json) | Saved contract, identity, validation or real-manifest audit evidence. |
| [support/B13_integration_prep/integration_tool_validation.json](support/B13_integration_prep/integration_tool_validation.json) | Saved contract, identity, validation or real-manifest audit evidence. |
| [support/B13_integration_prep/startup_dictionary_results.json](support/B13_integration_prep/startup_dictionary_results.json) | Saved contract, identity, validation or real-manifest audit evidence. |
| [support/B13_integration_prep/validate_prep_tools.py](support/B13_integration_prep/validate_prep_tools.py) | Historical builder, verifier, decoder or host probe; private inputs required. |
| [support/B13_integration_prep/verify_extracted_payloads.py](support/B13_integration_prep/verify_extracted_payloads.py) | Historical builder, verifier, decoder or host probe; private inputs required. |

### Withdrawn .1.3 packaging and validation

| File | Purpose |
|---|---|
| [support/B13_on_1.2/b13_qnx_preserved_revision.receipt.json](support/B13_on_1.2/b13_qnx_preserved_revision.receipt.json) | Saved contract, identity, validation or real-manifest audit evidence. |
| [support/B13_on_1.2/baseline_records.json](support/B13_on_1.2/baseline_records.json) | Saved contract, identity, validation or real-manifest audit evidence. |
| [support/B13_on_1.2/build_package.py](support/B13_on_1.2/build_package.py) | Historical builder, verifier, decoder or host probe; private inputs required. |
| [support/B13_on_1.2/cache_caller_validation.json](support/B13_on_1.2/cache_caller_validation.json) | Saved contract, identity, validation or real-manifest audit evidence. |
| [support/B13_on_1.2/check_application_version_gate.py](support/B13_on_1.2/check_application_version_gate.py) | Historical builder, verifier, decoder or host probe; private inputs required. |
| [support/B13_on_1.2/extracted_payload_mapping.json](support/B13_on_1.2/extracted_payload_mapping.json) | Saved contract, identity, validation or real-manifest audit evidence. |
| [support/B13_on_1.2/final_package_validation.json](support/B13_on_1.2/final_package_validation.json) | Saved contract, identity, validation or real-manifest audit evidence. |
| [support/B13_on_1.2/package_build_manifest.json](support/B13_on_1.2/package_build_manifest.json) | Saved contract, identity, validation or real-manifest audit evidence. |
| [support/B13_on_1.2/package_validation.json](support/B13_on_1.2/package_validation.json) | Saved contract, identity, validation or real-manifest audit evidence. |
| [support/B13_on_1.2/payload_preservation_validation.json](support/B13_on_1.2/payload_preservation_validation.json) | Saved contract, identity, validation or real-manifest audit evidence. |
| [support/B13_on_1.2/startup_dictionary_validation.json](support/B13_on_1.2/startup_dictionary_validation.json) | Saved contract, identity, validation or real-manifest audit evidence. |
| [support/B13_on_1.2/structural_validation.txt](support/B13_on_1.2/structural_validation.txt) | Captured host/static validation output. |
| [support/B13_on_1.2/tools/apply_b13_to_elf.py](support/B13_on_1.2/tools/apply_b13_to_elf.py) | Historical builder, verifier, decoder or host probe; private inputs required. |
| [support/B13_on_1.2/tools/check_cache_callers.py](support/B13_on_1.2/tools/check_cache_callers.py) | Historical builder, verifier, decoder or host probe; private inputs required. |
| [support/B13_on_1.2/tools/check_startup_dictionary.py](support/B13_on_1.2/tools/check_startup_dictionary.py) | Historical builder, verifier, decoder or host probe; private inputs required. |
| [support/B13_on_1.2/tools/integration_contract.json](support/B13_on_1.2/tools/integration_contract.json) | Saved contract, identity, validation or real-manifest audit evidence. |
| [support/B13_on_1.2/tools/verify_extracted_payloads.py](support/B13_on_1.2/tools/verify_extracted_payloads.py) | Historical builder, verifier, decoder or host probe; private inputs required. |
| [support/B13_on_1.2/validate_candidate_structure.py](support/B13_on_1.2/validate_candidate_structure.py) | Historical builder, verifier, decoder or host probe; private inputs required. |
| [support/B13_on_1.2/verify_package.py](support/B13_on_1.2/verify_package.py) | Historical builder, verifier, decoder or host probe; private inputs required. |
| [support/B13_on_1.2/version_gate_validation.json](support/B13_on_1.2/version_gate_validation.json) | Saved contract, identity, validation or real-manifest audit evidence. |

### Post-failure probes

| File | Purpose |
|---|---|
| [support/B13_boot_failure/findings.md](support/B13_boot_failure/findings.md) | Historical technical findings/design; abandoned status above is authoritative. |
| [support/B13_boot_failure/full_cache_probe.py](support/B13_boot_failure/full_cache_probe.py) | Historical builder, verifier, decoder or host probe; private inputs required. |
| [support/B13_boot_failure/full_cache_probe_results.txt](support/B13_boot_failure/full_cache_probe_results.txt) | Captured host/static validation output. |
| [support/B13_boot_failure/pic_decode.py](support/B13_boot_failure/pic_decode.py) | Historical builder, verifier, decoder or host probe; private inputs required. |

### Recovered trace-baseline evidence

| File | Purpose |
|---|---|
| [support/instrumentation_design_1_15/baseline_verification.json](support/instrumentation_design_1_15/baseline_verification.json) | Saved contract, identity, validation or real-manifest audit evidence. |

Cleanup checks: public Python/JSON syntax, documentation links, complete inventories and binary exclusions PASS. No historical firmware tests, builds or device actions were rerun. Diagnostic source and four packages were subsequently recovered and audited as described above; the decoder and withdrawn `.1.3` package were subsequently recovered as well; actual hardware trace output remains unavailable.

### Recovered boot-trace implementation and host harness

- [build_elf.py](support/boottrace/source/build_elf.py)
- [build_pkg.py](support/boottrace/source/build_pkg.py)
- [build_report.json](support/boottrace/source/build_report.json)
- [build_report_noop.json](support/boottrace/source/build_report_noop.json)
- [build_report_stamps.json](support/boottrace/source/build_report_stamps.json)
- [sha.inc](support/boottrace/source/sha.inc)
- [trace.asm](support/boottrace/source/trace.asm)
- [harness.c](support/boottrace/test_harness/harness.c)
- [mk_test.py](support/boottrace/test_harness/mk_test.py)
- [stubs.asm](support/boottrace/test_harness/stubs.asm)

### Recovered trace decoder

- [decode_trace.py](support/boottrace/decode_trace.py): standard-library Python decoder for the 64-byte `PXBTRACE` schema-1 header and 20 unsigned 64-bit nanosecond timestamps. Zero means not reached. Run `python3 decode_trace.py /private/path/px_boot_trace.bin`; `--make-sample` creates explicitly fake data for checking the decoder.
- [decoder_validation.json](support/boottrace/decoder_validation.json): compatibility checked against the actual failed ELF’s embedded header and the source marker assignments. Six synthetic/negative checks passed. This is not a real hardware trace or startup measurement. The decoder displays the baseline hash/build identity rather than enforcing an exact match; verify those fields before interpreting a file. Its historical address comments are reference notes; the implementation sources define actual hook locations.

### Supporting script inputs

Keep firmware inputs and generated binaries in a private working directory. The archived boottrace builders accept `--workspace PATH` and an optional mode (`full`, `stamps`, or `noop`). That workspace contains `in/voice.elf` and `in/pkg.bin` from the exact .1.15 baseline; outputs go to `work/`. NASM loads `trace.asm` and `sha.inc` beside the builder. For example:

```sh
python3 support/boottrace/source/build_elf.py full --workspace /path/to/private-workspace
python3 support/boottrace/source/build_pkg.py full --workspace /path/to/private-workspace
```

The host harness generator accepts `--work-dir PATH`, containing an assembled `stubs.bin`; generated harness files and `out_trace.bin` use that directory. Run the compiled harness there.

The v3 builder takes `BASELINE_ELF OBJECT_FILE OUTPUT_ELF` and optionally `--objcopy TOOL`; its validator takes `BASELINE_ELF CANDIDATE_ELF`. Section extracts are written beside the output ELF. These scripts reproduce investigation candidates, which remain abandoned.
