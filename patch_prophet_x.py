#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Build Prophet X 2.2.2.2.2 from your exact factory 2.2.2.0.0 update.

Windows, macOS and Linux; Python 3.11+.
"""
from pathlib import Path
import struct
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent / "firmware_builder" / "direct"))
from build import main

if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError, struct.error) as error:
        print(f"Build failed: {error}", file=sys.stderr)
        sys.exit(1)
