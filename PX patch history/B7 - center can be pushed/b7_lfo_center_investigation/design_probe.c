/* Isolated sizing/validation probe. Never linked into a firmware image. */
typedef unsigned long uintptr_t;
extern __attribute__((visibility("hidden"))) float *center_get_mod(void *, int, int);
extern __attribute__((visibility("hidden"))) int center_get_param(void *, int, int);
extern __attribute__((visibility("hidden"))) float *center_map, *center_diffs;

static float bound(float x) {
    if (x < 0) return 0;
    if (x > 999) return 999;
    return x;
}
static float effective(int raw, float mod) {
    return bound((float)raw + mod * 999.0f);
}
static float mapped(float x) {
    x = bound(x);
    int i = (int)x;
    return center_map[i] + (x - (float)i) * center_diffs[i];
}
void center_probe(void *engine, float *bank, const int *raw,
                  int part, int voice, int osc) {
    void *modulation = *(void **)((char *)engine + 0x2a0);
    float cm = *center_get_mod(modulation, voice, 9 + osc);
    /* Both signed zeros must preserve the original bank, even if endpoints
       alone are modulated across Center. NaNs/infinities retain stock handling. */
    if (cm == 0 || !__builtin_isfinite(cm)) return;
    void *params = *(void **)((char *)engine + 0x20c0);
    if (!center_get_param(params, part, 5 + osc * 0x41)) return;
    float sm = *center_get_mod(modulation, voice, 3 + osc);
    float em = *center_get_mod(modulation, voice, 5 + osc);
    if (!__builtin_isfinite(sm) || !__builtin_isfinite(em)) return;
    float s = effective(raw[0], sm);
    float c = effective(raw[1], cm);
    float e = effective(raw[3], em);
    if (s > e) return;
    float width = e - s;
    if (c < s) { s = c; e = c + width; }
    else if (c > e) { e = c; s = c - width; }
    else return;
    bank[0] = mapped(s);
    bank[0x60] = mapped(e);
}
