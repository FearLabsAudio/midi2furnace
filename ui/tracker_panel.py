# ui/tracker_panel.py
import imgui
from tracker.types import FurnaceConfig
from tracker.export import copy_selection_to_clipboard

def draw_tracker_settings_window(state):
    if not getattr(state, "show_tracker_settings", False):
        return
    imgui.begin("Furnace Export Settings")
    cfg: FurnaceConfig = state.tracker_cfg

    changed, lpq = imgui.slider_int("Lines per 1/4 note", cfg.lines_per_quarter, 1, 32)
    if changed: cfg.lines_per_quarter = lpq

    changed, tr = imgui.slider_int("Transpose (octaves)", cfg.transpose_octaves, -6, 6)
    if changed: cfg.transpose_octaves = tr

    # Instrument / Velocity
    imgui.separator()

    # NEW: Define Instrument toggle
    changed, definst = imgui.checkbox("Define Instrument", cfg.define_instrument)
    if changed:
        cfg.define_instrument = definst

    # Instrument (hex) — dim and read-only if Define Instrument is off
    readonly_flag = getattr(imgui, "INPUT_TEXT_READ_ONLY", 0)
    inst_flags = imgui.INPUT_TEXT_CHARS_UPPERCASE | (0 if cfg.define_instrument else readonly_flag)

    _pushed = False
    if not cfg.define_instrument:
        try:
            style = imgui.get_style()
            imgui.push_style_var(imgui.STYLE_ALPHA, style.alpha * 0.5)
            _pushed = True
        except Exception:
            pass

    changed, inst = imgui.input_text("Instrument (hex)", cfg.instrument_hex, 4, inst_flags)
    if cfg.define_instrument and changed:
        cfg.instrument_hex = inst.strip().upper()

    if _pushed:
        imgui.pop_style_var()

    # Velocity mapping checkbox — correctly use (changed, value)
    changed, v_on = imgui.checkbox("Velocity mapping", cfg.velocity_enabled)
    if changed:
        cfg.velocity_enabled = v_on

    # Velocity max — dim + read-only when velocity mapping is off
    readonly_flag = getattr(imgui, "INPUT_TEXT_READ_ONLY", 0)
    vmax_flags = imgui.INPUT_TEXT_CHARS_UPPERCASE | (0 if cfg.velocity_enabled else readonly_flag)

    _pushed = False
    if not cfg.velocity_enabled:
        try:
            style = imgui.get_style()
            imgui.push_style_var(imgui.STYLE_ALPHA, style.alpha * 0.5)
            _pushed = True
        except Exception:
            pass

    changed, vmax = imgui.input_text("Velocity max (hex)", cfg.velocity_max_hex, 4, vmax_flags)
    if cfg.velocity_enabled and changed:
        cfg.velocity_max_hex = vmax.strip().upper()

    if _pushed:
        imgui.pop_style_var()

    # Note-off mode
    imgui.separator()
    imgui.text("Note-off")
    off_off  = (cfg.note_off_mode == "OFF")
    off_rel  = (cfg.note_off_mode == "REL")
    if imgui.radio_button("OFF", off_off): cfg.note_off_mode = "OFF"
    imgui.same_line()
    if imgui.radio_button("REL", off_rel): cfg.note_off_mode = "REL"

    # Polyphony
    imgui.separator()
    imgui.text("Polyphony")
    p1 = (cfg.polyphony_mode == "per_track")
    p2 = (cfg.polyphony_mode == "spillover")
    if imgui.radio_button("Channel per track", p1):
        cfg.polyphony_mode = "per_track"
    if imgui.radio_button("Spillover", p2):
        cfg.polyphony_mode = "spillover"

    # --- Compatibility-friendly "disabled" UI for spillover count ---
    disabled = (cfg.polyphony_mode != "spillover")

    _pushed = False
    if disabled:
        # Dim the widget to look disabled
        try:
            style = imgui.get_style()
            imgui.push_style_var(imgui.STYLE_ALPHA, style.alpha * 0.5)
            _pushed = True
        except Exception:
            pass

    changed, c = imgui.slider_int("Spillover count", cfg.spillover_count, 1, 16)
    if not disabled and changed:
        cfg.spillover_count = c

    if _pushed:
        imgui.pop_style_var()

    imgui.separator()
    # Copy + status (uses the new (ok, msg) return)
    if imgui.button("Copy selection to Furnace (Ctrl+C)"):
        ok, msg = copy_selection_to_clipboard(state, cfg)
        if ok:
            imgui.same_line()
            imgui.text_colored("Copied!", 0.6, 1.0, 0.6, 1.0)
        else:
            state.pending_export_popup = msg or "Export failed."
            try:
                imgui.open_popup("Export Warning")
            except Exception:
                pass

    # Modal for warnings/errors (e.g., spillover with multi-track selection)
    if getattr(state, "pending_export_popup", None):
        try:
            imgui.open_popup("Export Warning")
        except Exception:
            pass
    try:
        opened = imgui.begin_popup_modal("Export Warning")[0]
    except Exception:
        opened = False
    if opened:
        imgui.text_wrapped(state.pending_export_popup)
        if imgui.button("OK"):
            imgui.close_current_popup()
            state.pending_export_popup = None
        imgui.end_popup()

    # --- Lightweight live preview ---
    imgui.separator()
    imgui.text("Preview")

    from tracker.export import build_furnace_clipboard_text
    ok, text_or_err = build_furnace_clipboard_text(state, cfg)

    # Fill to right + bottom; add horizontal scrollbar
    min_h = 240.0
    avail_w, avail_h = imgui.get_content_region_available()
    child_w = 0.0                     # 0 = take full remaining width
    child_h = max(min_h, float(avail_h))

    # Some pyimgui builds might not have the constant; fall back to 0.
    HSCROLL = getattr(imgui, "WINDOW_HORIZONTAL_SCROLLING_BAR", 0)

    imgui.begin_child("##furnace_preview", child_w, child_h, True, HSCROLL)

    # Important: use unwrapped text so long lines can scroll horizontally
    if ok:
        try:
            imgui.text_unformatted(text_or_err)
        except Exception:
            for line in text_or_err.splitlines():
                imgui.text_unformatted(line)
    else:
        imgui.text_colored("Cannot preview export:", 1.0, 0.5, 0.5, 1.0)
        imgui.separator()
        imgui.text_wrapped(text_or_err)

    imgui.end_child()

    imgui.end()
