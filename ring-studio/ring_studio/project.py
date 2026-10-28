"""The .ringstudio project file: everything about your clocks, including notes, and nothing secret.

It is YAML so it can be read and edited by hand. Loading is strict: the file is read with a safe
loader (it cannot run code), and every value is checked before use, because names, pins and
hardware settings end up inside the ESPHome firmware. A file that fails a check is rejected whole,
with a list of what is wrong. Numbers and colours outside their range are pulled back into range.
"""

import os
import re
from dataclasses import asdict

import yaml

from .storage import atomic_write
from .model import MARKERS, MODES, Clock, Dimming, Hardware, Project, Ring, from_hex, slug, to_hex

VERSION = 1
SUFFIX = ".ringstudio"
MAX_BYTES = 1_000_000
MAX_LEDS = 42  # Home Assistant caps a state at 255 characters, 6 per LED

METHODS = ("bit_bang", "esp8266_uart", "esp8266_dma", "esp32_rmt", "esp32_i2s")
VARIANTS = ("WS2812", "WS2812X", "WS2811", "WS2813", "SK6812", "APA106", "800KBPS", "400KBPS")
ORDERS = ("GRB", "RGB", "BRG", "RBG", "GBR", "BGR", "GRBW", "RGBW")

PIN = re.compile(r"GPIO\d{1,2}")
BOARD = re.compile(r"[a-z0-9_\-]{2,40}")
ENTITY = re.compile(r"[a-z_]+\.[a-z0-9_]+")
KEY = re.compile(r"\w{0,64}")
LABEL = re.compile(r"[\w \-.,'()&+/]{1,40}")
# Field names in the file are written for people; the model uses short ones.
RING_NAMES = {"mode": "layout", "entity": "entity", "attrs": "list_attributes", "key": "item_key",
              "t_start": "start_time_key", "t_end": "end_time_key", "scale": "multiply_by", "lo": "low",
              "hi": "high", "marker": "now_marker", "dim": "other_leds", "start_led": "led_at_12_oclock",
              "clockwise": "clockwise"}
HW_NAMES = {"board": "board", "pin": "data_pin", "method": "driver", "variant": "led_type", "order": "colour_order",
            "gamma": "gamma", "leds": "leds", "max_brightness": "max_brightness",
            "start_brightness": "start_brightness"}
DIM_NAMES = {"enabled": "follow_the_sun", "night_start": "off_from_hour", "night_end": "on_at_hour",
             "low": "dimmest", "elev_low": "dimmest_at_sun_angle", "high": "brightest",
             "elev_high": "brightest_at_sun_angle", "targets": "clocks"}
HEADER = "# Ring Studio project. Notes live here and are never exported. Secrets are never stored here.\n"


class ProjectError(ValueError):
    """The file was rejected. `problems` lists every reason, in plain words."""

    def __init__(self, problems):
        super().__init__("\n".join(problems))
        self.problems = problems


# ---------- checking ----------

def _num(value, lo, hi, kind=float):
    try:
        return max(lo, min(hi, kind(value)))
    except (TypeError, ValueError):
        raise ValueError from None


def _rgb(value):
    """A colour as [r, g, b]. Accepts "#RRGGBB" or a list of three numbers."""
    if isinstance(value, str):
        return from_hex(value)
    if isinstance(value, (list, tuple)) and len(value) == 3:
        return [_num(v, 0, 255, int) for v in value]
    raise ValueError


def clean_label(text):
    """Display and effect names: no quotes, backslashes, line breaks or other characters that could
    break out of the YAML they are written into."""
    out = "".join(ch for ch in str(text) if LABEL.fullmatch(ch)).strip()[:40]
    return out


def check(project: Project):
    """Checks and tidies a project in place. Raises ProjectError listing everything that is wrong."""
    problems, names = [], set()
    for i, c in enumerate(project.clocks):
        where = f"Clock {i + 1} ({c.friendly or c.name})"
        c.name = slug(c.name)
        if c.name in names:
            problems.append(f"{where}: the device name {c.name} is used twice.")
        names.add(c.name)
        c.friendly = clean_label(c.friendly) or c.name
        c.effect = clean_label(c.effect) or "Ring"
        c.note = str(c.note or "")
        problems += [f"{where}: {p}" for p in _hardware(c.hw)]
        problems += [f"{where}: {p}" for p in _ring(c.ring)]
        try:
            c.ring.start_led = _num(c.ring.start_led, 0, max(c.hw.leds - 1, 0), int)
        except ValueError:
            problems.append(f"{where}: the LED at 12 o'clock is not a number.")
        c.ring.clockwise = bool(c.ring.clockwise)
    d = project.dimming
    try:
        d.night_start, d.night_end = _num(d.night_start, 0, 24, int), _num(d.night_end, 0, 23, int)
        d.low, d.high = _num(d.low, 0, 255, int), _num(d.high, 0, 255, int)
        d.elev_low, d.elev_high = _num(d.elev_low, -90, 90), _num(d.elev_high, -90, 90)
        d.enabled = bool(d.enabled)
    except ValueError:
        problems.append("Brightness: a number is not a number.")
    if d.elev_high <= d.elev_low:
        problems.append("Brightness: the brightest sun angle must be above the dimmest.")
    d.targets = [slug(t) for t in d.targets if slug(t) in names]
    project.note = str(project.note or "")
    if problems:
        raise ProjectError(problems)
    return project


def _hardware(hw: Hardware):
    out = []
    hw.pin, hw.board = str(hw.pin).upper(), str(hw.board).lower()
    if not PIN.fullmatch(hw.pin):
        out.append(f"data pin {hw.pin!r} is not like GPIO12.")
    if not BOARD.fullmatch(hw.board):
        out.append(f"board {hw.board!r} is not a board name.")
    for name, value, allowed in (("driver", hw.method, METHODS), ("LED type", hw.variant, VARIANTS),
                                 ("colour order", hw.order, ORDERS)):
        if value not in allowed:
            out.append(f"{name} {value!r} is not one of {', '.join(allowed)}.")
    try:
        hw.leds = _num(hw.leds, 1, MAX_LEDS, int)
        hw.gamma = _num(hw.gamma, 0.1, 3.0)
        hw.max_brightness = _num(hw.max_brightness, 1, 255, int)
        hw.start_brightness = _num(hw.start_brightness, 0, hw.max_brightness, int)
    except ValueError:
        out.append("a hardware number is not a number.")
    return out


def _ring(r: Ring):
    out = []
    if r.mode not in MODES:
        return [f"layout {r.mode!r} is not one of {', '.join(MODES)}."]
    if r.entity and not ENTITY.fullmatch(str(r.entity)):
        out.append(f"entity {r.entity!r} is not like sensor.outdoor_temperature.")
    r.attrs = [str(a) for a in (r.attrs or [])]
    for name in [*r.attrs, r.key, r.t_start, r.t_end]:
        if not KEY.fullmatch(str(name or "")):
            out.append(f"data key {name!r} may only hold letters, digits and _.")
    if r.marker not in MARKERS:
        r.marker = "bright"
    try:
        r.scale, r.lo, r.hi = float(r.scale), float(r.lo), float(r.hi)
        r.dim = _num(r.dim, 0, 1)
        r.palette = [_rgb(p) for p in r.palette]
        r.below = None if r.below is None else _rgb(r.below)
        r.fallback, r.missing = _rgb(r.fallback), _rgb(r.missing)
        r.colors = {str(k): _rgb(v) for k, v in (r.colors or {}).items()}
    except (ValueError, TypeError):
        out.append("a colour is not #RRGGBB.")
    if r.hi == r.lo:
        out.append("the low end and the high end are the same number.")
    if len(r.palette) < 2:
        out.append("a gradient needs at least two colours.")
    r.labels = {str(k): str(v) for k, v in (r.labels or {}).items()}
    r.state_notes = {str(k): str(v) for k, v in (r.state_notes or {}).items() if v}
    r.raw = str(r.raw or "")
    return out


# ---------- the file ----------

def dump(project: Project, name="Untitled"):
    """The project as .ringstudio text. Colours are written as #RRGGBB so the file reads well."""
    clocks = []
    for c in project.clocks:
        r = asdict(c.ring)
        shows = {name: r[k] for k, name in RING_NAMES.items()}
        shows["palette"] = [to_hex(p).upper() for p in c.ring.palette]
        shows["below_range"] = to_hex(c.ring.below).upper() if c.ring.below else None
        shows["unknown_state"] = to_hex(c.ring.fallback).upper()
        shows["no_data"] = to_hex(c.ring.missing).upper()
        shows["states"] = {k: {"colour": to_hex(v).upper(), "means": c.ring.labels.get(k, ""),
                               "note": c.ring.state_notes.get(k, "")} for k, v in c.ring.colors.items()}
        if c.ring.mode == "raw":
            shows["raw_template"] = c.ring.raw
        clocks.append({"name": c.name, "display_name": c.friendly, "effect": c.effect, "note": c.note,
                       "hardware": _out(asdict(c.hw), HW_NAMES), "shows": shows})
    data = {"ring_studio": VERSION, "name": name, "note": project.note,
            "brightness": _out(asdict(project.dimming), DIM_NAMES), "clocks": clocks}
    return HEADER + yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=110)


def load(text):
    """Reads .ringstudio text into a checked Project. Raises ProjectError when anything is wrong."""
    if len(text.encode("utf-8")) > MAX_BYTES:
        raise ProjectError(["The file is larger than 1 MB, so it is not a Ring Studio project."])
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as err:
        raise ProjectError([f"The file is not valid YAML: {err}"]) from None
    if not isinstance(data, dict) or "ring_studio" not in data:
        raise ProjectError(["This is not a Ring Studio project file."])
    if not isinstance(data["ring_studio"], int) or data["ring_studio"] > VERSION:
        raise ProjectError(["This project was made with a newer Ring Studio. Update the app to open it."])
    try:
        project = Project(note=str(data.get("note") or ""),
                          dimming=_only(Dimming, _in(data.get("brightness"), DIM_NAMES)),
                          clocks=[_clock(c) for c in data.get("clocks") or []])
    except (TypeError, ValueError, AttributeError, KeyError) as err:
        raise ProjectError([f"The file has a value of the wrong kind: {err}"]) from None
    return check(project), str(data.get("name") or "Untitled")


def _only(cls, data):
    if data is None:
        return cls()
    if not isinstance(data, dict):
        raise TypeError(f"{cls.__name__.lower()} should be a section")
    return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


def _clock(c):
    if not isinstance(c, dict):
        raise TypeError("each clock should be a section")
    s = dict(c.get("shows") or {})
    states = s.pop("states", None) or {}
    if not isinstance(states, dict):
        raise TypeError("states should be a section")
    ring = _only(Ring, _in({k: v for k, v in s.items() if k in RING_NAMES.values() or k in ("palette", "below_range")},
                           {**RING_NAMES, "palette": "palette", "below": "below_range"}))
    ring.fallback = s.get("unknown_state", ring.fallback)
    ring.missing = s.get("no_data", ring.missing)
    ring.raw = str(s.get("raw_template") or "")
    ring.colors = {str(k): (v or {}).get("colour", "#000000") for k, v in states.items()}
    ring.labels = {str(k): str((v or {}).get("means") or "") for k, v in states.items() if (v or {}).get("means")}
    ring.state_notes = {str(k): str((v or {}).get("note") or "") for k, v in states.items() if (v or {}).get("note")}
    return Clock(name=str(c.get("name") or "clock"), friendly=str(c.get("display_name") or c.get("name") or ""),
                 effect=str(c.get("effect") or "Ring"), note=str(c.get("note") or ""),
                 hw=_only(Hardware, _in(c.get("hardware"), HW_NAMES)), ring=ring)


def _out(data, names):
    return {names[k]: v for k, v in data.items() if k in names}


def _in(data, names):
    if data is None:
        return None
    if not isinstance(data, dict):
        raise TypeError("expected a section")
    back = {v: k for k, v in names.items()}
    return {back[k]: v for k, v in data.items() if k in back}


def save(path, project: Project):
    """Saves safely: a temporary file is swapped in only once fully written, and the previous version is
    kept as <file>.bak."""
    if not path.endswith(SUFFIX):
        path += SUFFIX
    atomic_write(path, dump(project, name_of(path)), backup=True)
    return path


def open_file(path):
    if os.path.getsize(path) > MAX_BYTES:
        raise ProjectError(["The file is larger than 1 MB, so it is not a Ring Studio project."])
    with open(path, encoding="utf-8") as fh:
        project, _ = load(fh.read())
    return project


def name_of(path):
    return os.path.splitext(os.path.basename(path))[0] if path else "Untitled"
