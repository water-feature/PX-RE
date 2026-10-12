# SPDX-License-Identifier: GPL-2.0-or-later
"""Extract the QNX application from a verified Prophet X update (no patching)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "firmware_builder" / "source_rebuild"))
from container import FACTORY_SHA256, FINAL_SHA256, elf_layout, parse, sha256


def extract(data: bytes, expected_sha256: str | None = None) -> bytes:
    actual = sha256(data)
    if expected_sha256 is not None:
        if len(expected_sha256) != 64 or any(c not in "0123456789abcdef" for c in expected_sha256):
            raise ValueError("Expected SHA-256 must contain 64 hexadecimal digits")
        accepted = {expected_sha256}
    else:
        accepted = {FACTORY_SHA256, FINAL_SHA256}
    if actual not in accepted:
        raise ValueError("Update SHA-256 mismatch or unrecognised update. For another known-good "
                         "update, supply its independently verified --expected-sha256.")
    application = parse(data)[0].payload
    if len(application) < 64 or application[:6] != b"\x7fELF\x02\x01":
        raise ValueError("Application is not a complete little-endian ELF64")
    if int.from_bytes(application[18:20], "little") != 62:
        raise ValueError("Application is not x86-64")
    elf_layout(application)
    return application


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("update", type=Path)
    parser.add_argument("-o", "--output", type=Path, required=True)
    parser.add_argument("--expected-sha256", type=str.lower,
                        help="Independently verified update hash; defaults to the pinned factory/final updates")
    args = parser.parse_args()
    output = args.output.resolve()
    public = Path(__file__).resolve().parents[1]
    if output.is_relative_to(public):
        raise ValueError("Keep extracted firmware outside the repository")
    if output.exists():
        raise FileExistsError(output)
    data = args.update.read_bytes()
    application = extract(data, args.expected_sha256)
    created = False
    try:
        with output.open("xb") as stream:
            created = True
            stream.write(application)
    except BaseException:
        if created:
            output.unlink(missing_ok=True)
        raise
    print(json.dumps({"status": "PASS", "input_sha256": sha256(data),
                      "output": str(output), "application_bytes": len(application),
                      "application_sha256": sha256(application)}, indent=2))


if __name__ == "__main__":
    main()
