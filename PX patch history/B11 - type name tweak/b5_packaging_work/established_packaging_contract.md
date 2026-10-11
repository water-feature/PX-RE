# Established voice-update packaging contract used for B5

Source: `prophet_x_re_handoff_2026-10-01 (3).md`, application packaging pass 34 and “Voice-only firmware revision 2.2.2.0.2”. Only those packaging/version sections were used; no loader research was performed.

The update is F0, followed by three records, then F7. Each record has twelve header bytes: one type, 7B, five revision bytes, 7A, a four-byte big-endian payload length. Each payload is followed by a two-byte little-endian trailer. The application and FPGA trailers are sums of little-endian 16-bit payload words modulo 65536. The tested PIC record's trailer 0x3030 differs from that simple sum 0x4658; its complete record must remain unchanged.

Tested voice base: `voice_2.2.2.0.2.bin`, SHA-256 `2ad5392eb842cbcd5c2e85e65ab42c16f1fac12d16b09c417a61761a8348bcbf`. Its application header, updater comparison and DSP revision are 2.2.2.0.2. Descriptive firmware names use feature plus five-component revision; an updater-facing `PxUpdate_V<revision>.bin` name can be used if required by the existing USB procedure. Descriptive filename acceptance is not established here.

Revision .3 is assigned to voice/SysEx; .4 is assigned to a PIC-only test. B5 uses the separate .5 test header and descriptive name. The current task pins the complete candidate ELF hash, so no embedded version comparison or screen-reply literal is changed: DSP still reports .2. This header-only identity deliberately differs from the earlier voice procedure's synchronized screen identity to obey the exact-candidate requirement.

The established updater gate skips a header matching the application's compiled revision. B5 header .5 differs from compiled .2. The tested voice .2 rollback header matches compiled .2 and would be skipped; the documented offline gate permits official stock .0 first, then voice .2. Hardware rollback and QNX acceptance remain untested. If the application cannot run the updater, a pretest SSD recovery image is the fallback.
