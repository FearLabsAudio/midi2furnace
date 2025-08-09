# ui/timeline.py
import math
import imgui
from app.state import clamp, center_track_pitch_scroll

def draw_timeline_canvas(state):
    """Main piano roll canvas: grid, notes, marquee, scrollbars, ruler."""
    imgui.begin("Piano Roll", True, flags=imgui.WINDOW_NO_SCROLLBAR | imgui.WINDOW_NO_SCROLL_WITH_MOUSE)
    canvas_pos = imgui.get_cursor_screen_pos()
    avail_w, avail_h = imgui.get_content_region_available()

    # Cache for view actions
    state.last_canvas_width = avail_w
    state.last_canvas_height = avail_h

    draw_list = imgui.get_window_draw_list()
    x0, y0 = canvas_pos
    x1, y1 = x0 + avail_w, y0 + avail_h

    # Reserve space for custom scrollbars
    sb = 18.0
    view_x1 = x1 - sb
    view_y1 = y1 - sb

    # Areas
    ruler_y0 = y0
    ruler_y1 = y0 + state.ruler_h
    track_area_y0 = ruler_y1
    track_area_y1 = view_y1

    # Backgrounds
    draw_list.add_rect_filled(x0, y0, x1, y1, imgui.get_color_u32_rgba(0.11, 0.11, 0.11, 1.0))
    draw_list.add_rect_filled(x0, track_area_y0, view_x1, track_area_y1, imgui.get_color_u32_rgba(0.12, 0.12, 0.12, 1.0))

    header_x0 = x0
    header_x1 = x0 + state.track_header_w
    draw_list.add_rect_filled(header_x0, track_area_y0, header_x1, track_area_y1, imgui.get_color_u32_rgba(0.14, 0.14, 0.14, 1.0))

    # ---- Apply View-menu zoom actions now that we know canvas sizes ----
    do_fit_time = state.request_fit_time or state.request_fit_all
    do_fit_vert = state.request_fit_vertical or state.request_fit_all

    if state.request_reset_zoom:
        # imported from state.py
        from state import zoom_reset
        zoom_reset(state)
        state.request_reset_zoom = False

    if do_fit_time and state.midi.total_beats > 0:
        drawable_w = max(1.0, (view_x1 - header_x1))
        beats = max(1.0, state.midi.total_beats)
        state.px_per_beat = clamp(drawable_w / beats, 10.0, 400.0)
        state.scroll_x_px = 0.0

    if do_fit_vert:
        # Fit max pitch span into one track height
        largest_range = 0
        for td in state.midi.tracks:
            if not td.notes:
                continue
            largest_range = max(largest_range, td.pitch_max - td.pitch_min + 1)
        if largest_range > 0:
            available = max(8, state.track_height - 8)
            new_note_h = max(2, int(available / largest_range))
            state.note_height = clamp(new_note_h, 2, 48)
            for td in state.midi.tracks:
                center_track_pitch_scroll(state, td)

    # clear requests
    state.request_fit_time = False
    state.request_fit_vertical = False
    state.request_fit_all = False

    # Interaction helpers
    io = imgui.get_io()
    mousex, mousey = io.mouse_pos
    hovered = (header_x0 <= mousex <= view_x1) and (track_area_y0 <= mousey <= track_area_y1)

    # Start/stop panning (right or middle)
    if hovered and (imgui.is_mouse_clicked(2) or imgui.is_mouse_clicked(1)):
        state.panning = True
        state.pan_anchor = (mousex, mousey)
        state.pan_scroll_anchor = (state.scroll_x_px, state.scroll_y_px)
    if state.panning and not (imgui.is_mouse_down(2) or imgui.is_mouse_down(1)):
        state.panning = False

    if state.panning:
        dx = mousex - state.pan_anchor[0]
        dy = mousey - state.pan_anchor[1]
        state.scroll_x_px = max(0.0, state.pan_scroll_anchor[0] - dx)
        state.scroll_y_px = max(0.0, state.pan_scroll_anchor[1] - dy)

    # Selection marquee (left drag)
    if hovered and imgui.is_mouse_clicked(0):
        state.marquee_active = True
        state.marquee_start = (mousex, mousey)
        state.marquee_end = (mousex, mousey)
        state.selected_notes.clear()
    if state.marquee_active and imgui.is_mouse_down(0):
        state.marquee_end = (mousex, mousey)

    # Mouse wheel zoom/scroll
    wheel_y = io.mouse_wheel
    if hovered and abs(wheel_y) > 0.0:
        if io.key_ctrl:
            factor = 1.1 if wheel_y > 0 else 1 / 1.1
            mouse_time_beats = (state.scroll_x_px + (mousex - x0)) / max(1e-6, state.px_per_beat)
            state.px_per_beat = clamp(state.px_per_beat * factor, 10.0, 400.0)
            state.scroll_x_px = max(0.0, mouse_time_beats * state.px_per_beat - (mousex - x0))
        elif io.key_shift:
            factor = 1.1 if wheel_y > 0 else 1 / 1.1
            state.track_height = clamp(int(state.track_height * factor), 40, 400)
            for td in state.midi.tracks:
                center_track_pitch_scroll(state, td)
        elif io.key_alt:
            local_y = mousey - ruler_y1
            track_index = int((local_y + state.scroll_y_px) // state.track_height) if local_y >= 0 else -1
            if 0 <= track_index < len(state.midi.tracks):
                td = state.midi.tracks[track_index]
                td.pitch_scroll_px = clamp(td.pitch_scroll_px + (-wheel_y) * state.note_height * 2, -5000, 5000)
            else:
                factor = 1.1 if wheel_y > 0 else 1 / 1.1
                new_h = state.note_height * factor
                state.note_height = clamp(int(math.ceil(new_h)) if factor > 1 else int(math.floor(new_h)), 2, 48)
                for td in state.midi.tracks:
                    center_track_pitch_scroll(state, td)
        else:
            state.scroll_y_px = max(0.0, state.scroll_y_px - wheel_y * 40.0)

    # Click on ruler to seek
    if imgui.is_mouse_clicked(0):
        mx, my = io.mouse_pos
        if ruler_y0 <= my <= ruler_y1 and header_x1 <= mx <= view_x1:
            beat = (state.scroll_x_px + (mx - header_x1)) / max(1e-6, state.px_per_beat)
            state.playhead_beats = max(0.0, beat)

    # Visible beat range
    total_beats = state.midi.total_beats if state.midi.tracks else 128
    left_beat = max(0.0, state.scroll_x_px / max(1e-6, state.px_per_beat))
    right_beat = (state.scroll_x_px + avail_w) / max(1e-6, state.px_per_beat)

    # Visible track rows
    num_tracks = len(state.midi.tracks)
    if num_tracks <= 0:
        first_visible_row, last_visible_row = 0, -1
    else:
        first_visible_row = int(max(0, (state.scroll_y_px // state.track_height)))
        last_visible_row  = int(min(num_tracks - 1, math.floor((state.scroll_y_px + (track_area_y1 - track_area_y0)) / state.track_height)))

    # Precompute tick window
    tpq = state.midi.ticks_per_beat
    vis_start_tick  = int(left_beat * tpq)
    vis_end_tick    = int(right_beat * tpq)

    # Draw rows + notes
    note_color = imgui.get_color_u32_rgba(0.27, 0.58, 0.98, 0.95)
    border_col = imgui.get_color_u32_rgba(0.05, 0.1, 0.18, 1.0)

    if last_visible_row >= first_visible_row:
        for ti in range(first_visible_row, last_visible_row + 1):
            td = state.midi.tracks[ti]
            row_top    = track_area_y0 + (ti * state.track_height) - state.scroll_y_px
            row_bottom = row_top + state.track_height

            # Row stripes
            if ti % 2 == 0:
                draw_list.add_rect_filled(header_x1, row_top, view_x1, row_bottom, imgui.get_color_u32_rgba(0.13, 0.13, 0.13, 1.0))
            else:
                draw_list.add_rect_filled(header_x1, row_top, view_x1, row_bottom, imgui.get_color_u32_rgba(0.115, 0.115, 0.115, 1.0))

            # Header text
            draw_list.add_text(header_x0 + 8, row_top + 6, imgui.get_color_u32_rgba(1, 1, 1, 0.9), td.name or f"Track {ti+1}")
            draw_list.add_text(header_x0 + 8, row_top + 24, imgui.get_color_u32_rgba(1, 1, 1, 0.6), "Alt+Wheel: Pitch scroll")

            # Separator
            draw_list.add_line(header_x1, row_top, header_x1, row_bottom, imgui.get_color_u32_rgba(1,1,1,0.1))

            # Note area and horizontal semitone grid
            note_area_y0 = row_top + 4 + td.pitch_scroll_px
            clip_y0 = row_top + 1
            clip_y1 = row_bottom - 1
            if state.note_height >= 6:
                grid_col_h = imgui.get_color_u32_rgba(1, 1, 1, 0.05)
                step = float(state.note_height)
                if step > 0:
                    start_k = math.ceil((clip_y0 - note_area_y0) / step)
                    y_line = note_area_y0 + start_k * step
                    while y_line <= clip_y1:
                        draw_list.add_line(header_x1, y_line, view_x1, y_line, grid_col_h)
                        y_line += step

            # Draw notes in visible time
            for ni, n in enumerate(td.notes):
                if n.end_tick < vis_start_tick or n.start_tick > vis_end_tick:
                    continue

                start_b = n.start_tick / float(tpq or 1)
                end_b   = n.end_tick / float(tpq or 1)
                x_start = header_x1 + (start_b * state.px_per_beat) - state.scroll_x_px
                x_end   = header_x1 + (end_b   * state.px_per_beat) - state.scroll_x_px
                if x_end < header_x1 or x_start > view_x1:
                    continue

                y_note = note_area_y0 + ((127 - n.pitch) * state.note_height)
                y2     = y_note + state.note_height - 1
                if y2 < clip_y0 or y_note > clip_y1:
                    continue

                y1c = max(clip_y0, y_note)
                y2c = min(clip_y1, y2)
                x1c = max(header_x1, x_start)
                x2c = min(view_x1, x_end)

                sel = (ti, ni) in state.selected_notes
                fill_col = note_color if not sel else imgui.get_color_u32_rgba(0.98, 0.78, 0.28, 0.95)
                edge_col = border_col if not sel else imgui.get_color_u32_rgba(0.95, 0.85, 0.45, 1.0)
                draw_list.add_rect_filled(x1c, y1c, x2c, y2c, fill_col)
                draw_list.add_rect(x1c, y1c, x2c, y2c, edge_col)

            # Row bottom line
            draw_list.add_line(x0, row_bottom, view_x1, row_bottom, imgui.get_color_u32_rgba(1,1,1,0.08))

    # === Vertical grid overlay and ruler ===
    header_x = header_x1
    col_bar_grid  = imgui.get_color_u32_rgba(1, 1, 1, 0.18)
    col_beat_grid = imgui.get_color_u32_rgba(1, 1, 1, 0.12)
    col_8th  = imgui.get_color_u32_rgba(1, 1, 1, 0.07)
    col_16th = imgui.get_color_u32_rgba(1, 1, 1, 0.045)
    col_tick_ruler = imgui.get_color_u32_rgba(1, 1, 1, 0.18)

    def _vline_grid(beats_pos: float, col: int):
        X = header_x + (beats_pos * state.px_per_beat) - state.scroll_x_px
        if header_x <= X <= view_x1:
            draw_list.add_line(X, track_area_y0, X, track_area_y1, col)

    def _tick_on_ruler(beats_pos: float, tick_h: float, col: int):
        X = header_x + (beats_pos * state.px_per_beat) - state.scroll_x_px
        if header_x <= X <= view_x1:
            draw_list.add_line(X, ruler_y1 - tick_h, X, ruler_y1, col)

    show_8th = state.px_per_beat >= 50.0
    show_16th = state.px_per_beat >= 90.0

    if show_16th:
        step = 0.25
        i = math.ceil(left_beat / step)
        while True:
            pos = i * step
            if pos > right_beat: break
            _vline_grid(pos, col_16th)
            i += 1
    elif show_8th:
        step = 0.5
        i = math.ceil(left_beat / step)
        while True:
            pos = i * step
            if pos > right_beat: break
            _vline_grid(pos, col_8th)
            i += 1

    for seg in state.midi.ts_segments:
        seg_left = max(left_beat, seg['start_beats'])
        seg_right = min(right_beat, seg['end_beats'])
        if seg_left >= seg_right:
            continue
        bar_len = seg['bar_len']
        beat_len = seg['beat_len']
        num = seg['num']

        k0 = max(0, int(math.floor((seg_left - seg['start_beats']) / max(1e-9, bar_len))))
        k1 = int(math.floor((seg_right - seg['start_beats']) / max(1e-9, bar_len)))
        for k in range(k0, k1 + 1):
            mpos = seg['start_beats'] + k * bar_len
            _vline_grid(mpos, col_bar_grid)
            for j in range(1, num):
                bpos = mpos + j * beat_len
                if seg['start_beats'] <= bpos <= seg['end_beats'] and left_beat <= bpos <= right_beat:
                    _vline_grid(bpos, col_beat_grid)

    # Ruler on top
    draw_list.add_rect_filled(x0, ruler_y0, x1, ruler_y1, imgui.get_color_u32_rgba(0.16, 0.16, 0.16, 1.0))
    for seg in state.midi.ts_segments:
        seg_left = max(left_beat, seg['start_beats'])
        seg_right = min(right_beat, seg['end_beats'])
        if seg_left >= seg_right:
            continue
        bar_len = seg['bar_len']
        beat_len = seg['beat_len']
        num = seg['num']
        k0 = max(0, int(math.floor((seg_left - seg['start_beats']) / max(1e-9, bar_len))))
        k1 = int(math.floor((seg_right - seg['start_beats']) / max(1e-9, bar_len)))
        for k in range(k0, k1 + 1):
            mpos = seg['start_beats'] + k * bar_len
            _tick_on_ruler(mpos, 14, col_tick_ruler)
            meas_num = seg['measure_start_index'] + k + 1
            X = header_x + (mpos * state.px_per_beat) - state.scroll_x_px
            if header_x <= X <= view_x1:
                draw_list.add_text(X + 4, ruler_y0 + 4, imgui.get_color_u32_rgba(1, 1, 1, 0.95), str(meas_num))
            for j in range(1, num):
                bpos = mpos + j * beat_len
                if seg['start_beats'] <= bpos <= seg['end_beats'] and left_beat <= bpos <= right_beat:
                    _tick_on_ruler(bpos, 8, col_tick_ruler)

    # Finalize marquee selection when mouse released
    if state.marquee_active and not imgui.is_mouse_down(0):
        sx0, sy0 = state.marquee_start
        sx1_, sy1_ = state.marquee_end
        if sx1_ < sx0: sx0, sx1_ = sx1_, sx0
        if sy1_ < sy0: sy0, sy1_ = sy1_, sy0
        sx0 = max(sx0, header_x1); sx1_ = min(sx1_, view_x1)
        sy0 = max(sy0, track_area_y0); sy1_ = min(sy1_, track_area_y1)
        if (sx1_ - sx0) > 2 and (sy1_ - sy0) > 2:
            if last_visible_row >= first_visible_row:
                for ti in range(first_visible_row, last_visible_row + 1):
                    td = state.midi.tracks[ti]
                    row_top = track_area_y0 + (ti * state.track_height) - state.scroll_y_px
                    note_area_y0 = row_top + 4 + td.pitch_scroll_px
                    for ni, n in enumerate(td.notes):
                        if n.end_tick < vis_start_tick or n.start_tick > vis_end_tick:
                            continue
                        start_b = n.start_tick / float(tpq or 1)
                        end_b   = n.end_tick   / float(tpq or 1)
                        x_start = header_x1 + (start_b * state.px_per_beat) - state.scroll_x_px
                        x_end   = header_x1 + (end_b   * state.px_per_beat) - state.scroll_x_px
                        y_note  = note_area_y0 + ((127 - n.pitch) * state.note_height)
                        y2      = y_note + state.note_height - 1
                        if x_end < sx0 or x_start > sx1_:
                            continue
                        if y2 < sy0 or y_note > sy1_:
                            continue
                        state.selected_notes.add((ti, ni))
        state.marquee_active = False

        # >>> Snap playhead to selection start only when not playing <<<
        if state.selected_notes and not getattr(state, "playing", False):
            tpq = state.midi.ticks_per_beat or 480
            min_b = min(
                (state.midi.tracks[ti].notes[ni].start_tick / tpq)
                for (ti, ni) in state.selected_notes
            )
            state.playhead_beats = max(0.0, float(min_b))


    # Marquee overlay while dragging
    if state.marquee_active:
        sx0, sy0 = state.marquee_start
        sx1_, sy1_ = state.marquee_end
        vx0 = max(min(sx0, sx1_), header_x1)
        vx1 = min(max(sx0, sx1_), view_x1)
        vy0 = max(min(sy0, sy1_), track_area_y0)
        vy1 = min(max(sy0, sy1_), track_area_y1)
        if vx1 > vx0 and vy1 > vy0:
            col_fill = imgui.get_color_u32_rgba(0.6, 0.7, 1.0, 0.20)
            col_edge = imgui.get_color_u32_rgba(0.6, 0.7, 1.0, 0.85)
            draw_list.add_rect_filled(vx0, vy0, vx1, vy1, col_fill)
            draw_list.add_rect(vx0, vy0, vx1, vy1, col_edge)

    # Custom scrollbars
    content_w_time = max(0.0, state.midi.total_beats * state.px_per_beat)
    visible_w_time = max(1.0, view_x1 - header_x1)
    scroll_x_max = max(0.0, content_w_time - visible_w_time)
    state.scroll_x_px = clamp(state.scroll_x_px, 0.0, scroll_x_max)

    content_h = max(0.0, len(state.midi.tracks) * float(state.track_height))
    visible_h = max(1.0, track_area_y1 - track_area_y0)
    scroll_y_max = max(0.0, content_h - visible_h)
    state.scroll_y_px = clamp(state.scroll_y_px, 0.0, scroll_y_max)

    # Horizontal scrollbar (bottom)
    imgui.set_cursor_screen_position((header_x1, view_y1 + 2))
    imgui.push_item_width(max(10.0, view_x1 - header_x1 - 4))
    changed, new_sx = imgui.slider_float("##hsb", state.scroll_x_px, 0.0, max(1.0, scroll_x_max))
    if changed:
        state.scroll_x_px = new_sx
    imgui.pop_item_width()

    # Vertical scrollbar (right) — custom (compatible across pyimgui versions)
    vx0, vy0 = view_x1 + 2, track_area_y0
    vw, vh = (sb - 6), max(10.0, track_area_y1 - track_area_y0 - 4)

    # Track
    col_track = imgui.get_color_u32_rgba(1, 1, 1, 0.06)
    draw_list.add_rect_filled(vx0, vy0, vx0 + vw, vy0 + vh, col_track)


    # --- Playhead (draw last so it’s on top) ---
    Xp = header_x1 + (state.playhead_beats * state.px_per_beat) - state.scroll_x_px
    if header_x1 <= Xp <= view_x1:
        col_play = imgui.get_color_u32_rgba(1.0, 0.4, 0.2, 0.95)
        # through tracks
        draw_list.add_line(Xp, track_area_y0, Xp, track_area_y1, col_play, 2.0)
        # short mark on ruler
        draw_list.add_line(Xp, ruler_y0, Xp, ruler_y1, col_play, 2.0)


    # Thumb size & position
    if scroll_y_max > 0.0:
        thumb_h = max(18.0, vh * (visible_h / max(content_h, 1.0)))
        thumb_y = vy0 + (vh - thumb_h) * (state.scroll_y_px / scroll_y_max)
    else:
        thumb_h = vh
        thumb_y = vy0

    # Interaction area (invisible button)
    imgui.set_cursor_screen_position((vx0, vy0))
    imgui.invisible_button("##vsb", vw, vh)
    if imgui.is_item_active():
        if not state.vsb_dragging:
            state.vsb_dragging = True
            state.vsb_anchor_mouse_y = io.mouse_pos[1]
            state.vsb_anchor_scroll_y = state.scroll_y_px
        # Map mouse delta to scroll space
        denom = max(1.0, vh - thumb_h)
        factor = scroll_y_max / denom if scroll_y_max > 0.0 else 0.0
        dy = io.mouse_pos[1] - state.vsb_anchor_mouse_y
        state.scroll_y_px = clamp(state.vsb_anchor_scroll_y + dy * factor, 0.0, scroll_y_max)
    else:
        state.vsb_dragging = False

    # Draw thumb
    col_thumb = imgui.get_color_u32_rgba(1, 1, 1, 0.22)
    col_thumb_border = imgui.get_color_u32_rgba(1, 1, 1, 0.35)
    draw_list.add_rect_filled(vx0 + 1, thumb_y + 1, vx0 + vw - 1, thumb_y + thumb_h - 1, col_thumb)
    draw_list.add_rect(vx0 + 1, thumb_y + 1, vx0 + vw - 1, thumb_y + thumb_h - 1, col_thumb_border)

    imgui.end()
