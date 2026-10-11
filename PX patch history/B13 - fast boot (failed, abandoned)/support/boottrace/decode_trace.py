#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""
Decode px_boot_trace.bin (the Prophet X boot timing file) on a normal computer.

Usage:
    python decode_trace.py px_boot_trace.bin
    python decode_trace.py --make-sample sample.bin     (fake file, for testing this script)

File format (all numbers little-endian). The firmware side must match this:
    offset 0   8 bytes   magic "PXBTRACE"
    offset 8   u32       schema version (currently 1)
    offset 12  u32       number of markers N
    offset 16  32 bytes  SHA-256 of the baseline application (raw bytes)
    offset 48  16 bytes  build identity text, padded with zero bytes
    offset 64  N x u64   monotonic timestamp in nanoseconds for marker 0..N-1
                         a value of 0 means that marker was never reached

Only differences between timestamps are meaningful. The absolute values are not
treated as "time since boot", because that depends on the QNX version.
"""
import argparse
import struct
import sys

MAGIC = b"PXBTRACE"
HEADER = struct.Struct("<8sII32s16s")  # 64 bytes
SCHEMA = 1

# Marker IDs. The index in this list IS the marker ID the firmware must use.
# Addresses are from the exact-.15 hook map and are listed for reference only.
EVENTS = [
    "MAIN_ENTRY",          # 0   0x7d5e
    "SERIAL_BEGIN",        # 1   before call 0x7e25
    "SERIAL_END",          # 2   after RTS return 0x7e31
    "CTOR_BEGIN",          # 3   call 0x7e7f
    "INDEX_BEGIN",         # 4   call 0x161a3
    "INDEX_END",           # 5   return 0x161a8
    "CACHE_SETUP_BEGIN",   # 6   0x16353
    "PRELOAD_BEGIN",       # 7   call 0x1636a
    "PRELOAD_END",         # 8   return 0x1636f
    "SELECT_END",          # 9   0x163ae
    "CTOR_END",            # 10  return 0x7e84
    "FPGA_OPEN_BEGIN",     # 11  call 0x7ee6
    "FPGA_OPEN_END",       # 12  return 0x7ee8
    "SCHED_START_BEGIN",   # 13  call 0x7f73
    "SCHED_START_END",     # 14  return 0x7f76
    "WORKERS_BEGIN",       # 15  call 0x7f81
    "WORKERS_END",         # 16  return 0x7f86
    "STREAM_BEGIN",        # 17  call 0x7f8c
    "STREAM_END",          # 18  return 0x7f8f
    "LOOP_ENTER",          # 19  0x7f97
]

# Named stages: (label, start marker, end marker)
STAGES = [
    ("Whole run (entry to loop)",      "MAIN_ENTRY",        "LOOP_ENTER"),
    ("Entry to constructor",           "MAIN_ENTRY",        "CTOR_BEGIN"),
    ("  of which serial setup",        "SERIAL_BEGIN",      "SERIAL_END"),
    ("Whole constructor",              "CTOR_BEGIN",        "CTOR_END"),
    ("  Directory indexing",           "INDEX_BEGIN",       "INDEX_END"),
    ("  Cache/dictionary setup",       "CACHE_SETUP_BEGIN", "PRELOAD_BEGIN"),
    ("  Manifest preload",             "PRELOAD_BEGIN",     "PRELOAD_END"),
    ("  Initial group selection",      "PRELOAD_END",       "SELECT_END"),
    ("Hardware/engine preparation",    "CTOR_END",          "LOOP_ENTER"),
    ("  FPGA open",                    "FPGA_OPEN_BEGIN",   "FPGA_OPEN_END"),
    ("  Disk scheduler start",         "SCHED_START_BEGIN", "SCHED_START_END"),
    ("  Audio workers launch",         "WORKERS_BEGIN",     "WORKERS_END"),
    ("  Streaming enable/wait",        "STREAM_BEGIN",      "STREAM_END"),
]


def name_of(i):
    return EVENTS[i] if i < len(EVENTS) else "EVENT_%d" % i


def fail(msg):
    print("ERROR: " + msg, file=sys.stderr)
    sys.exit(1)


def load(path):
    try:
        with open(path, "rb") as f:
            data = f.read()
    except OSError as e:
        fail("cannot read %s: %s" % (path, e))
    if len(data) < HEADER.size:
        fail("file is only %d bytes, shorter than the 64-byte header" % len(data))
    magic, version, count, base_hash, build = HEADER.unpack_from(data, 0)
    if magic != MAGIC:
        fail("bad magic %r, this is not a trace file" % magic)
    if version != SCHEMA:
        fail("schema version %d, this decoder understands %d" % (version, SCHEMA))
    need = HEADER.size + 8 * count
    if len(data) < need:
        fail("header says %d markers (%d bytes) but file is %d bytes, truncated"
             % (count, need, len(data)))
    if len(data) > need:
        print("note: %d unexpected trailing bytes ignored" % (len(data) - need))
    stamps = list(struct.unpack_from("<%dQ" % count, data, HEADER.size))
    return base_hash, build.rstrip(b"\0").decode("ascii", "replace"), stamps


def fmt(ns):
    return "%9.3f s" % (ns / 1e9)


def report(path):
    base_hash, build, stamps = load(path)
    print("File:            %s" % path)
    print("Build identity:  %s" % (build or "(blank)"))
    print("Baseline SHA-256: %s" % base_hash.hex())
    print("Markers in file: %d" % len(stamps))

    reached = [(i, t) for i, t in enumerate(stamps) if t != 0]
    missing = [name_of(i) for i, t in enumerate(stamps) if t == 0]
    if not reached:
        fail("no markers were recorded")
    if missing:
        print("\nNOT REACHED: " + ", ".join(missing))

    # Check the markers are in time order.
    for (ia, ta), (ib, tb) in zip(reached, reached[1:]):
        if tb < ta:
            print("\nWARNING: %s is earlier than %s, marker order or clock is odd"
                  % (name_of(ib), name_of(ia)))

    origin = stamps[0] if stamps and stamps[0] != 0 else reached[0][1]

    print("\nTimeline (since first marker, and gap from previous reached marker)")
    print("%3s  %-20s %12s %12s" % ("ID", "marker", "elapsed", "gap"))
    prev = None
    for i, t in reached:
        gap = "" if prev is None else fmt(t - prev)
        print("%3d  %-20s %12s %12s" % (i, name_of(i), fmt(t - origin), gap))
        prev = t

    print("\nStages")
    lookup = {name_of(i): t for i, t in enumerate(stamps) if t != 0}
    total = None
    if "MAIN_ENTRY" in lookup and "LOOP_ENTER" in lookup:
        total = lookup["LOOP_ENTER"] - lookup["MAIN_ENTRY"]
    for label, a, b in STAGES:
        if a in lookup and b in lookup:
            d = lookup[b] - lookup[a]
            pct = "" if not total else "  %5.1f%%" % (100.0 * d / total)
            print("%-32s %s%s" % (label, fmt(d), pct))
        else:
            print("%-32s not recorded" % label)

    print("\nSlowest gaps between consecutive reached markers")
    gaps = []
    for (ia, ta), (ib, tb) in zip(reached, reached[1:]):
        gaps.append((tb - ta, ia, ib))
    gaps.sort(reverse=True)
    for d, ia, ib in gaps[:5]:
        skipped = " (markers in between were not reached)" if ib != ia + 1 else ""
        print("%s  %s -> %s%s" % (fmt(d), name_of(ia), name_of(ib), skipped))

    print("\nNote: percentages are of MAIN_ENTRY to LOOP_ENTER only. Time before the")
    print("application starts (bootloader, QNX bring-up) is not measured by this trace.")


def make_sample(path):
    """Write a FAKE trace so the decoder can be tested. Numbers are invented."""
    gaps_ms = [0, 5, 20, 3, 1, 1400, 2, 3, 3100, 50, 12, 20, 800, 5, 4, 90, 6, 4, 700, 2]
    t = 5_000_000_000
    stamps = []
    for g in gaps_ms[:len(EVENTS)]:
        t += g * 1_000_000
        stamps.append(t)
    hdr = HEADER.pack(MAGIC, SCHEMA, len(stamps), b"\0" * 32, b"SAMPLE-NOT-REAL")
    with open(path, "wb") as f:
        f.write(hdr + struct.pack("<%dQ" % len(stamps), *stamps))
    print("wrote fake sample trace to %s" % path)


def main():
    ap = argparse.ArgumentParser(description="Decode a Prophet X boot trace file.")
    ap.add_argument("file", help="trace file to decode, or output path with --make-sample")
    ap.add_argument("--make-sample", action="store_true",
                    help="write a fake trace file for testing instead of decoding")
    args = ap.parse_args()
    if args.make_sample:
        make_sample(args.file)
    else:
        report(args.file)


if __name__ == "__main__":
    main()
