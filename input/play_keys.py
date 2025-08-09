# input/play_keys.py
import imgui

def handle_play_keys(io, state):
    # don't trigger while typing in text boxes
    try:
        if getattr(io, "want_text_input", False):
            return
    except Exception:
        pass

    pressed = False
    KeyEnum = getattr(imgui, "Key", None)
    if KeyEnum is not None and hasattr(KeyEnum, "Space"):
        try:
            pressed = imgui.is_key_pressed(getattr(KeyEnum, "Space"), repeat=False)
        except Exception:
            pass
    if not pressed:
        legacy = getattr(imgui, "KEY_SPACE", None)
        if legacy is not None:
            try:
                pressed = imgui.is_key_pressed(legacy, repeat=False)
            except Exception:
                pass

    if pressed:
        from audio.player import start_playback, stop_playback
        if getattr(state, "playing", False):
            stop_playback(state, restore_cursor=True)
        else:
            start_playback(state)
