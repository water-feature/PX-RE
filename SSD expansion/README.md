# Expand the Prophet X SSD

Standalone technical guide for replacing the SSD with a larger drive while preserving the boot partition and copying the QNX sample filesystem. A Crucial M500 480 GB replacement has been hardware-confirmed. No firmware update required; this is a separate hardware/storage procedure.

Follow these steps in order. The original SSD is disconnected after backup; migration reads the backup and writes only to the replacement.

- [Before starting](#before-starting)
- [1. Back up the original SSD](#1-back-up-the-original-ssd)
- [2. Build the maintenance image](#2-build-the-maintenance-image)
- [3. Attach the replacement through QEMU](#3-attach-the-replacement-through-qemu)
- [4. Confirm the guest disk mapping](#4-confirm-the-guest-disk-mapping)
- [5. Set the partition boundaries](#5-set-the-partition-boundaries)
- [6. Preserve boot and create the sample filesystem](#6-preserve-boot-and-create-the-sample-filesystem)
- [7. Copy and verify the files](#7-copy-and-verify-the-files)
- [8. Shut down and test](#8-shut-down-and-test)
- [Troubleshooting](#troubleshooting)
- [Tested configuration and results](#tested-configuration-and-results)

## Before starting

Linux is required to read the QNX filesystem, so the guide has been written using Linux for the full process: backup, maintenance-image preparation and migration. You can use a Linux computer or a Linux VM on macOS or Windows. A whole-disk backup can be created on any operating system using a suitable imaging tool. Migration runs inside a QNX virtual machine; other host operating systems may work but are not covered here.

The commands below use Ubuntu/Debian package names; other distributions need equivalent packages and a kernel with the QNX6 filesystem driver.

You need:

- The original PX SSD, kept unchanged for rollback.
- A larger replacement SATA SSD that reports 512-byte logical sectors and is no larger than 2 TB. Its contents will be overwritten. The tested replacement is a Crucial M500 480 GB; the partition format’s capacity limit does not establish compatibility with every SSD up to 2 TB.
- A reliable SATA connection or USB-to-SATA adapter that exposes the whole disk with 512-byte logical sectors.
- A Linux environment with administrator access, Python 3, GNU binutils, QEMU and the QNX6 kernel driver.
- Storage for a whole-disk backup, plus temporary QEMU files. The tested original disk requires approximately 240 GB just for the backup image. Use a filesystem that supports files larger than 4 GB; FAT32 is unsuitable.

Keep the backup, extracted boot file and generated QNX images private. Store them outside this repository, on storage separate from both SSDs.

Confirm the original SSD has the two partitions shown below before continuing.

### If you use a Linux VM

Attach the SATA adapter to the Linux VM using your VM application's USB device controls. Linux must see the **whole physical SSD**, including its partition table, rather than a shared folder or a virtual disk containing copied files. Only one operating system should access it at a time. Decline any host prompts to initialise or format it.

Confirm that the disk appears in Linux using `lsblk` before continuing. If the adapter cannot be attached reliably, resolve that first. The Linux VM needs access to the backup storage too, with enough free space for the image and temporary files. A live Linux session is another option, but save all images and build outputs on persistent storage.

QEMU runs inside Linux, including when Linux itself is a VM. The commands use software x86 emulation, so hardware virtualisation support is not required for this inner QNX guest. On ARM hosts, the Linux environment must also provide GNU binutils capable of assembling and linking 32-bit x86 code; see step 2.

### Install the tools

In a **Linux terminal**:

```sh
sudo apt update
sudo apt install python3 binutils qemu-system-x86 util-linux coreutils
sudo modprobe qnx6
```

If `modprobe` fails, use a Linux kernel/distribution that supplies the QNX6 driver before continuing. A generic VM or WSL installation does not necessarily include it or expose physical USB disks.

### Where to enter commands

Steps 1–3 run in the **Linux terminal**. Steps 4–8 use the **QNX shell inside QEMU**, except where the **QEMU monitor** or a second **Linux terminal** is explicitly named. Commands for one environment must not be entered in another.

Enter commands individually. After each command completes, check its output; use `echo $?` immediately to inspect its exit status when no explicit status check is shown. Continue only on success. Long serial pastes can lose characters. Paths and device names in examples must be replaced with your own confirmed values. Avoid commas in the working-directory path because QEMU uses commas to separate drive options.

## 1. Back up the original SSD

Power off the synth before removing its SSD. Connect only the original SSD for this step. In the **Linux terminal**, list disks before and after connecting it:

```sh
lsblk --bytes -o NAME,PATH,SIZE,MODEL,SERIAL,TRAN,LOG-SEC,TYPE,MOUNTPOINTS
```

Identify the newly attached whole disk by model, serial number and exact byte capacity. `/dev/sdX` below is a placeholder for that disk, not a partition such as `/dev/sdX1`. Never select the computer's system disk. If the adapter hides its identity or identification is ambiguous, stop.

Set the confirmed source device and an absolute path on your backup storage. Keep this terminal open for steps 1–3:

```sh
px_source=/dev/sdX
px_work=/absolute/path/to/private-px-work
mkdir -p "$px_work"
lsblk --bytes -o NAME,PATH,SIZE,MODEL,SERIAL,LOG-SEC,TYPE,MOUNTPOINTS "$px_source"
sudo blockdev --getsize64 "$px_source"
sudo blockdev --getss "$px_source"
sudo fdisk -l "$px_source"
df -h "$px_work"
```

Record the exact capacity. Require 512-byte logical sectors, an MBR partition table, and the original PX partitions: active boot partition (type 177) followed by the sample partition (type 179). Check the backup storage has enough space. If any source partition is mounted, unmount each listed partition with `sudo umount /dev/sdX1`, substituting its actual name. Re-run `lsblk` and require no mountpoints on the source or its partitions. Do not format or repair the original.

Make sure `$px_work/qnx-backup.img` does not already exist. Then copy the whole disk:

```sh
sudo dd if="$px_source" of="$px_work/qnx-backup.img" bs=4M status=progress conv=fsync,excl
echo $?
stat -c %s "$px_work/qnx-backup.img"
```

`conv=excl` prevents overwriting an existing backup file. Require a zero copy status and an image length equal to the original disk's exact capacity. Read failures must be resolved; do not hide them with `conv=noerror`.

With the original still unmounted, compare whole-disk and image hashes. Each command reads the entire disk/image and may take a while:

```sh
sudo sha256sum "$px_source"
sha256sum "$px_work/qnx-backup.img"
```

Both hashes must match, with no read errors. Record the hash and capacity. Hash-check any transferred copy too. Disconnect and retain the original SSD; the remaining steps read the verified backup instead. Linux may reuse its device name for the replacement, so identify the replacement afresh in step 3.

## 2. Build the maintenance image

This step walks you through extracting the boot file from your verified backup and running the included [build_maintenance.py](maintenance%20image%20build%20tool/build_maintenance.py) tool to create `px-maintenance-vm-boot.img`, the QNX maintenance disk used in step 3. It provides the original QNX 7.0.1 utilities and a COM1 shell at 115200 baud, without automatically mounting, formatting or launching ProphetX.

### Extract the boot file

Continue in the **Linux terminal**. On x86 Linux, the installed GNU `as` and `ld` supply the required 32-bit x86 output. On ARM Linux, install the distribution's x86 cross-binutils and pass their executable names using `--assembler` and `--linker`; the native ARM tools cannot build this loader.

Inspect the backup's partition table:

```sh
fdisk -l "$px_work/qnx-backup.img"
```

Identify partition 1, the active type-177 boot partition. Record its start LBA and sector count. Multiply each by 512 to obtain the byte offset and length. The recorded layout starts at LBA 2048 and contains 524288 sectors, giving offset 1048576 and length 268435456. **Use these values only if your inspected partition table matches.**

Extract the boot file through a read-only QNX6 mount. Set the measured byte values first:

```sh
px_boot_offset=1048576
px_boot_length=268435456
sudo mkdir -p /mnt/px-boot
px_loop_device=$(sudo losetup --find --show --read-only --offset "$px_boot_offset" --sizelimit "$px_boot_length" "$px_work/qnx-backup.img")
sudo mount -t qnx6 -o ro "$px_loop_device" /mnt/px-boot
sudo cp /mnt/px-boot/.boot/x86_64-generic.bin "$px_work/px-qnx-boot.bin"
sudo umount /mnt/px-boot
sudo losetup -d "$px_loop_device"
```

### Verify the extracted file

The builder supports only the tested **9,278,800-byte** boot file, SHA-256:

```text
6a5124d8ee0eb6ad7561bf394e3c7469115dc6184e397d34ea7e3b72f8f6fccc
```

Check the extracted file before building:

```sh
stat -c %s "$px_work/px-qnx-boot.bin"
sha256sum "$px_work/px-qnx-boot.bin"
```

Require the exact size and hash above. Stop if either differs; this builder supports only that boot-file version.

### Build the QEMU boot disk

Keep [build_maintenance.py](maintenance%20image%20build%20tool/build_maintenance.py) and [bootloader.S](maintenance%20image%20build%20tool/bootloader.S) together. From the `SSD expansion` folder, run:

```sh
python3 "maintenance image build tool/build_maintenance.py" "$px_work/px-qnx-boot.bin" --output "$px_work/px-maintenance-build"
```

The output directory must not already exist. Use `--assembler` and `--linker` if your GNU tools have different executable names. The builder creates:

| Output | Purpose |
|---|---|
| `px-maintenance-vm-boot.img` | Boot disk for QEMU; 23,429,632 bytes. |
| `px-maintenance-candidate.ifs` | Rebuilt QNX payload; 23,410,436 bytes. |
| `build-report.json` | Input/output hashes, sizes, checksums and reference-match result. |

The builder checks its output hashes against the tested reference and stops if they differ. On success, use `$px_work/px-maintenance-build/px-maintenance-vm-boot.img` in step 3. The `.ifs` file and report are retained for inspection; you do not attach them to QEMU.

## 3. Attach the replacement through QEMU

Keep the original SSD disconnected. Connect the replacement; if using a VM, attach its SATA adapter to Linux. In the **Linux terminal**, identify the new disk:

```sh
lsblk --bytes -o NAME,PATH,SIZE,MODEL,SERIAL,TRAN,LOG-SEC,TYPE,MOUNTPOINTS
```

Match model, serial and capacity to the physical replacement. Set its whole-disk device name; `/dev/sdY` is a placeholder, not a partition:

```sh
px_target=/dev/sdY
lsblk --bytes -o NAME,PATH,SIZE,MODEL,SERIAL,LOG-SEC,TYPE,MOUNTPOINTS "$px_target"
sudo blockdev --getsize64 "$px_target"
sudo blockdev --getss "$px_target"
```

Record the target's byte capacity for step 5. Require 512-byte logical sectors. Check that this is the replacement, is larger than the original, and contains nothing you need. It must not be the Linux system disk or the disk holding `$px_work`.

Unmount any mounted target partitions individually using `sudo umount` and their actual names. Re-run `lsblk` and require no mountpoints on the target or its partitions. If a target partition is used as swap, disable that partition with `sudo swapoff /dev/sdY1`, using its actual name. Do not let the Linux desktop or outer VM host mount the target during migration.

Launch QEMU from the same Linux terminal. The next command grants the QNX guest write access to the **entire replacement SSD**. Recheck `$px_target` before running it:

```sh
sudo qemu-system-x86_64 -accel tcg -m 512 -machine pc \
  -drive "file=$px_work/px-maintenance-build/px-maintenance-vm-boot.img,if=ide,index=0,format=raw,snapshot=on" \
  -drive "file=$px_work/qnx-backup.img,if=ide,index=1,format=raw,snapshot=on" \
  -drive "file=$px_target,if=ide,index=2,format=raw" \
  -boot c -display none -serial mon:stdio
```

`snapshot=on` protects the maintenance image and backup through temporary overlays; never commit them. The replacement has no overlay, so its writes persist. Do not add the global `-snapshot` option: that would also discard replacement writes. A read-only IDE source caused `Block node is read-only` in the tested setup; the source overlay avoided that problem.

QEMU needs space for temporary overlays, normally in Linux's temporary directory. Keep sufficient free space there as well as on the backup storage. Wait for the banner `PX maintenance candidate: no disks mounted automatically` and the shell prompt. Continue in the **QNX shell** for step 4.

## 4. Confirm the guest disk mapping

At the **QNX shell**, start the drivers:

```sh
p=/lib/dll
export PCI_HW_MODULE=$p/pci/pci_hw-Intel_x86.so
export PCI_BKWD_COMPAT_MODULE=$p/pci/pci_bkwd_compat.so
pci-server --aspace-enable &
waitfor /dev/pci
a=ioport=0x1f0,irq=14
b=ioport=0x170,irq=15
devb-eide eide $a eide $b &
ls /dev/hd*
```

Press Ctrl+A, release, then C for the **QEMU monitor**. Run `info block` and confirm these attachments:

| Attachment | Contents | Expected QNX device |
|---|---|---|
| ide0-hd0 | Maintenance image | `/dev/hd0` |
| ide0-hd1 | Verified backup with temporary overlay | `/dev/hd1` |
| ide1-hd0 | Confirmed Linux `$px_target` replacement | `/dev/hd2` |

Return with Ctrl+A, C. Check the QNX devices before writing anything:

```sh
fdisk /dev/hd1 info
fdisk /dev/hd1 show -l
fdisk /dev/hd2 info
fdisk /dev/hd2 show -l
```

Require the source’s original QNX partitions and a target capacity/layout consistent with the replacement. Device names alone are insufficient identification. Recheck after any reconnect or reboot.

Mount the source samples read-only:

```sh
mount -t qnx6 -o ro /dev/hd1t179 /src
ls -la /src
```

Confirm `ProphetX`, `ProphetXBackup`, `startup.sh` and the expected sample directories. In the tested image, `mount` creates namespace mountpoints on the read-only root; `mkdir /src` is unnecessary. Stop if mounting fails.

## 5. Set the partition boundaries

The new sample partition starts at the same sector as the original and extends to near the end of the replacement. Calculate its boundaries before changing the target.

### Record the source and target values

Use the `fdisk` results from step 4 and the Linux capacity recorded in step 3:

| Value | Where to find it |
|---|---|
| **P** | Start LBA of source partition 2 (type 179), from QNX `fdisk /dev/hd1 show -l`. Check that the active boot partition ends before this sector. |
| **Q** | Target sector count reported by QNX `fdisk /dev/hd2 info`. Use the count, not the last sector number. |
| **B** | Target byte capacity from Linux `sudo blockdev --getsize64 "$px_target"` in step 3. |

All sector calculations below use 512-byte sectors. The usable sector count **T** is the smaller of Q and B / 512. Investigate any large difference between those counts before continuing.

### Calculate the final sector

Open a second **Linux terminal**, leaving QEMU running in the first. Run this calculator and enter your measured P, Q and B when prompted. It does not access or write any disk:

```sh
python3 -c '
p = int(input("Source sample start LBA (P): "))
q = int(input("QNX target sector count (Q): "))
b = int(input("Linux target capacity in bytes (B): "))
if p <= 0 or q <= p or b <= 0 or b % 512:
    raise SystemExit("Invalid values: check the recorded disk information.")
t = min(q, b // 512)
length = ((t - p) // 8) * 8
if length <= 0:
    raise SystemExit("Target has no space for the sample partition.")
print("Linux target sectors:", b // 512)
print("QNX target sectors:", q)
print("Usable target sectors (T):", t)
print("Sample partition length:", length)
print("psec=" + str(p))
print("endsec=" + str(p + length - 1))
'
```

The calculator rounds the partition length down to a multiple of eight sectors (4 KiB). Its final sector is inclusive: `end = P + length - 1`. Confirm the resulting partition is large enough for the source files and filesystem metadata.

For example, the recorded migration used P=526336 and T=937697985:

```text
length = floor((937697985 - 526336) / 8) * 8 = 937171648 sectors
end    = 526336 + 937171648 - 1 = 937697983
```

These are worked examples, not values to reuse for a different disk.

### Set the values in QNX

Return to the first terminal and the **QNX shell**. Set the confirmed guest disk names and enter the `psec` and `endsec` values printed by your calculation. The numbers below show the recorded example; replace them with your results:

```sh
srcdisk=/dev/hd1
dstdisk=/dev/hd2
psec=526336
endsec=937697983
```

## 6. Preserve boot and create the sample filesystem

### Copy the boot partition

Copy exactly the P sectors preceding the sample partition. This preserves the MBR, gaps and entire boot partition:

```sh
dd if=$srcdisk of=$dstdisk bs=512 count=$psec
echo $?
```

Require zero status and P complete records copied. For the tested source this is 257 MiB; other layouts require their measured P.

### Resize partition 2

Replace only partition slot 2. Check each status before entering the next command:

```sh
fdisk $dstdisk delete -s 2
echo $?
r=$psec,$endsec
fdisk $dstdisk add -s 2 -t 179 -l -c $r
echo $?
mount -e $dstdisk
echo $?
fdisk $dstdisk show -l
```

Confirm partition 1 retains its original boundaries and active flag, and partition 2 has the calculated start/end.

### Format the sample partition

Format only the target sample partition:

```sh
mkqnx6fs -b 4096 -g 16 /dev/hd2t179
echo $?
mount -t qnx6 /dev/hd2t179 /dst
echo $?
df -h /dst
```

Require successful formatting/mounting and the expected larger capacity. The formatter settings match the inspected original filesystem.

## 7. Copy and verify the files

### Copy the samples and application

```sh
cp -RpPq /src/. /dst/
copy_rc=$?
echo $copy_rc
```

Capture `copy_rc` immediately when `cp` returns. Require zero. The copy includes hidden files and preserves modes, ownership, modification times and links. It can take hours; optional `-V` adds per-file progress.

### Check the copied files

Compare file counts, checking for traversal errors:

```sh
find /src -type f | grep -c .
find /dst -type f | grep -c .
```

Flush and remount the target read-only, checking each command succeeds:

```sh
sync
umount /dst
mount -t qnx6 -o ro /dev/hd2t179 /dst
ls -la /dst
df -h /dst
mount -t qnx6 -o ro /dev/hd2t177 /bootcheck
ls -la /bootcheck/.boot
```

Require the expected application/sample layout and `.boot/x86_64-generic.bin`. Matching counts and successful remounts are limited checks. The tested image lacked `cmp` and checksum utilities; full file-content verification needs an additional toolchain.

## 8. Shut down and test

```sh
cd /
umount /bootcheck
umount /dst
umount /src
sync
```

Require clean unmounts. Switch to the QEMU monitor and enter `quit`, then wait for QEMU to exit back to the Linux terminal. Run `sudo sync` in Linux. Shut down Linux before disconnecting the replacement. If using a VM, shut down the VM and release its USB attachment before disconnecting the adapter; shut down the outer host too if the caddy requires it. Decline initialisation/formatting prompts on every host.

With the synth powered off, fit the replacement. Check boot, several factory and installed instruments, and a normal import. **Global → Update Library** shows the sample-storage budget, which differs from filesystem free space because firmware applies its own allowances. Testing imports beyond the old budget remains a separate validation step.

## Troubleshooting

| Problem | Response |
|---|---|
| Backup read error, size mismatch or differing hashes | Fix the connection and repeat backup verification before writing the replacement. |
| Disconnect or QEMU I/O error | Treat the target as incomplete. Stop, unmount if responsive, close QEMU and fix the connection. Re-identify disks, then rebuild/reformat the target and recopy. |
| Nonzero copy status or traversal errors | Preserve the error text. Resolve capacity/connection issues and recopy to a clean target. |
| Incorrect partition layout, failed mount or missing boot files | Stop and check the mapping and preceding commands. Keep repair attempts away from the original SSD and backup. |
| Busy unmount | Move shells to `/`, stop processes using the mount and retry. Leave the disk attached until QEMU releases it. |
| Synth boot or sample-loading failure | Power off and refit the unchanged original SSD. Confirm normal operation before diagnosing the replacement. |

## Tested configuration and results

| Item | Recorded value |
|---|---|
| Original image | 240,057,407,488 bytes |
| Original boot partition | Type 177; LBA 2048–526335; active |
| Original sample partition | Type 179; LBA 526336–468860927 |
| Replacement | Crucial M500 480 GB; new sample end 937697983 |
| Formatter | 117,146,452 blocks; 1,830,432 inodes; 16 groups |
| Copy | Exit status 0; 200,299 regular files on each side |
| Boot file | `x86_64-generic.bin`; 9,278,800 bytes |
| Final QNX filesystem | 447 GiB total; 156 GiB used; 291 GiB available |
| Synth | Successful boot; approximately 277,000 MB free in Update Library |


### Maintenance-image implementation and validation

The tool decompresses the boot filesystem, preserves the original utilities, drivers, libraries and loader links, replaces the startup commands with the maintenance shell, repairs headers/checksums and adds the BIOS loader. It verifies both output hashes against the tested reference before writing them. It does not access the physical replacement SSD.

[validation.json](maintenance%20image%20build%20tool/validation.json) records a byte-for-byte match to the working maintenance image, successful QEMU shell boot, and rejection of unsupported input and existing output directories. Physical migration was not repeated for that builder validation.

Expected output SHA-256 hashes are:

| Output | SHA-256 |
|---|---|
| Boot disk | `d09c8e53353ac9aabe7bcc9e905c6e5feabaa3002a0f92f72a99ac85beca4662` |
| QNX payload | `276d810a039e6d15cd4c7ceb04f8a829db0e4396e1e55e5eacb15b7d8ce6d8a1` |

## References

- QNX 7 [fdisk](https://www.qnx.com/developers/docs/7.0.0/com.qnx.doc.neutrino.utilities/topic/f/fdisk.html).
- QEMU [disk images and physical host disks](https://www.qemu.org/docs/master/system/images.html).
- GNU [backup copy options](https://www.gnu.org/software/coreutils/manual/html_node/dd-invocation.html).
- Linux [loop-device setup](https://manpages.ubuntu.com/manpages/jammy/man8/losetup.8.html) and [disk capacity queries](https://manpages.ubuntu.com/manpages/jammy/man8/blockdev.8.html).
