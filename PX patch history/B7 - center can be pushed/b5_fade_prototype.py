#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Host-only B5 model. No ELF writes, patching, assembler or firmware execution.

The reader is an ordinary [A,B) stream, not the complete loop/splice machine.
Resampler Load/Generate indexing follows the recovered x86-64 arithmetic.
Tap values use an illustrative kernel; tag/phase tests do not depend on it.
"""
from __future__ import annotations

import math
import struct
from dataclasses import dataclass, replace

BLOCK = 32
H = 240
RING = 1024
HORIZON = H + 2 * BLOCK  # Includes an endpoint whose block-rounded S is in this block.


def f32(x: float) -> float:
    try:
        return struct.unpack('<f', struct.pack('<f', x))[0]
    except OverflowError:
        return math.copysign(math.inf, x)


def cvttsd2si(x: float) -> int:
    # x86 indefinite result, rather than Python's unbounded integer conversion.
    if not math.isfinite(x) or not -(2**31) <= x < 2**31:
        return -(2**31)
    return int(x)


@dataclass(frozen=True)
class Config:
    a: int
    b: int
    rate: float
    reverse: bool = False
    loop: bool = False

    def normalized(self) -> Config:
        return replace(self, rate=f32(self.rate))

    def key(self) -> tuple:
        return self.a, self.b, struct.pack('<f', f32(self.rate)), self.reverse, self.loop

    def eligible(self) -> bool:
        r = f32(self.rate)
        return (not self.loop and math.isfinite(r) and r > 0
                and self.b > self.a and (self.b - self.a) > H * float(r))


@dataclass(frozen=True)
class Frame:
    kind: str
    values: tuple[float, ...]
    source: int | None = None


def pcm(source: int, channels: int) -> Frame:
    words = ((source * 73 + 9001) % 50000 - 25000,
             (source * 197 + 17) % 60000 - 30000)
    return Frame('pcm', tuple(v / 32768.0 for v in words[:channels]), source)


def zero(kind: str, channels: int) -> Frame:
    return Frame(kind, (0.0,) * channels)


@dataclass(frozen=True)
class ReadBatch:
    config: Config
    cursor: int
    frames: tuple[Frame, ...]
    boundary_offset: int
    serial: int


class Reader:
    """Ordinary reader. read() is speculative; only consume() commits movement.

    Noncustom updater advances toward the whole-file boundary, as recovered;
    custom=True clamps to A/B. This distinction matters for endpoint extension.
    """
    def __init__(self, config: Config, channels=2, cursor=None,
                 file_frames=200000, delay=0, custom=False):
        self.config = config.normalized()
        self.channels = channels
        self.cursor = (config.b if config.reverse else config.a) if cursor is None else cursor
        self.file_frames = file_frames
        self.delay = delay
        self.custom = custom
        self.serial = 0

    def read(self, count: int) -> ReadBatch:
        cfg, p = self.config, self.cursor
        distance = max(0, p - cfg.a if cfg.reverse else cfg.b - p)
        out = []
        for j in range(count):
            if j < self.delay:
                out.append(zero('delay', self.channels))
                continue
            n = j - self.delay
            src = p - 1 - n if cfg.reverse else p + n
            if cfg.loop and cfg.b > cfg.a:
                src = cfg.a + ((src - cfg.a) % (cfg.b - cfg.a))
                out.append(pcm(src, self.channels))
            elif n < distance and cfg.a <= src < cfg.b:
                out.append(pcm(src, self.channels))
            else:
                out.append(zero('terminal', self.channels))
        self.serial += 1
        return ReadBatch(cfg, p, tuple(out), self.delay + distance, self.serial)

    def consume(self, count: int) -> None:
        d = min(count, self.delay)
        self.delay -= d
        count -= d
        if self.config.reverse:
            lo = self.config.a if self.custom else 0
            self.cursor = max(lo, self.cursor - count)
        else:
            hi = self.config.b if self.custom else self.file_frames - 1
            self.cursor = min(hi, self.cursor + count)


class InputTimeline:
    """One linear ordinary epoch; no ring or buffer repair machinery."""
    def __init__(self):
        self.key = None
        self.endpoint = None
        self.terminal_seen = False

    def accept_loaded(self, batch: ReadBatch, offset: int, copied: int, pre_w: float,
                      needed: int | None = None):
        if self.key != batch.config.key():
            self.key, self.endpoint = batch.config.key(), None
            self.terminal_seen = False
        if copied > 0:
            candidate = int(pre_w) + batch.boundary_offset - offset
            portion = batch.frames[offset:offset + copied]
            terminal = next((i for i, frame in enumerate(portion) if frame.kind == 'terminal'), None)
            if terminal is not None:
                actual = int(pre_w) + terminal
                self.endpoint = min(self.endpoint, actual) if self.terminal_seen else actual
                self.terminal_seen = True
            elif not self.terminal_seen:
                # A prediction is not an observed terminal. A new source anchor
                # can move it after loader-inserted nonterminal shortage zeros.
                self.endpoint = candidate
        if needed is not None and copied < needed and not self.terminal_seen:
            self.endpoint = None  # No stable forecast across an incomplete Load.
        return self.endpoint

    def forecast_for(self, effective: Config):
        # An old buffered epoch is legacy control-change audio, not a forecast
        # of the newly accepted selected boundaries. Do not repair that history.
        return self.endpoint if self.key == effective.key() else None


class RecoveredResampler:
    """Independent instruction-shaped Load/Generate emulator with physical tags.

    It uses explicit contiguous ring+14 guard reads, not the scheduler's endpoint
    predicate. Synthetic normalized tap weights illustrate audio/tail behavior;
    the recovered coefficient tables and oscillator filter aren't reproduced.
    """
    def __init__(self, channels=2, phase=0.0, write=0.0):
        self.channels = channels
        self.phase, self.write = float(phase), float(write)
        self.rate = 1.0
        self.ring = [zero('startup', channels) for _ in range(RING)]
        self.guard = self.ring[:14]
        self.loads = []

    def load(self, batch: ReadBatch, rate: float, offset=0, available=None):
        self.rate = f32(rate)
        # cvtss2sd([r*32]); addsd phi; subsd W; addsd 1; cvttsd2si.
        n = cvttsd2si(((float(f32(self.rate * 32.0)) + self.phase) - self.write) + 1.0)
        if n < 0 or n > RING + 14:
            raise ValueError(f'unsupported recovered load count: {n}')
        if available is None:
            available = len(batch.frames) - offset
        copied = min(n, available)
        pre_w = self.write
        for j in range(n):
            frame = batch.frames[offset + j] if j < copied else zero('shortage', self.channels)
            self.ring[(cvttsd2si(pre_w) + j) & 1023] = frame
        self.write += float(n)
        self.guard = self.ring[:14]
        self.loads.append((pre_w, n, copied, offset, batch.serial))
        return copied, pre_w

    def generate(self, count=BLOCK):
        samples, footprints = [], []
        memory = self.ring + self.guard
        for _ in range(count):
            phi = self.phase
            first = cvttsd2si(phi - 14.0) & 1023
            coeff_phase = cvttsd2si(phi * 128.0) & 127
            taps = memory[first:first + 13]
            if len(taps) != 13:
                raise AssertionError('missing wrap guards')
            # Nonzero weights make terminal-tag influence visible in the model.
            weights = [1.0 + ((j + coeff_phase) % 7) / 10.0 for j in range(13)]
            norm = sum(weights)
            samples.append(tuple(sum(t.values[ch] * w for t, w in zip(taps, weights)) / norm
                                 for ch in range(self.channels)))
            footprints.append((phi, first, coeff_phase, tuple(t.kind for t in taps)))
            # cvtss2sd rate; addsd [phase]; movsd [phase]. No multiply by index.
            self.phase = float(self.rate) + self.phase
        return samples, footprints


def first_window_logical(phase: float, rate: float, endpoint: int, limit=HORIZON):
    """Prior design's logical-footprint predictor, kept to expose its failure."""
    phi, r = float(phase), float(f32(rate))
    for j in range(limit):
        if cvttsd2si(phi - 14.0) + 12 >= endpoint:
            return j
        phi = r + phi
    return None


def first_window_physical(phase: float, rate: float, endpoint: int,
                          loaded_w: float, limit=HORIZON):
    """Forecast the recovered ring's actual footprint, including load-ahead alias.

    At high r, Load can overwrite the current 13-tap history with future input.
    Latest physical slot identity follows W, not only trunc(phi-14). This is
    metadata arithmetic only; the prototype never rewrites ring samples.
    Assumes a contiguous ordinary epoch with terminal input from E onward.
    """
    phi, w, r = float(phase), float(loaded_w), float(f32(rate))
    if not math.isfinite(r) or r <= 0:
        return None
    r32 = float(f32(f32(rate) * 32.0))
    for j in range(limit):
        if j and j % BLOCK == 0:
            n = cvttsd2si(((r32 + phi) - w) + 1.0)
            if n < 0 or n > RING + 14:
                return None
            w += float(n)
        # Find newest unwrapped input occupying any of the 13 contiguous slots.
        latest_written = int(w) - 1
        first_slot = cvttsd2si(phi - 14.0) & 1023
        for tap in range(13):
            slot = (first_slot + tap) & 1023
            newest = latest_written - ((latest_written - slot) & 1023)
            if newest >= 0 and newest >= endpoint:
                return j
        phi = r + phi
    return None


@dataclass(frozen=True)
class Fade:
    start: int
    end: int
    key: tuple

    def gain(self, sample: int) -> float:
        return max(0.0, min(1.0, (self.end - sample) / float(self.end - self.start)))


class FadeScheduler:
    """Block-applied controls; only actual rendered ramp time authorizes holding."""
    def __init__(self, config: Config):
        self.effective = config.normalized()
        self.clock = 0
        self.fade = None
        self.no_opportunity_key = None
        self.pending = None
        self.events = []
        self.deferred = []
        self.completed_holds = []

    def audible_ramp(self) -> bool:
        return self.fade is not None and self.fade.start < self.clock < self.fade.end

    def note_on(self, config: Config):
        # Caller performs the existing reader/resampler resets; only B5 state here.
        self.__init__(config)

    def _apply(self, config: Config, reason: str):
        cfg = config.normalized()
        if cfg.key() != self.effective.key():
            self.effective = cfg
            self.fade = None
            self.no_opportunity_key = None
            self.events.append({'at': self.clock, 'action': 'apply', 'reason': reason,
                                'bounds': [cfg.a, cfg.b], 'rate': cfg.rate,
                                'reverse': cfg.reverse, 'loop': cfg.loop})

    def begin_block(self, request: Config | None = None) -> Config:
        if self.clock % BLOCK:
            raise AssertionError('original controls are applied at block boundaries')
        # Loop/direction changes are outside the approved endpoint/rate hold.
        immediate = request is not None and (request.loop != self.effective.loop
                                             or request.reverse != self.effective.reverse)
        if immediate:
            for event in self.deferred:
                event['released'] = self.clock
                event['resolution'] = 'mode-change'
                self.completed_holds.append(event)
            self.deferred.clear()
            self.pending = None
            self._apply(request, 'mode-change')
            return self.effective
        if self.audible_ramp():
            if request is not None and request.normalized().key() != self.effective.key():
                self.pending = request.normalized()
                event = {'requested': self.clock, 'audible': True,
                         'release_due': self.fade.end}
                self.deferred.append(event)
                self.events.append({'at': self.clock, 'action': 'defer'})
            elif request is not None:
                # Latest request reverting to the effective controls cancels pending.
                self.pending = request.normalized()
            return self.effective
        latest = request if request is not None else self.pending
        for event in self.deferred:
            event['released'] = self.clock
            event['resolution'] = 'coalesced/apply'
            self.completed_holds.append(event)
        self.deferred.clear()
        self.pending = None
        if latest is not None:
            self._apply(latest, 'ordinary-or-completion')
        return self.effective

    def _plan(self, phase: float, loaded_w: float, endpoint: int | None):
        if not self.effective.eligible():
            self.fade = None
            return
        key = self.effective.key()
        if self.fade is not None or self.no_opportunity_key == key or endpoint is None:
            return
        offset = first_window_physical(phase, self.effective.rate, endpoint, loaded_w)
        if offset is None:
            return
        end = ((self.clock + offset) // BLOCK) * BLOCK
        start = max(self.clock, end - H)
        if start >= self.clock + BLOCK:
            return  # No latch/hold yet; current controls remain immediately effective.
        if end <= self.clock:
            self.no_opportunity_key = key  # Preserve the existing late-control transient.
            self.events.append({'at': self.clock, 'action': 'no-positive-span'})
            return
        self.fade = Fade(start, end, key)
        self.events.append({'at': self.clock, 'action': 'plan', 'start': start, 'end': end,
                            'duration': end - start, 'first_terminal': self.clock + offset})

    def render(self, raw: list[tuple[float, ...]], phase: float,
               loaded_w: float, endpoint: int | None, available=True):
        if not available:
            # A nonrendered/error return ends audible fading. Holding a request
            # across repeated zero-output returns would have no wall-time bound.
            # Cancel B5 only; leave original PCM/history and error recovery alone.
            if self.audible_ramp() or self.deferred:
                for event in self.deferred:
                    event['released'] = self.clock
                    event['resolution'] = 'unavailable-cancel'
                    self.completed_holds.append(event)
                self.deferred.clear()
                latest, self.pending = self.pending, None
                self.fade = None
                self.no_opportunity_key = None
                self.events.append({'at': self.clock, 'action': 'unavailable-cancel'})
                if latest is not None:
                    self._apply(latest, 'unavailable-cancel')
            return []  # No envelope/output-clock commitment on unavailable output.
        if len(raw) != BLOCK:
            raise AssertionError('one original PlayNote block required')
        self._plan(phase, loaded_w, endpoint)
        gains = [self.fade.gain(self.clock + j) if self.fade else 1.0 for j in range(BLOCK)]
        out = [tuple(0.0 if g == 0 else value * g for value in frame)
               for frame, g in zip(raw, gains)]
        self.clock += BLOCK
        return out, gains


def read_count(rate: float) -> int:
    return min(0x440, (math.ceil(f32(rate)) + 2) * BLOCK)


def run_stream(config: Config, blocks: int, requests=None, channels=2,
               cursor=None, delay=0, custom=False, filter_tail=True):
    """Executable end-to-end host harness, returning both raw and B5 output.

    Filter is illustrative nonzero persistent history, not a recovered filter.
    Every PCM write is by original-style Load; B5 only scales rendered outputs.
    """
    requests = requests or {}
    reader = Reader(config, channels, cursor=cursor, delay=delay, custom=custom)
    resampler, scheduler, timeline = RecoveredResampler(channels), FadeScheduler(config), InputTimeline()
    history = [0.0] * channels
    result = {'raw': [], 'audio': [], 'gains': [], 'footprints': [], 'config': []}
    for _ in range(blocks):
        cfg = scheduler.begin_block(requests.get(scheduler.clock))
        reader.config = cfg
        batch = reader.read(read_count(cfg.rate))
        copied, pre_w = resampler.load(batch, cfg.rate)
        timeline.accept_loaded(batch, 0, copied, pre_w, needed=resampler.loads[-1][1])
        endpoint = timeline.forecast_for(cfg)
        phi, w = resampler.phase, resampler.write
        raw, footprints = resampler.generate()
        if filter_tail:
            filtered = []
            for frame in raw:
                for ch, value in enumerate(frame):
                    decay = 0.98 if ch == 0 else 0.995
                    history[ch] = history[ch] * decay + value * (1.0 - decay)
                filtered.append(tuple(history))
            raw = filtered
        audio, gains = scheduler.render(raw, phi, w, endpoint)
        reader.consume(copied)
        for name, values in [('raw', raw), ('audio', audio), ('gains', gains), ('footprints', footprints)]:
            result[name].extend(values)
        result['config'].extend([cfg] * BLOCK)
    result.update(scheduler=scheduler, reader=reader, resampler=resampler, timeline=timeline)
    return result


if __name__ == '__main__':
    import json
    example = run_stream(Config(100, 1500, 1.0), 52,
                         requests={1280: Config(100, 2300, 0.5)})
    print(json.dumps({'model': 'host only, no firmware edits',
                      'events': example['scheduler'].events,
                      'holds': example['scheduler'].completed_holds}, indent=2))
