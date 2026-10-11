# B11b — hardware-directed closure

10 October 2026. **GO to approve the scoped compact B11b implementation.** No firmware or package modified. This report supersedes the prior placement and deletion/cache NO-GO verdicts. Individual-instrument deletion investigation is stopped: the owner confirms that the front panel on 2.2.2.1.15 deletes complete User banks only. Its backend existence is not evidence of an accessible operation.

## 1. Actual User bank deletion and refresh

**PASS — owner hardware evidence (.1.15):** complete User bank deletion displays “Refreshing category files”; the deleted bank immediately disappears and is skipped during navigation, without reboot. This is reported hardware evidence, not a new device test performed here.

**PASS — matching stock machine-code trace:** Manage Samples Confirm dispatch reads its selected item at UI+BC, subtracts 28 and indexes the table at 9D025470. Item 31 selects table word 9D02547C -> 9D025B50, installing the bank-delete handler 9D01B61C. In that handler, button event 14 with press byte 1 enters 9D01B828. It displays “Deleting directory...”, maps the selected bank through 9D080E60, and invokes 9D0798D8 with a0=0. That helper sends command 4036 with the selected group and waits for the completion flag; its resend loop is stock behavior.

The matching QNX command-4036 branch at 200EA/20103 calls LibraryCopy_DeleteGroup (15D60), clears the affected group index/dictionary via GroupFileUpdateFolder (20149), and sends completion 4036 at 20158. LibraryCopy_DeleteGroup iterates the group's 17 category directories. PIC then refreshes the bank-availability word through 9D079744 and stores the result at 8004A118 + 4*group (9D01B8F4).

The actual subsequent sequence is:

| PIC call site | Operation |
|---|---|
| 9D01B904 -> 9D042A8C | Request counts; rewrite persistent count page |
| 9D01B90C -> 9D042B80 | Refresh sample-name records |
| **9D01B914 -> 9D040ED8** | **Rebuild expanded PIC count/offset cache** |
| 9D01B91C onward | Parameter, metadata, UI/navigation refresh; resume |

9D042A8C displays the exact hardware-observed text at 9D07DF40, “Refreshing category files...”. Thus there is a direct correspondence between the observed operation and the refreshing code path. Expanded counts are rebuilt synchronously before that handler returns. Bank availability is independently refreshed, which also explains why encoder navigation stops offering the deleted bank.

**PASS — actual PIC instruction harness:** check_bank_refresh.py executes the stock event dispatch, deletion completion and real expanded-cache builder, with controlled deletion/communication/UI/flash callbacks. It starts with stale populated RAM records, supplies a fresh extended-format persistent page with the deleted bank empty, and checks all **1,105** rows: count N+1 and correct cumulative offsets, including FFFFFFFF for empty rows. Stack and saved registers are preserved. This is not execution of real flash, deletion or QNX I/O; the owner's hardware observation supplies the independent device evidence.

## 2. What invokes 9D022760?

**PASS — identified as Debug Menu “Reload Sample Names”, item 3.** The menu-name table at 9D064310 contains the string pointer 9D0641FC at table+12 (9D06431C). The display loads this same table at 9D034578–5E4. The debug event handler is 9D021B00. Confirm event 12, press byte 1, with UI+C0=3 dispatches through 9D021EAC to **9D022760**. The instruction harness executes this exact event/selection and observes the count/name refresh calls without a RAM-builder call.

The handler is installed by the debug entry at 9D02E9AC, reached through the checks at 9D02B0C8 and 9D02E9A0 (two nonzero stored flags). The other recovered installation at 9D022894 restores that handler from its own debug operations. It is not the User bank-delete completion handler. No undocumented key sequence is inferred here.

The Debug command sends 402C(1), refreshes persistent counts and names, sends 402C(0), and returns to UI. QNX's 402C branch at 21EEB only changes its flag; it does not mutate/reindex the library. This command therefore lacks an expanded-cache rebuild, **but does not itself change the library's instrument population**. After the normal bank-delete refresh above, expanded counts and offsets are already current; reloading names does not by itself make them stale. The previously identified failure requires an independently changed population with no normal refresh. No such accessible operation was demonstrated for this route.

**Normal-operation assessment:** the missing call is not a demonstrated B11b stale-cache risk in the confirmed User bank workflow. The speculative single-instrument path is outside the accessible front-panel scope and is not an approval blocker. This is a scoped conclusion, not a claim that arbitrary external filesystem changes or every service/debug workflow is safe.

## 3. Is the two-instruction cache correction necessary?

**NO — omit it from B11b.** Actual bank deletion already executes the builder. Debug Reload Sample Names is a separate operation and supplies no demonstrated population mutation that needs this extra call. The prior correction remains an uninstalled historical sizing experiment, not part of the proposed implementation. Its omission avoids an unrelated firmware change and extra refresh work. No broader invalidation change, live count request, or group-specific exception is needed for B11b on the established evidence.

## 4. Verified solution to the 16-byte placement shortfall

**PASS — reduced within existing ownership.** measure_compact.py replaces the 220-byte active sketch with **200 active bytes in the existing 204-byte allocation**, leaving one padding word. No additional location, unowned code, FF space, or other patch is used.

| Established owned range | Allocated bytes | Contents in compact layout |
|---|---:|---|
| [9D02A74C, 9D02A794) | 72 | Shared entry, direction normalization/getter, primary snapshot |
| [9D02D428, 9D02D464) | 60 | Instrument-2 entry, helper tail, secondary snapshot, refresh selector |
| [9D02DD08, 9D02DD2C) | 36 | Guarded instrument-clamp helper head |
| [9D02DEF8, 9D02DF1C) | 36 | Boundary bypass, absolute Type invocation, padding |
| **Total** | **204** | **200 active + 4 padding; zero unplaced bytes** |

The four existing clamp-call words remain same-size replacements at 9D04DEBC, 9D04E010, 9D04E54C, 9D04E624 (16 bytes changed in place). The existing 72 shared refresh/UI bytes stay untouched. New persistent RAM and additional stack-frame requirements are zero; calling the absolute setter also removes the extra relative-setter frame from this manual route.

The reductions are specific:

- Set the common constant 1 in the instrument-dispatch branch's delay slot, removing duplicated setup while preserving both flag writes and Group routes.
- The caller already calculates and bounds the actual target. Pass it to the existing **absolute setter 9D04DACC**, avoiding the relative setter's duplicate calculation and stack maximum argument. For an in-range manual turn this is the same common target the stock relative setter passes to that absolute setter.
- Read the instrument selector from existing UI state at refresh, eliminating the caller's separate s3 refresh marker; allow the nonzero branch to fall through into the existing instrument-2 refresh entry.
- Pack the primary/secondary snapshots into the existing ranges. The helper still uses the setter's saved s4/s5 values and compares the actual per-bank old category against its common target.

The full manual return identity is now **9D02DF10** (supersedes DF14/DF0C in older sketches). The helper still compares the entire 32-bit saved return address, not just a low halfword. Nonmanual callers branch directly to stock clamp. Boundaries bypass the setter entirely; an unchanged secondary category never triggers promotion. Empty categories clamp promoted 1 back to 0. Valid remembered real selections retain stock handling. Both Layers retains the stock common Type target with independent per-bank counts/restoration. Group routes stay at their original entries.

## Validation and residual limits

**PASS — final compact encoding:** LLVM independently matches all **51 allocated words**, zero relocations.

**PASS — final compact instruction execution:**

- 18,366 routing/setter cases, covering both instruments, edit A/B/Both, boundaries, differing bank categories, populated/empty banks, zero/valid/excessive selections and direction sign.
- 42,120 additional routing cases covering **all 65 group IDs** with distinct adjacent group pairs, both instruments and every edit mode.
- 2,016 setter cases with the final helper, executing all four replacement sites, checking saved registers/stack and manual/nonmanual identities.
- 16 full-return-identity rejection cases across the other PIC 64 KiB regions; all retain nonmanual zero.
- Actual bulk validation with the final overlay preserves all four recalled zeros for cached counts 1, 2 and 256.
- Ownership assertion limits every proposed changed word to the four established Type ranges or four clamp-call words. A renewed raw direct-edge/aligned-pointer audit finds only the existing menu-table entry 9D029348 -> 9D02A74C entering from outside the owned Type ranges. No refresh/UI byte or existing unrelated patch is claimed.

**NOT VERIFIED:** final B11b behavior on hardware, complete on-device preset recall, real UI/metadata/sample side effects and interrupt timing. Setter tests stub external effects; bank-refresh tests execute the real builder against controlled flash bytes. Raw incoming scans do not prove absence of arbitrary computed entries. These are normal post-implementation validation limits, not evidence of a remaining placement/cache blocker.

## Recommendation

**GO for owner approval of the compact B11b implementation, without the cache correction.** No remaining investigation blocker identified within the requested scope. Approval is still required before firmware modification; no package or firmware has been written. Hardware acceptance after an approved implementation should cover both instruments/layers, mixed populated/empty Both Layers banks, unchanged secondary category, Type boundaries, valid/zero preset recall, and the confirmed complete User-bank deletion/refresh workflow. No category-skipping search or broader menu change is included.
