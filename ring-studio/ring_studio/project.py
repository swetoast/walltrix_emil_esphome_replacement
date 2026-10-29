"""The .ringstudio project file: everything about your clocks, including notes, and nothing secret.

It is YAML so it can be read and edited by hand. Loading is strict: the file is read with a safe
loader (it cannot run code), and every value is checked before use, because names, pins and
hardware settings end up inside the ESPHome firmware. A file that fails a check is rejected whole,
with a list of what is wrong. Numbers and colours outside their range are pulled back into range.
"""

import os
import re
import secrets
from dataclasses import asdict

import yaml

from .storage import atomic_write
from .model import COLOUR_BY, LAYOUTS, MARKERS, Clock, migrate_ring, Design, Dimming, Hardware, Project, Ring, from_hex, slug, to_hex

VERSION = 2  # 2: each clock has a library of designs and its own brightness; 1 is still read
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
RING_NAMES = {"layout": "layout", "entity": "entity", "value_attr": "value_attribute", "attrs": "list_attributes",
              "key": "item_key", "t_start": "start_time_key", "t_end": "end_time_key", "entity2": "second_entity",
              "value2_attr": "second_attribute", "scale": "multiply_by", "lo": "low", "hi": "high",
              "colour_by": "colour_by", "marker": "now_marker", "dim": "other_leds",
              "made_from": "made_from"}
MADE_FROM = re.compile(r"(weather\.[a-z0-9_]+ (hourly|daily)|calendar\.[a-z0-9_]+ (hours|week))?")
MAX_PARTS = 12
HW_NAMES = {"board": "board", "pin": "data_pin", "method": "driver", "variant": "led_type", "order": "colour_order",
            "gamma": "gamma", "leds": "leds", "max_brightness": "max_brightness",
            "start_brightness": "start_brightness", "start_led": "led_at_12_oclock", "clockwise": "clockwise"}
DIM_NAMES = {"enabled": "follow_the_sun", "night_start": "off_from_hour", "night_end": "on_at_hour",
             "low": "dimmest", "elev_low": "dimmest_at_sun_angle", "high": "brightest",
             "elev_high": "brightest_at_sun_angle"}
HEADER = "# Ring Studio project. Notes live here and are never exported. Secrets are never stored here.\n"


class _Loader(yaml.SafeLoader):
    """The safe loader, without anchors and aliases: a few lines of aliases can otherwise expand into
    gigabytes (the "billion laughs" file). Ring Studio never writes them."""

    def compose_node(self, parent, index):
        if self.check_event(yaml.AliasEvent):
            raise yaml.YAMLError("anchors and aliases (*name) are not allowed in a project file")
        return super().compose_node(parent, index)


class _Dumper(yaml.SafeDumper):
    def ignore_aliases(self, data):
        return True


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


def check(project: Project, for_export=False):
    """Checks and tidies a project in place. Raises ProjectError listing everything that is wrong.
    `for_export` is for checks that only matter when files are written; there are none at the moment."""
    problems, names, ids = [], set(), set()
    for i, c in enumerate(project.clocks):
        where = f"Clock {i + 1} ({c.friendly or c.name})"
        c.name = slug(c.name)
        if not re.fullmatch(r"[0-9a-f]{4,16}", str(c.id or "")) or c.id in ids:
            c.id = secrets.token_hex(4)  # a new or damaged id: the app's records start fresh for it
        ids.add(c.id)
        c.previous_names = [slug(x) for x in c.previous_names if slug(x) != c.name][:8]
        if c.name in names:
            problems.append(f"{where}: the device name {c.name} is used twice.")
        names.add(c.name)
        c.friendly = clean_label(c.friendly) or c.name
        c.effect = clean_label(c.effect) or "Ring"
        c.note = str(c.note or "")
        problems += [f"{where}: {p}" for p in _hardware(c.hw)]
        problems += [f"{where}: {p}" for p in _dimming(c.dimming)]
        if not c.designs:
            problems.append(f"{where}: it has no design.")
        titles = set()
        for d in c.designs:
            d.name, d.note = clean_label(d.name) or "Design", str(d.note or "")
            if d.name in titles:
                problems.append(f"{where}: the design name {d.name} is used twice.")
            titles.add(d.name)
            problems += [f"{where}, design {d.name}: {p}" for p in _design_ring(d.ring, c.hw)]
        c.active = max(0, min(int(c.active or 0), len(c.designs) - 1))
    project.note = str(project.note or "")
    if problems:
        raise ProjectError(problems)
    return project


def _design_ring(r: Ring, hw: Hardware):
    return _ring(r)


def _dimming(d: Dimming):
    try:
        d.night_start, d.night_end = _num(d.night_start, 0, 24, int), _num(d.night_end, 0, 23, int)
        d.low, d.high = _num(d.low, 0, 255, int), _num(d.high, 0, 255, int)
        d.elev_low, d.elev_high = _num(d.elev_low, -90, 90), _num(d.elev_high, -90, 90)
        d.enabled = bool(d.enabled)
    except ValueError:
        return ["brightness: a number is not a number."]
    if d.elev_high <= d.elev_low:
        return ["brightness: the brightest sun angle must be above the dimmest."]
    return []


def _hardware(hw: Hardware):
    out = []
    hw.pin, hw.board = str(hw.pin).upper(), str(hw.board).lower()
    if not PIN.fullmatch(hw.pin) or int(hw.pin[4:]) > 39:
        out.append(f"data pin {hw.pin!r} is not a pin from GPIO0 to GPIO39.")
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
        hw.start_led = _num(hw.start_led, 0, max(hw.leds - 1, 0), int)
        hw.clockwise = bool(hw.clockwise)
    except ValueError:
        out.append("a hardware number is not a number.")
    return out


def _ring(r: Ring):
    out = []
    if r.layout not in LAYOUTS:
        return [f"layout {r.layout!r} is not one of {', '.join(LAYOUTS)}."]
    for name in ("entity", "entity2"):
        if not isinstance(getattr(r, name) or "", str):
            return [f"{name} should be text."]
        value = getattr(r, name) or ""
        setattr(r, name, value)
        if value and not ENTITY.fullmatch(value):
            out.append(f"entity {value!r} is not like sensor.outdoor_temperature.")
    out += _parts(r)
    r.made_from = r.made_from if isinstance(r.made_from, str) else ""
    if not MADE_FROM.fullmatch(r.made_from):
        out.append(f"made_from {r.made_from!r} should be like 'weather.home hourly' or 'calendar.home week'.")
        r.made_from = ""
    if not isinstance(r.attrs, list) or not all(isinstance(a, str) for a in r.attrs):
        return ["list attributes should be a list of names."]
    for name in ("key", "t_start", "t_end", "entity"):
        if not isinstance(getattr(r, name) or "", str):
            return [f"{name} should be text."]
    for name in ("value_attr", "value2_attr"):
        if not isinstance(getattr(r, name) or "", str):
            return [f"{name} should be text."]
        setattr(r, name, getattr(r, name) or "")
    for name in [*r.attrs, r.key, r.t_start, r.t_end, r.value_attr, r.value2_attr]:
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
    out += _bands(r)
    for name in ("colors", "labels", "state_notes"):
        if not isinstance(getattr(r, name) or {}, dict):
            return out + [f"{name} should be a section."]
    texts = [*(r.labels or {}).items(), *(r.state_notes or {}).items()]
    if not all(isinstance(k, str) and isinstance(v, str) for k, v in texts):
        return out + ["a state, definition or note is not plain text."]
    r.labels = dict(r.labels or {})
    r.state_notes = {k: v for k, v in (r.state_notes or {}).items() if v}
    if not isinstance(r.raw or "", str):
        return out + ["the hand-written template is not text."]
    r.raw = r.raw or ""
    return out


def _parts(r: Ring):
    """Segments: [entity, attribute, name] each, at most MAX_PARTS."""
    if not isinstance(r.parts, list):
        return ["parts should be a list."]
    parts = []
    for p in r.parts:
        p = list(p) if isinstance(p, (list, tuple)) else [p.get("entity"), p.get("attribute"), p.get("name")] \
            if isinstance(p, dict) else None
        if not p or not isinstance(p[0], str) or not ENTITY.fullmatch(p[0]):
            return [f"each part needs an entity like binary_sensor.front_door, not {p and p[0]!r}."]
        attr = str((p + [""])[1] or "")
        if not KEY.fullmatch(attr):
            return [f"data key {attr!r} may only hold letters, digits and _."]
        parts.append([p[0], attr, clean_label((p + ["", ""])[2] or "")])
    if len(parts) > MAX_PARTS:
        return [f"a ring has room for {MAX_PARTS} parts at most."]
    r.parts = parts
    if r.layout == "segments" and not parts:
        return ["segments need at least one part."]
    return []


def _bands(r: Ring):
    """Gradient stop values and steps: numbers, lowest first."""
    out = []
    if r.colour_by not in COLOUR_BY:
        out.append(f"colour_by {r.colour_by!r} is not one of {', '.join(COLOUR_BY)}.")
    try:
        r.stops_at = [float(v) for v in (r.stops_at or [])]
    except (TypeError, ValueError):
        return out + ["a gradient stop value is not a number."]
    if r.stops_at and len(r.stops_at) != len(r.palette):
        out.append("give every gradient colour a value, or none of them.")
    elif r.stops_at != sorted(r.stops_at):
        out.append("gradient stop values should go from low to high.")
    steps = []
    for s in r.steps or []:
        try:
            value, colour, *name = s
            steps.append([float(value), _rgb(colour), clean_label(name[0]) if name and name[0] else ""])
        except (TypeError, ValueError):
            return out + ["each step needs a from value and a colour."]
    if [s[0] for s in steps] != sorted(s[0] for s in steps):
        out.append("steps should go from low to high.")
    r.steps = steps
    if r.colour_by == "steps" and not steps:
        out.append("colouring by steps needs at least one step.")
    return out


# ---------- the file ----------

def _design_out(d: Design):
    r = d.ring
    out = {"name": d.name, "note": d.note}
    out.update({name: getattr(r, k) for k, name in RING_NAMES.items()})
    if not r.made_from:
        out.pop("made_from")
    out["list_attributes"] = list(r.attrs)
    if r.stops_at:
        out["palette"] = [{"at": a, "colour": to_hex(p).upper()} for a, p in zip(r.stops_at, r.palette)]
    else:
        out["palette"] = [to_hex(p).upper() for p in r.palette]
    out["steps"] = [{"from": s[0], "colour": to_hex(s[1]).upper(), "means": s[2]} for s in r.steps]
    out["below_range"] = to_hex(r.below).upper() if r.below else None
    out["unknown_state"] = to_hex(r.fallback).upper()
    out["no_data"] = to_hex(r.missing).upper()
    out["states"] = {k: {"colour": to_hex(v).upper(), "means": r.labels.get(k, ""),
                         "note": r.state_notes.get(k, "")} for k, v in r.colors.items()}
    out["parts"] = [{"entity": p[0], "attribute": p[1], "name": p[2]} for p in r.parts]
    if r.layout == "raw":
        out["raw_template"] = r.raw
    return out


def dump(project: Project, name="Untitled"):
    """The project as .ringstudio text. Colours are written as #RRGGBB so the file reads well."""
    clocks = [{"id": c.id, "name": c.name, "display_name": c.friendly, "effect": c.effect, "note": c.note,
               "hardware": _out(asdict(c.hw), HW_NAMES), "brightness": _out(asdict(c.dimming), DIM_NAMES),
               "shows": c.design.name, "designs": [_design_out(d) for d in c.designs],
               **({"previous_names": c.previous_names} if c.previous_names else {})}
              for c in project.clocks]
    data = {"ring_studio": VERSION, "name": name, "note": project.note}
    data["clocks"] = clocks
    return HEADER + yaml.dump(data, Dumper=_Dumper, sort_keys=False, allow_unicode=True, width=110)


def load(text):
    """Reads .ringstudio text into a checked Project. Raises ProjectError when anything is wrong."""
    if len(text.encode("utf-8")) > MAX_BYTES:
        raise ProjectError(["The file is larger than 1 MB, so it is not a Ring Studio project."])
    try:
        data = yaml.load(text, Loader=_Loader)
    except yaml.YAMLError as err:
        mark = getattr(err, "problem_mark", None)
        where = f"Line {mark.line + 1}: " if mark else ""
        raise ProjectError([f"{where}not valid YAML, {getattr(err, 'problem', None) or err}."]) from None
    if not isinstance(data, dict) or "ring_studio" not in data:
        raise ProjectError(["This is not a Ring Studio project file."])
    if not isinstance(data["ring_studio"], int) or data["ring_studio"] > VERSION:
        raise ProjectError(["This project was made with a newer Ring Studio. Update the app to open it."])
    try:
        old = data["ring_studio"] < 2
        shared = _in(data.get("brightness"), {**DIM_NAMES, "targets": "clocks"}) if old else None
        project = Project(note=str(data.get("note") or ""),
                          clocks=[_clock(c, shared) for c in data.get("clocks") or []])
    except (TypeError, ValueError, AttributeError, KeyError) as err:
        raise ProjectError([f"The file has a value of the wrong kind: {err}"]) from None
    return check(project), str(data.get("name") or "Untitled")


def _only(cls, data):
    if data is None:
        return cls()
    if not isinstance(data, dict):
        raise TypeError(f"{cls.__name__.lower()} should be a section")
    return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


def _design(s, default_name):
    if not isinstance(s, dict):
        raise TypeError("each design should be a section")
    s = dict(s)
    old = migrate_ring({"layout": s.get("layout"), "dial": s.pop("dial", None)})  # names from before v4
    if old.get("layout"):
        s["layout"] = old["layout"]
    if "colour_by" in old:
        s["colour_by"] = old["colour_by"]
    states = s.pop("states", None) or {}
    palette = s.pop("palette", None)
    parts = s.pop("parts", None) or []
    if not isinstance(parts, list):
        raise TypeError("parts should be a list of {entity, attribute, name}")
    steps = s.pop("steps", None) or []
    if not isinstance(steps, list) or not all(isinstance(x, dict) for x in steps):
        raise TypeError("steps should be a list of {from, colour, means}")
    if not isinstance(states, dict):
        raise TypeError("states should be a section")
    ring = _only(Ring, _in({k: v for k, v in s.items() if k in RING_NAMES.values() or k == "below_range"},
                           {**RING_NAMES, "below": "below_range"}))
    if palette is not None:
        if not isinstance(palette, list):
            raise TypeError("palette should be a list")
        if palette and all(isinstance(p, dict) for p in palette):
            ring.stops_at = [p.get("at") for p in palette]
            ring.palette = [p.get("colour", "#000000") for p in palette]
        else:
            ring.palette = palette
    ring.steps = [[x.get("from"), x.get("colour", "#000000"), str(x.get("means") or "")] for x in steps]
    ring.parts = parts
    ring.fallback = s.get("unknown_state", ring.fallback)
    ring.missing = s.get("no_data", ring.missing)
    ring.raw = str(s.get("raw_template") or "")
    ring.colors = {str(k): (v or {}).get("colour", "#000000") for k, v in states.items()}
    ring.labels = {str(k): str((v or {}).get("means") or "") for k, v in states.items() if (v or {}).get("means")}
    ring.state_notes = {str(k): str((v or {}).get("note") or "") for k, v in states.items() if (v or {}).get("note")}
    return Design(str(s.get("name") or default_name), str(s.get("note") or ""), ring)


def _clock(c, shared=None):
    """One clock. `shared` is the project-wide brightness of a version 1 file, which had one design per clock."""
    if not isinstance(c, dict):
        raise TypeError("each clock should be a section")
    name = str(c.get("name") or "clock")
    friendly = str(c.get("display_name") or name)
    if shared is not None:
        designs, active = [_design(c.get("shows") or {}, friendly)], 0
        hardware = dict(c.get("hardware") or {})
        for k in ("led_at_12_oclock", "clockwise"):  # the ring's orientation moved to the hardware
            if k in (c.get("shows") or {}):
                hardware[k] = c["shows"][k]
        c = {**c, "hardware": hardware}
        dimming = _only(Dimming, {k: v for k, v in shared.items() if k != "targets"})
        dimming.enabled = bool(shared.get("enabled", True)) and name in (shared.get("targets") or [])
    else:
        raw = c.get("designs") or []
        if not isinstance(raw, list):
            raise TypeError("designs should be a list")
        designs = [_design(d, f"Design {i + 1}") for i, d in enumerate(raw)]
        shows = str(c.get("shows") or "")
        active = next((i for i, d in enumerate(designs) if d.name == shows), 0)
        dimming = _only(Dimming, _in(c.get("brightness"), DIM_NAMES))
    return Clock(id=str(c.get("id") or ""), previous_names=[slug(x) for x in c.get("previous_names") or []],
                 name=name, friendly=friendly, effect=str(c.get("effect") or "Ring"), note=str(c.get("note") or ""),
                 hw=_only(Hardware, _in(c.get("hardware"), HW_NAMES)), designs=designs or [Design()],
                 active=active, dimming=dimming)


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


EXAMPLES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "examples")
FIRST_EXAMPLE = "Example Clock"


def examples():
    """The example projects that ship with the app, as (name, path, first line of the note)."""
    out = []
    for f in sorted(os.listdir(EXAMPLES)) if os.path.isdir(EXAMPLES) else []:
        if f.endswith(SUFFIX):
            path = os.path.join(EXAMPLES, f)
            try:
                note = open_file(path).note
            except (OSError, ProjectError):
                continue
            out.append((f[:-len(SUFFIX)], path, note))
    first = [e for e in out if e[0] == FIRST_EXAMPLE]
    return first + [e for e in out if e[0] != FIRST_EXAMPLE]


def name_of(path):
    return os.path.splitext(os.path.basename(path))[0] if path else "Untitled"


# ---------- the YAML view ----------

FIELDS = [
    ("name", "the clock's device name: lower case, digits and _"),
    ("display_name", "the name Home Assistant shows"),
    ("effect", "the name of the light effect on the clock"),
    ("note", "your own notes, never exported"),
    ("shows", "the name of the design the clock shows"),
    ("designs[].name", "the design's name, unique on its clock"),
    ("designs[].note", "your own notes about the design"),
    ("hardware.data_pin", "the pin the LEDs are on, GPIO0 to GPIO39"),
    ("hardware.driver", ", ".join(METHODS)),
    ("hardware.led_type", ", ".join(VARIANTS)),
    ("hardware.colour_order", ", ".join(ORDERS)),
    ("hardware.leds", f"how many LEDs, 1 to {MAX_LEDS}"),
    ("hardware.gamma", "colour correction, 0.1 to 3, 1 = none"),
    ("hardware.max_brightness", "the brightest the clock may go, 1 to 255"),
    ("designs[].layout", ", ".join(LAYOUTS)),
    ("designs[].entity", "the Home Assistant entity, like sensor.outdoor_temperature"),
    ("designs[].value_attribute", "one value: read this attribute instead of the state; compass: the direction"),
    ("designs[].list_attributes", "from_now, dial_24h, week: the attributes holding the lists, read in order"),
    ("designs[].item_key", "from_now, dial_24h, week: the key in each item that colours its LED"),
    ("designs[].second_entity", "compass: the entity whose value colours the LED, such as a distance"),
    ("designs[].second_attribute", "compass: the attribute of the second entity; empty for its state"),
    ("designs[].made_from", "the entity is a sensor Ring Studio's package makes, like 'weather.home daily'"),
    ("designs[].parts", "segments: list of {entity, attribute, name}, at most 12"),
    ("designs[].start_time_key", "the key with each item's start time; empty when the first item is now"),
    ("designs[].end_time_key", "the key with each item's end time"),
    ("designs[].multiply_by", "multiplies every value first, for example 100 for SEK to öre"),
    ("designs[].low", "gradient start when no stop has a value; fill: empty at"),
    ("designs[].high", "gradient end when no stop has a value; fill: full at"),
    ("designs[].colour_by", "gradient or steps for numbers, values for text"),
    ("designs[].palette", "gradient colours: '#RRGGBB', or {at: value, colour: '#RRGGBB'} on every colour"),
    ("designs[].steps", "list of {from: value, colour: '#RRGGBB', means: name}, lowest first"),
    ("designs[].states", "text values: value: {colour: '#RRGGBB', means: name, note: your note}"),
    ("designs[].below_range", "colour under the first gradient colour or step; null for none"),
    ("designs[].unknown_state", "colour for a text value without a colour"),
    ("designs[].no_data", "colour for LEDs without data; the face colour for hands"),
    ("designs[].now_marker", "bright, white or none"),
    ("designs[].other_leds", "brightness of the LEDs after now, 0 to 1; hands: the quarter marks"),
    ("hardware.led_at_12_oclock", "the LED at the top of the ring"),
    ("hardware.clockwise", "true or false: the direction the LEDs run"),
    ("designs[].raw_template", "raw layout: the Jinja template, used as it is"),
    ("brightness.follow_the_sun", "true or false: the clock dims itself from sun.sun's elevation"),
    ("brightness.off_from_hour", "the hour the ring turns off, 24 = never"),
    ("brightness.on_at_hour", "the hour it comes back on"),
    ("brightness.dimmest", "brightness with the sun low, 0 to 255"),
    ("brightness.brightest", "brightness with the sun high, 0 to 255"),
    ]
WORDS = sorted({k.split(".")[-1] for k, _ in FIELDS} | {"ring_studio", "clocks", "hardware", "shows", "brightness", "designs",
                                                         "at", "colour", "from", "means", "gradient", "steps", "24h",
                                                         "bright", "white", "none", "true", "false", "null", "board",
                                                         "start_brightness", "dimmest_at_sun_angle",
                                                         "brightest_at_sun_angle", "values", *LAYOUTS, *METHODS, *VARIANTS,
                                                         *ORDERS})


def locate(text, problem):
    """The line (from 0) a problem is about: a "Line n" prefix, a quoted value, or the clock it names."""
    lines = text.splitlines()
    m = re.match(r"Line (\d+)", problem)
    if m:
        return int(m.group(1)) - 1
    start = 0
    m = re.match(r"Clock (\d+) ", problem)
    if m:
        items = [i for i, line in enumerate(lines) if re.match(r"^\s*- name:", line)]
        if int(m.group(1)) <= len(items):
            start = items[int(m.group(1)) - 1]
    for value in re.findall(r"'([^']+)'", problem):
        for i in range(start, len(lines)):
            if value in lines[i]:
                return i
    return start


def read(text):
    """The YAML view: (project, []) when the text is a good project, else (None, [(line, problem), ...])."""
    try:
        return load(text)[0], []
    except ProjectError as err:
        return None, [(locate(text, p), re.sub(r"^Line \d+: ", "", p)) for p in err.problems]
