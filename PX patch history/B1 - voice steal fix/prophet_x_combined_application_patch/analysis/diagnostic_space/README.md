# Diagnostic-space placement trial

Read prophet_x_voice_click_pass30.md and prophet_x_voice_click_pass31.md. No firmware update has been modified. placed.elf is a synthetic assembly container. unwind_layout_trial.elf is an offline layout test that includes corrected unwind records but omits integration branches. Neither is installable firmware. Actual exception/cancellation behavior remains untested.

Requires GNU binutils, Python, Capstone, pyelftools and Unicorn. Tests/audit expect the unmodified extracted ProphetX.elf in the parent directory. It is not bundled.

```sh
as --64 -o placed.o placed.S
ld -T placed.ld -o placed.elf placed.o
objcopy -O binary --only-section=.quiet placed.elf quiet_code.bin
objcopy -O binary --only-section=.hooks placed.elf hooks_code.bin
objcopy -O binary --only-section=.stub placed.elf debug_stub.bin
python audit_space.py
python test_placed_batch.py
python test_placed_activation.py
python build_unwind_trial.py
python test_unwind_lookup.py
```

placement_manifest.json records byte expectations only. It does not patch an update.

The unwind builder writes a separate trial ELF, metadata blob and review manifest. It never overwrites ProphetX.elf. The archive omits the original binary and reproducible full-size trial ELF. Supply the original extracted ProphetX.elf in the parent directory to reproduce it.
