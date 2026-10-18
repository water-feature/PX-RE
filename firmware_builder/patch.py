#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Patch the factory update beside this script; filenames are optional."""
from patch_prophet_x import main
import struct
import sys

if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError, struct.error) as error:
        print(f'Build failed: {error}', file=sys.stderr)
        sys.exit(1)
