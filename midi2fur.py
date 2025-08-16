import sys
import math
import pygame
from pygame.locals import DOUBLEBUF, OPENGL, RESIZABLE, VIDEORESIZE, QUIT
import OpenGL.GL as gl

import imgui
from imgui.integrations.pygame import PygameRenderer

from typing import List, Tuple, Optional


from input.shortcuts import handle_shortcuts, handle_global_keys
from input.nav import handle_navigation_keys
from ui.menu import draw_menu_bar
from ui.panels import draw_zoom_settings_window, draw_info_window
from ui.timeline import draw_timeline_canvas
from audio.player import update_playback
from input.play_keys import handle_play_keys
from ui.tracker_panel import draw_tracker_settings_window
from tracker.export import copy_selection_to_clipboard

from version import __version__


# Persist ImGui layout here
UI_INI_PATH = "imgui.ini"

# ---- bring in our split modules ----
from app.state import (
    AppState, clamp, beats_to_x, tick_to_beats,
    compute_track_pitch_bounds, center_track_pitch_scroll,
    zoom_to_fit_time, zoom_to_fit_vertical, zoom_reset, zoom_time_center,
)
from app.midi_doc import MidiDoc, Note, TrackData


# ---- simple file dialog for Open ----
def ask_open_midi() -> Optional[str]:
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        path = filedialog.askopenfilename(
            title="Open MIDI file",
            filetypes=[("MIDI files", "*.mid *.midi"), ("All files", "*.*")]
        )
        root.destroy()
        return path if path else None
    except Exception:
        return None


def do_open_file(state: AppState):
    path = ask_open_midi()
    if not path:
        return
    try:
        state.midi.load(path)
        # After load, try to fit both axes initially
        state.request_fit_all = True
    except Exception as e:
        print(f"Failed to open MIDI: {e}")


# ----------------- App -----------------
def main():
    # --- Pygame / GL init ---
    pygame.init()
    size = (1280, 720)
    flags = DOUBLEBUF | OPENGL | RESIZABLE

    def try_make_gl(size, flags):
        # Attempt 0: default (no attributes)
        try:
            pygame.display.set_mode(size, flags)
            return True, "default"
        except Exception as e0:
            print(f"[GL] default failed: {e0}")

        # Attempt 1: very compatible GL 2.1 (compat profile), no extra buffers
        try:
            try:
                pygame.display.gl_set_attribute(pygame.GL_CONTEXT_PROFILE_MASK, pygame.GL_CONTEXT_PROFILE_COMPATIBILITY)
            except Exception:
                pass
            for attr, val in [
                (pygame.GL_CONTEXT_MAJOR_VERSION, 2),
                (pygame.GL_CONTEXT_MINOR_VERSION, 1),
                (pygame.GL_DOUBLEBUFFER, 1),
                (pygame.GL_DEPTH_SIZE, 0),
                (pygame.GL_STENCIL_SIZE, 0),
                (pygame.GL_MULTISAMPLEBUFFERS, 0),
                (pygame.GL_MULTISAMPLESAMPLES, 0),
            ]:
                try: pygame.display.gl_set_attribute(attr, val)
                except Exception: pass
            pygame.display.set_mode(size, flags)
            return True, "GL 2.1 compat"
        except Exception as e1:
            print(f"[GL] GL 2.1 compat failed: {e1}")

        # Attempt 2: GL 3.2 core (some drivers prefer core profiles)
        try:
            try:
                pygame.display.gl_set_attribute(pygame.GL_CONTEXT_PROFILE_MASK, pygame.GL_CONTEXT_PROFILE_CORE)
            except Exception:
                pass
            for attr, val in [
                (pygame.GL_CONTEXT_MAJOR_VERSION, 3),
                (pygame.GL_CONTEXT_MINOR_VERSION, 2),
                (pygame.GL_DOUBLEBUFFER, 1),
                (pygame.GL_DEPTH_SIZE, 0),
                (pygame.GL_STENCIL_SIZE, 0),
                (pygame.GL_MULTISAMPLEBUFFERS, 0),
                (pygame.GL_MULTISAMPLESAMPLES, 0),
            ]:
                try: pygame.display.gl_set_attribute(attr, val)
                except Exception: pass
            pygame.display.set_mode(size, flags)
            return True, "GL 3.2 core"
        except Exception as e2:
            print(f"[GL] GL 3.2 core failed: {e2}")

        return False, "no GL context"

    ok, mode = try_make_gl(size, flags)
    if not ok:
        print("\n[Error] Could not create an OpenGL context. On Linux, install Mesa GL/GLX and run under X11/XWayland.\n"
            "Try: sudo apt install mesa-utils libgl1 libglu1-mesa libglx-mesa0\n"
            "If using Wayland, run: SDL_VIDEODRIVER=x11 ./midi2furnace\n")
        sys.exit(1)

    pygame.display.set_caption("MIDI Piano Roll (pyimgui)")
    gl.glViewport(0, 0, *pygame.display.get_surface().get_size())

    # (optional) Log GL info to help diagnose remote users
    try:
        ver = gl.glGetString(gl.GL_VERSION)
        rend = gl.glGetString(gl.GL_RENDERER)
        print(f"[GL] Context: {mode} | Version: {ver!r} | Renderer: {rend!r}")
    except Exception:
        pass


    # --- ImGui init ---
    imgui.create_context()
    io = imgui.get_io()
    io.config_flags |= imgui.CONFIG_NAV_ENABLE_KEYBOARD
    # Only allow moving windows from the title bar (not the content area)
    try:
        io.config_windows_move_from_title_bar_only = True
    except AttributeError:
        try:
            io.ConfigWindowsMoveFromTitleBarOnly = True
        except Exception:
            pass

    # Tell ImGui where to persist layout and load it
    try:
        io.ini_filename = UI_INI_PATH
    except AttributeError:
        try:
            io.ini_file_name = UI_INI_PATH
        except AttributeError:
            try:
                io.IniFilename = UI_INI_PATH
            except Exception:
                pass
    try:
        imgui.load_ini_settings_from_disk(UI_INI_PATH)
    except Exception as _e:
        # Non-fatal: we'll still run and save on exit
        print(f"[Layout] Load warning: {_e}")

    try:
        renderer = PygameRenderer(pygame.display.get_surface())
    except TypeError:
        renderer = PygameRenderer()

    clock = pygame.time.Clock()
    state = AppState()
    state.window_size = size

    try:
        while not state.should_quit:
            for event in pygame.event.get():
                if event.type == QUIT:
                    state.should_quit = True
                elif event.type == VIDEORESIZE:
                    size = event.size
                    pygame.display.set_mode(size, flags)
                    gl.glViewport(0, 0, *size)
                    state.window_size = size
                renderer.process_event(event)

            renderer.process_inputs()
            io.display_size = state.window_size

            imgui.new_frame()

            # UI
            draw_menu_bar(
                state,
                on_open=lambda: do_open_file(state),
                ini_path=UI_INI_PATH,
                on_copy=lambda: copy_selection_to_clipboard(state, state.tracker_cfg),
            )
            draw_zoom_settings_window(state)
            draw_info_window(state)
            draw_tracker_settings_window(state)

            # Update play transport and keys
            update_playback(state)
            draw_timeline_canvas(state)  # playhead draws inside this fn
            handle_navigation_keys(io, state)
            handle_play_keys(io, state)  # SPACE to toggle play
            handle_global_keys(io, state)
            handle_shortcuts(io, state, on_open=lambda: do_open_file(state),
                 on_copy=lambda: copy_selection_to_clipboard(state, state.tracker_cfg))

            if state.show_demo:
                imgui.show_demo_window()

            # Render
            gl.glClearColor(0.10, 0.10, 0.10, 1.0)
            gl.glClear(gl.GL_COLOR_BUFFER_BIT)

            imgui.render()
            renderer.render(imgui.get_draw_data())
            pygame.display.flip()
            clock.tick(120)
    finally:
        try:
            renderer.shutdown()
            try:
                imgui.save_ini_settings_to_disk(UI_INI_PATH)
            except Exception as _e:
                print(f"[Layout] Save warning: {_e}")
        except Exception:
            pass
        pygame.quit()
        try:
            if imgui.get_current_context() is not None:
                imgui.destroy_context()
        except Exception:
            pass


if __name__ == "__main__":
    main()
