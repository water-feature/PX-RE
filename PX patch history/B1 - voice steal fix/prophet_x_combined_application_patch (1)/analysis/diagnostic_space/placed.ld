ENTRY(px_quiet_voice)
px_mutex_lock = 0x7a10;
px_cond_wait = 0x7640;
px_mutex_unlock = 0x79a0;
px_set_gate = 0xead0;
px_startup_mutex = 0x2a57a0;
px_fresh_return = 0x216c6;
px_coordinator_return = 0x1b4a9;
px_scan_next = 0x213f0;
px_collect_return = 0x2148e;
px_scan_start = 0x213a0;
px_batch_wait_return = 0x215bf;
SECTIONS {
 .stub 0x49fd0 : { *(.stub) }
 .quiet 0x8fed0 : { *(.quiet) }
 .hooks 0x49fd4 : { *(.hooks) }
}
