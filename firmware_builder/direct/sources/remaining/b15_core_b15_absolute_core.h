// SPDX-License-Identifier: GPL-2.0-or-later
#ifndef B15_CORE_H
#define B15_CORE_H
/* Freestanding selection policy. Transport/firmware adapters are separate. */
typedef unsigned char b15_u8;
typedef unsigned short b15_u16;
typedef unsigned int b15_u32;
#define B15_PAIRS 4u
#define B15_KEYS 128u
#define B15_LAYERS 16u
#define B15_HIGHEST (-2)
enum b15_result { B15_OK, B15_DEFERRED, B15_DISABLED, B15_UNAVAILABLE,
                  B15_STALE, B15_BAD_ARGUMENT };
struct b15_pair {
    b15_u8 selected[B15_KEYS]; /* actual accepted note layer + 1; zero invalid */
    b15_u8 enabled, key, target, actual;
    b15_u8 prepared, snapshot, tag, bulk;
    b15_u8 want_highest, reserved;
    b15_u32 epoch;
};
struct b15_state { struct b15_pair pair[B15_PAIRS]; };
/* Resolve returns actual layer + 1 (1..16), or 0 if no new handler resolved.
   Successful adapter also installs/enqueues that handler using stock ownership.
   B15_HIGHEST asks adapter for highest eligible layer at the preferred key.
   Failed same-group resolve must not replace the previous usable handler. */
struct b15_io {
    void *cookie;
    int (*resolve)(void *, unsigned pair, unsigned key, int target_index);
    void (*publish)(void *, unsigned pair, unsigned epoch,
                    unsigned actual_layer);
};
void b15_init(struct b15_state *s);
int b15_note_attempt(struct b15_state *s, unsigned p, unsigned input_key);
int b15_note_accepted(struct b15_state *s, unsigned p, unsigned input_key,
                      unsigned zero_based_layer);
int b15_prepare(struct b15_state *s, unsigned p, unsigned input_key, unsigned tag);
int b15_enable(struct b15_state *s, const struct b15_io *io, unsigned p, int on);
int b15_commit(struct b15_state *s, const struct b15_io *io, unsigned p,
               unsigned final_key, unsigned tag);
int b15_key(struct b15_state *s, const struct b15_io *io, unsigned p, unsigned key);
int b15_absolute(struct b15_state *s, const struct b15_io *io, unsigned p,
                 unsigned setting);
int b15_group_changed(struct b15_state *s, const struct b15_io *io, unsigned p);
int b15_context_begin(struct b15_state *s, unsigned p, unsigned epoch);
int b15_context_end(struct b15_state *s, const struct b15_io *io, unsigned p,
                    unsigned epoch);
#endif
