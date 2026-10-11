"""Factory-to-final build from retained feature sources.

No generated firmware from the branch archives is staged as input.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


HERE = Path(__file__).resolve().parent
PUBLIC = HERE.parent if (HERE.parent / "PX patch history").is_dir() else HERE.parent / "_FOR GITHUB"
HISTORY = PUBLIC / "PX patch history"
FINAL_SHA = "488444589607a1b4e793a8d8f79a67c5bd50773b722c302e6d80bc1db77b4b7c"
FACTORY_SHA = "a4b304b3bb48ca933ae63c99c0098698c497ebfc7c38ab2a823b5e0df4919fa9"

DIRS = {
    "b5_candidate_work": "B5 - sample end fade/b5_candidate_work",
    "b8_candidate_work": "B8 - end escape/b8_candidate_work",
    "b7_candidate_work": "B7 - center can be pushed/b7_candidate_work",
    "b6_investigation": "B6 - center moves window/b6_investigation",
    "b6_candidate_work": "B6 - center moves window/b6_candidate_work",
    "b9_250_candidate_work": "B9 - slow preset browsing/b9_250_candidate_work",
    "b14_candidate_work": "B14 - disable encoder accel/implementation/b14_candidate_work",
    "b14_packaging_work": "B14 - disable encoder accel/implementation/b14_packaging_work",
    "b14_metadata_candidate_work": "B14 - disable encoder accel/implementation/b14_metadata_candidate_work",
    "b14_metadata_packaging_work": "B14 - disable encoder accel/implementation/b14_metadata_packaging_work",
    "b14_stable_frame_candidate_work": "B14 - disable encoder accel/implementation/b14_stable_frame_candidate_work",
    "b14_stable_frame_packaging_work": "B14 - disable encoder accel/implementation/b14_stable_frame_packaging_work",
    "b14_sample_acceleration_work": "B14 - disable encoder accel/implementation/b14_sample_acceleration_work",
    "b14_sample_acceleration_investigation": "B14 - disable encoder accel/implementation/b14_sample_acceleration_investigation",
    "b14_ui_candidate_work": "B14 - disable encoder accel/implementation/b14_ui_candidate_work",
    "b15_candidate_work": "B15 - stretch layer/implementation/b15_candidate_work",
    "b7_lfo_center_investigation": "B7 - center can be pushed/b7_lfo_center_investigation",
    "b10_ordinary_entry_design_1_12": "B10 - window scroll clicks/implementation/b10_ordinary_entry_design_1_12",
    "b11b_implementation_2_2_2_2_0": "B11 - type name tweak/b11b_implementation_2_2_2_2_0",
    "b11b_investigation": "B11 - type name tweak/b11b_investigation",
    "b11_placement_scratch": "B11 - type name tweak/b11_placement_scratch",
    "b16_finer_loop_sync_resolution": "B16 - new sync divisions/implementation/b16_finer_loop_sync_resolution",
}
HELPERS = {
    "b5_elf_placement_check.py": "B5 - sample end fade/b5_elf_placement_check.py",
    "b5_fade_prototype.py": "B8 - end escape/b5_fade_prototype.py",
    "patch_b4_minimal_qnx.py": "B5 - sample end fade/patch_b4_minimal_qnx.py",
    "b7_combined_instruction_model.py": "B7 - center can be pushed/b7_combined_instruction_model.py",
}

# Independent SHA-256 guards for the two B14 pre-edit spans.
B14_SPAN_GUARDS = [{'address': 2634289608, 'size': 76, 'sha256': 'f627fb4f5a31e7416ed531a6fbe9365293873f7f7b96769a1e0bb4efb33f3f4a'}, {'address': 2634289784, 'size': 8, 'sha256': '56e75428addb793d8167d3c023effea76afbdfb7505acca5c6d1e2533961fea5'}]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def clean(path: Path, *names: str) -> None:
    for name in names:
        target = path / name
        if target.is_dir():
            shutil.rmtree(target)
        elif target.exists():
            target.unlink()


def stage(root: Path) -> None:
    def ignore(directory: str, names: list[str]) -> set[str]:
        return {name for name in names if name == "__pycache__" or
                name.endswith((".bin", ".elf", ".o", ".pyc", ".dylib"))}
    for name, source in DIRS.items():
        shutil.copytree(HISTORY / source, root / name, ignore=ignore)
    # B5 follow-up sources were archived separately from the earlier B15 tree.
    followup = HISTORY / "B5 - sample end fade/b15_candidate_work"
    for candidate in followup.rglob("*"):
        if not candidate.is_file() or candidate.name in ignore(str(candidate.parent), [candidate.name]):
            continue
        destination = root / "b15_candidate_work" / candidate.relative_to(followup)
        if not destination.exists():
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(candidate, destination)
    for relative in ("lfo_endpoint_investigation/build_fix.py",
                     "lfo_endpoint_investigation/reproduce.c"):
        destination = root / "b15_candidate_work" / relative
        if not destination.exists():
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(HERE / "sources" / relative, destination)
    for name, source in HELPERS.items():
        shutil.copy2(HISTORY / source, root / name)
    for name in ("container.py", "build_b1.py", "build_b5.py", "build_b8.py", "build_b3_merge.py"):
        shutil.copy2(HERE / name, root / name)
    spec = (HISTORY / "B1 - voice steal fix/prophet_x_combined_application_patch (1)/"
            "analysis/combined_patch/patch_spec.json")
    destination = (root / "_FOR GITHUB/PX patch history/B1 - voice steal fix/"
                   "prophet_x_combined_application_patch (1)/analysis/combined_patch/patch_spec.json")
    destination.parent.mkdir(parents=True)
    shutil.copy2(spec, destination)
    (root / "b14_investigation").mkdir()
    (root / "b14_investigation/ui_exact_1_4.json").write_text(json.dumps(B14_SPAN_GUARDS, indent=2) + "\n")
    shutil.copy2(root / "b7_lfo_center_investigation/HISTORICAL_SHA256SUMS",
                 root / "b7_lfo_center_investigation/SHA256SUMS")
    (root / "b5_packaging_work").mkdir()
    shutil.copy2(HISTORY / "B11 - type name tweak/b5_packaging_work/established_packaging_contract.md",
                 root / "b5_packaging_work/established_packaging_contract.md")
    (root / "b14_ui_packaging_work").mkdir()
    shutil.copy2(HISTORY / "B11 - type name tweak/b14_ui_packaging_work/package_display.py",
                 root / "b14_ui_packaging_work/package_display.py")
    clean(root / "b16_finer_loop_sync_resolution", "in_place_candidate", "geometry_candidate")
    (root / "b16_finer_loop_sync_resolution/geometry_candidate").mkdir()
    for name in ("build.py", "validate_geometry.py"):
        shutil.copy2(HISTORY / DIRS["b16_finer_loop_sync_resolution"] / "geometry_candidate" / name,
                     root / "b16_finer_loop_sync_resolution/geometry_candidate" / name)
    # The B16 preservation receipt is re-created for this source-only checkout.
    offline = root / "b16_finer_loop_sync_resolution/offline_candidate"
    before = {str(p.relative_to(offline)): digest(p) for p in offline.rglob("*") if p.is_file()}
    (root / "b16_finer_loop_sync_resolution/safety_review/candidate_preservation.json").write_text(
        json.dumps({"before": before}, indent=2) + "\n")
    # Refresh source receipts for the portable public archive; firmware input
    # receipts remain the independently pinned historical values.
    manifest_path = root / "b11b_implementation_2_2_2_2_0/input_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for name in manifest:
        if not name.endswith((".bin", ".elf")) and (root / name).is_file():
            manifest[name] = digest(root / name)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")


def run(root: Path, relative: str, *args: str) -> None:
    script = root / relative
    print(f"running {relative}", flush=True)
    with (root / "build.log").open("a") as log:
        subprocess.run([sys.executable, str(script), *args], cwd=root, check=True,
                       stdout=log, stderr=subprocess.STDOUT)


def require_hash(root: Path, relative: str, expected: str) -> None:
    actual = digest(root / relative)
    if actual != expected:
        raise ValueError(f"{relative}: expected {expected}, got {actual}")
    print(f"PASS {relative}: {actual}", flush=True)


def build(root: Path, factory: Path) -> Path:
    if digest(factory) != FACTORY_SHA:
        raise ValueError("factory SHA-256 mismatch")
    stage(root)
    inventory = {str(p.relative_to(root)): digest(p) for p in root.rglob("*") if p.is_file()}
    (root / "staged_source_inventory.json").write_text(json.dumps(inventory, indent=2) + "\n")
    shutil.copy2(factory, root / "PxUpdate_V2.2.2.0.0.bin")
    run(root, "container.py", str(root / "PxUpdate_V2.2.2.0.0.bin"), "--null-output", str(root / "factory_null.bin"))
    run(root, "build_b1.py", str(root / "PxUpdate_V2.2.2.0.0.bin"), str(root / "PxUpdate_V2.2.2.0.2.bin"))
    run(root, "build_b5.py", str(root / "PxUpdate_V2.2.2.0.2.bin"), str(root / "voice_b5_2.2.2.0.5.bin"))
    shutil.copy2(root / "voice_b5_2.2.2.0.5.bin", root / "b5_packaging_work/voice_b5_2.2.2.0.5.bin")
    run(root, "build_b8.py", str(root / "voice_b5_2.2.2.0.5.bin"), str(root / "PxUpdate_V2.2.2.0.6.bin"))
    run(root, "build_b3_merge.py", str(root / "PxUpdate_V2.2.2.0.6.bin"), str(root / "PxUpdate_V2.2.2.0.7.bin"))
    from container import parse
    rows = parse((root / "PxUpdate_V2.2.2.0.7.bin").read_bytes())
    (root / "pic_2.2.2.0.7.bin").write_bytes(rows[2].payload)
    run(root, "b7_candidate_work/build_validate_b7.py")
    run(root, "b6_candidate_work/build_b6.py")
    run(root, "b6_candidate_work/validate_candidate.py")
    run(root, "b6_candidate_work/verify_package.py", str(root / "b6_candidate_work/package_pending_validation.bin"))
    run(root, "b6_candidate_work/publish_b6.py")
    run(root, "b9_250_candidate_work/build_b9.py")
    run(root, "b9_250_candidate_work/validate_instructions.py")
    run(root, "b9_250_candidate_work/verify_placement.py")
    run(root, "b9_250_candidate_work/verify_package.py", str(root / "b9_250_candidate_work/package_pending_validation.bin"))
    run(root, "b9_250_candidate_work/publish_b9.py")
    run(root, "b14_candidate_work/build_b14.py")
    run(root, "b14_candidate_work/validate_b14.py")
    run(root, "b14_packaging_work/package_b14.py")
    run(root, "b14_metadata_candidate_work/build_metadata.py")
    run(root, "b14_metadata_candidate_work/validate_metadata.py")
    run(root, "b14_metadata_packaging_work/package_metadata.py")
    run(root, "b14_stable_frame_candidate_work/build_stable.py")
    run(root, "b14_stable_frame_candidate_work/validate_stable.py")
    run(root, "b14_stable_frame_packaging_work/package_stable.py")
    run(root, "b15_candidate_work/build_pic_absolute.py")
    run(root, "b15_candidate_work/build_pic_integrated.py")
    run(root, "b15_candidate_work/build_qnx_absolute.py")
    run(root, "b15_candidate_work/build_candidate_1_8.py")
    run(root, "b15_candidate_work/lfo_endpoint_investigation/build_fix.py")
    run(root, "b15_candidate_work/build_candidate_1_9.py")
    run(root, "b14_sample_acceleration_work/build.py")
    run(root, "b14_sample_acceleration_work/validate.py")
    run(root, "b14_sample_acceleration_work/package.py")
    run(root, "b15_candidate_work/lfo_endpoint_investigation/completion_fix/build.py")
    run(root, "b15_candidate_work/lfo_endpoint_investigation/completion_fix/validate.py")
    run(root, "b15_candidate_work/lfo_endpoint_investigation/completion_fix/package.py")
    run(root, "b7_lfo_center_investigation/measure_design.py")
    run(root, "b7_lfo_center_investigation/implementation_1_12/build.py")
    run(root, "b7_lfo_center_investigation/implementation_1_12/validate.py")
    run(root, "b7_lfo_center_investigation/implementation_1_12/package.py")
    run(root, "b10_ordinary_entry_design_1_12/candidate_1_15/build.py")
    run(root, "b10_ordinary_entry_design_1_12/candidate_1_15/validate.py")
    run(root, "b10_ordinary_entry_design_1_12/candidate_1_15/package.py")
    run(root, "b11b_implementation_2_2_2_2_0/measure_compact.py")
    b11 = root / "b11b_implementation_2_2_2_2_0"
    for generated in (b11 / "compact").glob("fragment_*.bin"):
        shutil.copy2(generated, b11 / "approved" / generated.name)
    clean(b11, "PIC_diff.tsv", "QNX_diff.tsv", "emission_listing.txt", "emission.json",
          "validation.log", "branch_targets.json", "validation.json", "package_results.json")
    run(root, "b11b_implementation_2_2_2_2_0/build.py")
    run(root, "b11b_implementation_2_2_2_2_0/validate.py")
    run(root, "b11b_implementation_2_2_2_2_0/package.py")
    run(root, "b16_finer_loop_sync_resolution/in_place_validation/preflight.py")
    run(root, "b16_finer_loop_sync_resolution/in_place_validation/dependencies.py")
    run(root, "b16_finer_loop_sync_resolution/in_place_validation/integrate.py")
    run(root, "b16_finer_loop_sync_resolution/geometry_candidate/build.py")
    final = root / "b16_finer_loop_sync_resolution/geometry_candidate/PxUpdate_V2.2.2.2.2_B16_geometry_candidate.bin"
    require_hash(root, str(final.relative_to(root)), FINAL_SHA)
    return final


def main() -> None:
    if not __debug__:
        raise RuntimeError("Run Python without -O or PYTHONOPTIMIZE; validation assertions are required")
    parser = argparse.ArgumentParser(description="Build the exact Prophet X 2.2.2.2.2 update from retained feature sources.")
    parser.add_argument("factory", type=Path)
    parser.add_argument("-o", "--output", type=Path, default=Path("PxUpdate_V2.2.2.2.2.bin"))
    parser.add_argument("--work-dir", type=Path, help="Keep source staging, firmware intermediates, validation reports and build.log in this NEW private directory")
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(output)
    if output.is_relative_to(PUBLIC.resolve()):
        raise ValueError("Keep generated firmware outside the public source tree")
    if digest(args.factory) != FACTORY_SHA or args.factory.stat().st_size != 3099064:
        raise ValueError("Expected the exact factory 2.2.2.0.0 input (SHA-256 mismatch)")
    for command in ("clang", "rustc", "objdump"):
        if shutil.which(command) is None:
            raise RuntimeError(f"Required build tool is missing: {command}")

    def execute(root: Path) -> None:
        try:
            final = build(root, args.factory.resolve())
            data = final.read_bytes()
            if len(data) != 3187784:
                raise ValueError("Final package size mismatch")
            from container import parse, serialize
            original = parse(args.factory.read_bytes())
            recovered = parse(data)
            if serialize(recovered) != data or recovered[1].encode() != original[1].encode():
                raise ValueError("Final round-trip or FPGA preservation failed")
            report = {"status": "PASS", "factory_sha256": digest(args.factory),
                      "final_sha256": hashlib.sha256(data).hexdigest(), "final_bytes": len(data),
                      "round_trip_identical": True, "FPGA_record_unchanged": True,
                      "component_sha256": {str(row.kind): hashlib.sha256(row.payload).hexdigest() for row in recovered},
                      "staged_source_inventory_sha256": digest(root / "staged_source_inventory.json")}
            (root / "source_build_verification.json").write_text(json.dumps(report, indent=2) + "\n")
            created = False
            try:
                with output.open("xb") as stream:
                    created = True
                    stream.write(data)
            except BaseException:
                if created:
                    output.unlink(missing_ok=True)
                raise
        except BaseException:
            log = root / "build.log"
            if log.exists():
                print("Last build log lines:\n" + "\n".join(log.read_text(errors="replace").splitlines()[-60:]), file=sys.stderr)
            raise

    if args.work_dir:
        root = args.work_dir.resolve()
        if root.is_relative_to(PUBLIC.resolve()):
            raise ValueError("Keep the working directory outside the public source tree")
        root.mkdir(parents=True, exist_ok=False)
        execute(root)
    else:
        with tempfile.TemporaryDirectory(prefix="px-source-build-") as temp:
            execute(Path(temp))
    print(json.dumps({"status": "PASS", "output": str(output),
                      "bytes": output.stat().st_size, "sha256": digest(output)}, indent=2))


if __name__ == "__main__":
    main()
