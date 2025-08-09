import imgui
from tracker.export import copy_selection_to_clipboard

def handle_shortcuts(io, state, on_open, on_copy=None):
    """Ctrl+O/Q/... cross-version, falls back to pygame if needed."""
    import pygame as _pg

    mod_ctrl = bool(getattr(io, "key_ctrl", False)) or bool(
        _pg.key.get_mods() & (_pg.KMOD_LCTRL | _pg.KMOD_RCTRL)
    )
    if not mod_ctrl:
        return

    def _pressed(letter: str) -> bool:
        KeyEnum = getattr(imgui, "Key", None)
        if KeyEnum is not None and hasattr(KeyEnum, letter):
            try:
                return imgui.is_key_pressed(getattr(KeyEnum, letter), repeat=False)
            except Exception:
                pass
        legacy = getattr(imgui, f"KEY_{letter}", None)
        if legacy is not None:
            try:
                return imgui.is_key_pressed(legacy, repeat=False)
            except Exception:
                pass
        try:
            return _pg.key.get_pressed()[getattr(_pg, f"K_{letter.lower()}")]
        except Exception:
            return False

    if _pressed("O"):
        on_open()
    if _pressed("Q"):
        state.should_quit = True
    if _pressed("S"):
        print("[Action] Save")
    if _pressed("N"):
        print("[Action] New")
    if _pressed("C"):
        ok, msg = copy_selection_to_clipboard(state, state.tracker_cfg)
        if not ok:
            state.pending_export_popup = msg or "Export failed."
            state.show_tracker_settings = True  # bring the settings window forward


def handle_global_keys(io, state):
    """ESC clears selection; cross-version + pygame fallback."""
    esc = False
    KeyEnum = getattr(imgui, "Key", None)
    if KeyEnum is not None and hasattr(KeyEnum, "Escape"):
        try:
            esc = imgui.is_key_pressed(getattr(KeyEnum, "Escape"), repeat=False)
        except Exception:
            pass
    if not esc:
        legacy = getattr(imgui, "KEY_ESCAPE", None)
        if legacy is not None:
            try:
                esc = imgui.is_key_pressed(legacy, repeat=False)
            except Exception:
                pass
    if not esc:
        try:
            import pygame as _pg
            esc = _pg.key.get_pressed()[_pg.K_ESCAPE]
        except Exception:
            pass
    if esc:
        state.selected_notes.clear()
        state.marquee_active = False
        state.playhead_beats = 0.0
