# Firmware builders

The two build workflows live in separate folders:

- [Direct builder](direct/README.md): the default used by the [direct firmware patcher](patch_prophet_x.py). Requires Python 3.11+ and runs on Windows, macOS and Linux. Generates the final firmware from your factory input, authored recipes and pinned redacted objects.
- [Source rebuild](source_rebuild/README.md): compiles the feature sources and rebuilds the historical chain for inspection. Uses the documented macOS compiler toolchain and can retain intermediate packages and validation reports.

Both workflows require the exact factory update and check the same final firmware size and SHA-256. Commands and input/output hashes are in the [main guide](../README.md).

## Directory map

| Location | Purpose |
|---|---|
| `firmware_builder/patch_prophet_x.py` | Patcher launcher |
| `firmware_builder/direct/` | Default patcher, source generators, redacted object cache, linker and final checks |
| `firmware_builder/source_rebuild/` | Compiler orchestrator, stage wrappers, container inspection tool, follow-up sources and historical rebuild receipt |
| `PX patch history/` | Feature implementations, research and test evidence; selected files are inputs to the source rebuild |

The [source rebuild directory map](source_rebuild/README.md#directory-map) describes its feature inputs in detail. Recovery and SSD tools are documented in the [recovery guide](../RECOVERY.md) and [SSD expansion guide](../SSD%20expansion/README.md).
