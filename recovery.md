# Prophet X recovery

Keep the factory update `PxUpdate_V2.2.2.0.0.bin`, the factory recovery file `PX_Main_2.2.2.0.0.syx`, and a verified full SSD image backup available privately. Recovery differs between the PIC controller and the SSD-resident QNX system. The synth does not perform any version gating, so rollback to an earlier firmware version is always possible. 

Note: The patches described in this repo have all been tested on hardware and do not touch the synth's bootloader so you should always be able to recover from a non-booting state.

## PIC / Main OS recovery over MIDI

Download **`PX_Main_2.2.2.0.0.syx`** from the attachment in [Sequential's Prophet X OS forum post](https://forum.sequential.com/index.php?topic=2656.0) (this is the factory PIC / Main OS recovery file; the `.bin` will not work here). Power off the instrument. Hold **SAMPLE STRETCH** while powering it on to enter bootloader mode, then transmit the appropriate factory recovery `.syx` file through the synth's DIN MIDI input using a SysEx sender. Wait for reception and the update to complete, then restart. Finally, install your preferred `.bin` firmware via item 33 in the synth's global menu.   

Verify the downloaded `PX_Main_2.2.2.0.0.syx` matches the retained recovery file before transmitting it:

- **Size:** 2,398,215 bytes
- **SHA-256:** `63882cc635caa42dfaa45f0bde6545b406c78e248128732663736d946b94daf0`

Note: This recovery path does not repair the SSD's QNX application or filesystem. If the sysex recovery process fails, the issue is likely related to the QNX system on the SSD - proceed to the next step.

## SSD / QNX recovery

**The easiest way to back up and restore the SSD is to make a full image clone of the entire drive.** Instructions for doing so are at the start of the [SSD expansion guide](SSD%20expansion/README.md#1-back-up-the-original-ssd) This preserves the partition table, boot partition, QNX application and sample filesystem together. Keep a verified image of the working SSD before making changes; restoring it returns the drive to that saved state and overwrites any later changes.

The rest of this document outlines the steps to recover specific sections of a failed QNX image, which can often be quicker than performing a full image restore:

- **Damaged QNX application:** restore the known-good application to both `ProphetX` and `ProphetXBackup` on the QNX filesystem. The SSD application recovery procedure below documents the Windows/QEMU maintenance workflow used after a failed firmware update. In that incident the boot image was unchanged; restoring the application was the required repair.
- **Damaged bootloader or boot partition:** restore the matching known-good boot image or boot partition from your own backup. The [SSD expansion guide](SSD%20expansion/README.md#6-preserve-boot-and-create-the-sample-filesystem) explains copying the disk's boot region with verified partition boundaries. Use its boot-copy step only when appropriate; the later formatting steps belong to SSD expansion. Preserve the destination's partition layout when restoring to a drive with a different geometry.
- **Damaged partition table/filesystem, or uncertain damage:** restore a verified full-disk backup to the confirmed target SSD, or refit the unchanged original drive. A full-image restore overwrites that drive, including samples and changes made since the backup. 

Do not copy boot sectors between arbitrary layouts or assume MIDI recovery can repair an SSD boot hang. Check the recovery source, target disk, byte capacity and partition boundaries before performing disk writes.

## SSD application recovery procedure

**Verification status:** The owner followed the procedure below and confirmed that it restored the broken SSD to a bootable state. Final repaired-file hashes were not recorded in the retained evidence.

**Other operating systems:** The procedure below documents the tested Windows/QEMU setup. The same QNX maintenance image should work in QEMU on Linux or macOS, with changes to host paths, command quoting, disk access permissions and physical SSD identification/unmounting. The commands inside QNX should remain the same if the emulated IDE controllers and disk order are preserved. Other VM applications may require different QNX disk drivers. Recovery on other hosts has not been verified.

This records the Windows/QEMU procedure used after the failed firmware update. The failed flash left the synth hanging after the boot bar. We restored the SSD-resident application, not its boot partition: the boot image was verified unchanged. Repaired SSD was successfully tested on hardware.

Both `ProphetX` and `ProphetXBackup` contained the failed application. The stock startup script checks whether the process exists after five seconds; a hung process can pass that check and overwrite the backup.


### 1. Prepare Windows

Use an elevated **Command Prompt (cmd.exe)**. The commands below assume the same files and drive mapping as the successful session:

- `C:\Program Files\qemu\qemu-system-x86_64.exe`
- `D:\px-maintenance-vm-boot.img` — maintenance boot image; create it using [SSD expansion, step 2: Build the maintenance image](SSD%20expansion/README.md#2-build-the-maintenance-image), then copy it to this path. Follow only that image-building section for recovery, not the SSD migration steps.
- `D:\qnx-backup.img` — known-good backup image
- `D:\PX_Recovery` — existing folder for transfers
- `\\.\PhysicalDrive2` — affected synth SSD, offline in Windows

**Confirm the physical disk number before launching.** PhysicalDrive2 was correct in our session; another machine or reconnection may assign a different number. Match the SSD model and capacity in Windows Disk Management. Set that SSD offline. Do not initialize or format it.

#### Obtain the replacement executable

Choose a firmware update that you know boots correctly on your synth and is compatible with its installed PIC firmware. You need the QNX application from that update, not necessarily the newest build and not specifically .1.2.

Extract the application directly from the complete update `.bin` with [extract_qnx.py](extract_qnx.py). It uses only Python's standard library (Python 3.10 or newer) and runs on Windows, Linux or macOS. From the downloaded repository folder, run this in Windows Command Prompt, replacing the input path:

```bat
python extract_qnx.py "C:\path\to\PxUpdate.bin" -o "D:\PX_Recovery\recovery.elf"
```

On Linux or macOS, use `python3` and the corresponding host paths. The output must be a new file outside the repository. The command verifies the update identity, container checksums and x86-64 ELF structure, then prints the extracted application's size and SHA-256. It does not patch firmware or access the SSD.

The default accepted inputs are the exact official 2.2.2.0.0 update and this project's accepted 2.2.2.2.2 update. For another known-good compatible update, add `--expected-sha256 HASH`, using an independently verified SHA-256 for that exact update. A matching hash and valid structure do not establish that an update boots correctly or is compatible with your installed PIC firmware.

The extracted executable normally uses the **`.elf` extension**. Copy or save it to:

```text
D:\PX_Recovery\recovery.elf
```

Renaming a complete update `.bin` to `.elf` does not extract its application. On the synth SSD, this same executable must be named `ProphetX` and `ProphetXBackup`, **without an extension**. The copy commands below handle those names.

File size varies between patched builds; do not require the historical .1.2 size or hash.

### 2. Launch the proven VM configuration

Paste this as one command in elevated cmd.exe, after confirming PhysicalDrive2:

```bat
"C:\Program Files\qemu\qemu-system-x86_64.exe" -m 512 -machine pc -drive file=D:\px-maintenance-vm-boot.img,if=ide,index=0,format=raw -drive file=D:\qnx-backup.img,if=ide,index=1,format=raw,snapshot=on -drive file=\\.\PhysicalDrive2,if=ide,index=2,format=raw -drive file=fat:rw:D:\PX_Recovery,if=ide,index=3,format=raw -boot c -display none -serial mon:stdio
```

The backup image uses a temporary snapshot overlay. The physical SSD is passed through directly and can be written by the guest. Initially mount its filesystems read-only.

Do not edit the Windows transfer folder while QEMU is running. Unmount it and quit QEMU before changing its contents from Windows.

### 3. Start the QNX disk driver

At the QNX `#` prompt, enter **one short line at a time**. Long pasted lines were truncated by the serial console during our session.

```sh
p=/lib/dll
export PCI_HW_MODULE=$p/pci/pci_hw-Intel_x86.so
export PCI_BKWD_COMPAT_MODULE=$p/pci/pci_bkwd_compat.so
pci-server --aspace-enable &
waitfor /dev/pci
a=ioport=0x1f0,irq=14
b=ioport=0x170,irq=15
devb-eide eide $a eide $b &
waitfor /dev/hd3
ls -l /dev/hd*
```

Expected mapping for this launch:

| Guest device | Contents |
|---|---|
| `/dev/hd0` | Maintenance boot image |
| `/dev/hd1` | Backup image with temporary overlay |
| `/dev/hd2` | Physical synth SSD |
| `/dev/hd2t177` | Physical SSD boot partition |
| `/dev/hd2t179` | Physical SSD content/application partition |
| `/dev/hd3t6` | Windows transfer folder, presented as FAT |

Plain `devb-eide cam quiet` did not discover disks in the failed attempts. Explicit IDE ports above worked after a fresh VM launch. If no `/dev/hd*` devices exist, fix disk discovery before attempting mounts. An empty `/dev/pci` directory alone is not evidence that PCI startup failed.

To check QEMU attachments, press **Ctrl+A, then C** to enter the monitor:

```text
info block
info pci
```

Confirm the intended physical drive is attached at IDE index 2. Press Ctrl+A, then C again to return to QNX. `quit` at the monitor exits QEMU; unmount filesystems first.

### 4. Preserve evidence read-only

Create separate mount directories:

```sh
mkdir /failed
mkdir /boot
mkdir /out
mount -t qnx6 -o ro /dev/hd2t179 /failed
mount -t qnx6 -o ro /dev/hd2t177 /boot
mount -t dos /dev/hd3t6 /out
mount
ls -l /failed/ProphetX*
cat /failed/startup.sh
ls -l /boot/.boot/x86_64-generic.bin
```

Use separate mountpoints. We accidentally mounted both SSD partitions on `/failed` once; the boot partition then obscured the application files.

Export evidence without changing the SSD:

```sh
cp -p /failed/ProphetX /out/ProphetX
cp -p /failed/ProphetXBackup /out/ProphetXBackup
cp -p /failed/startup.sh /out/startup.sh
cp -p /boot/.boot/x86_64-generic.bin /out/boot.bin
ls -l /out
sync
umount /failed
umount /boot
umount /out
```

Enter the QEMU monitor with Ctrl+A, then C and type:

```text
quit
```

The evidence copies are now in `D:\PX_Recovery`. Preserve them before restoring the application. In the recorded recovery, both applications contained the failed build, while the boot image and startup script were unchanged. No boot-partition rewrite was needed.

### 5. Restore both application files

With QEMU stopped, confirm `recovery.elf` is the final extracted executable obtained in section 1 and is in the transfer folder. Launch the same QEMU command and run the driver setup again.

```sh
mkdir /in
mkdir /fix
mount -t dos /dev/hd3t6 /in
ls -l /in/recovery.elf
mount -t qnx6 /dev/hd2t179 /fix
mount
ls -l /fix/ProphetX*
```

Before copying, confirm `/fix` is the physical SSD's **content partition**, and the original files are present. Then:

```sh
cp /in/recovery.elf /fix/ProphetX
cp /in/recovery.elf /fix/ProphetXBackup
chmod 777 /fix/ProphetX
chmod 777 /fix/ProphetXBackup
sync
ls -l /fix/ProphetX*
```

Both should have the same size as `/in/recovery.elf`, with executable permissions. The historical recovery used this same copy procedure. Leave startup.sh and the boot partition as they are.

### 6. Finish and optionally verify the copies

Unmount, remount read-only and export the repaired copies:

```sh
umount /fix
mount -t qnx6 -o ro /dev/hd2t179 /fix
cp /fix/ProphetX /in/repaired-main
cp /fix/ProphetXBackup /in/repaired-backup
sync
umount /fix
umount /in
```

Quit QEMU through its monitor. The read-back files are now in the Windows transfer folder. You can compare them byte for byte with the replacement executable, without any fixed version-specific hash:

```bat
fc /b D:\PX_Recovery\recovery.elf D:\PX_Recovery\repaired-main
fc /b D:\PX_Recovery\recovery.elf D:\PX_Recovery\repaired-backup
```

Each comparison should report no differences. After a completed VM shutdown, disconnect the SSD, reinstall it in the synth and test boot. If it still hangs, preserve the evidence and investigate further; the procedure does not justify formatting or rewriting the boot partition.

### Troubleshooting from the actual session

- **No `/dev/hd*`:** the disk driver has not discovered the drives. Restart QEMU fresh and use the explicit IDE-port setup. Avoid accumulating duplicate devb-eide processes.
- **DOS mount returns Invalid argument:** first check `/dev/hd3t6` exists. In our session this error occurred before disks were discovered; the same mount worked afterward.
- **Application files disappear after a boot mount:** check `mount` for two partitions sharing a mountpoint. Unmount the covering filesystem and use distinct directories.
- **No `/failedboot/.boot/x86_64-generic.b`:** the actual filename is `x86_64-generic.bin`; use short commands to avoid serial-line truncation.
- **Cannot reach the synth update menu:** this procedure restores the SSD application externally, so it does not depend on that menu. SysEx recovery had not repaired the failing SSD application in this case.
