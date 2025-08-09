import imgui
from app.state import center_track_pitch_scroll, compute_track_pitch_bounds

def draw_zoom_settings_window(state):
    if not state.show_zoom_settings:
        return
    imgui.begin("Zoom Settings")

    changed, pxb = imgui.slider_float("Pixels per Beat (h-zoom)", state.px_per_beat, 10.0, 400.0)
    if changed:
        state.px_per_beat = pxb

    changed, th = imgui.slider_int("Track height (v-zoom tracks)", state.track_height, 40, 400)
    if changed:
        state.track_height = th
        for td in state.midi.tracks:
            center_track_pitch_scroll(state, td)

    changed, nh = imgui.slider_int("Note height (v-zoom notes)", state.note_height, 2, 48)
    if changed:
        state.note_height = nh
        for td in state.midi.tracks:
            center_track_pitch_scroll(state, td)

    imgui.text("Tips:")
    imgui.bullet_text("Middle or Right-drag to pan")
    imgui.bullet_text("Ctrl + Wheel: horizontal zoom")
    imgui.bullet_text("Shift + Wheel: vertical track zoom")
    imgui.bullet_text("Alt + Wheel: note height zoom")
    imgui.bullet_text("Alt + Wheel over a track: scroll pitches in that track")
    imgui.bullet_text("Left-drag in roll: Marquee select")

    imgui.separator()
    imgui.text("Keyboard:")
    imgui.bullet_text("Arrow Keys: Pan (time / rows)")
    imgui.bullet_text("= / - : Horizontal zoom")
    imgui.bullet_text("Shift + (= / -): Vertical track zoom")
    imgui.bullet_text("PageUp / PageDown: Note height zoom")
    imgui.bullet_text("Esc: Clear selection")
    imgui.bullet_text("Space: Start/Stop selection note playback")

    imgui.end()


def draw_info_window(state):
    if not state.show_info_pane:
        return
    imgui.begin("Info")
    if state.midi.path:
        imgui.text(f"Loaded: {state.midi.path}")
        imgui.text(f"Tracks: {len(state.midi.tracks)}   Ticks/Beat: {state.midi.ticks_per_beat}")
        imgui.text(f"Length: {state.midi.total_beats:.2f} quarter-beats")
        has_notes, gmin, gmax = compute_track_pitch_bounds(state)
        if has_notes:
            imgui.text(f"Pitch span across tracks: {gmin}..{gmax} ({gmax-gmin+1} semitones)")
        if state.midi.ts_segments:
            imgui.separator()
            imgui.text("Time Signatures:")
            shown = 0
            for seg in state.midi.ts_segments:
                if shown >= 6:
                    imgui.text("…")
                    break
                imgui.bullet_text(f"{seg['num']}/{seg['den']} from {seg['start_beats']:.2f} to {seg['end_beats']:.2f} beats")
                shown += 1
    else:
        imgui.text("No MIDI loaded.")
    imgui.end()
