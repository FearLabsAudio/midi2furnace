# tracker/export.py
import math
from typing import List, Tuple, Dict, Set
from tracker.types import FurnaceConfig

NOTE_NAMES = ["C","C#","D","D#","E","F","F#","G","G#","A","A#","B"]

def _midi_to_name_oct(note: int, transpose_octaves: int) -> Tuple[str, str, int]:
    n = max(0, min(127, int(note) + 12 * transpose_octaves))
    name = NOTE_NAMES[n % 12]
    letter = name[0]
    accidental = '#' if (len(name) >= 2 and name[1] == '#') else '-'
    octave = n // 12 - 1
    return letter, accidental, octave

def _vol_hex(vel: int, cfg: FurnaceConfig) -> str:
    if not cfg.velocity_enabled:
        return ".."
    vmax = int(cfg.velocity_max_hex or "FF", 16) & 0xFF
    v = max(0, min(127, int(vel)))
    out = round(v / 127.0 * vmax)
    return f"{out:02X}"

def _note_on_cell(note: int, vel: int, cfg: FurnaceConfig) -> str:
    L, acc, octv = _midi_to_name_oct(note, cfg.transpose_octaves)
    if cfg.define_instrument:
        inst = (cfg.instrument_hex or "00").upper().strip()
        if len(inst) != 2:
            try:
                inst = f"{int(inst or '0', 16) & 0xFF:02X}"
            except Exception:
                inst = "00"
    else:
        inst = ".."  # <<< no instrument defined

    vol = _vol_hex(vel, cfg)  # returns ".." when velocity mapping is off
    return f"{L}{acc}{octv}{inst}{vol}...."   # 11 chars

def _off_cell(cfg: FurnaceConfig) -> str:
    # OFF or REL + 8 dots
    tag = cfg.note_off_mode if cfg.note_off_mode in ("OFF", "REL") else "OFF"
    return f"{tag}{'.'*8}"

def _blank_cell() -> str:
    return "..........."  # 11 dots

def _quantize_beats_to_line(beat: float, lpq: int) -> int:
    return int(round(beat * lpq))

def _gather_notes(state, cfg: FurnaceConfig):
    """Return:
       items: list[(ti, sl, el, pitch, vel)]
       min_line, max_line: int (exclusive end)
       used_tracks: sorted list of track indices used
       by_track: dict[ti] -> list[(sl, el, pitch, vel)]
    """
    tpq = state.midi.ticks_per_beat or 480
    lpq = max(1, int(cfg.lines_per_quarter))
    items: List[Tuple[int,int,int,int,int]] = []
    used: Set[int] = set()
    by_track: Dict[int, List[Tuple[int,int,int,int]]] = {}

    if state.selected_notes:
        src = list(state.selected_notes)
    else:
        src = [(ti, ni) for ti, td in enumerate(state.midi.tracks) for ni, _ in enumerate(td.notes)]

    for (ti, ni) in src:
        td = state.midi.tracks[ti]
        n = td.notes[ni]
        sb = n.start_tick / tpq
        eb = n.end_tick  / tpq
        sl = _quantize_beats_to_line(sb, lpq)
        el = _quantize_beats_to_line(eb, lpq)
        if el <= sl:
            el = sl + 1  # ensure >= 1 line
        items.append((ti, sl, el, n.pitch, n.velocity))
        used.add(ti)
        by_track.setdefault(ti, []).append((sl, el, n.pitch, n.velocity))

    if not items:
        return [], 0, 0, [], {}

    min_l = min(sl for _, sl, _, _, _ in items)
    max_l = max(el for _, _, el, _, _ in items)
    return items, min_l, max_l, sorted(used), by_track

def _max_concurrency(intervals: List[Tuple[int,int]]) -> int:
    """Given (start,end) line intervals, return peak active overlap."""
    events: List[Tuple[int,int]] = []
    for sl, el in intervals:
        events.append((sl, +1))
        events.append((el, -1))
    events.sort()
    cur = 0
    peak = 0
    for _, d in events:
        cur += d
        peak = max(peak, cur)
    return peak

def build_furnace_clipboard_text(state, cfg: FurnaceConfig) -> Tuple[bool, str]:
    """Return (ok, text_or_error). On success, ok=True and text is the clipboard payload."""
    cfg.sanitize()
    items, min_line, max_line, used_tracks, by_track = _gather_notes(state, cfg)
    header = "org.tildearrow.furnace - Pattern Data (219)\n0\n"

    if not items:
        return True, header  # nothing selected -> minimal header

    total_lines = max(1, max_line - min_line)  # rows
    lpq = max(1, int(cfg.lines_per_quarter))

    if cfg.polyphony_mode == "spillover":
        # Require single track selection
        if len(used_tracks) > 1:
            return False, ("Spillover export requires notes from a single track.\n"
                           f"{len(used_tracks)} tracks detected in the selection.")
        ti = used_tracks[0] if used_tracks else 0
        track_items = by_track.get(ti, [])
        # channels needed = concurrency (clamped to spillover_count)
        intervals = [(sl, el) for (sl, el, _, _) in track_items]
        need = max(1, _max_concurrency(intervals))
        chans = max(1, min(int(cfg.spillover_count), need))

        # grid: rows x chans
        grid: List[List[str]] = [[_blank_cell() for _ in range(chans)] for __ in range(total_lines)]

        # spillover placement with stomp
        chan_ends = [ -10**9 for _ in range(chans) ]   # end line per subchannel
        off_events: Dict[int, List[int]] = {}          # line -> list[subch]

        # sort by (start, end, pitch) for stable placement
        for (tix, sl, el, pitch, vel) in sorted(items, key=lambda x: (x[1], x[2], x[3])):
            if tix != ti:
                continue
            sl_rel = sl - min_line
            el_rel = el - min_line
            # find free subch
            free = None
            for j in range(chans):
                if chan_ends[j] <= sl_rel:
                    free = j
                    break
            if free is None:
                # stomp oldest (smallest end)
                j = min(range(chans), key=lambda k: chan_ends[k])
                # emit OFF at sl_rel unless a note-on is here already
                if grid[sl_rel][j] == _blank_cell():
                    grid[sl_rel][j] = _off_cell(cfg)
                chan_ends[j] = sl_rel
                free = j

            # place note-on
            grid[sl_rel][free] = _note_on_cell(pitch, vel, cfg)
            # schedule OFF at el_rel if no new note-on overwrites it
            off_events.setdefault(el_rel, []).append(free)
            chan_ends[free] = el_rel

        # emit OFFs
        for line, subs in off_events.items():
            for sub in subs:
                if 0 <= line < total_lines and grid[line][sub] == _blank_cell():
                    grid[line][sub] = _off_cell(cfg)

        # compose
        bar = "|"
        out_lines = ["".join(cell + bar for cell in row) for row in grid]
        return True, header + "\n".join(out_lines)

    # ----- per_track (channel-per-track) -----
    # Only include channels for tracks that actually have notes in this export
    track_order = used_tracks  # already sorted
    track_to_ch = {ti: idx for idx, ti in enumerate(track_order)}
    chans = len(track_order)

    grid: List[List[str]] = [[_blank_cell() for _ in range(chans)] for __ in range(total_lines)]

    # Overlap counting per *included* track
    active_counts: Dict[int, int] = {ti: 0 for ti in track_order}
    dec_events: Dict[int, List[int]] = {}  # line -> list[ti]

    # place note-ons, remember when to decrement
    for (ti, sl, el, pitch, vel) in sorted(items, key=lambda x: (x[0], x[1], x[2], x[3])):
        if ti not in track_to_ch:
            continue
        ch = track_to_ch[ti]
        sl_rel = sl - min_line
        el_rel = el - min_line
        grid[sl_rel][ch] = _note_on_cell(pitch, vel, cfg)
        active_counts[ti] = active_counts.get(ti, 0) + 1
        dec_events.setdefault(el_rel, []).append(ti)

    # emit OFFs when last overlapping note ends (per track)
    for line in range(total_lines):
        for ti in dec_events.get(line, []):
            active_counts[ti] = max(0, active_counts.get(ti, 0) - 1)
            if active_counts[ti] == 0:
                ch = track_to_ch[ti]
                if grid[line][ch] == _blank_cell():
                    grid[line][ch] = _off_cell(cfg)

    # compose
    bar = "|"
    out_lines = ["".join(cell + bar for cell in row) for row in grid]
    return True, header + "\n".join(out_lines)

def copy_selection_to_clipboard(state, cfg: FurnaceConfig) -> Tuple[bool, str]:
    """(ok, message). On success, message='Copied'. On error, message explains why."""
    ok, text_or_error = build_furnace_clipboard_text(state, cfg)
    if not ok:
        return False, text_or_error

    text = text_or_error
    # Try imgui first (often available on all platforms)
    try:
        import imgui
        try:
            imgui.set_clipboard_text(text)
            return True, "Copied"
        except Exception:
            pass
    except Exception:
        pass
    # Fallback to pyperclip
    try:
        import pyperclip
        pyperclip.copy(text)
        return True, "Copied"
    except Exception:
        pass
    # Last resort: Tk
    try:
        import tkinter as tk
        r = tk.Tk(); r.withdraw()
        r.clipboard_clear(); r.clipboard_append(text); r.update(); r.destroy()
        return True, "Copied"
    except Exception:
        return False, "Failed to access any clipboard backend"
