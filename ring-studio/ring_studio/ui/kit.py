"""Colours, sizes and the small building blocks every screen uses.

Design rules used throughout: greys plus one accent, raised surfaces lighter with a soft shadow, inputs sunk
and darker, hierarchy by weight and colour, generous spacing, and at most two levels of disclosure (a section,
then "More" inside it). Every input goes through `field`.
"""

import difflib
import hashlib
import math
from dataclasses import asdict
from datetime import datetime

import flet as ft
import flet_code_editor as fce

from .. import generate
from ..model import Hardware, from_hex, to_hex

BG, BAR, CARD, SUNK, RAISED, LINE = "#101318", "#151920", "#181C22", "#0E1115", "#1F252D", "#2A313B"
TEXT, SUB, FAINT = "#E8ECF0", "#9AA5B1", "#6F7A86"
ACCENT, ACCENT_BG, ON_ACCENT = "#3DB8C8", "#17303A", "#0B1216"
WARN, WARN_BG, OK, GREEN = "#F0D79A", "#2A2312", "#A9E4BF", "#4CC37A"
FACE = "#2C333C"  # an unlit LED on screen
MONO = "monospace"
PRESETS = ["#FFFFFF", "#FFD700", "#FFA500", "#FF4500", "#FF0040", "#FF1493", "#FF00FF", "#B000FF",
           "#8000FF", "#4B0082", "#4000FF", "#0000CD", "#0040FF", "#1E90FF", "#00BFFF", "#40E0D0",
           "#008B8B", "#00C853", "#7CFC00", "#C8E1FF", "#BEBECD", "#708090", "#0F2043", "#000000"]
# The layout names on screen are the ones in the project file (designs[].layout), with a short line each.
LAYOUT_NAMES = {"from_now": ("From now", "One LED per item, starting at now"),
                "dial_24h": ("24-hour dial", "Midnight at the top, every hour in place"),
                "week": ("Week", "Seven sections, today at the top"),
                "fill": ("Fill", "The value fills the ring like a gauge"),
                "whole_ring": ("Whole ring", "Every LED in the value's colour"),
                "compass": ("Compass", "One LED at a direction"),
                "countdown": ("Countdown", "One LED per minute left"),
                "segments": ("Segments", "Up to 12 parts, one entity each"),
                "hands": ("Hands", "An analog clock, colours through the day"),
                "day_arc": ("Day arc", "24 hours: day lit, night dim, sunrise and sunset marked"),
                "raw": ("Hand-written", "A template kept as it is")}
HW_NAME, HW_PRESET = "EnergiKlockan EMIL", Hardware()
HW_KEYS = ("board", "pin", "method", "variant", "order", "gamma", "leds")
FADE = ft.ButtonStyle(color={ft.ControlState.DISABLED: "#3A424D", ft.ControlState.DEFAULT: SUB})
PACKAGES_LINE = "homeassistant:\n  packages: !include_dir_named packages"
DOMAIN_ICONS = {"sensor": ft.Icons.SENSORS, "weather": ft.Icons.WB_SUNNY_OUTLINED, "calendar": ft.Icons.CALENDAR_MONTH,
                "binary_sensor": ft.Icons.TOGGLE_ON_OUTLINED, "number": ft.Icons.PIN, "input_number": ft.Icons.PIN,
                "select": ft.Icons.LIST, "input_select": ft.Icons.LIST, "sun": ft.Icons.WB_TWILIGHT,
                "person": ft.Icons.PERSON_OUTLINE, "light": ft.Icons.LIGHTBULB_OUTLINE, "climate": ft.Icons.THERMOSTAT,
                "timer": ft.Icons.TIMER_OUTLINED, "plant": ft.Icons.LOCAL_FLORIST_OUTLINED}
MARKERS = {"bright": "Now bright", "white": "Now white", "none": "No marker"}
LIFT = [ft.BoxShadow(blur_radius=2, offset=ft.Offset(0, 1), color=ft.Colors.with_opacity(0.5, "#000000")),
        ft.BoxShadow(blur_radius=24, offset=ft.Offset(0, 10), color=ft.Colors.with_opacity(0.25, "#000000"))]
TOP_EDGE = ft.Border.only(top=ft.BorderSide(1, ft.Colors.with_opacity(0.06, "#FFFFFF")))
CODE_THEME = fce.CustomCodeTheme(
    root=ft.TextStyle(color=TEXT, bgcolor="#0B0E12"), attr=ft.TextStyle(color="#7FD6E0"),
    string=ft.TextStyle(color="#C9D1D9"), number=ft.TextStyle(color="#E9C46A"), literal=ft.TextStyle(color="#E9C46A"),
    comment=ft.TextStyle(color=FAINT, italic=True), bullet=ft.TextStyle(color=SUB), meta=ft.TextStyle(color=SUB),
    keyword=ft.TextStyle(color="#E9C46A"))
HOOKS = []  # called after every edit: autosave and live preview


def now():
    return datetime.now().astimezone()


def edited():
    for hook in HOOKS:
        hook()


def text(value, size=14, color=TEXT, weight=None, mono=False, **kw):
    return ft.Text(value, size=size, color=color, weight=weight, font_family=MONO if mono else None, **kw)


def caption(value):
    return text(value, 12, FAINT)


def box(control=None, **kw):
    """A sunk input surface."""
    kw.setdefault("text_size", 14)
    kw.setdefault("content_padding", ft.Padding.symmetric(horizontal=14, vertical=18))
    return ft.TextField(filled=True, fill_color=SUNK, border_color=SUNK, focused_border_color=ACCENT,
                        border_radius=10, dense=True, cursor_color=ACCENT, hint_style=ft.TextStyle(color=FAINT), **kw)


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
    return ft.Column([caption(title), dd], spacing=6, tight=True) if title else dd


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


def link(label, on_click, color=ACCENT, icon=None):
    return ft.TextButton(label, icon=icon, on_click=on_click, style=ft.ButtonStyle(color=color))


def dot(color, size=28, on_click=None, tooltip=None):
    return ft.Container(width=size, height=size, border_radius=size / 2, bgcolor=color or "#000000",
                        border=ft.Border.all(2, LINE), on_click=on_click, tooltip=tooltip)


def status_dot(color, size=8):
    return ft.Container(width=size, height=size, border_radius=size / 2, bgcolor=color)


def card(content, padding=0, bgcolor=CARD):
    return ft.Container(content, bgcolor=bgcolor, border_radius=16, border=TOP_EDGE, shadow=LIFT, padding=padding)


def note(value, fix=None):
    """A warning line, optionally with a one-click fix."""
    items = [ft.Container(text(value, 13, WARN), expand=True)]
    if fix:
        items.append(ft.TextButton(fix[0], on_click=fix[1], style=ft.ButtonStyle(color=WARN)))
    return ft.Container(ft.Row(items, spacing=12), bgcolor=WARN_BG, border_radius=10,
                        padding=ft.Padding.symmetric(horizontal=14, vertical=8))


def info(value, icon=ft.Icons.INFO_OUTLINE, action=None):
    """A calm hint line in the accent colour, optionally with an action."""
    items = [ft.Icon(icon, size=16, color=ACCENT), ft.Container(text(value, 13), expand=True)]
    if action:
        items.append(link(*action))
    return ft.Container(ft.Row(items, spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                        bgcolor=ACCENT_BG, border_radius=10, padding=ft.Padding.symmetric(horizontal=14, vertical=8))


def segmented(options, value, choose):
    """A row of options, one picked. `choose(key)` runs on a click."""
    return ft.Container(ft.Row([ft.Container(text(v, 13, TEXT if k == value else SUB),
                                             bgcolor=RAISED if k == value else None, border_radius=8, ink=True,
                                             padding=ft.Padding.symmetric(horizontal=14, vertical=10),
                                             on_click=lambda _, k=k: choose(k)) for k, v in options.items()],
                               spacing=2, tight=True, wrap=True), bgcolor=SUNK, border_radius=10, padding=3)


def tile(title, sub, on, on_click, width=230):
    return ft.Container(ft.Column([text(title, 14, TEXT if on else SUB, ft.FontWeight.W_600), text(sub, 12, FAINT)],
                                  spacing=4, tight=True),
                        width=width, padding=ft.Padding.symmetric(horizontal=14, vertical=12), border_radius=12,
                        bgcolor=ACCENT_BG if on else RAISED, border=ft.Border.all(1, ACCENT if on else RAISED),
                        ink=True, on_click=on_click)


def ring_view(colors, size=300, tips=None, centre=None, first_big=True):
    """The clock face. `tips[i]` is what LED i shows, as its tooltip."""
    c, r, dots = size / 2, size / 2 - size * 0.08, []
    if centre:
        dots.append(ft.Container(ft.Column([text(centre[0], size * 0.087, "#2A3038", ft.FontWeight.W_700),
                                            text(centre[1], 12, "#6A717A")], spacing=2, tight=True,
                                           horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                                 left=0, right=0, top=c - 30, alignment=ft.Alignment.CENTER))
    big, small = size * 0.053, size * 0.04
    for i, col in enumerate(colors):
        col = FACE if col.lower() == "#000000" else col  # an LED that is off looks unlit
        t, s = i / len(colors) * 2 * math.pi, big if i == 0 and first_big else small
        hit = max(s + 6, 14)
        tip = tips[i] if tips and i < len(tips) else None
        dots.append(ft.Container(
            ft.Container(width=s, height=s, border_radius=s / 2, bgcolor=col,
                         shadow=ft.BoxShadow(blur_radius=s - 4, color=col) if col != FACE else None),
            left=c + r * math.sin(t) - hit / 2, top=c - r * math.cos(t) - hit / 2, width=hit, height=hit,
            alignment=ft.Alignment.CENTER, tooltip=f"LED {i + 1} · {tip}" if tip else None))
    return ft.Container(ft.Stack(dots, width=size, height=size), width=size, height=size, bgcolor="#F1EFEA",
                        border_radius=size / 2,
                        shadow=ft.BoxShadow(blur_radius=size * 0.12, offset=ft.Offset(0, size * 0.045),
                                            color=ft.Colors.with_opacity(0.45, "#000000")))


def state_of(project):
    """The project as plain data, without secrets: what the draft, undo and "unsaved" compare."""
    if isinstance(project, dict):
        return project
    data = asdict(project)
    data.pop("secrets", None)
    return data


def percent_slider(obj, name, top):
    """A 0 to `top` percent slider for a 0 to 1 setting. The value is clamped into range, so a setting carried
    over from another layout can never be out of the slider's bounds."""
    value = max(0.0, min(float(getattr(obj, name) or 0) * 100, top))
    return ft.Slider(min=0, max=top, divisions=top // 5, value=value, width=180, active_color=ACCENT,
                     label="{value}%", on_change_end=lambda e: (setattr(obj, name, round(e.control.value / 100, 2)),
                                                                 edited()))


def num(v):
    """A number as people write it: 12.5, -11.67, 100."""
    return f"{round(float(v), 2):g}"


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


def when(t):
    """A file time as people say it: today 08:02, yesterday, 12 Oct."""
    days = (now().date() - t.date()).days
    return f"today {t:%H:%M}" if days == 0 else "yesterday" if days == 1 else f"{t:%d %b}"


def day_name(t):
    days = (t.date() - now().date()).days
    return {0: "Today", 1: "Tomorrow"}.get(days, f"{t:%a}")


def template_hash(clock):
    """Identifies what Home Assistant renders for a clock, to tell whether the clock shows the latest edits."""
    return hashlib.sha256(generate.jinja(clock).encode()).hexdigest()[:16]


def firmware_hash(clock):
    """Identifies the firmware the app would build for a clock now, to tell whether it needs an update."""
    return hashlib.sha256(generate.firmware_file(clock, "").encode()).hexdigest()[:16]


def ring_color(r):
    """One colour that stands for a design, for the dots in the sidebar."""
    if r.layout in ("hands", "day_arc"):
        return to_hex(r.palette[len(r.palette) // 2]) if r.layout == "hands" and r.palette else "#FFC35E"
    if r.colour_by == "values" and r.colors:
        return to_hex(next(iter(r.colors.values())))
    if r.colour_by == "steps" and r.steps:
        return to_hex(r.steps[-1][1])
    return to_hex(r.palette[len(r.palette) // 2]) if r.palette else ACCENT
