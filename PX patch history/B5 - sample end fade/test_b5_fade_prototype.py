#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Executable adversarial host tests; no firmware output is ever generated."""
import copy
import hashlib
import json
import math
import random
import struct
import sys
import unittest
from pathlib import Path

from b5_fade_prototype import (BLOCK, H, HORIZON, Config, Fade, FadeScheduler,
                               InputTimeline, Reader, RecoveredResampler,
                               cvttsd2si, f32, first_window_logical,
                               first_window_physical, pcm, read_count, run_stream)

ROOT = Path(__file__).resolve().parent
METRICS = {'oracle_cases': 0, 'early_offsets': [], 'ramp_intervals': [],
           'shortened_intervals': [], 'max_hold_outputs': 0}
COUNTEREXAMPLES = []


def seeded_stream(rate, phase, write, endpoint, reverse=False, channels=2):
    cfg = Config(100, 100 + endpoint, rate, reverse).normalized()
    reader = Reader(cfg, channels, cursor=cfg.b - write if reverse else cfg.a + write)
    sampler = RecoveredResampler(channels, phase, write)
    # Prime actual physical memory using explicit historical source identities.
    for i in range(max(0, write - 1024), write):
        src = cfg.b - 1 - i if reverse else cfg.a + i
        if i < endpoint:
            sampler.ring[i & 1023] = pcm(src, channels)
        else:
            from b5_fade_prototype import zero
            sampler.ring[i & 1023] = zero('terminal', channels)
    batch = reader.read(read_count(rate))
    copied, pre_w = sampler.load(batch, rate)
    reader.consume(copied)
    tracker = InputTimeline()
    e = tracker.accept_loaded(batch, 0, copied, pre_w)
    return cfg, reader, sampler, e


def oracle_first_hit(reader, sampler, limit=HORIZON):
    """Detect actual terminal tags in contiguous physical reads, not a formula."""
    for base in range(0, limit, BLOCK):
        _, footprints = sampler.generate()
        for j, footprint in enumerate(footprints):
            if base + j >= limit:
                return None
            if 'terminal' in footprint[3]:
                return base + j
        batch = reader.read(read_count(sampler.rate))
        copied, _ = sampler.load(batch, sampler.rate)
        reader.consume(copied)
    return None


class B5Tests(unittest.TestCase):
    def test_01_boundary_prediction_physical_oracle_grid(self):
        rng = random.Random(0xB5)
        rates = [0.01, 0.1, 0.5, 0.99999994, 1.0, 1.125, 4.0, 31.5, 32.0]
        for rate in rates:
            for reverse in [False, True]:
                for base in [0, 1008, 4090]:
                    for frac in [0.0, 0.125, 0.999999999]:
                        phase = base + frac
                        write = base
                        gap = max(1, int(f32(rate) * rng.randrange(25, 290)))
                        cfg, reader, sampler, e = seeded_stream(rate, phase, write, write + gap, reverse)
                        prediction = first_window_physical(sampler.phase, cfg.rate, e, sampler.write)
                        truth = oracle_first_hit(reader, sampler)
                        METRICS['oracle_cases'] += 1
                        self.assertEqual(prediction, truth, (rate, reverse, phase, write, e))

    def test_02_forward_reverse_mapping_offset_and_stereo(self):
        for reverse in [False, True]:
            cfg = Config(17, 617, 1.0, reverse)
            reader = Reader(cfg, channels=2)
            batch = reader.read(650)
            actual_terminal = next(i for i, f in enumerate(batch.frames) if f.kind == 'terminal')
            self.assertEqual(actual_terminal, 600)
            self.assertEqual(batch.frames[0].source, 616 if reverse else 17)
            self.assertEqual(batch.frames[599].source, 17 if reverse else 616)
            timeline = InputTimeline()
            e = timeline.accept_loaded(batch, offset=41, copied=27, pre_w=2000)
            self.assertEqual(e - 2000 + 41, actual_terminal)
            self.assertNotEqual(e, 2000 + actual_terminal)  # Catches forgotten Load offset.
            self.assertNotEqual(batch.frames[0].values[0], batch.frames[0].values[1])

    def test_03_high_rate_logical_predictor_counterexample(self):
        cfg, reader, sampler, e = seeded_stream(32.0, 9216.0, 9217, 10236)
        logical = first_window_logical(sampler.phase, cfg.rate, e)
        physical = first_window_physical(sampler.phase, cfg.rate, e, sampler.write)
        truth = oracle_first_hit(reader, sampler)
        self.assertEqual((logical, physical, truth), (32, 0, 0))
        COUNTEREXAMPLES.append({'id': 'F1-high-rate-ring-alias', 'rate': 32,
                               'phase': 9216, 'E': e, 'W_after_load': 10241,
                               'old_T_offset': logical, 'actual_T_offset': truth,
                               'old_zero_at': 320, 'required_zero_at': 288,
                               'old_gain_at_actual_terminal': 32 / 240})

    def test_04_startup_truncation_mutant(self):
        cfg, reader, sampler, e = seeded_stream(0.5, 0.25, 0, 1)
        truth = oracle_first_hit(reader, sampler)
        phi = 0.25
        floor_hit = None
        for j in range(HORIZON):
            if math.floor(phi - 14) + 12 >= 1:
                floor_hit = j
                break
            phi += f32(0.5)
        self.assertEqual(truth, 4)
        self.assertEqual(floor_hit, 6)
        COUNTEREXAMPLES.append({'id': 'F2-floor-startup', 'phase': 0.25, 'rate': 0.5,
                               'E': 1, 'correct_first_hit': truth, 'floor_mutant': floor_hit})

    def test_05_float32_rate_and_sequential_double_additions(self):
        # A naive closed-form ceil with double r fails far from the origin.
        phi = 1048575.9900000672
        r = f32(0.01)
        e = 1048577
        exact = first_window_logical(phi, r, e, 1000)
        naive = math.ceil((e + 2 - phi) / r)
        self.assertNotEqual(exact, naive)
        COUNTEREXAMPLES.append({'id': 'F3-closed-form-rounding', 'phase': phi, 'rate_f32': r,
                               'E': e, 'sequential_hit': exact, 'division_ceil_hit': naive})
        # Check coefficient selection and phase with instruction-order oracle.
        _, reader, sampler, _ = seeded_stream(0.1, 1008.125, 1008, 2000)
        initial = sampler.phase
        _, footprint = sampler.generate()
        step = initial
        for phi, first, coeff, _ in footprint:
            self.assertEqual(phi, step)
            self.assertEqual(first, cvttsd2si(step - 14) & 1023)
            self.assertEqual(coeff, cvttsd2si(step * 128) & 127)
            step = float(f32(0.1)) + step
        self.assertEqual(sampler.phase, step)
        self.assertNotEqual(sampler.phase, initial + 32 * 0.1)

    def test_06_all_32_early_finish_offsets_and_full_240_ramp(self):
        for terminal in range(800, 832):
            stream = run_stream(Config(100, 100 + terminal, 1.0), 36, filter_tail=False)
            actual = next(i for i, fp in enumerate(stream['footprints']) if 'terminal' in fp[3])
            plan = next(x for x in stream['scheduler'].events if x['action'] == 'plan')
            z, s = plan['end'], plan['start']
            self.assertEqual(z - s, H)
            self.assertEqual(stream['gains'][s], 1)
            self.assertEqual(stream['gains'][z], 0)
            self.assertTrue(all(stream['gains'][s + j + 1] < stream['gains'][s + j]
                                for j in range(H)))
            self.assertEqual(actual - z, actual % BLOCK)
            self.assertLessEqual(actual - z, 31)
            METRICS['ramp_intervals'].append(z - s)
            METRICS['early_offsets'].append(actual - z)
        self.assertEqual(set(METRICS['early_offsets']), set(range(32)))

    def test_07_low_and_high_rate_zero_before_actual_terminal(self):
        for rate, length in [(0.01, 33), (0.1, 150), (0.5, 700), (1.125, 1300),
                             (4, 5000), (31.5, 10236), (32, 10236)]:
            for reverse in [False, True]:
                blocks = math.ceil(((length + 14) / f32(rate) + 64) / BLOCK)
                stream = run_stream(Config(23, 23 + length, rate, reverse), blocks)
                terminal = next(i for i, fp in enumerate(stream['footprints']) if 'terminal' in fp[3])
                plan = next(x for x in stream['scheduler'].events if x['action'] == 'plan')
                self.assertEqual(plan['duration'], H)
                self.assertTrue(0 <= terminal - plan['end'] <= 31, (rate, reverse, terminal, plan))
                self.assertEqual(stream['gains'][terminal], 0)

    def test_08_horizon_must_include_block_rounded_ramp_start(self):
        cfg, reader, sampler, e = seeded_stream(1.0, 0, 0, 285)
        t = oracle_first_hit(copy.deepcopy(reader), copy.deepcopy(sampler))
        self.assertEqual(t, 287)
        self.assertIsNone(first_window_physical(sampler.phase, 1, e, sampler.write, limit=240))
        self.assertEqual(first_window_physical(sampler.phase, 1, e, sampler.write), 287)
        sched = FadeScheduler(cfg)
        _, gains = sched.render([(1.0, 2.0)] * BLOCK, sampler.phase, sampler.write, e)
        self.assertEqual((sched.fade.start, sched.fade.end), (16, 256))
        self.assertEqual(gains[16], 1)
        self.assertLess(gains[17], 1)
        COUNTEREXAMPLES.append({'id': 'F4-short-lookahead', 'E': e, 'T': 287,
                               'required_S': 16, 'horizon_240_misses_first_fade_block': True,
                               'fixed_horizon': HORIZON})

    def test_09_full_region_threshold_against_duration_fraction(self):
        from fractions import Fraction
        for rate in [0.01, 0.1, 0.5, 1, 1.125, 4, 32]:
            r = f32(rate)
            cut = H * r
            for length in sorted(set([max(1, math.floor(cut) - 1), max(1, math.floor(cut)),
                                      max(1, math.ceil(cut)), math.ceil(cut) + 1])):
                cfg = Config(300, 300 + length, r)
                duration = Fraction(length, 1) / Fraction.from_float(r) / 48000
                self.assertEqual(cfg.eligible(), duration > Fraction(5, 1000))
                if not cfg.eligible():
                    data = run_stream(cfg, 10)
                    self.assertTrue(all(g == 1 for g in data['gains']))
                    self.assertEqual(data['audio'], data['raw'])
                    self.assertFalse(data['scheduler'].events)
        for length in [239, 240]:
            self.assertFalse(Config(0, length, 1).eligible())
        self.assertTrue(Config(0, 241, 1).eligible())

    def test_10_shortened_late_start_has_unity_first_gain(self):
        # Full region long, but note starts 130 source frames from its endpoint.
        data = run_stream(Config(0, 1000, 1), 12, cursor=870)
        plan = next(x for x in data['scheduler'].events if x['action'] == 'plan')
        self.assertEqual((plan['start'], plan['end'], plan['duration']), (0, 128, 128))
        self.assertEqual(data['gains'][0], 1)
        self.assertEqual(data['gains'][128], 0)
        self.assertLess(plan['duration'], H)
        METRICS['shortened_intervals'].append(plan['duration'])
        old_first_gain = 128 / H
        self.assertNotEqual(old_first_gain, data['gains'][0])
        COUNTEREXAMPLES.append({'id': 'F5-fixed-denominator-late-start',
                               'available_span': 128, 'old_initial_gain': old_first_gain,
                               'revised_initial_gain': data['gains'][0]})

    def test_11_barely_eligible_startup_clips_240_span(self):
        data = run_stream(Config(0, 241, 1), 10)
        plan = next(x for x in data['scheduler'].events if x['action'] == 'plan')
        self.assertEqual(plan['duration'], 224)
        self.assertEqual(plan['start'], 0)
        self.assertEqual(data['gains'][0], 1)
        self.assertLess(plan['duration'], H)
        METRICS['shortened_intervals'].append(plan['duration'])

    def test_12_immediate_late_control_shortens_without_prehold(self):
        # At 320 the old endpoint is distant. The new region remains >5ms long,
        # but its endpoint is only about 112 input frames ahead of the cursor.
        requests = {320: Config(0, 450, 1)}
        data = run_stream(Config(0, 2000, 1), 20, requests)
        app = next(x for x in data['scheduler'].events if x['action'] == 'apply')
        plan = next(x for x in data['scheduler'].events if x['action'] == 'plan')
        self.assertEqual(app['at'], 320)
        self.assertEqual(plan['start'], 320)
        self.assertLessEqual(plan['duration'], H)
        self.assertEqual(data['gains'][320], 1)
        self.assertFalse(data['scheduler'].completed_holds)
        METRICS['shortened_intervals'].append(plan['duration'])

    def test_13_no_positive_span_does_not_manufacture_shutdown(self):
        cfg = Config(0, 1000, 1)
        sched = FadeScheduler(cfg)
        # Late start/cut: terminal window appears before the next block boundary.
        _, gains = sched.render([(1.0, -0.5)] * BLOCK, phase=0, loaded_w=33, endpoint=10)
        self.assertEqual(gains, [1.0] * BLOCK)
        self.assertIsNone(sched.fade)
        self.assertEqual(sched.events[0]['action'], 'no-positive-span')
        sched.begin_block(Config(0, 2000, 1))
        self.assertEqual(sched.effective.b, 2000)

    def test_14_before_first_audible_block_control_is_not_deferred(self):
        # Baseline E=802: Z=800,S=560; first ramp block starts at 544.
        data = run_stream(Config(0, 802, 1), 35, requests={544: Config(0, 1300, 0.5)})
        self.assertEqual(data['config'][544].b, 1300)
        self.assertTrue(all(g == 1 for g in data['gains'][:800]))
        self.assertFalse(data['scheduler'].completed_holds)

    def test_15_active_only_deferral_and_completion_latest_wins(self):
        data = run_stream(Config(0, 802, 1), 39,
                          requests={576: Config(0, 1200, 0.5),
                                    608: Config(0, 1350, 2),
                                    768: Config(0, 1700, 0.75)})
        holds = data['scheduler'].completed_holds
        self.assertEqual([x['released'] for x in holds], [800, 800, 800])
        self.assertEqual([x['requested'] for x in holds], [576, 608, 768])
        self.assertEqual(data['config'][799].key(), Config(0, 802, 1).key())
        self.assertEqual(data['config'][800].key(), Config(0, 1700, 0.75).key())
        for event in holds:
            delay = event['released'] - event['requested']
            self.assertTrue(event['audible'])
            self.assertLessEqual(delay, H)
            METRICS['max_hold_outputs'] = max(METRICS['max_hold_outputs'], delay)
        self.assertEqual(METRICS['max_hold_outputs'], 224)
        # A mutant releasing one extra block later would violate the 5ms cap.
        self.assertGreater(800 + BLOCK - 576, H)

    def test_16_request_at_completion_overrides_pending_immediately(self):
        data = run_stream(Config(0, 802, 1), 37,
                          requests={576: Config(0, 1200, 0.5), 800: Config(0, 1800, 1)})
        self.assertEqual(data['config'][800].b, 1800)
        self.assertEqual(data['config'][800].rate, 1)
        self.assertTrue(all(x['released'] == 800 for x in data['scheduler'].completed_holds))

    def test_17_extension_after_completion_resumes_without_noteon(self):
        for reverse in [False, True]:
            cfg = Config(2000, 2802, 1, reverse)
            extended = Config(0 if reverse else 2000, 2802 if reverse else 4000, 1, reverse)
            data = run_stream(cfg, 48, requests={864: extended}, custom=False)
            self.assertTrue(all(g == 0 for g in data['gains'][800:864]))
            self.assertEqual(data['config'][864].key(), extended.key())
            self.assertEqual(data['gains'][864], 1)
            self.assertTrue(any(any(v != 0 for v in f) for f in data['audio'][880:1000]))
            self.assertEqual(data['audio'][864:1000], data['raw'][864:1000])
            self.assertFalse(data['scheduler'].completed_holds)

    def test_18_unchanged_completion_cannot_rebound(self):
        data = run_stream(Config(0, 802, 1), 45, filter_tail=True)
        self.assertTrue(any(any(v != 0 for v in f) for f in data['raw'][800:1000]))
        self.assertTrue(all(g == 0 for g in data['gains'][800:]))
        self.assertTrue(all(f == (0.0, 0.0) for f in data['audio'][800:]))
        self.assertEqual(len([x for x in data['scheduler'].events if x['action'] == 'plan']), 1)
        COUNTEREXAMPLES.append({'id': 'F6-unity-after-fade-rebound',
                               'raw_filter_value_at_Z': list(data['raw'][800]),
                               'correct_output_at_Z': list(data['audio'][800])})

    def test_19_queued_short_region_obeys_bypass_at_completion(self):
        data = run_stream(Config(0, 802, 1), 30, requests={576: Config(700, 900, 1)})
        self.assertEqual(data['config'][799].b, 802)
        self.assertEqual(data['config'][800].a, 700)
        self.assertTrue(all(g == 1 for g in data['gains'][800:]))

    def test_20_speculation_and_unavailable_output_never_commit(self):
        cfg = Config(0, 802, 1)
        reader, sched = Reader(cfg), FadeScheduler(cfg)
        before = copy.deepcopy(sched.__dict__)
        for _ in range(31):
            reader.read(1000)
        self.assertEqual(reader.cursor, 0)
        self.assertEqual(sched.__dict__, before)
        self.assertEqual(sched.render([(1.0, 1.0)] * BLOCK, 0, 33, 802, available=False), [])
        self.assertEqual(sched.__dict__, before)
        self.assertEqual(sched.begin_block(Config(0, 1200, 0.5)).b, 1200)

    def test_21_partial_load_and_shortage_zero_are_not_terminal(self):
        reader = Reader(Config(0, 1000, 1))
        batch = reader.read(100)
        sampler = RecoveredResampler()
        copied, w = sampler.load(batch, 1, offset=7, available=5)
        self.assertEqual(copied, 5)
        self.assertEqual(sampler.write, 33)
        tracker = InputTimeline()
        e = tracker.accept_loaded(batch, 7, copied, w, needed=33)
        self.assertIsNone(e)
        _, footprints = sampler.generate()
        self.assertTrue(any('shortage' in fp[3] for fp in footprints))
        self.assertFalse(any('terminal' in fp[3] for fp in footprints))
        self.assertIsNone(tracker.forecast_for(reader.config))

    def test_22_start_delay_not_terminal_and_does_not_advance_source(self):
        data = run_stream(Config(0, 802, 1), 38, delay=64, filter_tail=False)
        actual = next(i for i, fp in enumerate(data['footprints']) if 'terminal' in fp[3])
        self.assertEqual(actual, 868)
        self.assertTrue(any('delay' in fp[3] for fp in data['footprints'][:100]))
        plan = next(x for x in data['scheduler'].events if x['action'] == 'plan')
        self.assertEqual(plan['end'], 864)

    def test_23_looping_passthrough_and_immediate_mode_change(self):
        for reverse in [False, True]:
            for length, rate in [(33, 4), (802, 1)]:
                data = run_stream(Config(0, length, rate, reverse, True), 60)
                self.assertEqual(data['audio'], data['raw'])
                self.assertEqual(data['gains'], [1.0] * (60 * BLOCK))
                self.assertFalse(data['scheduler'].events)
                self.assertFalse(data['scheduler'].completed_holds)
        cfg = Config(0, 802, 1)
        data = run_stream(cfg, 25, requests={576: Config(0, 802, 1, loop=True)})
        self.assertTrue(all(g == 1 for g in data['gains'][576:]))
        self.assertFalse(data['scheduler'].completed_holds)

    def test_24_stereo_shared_clock_and_no_pcm_history_rewrites(self):
        cfg = Config(0, 1000, 1.125)
        stereo = run_stream(cfg, 35, channels=2)
        mono = run_stream(cfg, 35, channels=1)
        self.assertEqual(stereo['gains'], mono['gains'])
        self.assertEqual(stereo['scheduler'].clock, 35 * BLOCK)
        for raw, out, gain in zip(stereo['raw'], stereo['audio'], stereo['gains']):
            self.assertEqual(out, tuple(v * gain for v in raw))
        # Independent untouched baseline Load/Generate sequence has identical memory.
        reader, baseline = Reader(cfg, channels=2), RecoveredResampler(channels=2)
        for _ in range(35):
            batch = reader.read(read_count(cfg.rate))
            copied, _ = baseline.load(batch, cfg.rate)
            baseline.generate()
            reader.consume(copied)
        self.assertEqual(stereo['resampler'].ring, baseline.ring)
        self.assertEqual(stereo['resampler'].guard, baseline.guard)
        self.assertEqual(stereo['resampler'].phase, baseline.phase)
        self.assertEqual(stereo['resampler'].write, baseline.write)
        self.assertEqual(stereo['reader'].cursor, reader.cursor)

    def test_25_nonfinite_rates_bypass_and_zero_gain_clears_nan(self):
        for r in [0, -1, math.nan, math.inf]:
            cfg = Config(0, 1000, r)
            sched = FadeScheduler(cfg)
            self.assertFalse(cfg.eligible())
            _, gains = sched.render([(1.0, 0.5)] * BLOCK, 0, 33, 1000)
            self.assertTrue(all(g == 1 for g in gains))
            self.assertFalse(sched.events)
        sched = FadeScheduler(Config(0, 1000, 1))
        sched.fade = Fade(0, 32, sched.effective.key())
        sched.clock = 32
        out, gains = sched.render([(math.nan, math.inf)] * BLOCK, 32, 65, 1000)
        self.assertEqual(out, [(0.0, 0.0)] * BLOCK)

    def test_26_original_voice_and_firmware_bytes_untouched(self):
        pins = {'voice_2.2.2.0.2_qnx.elf': '651f0ac3339f4f41a4c0bc562cdf4c72df821d85aad3f689e700612b8c8b05e7',
                'voice_2.2.2.0.2.bin': '2ad5392eb842cbcd5c2e85e65ab42c16f1fac12d16b09c417a61761a8348bcbf'}
        for name, expected in pins.items():
            self.assertEqual(hashlib.sha256((ROOT / name).read_bytes()).hexdigest(), expected)
        elf = (ROOT / 'voice_2.2.2.0.2_qnx.elf').read_bytes()
        self.assertEqual(elf[0x1b49e:0x1b4a3], bytes.fromhex('e9 ce eb 02 00'))
        self.assertEqual(elf[0x1b7e5:0x1b7ea], b'\x90' * 5)

    def test_27_loaded_batch_identity_not_latest_speculative_read(self):
        cfg = Config(0, 1000, 1)
        reader, timeline, sampler = Reader(cfg), InputTimeline(), RecoveredResampler()
        actual = reader.read(96)
        reader.config = Config(0, 2000, 1)
        reader.read(96)  # A newer speculative descriptor is not the loaded one.
        copied, w = sampler.load(actual, 1)
        timeline.accept_loaded(actual, 0, copied, w)
        self.assertEqual(timeline.forecast_for(cfg), 1000)
        self.assertIsNone(timeline.forecast_for(reader.config))
        sampler.generate()
        reader.consume(copied)
        fresh = reader.read(96)
        copied, w = sampler.load(fresh, 1)
        timeline.accept_loaded(fresh, 0, copied, w)
        self.assertEqual(timeline.forecast_for(reader.config), 2000)

    def test_28_latest_request_revert_cancels_queued_extension(self):
        cfg = Config(0, 802, 1)
        data = run_stream(cfg, 36, requests={576: Config(0, 1400, 0.5), 608: cfg})
        self.assertEqual(data['config'][800].key(), cfg.key())
        self.assertTrue(all(g == 0 for g in data['gains'][800:]))
        self.assertTrue(all(x['released'] == 800 for x in data['scheduler'].completed_holds))

    def test_29_note_reuse_drops_old_completion_and_pending(self):
        cfg = Config(0, 802, 1)
        sched = FadeScheduler(cfg)
        sched.clock = 576
        sched.fade = Fade(560, 800, cfg.key())
        sched.begin_block(Config(0, 1500, 0.5))
        self.assertIsNotNone(sched.pending)
        sched.note_on(cfg)
        self.assertEqual(sched.clock, 0)
        self.assertIsNone(sched.fade)
        self.assertIsNone(sched.pending)
        self.assertFalse(sched.deferred)

    def test_30_direction_change_not_added_to_control_deferral(self):
        cfg = Config(0, 802, 1)
        sched = FadeScheduler(cfg)
        sched.clock = 576
        sched.fade = Fade(560, 800, cfg.key())
        new = Config(0, 802, 1, reverse=True)
        self.assertEqual(sched.begin_block(new).key(), new.key())
        self.assertIsNone(sched.fade)
        self.assertFalse(sched.pending)

    def test_31_shortage_then_new_anchor_revises_prediction_not_history(self):
        cfg = Config(0, 300, 1)
        reader, sampler, timeline = Reader(cfg), RecoveredResampler(), InputTimeline()
        batch = reader.read(96)
        copied, w = sampler.load(batch, 1, available=5)
        timeline.accept_loaded(batch, 0, copied, w, needed=33)
        self.assertIsNone(timeline.forecast_for(cfg))
        reader.consume(copied)
        sampler.generate()
        fresh = reader.read(96)
        copied, w = sampler.load(fresh, 1)
        timeline.accept_loaded(fresh, 0, copied, w, needed=sampler.loads[-1][1])
        reader.consume(copied)
        e = timeline.forecast_for(cfg)
        self.assertEqual(e, 328)  # 300 real frames + 28 inserted shortage zeros.
        prediction = first_window_physical(sampler.phase, 1, e, sampler.write)
        # Extend oracle far enough to see this later endpoint.
        truth = oracle_first_hit(reader, sampler, limit=400)
        self.assertEqual(prediction, truth)
        self.assertEqual(truth + 32, 330)
        old_z, correct_z = (302 // 32) * 32, (330 // 32) * 32
        self.assertGreater(330 - old_z, 31)
        COUNTEREXAMPLES.append({'id': 'F7-forecast-is-not-observed-EOF',
                               'shortage_inputs': 28, 'old_E': 300, 'actual_E': e,
                               'old_Z': old_z, 'revised_Z': correct_z,
                               'old_early_finish': 330-old_z})

    def test_32_no_output_during_fade_cancels_deferral_not_history(self):
        cfg, new = Config(0, 802, 1), Config(0, 1400, 0.5)
        sched = FadeScheduler(cfg)
        sched.fade = Fade(560, 800, cfg.key())
        sched.clock = 576
        sched.begin_block(new)
        self.assertEqual(sched.effective.key(), cfg.key())
        sched.clock = 640
        sched.render([], 640, 673, 802, available=False)
        self.assertIsNone(sched.fade)
        self.assertIsNone(sched.pending)
        self.assertEqual(sched.effective.key(), new.key())
        self.assertEqual(sched.completed_holds[0]['released'], 640)
        self.assertEqual(sched.completed_holds[0]['resolution'], 'unavailable-cancel')
        for _ in range(20):
            sched.render([], 640, 673, 802, available=False)
        self.assertEqual(sched.clock, 640)
        self.assertFalse(sched.audible_ramp())
        self.assertEqual(sched.begin_block(Config(0, 1600, 1)).b, 1600)
        COUNTEREXAMPLES.append({'id': 'F8-unavailable-return-stale-hold',
                               'request_at': 576, 'failure_at': 640,
                               'stalled_clock_while_silent_blocks_pass': True,
                               'fix': 'cancel active B5/hold on zero-output return'})

    def test_33_every_block_application_point_is_inside_ramp_or_immediate(self):
        cfg, new = Config(0, 802, 1), Config(0, 1400, 0.5)
        for c in range(512, 865, 32):
            sched = FadeScheduler(cfg)
            sched.fade = Fade(560, 800, cfg.key())
            sched.clock = c
            active = 560 < c < 800
            out = sched.begin_block(new)
            self.assertEqual(bool(sched.pending), active)
            if active:
                self.assertEqual(out.key(), cfg.key())
                sched.clock = 800
                self.assertEqual(sched.begin_block().key(), new.key())
                self.assertLessEqual(800 - c, H)
            else:
                self.assertEqual(out.key(), new.key())

    def test_34_logical_predictor_mutant_leaks_at_real_terminal_end_to_end(self):
        from unittest.mock import patch
        cfg = Config(0, 10236, 32)
        corrected = run_stream(cfg, 12, filter_tail=False)
        with patch('b5_fade_prototype.first_window_physical',
                   lambda phase, rate, endpoint, loaded_w: first_window_logical(phase, rate, endpoint)):
            mutant = run_stream(cfg, 12, filter_tail=False)
        terminal = next(i for i, fp in enumerate(corrected['footprints']) if 'terminal' in fp[3])
        self.assertEqual(terminal, 288)
        self.assertEqual(corrected['gains'][terminal], 0)
        self.assertEqual(mutant['gains'][terminal], 32 / H)
        self.assertNotEqual(mutant['audio'][terminal], (0.0, 0.0))
        self.assertEqual(corrected['audio'][terminal], (0.0, 0.0))
        # Same original ring/phase/PCM; only proposed scheduling differs.
        self.assertEqual(corrected['resampler'].ring, mutant['resampler'].ring)
        self.assertEqual(corrected['raw'], mutant['raw'])


class RecordingResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.case_results = []

    def addSuccess(self, test):
        super().addSuccess(test)
        self.case_results.append({'name': test._testMethodName, 'status': 'pass'})

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.case_results.append({'name': test._testMethodName, 'status': 'fail',
                                  'detail': self._exc_info_to_string(err, test)})

    def addError(self, test, err):
        super().addError(test, err)
        self.case_results.append({'name': test._testMethodName, 'status': 'error',
                                  'detail': self._exc_info_to_string(err, test)})


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(B5Tests)
    result = unittest.TextTestRunner(verbosity=2, resultclass=RecordingResult).run(suite)
    report = {'scope': 'host-only; no firmware execution or changes',
              'tests': result.testsRun, 'failures': len(result.failures), 'errors': len(result.errors),
              'cases': result.case_results, 'metrics': METRICS, 'counterexamples': COUNTEREXAMPLES,
              'limitations': ['Synthetic 13-tap weights and filter, not acoustic validation',
                              'Ordinary stream model, not full legacy loop/splice emulator',
                              'Control timing relative to original block-application points',
                              'No target QNX loader, unwind execution or machine-code patch']}
    (ROOT / 'b5_fade_prototype_results.json').write_text(json.dumps(report, indent=2) + '\n')
    sys.exit(not result.wasSuccessful())
