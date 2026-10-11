#include "b15_absolute_core.h"
_Static_assert(sizeof(struct b15_state) <= 0x300, "QNX state exceeds audited reservation");
static int valid(unsigned p) { return p < B15_PAIRS; }
static void clear_map(struct b15_pair *r) {
    unsigned k;
    for (k = 0; k < B15_KEYS; ++k) r->selected[k] = 0;
}
static void publish(struct b15_pair *r, const struct b15_io *io, unsigned p) {
    io->publish(io->cookie, p, r->epoch, r->enabled ? r->actual : 0);
}
static int resolve(struct b15_pair *r, const struct b15_io *io, unsigned p) {
    int n;
    if (r->bulk || r->prepared) return B15_DEFERRED;
    if (!r->enabled) return B15_DISABLED;
    if (!r->target && !r->want_highest) return B15_UNAVAILABLE;
    n = io->resolve(io->cookie, p, r->key,
                    r->want_highest ? B15_HIGHEST : (int)r->target - 1);
    if (n < 1 || n > (int)B15_LAYERS) return B15_UNAVAILABLE;
    r->actual = (b15_u8)n;
    if (r->want_highest) {
        r->target = (b15_u8)n;
        r->want_highest = 0;
    }
    return B15_OK;
}
void b15_init(struct b15_state *s) {
    unsigned p, k;
    b15_u8 *bytes = (b15_u8 *)s;
    for (k = 0; k < sizeof(*s); ++k) bytes[k] = 0;
    for (p = 0; p < B15_PAIRS; ++p) s->pair[p].key = 60;
}
int b15_note_attempt(struct b15_state *s, unsigned p, unsigned key) {
    if (!valid(p) || key >= B15_KEYS) return B15_BAD_ARGUMENT;
    s->pair[p].selected[key] = 0;
    return B15_OK;
}
int b15_note_accepted(struct b15_state *s, unsigned p, unsigned key, unsigned layer) {
    if (!valid(p) || key >= B15_KEYS || layer >= B15_LAYERS) return B15_BAD_ARGUMENT;
    s->pair[p].selected[key] = (b15_u8)(layer + 1);
    return B15_OK;
}
int b15_prepare(struct b15_state *s, unsigned p, unsigned key, unsigned tag) {
    struct b15_pair *r;
    if (!valid(p) || key >= B15_KEYS || tag > 127) return B15_BAD_ARGUMENT;
    r = &s->pair[p];
    if (r->bulk) return B15_DEFERRED;
    r->prepared = 1;
    r->snapshot = r->selected[key];
    r->tag = (b15_u8)tag;
    return r->snapshot ? B15_OK : B15_UNAVAILABLE;
}
int b15_enable(struct b15_state *s, const struct b15_io *io, unsigned p, int on) {
    struct b15_pair *r;
    int result;
    if (!valid(p)) return B15_BAD_ARGUMENT;
    r = &s->pair[p];
    if (!on) {
        r->enabled = r->target = r->actual = r->prepared = r->snapshot = r->want_highest = 0;
        publish(r, io, p);
        return B15_OK;
    }
    if (r->enabled) return B15_OK; /* PREPARE/COMMIT may recapture while already on. */
    r->enabled = 1;
    r->want_highest = 1;
    result = resolve(r, io, p);
    publish(r, io, p);
    return result;
}
int b15_commit(struct b15_state *s, const struct b15_io *io, unsigned p,
               unsigned key, unsigned tag) {
    struct b15_pair *r;
    int result;
    if (!valid(p) || key >= B15_KEYS || tag > 127) return B15_BAD_ARGUMENT;
    r = &s->pair[p];
    if (!r->prepared || r->tag != tag || r->bulk) return B15_STALE;
    r->key = (b15_u8)key;
    r->prepared = 0;
    if (!r->snapshot || !r->enabled) {
        r->snapshot = 0;
        /* A failed capture cannot become a later no-held highest selection. */
        r->want_highest = 0;
        publish(r, io, p);
        return B15_UNAVAILABLE;
    }
    r->target = r->snapshot;
    r->snapshot = r->want_highest = 0;
    result = resolve(r, io, p);
    publish(r, io, p);
    return result;
}
int b15_key(struct b15_state *s, const struct b15_io *io, unsigned p, unsigned key) {
    struct b15_pair *r;
    int result;
    if (!valid(p) || key >= B15_KEYS) return B15_BAD_ARGUMENT;
    r = &s->pair[p]; r->key = (b15_u8)key;
    result = resolve(r, io, p);
    publish(r, io, p);
    return result;
}
int b15_absolute(struct b15_state *s, const struct b15_io *io, unsigned p, unsigned n) {
    struct b15_pair *r;
    int result = B15_OK;
    if (!valid(p) || n > B15_LAYERS) return B15_BAD_ARGUMENT;
    r = &s->pair[p];
    if (r->bulk) return B15_DEFERRED; /* loaded data, not a user layer edit */
    if (r->enabled && n) {
        r->target = (b15_u8)n;
        r->want_highest = 0;
        result = resolve(r, io, p);
    }
    publish(r, io, p);
    return result;
}
int b15_group_changed(struct b15_state *s, const struct b15_io *io, unsigned p) {
    struct b15_pair *r;
    int result;
    if (!valid(p)) return B15_BAD_ARGUMENT;
    r = &s->pair[p];
    clear_map(r);
    r->actual = r->prepared = r->snapshot = 0;
    if (r->enabled && !r->target) r->want_highest = 1;
    result = resolve(r, io, p);
    publish(r, io, p);
    return result;
}
int b15_context_begin(struct b15_state *s, unsigned p, unsigned epoch) {
    struct b15_pair *r;
    if (!valid(p)) return B15_BAD_ARGUMENT;
    r = &s->pair[p]; clear_map(r);
    r->bulk = 1; r->epoch = epoch;
    r->prepared = r->snapshot = r->target = r->actual = r->want_highest = 0;
    return B15_OK;
}
int b15_context_end(struct b15_state *s, const struct b15_io *io, unsigned p,
                    unsigned epoch) {
    struct b15_pair *r;
    int result;
    if (!valid(p)) return B15_BAD_ARGUMENT;
    r = &s->pair[p];
    if (!r->bulk || r->epoch != epoch) return B15_STALE;
    r->bulk = 0;
    r->want_highest = r->enabled;
    result = resolve(r, io, p);
    publish(r, io, p);
    return result;
}
