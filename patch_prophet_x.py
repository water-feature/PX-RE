#!/usr/bin/env python3
"""Build Prophet X 2.2.2.2.2 from your exact factory 2.2.2.0.0 update.

Requires the complete source repository and the macOS build tools documented
in README.md. No firmware image or whole-image delta is embedded here.
"""
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "firmware_builder"))
from source_pipeline import main

if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"Build failed: {error}", file=sys.stderr)
        sys.exit(1)
