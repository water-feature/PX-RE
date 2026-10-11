# B11: closure of the 276-byte candidate

## Verdict

**Implementation NO-GO. Storage is feasible for the corrected primary-bank algorithm: 268 active instruction bytes plus 8 padding bytes, independently assembled into the same 276 bytes.** There is no demonstrated byte shortfall for that algorithm. This is not a proof that the complete requested behavior is impossible in 276 bytes. Two correctness issues prevent approval: mixed-bank Both Layers semantics and cache freshness. Claiming a minimum shortfall for their unresolved solutions would be speculation.

No firmware, version, package, other patch, or loaded Ghidra database was changed. All scratch writes are under `b11_placement_scratch/`. Only the authorized report, prior authorized inputs, authorized PIC image, and our own scratch files were read as project inputs.

## Image identity

The active Ghidra listing has the raw image at `9D000000–9D08195F`, length `0x81960`. The authorized `b10_ordinary_entry_design_1_12/candidate_1_15/reextracted_pic.bin` has the same length and SHA-256:

`be8eb8ac823a639f3024b97e01b017ef0cef5f33d086eaa71dfe55d4b0e34622`

Its decoded Type instructions match the loaded listing, including the category setter, Group routes and refresh code. This is anchor correspondence, not a byte-for-byte export/hash of the Ghidra database. Revision **2.2.2.1.15 is user-established**; no package manifest or embedded revision was independently verified. No assumption of 2.2.2.1.7 is made.

## Both Layers: stock uses a primary-bank absolute target

Type is event case 16 through `9D029348 -> 9D02A74C`. That dispatch and Type entry contain no exclusion of edit value 2. UI code explicitly recognizes `UI+44 == 2` at `9D01E714`. Thus Both Layers must be covered; treating this as a single-layer-only handler is unsafe.

The getter selects bank A for edit 0 **and 2**, bank B otherwise:

```asm
9D04D300 andi  a0,a0,0xfffd
9D04D304 bnel  a0,zero,9D04D30C
9D04D308  addiu a1,a1,0x6b7
9D04D30C sll   a1,a1,1
9D04D310 lui   v0,0x8000
9D04D314 addiu v0,v0,0x46c
9D04D318 addu  a1,a1,v0
9D04D31C jr    ra
9D04D320  lhu v0,0(a1)
```

The relative setter similarly chooses one current category, calls the clamp at `9D0816E0`, and passes one absolute result to `9D04DACC`:

```asm
9D04FA84 andi  v0,a1,0xfffd
9D04FA94 beq   v0,zero,9D04FAF8
9D04FA98  lw a2,0x30(sp)       # maximum, caller's stack+10
...                          # alternate-bank current category
9D04FAB4 jal   9D0816E0       # clamp(current + delta, 0, maximum)
9D04FAB8  nop
9D04FABC andi  a3,v0,0xffff   # one absolute target
...
9D04FAF0 j     9D04DACC
9D04FAF4  addiu sp,sp,0x20
```

In the absolute setter, edit 2 takes both bank paths. Bank A is stored at `9D04DE6C`; bank B at `9D04DFC0`. The transition at `9D04DB7C–84` decrements edit 2 to 1 and continues into bank B. `s3` retains the common absolute category across these paths. Existing patch interceptors are retained; the category parameters 0x24/0x65 take their ordinary paths.

**Stock does not independently increment two different starting categories.** For example, A category 2/B category 12 with positive Type produces common category 3. The corrected candidate preserves this primary-master contract, rather than incorrectly applying a common delta independently to B.

However, primary-master filtering does **not** establish the whole requested behavior when groups differ:

* A nonfactory populated result can be empty in B's different nonfactory group.
* A nonfactory primary skip can advance a Factory secondary bank by multiple categories.
* A Factory primary bypass can select an empty category in a nonfactory secondary bank.

With stock's common-target semantics, a Factory target that is empty in the other bank cannot simultaneously retain the Factory step and be a populated target in both banks. An explicit mixed-bank policy is required before calling a single-bank search correct. No independent per-bank navigation or change to stock coupling was silently introduced.

## Real category/instrument adjustment

The ordinary category write is clamped by `9D04D4FC` using the category descriptors (max 16 at `9D047648` and `9D047954`). The setter then restores the remembered instrument selection and validates it against the new group's/category's count. Instrument 1 paths include `9D04DEAC–DEC8` and `9D04E000–E01C`; Instrument 2 equivalents are `9D04E53C–E558` and `9D04E614–E630`.

```asm
9D04DECC lhu   a0,0x44(s1)    # bank A Instrument 1 group
9D04DED0 jal   9D0792E0
9D04DED4  lhu a1,0x48(s1)     # category
9D04DED8 slt   v0,s4,v0       # remembered instrument < count?
9D04DEDC beql  v0,zero,9D04E6F4
9D04DEE0  lhu a0,0x44(s1)
...
9D04E6F4 jal   9D0792E0
9D04E6F8  lhu a1,0x48(s1)
9D04E6FC andi  a2,v0,0xffff
9D04E700 clear a0
9D04E704 jal   9D04D4FC
9D04E708  li a1,0x23
9D04E710 sh    v0,0x46(s1)
...
9D04D620 jal   9D0792E0
9D04D624  nop
9D04D628 addiu v0,v0,-1       # highest valid instrument = count - 1
9D04D62C andi  v0,v0,0xffff
```

Thus a remembered valid instrument survives; an excessive value clamps to count-1, including placeholder zero in an empty category. Loading/notification continues through the existing setter. The search does not write category/instrument parameters or replace these paths.

## Count contract, bounds and lifecycle

`9D0792E0` is exactly a pure, unchecked load:

```asm
9D0792E0 sll   v0,a0,4
9D0792E4 addu  a0,v0,a0
9D0792E8 addu  a1,a0,a1
9D0792EC sll   v0,a1,3
9D0792F0 lui   v1,0x8003
9D0792F4 addiu v1,v1,0x7e90
9D0792F8 jr    ra
9D0792FC  lwx v0,v0(v1)
```

Record address: `80037E90 + 8*(17*group + category)`, 65 groups, 17 categories. It clobbers a0/a1/v0/v1, preserves the candidate's t registers and a2/a3, and causes no communication, cache fill, instrument selection or loading. The revised candidate calls this existing routine rather than duplicating its addressing.

`9D040ED8` reads raw byte counts from persistent page `005FD000`, adds one (`9D040F8C`), and writes the expanded count. **Normal empty = 1; populated = N+1 >= 2.** The second word is cumulative index for populated records, `FFFFFFFF` for count <2. Legacy unused groups are explicitly filled `{1, FFFFFFFF}` at `9D040FF8/FFC`. The first byte FF selects the extended 65-group page format. An FF elsewhere becomes count 256; it is not an established unavailable marker. There is no recovered per-record validity/generation field. Stale entries have the same representation as current entries; unavailable cannot reliably be inferred from a distinct cached value.

Normal group limits are 64 in both descriptors (`9D047630`, `9D04793C`). Ordinary setters clamp through the descriptor table; bulk parameter validation at `9D04D6D4–D728` validates both banks, replacing values above each descriptor maximum with its default. Calls follow preset loads at `9D0267B8`, `9D0269B0`, `9D026C04`, `9D07824C`, `9D0783B8`; `9D07C478` also validates before rebuilding parameter state. This supports bounds for ordinary validated states, rather than arbitrary corrupt RAM. The candidate checks every candidate category before calling the unchecked getter, and performs at most 16 alternative-category reads from a valid starting category. Invalid starting categories exit without a count read.

Initialization is explicit: `9D0530E4 -> 9D079220 -> 9D040ED8`. Rebuild callers `9D01B904` and `9D02453C` run `9D042A8C`, then `9D042B80`, then `9D040ED8` before continuing. Expanded-cache construction is synchronous; its count loads are flash I/O, distinct from the pure getter.

**Freshness remains a concrete blocker:** the rebuild route at `9D02277C` calls `9D042A8C` and `9D042B80`, then returns through `9D021BB0` without the explicit expanded-cache reconstruction seen in the other routes. `9D042A8C` stages 65*17 fresh results from the blocking communication routine `9D079978`, writes the persistent page, and does not itself call `9D040ED8`. The recovered direct-call scan found only the three builder call sites above. This establishes a route needing further lifecycle explanation, not proof of actual stale counts on every execution. No complete asynchronous invalidation/refresh guarantee was established. Raw count reads are equivalent to stock reads, but are not proof of current real instrument availability. No new messages or full flash rebuild were added to Type.

## Ownership: correction to the previous report

The four rewritten ranges remain exactly:

| Half-open range | Bytes |
|---|---:|
| 9D02A74C–9D02A7BC | 112 |
| 9D02D428–9D02D484 | 92 |
| 9D02DD08–9D02DD2C | 36 |
| 9D02DEF8–9D02DF1C | 36 |
| Total | 276 |

Missing predecessors now decode as:

```asm
9D02A740 addiu a1,s0,0x44
9D02A744 j     9D0291C8
9D02A748  clear v0
...
9D02DCF8 jal   9D036A28
9D02DCFC  clear a2
9D02DD00 j     9D02A200
9D02DD04  lui v0,0x9d03
```

Together with the previously decoded jumps at `9D02D420/424` and `9D02DEF0/F4`, all four predecessors branch away. No unrelated fallthrough into a rewritten range was found. `9D02A7BC` continues the shared UI path and is untouched.

**The previous Ghidra-only incoming-reference inventory was incomplete.** Scanning every aligned raw word for full-address pointers and direct MIPS branch/jump targets found six additional live incoming Group edges:

```asm
9D02EB14 beq v0,s1,9D02D464
9D02EB54 j         9D02D464
9D02EB60 beq v0,zero,9D02D464
9D02EC18 beq v0,s1,9D02A794
9D02EC58 j         9D02A794
9D02EC64 beq v0,zero,9D02A794
```

These are Group boundary and successful-navigation returns. The original 276-byte sketch breaks them. **The corrected sketch retains the original six refresh instructions at 9D02A794 and the original six refresh instructions plus UI join at 9D02D464.** It retains the dispatch address and Group routing. No Group instruction outside the four ranges changes.

The only aligned full-address pointer into the ranges is `9D029348 -> 9D02A74C`. All direct incoming edges are now accounted for, including these Group entries. The known computed entry is bounded dispatch table case 16 at `9D029300`; other entries in that table target other case bodies. A local raw LUI/addiu/ori construction scan found no additional constructed addresses into the ranges. This scan is supplementary evidence, not an exhaustive theorem about arbitrary computed control flow. The claimed allocation is occupied Type/shared-refresh code with retained public entries, never FF bytes or undefined functions. No other patch is compacted or allocated.

## Corrected measured candidate

`b11_placement_scratch/measure_corrected.py` emits isolated fragments only, never opens firmware, and interprets the emitted words. The corresponding listing and independent toolchain sources/object are under `b11_placement_scratch/corrected/`.

Important revised instructions:

```asm
9D02A770 lhu   a0,0x44(s0)
9D02A774 jal   9D04D300      # existing getter returns category and its address in a1
9D02A778  move a1,a2
9D02A77C lhu   t0,-4(a1)    # matching group
9D02A780 move  t2,v0        # original category
...
9D02D444 addiu a3,t3,-1     # normalized direction, t3 is 0 or 2
9D02D448 li    v0,16
9D02D44C sw    v0,0x10(sp)
9D02D450 beq   t0,zero,9D02DEF8 # Factory uses stock +/-1 setter
9D02D454  move t3,t2
9D02D458 addu  t3,t3,a3
9D02D45C b     9D02DD08
9D02D460  sltiu t4,t3,17
...
9D02DD08 beq   t4,zero,9D02DF04
9D02DD0C  move a0,t0
9D02DD10 jal   9D0792E0
9D02DD14  move a1,t3
9D02DD18 sltiu v0,v0,2
9D02DD1C bne   v0,zero,9D02D458
9D02DD20  nop
9D02DD24 b     9D02DEF8
9D02DD28  subu a3,t3,t2
...
9D02DEF8 lhu   a1,0x44(s0)
9D02DEFC jal   9D04FA6C
9D02DF00  clear a0
9D02DF04 beq   s3,zero,9D02A794
9D02DF08  nop
9D02DF0C b     9D02D464
9D02DF10  nop
```

Both directions and instruments share the scan. No forward populated candidate means no setter call; stock refresh/UI continuation still runs. Clamping is retained, with no wrap. Instrument selection is delegated to the real setter. The enclosing frame already preserves s3; no new frame or persistent RAM is required.

| Budget item | Measured bytes |
|---|---:|
| Four emitted replacement fragments | 276 |
| Active instructions | 268 |
| Unreachable trailing padding at 9D02DF14/18 | 8 |
| Outside helper/adapters/trampolines/alignment | 0 |
| Additional persistent RAM, tables, preset fields, messages | 0 |
| Proven shortfall for this primary-bank candidate | 0 |

The 8 trailing bytes are inside its owned range; they are not evidence of a separate cave or automatically sufficient for a complete freshness/mixed-bank correction.

Independent verification used Rust 1.83.0's LLVM MIPS assembler (`mipsel-unknown-none`, `mips32r2`, noreorder/noat), emitting an ELF object from assembly. All 69 words match the explicit subset encoder, with no unresolved relocations. Sparse object padding and dummy external Group labels are tool artifacts, not firmware storage. `corrected/verification.txt` records the comparison. Apple clang's missing MIPS backend was bypassed without installing packages.

**1,632 modeled cases pass** for both instruments, edit values 0/1/2, every category, both directions, six population patterns, Factory bypass, Group routing, setter arguments and refresh order. Getter/count clobbers are modeled from their actual instructions. The setter itself remains mocked: this is not hardware validation, mixed-bank population verification, or proof of cache freshness.

## Decision

The missed ownership entries and independent encoding gaps are closed for the corrected sketch. Stock coupled setter semantics and instrument adjustment are established. Ordinary-state group/category bounds and initialization have positive evidence.

**Do not implement yet.** Resolve the mixed-bank policy against the stated Factory/nonfactory requirements, and explain the cache refresh/invalidation route at `9D02277C` before asserting current population counts. No complete corrected algorithm for those two issues has been specified, so its byte cost and any eventual shortfall are not established. The evidence supports an in-place storage opportunity, not unconditional implementation approval or a claim that 276 bytes is impossible.
