# audio/player.py
import math
import pygame
from audio.synth import init_audio, tone

def selection_bounds_in_beats(state):
    if not state.selected_notes:
        return None
    tpq = state.midi.ticks_per_beat or 480
    lo = math.inf
    hi = 0.0
    for (ti, ni) in state.selected_notes:
        td = state.midi.tracks[ti]
        n = td.notes[ni]
        lo = min(lo, n.start_tick / tpq)
        hi = max(hi, n.end_tick / tpq)
    return None if lo is math.inf else (lo, hi)

def build_schedule(state, start_b: float, end_b: float):
    """Precompute per-note start_us/end_us for fast, tempo-accurate playback."""
    ev = []
    tpq = state.midi.ticks_per_beat or 480
    if state.selected_notes:
        src = list(state.selected_notes)
    else:
        src = [(ti, ni) for ti, td in enumerate(state.midi.tracks) for ni, _ in enumerate(td.notes)]

    b2us = state.midi.beat_to_us
    for (ti, ni) in src:
        td = state.midi.tracks[ti]
        n = td.notes[ni]
        sb = n.start_tick / tpq
        eb = n.end_tick  / tpq
        if eb <= start_b or sb >= end_b:
            continue
        sb_clip = max(sb, start_b)
        eb_clip = max(sb_clip + 1e-4, min(eb, end_b))  # avoid zero-length
        ev.append({
            "start_beats": sb_clip,
            "end_beats": eb_clip,
            "start_us": b2us(sb_clip),
            "end_us": b2us(eb_clip),
            "pitch": n.pitch,
        })
    ev.sort(key=lambda e: e["start_us"])
    state.play_events = ev
    state.play_next_index = 0

def start_playback(state):
    init_audio()
    bounds = selection_bounds_in_beats(state)
    if bounds:
        start_b, end_b = bounds
    else:
        start_b = state.playhead_beats
        end_b = max(state.midi.total_beats, start_b)

    state.play_return_beats = state.playhead_beats
    state.play_start_beats = float(start_b)
    state.play_end_beats   = float(end_b)
    state.play_start_us    = state.midi.beat_to_us(state.play_start_beats)
    state.play_end_us      = state.midi.beat_to_us(state.play_end_beats)
    state.play_start_time_ms = pygame.time.get_ticks()
    state.playing = True

    build_schedule(state, start_b, end_b)

def stop_playback(state, *, restore_cursor=True):
    if not state.playing:
        return
    state.playing = False
    try:
        pygame.mixer.stop()
    except Exception:
        pass
    if restore_cursor:
        state.playhead_beats = getattr(state, "play_return_beats", state.playhead_beats)

def update_playback(state):
    if not state.playing:
        return
    now_ms = pygame.time.get_ticks()
    elapsed_ms = max(0, now_ms - state.play_start_time_ms)
    cur_us = state.play_start_us + elapsed_ms * 1000.0
    cur_beats = state.midi.us_to_beat(cur_us)
    state.playhead_beats = cur_beats

    # Fire due notes (tempo-accurate)
    idx = state.play_next_index
    ev = state.play_events
    while idx < len(ev) and ev[idx]["start_us"] <= cur_us:
        p = ev[idx]["pitch"]
        dur_ms = max(30, int((ev[idx]["end_us"] - ev[idx]["start_us"]) / 1000.0))
        freq = 440.0 * (2.0 ** ((p - 69) / 12.0))
        gain = getattr(state, "master_gain", 0.5)  # 0.5 = half, 0.25 = quarter
        ch = tone(freq, dur_ms).play()
        if ch:
            ch.set_volume(gain)
        idx += 1
    state.play_next_index = idx

    if cur_us >= state.play_end_us or (idx >= len(ev) and not ev):
        stop_playback(state)
