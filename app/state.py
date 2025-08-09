"""Application state and UI helpers.

Usage:
    from state import AppState, clamp, center_track_pitch_scroll,
        compute_track_pitch_bounds, zoom_to_fit_time, zoom_to_fit_vertical,
        zoom_reset, zoom_time_center
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Tuple, Set
import math

from app.midi_doc import MidiDoc, TrackData
from tracker.types import FurnaceConfig

# ----------------- Helpers -----------------

def clamp(v: float, lo: float, hi: float) -> float:
    return lo if v < lo else hi if v > hi else v


def beats_to_x(px_per_beat: float, beats: float, scroll_x_px: float, canvas_x: float) -> float:
    return canvas_x + (beats * px_per_beat) - scroll_x_px


def tick_to_beats(ticks: int, tpq: int) -> float:
    return ticks / float(tpq or 1)


def compute_track_pitch_bounds(state: "AppState") -> tuple[bool, int, int]:
    has_notes = False
    gmin, gmax = 127, 0
    for td in state.midi.tracks:
        if not td.notes:
            continue
        has_notes = True
        gmin = min(gmin, td.pitch_min)
        gmax = max(gmax, td.pitch_max)
    return has_notes, gmin, gmax


def center_track_pitch_scroll(state: "AppState", td: TrackData) -> None:
    """Center the track's pitch range in its row using current note_height."""
    if td.pitch_min > td.pitch_max:
        return
    center_pitch = (td.pitch_min + td.pitch_max) * 0.5
    # y = row_top + 4 + pitch_scroll + (127 - center_pitch) * note_h  -> want row center
    row_center = state.track_height * 0.5
    td.pitch_scroll_px = row_center - 4 - (127.0 - center_pitch) * state.note_height


def zoom_to_fit_time(state: "AppState") -> None:
    if state.last_canvas_width <= 0:
        return
    if state.midi.total_beats <= 0:
        return
    drawable_w = max(1.0, state.last_canvas_width - state.track_header_w - 16)
    beats = max(1.0, state.midi.total_beats)
    state.px_per_beat = clamp(drawable_w / beats, 10.0, 400.0)
    state.scroll_x_px = 0.0


def zoom_to_fit_vertical(state: "AppState") -> None:
    """Fit the largest pitch range across all tracks into a single track height."""
    largest_range = 0
    for td in state.midi.tracks:
        if not td.notes:
            continue
        prange = (td.pitch_max - td.pitch_min + 1)
        largest_range = max(largest_range, prange)

    if largest_range <= 0:
        return

    available = max(8, state.track_height - 8)  # small margins
    new_note_h = max(2, int(available / largest_range))
    state.note_height = int(clamp(new_note_h, 2, 48))

    # Recenter each track range
    for td in state.midi.tracks:
        center_track_pitch_scroll(state, td)


def zoom_reset(state: "AppState") -> None:
    state.px_per_beat = 60.0
    state.track_height = 120
    state.note_height = 8
    state.scroll_x_px = 0.0
    state.scroll_y_px = 0.0
    for td in state.midi.tracks:
        td.pitch_scroll_px = 0.0


def zoom_time_center(state: "AppState", factor: float) -> None:
    """Zoom horizontally around the center of the visible timeline area."""
    view_w = max(1.0, state.last_canvas_width - state.track_header_w - 18.0)
    pivot_px = view_w * 0.5
    time_beats_at_pivot = (state.scroll_x_px + pivot_px) / max(1e-6, state.px_per_beat)
    state.px_per_beat = clamp(state.px_per_beat * factor, 10.0, 400.0)
    state.scroll_x_px = max(0.0, time_beats_at_pivot * state.px_per_beat - pivot_px)


# ----------------- State -----------------

@dataclass
class AppState:
    should_quit: bool = False
    show_demo: bool = False
    show_zoom_settings: bool = True
    show_info_pane: bool = True

    # Drawing / layout
    px_per_beat: float = 60.0
    track_height: int = 120
    note_height: int = 8
    ruler_h: int = 28
    track_header_w: int = 160

    # Global scroll (canvas space, pixels)
    scroll_x_px: float = 0.0
    scroll_y_px: float = 0.0

    # Interactions
    panning: bool = False
    pan_anchor: Tuple[float, float] = (0.0, 0.0)
    pan_scroll_anchor: Tuple[float, float] = (0.0, 0.0)

    # Selection / marquee
    selected_notes: Set[Tuple[int, int]] = field(default_factory=set)
    marquee_active: bool = False
    marquee_start: Tuple[float, float] = (0.0, 0.0)
    marquee_end: Tuple[float, float] = (0.0, 0.0)

    # Custom vertical scrollbar drag state
    vsb_dragging: bool = False
    vsb_anchor_mouse_y: float = 0.0
    vsb_anchor_scroll_y: float = 0.0

    # MIDI
    midi: MidiDoc = field(default_factory=MidiDoc)

    # Window/canvas cache
    window_size: Tuple[int, int] = (1280, 720)
    last_canvas_width: float = 0.0
    last_canvas_height: float = 0.0

    # View menu actions (set by menu, consumed in draw)
    request_fit_time: bool = False
    request_fit_vertical: bool = False
    request_fit_all: bool = False
    request_reset_zoom: bool = False

    playhead_beats = 0.0
    playing = False
    play_start_time_ms = 0
    play_start_beats = 0.0
    play_return_beats = 0.0
    play_end_beats = 0.0
    play_start_us = 0.0
    play_end_us = 0.0
    play_events = []
    play_next_index = 0

    master_gain = 0.5

    show_tracker_settings = True
    tracker_cfg = FurnaceConfig()

    pending_export_popup: str | None = None
    
__all__ = [
    "AppState",
    "clamp",
    "beats_to_x",
    "tick_to_beats",
    "compute_track_pitch_bounds",
    "center_track_pitch_scroll",
    "zoom_to_fit_time",
    "zoom_to_fit_vertical",
    "zoom_reset",
    "zoom_time_center",
]
