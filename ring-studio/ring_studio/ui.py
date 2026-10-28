"""Ring Studio UI: one window. Clocks on the left, one editor in the middle, the live ring on the right.

Design rules used throughout: greys plus one accent, raised surfaces lighter with a soft shadow,
inputs sunk and darker, hierarchy by weight and colour, generous spacing, and at most two levels
of disclosure (a section, then "Data mapping" inside it). Every input goes through `field`.
"""

import math
import os
import threading
from dataclasses import asdict

import flet as ft

from . import generate, services
from .importer import read_repo
from .model import LIST_MODES, MAP_MODES, Project, from_hex, new_clock, project_from_dict, slug, to_hex

BG, BAR, CARD, SUNK, RAISED, LINE = "#101318", "#151920", "#181C22", "#0E1115", "#1F252D", "#2A313B"
TEXT, SUB, FAINT = "#E8ECF0", "#9AA5B1", "#6F7A86"
ACCENT, ACCENT_BG, ON_ACCENT = "#3DB8C8", "#17303A", "#0B1216"
WARN, WARN_BG, OK = "#F0D79A", "#2A2312", "#A9E4BF"
MONO = "monospace"
PRESETS = ["#FFFFFF", "#FFD700", "#FFA500", "#FF4500", "#FF0040", "#FF1493", "#FF00FF", "#B000FF",
           "#8000FF", "#4B0082", "#4000FF", "#0000CD", "#0040FF", "#1E90FF", "#00BFFF", "#40E0D0",
           "#008B8B", "#00C853", "#7CFC00", "#C8E1FF", "#BEBECD", "#708090", "#0F2043", "#000000"]
LAYOUTS = {"timeline": ("Timeline", "Numbers over time"), "states": ("States", "States over time"),
           "gauge": ("Gauge", "Number fills ring"), "solid": ("Solid", "Number, whole ring"),
           "state": ("State", "State, whole ring")}
SUBTITLES = {"timeline": "One LED per list item, starting at now. Colour follows the value.",
             "states": "One LED per list item, starting at now. Colour follows the state.",
             "gauge": "The current value fills the ring from the low end to the high end.",
             "solid": "The whole ring shows the colour of the current value.",
             "state": "The whole ring shows the colour of the current state.",
             "raw": "A hand-written template, kept exactly as it was."}
MARKERS = {"bright": "Now bright", "white": "Now white", "none": "No marker"}
FIXES = {"below the range": ("Give them their own colour", lambda p, c: setattr(c.ring, "below", [255, 255, 255])),
         "No brightness automation": ("Use the shared one", lambda p, c: p.dimming.targets.append(c.name))}
LIFT = [ft.BoxShadow(blur_radius=2, offset=ft.Offset(0, 1), color=ft.Colors.with_opacity(0.5, "#000000")),
        ft.BoxShadow(blur_radius=24, offset=ft.Offset(0, 10), color=ft.Colors.with_opacity(0.25, "#000000"))]
TOP_EDGE = ft.Border.only(top=ft.BorderSide(1, ft.Colors.with_opacity(0.06, "#FFFFFF")))
HOOKS = []  # called after every edit: autosave and live preview


def edited():
    for hook in HOOKS:
        hook()


# ---------- building blocks ----------

def text(value, size=14, color=TEXT, weight=None, mono=False, **kw):
    return ft.Text(value, size=size, color=color, weight=weight, font_family=MONO if mono else None, **kw)


def caption(value):
    return text(value, 12, FAINT)


def box(control=None, **kw):
    """A sunk input surface."""
    return ft.TextField(filled=True, fill_color=SUNK, border_color=SUNK, focused_border_color=ACCENT,
                        border_radius=10, dense=True, text_size=14, cursor_color=ACCENT,
                        hint_style=ft.TextStyle(color=FAINT),
                        content_padding=ft.Padding.symmetric(horizontal=14, vertical=14), **kw)


def field(title, get, put, conv=str, fmt=str, width=200, mono=False, **kw):
    """A labelled input bound to the model. Bad input shows inline and is not stored."""
    tf = box(value=fmt(get()), width=width, text_style=ft.TextStyle(font_family=MONO) if mono else None, **kw)

    def changed(e):
        try:
            put(conv(e.control.value))
            tf.error = None
        except (ValueError, TypeError):
            tf.error = "Check this value"
        tf.update()
        edited()

    tf.on_change = changed
    return ft.Column([caption(title), tf], spacing=6, tight=True) if title else tf


def attr(obj, name, title, conv=str, fmt=str, **kw):
    return field(title, lambda: getattr(obj, name), lambda v: setattr(obj, name, v), conv, fmt, **kw)


def pick(title, value, options, on_pick, width=200):
    dd = ft.Dropdown(value=value, width=width, dense=True, filled=True, fill_color=SUNK, border_color=SUNK,
                     focused_border_color=ACCENT, border_radius=10,
                     options=[ft.DropdownOption(key=k, text=v) for k, v in options.items()],
                     on_select=lambda e: (on_pick(e.control.value), edited()))
    return ft.Column([caption(title), dd], spacing=6, tight=True)


def button(label, on_click, primary=False, danger=False, icon=None, disabled=False):
    shape = ft.RoundedRectangleBorder(radius=10)
    pad = ft.Padding.symmetric(horizontal=18, vertical=18)
    if primary:
        return ft.FilledButton(label, icon=icon, on_click=on_click, disabled=disabled,
                               style=ft.ButtonStyle(bgcolor=ACCENT, color=ON_ACCENT, shape=shape, padding=pad))
    return ft.OutlinedButton(label, icon=icon, on_click=on_click, disabled=disabled,
                             style=ft.ButtonStyle(color=WARN if danger else TEXT, side=ft.BorderSide(1, LINE),
                                                  shape=shape, padding=pad))


def dot(color, size=28, on_click=None, tooltip=None):
    return ft.Container(width=size, height=size, border_radius=size / 2, bgcolor=color or "#000000",
                        border=ft.Border.all(2, LINE), on_click=on_click, tooltip=tooltip)


def card(content, padding=0, bgcolor=CARD):
    return ft.Container(content, bgcolor=bgcolor, border_radius=16, border=TOP_EDGE, shadow=LIFT, padding=padding)


def note(value, fix=None):
    """A warning line, optionally with a one-click fix."""
    items = [ft.Container(text(value, 13, WARN), expand=True)]
    if fix:
        items.append(ft.TextButton(fix[0], on_click=fix[1], style=ft.ButtonStyle(color=WARN)))
    return ft.Container(ft.Row(items, spacing=12), bgcolor=WARN_BG, border_radius=10,
                        padding=ft.Padding.symmetric(horizontal=14, vertical=8))


def ring_view(colors, size=300):
    c, r, dots = size / 2, size / 2 - 24, []
    for i, col in enumerate(colors):
        t, s = i / len(colors) * 2 * math.pi, 16 if i == 0 else 12
        dots.append(ft.Container(left=c + r * math.sin(t) - s / 2, top=c - r * math.cos(t) - s / 2, width=s, height=s,
                                 border_radius=s / 2, bgcolor=col,
                                 shadow=ft.BoxShadow(blur_radius=s - 4, color=col) if col != "#2C333C" else None))
    return ft.Container(ft.Stack(dots, width=size, height=size), width=size, height=size, bgcolor="#F1EFEA",
                        border_radius=size / 2,
                        shadow=ft.BoxShadow(blur_radius=36, offset=ft.Offset(0, 14),
                                            color=ft.Colors.with_opacity(0.45, "#000000")))


def clock_color(c):
    r = c.ring
    if r.mode in MAP_MODES and r.colors:
        return to_hex(next(iter(r.colors.values())))
    return to_hex(r.palette[len(r.palette) // 2]) if r.palette else ACCENT


class App:
    def __init__(self, page: ft.Page):
        self.page, self.s = page, services.load_settings()
        draft = services.load_draft()
        self.project = project_from_dict(draft) if draft and draft.get("clocks") else Project()
        self.idx, self.entities, self.connected, self.timer = 0, {}, False, None
        self.opened = {"what": True, "bright": False, "device": False, "mapping": False}
        self.preview_colors, self.preview_note = None, "Connect Home Assistant to see the live ring."
        HOOKS[:] = [self.on_edit]
        self.picker = ft.FilePicker()
        page.services.append(self.picker)
        page.title, page.bgcolor, page.padding = "Ring Studio", BG, 0
        page.theme_mode, page.dark_theme = ft.ThemeMode.DARK, ft.Theme(color_scheme_seed=ACCENT)
        page.window.width, page.window.height, page.window.min_width = 1440, 940, 1080
        self.status = text("", 13, SUB)
        self.bar, self.side = ft.Container(), ft.Container(width=264)
        self.editor = ft.Column(scroll=ft.ScrollMode.AUTO, expand=True, spacing=20)
        self.preview = ft.Column(horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=20)
        page.add(ft.Column([self.bar, ft.Row([
            self.side,
            ft.Container(self.editor, expand=True, padding=ft.Padding.only(left=36, right=16, top=32, bottom=24)),
            ft.Container(self.preview, width=380, padding=ft.Padding.only(top=104, right=28))],
            expand=True, spacing=0, vertical_alignment=ft.CrossAxisAlignment.START)], expand=True, spacing=0))
        if self.s.get("ha_url") and self.s.get("ha_token"):
            page.run_thread(self.connect)
        self.refresh()

    # ---------- state ----------
    @property
    def clock(self):
        return self.project.clocks[self.idx] if self.project.clocks else None

    @property
    def ha(self):
        return services.HomeAssistant(self.s.get("ha_url", ""), self.s.get("ha_token", ""))

    def save_setting(self, key, value):
        self.s[key] = value
        services.save_settings(self.s)

    def on_edit(self):
        services.save_draft(asdict(self.project))
        self.status.value = "Draft saved"
        self.status.update()
        self.schedule_preview()

    def refresh(self):
        self.bar.content, self.side.content = self.top_bar(), self.sidebar()
        self.bar.bgcolor, self.bar.padding = BAR, ft.Padding.symmetric(horizontal=28, vertical=12)
        self.side.padding = ft.Padding.symmetric(horizontal=16, vertical=28)
        self.editor.controls = self.editor_view()
        services.save_draft(asdict(self.project))
        self.preview.controls = self.preview_view()
        self.page.update()
        self.schedule_preview(0)

    def toast(self, value):
        self.page.show_dialog(ft.SnackBar(text(value)))

    def dialog(self, title, content, actions, width=620):
        dlg = ft.AlertDialog(title=text(title, 22, weight=ft.FontWeight.W_700), bgcolor=RAISED,
                             content=ft.Container(content, width=width), actions=actions,
                             shape=ft.RoundedRectangleBorder(radius=20))
        self.page.show_dialog(dlg)
        return dlg

    def close(self, _=None):
        self.page.pop_dialog()

    def confirm(self, title, body, label, on_yes):
        def yes(_):
            self.close()
            on_yes()
        self.dialog(title, text(body, color=SUB), [button("Cancel", self.close), button(label, yes, danger=True)], 440)

    # ---------- Home Assistant ----------
    def connect(self):
        try:
            self.entities, self.connected = self.ha.entities(), True
        except RuntimeError as err:
            self.entities, self.connected, self.preview_note = {}, False, str(err)
        self.refresh()

    def schedule_preview(self, delay=0.6):
        if self.timer:
            self.timer.cancel()
        self.timer = threading.Timer(delay, self.render_preview)
        self.timer.daemon = True
        self.timer.start()

    def render_preview(self):
        c = self.clock
        if not c or not self.connected:
            return
        try:
            s, n = self.ha.render(generate.jinja(c)), c.hw.leds
            if len(s) != n * 6:
                raise RuntimeError(f"The template returned {len(s)} characters instead of {n * 6}.")
            self.preview_colors = ["#" + s[i:i + 6] for i in range(0, n * 6, 6)]
            self.preview_note = "Live from Home Assistant"
        except (RuntimeError, ValueError) as err:
            self.preview_colors, self.preview_note = None, str(err)
        self.preview.controls = self.preview_view()
        self.page.update()

    def connect_dialog(self, _=None):
        out = text("Connected · {} entities".format(len(self.entities)) if self.connected else "", 13, OK)

        def go(_):
            out.value, out.color = "Connecting…", SUB
            out.update()
            self.connect()
            out.value = f"Connected · {len(self.entities)} entities" if self.connected else self.preview_note
            out.color = OK if self.connected else WARN
            out.update()

        self.dialog("Home Assistant", ft.Column([
            text("Used for picking entities and states, the live preview, and reloading after export.", color=SUB),
            field("URL", lambda: self.s.get("ha_url", ""), lambda v: self.save_setting("ha_url", v), width=560,
                  hint_text="https://homeassistant.local:8123"),
            field("Long-lived access token", lambda: self.s.get("ha_token", ""),
                  lambda v: self.save_setting("ha_token", v), width=560, password=True, can_reveal_password=True),
            caption("Create one in Home Assistant under your profile, Security, Long-lived access tokens."),
            out], spacing=18, tight=True), [button("Close", self.close), button("Connect", go, primary=True)])

    # ---------- chrome ----------
    def top_bar(self):
        logo = ft.Container(width=26, height=26, border_radius=13, border=ft.Border.all(4, ACCENT))
        ha = ft.OutlinedButton(
            content=ft.Row([ft.Container(width=8, height=8, border_radius=4, bgcolor="#4CC37A" if self.connected
                                         else FAINT), text("Home Assistant" if self.connected
                                                           else "Connect Home Assistant", 13, TEXT)], spacing=8,
                           tight=True),
            on_click=self.connect_dialog,
            style=ft.ButtonStyle(side=ft.BorderSide(1, LINE), shape=ft.RoundedRectangleBorder(radius=20),
                                 padding=ft.Padding.symmetric(horizontal=14, vertical=14)))
        return ft.Row([logo, text("Ring Studio", 17, weight=ft.FontWeight.W_700), ft.Container(expand=True),
                       self.status, ha, button("Open repo", self.open_dialog),
                       button("Export", self.export_dialog, primary=True, disabled=not self.project.clocks)],
                      spacing=14)

    def sidebar(self):
        def select(i):
            self.idx = i
            self.refresh()

        def add(_):
            self.project.clocks.append(new_clock(f"clock{len(self.project.clocks) + 1}"))
            self.idx, self.opened["device"] = len(self.project.clocks) - 1, True
            self.refresh()

        items = [ft.Container(text("CLOCKS", 12, FAINT, ft.FontWeight.W_600), padding=ft.Padding.only(left=12, bottom=8))]
        for i, c in enumerate(self.project.clocks):
            on = i == self.idx
            items.append(ft.Container(
                ft.Row([dot(clock_color(c), 28), ft.Column([text(c.friendly, weight=ft.FontWeight.W_600),
                                                            text(LAYOUTS.get(c.ring.mode, ("Raw",))[0], 12, SUB)],
                                                           spacing=2, tight=True)], spacing=12),
                bgcolor=ACCENT_BG if on else None, border_radius=12, padding=12, ink=True,
                on_click=lambda _, i=i: select(i)))
        items.append(ft.TextButton("+  Add clock", on_click=add, style=ft.ButtonStyle(color=SUB)))
        return ft.Column(items, spacing=6)

    # ---------- editor ----------
    def editor_view(self):
        c = self.clock
        if not c:
            return [ft.Container(ft.Column([
                text("No clocks yet", 24, weight=ft.FontWeight.W_700),
                text("Open a repo with your existing clocks, or start a new one.", color=SUB),
                ft.Row([button("Open repo", self.open_dialog, primary=True),
                        button("Add a clock", lambda _: (self.project.clocks.append(new_clock("clock1")),
                                                         self.refresh()))], spacing=12)],
                spacing=16), padding=ft.Padding.only(top=80))]
        r, d = c.ring, self.project.dimming
        what = (f"{LAYOUTS[r.mode][0]} · {len(r.colors)} colours" if r.mode in MAP_MODES
                else f"{LAYOUTS[r.mode][0]} · {len(r.palette)} stops" if r.mode in LAYOUTS else "Raw template")
        bright = (f"Follows the sun · off {d.night_start:02d} to {d.night_end:02d}" if c.name in d.targets
                  else "Fixed, set on the device")
        device = f"{c.hw.pin} · {c.hw.leds} LEDs · {c.name}.local"
        return [ft.Column([text(c.friendly, 28, weight=ft.FontWeight.W_700), text(SUBTITLES[r.mode], color=SUB)],
                          spacing=6),
                self.section("what", "What it shows", what, self.what_body),
                self.section("bright", "Brightness", bright, self.bright_body),
                self.section("device", "Device", device, self.device_body)]

    def section(self, key, title, summary, body):
        def toggle(_):
            self.opened[key] = not self.opened[key]
            self.editor.controls = self.editor_view()
            self.editor.update()

        head = ft.Container(ft.Row([text(title, 17, weight=ft.FontWeight.W_600), ft.Container(expand=True),
                                    text(summary, 13, SUB),
                                    ft.Icon(ft.Icons.EXPAND_LESS if self.opened[key] else ft.Icons.EXPAND_MORE,
                                            color=SUB)], spacing=12),
                            padding=ft.Padding.symmetric(horizontal=24, vertical=20), on_click=toggle, ink=True,
                            border_radius=16)
        parts = [head]
        if self.opened[key]:
            parts.append(ft.Container(body(), padding=ft.Padding.only(left=24, right=24, bottom=28)))
        return card(ft.Column(parts, spacing=0))

    def what_body(self):
        r = self.clock.ring
        if r.mode == "raw":
            return ft.Column([note("This template was not recognised, so it is kept exactly as is."),
                              box(value=r.raw, multiline=True, read_only=True, min_lines=10, text_size=12),
                              button("Replace with an editable timeline", lambda _: self.set_mode("timeline"))],
                             spacing=16)
        if self.entities:
            entity = ft.Dropdown(value=r.entity if r.entity in self.entities else None, width=560, dense=True,
                                 editable=True, enable_filter=True, menu_height=420, filled=True, fill_color=SUNK,
                                 border_color=SUNK, focused_border_color=ACCENT, border_radius=10,
                                 hint_text=r.entity or "Search entities",
                                 options=[ft.DropdownOption(key=e) for e in self.entities],
                                 on_select=lambda e: (setattr(r, "entity", e.control.value), edited(), self.refresh()))
        else:
            entity = field("", lambda: r.entity, lambda v: setattr(r, "entity", v), width=560, mono=True)
        lists = self.entities.get(r.entity)
        parts = [ft.Column([caption("Entity"), entity] + ([caption("List attributes: " + ", ".join(lists))]
                                                            if lists else []), spacing=6),
                 ft.Column([caption("Ring layout"), ft.Row([self.tile(k, v) for k, v in LAYOUTS.items()],
                                                         wrap=True, spacing=10, run_spacing=10)], spacing=8),
                 self.map_editor(r) if r.mode in MAP_MODES else self.gradient_editor(r)]
        chips = [self.color_chip("No data", lambda: r.missing, lambda v: setattr(r, "missing", v))]
        if r.mode in MAP_MODES:
            chips.insert(0, self.color_chip("Unknown state", lambda: r.fallback, lambda v: setattr(r, "fallback", v)))
        else:
            chips.insert(0, self.color_chip("Below range", lambda: r.below, lambda v: setattr(r, "below", v), True))
        if r.mode in LIST_MODES:
            chips += [self.segmented(MARKERS, r.marker, lambda v: setattr(r, "marker", v)),
                      ft.Row([caption("Other LEDs"), ft.Slider(min=0, max=100, divisions=20, value=r.dim * 100,
                                                                width=180, active_color=ACCENT, label="{value}%",
                                                                on_change_end=lambda e: (setattr(r, "dim", round(
                                                                    e.control.value / 100, 2)), edited()))],
                             spacing=4, tight=True)]
        parts += [ft.Row(chips, wrap=True, spacing=12, run_spacing=12), self.mapping(r)]
        return ft.Column(parts, spacing=28)

    def set_mode(self, mode):
        self.clock.ring.mode = mode
        edited()
        self.refresh()

    def tile(self, key, label):
        on = self.clock.ring.mode == key
        return ft.Container(ft.Column([
            ft.Container(width=26, height=26, border_radius=13, border=ft.Border.all(5, ACCENT if on else "#55606C")),
            text(label[0], 14, TEXT if on else SUB, ft.FontWeight.W_600), text(label[1], 11, FAINT)],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=6, tight=True),
            width=132, height=104, padding=ft.Padding.symmetric(vertical=14, horizontal=6), border_radius=12,
            bgcolor=ACCENT_BG if on else RAISED, border=ft.Border.all(1, ACCENT if on else RAISED), ink=True,
            on_click=lambda _: self.set_mode(key))

    def segmented(self, options, value, put):
        def choose(k):
            put(k)
            edited()
            self.editor.controls = self.editor_view()
            self.editor.update()

        return ft.Container(ft.Row([ft.Container(text(v, 13, TEXT if k == value else SUB),
                                                 bgcolor=RAISED if k == value else None, border_radius=8, ink=True,
                                                 padding=ft.Padding.symmetric(horizontal=14, vertical=10),
                                                 on_click=lambda _, k=k: choose(k)) for k, v in options.items()],
                                   spacing=2, tight=True), bgcolor=SUNK, border_radius=10, padding=3)

    def color_chip(self, label, get, put, optional=False):
        sw = dot(to_hex(get()) if get() else None, 18)

        def done(v):
            put(v)
            sw.bgcolor = to_hex(v) if v else "#000000"
            sw.update()

        return ft.Container(ft.Row([sw, text(label, 13)], spacing=10, tight=True), bgcolor=RAISED, border_radius=10,
                            padding=ft.Padding.symmetric(horizontal=14, vertical=12), ink=True,
                            on_click=lambda _: self.color_dialog(label, get(), done, optional))

    def gradient_editor(self, r):
        width = 520

        def edit_stop(i):
            def done(v):
                r.palette[i] = v
                self.refresh_editor()

            def remove():
                r.palette.pop(i)
                self.refresh_editor()

            self.color_dialog(f"Stop {i + 1}", r.palette[i], done,
                              remove=remove if len(r.palette) > 2 else None)

        def add(_):
            r.palette.append(r.palette[-1][:])
            edited()
            self.refresh_editor()

        n = len(r.palette)
        dots = [ft.Container(left=i / (n - 1) * (width - 30), top=0, width=30, height=30, border_radius=15,
                             bgcolor=to_hex(p), border=ft.Border.all(3, CARD), ink=True, tooltip="Edit colour",
                             shadow=ft.BoxShadow(blur_radius=4, offset=ft.Offset(0, 2),
                                                 color=ft.Colors.with_opacity(0.5, "#000000")),
                             on_click=lambda _, i=i: edit_stop(i)) for i, p in enumerate(r.palette)]
        bar = ft.Container(left=15, top=8, width=width - 30, height=14, border_radius=7, gradient=ft.LinearGradient(
            colors=[to_hex(p) for p in r.palette], begin=ft.Alignment.CENTER_LEFT, end=ft.Alignment.CENTER_RIGHT))
        return ft.Column([ft.Row([caption(f"Colours from {r.lo:g} to {r.hi:g}"), ft.Container(expand=True),
                                  ft.TextButton("+ Add stop", on_click=add, style=ft.ButtonStyle(color=SUB))],
                                 width=width),
                          ft.Stack([bar] + dots, width=width, height=34)], spacing=8)

    def refresh_editor(self):
        edited()
        self.editor.controls = self.editor_view()
        self.side.content = self.sidebar()
        self.page.update()

    def map_editor(self, r):
        def rename(old, new):
            r.colors = {(new if k == old else k): v for k, v in r.colors.items()}
            r.labels = {(new if k == old else k): v for k, v in r.labels.items()}

        def add(states):
            for s in states:
                r.colors.setdefault(s, from_hex(PRESETS[(len(r.colors) + 1) % len(PRESETS)]))
            self.refresh_editor()

        def remove(key):
            r.colors.pop(key, None)
            r.labels.pop(key, None)
            self.refresh_editor()

        def fetch():
            try:
                found = self.ha.seen_states(r.entity, r.attrs if r.mode in LIST_MODES else [], r.key)
            except RuntimeError as err:
                self.toast(str(err))
                return
            new = [s for s in found if s not in r.colors]
            self.toast(f"Found {len(found)} states, {len(new)} new" if found else "No states found on that entity")
            add(new)

        rows = []
        for key in list(r.colors):
            cell = [key]

            def recolor(v, cell=cell):
                r.colors[cell[0]] = v
                self.refresh_editor()

            rows.append(ft.Row([
                dot(to_hex(r.colors[key]), 30, tooltip="Change colour",
                    on_click=lambda _, cell=cell: self.color_dialog(cell[0], r.colors[cell[0]], recolor)),
                field("", lambda cell=cell: cell[0], lambda v, cell=cell: (rename(cell[0], v), cell.__setitem__(0, v)),
                      width=170, mono=True),
                field("", lambda cell=cell: r.labels.get(cell[0], ""),
                      lambda v, cell=cell: r.labels.__setitem__(cell[0], v), width=300,
                      hint_text="What this colour means"),
                ft.IconButton(ft.Icons.DELETE_OUTLINE, icon_color=FAINT, tooltip="Remove state",
                              on_click=lambda _, k=key: remove(k))], spacing=12))
        head = ft.Row([caption("Colours by state"), ft.Container(expand=True),
                       ft.TextButton("Fetch states from Home Assistant", disabled=not (self.connected and r.entity),
                                     on_click=lambda _: self.page.run_thread(fetch),
                                     style=ft.ButtonStyle(color=ACCENT))], width=620)
        return ft.Column([head] + rows + [ft.TextButton("+ Add state", style=ft.ButtonStyle(color=SUB),
                                                        on_click=lambda _: add([f"state{len(r.colors) + 1}"]))],
                         spacing=8)

    def mapping(self, r):
        """Second disclosure level: where the values come from."""
        def toggle(_):
            self.opened["mapping"] = not self.opened["mapping"]
            self.editor.controls = self.editor_view()
            self.editor.update()

        bits = ([" + ".join(r.attrs) or "no list", r.key or "no key"] if r.mode in LIST_MODES else ["entity state"])
        if r.mode not in MAP_MODES:
            bits.append(f"× {r.scale:g}")
        head = ft.Container(ft.Row([ft.Icon(ft.Icons.EXPAND_LESS if self.opened["mapping"] else ft.Icons.EXPAND_MORE,
                                            color=FAINT, size=18), text("Data mapping · " + " · ".join(bits), 13, SUB)],
                                   spacing=6), on_click=toggle, ink=True, border_radius=8, padding=6)
        if not self.opened["mapping"]:
            return head
        rows = []
        if r.mode in LIST_MODES:
            rows += [attr(r, "attrs", "List attributes", lambda s: [x.strip() for x in s.split(",") if x.strip()],
                          ", ".join), attr(r, "key", "Item key", mono=True),
                     attr(r, "t_start", "Start time key", mono=True), attr(r, "t_end", "End time key", mono=True)]
        if r.mode not in MAP_MODES:
            rows += [attr(r, "scale", "Multiply value by", float), attr(r, "lo", "Low end", float),
                     attr(r, "hi", "High end", float)]
        tip = "Leave the time keys empty when item 0 is always now." if r.mode in LIST_MODES else ""
        return ft.Column([head, ft.Row(rows, wrap=True, spacing=14, run_spacing=14)] + ([caption(tip)] if tip else []),
                         spacing=14)

    def bright_body(self):
        c, d = self.clock, self.project.dimming
        on = c.name in d.targets

        def toggle(e):
            d.targets = [t for t in d.targets if t != c.name] + ([c.name] if e.control.value else [])
            edited()
            self.editor.controls = self.editor_view()
            self.editor.update()

        users = [x.friendly for x in self.project.clocks if x.name in d.targets]
        parts = [ft.Row([ft.Column([text("Adaptive brightness"),
                                    caption("Dims with the sun and turns the ring off at night.")], spacing=2,
                                   expand=True),
                         ft.Switch(value=on, active_color=ACCENT, on_change=toggle)])]
        if on:
            parts += [ft.Row([attr(d, "night_start", "Off from (hour)", int, width=150),
                              attr(d, "night_end", "Back on at (hour)", int, width=150),
                              attr(d, "low", "Dimmest", int, width=110),
                              attr(d, "elev_low", "at sun angle °", float, width=130),
                              attr(d, "high", "Brightest", int, width=110),
                              attr(d, "elev_high", "at sun angle °", float, width=130)], wrap=True, spacing=14,
                             run_spacing=14),
                      caption("Shared by " + ", ".join(users) + ".")]
        return ft.Column(parts, spacing=20)

    def device_body(self):
        c, hw = self.clock, self.clock.hw

        def rename(v):
            old, c.name = c.name, v
            t = self.project.dimming.targets
            if old in t:
                t[t.index(old)] = v

        def remove():
            self.project.clocks.pop(self.idx)
            self.idx = 0
            self.refresh()

        return ft.Column([
            ft.Row([field("Device name", lambda: c.name, rename, slug, mono=True),
                    attr(c, "friendly", "Display name"), attr(c, "effect", "Effect name")], wrap=True, spacing=14,
                   run_spacing=14),
            ft.Row([attr(hw, "board", "Board", width=150), attr(hw, "pin", "Data pin", width=130),
                    pick("Driver", hw.method, {m: m for m in ("bit_bang", "esp8266_uart", "esp8266_dma")},
                         lambda v: setattr(hw, "method", v), 170),
                    attr(hw, "variant", "LED type", width=130),
                    pick("Colour order", hw.order, {o: o for o in ("GRB", "RGB", "BRG", "GRBW")},
                         lambda v: setattr(hw, "order", v), 140),
                    attr(hw, "gamma", "Gamma", float, width=100), attr(hw, "leds", "LEDs", int, width=100),
                    attr(hw, "start_brightness", "Start brightness", int, width=140),
                    attr(hw, "max_brightness", "Max brightness", int, width=140)], wrap=True, spacing=14,
                   run_spacing=14),
            ft.Row([ft.Row([button("Flash and back up", self.firmware_dialog, icon=ft.Icons.USB),
                            button("WiFi and keys", self.keys_dialog, icon=ft.Icons.WIFI)], spacing=12, tight=True),
                    button("Remove clock", lambda _: self.confirm(
                        "Remove clock", f"Remove {c.friendly} from this project? Exported files are not deleted.",
                        "Remove", remove), danger=True)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)], spacing=24)

    # ---------- preview ----------
    def preview_view(self):
        c = self.clock
        if not c:
            return []
        colors = self.preview_colors if self.preview_colors and len(self.preview_colors) == c.hw.leds \
            else ["#2C333C"] * c.hw.leds
        live = self.connected and self.preview_colors
        status = ft.Row([ft.Container(width=8, height=8, border_radius=4, bgcolor="#4CC37A" if live else FAINT),
                         text(self.preview_note, 12, SUB, max_lines=3, width=300)], spacing=8, tight=True)
        r = c.ring
        if r.mode in MAP_MODES:
            legend = [(to_hex(v), r.labels.get(k) or k) for k, v in r.colors.items()]
        elif r.mode in LAYOUTS:
            legend = [(to_hex(r.palette[0]), f"{r.lo:g}"), (to_hex(r.palette[len(r.palette) // 2]),
                                                            f"{(r.lo + r.hi) / 2:g}"), (to_hex(r.palette[-1]), f"{r.hi:g}")]
            if r.below:
                legend.append((to_hex(r.below), f"below {r.lo:g}"))
        else:
            legend = []
        chips = [ft.Row([ft.Container(width=10, height=10, border_radius=5, bgcolor=col,
                                      border=ft.Border.all(1, LINE)), text(t, 12, SUB)],
                        spacing=6, tight=True) for col, t in legend]
        out = [ring_view(colors), status, ft.Row(chips, wrap=True, spacing=14, run_spacing=8, width=320,
                                                alignment=ft.MainAxisAlignment.CENTER)]
        if not self.connected:
            out.append(button("Connect Home Assistant", self.connect_dialog))
        return out

    # ---------- dialogs ----------
    def color_dialog(self, title, current, on_done, optional=False, remove=None):
        hexbox = box(value=to_hex(current) if current else "", width=160, text_style=ft.TextStyle(font_family=MONO))

        def done(value):
            self.close()
            on_done(from_hex(value) if value else None)
            edited()

        def apply(_):
            try:
                done(hexbox.value.strip())
            except ValueError:
                hexbox.error = "Use #RRGGBB"
                hexbox.update()

        grid = ft.Row([ft.Container(width=40, height=40, border_radius=10, bgcolor=h, tooltip=h, ink=True,
                                    border=ft.Border.all(1, LINE), on_click=lambda _, h=h: done(h))
                       for h in PRESETS], wrap=True, spacing=10, run_spacing=10, width=420)
        actions = []
        if remove:
            actions.append(button("Remove stop", lambda _: (self.close(), remove()), danger=True))
        if optional:
            actions.append(button("No colour", lambda _: done("")))
        actions += [button("Cancel", self.close), button("Apply", apply, primary=True)]
        self.dialog(title, ft.Column([grid, ft.Row([caption("Or a hex value"), hexbox], spacing=12)], spacing=20,
                                     tight=True), actions, 440)

    def open_dialog(self, _=None):
        body = ft.Column([text("Pick a folder or zip with config/ and homeassistant/ inside.", color=SUB)],
                         spacing=16, tight=True)
        state = {"project": None}

        def show_report(project, root):
            state["project"] = project
            rows = []
            for c in project.clocks:
                warns = [n.lstrip("! ") for n in project.notes.get(c.name, []) if n.startswith("!")]
                lines = []
                for w in warns:
                    fix = next(((label, fn) for k, (label, fn) in FIXES.items() if k in w), None)
                    holder = ft.Container()

                    def apply(_, fn=fix[1] if fix else None, c=c, holder=holder, w=w):
                        fn(project, c)
                        holder.content = text("Fixed: " + w, 13, OK)
                        holder.update()

                    holder.content = note(w, (fix[0], apply) if fix else None)
                    lines.append(holder)
                rows.append(ft.Container(ft.Column([ft.Row([dot(clock_color(c), 28), ft.Column([
                    text(c.friendly, 16, weight=ft.FontWeight.W_600),
                    text(f"{LAYOUTS.get(c.ring.mode, ('Raw',))[0]} · {c.ring.entity}", 13, SUB)], spacing=2,
                    expand=True)], spacing=14)] + lines, spacing=12), bgcolor=SUNK, border_radius=14, padding=18))
            body.controls = [text(f"Found {len(project.clocks)} clocks in {os.path.basename(root.rstrip('/'))}",
                                  color=SUB)] + rows
            if self.project.clocks:
                body.controls.append(caption("Opening replaces the current draft."))
            body.update()
            go.disabled = not project.clocks
            go.content = f"Open {len(project.clocks)} clocks"
            go.update()

        def load(path, repo):
            try:
                project, root = read_repo(path)
            except (OSError, ValueError, KeyError) as err:
                self.toast(f"Could not read that repo: {err}")
                return
            if repo:
                self.save_setting("repo", repo)
            show_report(project, path)

        async def folder(_):
            if path := await self.picker.get_directory_path(dialog_title="Repo folder"):
                load(path, path)

        async def archive(_):
            if files := await self.picker.pick_files(allowed_extensions=["zip"]):
                load(files[0].path, None)

        def use(_):
            self.project, self.idx = state["project"], 0
            self.close()
            self.refresh()

        go = button("Open", use, primary=True, disabled=True)
        body.controls.append(ft.Row([button("Choose folder", folder, icon=ft.Icons.FOLDER_OPEN),
                                     button("Choose zip", archive)], spacing=12))
        self.dialog("Open repo", body, [button("Cancel", self.close), go], 660)

    def export_dialog(self, _=None):
        files = generate.repo_files(self.project)
        listing = ft.Column(spacing=0)
        package_on = ft.Switch(value=bool(self.s.get("package")), active_color=ACCENT)
        go = button("Export", None, primary=True)

        def status(rel):
            path = os.path.join(self.s.get("repo") or "", rel)
            if not self.s.get("repo") or not os.path.exists(path):
                return "New"
            with open(path, encoding="utf-8") as fh:
                return "Unchanged" if fh.read() == files[rel] else "Changed"

        def view(rel):
            self.dialog(rel, box(value=files[rel], multiline=True, read_only=True, min_lines=22, text_size=12,
                                 text_style=ft.TextStyle(font_family=MONO)), [button("Close", self.close)], 860)

        def fill():
            states = {rel: status(rel) for rel in files}
            listing.controls = [ft.Container(ft.Row([text(rel, 13, mono=True, expand=True),
                                                     text(st, 12, ACCENT if st != "Unchanged" else FAINT),
                                                     ft.TextButton("View", on_click=lambda _, rel=rel: view(rel))], spacing=12),
                                             padding=ft.Padding.symmetric(horizontal=16, vertical=4))
                                for rel, st in states.items()]
            todo = [rel for rel, st in states.items() if st != "Unchanged"]
            go.content, go.disabled = (f"Export {len(todo)} files" if todo else "Nothing to export"), not todo
            return todo

        def choose(key):
            async def run(_):
                if path := await self.picker.get_directory_path():
                    self.save_setting(key, path)
                    self.close()
                    self.export_dialog()
            return run

        def export(_):
            if not self.s.get("repo"):
                self.toast("Choose the repo folder first")
                return
            todo = fill()
            generate.write_files(self.s["repo"], {rel: files[rel] for rel in todo})
            msg = f"Exported {len(todo)} files"
            if package_on.value and self.s.get("packages"):
                generate.write_files(self.s["packages"], {"ring_studio.yaml": generate.package_file(self.project)})
                try:
                    self.ha.reload()
                    msg += ", wrote the package and reloaded Home Assistant"
                except RuntimeError as err:
                    msg += f", wrote the package but reload failed: {err}"
            self.save_setting("package", package_on.value)
            self.close()
            self.toast(msg)

        go.on_click = export
        fill()
        self.dialog("Export", ft.Column([
            text("Writes the draft as real YAML. Only new and changed files are written.", color=SUB),
            ft.Row([field("Repo folder", lambda: self.s.get("repo", ""), lambda v: self.save_setting("repo", v),
                          width=460, mono=True),
                    ft.Container(button("Choose", choose("repo")), padding=ft.Padding.only(top=18))], spacing=10),
            ft.Container(listing, bgcolor=SUNK, border_radius=14, padding=ft.Padding.symmetric(vertical=8)),
            ft.Row([ft.Column([text("Also write a Home Assistant package"),
                               caption("One file for config/packages/, then reload templates and automations")],
                              spacing=2, expand=True), package_on]),
            ft.Row([field("Packages folder", lambda: self.s.get("packages", ""),
                          lambda v: self.save_setting("packages", v), width=460, mono=True),
                    ft.Container(button("Choose", choose("packages")), padding=ft.Padding.only(top=18))],
                   spacing=10)], spacing=20, tight=True, scroll=ft.ScrollMode.AUTO),
            [button("Cancel", self.close), go], 700)

    def keys_dialog(self, _=None):
        sec = self.project.secrets
        generate.secrets_file(self.project)
        api_state = text("", 13)

        def paint():
            ok = generate.valid_api_key(sec.get("api_key", ""))
            api_state.value = "API key is valid" if ok else "API key is missing or invalid. Generate one, then flash over USB."
            api_state.color = OK if ok else WARN

        def regen(key):
            def go():
                sec[key] = generate.gen_secret(key)
                edited()
                paint()
                api_state.update()
                self.toast(f"New {key.replace('_', ' ')} generated. Flash over USB so the clock gets it.")
            self.confirm("Generate new key",
                         "The clock keeps its old key until you flash it over USB, and Home Assistant will ask "
                         "for the new one. Continue?", "Generate", go)

        paint()
        put = lambda k: (lambda v: sec.__setitem__(k, v))  # noqa: E731
        self.dialog("WiFi and keys", ft.Column([
            field("WiFi name", lambda: sec.get("wifi_ssid", ""), put("wifi_ssid"), width=560),
            field("WiFi password", lambda: sec.get("wifi_password", ""), put("wifi_password"), width=560,
                  password=True, can_reveal_password=True),
            field("Fallback hotspot password", lambda: sec.get("ap_password", ""), put("ap_password"), width=560,
                  password=True, can_reveal_password=True),
            caption("The clock opens its own hotspot with this password when it cannot join your WiFi."),
            api_state,
            ft.Row([button("Generate API key", lambda _: regen("api_key")),
                    button("Generate OTA password", lambda _: regen("ota_password"))], spacing=12)],
            spacing=16, tight=True), [button("Done", self.close, primary=True)])

    def firmware_dialog(self, _=None):
        c = self.clock
        log = ft.ListView(height=220, spacing=2, auto_scroll=True)
        tools = text("", 13)
        backup = {"path": self.s.get(f"backup_{c.name}") or os.path.join(services.HOME, "backups",
                                                                         f"{c.name}_stock_4MB.bin")}
        ports = services.serial_ports()
        port = {"value": self.s.get("port") or (ports[0] if ports else "COM4")}
        buttons = []

        def paint_tools():
            v = services.tool_versions()
            tools.value = (f"ESPHome {v['esphome']} · esptool {v['esptool']}" if all(v.values())
                           else "ESPHome is not installed yet. It installs automatically the first time you flash.")
            tools.color = SUB if all(v.values()) else WARN

        def say(line, color=TEXT):
            log.controls.append(text(line, 12, color, mono=True, selectable=True))
            self.page.update()

        def busy(on):
            for b in buttons:
                b.disabled = on
            self.page.update()

        def job(*steps):
            def work():
                busy(True)
                for title, step in steps:
                    say(f"▸ {title}", ACCENT)
                    code = step(say)
                    if code:
                        say(f"Stopped: {title} failed (exit {code}).", WARN)
                        break
                else:
                    say("Done.", OK)
                paint_tools()
                busy(False)
            self.page.run_thread(work)

        def ensure_tools(out):
            return services.install_tools(out) if not all(services.tool_versions().values()) else 0

        def build(out):
            generate.write_files(services.BUILD, generate.repo_files(self.project))
            out(f"Wrote config to {services.BUILD}")
            return 0

        def device_port():
            return port["value"].split(" · ")[0]

        def flash(device):
            return lambda out: services.run(services.esphome(f"{c.name}.yaml", device()), out,
                                            cwd=os.path.join(services.BUILD, "config"))

        def esptool(*args):
            def step(out):
                if args == services.RESTORE and not os.path.exists(backup["path"]):
                    out(f"No backup file at {backup['path']}. Back up first or pick the right file.")
                    return 1
                os.makedirs(os.path.dirname(os.path.abspath(backup["path"])), exist_ok=True)
                return services.run(services.esptool(device_port(), *args, backup["path"]), out)
            return step

        def set_backup(v):
            backup["path"] = v
            self.save_setting(f"backup_{c.name}", v)

        def set_port(v):
            port["value"] = v
            self.save_setting("port", v)

        problems = []
        if not generate.valid_api_key(self.project.secrets.get("api_key", "")):
            problems.append(note("The API key is invalid, so the flash will fail.",
                                 ("Fix in WiFi and keys", lambda _: (self.close(), self.keys_dialog()))))
        if self.project.secrets.get("wifi_ssid", "YOUR_WIFI_NAME") == "YOUR_WIFI_NAME":
            problems.append(note("WiFi is not set, so the clock will only open its fallback hotspot.",
                                 ("Set WiFi", lambda _: (self.close(), self.keys_dialog()))))
        if not os.path.exists(backup["path"]):
            problems.append(note("No stock backup for this clock yet. Back up before the first USB flash."))
        paint_tools()
        b_backup = button("Back up stock", lambda _: job(("Install tools", ensure_tools),
                                                         ("Back up 4 MB", esptool(*services.BACKUP))))
        b_flash = button("Flash over USB", lambda _: job(("Install tools", ensure_tools), ("Prepare", build),
                                                         ("Compile and flash", flash(device_port))), primary=True)
        b_ota = button("Update over the air", lambda _: job(("Install tools", ensure_tools), ("Prepare", build),
                                                            ("Compile and update", flash(lambda: "OTA"))))
        b_restore = button("Restore stock", lambda _: self.confirm(
            "Restore stock firmware", "This replaces the ESPHome firmware with the backup. Continue?", "Restore",
            lambda: job(("Restore 4 MB", esptool(*services.RESTORE)))),
            danger=True)
        buttons += [b_backup, b_flash, b_ota, b_restore]
        self.dialog(f"Flash {c.friendly}", ft.Column(problems + [
            tools,
            ft.Row([pick("Serial port", port["value"], {p: p for p in dict.fromkeys(ports + [port["value"]])},
                         set_port, 340),
                    field("Backup file", lambda: backup["path"], set_backup,
                          width=300, mono=True)], spacing=14),
            caption("The first flash goes over USB. After that, updates go over the air. The first compile "
                    "downloads the ESP8266 toolchain and takes a few minutes."),
            ft.Row([ft.Row([b_flash, b_ota, b_backup], spacing=10, tight=True), b_restore],
                   alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Container(log, bgcolor=SUNK, border_radius=12, padding=12)], spacing=16, tight=True),
            [button("Close", self.close)], 760)


def main(page: ft.Page):
    App(page)
