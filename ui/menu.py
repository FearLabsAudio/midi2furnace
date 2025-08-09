import imgui

def draw_menu_bar(state, *, on_open, ini_path: str, on_copy=None):
    if imgui.begin_main_menu_bar():
        if imgui.begin_menu("File", True):
            if imgui.menu_item("Open…", "Ctrl+O", False, True)[0]:
                on_open()
            imgui.separator()
            if imgui.menu_item("Quit", "Ctrl+Q", False, True)[0]:
                state.should_quit = True
            imgui.end_menu()

        if imgui.begin_menu("Edit", True):
            if on_copy and imgui.menu_item("Copy selection to Furnace", "Ctrl+C", False, True)[0]:
                on_copy()
            imgui.end_menu()

        if imgui.begin_menu("View", True):
            if imgui.menu_item("Zoom Settings…", None, state.show_zoom_settings, True)[0]:
                state.show_zoom_settings = not state.show_zoom_settings
            if imgui.menu_item("Info Pane", None, state.show_info_pane, True)[0]:
                state.show_info_pane = not state.show_info_pane
            if imgui.menu_item("Furnace Export Settings…", None, state.show_tracker_settings, True)[0]:
                state.show_tracker_settings = not state.show_tracker_settings
            imgui.separator()
            if imgui.menu_item("Zoom to Fit (Time)", None, False, True)[0]:
                state.request_fit_time = True
            if imgui.menu_item("Zoom to Fit (Vertical)", None, False, True)[0]:
                state.request_fit_vertical = True
            if imgui.menu_item("Zoom to Fit (All)", None, False, True)[0]:
                state.request_fit_all = True
            imgui.separator()
            if imgui.menu_item("Reset Zoom", None, False, True)[0]:
                state.request_reset_zoom = True
            imgui.separator()
            if imgui.menu_item("Load Layout", None, False, True)[0]:
                try:
                    imgui.load_ini_settings_from_disk(ini_path)
                except Exception as e:
                    print(f"[Layout] Load failed: {e}")
            if imgui.menu_item("Save Layout", None, False, True)[0]:
                try:
                    imgui.save_ini_settings_to_disk(ini_path)
                except Exception as e:
                    print(f"[Layout] Save failed: {e}")
            imgui.end_menu()

        imgui.end_main_menu_bar()
