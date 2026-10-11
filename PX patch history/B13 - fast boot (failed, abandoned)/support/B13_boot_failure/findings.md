# B13 boot failure investigation

The supplied 2.2.2.1.3 candidate installs but repeatedly hangs at the completed boot bar. SysEx recovery is in progress. This candidate is withdrawn.

No root cause has been established. Static inspection found correct helper call targets, stack argument placement, buffer extent, saved registers and package preservation. The new probe executes the full original manifest parser, cache insertion and SwitchSampleGroup on an initially empty cache, using Linux I/O and QNX-compatible stat-size placement with no-op locks. All 927 manifests parse successfully with zero UUID. Five trials of the exact candidate startup worker running on four concurrent host threads each finish and produce all 927 insertion calls. QNX thread control and scheduling calls are stubbed, so this does not validate QNX behavior.

The original PIC startup code near 0x9D052EC4/0x9D052F18 waits for reply command 0x4013 in the upper 16 bits. It accepts the lower revision value and passes it to its version handler at 0x9D0530AC. It does not require the DSP final revision to equal PIC there. A missing reply is consistent with the observed screen, but this does not distinguish an application crash from an initialization block.

The earlier tests checked helper behavior and startup projections, but not the complete QNX application startup. The previous description of workers as joined was imprecise: stock code uses detached workers and polls completion markers.

Next decisive evidence: whether recovery restores boot, followed by QNX crash/core or live process/thread state if obtainable. No corrected candidate is justified yet.
