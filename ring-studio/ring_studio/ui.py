"""Ring Studio UI: one window. Clocks on the left, one editor in the middle, the live ring on the right.

Design rules used throughout: greys plus one accent, raised surfaces lighter with a soft shadow,
inputs sunk and darker, hierarchy by weight and colour, generous spacing, and at most two levels
of disclosure (a section, then "Data mapping" inside it). Every input goes through `field`.
"""

import difflib
import math
import os
import re
import threading
import time
from dataclasses import asdict
from datetime import datetime

import flet as ft

from . import detect, generate, project as projects, sample, services, sun
from .render import Snapshot
from . import storage
from .storage import Secrets
from .model import (GRADIENTS, LIST_MODES, MAP_MODES, STARTERS, Hardware, Project, from_hex, project_from_dict,
                    slug, to_hex)

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
           "state": ("State", "State, whole ring"), "hands": ("Hands", "Clock, day colours")}
SUBTITLES = {"timeline": "One LED per list item, starting at now. Colour follows the value.",
             "states": "One LED per list item, starting at now. Colour follows the state.",
             "gauge": "The current value fills the ring from the low end to the high end.",
             "solid": "The whole ring shows the colour of the current value.",
             "state": "The whole ring shows the colour of the current state.",
             "hands": "The ring is a clock: the hour and minute hands light up, and their colour follows the "
                      "time of day.",
             "raw": "A hand-written template, kept exactly as it was."}
DIAL_SUBTITLE = "A 24-hour dial: midnight at the top, every hour in its own place, showing the next 24 hours."
HW_NAME, HW_PRESET = "EnergiKlockan EMIL", Hardware()
HW_KEYS = ("board", "pin", "method", "variant", "order", "gamma", "leds")
FADE = ft.ButtonStyle(color={ft.ControlState.DISABLED: "#3A424D", ft.ControlState.DEFAULT: SUB})
PACKAGES_LINE = "homeassistant:\n  packages: !include_dir_named packages"
DOMAIN_ICONS = {"sensor": ft.Icons.SENSORS, "weather": ft.Icons.WB_SUNNY_OUTLINED, "calendar": ft.Icons.CALENDAR_MONTH,
                "binary_sensor": ft.Icons.TOGGLE_ON_OUTLINED, "number": ft.Icons.PIN, "input_number": ft.Icons.PIN,
                "select": ft.Icons.LIST, "input_select": ft.Icons.LIST, "sun": ft.Icons.WB_TWILIGHT,
                "person": ft.Icons.PERSON_OUTLINE, "light": ft.Icons.LIGHTBULB_OUTLINE, "climate": ft.Icons.THERMOSTAT}
MARKERS = {"bright": "Now bright", "white": "Now white", "none": "No marker"}
LIFT = [ft.BoxShadow(blur_radius=2, offset=ft.Offset(0, 1), color=ft.Colors.with_opacity(0.5, "#000000")),
        ft.BoxShadow(blur_radius=24, offset=ft.Offset(0, 10), color=ft.Colors.with_opacity(0.25, "#000000"))]
TOP_EDGE = ft.Border.only(top=ft.BorderSide(1, ft.Colors.with_opacity(0.06, "#FFFFFF")))
HOOKS = []  # called after every edit: autosave and live preview


def now():
    return datetime.now().astimezone()


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
    kw.setdefault("text_size", 14)
    return ft.TextField(filled=True, fill_color=SUNK, border_color=SUNK, focused_border_color=ACCENT,
                        border_radius=10, dense=True, cursor_color=ACCENT,
                        hint_style=ft.TextStyle(color=FAINT),
                        content_padding=ft.Padding.symmetric(horizontal=14, vertical=18), **kw)


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
                     focused_border_color=ACCENT, border_radius=10, text_size=14,
                     content_padding=ft.Padding.symmetric(horizontal=14, vertical=10),
                     options=[ft.DropdownOption(key=k, text=v) for k, v in options.items()],
                     on_select=lambda e: (on_pick(e.control.value), edited()))
    return ft.Column([caption(title), dd], spacing=6, tight=True)


def button(label, on_click, primary=False, danger=False, icon=None, disabled=False):
    shape = ft.RoundedRectangleBorder(radius=10)
    pad = ft.Padding.symmetric(horizontal=18, vertical=18)
    if primary:
        return ft.FilledButton(label, icon=icon, on_click=on_click, disabled=disabled,
                               style=ft.ButtonStyle(bgcolor={ft.ControlState.DISABLED: "#2B5C64",
                                                             ft.ControlState.DEFAULT: ACCENT},
                                                    color={ft.ControlState.DISABLED: "#A9C9CE",
                                                           ft.ControlState.DEFAULT: ON_ACCENT},
                                                    shape=shape, padding=pad))
    return ft.OutlinedButton(label, icon=icon, on_click=on_click, disabled=disabled,
                             style=ft.ButtonStyle(color={ft.ControlState.DISABLED: FAINT,
                                                         ft.ControlState.DEFAULT: WARN if danger else TEXT},
                                                  side=ft.BorderSide(1, LINE), shape=shape, padding=pad))


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


def ring_view(colors, size=300, on_led=None, centre=None, first_big=True):
    """The clock face. `on_led(i)` fires when the pointer is over or clicks LED i."""
    c, r, dots = size / 2, size / 2 - 24, []
    if centre:
        dots.append(ft.Container(ft.Column([text(centre[0], 26, "#2A3038", ft.FontWeight.W_700),
                                            text(centre[1], 12, "#6A717A")], spacing=2, tight=True,
                                           horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                                 left=0, right=0, top=c - 30, alignment=ft.Alignment.CENTER))
    for i, col in enumerate(colors):
        t, s = i / len(colors) * 2 * math.pi, 16 if i == 0 and first_big else 12
        hit = 22
        dots.append(ft.Container(
            ft.Container(width=s, height=s, border_radius=s / 2, bgcolor=col,
                         shadow=ft.BoxShadow(blur_radius=s - 4, color=col) if col != "#2C333C" else None),
            left=c + r * math.sin(t) - hit / 2, top=c - r * math.cos(t) - hit / 2, width=hit, height=hit,
            alignment=ft.Alignment.CENTER,
            on_hover=(lambda _, i=i: on_led(i)) if on_led else None,
            on_click=(lambda _, i=i: on_led(i)) if on_led else None))
    return ft.Container(ft.Stack(dots, width=size, height=size), width=size, height=size, bgcolor="#F1EFEA",
                        border_radius=size / 2,
                        shadow=ft.BoxShadow(blur_radius=36, offset=ft.Offset(0, 14),
                                            color=ft.Colors.with_opacity(0.45, "#000000")))


def state_of(project):
    """The project as plain data, without secrets: what the draft, undo and "unsaved" compare."""
    if isinstance(project, dict):
        return project
    data = asdict(project)
    data.pop("secrets", None)
    return data


def mounted(control):
    try:
        return control.page is not None
    except RuntimeError:
        return False


def diff_view(old, new):
    """Changed lines in red and green, with three lines of context."""
    lines = list(difflib.unified_diff(old.splitlines(), new.splitlines(), "exported", "draft", n=3, lineterm=""))
    tint = {"+": ("#A9E4BF", "#12271B"), "-": ("#F2A7A7", "#2B1414"), "@": (ACCENT, None)}
    rows = []
    for line in lines[2:]:
        fg, bg = tint.get(line[:1], (SUB, None))
        rows.append(ft.Container(text(line or " ", 12, fg, mono=True, selectable=True), bgcolor=bg,
                                 padding=ft.Padding.symmetric(horizontal=8, vertical=1)))
    return ft.ListView(rows, height=480, spacing=0)


def dim(color, factor):
    """A colour as the ring shows it at a brightness. Kept visible on screen even when very dim."""
    rgb = from_hex(color)
    return to_hex([v * (0.25 + 0.75 * factor) if factor else 24 for v in rgb])


def since(stamp):
    t = datetime.fromisoformat(stamp).astimezone()
    return f"{t:%H:%M}" if t.date() == now().date() else f"{t:%d %b}"


def day_name(t):
    days = (t.date() - now().date()).days
    return {0: "Today", 1: "Tomorrow"}.get(days, f"{t:%a}")


def clock_color(c):
    r = c.ring
    if r.mode in MAP_MODES and r.colors:
        return to_hex(next(iter(r.colors.values())))
    return to_hex(r.palette[len(r.palette) // 2]) if r.palette else ACCENT


class App:
    def __init__(self, page: ft.Page):
        self.page, self.s = page, services.load_settings()
        self.vault = Secrets()
        draft = services.load_draft() or {}
        old = {**draft.pop("secrets", {}), **({"ha_token": self.s.pop("ha_token")} if "ha_token" in self.s else {})}
        if old:  # secrets from before they moved to the keychain
            self.vault.update({k: v for k, v in old.items() if not self.vault.get(k)})
            services.save_settings(self.s)
        self.path = self.s.get("project_path") if os.path.exists(self.s.get("project_path") or "") else None
        self.saved, restored, self.example = None, False, None
        if self.path:
            try:
                self.saved = state_of(projects.open_file(self.path))
            except (OSError, projects.ProjectError):
                self.path = None
        example = dict((n, p) for n, p, _ in projects.examples()).get(self.s.get("example") or "")
        if not self.path and example:  # the draft started from an example: compare against it
            self.example, self.saved = self.s["example"], state_of(projects.open_file(example))
        if draft.get("clocks") or draft.get("note"):
            try:  # the draft can hold half-typed values, so it is checked on save, export and flash instead
                self.project = project_from_dict(draft)
            except (KeyError, TypeError, ValueError, AttributeError):
                self.project = Project()  # a damaged draft is not used
            restored = (self.path or self.example) is not None and state_of(self.project) != self.saved
        elif self.path:
            self.project = project_from_dict(self.saved)
        else:
            self.project = self.first_example()
        self.project.secrets = self.vault.all()
        self.idx, self.entities, self.connected, self.timer = 0, {}, False, None
        self.opened = {"what": True, "bright": False, "device": False, "mapping": False}
        self.preview_colors, self.preview_note = None, "Connect Home Assistant to see the live ring."
        self.snap, self.times, self.at, self.lines, self.sent = None, [], 0, [], False
        self.states, self.place = [], None  # Home Assistant states and (lat, lon, name)
        self.curve = ft.Container()
        self.painting = threading.Lock()
        self.history, self.future, self.last, self.last_edit = [], [], state_of(self.project), 0.0
        self.title = text("", 17, weight=ft.FontWeight.W_700)
        self.title_dot = ft.Container(width=8, height=8, border_radius=4, bgcolor=WARN, tooltip="Unsaved changes")
        page.on_keyboard_event = self.on_key
        self.undo_btn = ft.IconButton(ft.Icons.UNDO, tooltip="Undo (Ctrl+Z)", disabled=True, style=FADE,
                                      on_click=lambda _: self.step(True))
        self.redo_btn = ft.IconButton(ft.Icons.REDO, tooltip="Redo (Ctrl+Y)", disabled=True, style=FADE,
                                      on_click=lambda _: self.step(False))
        self.detail = text("Point at an LED to see what it shows.", 13, SUB)
        self.detail_dot = ft.Container(width=14, height=14, border_radius=7, bgcolor=LINE)
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
        if self.s.get("ha_url") and self.vault.get("ha_token"):
            page.run_thread(self.connect)
        threading.Thread(target=self.poll, daemon=True).start()
        self.refresh()
        if restored:
            self.toast(f"Restored your unsaved changes to {self.project_name}.")
        elif not self.s.get("welcomed"):
            self.welcome_dialog()

    # ---------- state ----------
    @property
    def clock(self):
        return self.project.clocks[self.idx] if self.project.clocks else None

    @property
    def ha(self):
        return services.HomeAssistant(self.s.get("ha_url", ""), self.vault.get("ha_token"))

    def save_setting(self, key, value):
        self.s[key] = value
        services.save_settings(self.s)

    def record(self, new_step=False):
        """Keeps an undo step per burst of typing (a pause of a second starts a new step).
        Bigger changes, like adding a clock or opening a repo, are always a step of their own."""
        snap = state_of(self.project)
        if snap == self.last:
            return
        if new_step or time.monotonic() - self.last_edit > 1.0:
            self.history = (self.history + [self.last])[-50:]
            self.future.clear()
        self.last, self.last_edit = snap, 0.0 if new_step else time.monotonic()
        self.paint_undo()

    def paint_undo(self):
        self.undo_btn.disabled, self.redo_btn.disabled = not self.history, not self.future
        if mounted(self.undo_btn):
            self.undo_btn.update()
            self.redo_btn.update()

    def step(self, back):
        src, dst = (self.history, self.future) if back else (self.future, self.history)
        if not src:
            return
        dst.append(state_of(self.project))
        self.last = src.pop()
        self.project = project_from_dict(self.last)
        self.project.secrets = self.vault.all()
        self.idx = min(self.idx, max(len(self.project.clocks) - 1, 0))
        self.snap, self.preview_colors = None, None
        self.paint_undo()
        self.refresh()
        self.toast("Undone" if back else "Redone")

    def on_key(self, e):
        if not (e.ctrl or e.meta):
            return
        key = e.key.upper()
        if key == "Z":
            self.step(back=not e.shift)
        elif key == "Y":
            self.step(back=False)
        elif key == "E" and self.project.clocks:
            self.export_dialog()
        elif key == "S":
            self.save_project_as() if e.shift else self.save_project()

    def on_edit(self):
        self.record()
        services.save_draft(state_of(self.project))
        self.paint_title()
        self.status.value = "Draft saved"
        self.status.update()
        if mounted(self.curve):
            self.curve.content = self.curve_view()
            self.curve.update()
        self.schedule_preview()

    def refresh(self):
        self.bar.content, self.side.content = self.top_bar(), self.sidebar()
        self.bar.bgcolor, self.bar.padding = BAR, ft.Padding.symmetric(horizontal=28, vertical=12)
        self.side.padding = ft.Padding.symmetric(horizontal=16, vertical=28)
        self.editor.controls = self.editor_view()
        self.record(new_step=True)
        services.save_draft(state_of(self.project))
        self.paint_title()
        self.preview.controls = self.preview_view()
        self.page.update()
        self.schedule_preview(0)

    def toast(self, value):
        self.page.show_dialog(ft.SnackBar(text(value)))

    def dialog(self, title, content, actions, width=620, scrollable=False):
        dlg = ft.AlertDialog(title=text(title, 22, weight=ft.FontWeight.W_700), bgcolor=RAISED, scrollable=scrollable,
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
            self.states = self.ha.states()
            self.entities, self.connected = self.ha.entities(self.states), True
            cfg = self.ha.config()
            self.place = (cfg["latitude"], cfg["longitude"], cfg.get("location_name") or "home")
        except (RuntimeError, KeyError, TypeError) as err:
            self.entities, self.connected, self.preview_note = {}, False, str(err)
        self.refresh()

    def poll(self):
        """Refreshes clock status once a minute while connected."""
        while True:
            time.sleep(60)
            if not self.connected:
                continue
            try:
                self.states = self.ha.states()
            except RuntimeError:
                continue
            self.side.content = self.sidebar()
            self.page.update()

    def clock_state(self, c):
        return services.clock_status(c, self.states) if self.connected else None

    def identify(self, c):
        st = self.clock_state(c)

        def work():
            try:
                self.ha.call("light", "turn_on", {"entity_id": st["light"], "effect": "Rainbow Test"})
                time.sleep(5)
                self.ha.call("light", "turn_on", {"entity_id": st["light"], "effect": c.effect})
            except RuntimeError as err:
                self.toast(str(err))
        self.toast(f"{c.friendly} shows a rainbow for 5 seconds.")
        self.page.run_thread(work)

    def schedule_preview(self, delay=0.6):
        if self.timer:
            self.timer.cancel()
        self.timer = threading.Timer(delay, self.render_preview)
        self.timer.daemon = True
        self.timer.start()

    def render_preview(self):
        """Fetches the entity once, then paints. Moving the time slider only repaints."""
        c = self.clock
        if not c:
            return
        try:
            e = c.ring.entity
            if self.connected:
                st = self.ha.state(e) if e else {}
            else:  # before Home Assistant is connected, the examples run on sample data
                st = sample.state(e, now()) if e else {}
                if st is None:
                    self.snap, self.preview_colors = None, None
                    self.preview_note = "Connect Home Assistant to see this clock with your data."
                    self.preview.controls = self.preview_view()
                    self.page.update()
                    return
            self.snap = Snapshot(c, st) if e or c.ring.mode == "hands" else None
            self.times = self.snap.times(now()) if self.snap else [now()]
            self.at = min(self.at, len(self.times) - 1)
        except (RuntimeError, ValueError) as err:
            self.snap, self.preview_colors, self.preview_note = None, None, str(err)
        self.paint()

    def paint(self):
        with self.painting:
            self._paint()

    def _paint(self):
        c = self.clock
        if not c or not (self.connected or self.snap):
            return
        try:
            if self.at == 0 and self.connected:
                s, n = self.ha.render(generate.jinja(c)), c.hw.leds
                if len(s) != n * 6:
                    raise ValueError(f"The template returned {len(s)} characters instead of {n * 6}.")
                self.preview_colors = ["#" + s[i:i + 6] for i in range(0, n * 6, 6)]
                self.preview_note = "Live from Home Assistant"
            else:
                self.preview_colors = self.snap.colors(self.times[self.at])
                self.preview_note = ("Worked out from Home Assistant data" if self.connected else
                                     "Sample data. Connect Home Assistant to see your own.")
            self.lines = self.snap.details(self.times[self.at], now()) if self.snap else []
        except (RuntimeError, ValueError) as err:
            self.preview_colors, self.lines, self.preview_note = None, [], str(err)
        self.preview.controls = self.preview_view()
        self.page.update()

    def back_to_now(self, _=None):
        self.at, self.sent = 0, False
        self.page.run_thread(self.paint)

    def show_led(self, i):
        if not self.preview_colors or i >= len(self.preview_colors):
            return
        self.detail_dot.bgcolor = self.preview_colors[i]
        self.detail.value = f"LED {i + 1} · " + (self.lines[i] if i < len(self.lines) else "")
        self.detail.color = TEXT
        self.page.update()

    def send_to_clock(self, _=None):
        c, colors = self.clock, self.preview_colors

        def work():
            try:
                self.ha.show(c.colors_entity, "".join(x[1:] for x in colors))
                self.sent = True
            except RuntimeError as err:
                self.toast(str(err))
            self.paint()
        self.page.run_thread(work)

    def stop_sending(self, _=None):
        c = self.clock

        def work():
            try:
                self.ha.update(c.colors_entity)
            except RuntimeError as err:
                self.toast(str(err))
            self.sent = False
            self.at = 0
            self.paint()
        self.page.run_thread(work)

    def connect_dialog(self, _=None):
        out = text("Connected · {} entities".format(len(self.entities)) if self.connected else "", 13, OK)

        warn = text(services.plain_http_warning(self.s.get("ha_url", "")) or "", 12, WARN)

        def set_url(v):
            self.save_setting("ha_url", v.strip())
            warn.value = services.plain_http_warning(v) or ""
            warn.update()

        def go(_):
            try:
                services.check_url(self.s.get("ha_url", ""))
            except RuntimeError as err:
                out.value, out.color = str(err), WARN
                out.update()
                return
            out.value, out.color = "Connecting…", SUB
            out.update()
            self.connect()
            out.value = f"Connected · {len(self.entities)} entities" if self.connected else self.preview_note
            out.color = OK if self.connected else WARN
            out.update()

        self.dialog("Home Assistant", ft.Column([
            text("Used for picking entities and states, the live preview, and reloading after export.", color=SUB),
            field("URL", lambda: self.s.get("ha_url", ""), set_url, width=560,
                  hint_text="https://homeassistant.local:8123"),
            warn,
            field("Long-lived access token", lambda: self.vault.get("ha_token"),
                  lambda v: self.vault.set("ha_token", v), width=560, password=True, can_reveal_password=True),
            caption(f"The token is kept in {self.vault.where}."),
            caption("Create one in Home Assistant under your profile, Security, Long-lived access tokens."),
            out], spacing=18, tight=True), [button("Close", self.close), button("Connect", go, primary=True)])

    # ---------- project files ----------
    @property
    def dirty(self):
        return state_of(self.project) != (self.saved or state_of(Project()))

    @property
    def source_name(self):
        """The project's file name without .ringstudio, for exported headers and Save as."""
        return projects.name_of(self.path) if self.path else self.example or "Untitled"

    @property
    def project_name(self):
        if self.path:
            return projects.name_of(self.path)
        return f"{self.example} (example)" if self.example else "Untitled"

    def paint_title(self, update=True):
        self.title.value = self.project_name
        self.title.color = TEXT if self.path else SUB
        self.title_dot.visible = self.dirty
        self.page.title = f"{self.project_name}{' (unsaved)' if self.dirty else ''} · Ring Studio"
        if update and mounted(self.title):
            self.title.update()
            self.title_dot.update()

    def welcome_dialog(self, _=None):
        """The first thing a new user sees: what they are looking at and the three ways to carry on."""
        self.save_setting("welcomed", True)

        def then(action):
            return lambda _: (self.close(), action())

        def step(number, title, body, action=None):
            return ft.Row([
                ft.Container(text(str(number), 14, ON_ACCENT, ft.FontWeight.W_700), width=28, height=28,
                             border_radius=14, bgcolor=ACCENT, alignment=ft.Alignment.CENTER),
                ft.Column([text(title, 15, weight=ft.FontWeight.W_600), text(body, 13, SUB)], spacing=2,
                          expand=True)] + ([action] if action else []),
                spacing=14, vertical_alignment=ft.CrossAxisAlignment.START)

        self.dialog("Welcome to Ring Studio", ft.Column([
            text("Design what your LED ring clock shows, preview it, then flash it. You are looking at the "
                 f"{self.example or 'Home Clocks'} example with sample data, so everything works straight away.",
                 color=SUB),
            step(1, "Look around", "Pick a clock on the left, change colours under What it shows, and drag "
                                   "Preview time to see the ring later today."),
            step(2, "Use your own data", "Connect Home Assistant and pick your own sensors by name.",
                 button("Connect", then(self.connect_dialog))),
            step(3, "Make your own clock", "Start from a ready-made clock: prices, weather, temperature, battery, "
                                           "calendar or clock hands.",
                 button("Add a clock", then(self.starter_dialog))),
            caption("Open this again from File > Getting started.")], spacing=20, tight=True),
            [button("Open an example", then(self.examples_dialog)),
             button("Start exploring", lambda _: self.close(), primary=True)], 640)

    def first_example(self):
        """On a first start, the Home Clocks example is open, so there is something to look at and change."""
        found = projects.examples()
        if not found:
            return Project()
        name, path, _ = found[0]
        project = projects.open_file(path)
        self.example, self.saved = name, state_of(project)
        self.save_setting("example", name)
        return project

    def adopt(self, project, path, example=None):
        """Makes `project` the open one. Secrets come from the keychain."""
        project.secrets = self.vault.all()
        self.project, self.path, self.idx, self.example = project, path, 0, example
        self.snap, self.preview_colors, self.at, self.sent = None, None, 0, False
        if path or example:
            self.saved = state_of(project)
        self.save_setting("project_path", path or "")
        self.save_setting("example", example or "")
        self.refresh()

    def open_example(self, name, path):
        def go():
            self.adopt(projects.open_file(path), None, example=name)
            self.toast(f"Opened the {name} example. Choose File > Save as to keep it as your own project.")
        self.close()
        self.unsaved_then(go)

    def examples_dialog(self, _=None):
        tiles = []
        for name, path, note in projects.examples():
            p = projects.open_file(path)
            swatch = [to_hex(v) for c in p.clocks for v in (list(c.ring.colors.values())[:4] if c.ring.colors
                                                              else c.ring.palette[::2])][:9]
            tiles.append(ft.Container(ft.Column([
                ft.Row([ft.Container(width=14, height=14, border_radius=7, bgcolor=col, border=ft.Border.all(1, LINE))
                        for col in swatch], spacing=4),
                text(name, 15, weight=ft.FontWeight.W_600),
                text(f"{len(p.clocks)} clocks" if len(p.clocks) > 1 else LAYOUTS.get(p.clocks[0].ring.mode,
                                                                                    ("",))[0] + " layout",
                     12, SUB)], spacing=8, tight=True),
                width=210, height=104, padding=16, bgcolor=CARD, border_radius=14, border=TOP_EDGE, shadow=LIFT,
                ink=True, tooltip=note, on_click=lambda _, n=name, pth=path: self.open_example(n, pth)))
        self.dialog("Open an example", ft.Column([
            text("Ready-made projects. Open one, change the entities to your own, then save it as your project.",
                 color=SUB),
            ft.Row(tiles, wrap=True, spacing=14, run_spacing=14)], spacing=18, tight=True),
            [button("Cancel", self.close)], 690)

    def unsaved_then(self, then):
        """Runs `then`, asking first when there are unsaved changes."""
        if not self.dirty or not self.project.clocks:
            then()
            return
        self.confirm("Unsaved changes", f"{self.project_name} has changes that are not saved to a project "
                     "file. Continue without saving them?", "Continue", then)

    def new_project(self, _=None):
        def go():
            self.saved = state_of(Project())
            self.adopt(Project(), None)
            self.save_setting("project_path", "")
        self.unsaved_then(go)

    def open_project(self, _=None):
        async def pick():
            files = await self.picker.pick_files(dialog_title="Open project", file_type=ft.FilePickerFileType.CUSTOM,
                                                 allowed_extensions=[projects.SUFFIX.lstrip(".")])
            if not files:
                return
            try:
                project = projects.open_file(files[0].path)
            except projects.ProjectError as err:
                self.dialog("Cannot open this project", ft.Column(
                    [text("Nothing was changed. The file was rejected because:", color=SUB)]
                    + [note(p) for p in err.problems[:12]], spacing=10, tight=True), [button("OK", self.close)])
                return
            except OSError as err:
                self.toast(f"Cannot read the file: {err}")
                return
            self.adopt(project, files[0].path)
            self.toast(f"Opened {projects.name_of(files[0].path)}.")
        self.unsaved_then(lambda: self.page.run_task(pick))

    def save_project(self, _=None):
        if not self.path:
            self.save_project_as()
            return
        try:
            projects.check(self.project)
            projects.save(self.path, self.project)
        except projects.ProjectError as err:
            self.problems_dialog("Cannot save yet", err.problems)
            return
        except OSError as err:
            self.toast(f"Cannot save: {err}")
            return
        self.saved = state_of(self.project)
        self.paint_title()
        self.toast(f"Saved {projects.name_of(self.path)}. The previous version is kept as a .bak file.")

    def save_project_as(self, _=None):
        async def pick():
            path = await self.picker.save_file(dialog_title="Save project", file_name=self.source_name
                                               + projects.SUFFIX, file_type=ft.FilePickerFileType.CUSTOM,
                                               allowed_extensions=[projects.SUFFIX.lstrip(".")])
            if path:
                self.path = path if path.endswith(projects.SUFFIX) else path + projects.SUFFIX
                self.save_setting("project_path", self.path)
                self.example = None
                self.save_setting("example", "")
                self.save_project()
        self.page.run_task(pick)

    def problems_dialog(self, title, problems):
        self.dialog(title, ft.Column([note(p) for p in problems[:12]], spacing=10, tight=True),
                    [button("OK", self.close)])

    def notes_dialog(self, _=None):
        self.dialog("Project notes", ft.Column([
            text("Notes stay in the project file. They never reach the exported YAML.", color=SUB),
            attr(self.project, "note", "", width=560, multiline=True, min_lines=6, max_lines=14,
                 hint_text="What these clocks are for, where they hang, what to remember next time")],
            spacing=14, tight=True), [button("Done", self.close, primary=True)])

    def keep_secrets(self):
        """Keys the export or flash generated are stored in the keychain so they stay the same."""
        placeholders = {"YOUR_WIFI_NAME", "YOUR_WIFI_PASSWORD"}
        self.vault.update({k: v for k, v in self.project.secrets.items() if v not in placeholders})

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
        item = lambda label, icon, act: ft.PopupMenuItem(  # noqa: E731
            content=ft.Row([ft.Icon(icon, size=18, color=SUB), text(label, 14)], spacing=12), on_click=act)
        menu = ft.PopupMenuButton(
            content=ft.Container(ft.Row([text("File", 14), ft.Icon(ft.Icons.ARROW_DROP_DOWN, color=SUB, size=18)],
                                        spacing=2, tight=True), padding=ft.Padding.symmetric(horizontal=10, vertical=8)),
            bgcolor=RAISED, menu_position=ft.PopupMenuPosition.UNDER, items=[
                item("New project", ft.Icons.ADD, self.new_project),
                item("Open project…", ft.Icons.FOLDER_OPEN, self.open_project),
                item("Save  (Ctrl+S)", ft.Icons.SAVE_OUTLINED, self.save_project),
                item("Save as…", ft.Icons.SAVE_AS_OUTLINED, self.save_project_as),
                ft.PopupMenuItem(),
                item("Project notes…", ft.Icons.STICKY_NOTE_2_OUTLINED, self.notes_dialog),
                item("Open example…", ft.Icons.AUTO_AWESOME_OUTLINED, self.examples_dialog),
                item("Getting started", ft.Icons.HELP_OUTLINE, self.welcome_dialog)])
        self.paint_title(update=False)
        return ft.Row([logo, text("Ring Studio", 17, weight=ft.FontWeight.W_700),
                       ft.Container(width=1, height=22, bgcolor=LINE), menu, ft.Row([self.title, self.title_dot], spacing=10, tight=True),
                       ft.Container(expand=True),
                       self.status,
                       self.undo_btn, self.redo_btn,
                       ha,
                       button("Export", self.export_dialog, primary=True, disabled=not self.project.clocks)],
                      spacing=14)

    def sidebar(self):
        def select(i):
            self.idx, self.at, self.sent, self.snap, self.preview_colors = i, 0, False, None, None
            self.refresh()

        def add(_):
            self.starter_dialog()

        items = [ft.Container(text("CLOCKS", 12, FAINT, ft.FontWeight.W_600), padding=ft.Padding.only(left=12, bottom=8))]
        for i, c in enumerate(self.project.clocks):
            on, st = i == self.idx, self.clock_state(c)
            kind = LAYOUTS.get(c.ring.mode, ("Raw",))[0]
            line = (kind if not st else f"{kind} · online" if st["online"] else
                    f"{kind} · offline" + (f" since {since(st['since'])}" if st["since"] else "") if st["found"]
                    else f"{kind} · not in Home Assistant")
            items.append(ft.Container(
                ft.Row([ft.Stack([dot(clock_color(c), 28), ft.Container(
                    width=10, height=10, border_radius=5, right=0, bottom=0, border=ft.Border.all(2, BG),
                    bgcolor="#4CC37A" if st and st["online"] else FAINT, visible=bool(st))], width=28, height=28),
                        ft.Column([text(c.friendly, weight=ft.FontWeight.W_600), text(line, 12, SUB)],
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
                text("Open one of the examples, or start a new clock.", color=SUB),
                ft.Row([button("Open an example", self.examples_dialog, primary=True),
                        button("Add a clock", lambda _: self.starter_dialog())], spacing=12)],
                spacing=16), padding=ft.Padding.only(top=80))]
        r, d = c.ring, self.project.dimming
        what = (f"{LAYOUTS[r.mode][0]} · {len(r.colors)} colours" if r.mode in MAP_MODES
                else f"{LAYOUTS[r.mode][0]} · {len(r.palette)} stops" if r.mode in LAYOUTS else "Raw template")
        nights = "on all night" if d.night_start >= 24 else f"off {d.night_start:02d} to {d.night_end:02d}"
        bright = f"Follows the sun · {nights}" if c.name in d.targets else "Fixed, set on the device"
        device = f"{c.hw.pin} · {c.hw.leds} LEDs · {c.name}.local"
        return [ft.Column([text(c.friendly, 28, weight=ft.FontWeight.W_700), text(DIAL_SUBTITLE if r.dial == "24h" and r.mode in LIST_MODES
                                                                else SUBTITLES[r.mode], color=SUB),
                           ft.Container(attr(c, "note", "", width=620, multiline=True, min_lines=1, max_lines=6,
                                             hint_text="Notes about this clock, only for you", text_size=13),
                                        padding=ft.Padding.only(top=6))],
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
        if r.mode == "hands":
            return self.hands_body(r)
        if self.connected:
            entity = self.entity_card(r)
        else:
            entity = ft.Column([field("", lambda: r.entity, lambda v: setattr(r, "entity", v), width=560, mono=True),
                                caption("Connect Home Assistant to choose from your entities instead of typing.")],
                               spacing=6)
        parts = [ft.Column([caption("Entity"), entity], spacing=6),
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
        parts += [ft.Row(chips, wrap=True, spacing=12, run_spacing=12)]
        if r.mode in LIST_MODES:
            parts.append(self.dial_options(r))
        parts.append(self.mapping(r))
        return ft.Column(parts, spacing=28)

    # ---------- entities ----------
    def entity_state(self, entity_id):
        return next((s for s in self.states if s.get("entity_id") == entity_id), {})

    def entity_card(self, r):
        """The chosen entity as people know it, with a button to change it."""
        st = self.entity_state(r.entity)
        if not r.entity:
            return button("Choose an entity", lambda _: self.entity_dialog(), primary=True, icon=ft.Icons.SEARCH)
        name = (st.get("attributes") or {}).get("friendly_name") or r.entity
        domain = r.entity.split(".")[0]
        return ft.Container(ft.Row([
            ft.Icon(DOMAIN_ICONS.get(domain, ft.Icons.CIRCLE_OUTLINED), color=ACCENT, size=22),
            ft.Column([text(name, 15, weight=ft.FontWeight.W_600),
                       text(r.entity, 12, SUB, mono=True)], spacing=2, tight=True, expand=True),
            text(detect.shown_value(st) if st else "Not found in Home Assistant", 13, SUB if st else WARN),
            ft.TextButton("Change", on_click=lambda _: self.entity_dialog(), style=ft.ButtonStyle(color=ACCENT))],
            spacing=14), bgcolor=SUNK, border_radius=12, width=620, ink=True,
            padding=ft.Padding.only(left=16, right=8, top=12, bottom=12), on_click=lambda _: self.entity_dialog())

    def use_entity(self, entity_id, announce=True):
        """Sets the entity and fills the data mapping from its data."""
        r = self.clock.ring
        r.entity = entity_id
        fields, words = detect.guess(r.mode, self.entity_state(entity_id))
        for k, v in fields.items():
            setattr(r, k, v)
        edited()
        self.snap, self.preview_colors, self.at = None, None, 0
        self.refresh()
        if announce and words:
            self.toast(words)

    def entity_dialog(self, _=None):
        """Every entity Home Assistant has, live, with its attributes. The ones that fit the layout come first."""
        r = self.clock.ring
        layout = LAYOUTS.get(r.mode, ("this layout",))[0]
        ui = {"query": "", "only": True, "picked": r.entity}
        rows = ft.ListView(height=440, spacing=2)
        count = caption("")
        detail = ft.Column(spacing=10, scroll=ft.ScrollMode.AUTO, height=500)
        loaded = caption("")
        use = button("Use this entity", None, primary=True)

        def name_of(st):
            return (st.get("attributes") or {}).get("friendly_name") or st["entity_id"]

        def paint_list():
            words = ui["query"].lower().split()
            pool = [st for st in self.states if all(w in (st["entity_id"] + " " + name_of(st)).lower() for w in words)]
            fit = sorted((st for st in pool if detect.fits(r.mode, st)), key=name_of)
            shown = fit if ui["only"] else fit + sorted((st for st in pool if st not in fit), key=name_of)
            rows.controls = [self.entity_row(st, st["entity_id"] == ui["picked"], detect.fits(r.mode, st),
                                             lambda st=st: pick(st["entity_id"])) for st in shown[:150]]
            count.value = (f"{len(shown)} {'entity' if len(shown) == 1 else 'entities'}" if len(shown) <= 150 else
                           f"Showing 150 of {len(shown)}. Type to narrow it down.") + \
                (f" that fit {layout}." if ui["only"] else ".")
            if not shown and ui["only"]:
                count.value = f"Nothing here fits {layout}. Switch to All entities."

        def paint_detail():
            st = self.entity_state(ui["picked"])
            use.disabled = not st
            if not st:
                detail.controls = [text("Pick an entity on the left to see its data.", color=SUB)]
                return
            fields, words = detect.guess(r.mode, st)
            attrs = [ft.Container(ft.Column([
                ft.Row([text(n, 13, mono=True, weight=ft.FontWeight.W_600), text(v, 12, SUB, expand=True)],
                       spacing=10, vertical_alignment=ft.CrossAxisAlignment.START)]
                + ([text(sample, 11, FAINT, mono=True)] if sample else []), spacing=2, tight=True),
                padding=ft.Padding.symmetric(vertical=6)) for n, v, sample in detect.attribute_rows(st)]
            detail.controls = [
                text(name_of(st), 18, weight=ft.FontWeight.W_700), text(st["entity_id"], 12, SUB, mono=True),
                ft.Row([text("Now", 12, FAINT), text(detect.shown_value(st), 14)], spacing=10),
                ft.Container(ft.Row([ft.Icon(ft.Icons.AUTO_FIX_HIGH, size=16, color=ACCENT),
                                     text(words or f"Nothing to set up for {layout}.", 12, TEXT, expand=True)],
                                    spacing=8, vertical_alignment=ft.CrossAxisAlignment.START),
                             bgcolor=ACCENT_BG, border_radius=10, padding=12),
                caption("Attributes")] + (attrs or [text("No attributes.", 12, SUB)])

        def pick(entity_id):
            ui["picked"] = entity_id
            paint_list()
            paint_detail()
            self.page.update()

        def search(e):
            ui["query"] = e.control.value or ""
            paint_list()
            rows.update()
            count.update()

        def scope(v):
            ui["only"] = v == "fit"
            paint_list()
            filters.content = seg()
            self.page.update()

        def seg():
            return self.segmented({"fit": f"Fits {layout}", "all": "All entities"}, "fit" if ui["only"] else "all",
                                  scope, local=True).content

        def reload(_):
            def work():
                loaded.value = "Loading…"
                self.page.update()
                try:
                    self.states = self.ha.states()
                    self.entities = self.ha.entities(self.states)
                    loaded.value = f"{len(self.states)} entities, loaded {now():%H:%M}"
                except RuntimeError as err:
                    loaded.value = str(err)
                paint_list()
                paint_detail()
                self.page.update()
            self.page.run_thread(work)

        def done(_):
            self.close()
            self.use_entity(ui["picked"])

        use.on_click = done
        filters = ft.Container(seg())
        loaded.value = f"{len(self.states)} entities from Home Assistant"
        paint_list()
        paint_detail()
        left = ft.Column([box(hint_text="Search by name or entity ID", autofocus=True, on_change=search, width=430,
                              prefix_icon=ft.Icons.SEARCH),
                          ft.Row([filters], spacing=8), count, rows], spacing=10, width=430)
        right = ft.Container(detail, width=440, bgcolor=SUNK, border_radius=14, padding=18)
        self.dialog("Choose an entity", ft.Column([
            ft.Row([loaded, ft.Container(expand=True),
                    ft.TextButton("Reload from Home Assistant", icon=ft.Icons.REFRESH, on_click=reload,
                                  style=ft.ButtonStyle(color=SUB))]),
            ft.Row([left, right], spacing=20, vertical_alignment=ft.CrossAxisAlignment.START)], spacing=8, tight=True),
            [button("Cancel", self.close), use], 900)

    def entity_row(self, st, picked, fits, on_pick):
        domain = st["entity_id"].split(".")[0]
        name = (st.get("attributes") or {}).get("friendly_name") or st["entity_id"]
        return ft.Container(ft.Row([
            ft.Icon(DOMAIN_ICONS.get(domain, ft.Icons.CIRCLE_OUTLINED), size=18, color=ACCENT if fits else FAINT),
            ft.Column([text(name, 13, TEXT if fits else SUB, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                       text(st["entity_id"], 11, FAINT, mono=True, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)],
                      spacing=1, tight=True, expand=True),
            text(detect.shown_value(st), 12, SUB, max_lines=1, width=110, text_align=ft.TextAlign.RIGHT)],
            spacing=12), bgcolor=ACCENT_BG if picked else None, border=ft.Border.all(1, ACCENT if picked else BG),
            border_radius=10, padding=ft.Padding.symmetric(horizontal=12, vertical=8), ink=True,
            on_click=lambda _: on_pick())

    def orientation(self, r):
        """Where 12 o'clock is on the ring and which way the LEDs run. Used by Hands and the 24-hour dial."""
        def turn(v):
            r.clockwise = v == "cw"

        return ft.Row([attr(r, "start_led", "LED at 12 o'clock", int, width=150),
                       ft.Column([caption("LED order"), self.segmented({"cw": "Clockwise", "ccw": "Anticlockwise"},
                                                                       "cw" if r.clockwise else "ccw", turn)],
                                 spacing=6, tight=True)], spacing=20, vertical_alignment=ft.CrossAxisAlignment.START)

    def dial_options(self, r):
        """List layouts: one LED per item from now, or a fixed 24-hour dial with midnight at the top."""
        def choose(v):
            r.dial = v
            edited()
            self.refresh()

        parts = [ft.Column([caption("Hours on the ring"), self.segmented(
            {"": "From now, one LED per item", "24h": "24-hour dial"}, r.dial, choose, local=True)],
            spacing=6, tight=True)]
        if r.dial == "24h":
            per = self.clock.hw.leds / 24
            size = f"{per:g} LEDs" if per == int(per) else "1 or 2 LEDs, since the LEDs do not split evenly into 24"
            parts.append(caption("Midnight is at the top and every hour keeps its place: 00-01, 01-02 and so on, "
                                 f"{size}. The ring shows the next 24 hours, and the current hour is the bright one."))
            if not r.t_start:
                parts.append(note("The 24-hour dial needs the time of each item. Set the start time key in Data "
                                  "mapping, or press Detect from the entity again."))
            parts.append(self.orientation(r))
        return ft.Column(parts, spacing=12)

    def hands_body(self, r):
        """The clock-hands layout needs no entity: Home Assistant's clock drives it."""
        return ft.Column([
            ft.Column([caption("Ring layout"), ft.Row([self.tile(k, v) for k, v in LAYOUTS.items()],
                                                     wrap=True, spacing=10, run_spacing=10)], spacing=8),
            self.gradient_editor(r),
            caption("The colour stops are spread evenly over the day, starting at midnight on the left and wrapping "
                    "back to it. The hour hand shows the colour for now, the minute hand a lighter version."),
            ft.Row([self.color_chip("Face", lambda: r.missing, lambda v: setattr(r, "missing", v)),
                    ft.Row([caption("Quarter marks"), ft.Slider(
                        min=0, max=50, divisions=10, value=r.dim * 100, width=180, active_color=ACCENT,
                        label="{value}%", on_change_end=lambda e: (setattr(r, "dim", round(e.control.value / 100, 2)),
                                                                    edited()))], spacing=4, tight=True)],
                   wrap=True, spacing=12, run_spacing=12),
            self.orientation(r),
            caption("If the hands sit in the wrong place on the wall, change the LED at 12 o'clock. If they move "
                    "backwards, change the LED order. Send this to the clock to check.")], spacing=24)

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

    def segmented(self, options, value, put, local=False):
        def choose(k):
            put(k)
            if local:
                return
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
        title = "Colours through the day" if r.mode == "hands" else f"Colours from {r.lo:g} to {r.hi:g}"
        return ft.Column([ft.Row([caption(title), ft.Container(expand=True),
                                  ft.TextButton("+ Add stop", on_click=add, style=ft.ButtonStyle(color=SUB))],
                                 width=width),
                          ft.Stack([bar] + dots, width=width, height=34),
                          ft.Row([caption("Presets")] + [self.gradient_chip(r, name, stops)
                                                         for name, stops in GRADIENTS.items()],
                                 wrap=True, spacing=8, run_spacing=8, width=width + 120)], spacing=10)

    def gradient_chip(self, r, name, stops):
        def use(_):
            r.palette = [c[:] for c in stops]
            self.refresh_editor()

        same = r.palette == stops
        return ft.Container(ft.Row([ft.Container(width=34, height=10, border_radius=5, gradient=ft.LinearGradient(
            colors=[to_hex(p) for p in stops], begin=ft.Alignment.CENTER_LEFT, end=ft.Alignment.CENTER_RIGHT)),
            text(name, 12, TEXT if same else SUB)], spacing=8, tight=True), on_click=use, ink=True,
            border_radius=16, border=ft.Border.all(1, ACCENT if same else LINE),
            padding=ft.Padding.symmetric(horizontal=10, vertical=6))

    def refresh_editor(self):
        edited()
        self.editor.controls = self.editor_view()
        self.side.content = self.sidebar()
        self.page.update()

    def state_note_dialog(self, r, key):
        def put(v):
            if v:
                r.state_notes[key] = v
            else:
                r.state_notes.pop(key, None)

        def done(_):
            self.close()
            self.refresh_editor()

        self.dialog(f"Note for {key}", ft.Column([
            caption("Only for you. Kept in the project file, never exported."),
            field("", lambda: r.state_notes.get(key, ""), put, width=520, multiline=True, min_lines=3,
                  max_lines=8, hint_text="For example: shows up a few times a year, so a strong colour is fine")],
            spacing=10, tight=True), [button("Done", done, primary=True)], 560)

    def map_editor(self, r):
        def rename(old, new):
            r.colors = {(new if k == old else k): v for k, v in r.colors.items()}
            r.labels = {(new if k == old else k): v for k, v in r.labels.items()}
            r.state_notes = {(new if k == old else k): v for k, v in r.state_notes.items()}

        def add(states):
            for s in states:
                r.colors.setdefault(s, from_hex(PRESETS[(len(r.colors) + 1) % len(PRESETS)]))
            self.refresh_editor()

        def remove(key):
            r.colors.pop(key, None)
            r.labels.pop(key, None)
            r.state_notes.pop(key, None)
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
                ft.IconButton(ft.Icons.STICKY_NOTE_2 if r.state_notes.get(key) else ft.Icons.STICKY_NOTE_2_OUTLINED,
                              icon_color=ACCENT if r.state_notes.get(key) else FAINT,
                              tooltip=r.state_notes.get(key) or "Add a note", on_click=lambda _, cell=cell:
                              self.state_note_dialog(r, cell[0])),
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
        again = ft.TextButton("Detect from the entity again", icon=ft.Icons.AUTO_FIX_HIGH,
                              style=ft.ButtonStyle(color=ACCENT), disabled=not (self.connected and r.entity),
                              on_click=lambda _: self.use_entity(r.entity))
        rows = []
        if r.mode in LIST_MODES:
            rows += [attr(r, "attrs", "List attributes", lambda s: [x.strip() for x in s.split(",") if x.strip()],
                          ", ".join), attr(r, "key", "Item key", mono=True),
                     attr(r, "t_start", "Start time key", mono=True), attr(r, "t_end", "End time key", mono=True)]
        if r.mode not in MAP_MODES:
            rows += [attr(r, "scale", "Multiply value by", float), attr(r, "lo", "Low end", float),
                     attr(r, "hi", "High end", float)]
        tip = "Leave the time keys empty when item 0 is always now." if r.mode in LIST_MODES else ""
        return ft.Column([head, ft.Row(rows, wrap=True, spacing=14, run_spacing=14,
                                       vertical_alignment=ft.CrossAxisAlignment.START)]
                         + ([caption(tip)] if tip else []) + [again], spacing=14)

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
            parts += [ft.Row([attr(d, "night_start", "Off from (hour, 24 = never)", int, width=190),
                              attr(d, "night_end", "Back on at (hour)", int, width=150),
                              attr(d, "low", "Dimmest", int, width=110),
                              attr(d, "elev_low", "at sun angle °", float, width=130),
                              attr(d, "high", "Brightest", int, width=110),
                              attr(d, "elev_high", "at sun angle °", float, width=130)], wrap=True, spacing=14,
                             run_spacing=14, vertical_alignment=ft.CrossAxisAlignment.START),
                      caption("Shared by " + ", ".join(users) + ".")]
            self.curve.content = self.curve_view()
            parts.insert(1, self.curve)
        return ft.Column(parts, spacing=20)

    def curve_view(self):
        """Brightness over today, from the sun at the Home Assistant location. Half an hour per bar."""
        d = self.project.dimming
        if not self.place:
            return caption("Connect Home Assistant to see today's brightness curve.")
        lat, lon, where = self.place
        today = now()
        curve = sun.day_curve(d, lat, lon, today)
        top, h = max(d.high, 1), 72
        here = (today.hour * 60 + today.minute) // 30
        bars = [ft.Container(width=9, height=max(2, h * b / top), border_radius=2, tooltip=f"{t:%H:%M} · {b}",
                             bgcolor=(ACCENT if i == here else ft.Colors.with_opacity(0.55, ACCENT)) if b else LINE)
                for i, (t, b) in enumerate(curve)]
        lit = [(t, b) for t, b in curve if b]
        peak = max(lit, key=lambda x: x[1]) if lit else None
        if not lit:
            words = f"Today in {where}: off all day."
        elif d.night_start >= 24:
            words = f"Today in {where}: on day and night, brightest {peak[1]} at {peak[0]:%H:%M}."
        else:
            words = (f"Today in {where}: on from {lit[0][0]:%H:%M}, brightest {peak[1]} at {peak[0]:%H:%M}, "
                     f"off from {d.night_start:02d}:00.")
        ticks = ft.Row([caption(f"{x:02d}") for x in (0, 6, 12, 18, 24)], width=48 * 12 - 3,
                       alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
        return ft.Column([ft.Row(bars, spacing=3, vertical_alignment=ft.CrossAxisAlignment.END, height=h),
                          ticks, text(words, 13, SUB)], spacing=8)

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

        return ft.Column(self.device_status(c) + [
            ft.Row([field("Device name", lambda: c.name, rename, slug, mono=True),
                    attr(c, "friendly", "Display name"), attr(c, "effect", "Effect name")], wrap=True, spacing=14,
                   run_spacing=14, vertical_alignment=ft.CrossAxisAlignment.START),
            self.hardware(hw),
            ft.Row([ft.Row([button("Flash and back up", self.firmware_dialog, icon=ft.Icons.USB),
                            button("WiFi and keys", self.keys_dialog, icon=ft.Icons.WIFI)], spacing=12, tight=True),
                    button("Remove clock", lambda _: self.confirm(
                        "Remove clock", f"Remove {c.friendly} from this project? Exported files are not deleted.",
                        "Remove", remove), danger=True)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)], spacing=24)

    def device_status(self, c):
        """Online state, firmware version and Identify, from Home Assistant."""
        st = self.clock_state(c)
        if not st:
            return []
        if not st["found"]:
            return [caption("Not in Home Assistant yet. After the first flash, add it under Settings, Devices "
                            "and services, where it shows up as discovered.")]
        version = st["version"]
        installed = services.tool_versions()["esphome"]
        words = ("Online" if st["online"] else "Offline" + (f" since {since(st['since'])}" if st["since"] else "")) \
            + (f" · ESPHome {version}" if version else "")
        row = ft.Row([ft.Container(width=10, height=10, border_radius=5,
                                   bgcolor="#4CC37A" if st["online"] else FAINT),
                      text(words, 13, TEXT if st["online"] else SUB, expand=True),
                      button("Identify", lambda _: self.identify(c), icon=ft.Icons.LIGHTBULB_OUTLINE,
                             disabled=not st["online"])], spacing=10)
        out = [row]
        if st["online"] and services.newer(installed, version):
            out.append(note(f"The clock runs ESPHome {version}. {installed} is installed here.",
                            ("Update over the air", lambda _: self.firmware_dialog())))
        elif st["online"] and not version:
            out.append(caption("Update over the air once to show the firmware version here."))
        return out

    def hardware(self, hw):
        """The tested preset as one card. The raw fields only when asked for."""
        preset = asdict(HW_PRESET)
        matches = all(getattr(hw, k) == preset[k] for k in HW_KEYS)

        def use_preset(_):
            for k in HW_KEYS:
                setattr(hw, k, preset[k])
            edited()
            self.refresh()

        def toggle(_):
            self.opened["hw"] = not self.opened.get("hw")
            self.refresh()

        summary = f"ESP8266 · {hw.pin} · {hw.leds} LEDs · {hw.method} · {hw.order}"
        face = ft.Container(width=34, height=34, border_radius=17, bgcolor="#F1EFEA",
                            content=ft.Container(border_radius=12, border=ft.Border.all(2.5, ACCENT), margin=5))
        head = ft.Row([face, ft.Column([text(HW_NAME if matches else "Custom hardware", weight=ft.FontWeight.W_600),
                                        text(summary, 12, SUB)], spacing=3, tight=True, expand=True),
                       ft.Row([ft.Icon(ft.Icons.CHECK, size=16, color="#7FD6E0"),
                               text("Tested on this clock", 13, "#7FD6E0")], spacing=6, tight=True) if matches
                       else ft.TextButton(f"Use {HW_NAME}", on_click=use_preset, style=ft.ButtonStyle(color=ACCENT))],
                      spacing=14)
        parts = [caption("Hardware"),
                 ft.Container(head, bgcolor=ACCENT_BG if matches else SUNK, border_radius=12,
                              border=ft.Border.all(1, "#2E5A63" if matches else LINE),
                              padding=ft.Padding.symmetric(horizontal=18, vertical=14)),
                 ft.TextButton("Hide custom hardware" if self.opened.get("hw") else "Custom hardware",
                               icon=ft.Icons.EXPAND_LESS if self.opened.get("hw") else ft.Icons.CHEVRON_RIGHT,
                               on_click=toggle, style=ft.ButtonStyle(color=SUB))]
        if self.opened.get("hw"):
            parts.append(ft.Row([
                attr(hw, "board", "Board", width=150), attr(hw, "pin", "Data pin", width=130),
                pick("Driver", hw.method, {m: m for m in ("bit_bang", "esp8266_uart", "esp8266_dma")},
                     lambda v: setattr(hw, "method", v), 170),
                attr(hw, "variant", "LED type", width=130),
                pick("Colour order", hw.order, {o: o for o in ("GRB", "RGB", "BRG", "GRBW")},
                     lambda v: setattr(hw, "order", v), 140),
                attr(hw, "gamma", "Gamma", float, width=100), attr(hw, "leds", "LEDs", int, width=100),
                attr(hw, "start_brightness", "Start brightness", int, width=140),
                attr(hw, "max_brightness", "Max brightness", int, width=140)], wrap=True, spacing=14,
                run_spacing=14, vertical_alignment=ft.CrossAxisAlignment.START))
        return ft.Column(parts, spacing=8)

    # ---------- preview ----------
    def preview_view(self):
        c = self.clock
        if not c:
            return []
        colors = self.preview_colors if self.preview_colors and len(self.preview_colors) == c.hw.leds \
            else ["#2C333C"] * c.hw.leds
        live = bool(self.preview_colors)
        timed = self.snap is not None and len(self.times) > 1
        at = self.times[self.at] if timed else None
        d, glow = self.project.dimming, None
        if live and self.place and d.enabled and c.name in d.targets:
            level = sun.at(d, self.place[0], self.place[1], at or now())
            glow = f"Brightness {level} of {d.high}" if level else \
                f"Off at night, {d.night_start:02d}:00 to {d.night_end:02d}:00"
            colors = [dim(col, level / max(d.high, 1)) for col in colors]
        centre = (f"{at:%H:%M}", ("Now · " if self.at == 0 else "") + day_name(at)) if timed else None
        dot_colour = ("#4CC37A" if self.connected else "#E9C46A") if live else FAINT
        status = ft.Row([ft.Container(width=8, height=8, border_radius=4, bgcolor=dot_colour),
                         text(self.preview_note, 12, SUB, max_lines=3, width=300)], spacing=8, tight=True)
        out = [ring_view(colors, on_led=self.show_led if live else None, centre=centre,
                         first_big=c.ring.mode in LIST_MODES and c.ring.dial != "24h"), status]
        if glow:
            out.insert(2, ft.Row([ft.Icon(ft.Icons.LIGHT_MODE_OUTLINED, size=14, color=SUB), text(glow, 12, SUB)],
                                 spacing=8, tight=True))
        if live:
            self.detail = text("Point at an LED to see what it shows.", 13, SUB)
            self.detail_dot = ft.Container(width=14, height=14, border_radius=7, bgcolor=LINE)
            out.append(ft.Container(ft.Row([self.detail_dot, ft.Container(self.detail, expand=True)], spacing=12),
                                    width=320, bgcolor=CARD, border=TOP_EDGE, border_radius=12,
                                    padding=ft.Padding.symmetric(horizontal=14, vertical=12)))
        if timed:
            def slide(e):
                self.at = int(e.control.value)
                self.page.run_thread(self.paint)
            last = self.times[-1]
            out.append(ft.Column([
                ft.Row([caption("Preview time"), text(f"{day_name(at)} {at:%H:%M}", 12)],
                       alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Slider(min=0, max=len(self.times) - 1, divisions=len(self.times) - 1, value=self.at,
                          active_color=ACCENT, on_change_end=slide),
                ft.Row([caption("Now"), caption(f"{day_name(last)} {last:%H:%M}")],
                       alignment=ft.MainAxisAlignment.SPACE_BETWEEN)]
                + ([ft.Row([ft.TextButton("Back to now", style=ft.ButtonStyle(color=SUB), on_click=self.back_to_now)],
                           alignment=ft.MainAxisAlignment.CENTER)] if self.at else []),
                width=320, spacing=4))
        if live and self.sent:
            out.append(ft.Container(ft.Row([
                ft.Column([text("On the wall now", 13, "#B5EAF0"),
                           caption("Back to normal at the next update, within a minute.")], spacing=2, expand=True),
                button("Stop", self.stop_sending)], spacing=12), width=320, bgcolor="#13282C", border_radius=12,
                border=ft.Border.all(1, "#2E5A63"), padding=ft.Padding.symmetric(horizontal=14, vertical=10)))
        elif live and self.connected:
            out.append(ft.Container(button("Send this to the clock", self.send_to_clock, icon=ft.Icons.ARROW_FORWARD),
                                    width=320, alignment=ft.Alignment.CENTER))
        out.append(self.legend(c))
        if not self.connected:
            out.append(button("Connect Home Assistant", self.connect_dialog))
        return out

    def legend(self, c):
        r = c.ring
        if r.mode == "hands":
            stops = len(r.palette)
            items = [(to_hex(r.palette[round(h / 24 * stops) % stops]), f"{h:02d}:00") for h in (0, 6, 12, 18)]
        elif r.mode in MAP_MODES:
            items = [(to_hex(v), r.labels.get(k) or k) for k, v in r.colors.items()]
        elif r.mode in LAYOUTS:
            items = [(to_hex(r.palette[0]), f"{r.lo:g}"), (to_hex(r.palette[len(r.palette) // 2]),
                                                           f"{(r.lo + r.hi) / 2:g}"), (to_hex(r.palette[-1]), f"{r.hi:g}")]
            if r.below:
                items.append((to_hex(r.below), f"below {r.lo:g}"))
        else:
            items = []
        chips = [ft.Row([ft.Container(width=10, height=10, border_radius=5, bgcolor=col,
                                      border=ft.Border.all(1, LINE)), text(t, 12, SUB)],
                        spacing=6, tight=True) for col, t in items]
        return ft.Row(chips, wrap=True, spacing=14, run_spacing=8, width=320, alignment=ft.MainAxisAlignment.CENTER)

    # ---------- dialogs ----------
    def starter_dialog(self, _=None):
        def make(key):
            c = STARTERS[key][2]()
            taken = {x.name for x in self.project.clocks}
            base, n = c.name, 2
            while c.name in taken:
                c.name, c.friendly, n = f"{base}_{n}", f"{c.friendly} {n}", n + 1
            self.project.clocks.append(c)
            self.project.dimming.targets.append(c.name)
            self.idx, self.at, self.snap, self.preview_colors = len(self.project.clocks) - 1, 0, None, None
            self.opened.update(what=True, device=False)
            self.close()
            edited()
            self.refresh()

        tiles = []
        for key, (title, sub, factory) in STARTERS.items():
            c = factory()
            swatch = [to_hex(v) for v in (list(c.ring.colors.values())[:5] if c.ring.colors else c.ring.palette)]
            tiles.append(ft.Container(ft.Column([
                ft.Row([ft.Container(width=14, height=14, border_radius=7, bgcolor=col, border=ft.Border.all(1, LINE))
                        for col in swatch]
                       if key != "blank" else [ft.Icon(ft.Icons.ADD, color=SUB, size=14)], spacing=4),
                text(title, 15, weight=ft.FontWeight.W_600), caption(sub)], spacing=8, tight=True),
                width=210, height=112, padding=16, bgcolor=CARD, border_radius=14, border=TOP_EDGE, shadow=LIFT,
                ink=True, on_click=lambda _, key=key: make(key)))
        self.dialog("Add a clock", ft.Column([
            text("Start from a ready-made clock and change anything afterwards.", color=SUB),
            ft.Row(tiles, wrap=True, spacing=14, run_spacing=14)], spacing=18, tight=True),
            [button("Cancel", self.close)], 690)

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

    def export_dialog(self, _=None):
        try:
            projects.check(self.project)
        except projects.ProjectError as err:
            self.problems_dialog("Fix these before exporting", err.problems)
            return
        source = self.source_name
        files = generate.repo_files(self.project, source)
        self.keep_secrets()
        listing = ft.Column(spacing=0)
        package_on = ft.Switch(value=bool(self.s.get("package")), active_color=ACCENT)
        go = button("Export", None, primary=True)

        package = generate.package_file(self.project, source)

        def current(rel):
            path = os.path.join(self.s.get("repo") or "", rel)
            if not self.s.get("repo") or not os.path.exists(path):
                return None
            with open(path, encoding="utf-8") as fh:
                return fh.read()

        def status(rel):
            old = current(rel)
            return "New" if old is None else "Unchanged" if old == files[rel] else "Changed"

        def view(rel):
            if os.path.basename(rel) == "secrets.yaml":
                body = ft.Container(text("This file holds your WiFi password and keys, so it is not shown here. "
                                         "It is written readable only by your account.", color=SUB), width=500)
                self.dialog(rel, body, [button("Close", self.close)], 560)
                return
            old = current(rel)
            if old is None or old == files[rel]:
                body = box(value=files[rel], multiline=True, read_only=True, min_lines=22, text_size=12,
                           text_style=ft.TextStyle(font_family=MONO))
            else:
                body = ft.Container(diff_view(old, files[rel]), bgcolor=SUNK, border_radius=12, padding=12)
            self.dialog(rel + ("" if old is None or old == files[rel] else " · changes"), body,
                        [button("Close", self.close)], 860)

        def fill():
            states = {rel: status(rel) for rel in files}
            listing.controls = [ft.Container(ft.Row([text(rel, 13, mono=True, expand=True),
                                                     text(st, 12, ACCENT if st != "Unchanged" else FAINT),
                                                     ft.TextButton("View", on_click=lambda _, rel=rel: view(rel))], spacing=12),
                                             padding=ft.Padding.symmetric(horizontal=16, vertical=4))
                                for rel, st in states.items()]
            todo = [rel for rel, st in states.items() if st != "Unchanged"]
            go.content = f"Export {len(todo)} files" if todo else "Export"
            return todo

        def choose(key):
            async def run(_):
                if path := await self.picker.get_directory_path():
                    self.save_setting(key, path)
                    self.close()
                    self.export_dialog()
            return run

        def export(_):
            if not self.s.get("repo") and not (package_on.value and self.s.get("packages")):
                self.toast("Choose the repo folder or the Home Assistant packages folder first")
                return
            msg = "Nothing written to the repo"
            if self.s.get("repo"):
                todo = fill()
                try:
                    generate.write_files(self.s["repo"], {rel: files[rel] for rel in todo})
                    ignored = generate.protect_secrets(self.s["repo"])
                except (OSError, ValueError) as err:
                    self.toast(f"Cannot write to the repo folder: {err}")
                    return
                msg = f"Exported {len(todo)} files" + (", and added config/secrets.yaml to .gitignore"
                                                        if ignored else "")
                if generate.secrets_committed(self.s["repo"]):
                    self.problems_dialog("secrets.yaml is already in git", [
                        "Git already tracks config/secrets.yaml, so your WiFi password and keys are in the "
                        "repo's history. Stop tracking it with: git rm --cached config/secrets.yaml, then commit. "
                        "If the repo was ever pushed, generate new keys in WiFi and keys and change your WiFi "
                        "password."])
            if package_on.value and self.s.get("packages"):
                try:
                    generate.write_files(self.s["packages"], {"ring_studio.yaml": package})
                except OSError as err:
                    self.toast(f"Cannot write to the packages folder: {err}")
                    return
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
            ft.Row([ft.Column([text("Send straight to Home Assistant"),
                               caption("Writes one package file into Home Assistant's config, then reloads "
                                       "templates and automations. A network share works.")],
                              spacing=2, expand=True), package_on]),
            ft.Row([field("Home Assistant packages folder", lambda: self.s.get("packages", ""),
                          lambda v: self.save_setting("packages", v), width=460, mono=True,
                          hint_text=r"\\server\config\packages"),
                    ft.Container(button("Choose", choose("packages")), padding=ft.Padding.only(top=18))],
                   spacing=10),
            ft.Column([caption("Home Assistant reads packages only with this in configuration.yaml. "
                               "Add it once, then restart Home Assistant. If there already is a homeassistant: "
                               "section, add only the packages line inside it."),
                       ft.Container(text(PACKAGES_LINE, 12, mono=True, selectable=True), bgcolor=SUNK,
                                     border_radius=10, padding=12)], spacing=6)],
            spacing=20, tight=True, scroll=ft.ScrollMode.AUTO),
            [button("Cancel", self.close), go], 700)

    def keys_dialog(self, _=None):
        sec = self.project.secrets
        generate.secrets_file(self.project)
        self.keep_secrets()
        api_state = text("", 13)
        api_box = box(value=sec.get("api_key", ""), read_only=True, password=True, can_reveal_password=True,
                      width=560, text_style=ft.TextStyle(font_family=MONO))

        def paint():
            ok = generate.valid_api_key(sec.get("api_key", ""))
            api_state.value = "API key is valid" if ok else "API key is missing or invalid. Generate one, then flash over USB."
            api_state.color = OK if ok else WARN

        def regen(key):
            def go():
                sec[key] = generate.gen_secret(key)
                self.vault.set(key, sec[key])
                api_box.value = sec.get("api_key", "")
                api_box.update()
                edited()
                paint()
                api_state.update()
                self.toast(f"New {key.replace('_', ' ')} generated. Flash over USB so the clock gets it.")
            self.confirm("Generate new key",
                         "The clock keeps its old key until you flash it over USB, and Home Assistant will ask "
                         "for the new one. Continue?", "Generate", go)

        paint()
        put = lambda k: (lambda v: (sec.__setitem__(k, v), self.vault.set(k, v)))  # noqa: E731
        self.dialog("WiFi and keys", ft.Column([
            ft.Row([ft.Icon(ft.Icons.LOCK_OUTLINE, size=16, color=SUB),
                    text(f"Stored in {self.vault.where}. Never in project files or the draft.", 12, SUB,
                         expand=True)], spacing=8),
            field("WiFi name", lambda: sec.get("wifi_ssid", ""), put("wifi_ssid"), width=560),
            field("WiFi password", lambda: sec.get("wifi_password", ""), put("wifi_password"), width=560,
                  password=True, can_reveal_password=True),
            field("Fallback hotspot password", lambda: sec.get("ap_password", ""), put("ap_password"), width=560,
                  password=True, can_reveal_password=True),
            caption("The clock opens its own hotspot with this password when it cannot join your WiFi."),
            api_state,
            ft.Column([caption("API key. Home Assistant asks for it as the encryption key when you add the clock."),
                       api_box], spacing=6),
            ft.Row([button("Generate API key", lambda _: regen("api_key")),
                    button("Generate OTA password", lambda _: regen("ota_password"))], spacing=12)],
            spacing=16, tight=True), [button("Done", self.close, primary=True)])

    def firmware_dialog(self, _=None):
        """Flash, update, back up and restore. Each job shows as steps; the raw log is one click away."""
        c, st = self.clock, {"steps": [], "port": None}
        backup = {"path": self.s.get(f"backup_{c.name}") or os.path.join(services.HOME, "backups",
                                                                         f"{c.name}_stock_4MB.bin")}
        log = ft.ListView(height=180, spacing=2, auto_scroll=True)
        log_box = ft.Container(log, bgcolor=SUNK, border_radius=12, padding=12, visible=False)
        rows = ft.Column(spacing=0)
        progress = ft.ProgressBar(value=None, color=ACCENT, bgcolor=SUNK, bar_height=6, border_radius=3)
        steps_box = ft.Container(ft.Column([rows, ft.Container(progress, padding=ft.Padding.only(left=38))],
                                           spacing=6), bgcolor=CARD, border_radius=14, visible=False,
                                 padding=ft.Padding.symmetric(horizontal=14, vertical=10))
        tools = text("", 12, SUB)
        port_dd = ft.Dropdown(width=340, dense=True, filled=True, fill_color=SUNK, border_color=SUNK, text_size=14,
                              focused_border_color=ACCENT, border_radius=10,
                              content_padding=ft.Padding.symmetric(horizontal=14, vertical=10))
        port_hint = text("", 12, SUB)
        backup_name = text("", 13, mono=True)
        backup_state = text("", 12, SUB)
        buttons = []

        def details(_=None, show=None):
            log_box.visible = not log_box.visible if show is None else show
            more.content = "Hide details" if log_box.visible else "Show details"
            more.icon = ft.Icons.EXPAND_LESS if log_box.visible else ft.Icons.CHEVRON_RIGHT
            self.page.update()

        more = ft.TextButton("Show details", icon=ft.Icons.CHEVRON_RIGHT, on_click=details, visible=False,
                             style=ft.ButtonStyle(color=SUB))

        # ---- ports and backup ----
        def fill_ports(_=None):
            ports, saved = services.serial_ports(), self.s.get("port")
            found = ports[0] if ports and services.is_clock_port(ports[0]) else None
            fallback = "COM4" if os.name == "nt" else "/dev/ttyUSB0"
            choice = found if found and saved not in ports else saved or (ports[0] if ports else fallback)
            port_dd.options = [ft.DropdownOption(key=p, text=p) for p in dict.fromkeys(ports + [choice])]
            port_dd.value = st["port"] = choice
            port_hint.value = ("Found the clock's USB chip and picked it for you." if choice == found else
                               "No USB serial port found. Plug the clock in and press refresh." if not ports else "")
            port_hint.color = "#7FD6E0" if choice == found else WARN if not ports else SUB
            if problem := services.port_problem(choice, ports):
                port_hint.value, port_hint.color = problem, WARN
            port_hint.width = 360
            self.page.update()

        def set_port(e):
            st["port"] = e.control.value
            self.save_setting("port", st["port"])

        port_dd.on_select = set_port

        def paint_backup():
            path = backup["path"]
            backup_name.value = os.path.basename(path)
            exists = os.path.exists(path)
            if exists:
                when = datetime.fromtimestamp(os.path.getmtime(path))
                checked = self.s.get(f"verified_{c.name}") == f"{path}|{os.path.getmtime(path)}"
                backup_state.value = (f"Backed up {when:%d %b %H:%M} · {os.path.getsize(path) / 1048576:.1f} MB · "
                                      + ("checked against the clock" if checked else "not checked yet"))
                backup_state.color = "#4CC37A" if checked else SUB
            else:
                backup_state.value, backup_state.color = "No backup yet. Back up before the first USB flash.", WARN
            b_restore.disabled = not exists

        async def change_backup(_):
            if path := await self.picker.save_file(dialog_title="Backup file", file_name=os.path.basename(
                    backup["path"]), file_type=ft.FilePickerFileType.CUSTOM, allowed_extensions=["bin"]):
                backup["path"] = path
                self.save_setting(f"backup_{c.name}", path)
                paint_backup()
                self.page.update()

        # ---- jobs ----
        def paint_steps():
            marks = {"todo": (None, LINE, FAINT), "now": (None, ACCENT, TEXT), "done": (ft.Icons.CHECK, "#4CC37A", TEXT),
                     "fail": (ft.Icons.CLOSE, WARN, WARN)}
            rows.controls = []
            for title, sub, state, took in st["steps"]:
                icon, col, fg = marks[state]
                badge = ft.Container(ft.Icon(icon, size=14, color=ON_ACCENT) if icon else None, width=24, height=24,
                                     border_radius=12, bgcolor=col if icon else None,
                                     border=None if icon else ft.Border.all(2, col), alignment=ft.Alignment.CENTER)
                rows.controls.append(ft.Container(ft.Row([
                    badge, ft.Column([text(title, 14, fg, ft.FontWeight.W_600 if state == "now" else None),
                                      caption(sub)], spacing=2, tight=True, expand=True),
                    text(took or "", 12, SUB)], spacing=14), padding=ft.Padding.symmetric(vertical=8)))

        def out(line):
            log.controls.append(text(line, 12, SUB, mono=True, selectable=True))
            if m := re.search(r"\((\d{1,3}) ?%\)|\b(\d{1,3})%", line):
                progress.value = min(int(m.group(1) or m.group(2)), 100) / 100
            self.page.update()

        def busy(on):
            for b in buttons:
                b.disabled = on
            port_dd.disabled = on
            if not on:
                paint_backup()
            self.page.update()

        def job(*steps):
            st["steps"] = [[title, sub, "todo", None] for title, sub, _ in steps]
            log.controls.clear()
            steps_box.visible = more.visible = True

            def work():
                busy(True)
                for i, (title, _, step) in enumerate(steps):
                    st["steps"][i][2], progress.value, began = "now", None, time.monotonic()
                    paint_steps()
                    out(f"> {title}")
                    try:
                        code = step()
                    except OSError as err:
                        out(str(err))
                        code = 1
                    took = int(time.monotonic() - began)
                    st["steps"][i][2:] = ["fail" if code else "done", f"{took // 60}:{took % 60:02d}" if took >= 60
                                          else f"{took} s"]
                    if code:
                        out(f"Stopped: {title} failed (exit {code}).")
                        if problem := services.port_problem(st["port"] or "", services.serial_ports()):
                            out(problem)
                            port_hint.value, port_hint.color = problem, WARN
                        details(show=True)
                        break
                progress.value = 1 if not code else 0
                services.forget_build_secrets()
                paint_steps()
                paint_tools()
                busy(False)
            self.page.run_thread(work)

        def paint_tools():
            v = services.tool_versions()
            tools.value = (f"ESPHome {v['esphome']} · esptool {v['esptool']}" if all(v.values())
                           else "ESPHome is not installed yet. It installs the first time you flash.")
            tools.color = SUB if all(v.values()) else WARN

        def port():
            return (st["port"] or "").split(" · ")[0]

        def install():
            return ("Install tools", "Already installed" if all(services.tool_versions().values())
                    else "ESPHome and esptool, into this Python",
                    lambda: 0 if all(services.tool_versions().values()) else services.install_tools(out))

        def prepare():
            def step():
                try:
                    projects.check(self.project)
                except projects.ProjectError as err:
                    for problem in err.problems:
                        out(problem)
                    return 1
                generate.write_files(services.BUILD, generate.repo_files(self.project, self.source_name))
                self.keep_secrets()
                out(f"Wrote config to {services.BUILD}")
                return 0
            return "Prepare config", f"{c.name}.yaml and secrets", step

        def esphome(command, title, sub, device=None):
            return title, sub, lambda: services.run(services.esphome(command, f"{c.name}.yaml", device and device()),
                                                    out, cwd=os.path.join(services.BUILD, "config"))

        def esptool(title, sub, args, after=None):
            def step():
                if args == services.RESTORE and not os.path.exists(backup["path"]):
                    out(f"No backup file at {backup['path']}.")
                    return 1
                os.makedirs(os.path.dirname(os.path.abspath(backup["path"])), exist_ok=True)
                code = services.run(services.esptool(port(), *args, backup["path"]), out)
                if os.path.exists(backup["path"]):
                    storage.private(backup["path"])  # the stock firmware holds its old WiFi settings
                if not code and after:
                    after()
                return code
            return title, sub, step

        def checked():
            p = backup["path"]
            storage.private(p)
            self.save_setting(f"verified_{c.name}", f"{p}|{os.path.getmtime(p)}")

        compile_step = esphome("compile", "Compile firmware", "The first build downloads the ESP8266 toolchain")
        b_flash = button("Flash over USB", lambda _: job(install(), prepare(), compile_step, esphome(
            "upload", "Upload over USB", "About 30 seconds", port)), primary=True)
        b_ota = button("Update over the air", lambda _: job(install(), prepare(), compile_step, esphome(
            "upload", "Upload over WiFi", f"To {c.name}.local", lambda: "OTA")))
        b_backup = button("Back up stock", lambda _: job(
            install(), esptool("Read 4 MB from the clock", "About a minute", services.BACKUP),
            esptool("Check the backup", "Compares the file with the clock", services.VERIFY, checked)))
        b_restore = button("Restore stock", lambda _: self.confirm(
            "Restore stock firmware", "This replaces the ESPHome firmware with the backup. Continue?", "Restore",
            lambda: job(install(), esptool("Write the backup to the clock", "About a minute", services.RESTORE))),
            danger=True)
        buttons += [b_backup, b_flash, b_ota, b_restore]

        problems = []
        if not generate.valid_api_key(self.project.secrets.get("api_key", "")):
            problems.append(note("The API key is invalid, so the flash will fail.",
                                 ("Fix in WiFi and keys", lambda _: (self.close(), self.keys_dialog()))))
        if self.project.secrets.get("wifi_ssid", "YOUR_WIFI_NAME") == "YOUR_WIFI_NAME":
            problems.append(note("WiFi is not set, so the clock will only open its fallback hotspot.",
                                 ("Set WiFi", lambda _: (self.close(), self.keys_dialog()))))
        paint_tools()
        paint_backup()
        port_col = ft.Column([caption("Serial port"), ft.Row([port_dd, ft.IconButton(
            ft.Icons.REFRESH, tooltip="Look for ports again", on_click=fill_ports, icon_color=SUB)], spacing=6),
            port_hint], spacing=6, tight=True)
        backup_col = ft.Column([caption("Stock backup"), ft.Container(ft.Row([
            ft.Container(backup_name, expand=True), ft.TextButton("Change", on_click=change_backup,
                                                                   style=ft.ButtonStyle(color=SUB))]),
            bgcolor=SUNK, border_radius=10, width=300, padding=ft.Padding.only(left=14, right=4)), backup_state],
            spacing=6, tight=True)
        self.dialog(f"Flash {c.friendly}", ft.Column(problems + [
            ft.Row([port_col, backup_col], spacing=16, vertical_alignment=ft.CrossAxisAlignment.START),
            caption("The first flash goes over USB. After that, updates go over the air."),
            ft.Row([ft.Row([b_flash, b_ota, b_backup], spacing=10, tight=True), b_restore],
                   alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            steps_box, more, log_box, tools], spacing=16, tight=True),
            [button("Close", self.close)], 760, scrollable=True)
        fill_ports()


def main(page: ft.Page):
    App(page)
