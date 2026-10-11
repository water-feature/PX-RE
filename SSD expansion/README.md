# B2 - Expand the Prophet X SSD

Standalone technical guide for replacing the SSD with a larger drive while preserving the boot partition and copying the QNX sample filesystem. A Crucial M500 480 GB replacement has been hardware-confirmed. Storage expansion does not increase sample-bank slot limits.

**Firmware:** No firmware update required; this is a separate hardware/storage procedure.

**Hardware: PASS (owner-reported, limited scope)** The replacement boots and Global → Update Library reports approximately 277,000 MB free. Broad playback testing, full file-content comparison and imports beyond the original approximately 53 GB budget remain unverified.

## Before starting

**Patch location:** SSD storage/layout only; no QNX application or PIC firmware patch.

**Patch size:** 0 firmware bytes. Disk/partition sizes depend on the source layout and replacement SSD; the maintenance-image tool generates a separate private service image.

You need:

- The original PX SSD, kept unchanged for rollback.
- A larger replacement SATA SSD and a reliable connection. Its contents will be overwritten.
- Storage for a verified whole-disk backup. A second extracted copy of the sample library is unnecessary.
- macOS for the backup commands below; Windows with Administrator access and QEMU for migration. The tested migration used Windows 10 and a laptop SATA caddy.
- A validated PX maintenance image with a QNX serial shell, filesystem driver and `mkqnx6fs`.

The maintenance image is built from your own `.boot/x86_64-generic.bin` using the source tool in step 2. It provides the original QNX 7.0.1 x86_64 utilities and a COM1 shell at 115200 baud, without automatically mounting, formatting or launching ProphetX. Keep the backup, extracted boot file and generated QNX images private.

Use this guide only for the tested **two-partition MBR layout with 512-byte sectors**. GPT, other sector sizes, additional partitions and drives beyond MBR’s addressing range require a separate procedure.

Enter commands individually. After each command completes, check its output; use `echo $?` immediately to inspect its exit status. Continue only on success. Long serial pastes can lose characters.

## 1. Back up the original SSD

Power off the synth before removing its SSD. On macOS, identify it by model and exact byte capacity:

```sh
diskutil list
diskutil info /dev/diskN
```

Replace `N` with the confirmed disk number and `DEST` with the backup volume. Never select the computer’s system disk. Cancel offers to initialise or format the PX SSD.

```sh
diskutil unmountDisk /dev/diskN
sudo dd if=/dev/rdiskN of="/Volumes/DEST/qnx-backup.img" bs=4m
echo $?
stat -f %z "/Volumes/DEST/qnx-backup.img"
```

Require a zero copy status and an image length equal to the original disk’s exact capacity. Ctrl+T requests progress during macOS `dd`. Read failures must be resolved; do not hide them with `conv=noerror`.

With the original still unmounted, compare whole-disk and image hashes:

```sh
sudo shasum -a 256 /dev/rdiskN
shasum -a 256 "/Volumes/DEST/qnx-backup.img"
```

Both hashes must match, with no read errors. Record the hash and capacity. Hash-check any transferred copy too. Use a Windows-readable destination for migration; APFS is not natively readable by Windows. Disconnect and retain the original SSD.

## 2. Build the maintenance image

Use Linux, a Linux VM or suitable WSL environment with Python 3 and GNU binutils supporting 32-bit x86 output. On Ubuntu:

```sh
sudo apt install python3 binutils
```

Extract the boot file from the verified backup through a read-only QNX6 mount. Check the source partition table first: the example offset and length below apply to the recorded 256 MiB boot partition only. Replace paths and measured values as needed.

```sh
sudo modprobe qnx6
sudo mkdir -p /mnt/px-boot
px_loop_device=$(sudo losetup --find --show --read-only --offset 1048576 --sizelimit 268435456 /private/path/qnx-backup.img)
sudo mount -t qnx6 -o ro "$px_loop_device" /mnt/px-boot
sudo cp /mnt/px-boot/.boot/x86_64-generic.bin /private/path/px-qnx-boot.bin
sudo umount /mnt/px-boot
sudo losetup -d "$px_loop_device"
```

Require each command to succeed before continuing. The builder supports only the tested **9,278,800-byte** boot file, SHA-256:

```text
6a5124d8ee0eb6ad7561bf394e3c7469115dc6184e397d34ea7e3b72f8f6fccc
```

It rejects other inputs. Other boot-file versions require separate analysis; keep the hash checks intact.

Keep [build_maintenance.py](maintenance%20image%20build%20tool/build_maintenance.py) and [bootloader.S](maintenance%20image%20build%20tool/bootloader.S) together. From the `SSD expansion` folder, run:

```sh
python3 "maintenance image build tool/build_maintenance.py" /private/path/px-qnx-boot.bin --output /private/path/px-maintenance-build
```

The output directory must not already exist. Use `--assembler` and `--linker` if your GNU tools have different executable names. The builder creates:

| Output | Purpose |
|---|---|
| `px-maintenance-vm-boot.img` | Boot disk for QEMU; 23,429,632 bytes. |
| `px-maintenance-candidate.ifs` | Rebuilt QNX payload; 23,410,436 bytes. |
| `build-report.json` | Input/output hashes, sizes, checksums and reference-match result. |

The tool decompresses the boot filesystem, preserves the original utilities, drivers, libraries and loader links, replaces the startup commands with the maintenance shell, repairs headers/checksums and adds the BIOS loader. It verifies both output hashes against the tested reference before writing them. It does not access the physical replacement SSD.

[validation.json](maintenance%20image%20build%20tool/validation.json) records a byte-for-byte match to the working maintenance image, successful QEMU shell boot, and rejection of unsupported input and existing output directories. Physical migration was not repeated for that builder validation. Expected output SHA-256 hashes are:

| Output | SHA-256 |
|---|---|
| Boot disk | `d09c8e53353ac9aabe7bcc9e905c6e5feabaa3002a0f92f72a99ac85beca4662` |
| QNX payload | `276d810a039e6d15cd4c7ceb04f8a829db0e4396e1e55e5eacb15b7d8ce6d8a1` |

Copy the boot disk to the Windows host and hash-check the transferred copy. Keep all generated images outside the public source folder. The expected serial banner is `PX maintenance candidate: no disks mounted automatically`.

## 3. Attach the replacement through QEMU

In **Administrator PowerShell**, identify the replacement:

```powershell
Get-Disk | Format-Table Number,FriendlyName,SerialNumber,Size,LogicalSectorSize,IsBoot,IsSystem,IsOffline
Get-Partition | Format-Table DiskNumber,PartitionNumber,DriveLetter,Offset,Size
```

Match model, serial and capacity to the physical SSD. Require `IsBoot` and `IsSystem` to be false. If identification is ambiguous, stop. Record its disk number and take only that disk offline:

```powershell
Set-Disk -Number N -IsOffline $true
```

In **Administrator cmd.exe**, launch QEMU. Replace the paths and `PhysicalDriveN` with the verified values:

```bat
"C:\Program Files\qemu\qemu-system-x86_64.exe" -m 512 -machine pc -drive "file=D:\px-maintenance-vm-boot.img,if=ide,index=0,format=raw" -drive "file=D:\qnx-backup.img,if=ide,index=1,format=raw,snapshot=on" -drive "file=\\.\PhysicalDriveN,if=ide,index=2,format=raw" -boot c -display none -serial mon:stdio
```

The shell uses the serial terminal. `snapshot=on` protects the backup through a temporary overlay; never commit it. Apply it only to the source image so replacement writes persist. A read-only IDE source caused `Block node is read-only` in the tested setup; the overlay avoided that problem.

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
| ide1-hd0 | Confirmed `PhysicalDriveN` replacement | `/dev/hd2` |

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

Record these values before changing the target:

| Value | How to determine it |
|---|---|
| **P** | Source sample partition’s start LBA. Verify the active boot partition ends before it. |
| **T** | Smaller of QNX’s reported target sector count and Windows target byte capacity divided by 512. Investigate a large discrepancy. |
| **length** | `floor((T - P) / 8) * 8` sectors, aligning the length to 4 KiB. |
| **end** | `P + length - 1`, inclusive. |

Require positive length, boundaries within the target and enough space for source files plus filesystem metadata. The tested values were P=526336 and T=937697985, giving end=937697983. **These are examples, not fixed values for every disk.**

Set the confirmed device names and substitute your measured numeric boundaries:

```sh
srcdisk=/dev/hd1
dstdisk=/dev/hd2
psec=526336
endsec=937697983
```

## 6. Preserve boot and create the sample filesystem

Copy exactly the P sectors preceding the sample partition. This preserves the MBR, gaps and entire boot partition:

```sh
dd if=$srcdisk of=$dstdisk bs=512 count=$psec
echo $?
```

Require zero status and P complete records copied. For the tested source this is 257 MiB; other layouts require their measured P.

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

Confirm partition 1 retains its original boundaries and active flag, and partition 2 has the calculated start/end. Then format only the target sample partition:

```sh
mkqnx6fs -b 4096 -g 16 /dev/hd2t179
echo $?
mount -t qnx6 /dev/hd2t179 /dst
echo $?
df -h /dst
```

Require successful formatting/mounting and the expected larger capacity. The formatter settings match the inspected original filesystem.

## 7. Copy and verify the files

```sh
cp -RpPq /src/. /dst/
copy_rc=$?
echo $copy_rc
```

Capture `copy_rc` immediately when `cp` returns. Require zero. The copy includes hidden files and preserves modes, ownership, modification times and links. It can take hours; optional `-V` adds per-file progress.

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

Require clean unmounts. Switch to the QEMU monitor and enter `quit`, then fully shut down Windows before removing a SATA-caddy SSD. Keep the target offline in Windows and decline initialisation/formatting prompts.

With the synth powered off, fit the replacement. Check boot, several factory and installed instruments, and a normal import. **Global → Update Library** shows the sample-storage budget, which differs from filesystem free space because firmware applies its own allowances. Testing imports beyond the old budget remains a separate validation step.

## If a step fails

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

Full file-content comparison, broad playback testing and imports beyond the original budget remain unverified.

## References

- QNX 7 [fdisk](https://www.qnx.com/developers/docs/7.0.0/com.qnx.doc.neutrino.utilities/topic/f/fdisk.html).
- QEMU [disk images](https://www.qemu.org/docs/master/system/images.html).
