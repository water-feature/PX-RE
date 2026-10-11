# Reproducing the B1 application patch

This public bundle supplies the application patch source and historical offline test reports. Firmware and generated binary artifacts are omitted. The builder produces the pre-packaging candidate; see the [B1 handover](../../../README.md) for the final version and later hardware result.

Supply your privately held stock application as `analysis/ProphetX.elf`. Required size: 986,520 bytes. SHA-256: `7db8a8276f0bda34d22fdd2e8744b304dc7d62f80f9189836b107a4d7b178cff`.

Dependencies: Python, pyelftools, Capstone and Unicorn. From the bundle root:

```sh
python analysis/combined_patch/build_application_patch.py --input analysis/ProphetX.elf --output analysis/combined_patch/ProphetX_voice_fade_candidate.elf
python analysis/combined_patch/test_builder.py
PX_CANDIDATE_ELF="$PWD/analysis/combined_patch/ProphetX_voice_fade_candidate.elf" python analysis/diagnostic_space/test_placed_batch.py
PX_CANDIDATE_ELF="$PWD/analysis/combined_patch/ProphetX_voice_fade_candidate.elf" python analysis/diagnostic_space/test_placed_activation.py
PX_CANDIDATE_ELF="$PWD/analysis/combined_patch/ProphetX_voice_fade_candidate.elf" python analysis/diagnostic_space/test_unwind_lookup.py
```

Run locally outside the publication folder to keep generated firmware private. The builder refuses to overwrite an existing output. Tests mock QNX scheduling, threading and DSP operations; they do not establish hardware timing or audio behavior. This builder does not package an installable update.
