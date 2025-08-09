"""MIDI data structures and loader.

This module provides:
- Note:      simple note event container
- TrackData: per-track note list + pitch bounds + per-track pitch scroll offset
- MidiDoc:   full song document with time-signature changes and derived segments

Usage:
    from midi_doc import MidiDoc, Note, TrackData
    doc = MidiDoc()
    doc.load("path/to/file.mid")
"""
from __future__ import annotations

from typing import List, Tuple, Optional, Dict
import math

# ---- MIDI parsing (mido) ----
try:
    import mido
except ImportError:  # makes the module importable without mido for tooling/IDE
    mido = None  # type: ignore


class Note:
    __slots__ = ("start_tick", "end_tick", "pitch", "velocity", "channel")

    def __init__(self, start_tick: int, end_tick: int, pitch: int, velocity: int, channel: int):
        self.start_tick = int(start_tick)
        self.end_tick = int(end_tick)
        self.pitch = int(pitch)
        self.velocity = int(velocity)
        self.channel = int(channel)


class TrackData:
    def __init__(self, name: str):
        self.name: str = name
        self.notes: List[Note] = []
        # Per-track vertical offset inside its row (piano-key scroll), in pixels
        self.pitch_scroll_px: float = 0.0
        # Pitch bounds for the track (inclusive)
        self.pitch_min: int = 127
        self.pitch_max: int = 0


class MidiDoc:
    """Loaded MIDI document with tracks and time-signature map.

    Attributes
    -----------
    path: str
        Source file path.
    ticks_per_beat: int
        PPQ from the MIDI header (aka ticks per quarter note).
    tracks: list[TrackData]
        Non-empty tracks containing parsed notes.
    total_ticks: int
        Absolute end tick of the song across all tracks.
    ts_changes: list[tuple[int,int,int]]
        Time-signature change events as (abs_tick, numerator, denominator).
    ts_segments: list[dict]
        Precomputed segments derived from ts_changes for efficient rendering.
        Each segment dict contains:
          - start_beats, end_beats: segment range in beats
          - num, den: time signature
          - beat_len: length of one beat (in quarter-note beats)
          - bar_len: length of one bar (in quarter-note beats)
          - measure_start_index: absolute measure index at the start of the segment
    """

    def __init__(self) -> None:
        self.path: str = ""
        self.ticks_per_beat: int = 480
        self.tracks: List[TrackData] = []
        self.total_ticks: int = 0
        self.ts_changes: List[Tuple[int, int, int]] = []
        self.ts_segments: List[Dict[str, float | int]] = []
        self.time_sig_num: int = 4
        self.time_sig_den: int = 4
        self.tempo_segments = []   # list[dict]: {start_tick, end_tick, start_beats, end_beats, us_per_beat, start_us, end_us}
        self.tempo_bpm_default = 120.0  # fallback if no tempo events

    # -------- Derived quantities --------
    @property
    def total_beats(self) -> float:
        return self.total_ticks / float(self.ticks_per_beat or 1)

    # -------- Loader --------
    def load(self, path: str) -> None:
        if not mido:
            raise RuntimeError("mido not installed. Run: pip install mido")

        mid = mido.MidiFile(path)
        self.path = path
        self.ticks_per_beat = int(mid.ticks_per_beat or 480)
        self.tracks.clear()
        self.ts_changes = []

        overall_last_tick = 0
        for t in mid.tracks:
            name: Optional[str] = None
            abs_tick = 0
            # key: (pitch, channel) -> (start_tick, velocity)
            active: Dict[Tuple[int, int], Tuple[int, int]] = {}
            td = TrackData(name="")

            for msg in t:
                abs_tick += msg.time
                if msg.type == "track_name" and name is None:
                    name = msg.name
                if msg.type == "time_signature":
                    num = int(getattr(msg, "numerator", 4) or 4)
                    den = int(getattr(msg, "denominator", 4) or 4)
                    self.ts_changes.append((abs_tick, num, den))
                if msg.type == "note_on" and msg.velocity > 0:
                    key = (int(msg.note), int(getattr(msg, "channel", 0)))
                    active[key] = (abs_tick, int(msg.velocity))
                elif (msg.type == "note_off") or (msg.type == "note_on" and msg.velocity == 0):
                    key = (int(msg.note), int(getattr(msg, "channel", 0)))
                    if key in active:
                        start_tick, vel = active.pop(key)
                        end_tick = abs_tick
                        if end_tick > start_tick:
                            td.notes.append(Note(start_tick, end_tick, key[0], vel, key[1]))
                            td.pitch_min = min(td.pitch_min, key[0])
                            td.pitch_max = max(td.pitch_max, key[0])

                overall_last_tick = max(overall_last_tick, abs_tick)

            # Close any dangling notes at end of track
            for (pitch, ch), (start_tick, vel) in active.items():
                td.notes.append(Note(start_tick, overall_last_tick, pitch, vel, ch))
                td.pitch_min = min(td.pitch_min, pitch)
                td.pitch_max = max(td.pitch_max, pitch)

            td.name = name or f"Track {len(self.tracks)}"
            if td.notes:
                self.tracks.append(td)

        self.total_ticks = overall_last_tick
        self._build_ts_segments()
        
        self._build_tempo_segments(mid)
        # Optional: expose a "current" bpm for UI (tempo at beat 0)
        if self.tempo_segments:
            self.tempo_bpm = 60_000_000.0 / self.tempo_segments[0]["us_per_beat"]
        else:
            self.tempo_bpm = self.tempo_bpm_default

    # -------- Time signature segments --------
    def _build_ts_segments(self) -> None:
        # Ensure at least a default signature
        if not self.ts_changes:
            self.ts_changes.append((0, 4, 4))
        # Sort by absolute tick
        self.ts_changes.sort(key=lambda t: t[0])
        # Ensure we have an entry at tick 0
        if self.ts_changes[0][0] > 0:
            first = self.ts_changes[0]
            self.ts_changes.insert(0, (0, int(first[1]), int(first[2])))

        self.ts_segments.clear()
        measure_index = 0
        tpq = float(self.ticks_per_beat or 1)
        for i, (tick, num, den) in enumerate(self.ts_changes):
            start_tick = int(tick)
            end_tick = int(self.ts_changes[i + 1][0]) if (i + 1) < len(self.ts_changes) else int(self.total_ticks)
            start_beats = start_tick / tpq
            end_beats = end_tick / tpq
            beat_len = 4.0 / float(den or 4)  # in quarter-note beats
            bar_len = float(num) * beat_len
            # Bars in this segment (for numbering)
            bars = 0
            if end_beats > start_beats and bar_len > 1e-9:
                bars = int(math.floor((end_beats - start_beats) / bar_len + 1e-9))

            self.ts_segments.append({
                'start_beats': start_beats,
                'end_beats': end_beats,
                'num': int(num),
                'den': int(den),
                'beat_len': beat_len,
                'bar_len': bar_len,
                'measure_start_index': measure_index,
            })
            measure_index += bars

        # Keep quick-ref to the first TS
        self.time_sig_num = int(self.ts_changes[0][1])
        self.time_sig_den = int(self.ts_changes[0][2])

    def _build_tempo_segments(self, mid: "mido.MidiFile"):
        """Build tempo map segments in microseconds with beat and tick ranges."""
        tpq = int(self.ticks_per_beat or mid.ticks_per_beat or 480)

        # Collect absolute-tick tempo events across ALL tracks
        tempo_events = []  # (abs_tick, us_per_beat)
        for trk in mid.tracks:
            t = 0
            for msg in trk:
                t += msg.time
                if msg.type == "set_tempo":
                    tempo_events.append((t, int(msg.tempo)))  # msg.tempo = microseconds per beat

        tempo_events.sort(key=lambda x: x[0])

        # Default tempo if none present
        DEFAULT_USPB = int(60_000_000 / self.tempo_bpm_default)  # e.g. 500_000 for 120 BPM

        # Build breakpoints: always have a 0-start tempo
        breakpoints = []
        if tempo_events and tempo_events[0][0] == 0:
            breakpoints.append((0, tempo_events[0][1]))
            breakpoints.extend(tempo_events[1:])
        else:
            breakpoints.append((0, DEFAULT_USPB))
            breakpoints.extend(tempo_events)

        # Determine total length in beats
        total_beats = float(self.total_beats or 0.0)
        # If we somehow don't have a total yet, estimate from the longest track end_tick
        if total_beats <= 0:
            max_tick = 0
            for td in self.tracks:
                if td.notes:
                    last_tick = max(n.end_tick for n in td.notes)
                    max_tick = max(max_tick, last_tick)
            total_beats = max_tick / float(tpq or 1)

        # Build segments with cumulative microseconds
        segs = []
        us_cursor = 0.0
        prev_tick = 0
        prev_beats = 0.0
        prev_uspb = breakpoints[0][1]

        for i in range(1, len(breakpoints)):
            btick, buspb = breakpoints[i]
            bbeats = btick / float(tpq)
            # duration of previous tempo span in beats
            dbeats = max(0.0, bbeats - prev_beats)
            if dbeats > 0:
                segs.append(dict(
                    start_tick=prev_tick,
                    end_tick=btick,
                    start_beats=prev_beats,
                    end_beats=bbeats,
                    us_per_beat=float(prev_uspb),
                    start_us=us_cursor,
                    end_us=us_cursor + dbeats * float(prev_uspb),
                ))
                us_cursor += dbeats * float(prev_uspb)

            prev_tick = btick
            prev_beats = bbeats
            prev_uspb = buspb

        # Final segment to song end
        if total_beats > prev_beats:
            dbeats = total_beats - prev_beats
            segs.append(dict(
                start_tick=prev_tick,
                end_tick=int(total_beats * tpq),
                start_beats=prev_beats,
                end_beats=total_beats,
                us_per_beat=float(prev_uspb),
                start_us=us_cursor,
                end_us=us_cursor + dbeats * float(prev_uspb),
            ))
            us_cursor += dbeats * float(prev_uspb)

        self.tempo_segments = segs
        self.total_us = us_cursor  # total song length in microseconds

    def beat_to_us(self, beat: float) -> float:
        """Map an absolute beat position to absolute microseconds using tempo map."""
        segs = self.tempo_segments
        if not segs:
            # fallback to constant tempo
            uspb = 60_000_000 / float(getattr(self, "tempo_bpm_default", 120.0))
            return float(beat) * float(uspb)

        # binary search would be nicer; linear is fine (tempo events are few)
        for s in segs:
            if s["start_beats"] <= beat < s["end_beats"]:
                return s["start_us"] + (beat - s["start_beats"]) * s["us_per_beat"]
        # after last
        last = segs[-1]
        if beat >= last["end_beats"]:
            extra = max(0.0, beat - last["end_beats"])
            return last["end_us"] + extra * last["us_per_beat"]
        # before first
        first = segs[0]
        if beat < first["start_beats"]:
            return max(0.0, first["start_us"] - (first["start_beats"] - beat) * first["us_per_beat"])
        return 0.0

    def us_to_beat(self, us: float) -> float:
        """Map absolute microseconds to absolute beats using tempo map."""
        segs = self.tempo_segments
        if not segs:
            uspb = 60_000_000 / float(getattr(self, "tempo_bpm_default", 120.0))
            return float(us) / float(uspb)

        for s in segs:
            if s["start_us"] <= us < s["end_us"]:
                return s["start_beats"] + (us - s["start_us"]) / s["us_per_beat"]
        # after last
        last = segs[-1]
        if us >= last["end_us"]:
            extra = max(0.0, us - last["end_us"])
            return last["end_beats"] + extra / last["us_per_beat"]
        # before first
        first = segs[0]
        if us < first["start_us"]:
            deficit = first["start_us"] - us
            return max(0.0, first["start_beats"] - deficit / first["us_per_beat"])
        return 0.0



__all__ = [
    "Note",
    "TrackData",
    "MidiDoc",
]
