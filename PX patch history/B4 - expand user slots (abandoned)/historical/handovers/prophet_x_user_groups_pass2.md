# Branch 4 — preset encoding and PIC bounds, pass 2

2 October 2026, Australia/Brisbane. Continues pass 1 on clean official 2.2.2.0.0. Static disassembly plus actual PIC instruction emulation. No firmware file patched or hardware tested.

## Outcome

64 user groups is representable by the inspected preset and message formats. The inspected formats can also represent ID 132 (the last existing u99 name). The earlier hypothetical seven-bit/95-user ceiling is **not imposed by these paths**: MIDI SysEx packs each byte's high bit separately and restores it. This does not establish that every UI, NRPN, import or metadata path supports 100 user groups.

Stock has two important limits: individual group parameter edits clamp to ID 64; bulk preset validation resets above-limit group IDs to the default 0. Both must change together. Extending limits before relocating/rebuilding the indexed tables would permit out-of-bounds reads.

## Identified sample parameters

| Parameter | Purpose | Stock max | Default | Byte in stored part A | Byte in stored part B |
|---|---|---:|---:|---|---|
| 0x22 | Sample oscillator 1 group | 64 | 0 | 0x22 | 0x822 |
| 0x23 | Oscillator 1 instrument | 255 | 0 | 0x23 | 0x823 |
| 0x24 | Oscillator 1 category | 16 | 12 | 0x24 | 0x824 |
| 0x63 | Sample oscillator 2 group | 64 | 0 | 0x63 | 0x863 |
| 0x64 | Oscillator 2 instrument | 255 | 0 | 0x64 | 0x864 |
| 0x65 | Oscillator 2 category | 16 | 12 | 0x65 | 0x865 |

The group/category/instrument identities are verified by PIC validation calls and QNX's sample-switch dispatcher. Runtime PIC parameter base is RAM 0x8000046C. There are 0x6B7 halfword slots per part; part B starts at base+0xD6E. Getter 0x9D04D300 returns the whole halfword.

Parameter descriptors are 12 bytes each at flash 0x9D047498. Group max halfwords are at 0x9D047630 (parameter 0x22) and 0x9D04793C (parameter 0x63). Both contain 0x0040 and default 0. These are identified dependency sites, not an approved standalone patch.

## Edit, save, load and SysEx

- Individual limiter 0x9D04D4FC loads descriptor max and returns min(input,max) for these two group parameters. Setter 0x9D04DACC calls it and stores the result as a halfword. For sample changes it separately adjusts instrument selection using the group/category count table. Raising max before expanding that table is unsafe.
- Bulk sanitizer 0x9D04D6D4 scans descriptors and both parts. It compares each halfword against its max and substitutes descriptor DEFAULT when above max. Group 65 becomes group 0 in stock, not 64. Caller sites include normal program-update wrapper 0x9D07C470 and both SysEx program handlers (calls at 0x9D07824C and 0x9D0783B8).
- Save routine 0x9D046B5C stages a 4096-byte page in RAM 0x80010DAC. The loops at 0x9D046C40 and 0x9D046C64 read 0x6B7 parameters for each part with getter 0x9D04D300 and write their low bytes at page offsets 0 and 0x800. Group fields are consequently full 8-bit values. Pre-save helper 0x9D046704 splits some paired halfwords into bytes; group offsets are not among the pairs read/rewritten. Post-save helper 0x9D046970 recombines those pairs.
- Serial-memory load routine 0x9D040418 has two 0x800-byte read loops. Actual parameter reads are stored with sh at 0x9D0404E8 and 0x9D040868; there is no 0x7F mask on the group bytes. Several normal program-selection callers use this loader, including around 0x9D0267A8/0x9D0269A8. Later bulk validation supplies the max/default gate. The complete hardware timing and page I/O were not emulated.
- SysEx sender 0x9D0742D0 uses low bytes of the same runtime parameters for an edit-buffer dump and byte reads for a stored program. It packs seven raw bytes into eight MIDI-safe bytes through 0x9D078830.
- SysEx unpacker 0x9D078878 restores bit 7 using the leading bitmask byte. Receiver 0x9D0744CC loads those decoded bytes with lbu and stores parameter halfwords, then its callers run the bulk sanitizer.
- Therefore seven-bit MIDI bytes do not mean seven-bit sample group IDs. ID 128 and ID 132 survive packing/unpacking and the inspected raw-byte storage. This supersedes only the conditional ceiling discussed in pass 1; NRPN and every other path remain to be checked.

## Audio-side continuation

PIC parameter sender 0x9D04D324 places a parameter number in the upper 16 bits and the parameter halfword in the lower bits. Part B adds 0x800 to the parameter number. QNX dispatches sample parameter triples 0x22..0x24 and 0x63..0x65 to the shared path at 0x220E8. At 0x22259 it extracts the low **byte** with movzx and stores it through CParams::SetActualVal; there is no seven-bit mask there. The directory accessor at 0x33C10 still rejects IDs above 64. Accepted lookup results reach CSampleGroup::SwitchSampleGroup at 0x222C3. Thus the audio sample-switch path also carries IDs 65, 96 and 132 within its byte width, but needs the previously identified table/bounds changes to resolve them.

## PIC table and persistent record

Further verified dependencies:

- Runtime group/category cache begins at 0x80037E90. Each entry is 8 bytes: a count and an index/offset. Row stride is 17*8 = 0x88. Getter 0x9D0792E0 directly reads row group*17+category; there is no local bounds check. Name-table reader 0x9D041E8C reads the second word and derives an instrument-name record address using a 64-byte stride from 0xC00000.
- Runtime cache initialization 0x9D040ED8 reads byte counts from serial-memory address 0x5FD000. It normally reads first 41 rows (IDs 0..40), then initializes remaining rows to count=1 and index=-1. A leading 0xFF marker triggers the extended layout and changes its read-through limit to 64 at 0x9D041044. Total end remains base+0x2288, i.e. 65*17*8 = 8840 bytes. This backward-compatible record handling is another limit to change; simply extending the count-rebuild loop is incomplete.
- Rebuild 0x9D042A8C stages marker 0xFF at RAM 0x80010DAC and 65*17 byte counts starting 0x80010DAD, then writes the 4 KiB page at 0x5FD000.
- Page writer 0x9D042340 issues serial commands 0x06 (write enable) and 0x02 with three address bytes, followed by 256 bytes from the staging buffer; status helper checks bit 0. This verifies a serial-memory page-program protocol, not an internal PIC Program Flash write. Exact device capacity, free sectors and safe new record ownership are unresolved.
- Counts alone for 97 total groups would take 1+97*17 = 1650 bytes, within the existing 4 KiB count page; 133 total groups would take 2262 bytes. **This size fit does not make expansion safe.** Runtime cache relocation, adjacent RAM ownership, name-record offsets/capacity and every reader remain to audit.

## Emulation evidence

verify_group_encoding.py executes stock MIPS instructions under Unicorn. It applies higher descriptor max values only to emulator memory and restores them; no modified BIN is emitted.

Passed:

1. Actual individual limiter for both group parameters, boundary inputs 0,1,8,9,40,41,64,65,96,97,127,128,132,133,255, with max 64,96,132.
2. Actual bulk sanitizer for both parameters in both parts, including defaults for invalid values, with max 64,96,132.
3. Actual getter retains IDs 65,96,127,128,132,255 in both parts.
4. Actual SysEx packer and decoder: 256 seven-byte cases, each position traversing all byte values; all output MIDI bytes <128 and decoded bytes equal input.

Unicorn lacks the two DSP lbux instructions in the decoder: those two loads alone are supplied by a hook implementing their unsigned indexed-byte-load semantics. All other instructions in those routines are the stock bytes. No serial-memory device, full selector, complete preset receive/send transaction or hardware timing was tested.

## Next concrete task

Audit ownership and relocation options for PIC runtime cache 0x80037E90..0x8003A117, all initialization/read/write paths and serial-memory instrument-name metadata. Trace selector ordering, labels and menu maxima plus import destination logic. Then audit matching QNX layout and caches. 64 user groups (97 total IDs, last ID 96=u63) remains a sensible first development target because the inspected formats can represent it while preserving all original IDs. It is not yet approved for building or flashing.
