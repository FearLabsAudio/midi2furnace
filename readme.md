# Midi to Furnace

A simple utility that allows one to open a MIDI file, select, and copy sequences of notes that may be pasted into Furnace Tracker (https://github.com/tildearrow/furnace)

---

## Quick Start

1. **Open** a MIDI file: `File -> Open…` or `Ctrl+O`.
2. **Zoom/Pan** to view notes (see controls below).
3. **Marquee-select** notes with left-drag.
4. Open **View -> Furnace Export Settings** (or it’s already open).
5. Adjust **Lines per 1/4 note**, instrument/velocity/overflow options.
6. Click **Copy selection to Furnace** (or hit `Ctrl+C`).  
   Paste into **Furnace** pattern editor.

---

## Controls

### Mouse

- **Middle or Right-drag**: pan
- **Wheel**: vertical scroll
- **Ctrl + Wheel**: horizontal zoom (time)
- **Shift + Wheel**: vertical zoom (track height)
- **Alt + Wheel**: note height zoom (global)
- **Alt + Wheel over a track**: pitch scroll within that track
- **Left-drag in roll**: marquee selection
- **Click in ruler**: move playhead

### Keyboard

- **Arrows**: pan (time / rows)
- **+ / -**: horizontal zoom
- **Shift (+ / -)**: vertical track zoom
- **PgUp / PgDn**: note height zoom
- **Space**: play/stop (selected notes if any, otherwise all)
- **Esc**: clear selection
- **Ctrl+O**: open MIDI
- **Ctrl+Q**: quit
- **Ctrl+C**: copy selection to Furnace format

---

## Requirements

See `requirements.txt`:
