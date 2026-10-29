"""Data model. One Clock is one ESP device plus the Home Assistant template that colours it."""

import re
import secrets
import unicodedata
from dataclasses import InitVar, dataclass, field, replace

PALETTE = [[0, 191, 255], [0, 112, 255], [0, 64, 255], [64, 0, 255], [128, 0, 255],
           [176, 0, 255], [255, 0, 255], [255, 0, 128], [255, 0, 64]]

# Layouts: where the colours go on the ring. The names are the ones the screen uses.
LAYOUTS = {
    "from_now": "From now: one LED per list item, starting at now",
    "dial_24h": "24-hour dial: every hour in its place, midnight at the top",
    "week": "Week: seven sections, today at the top",
    "fill": "Fill: one value fills the ring",
    "whole_ring": "Whole ring: every LED in one value's colour",
    "compass": "Compass: one LED at a direction",
    "countdown": "Countdown: one LED per minute left",
    "segments": "Segments: up to 12 parts, one entity each",
    "hands": "Hands: an analog clock, colours through the day",
    "day_arc": "Day and night: a 24-hour face, day lit, night dim",
    "raw": "Hand-written: a template kept as it is",
}
MODES = LAYOUTS  # the name older code and files use
LIST_LAYOUTS = ("from_now", "dial_24h", "week")  # read a list of items with times
NUMBER_LAYOUTS = ("from_now", "dial_24h", "week", "fill", "whole_ring", "compass", "countdown", "segments")
COLOUR_BY = ("gradient", "steps", "values")  # numbers smoothly, numbers in bands, or one colour per text value
OLD_LAYOUTS = {"timeline": ("from_now", None), "states": ("from_now", "values"), "gauge": ("fill", None),
               "solid": ("whole_ring", None), "state": ("whole_ring", "values")}


def migrate_ring(data):
    """Ring settings from before layouts were renamed: mode and dial became layout, and text values became
    colour_by "values". Returns a new dict; current settings pass through unchanged."""
    d = dict(data or {})
    mode = d.pop("mode", None)
    dial = d.pop("dial", None)
    layout = d.get("layout") or mode
    if layout in OLD_LAYOUTS:
        layout, by = OLD_LAYOUTS[layout]
        if by:
            d["colour_by"] = by
    if layout == "from_now" and dial == "24h":
        layout = "dial_24h"
    if layout:
        d["layout"] = layout
    return d
MARKERS = {"bright": "Full brightness", "white": "White pip", "none": "No marker"}


@dataclass
class Hardware:
    board: str = "esp12e"
    pin: str = "GPIO12"
    method: str = "bit_bang"
    variant: str = "WS2812"
    order: str = "GRB"
    gamma: float = 1.0
    leds: int = 36
    max_brightness: int = 90
    start_brightness: int = 40
    start_led: int = 0  # the LED at 12 o'clock, for the hands and the 24-hour dial
    clockwise: bool = True  # LED numbers increase clockwise


@dataclass
class Ring:
    layout: str = "from_now"
    entity: str = ""
    attrs: list = field(default_factory=list)
    key: str = ""
    t_start: str = ""
    t_end: str = ""
    scale: float = 1.0
    lo: float = 0.0
    hi: float = 100.0
    palette: list = field(default_factory=lambda: [c[:] for c in PALETTE])
    below: list | None = None
    colors: dict = field(default_factory=dict)
    labels: dict = field(default_factory=dict)
    state_notes: dict = field(default_factory=dict)
    fallback: list = field(default_factory=lambda: [100, 100, 100])
    missing: list = field(default_factory=lambda: [0, 0, 0])
    marker: str = "bright"
    dim: float = 0.55
    colour_by: str = "gradient"  # "gradient" (smooth between stops), "steps" (bands from a value up) or "values"
    stops_at: list = field(default_factory=list)  # gradient: the value each palette colour sits at; empty = even
    steps: list = field(default_factory=list)  # steps: [from value, [r, g, b], name], lowest first
    value_attr: str = ""  # one value: read this attribute instead of the entity's state
    entity2: str = ""  # compass: the entity whose value colours the LED (distance, speed); empty = the first
    value2_attr: str = ""  # compass: the attribute of entity2 to read; empty = its state
    parts: list = field(default_factory=list)  # segments: [entity, attribute or "", name] per part
    made_from: str = ""  # the entity is a sensor a package makes from this, e.g. "weather.home hourly"
    raw: str = ""


@dataclass
class Dimming:
    """Brightness that follows the sun. It runs on the clock itself, from the clock's own sun calculation."""
    enabled: bool = True
    night_start: int = 23  # off from this hour; 24 = never
    night_end: int = 6  # back on at this hour
    low: int = 10
    high: int = 90
    elev_low: float = -6
    elev_high: float = 30


@dataclass
class Design:
    """What a clock shows: one entity's data, its colours and how they sit on the ring."""
    name: str = "New design"
    note: str = ""
    ring: Ring = field(default_factory=Ring)


@dataclass
class Clock:
    """One physical clock. It keeps a library of designs and shows exactly one of them, `active`."""
    name: str
    friendly: str
    effect: str = "Ring"
    note: str = ""
    hw: Hardware = field(default_factory=Hardware)
    designs: list = field(default_factory=list)
    active: int = 0
    dimming: Dimming = field(default_factory=Dimming)
    id: str = ""  # fixed for the app's own records (backup, flashed, applied), so renames keep them
    previous_names: list = field(default_factory=list)  # device names since the last apply, to tidy up after
    ring: InitVar[Ring | None] = None  # Clock(ring=...) makes a clock with that one design

    def __post_init__(self, ring):
        if ring is not None or not self.designs:
            self.designs = [Design(self.friendly or "Design", "", ring if ring is not None else Ring())] \
                + list(self.designs if ring is not None else [])
        self.active = max(0, min(int(self.active or 0), len(self.designs) - 1))
        if not self.id:
            self.id = secrets.token_hex(4)

    @property
    def design(self):
        return self.designs[max(0, min(self.active, len(self.designs) - 1))]

    def showing(self, i):
        """The clock as it would be with design i on it. Shares the hardware and the design, so edits stick."""
        return replace(self, designs=[self.designs[i]], active=0, ring=None)

    @property
    def colors_entity(self):
        """Fixed by default_entity_id in the template sensor, so it follows the device name."""
        return f"sensor.{self.name}_ring_colors"



# The design on the clock. Set after the class, because `ring` is also the constructor's InitVar.
Clock.ring = property(lambda self: self.design.ring)


@dataclass
class Project:
    clocks: list = field(default_factory=list)
    secrets: dict = field(default_factory=dict)  # held in the system keychain, never in files
    note: str = ""


def _build(cls, data):
    return cls(**{k: v for k, v in (data or {}).items() if k in cls.__dataclass_fields__})


def project_from_dict(data):
    """From asdict(Project): the draft and the undo history. Also reads drafts from before designs existed."""
    old = data.get("dimming") or {}
    clocks = []
    for c in data.get("clocks", []):
        if "designs" in c:
            designs = [Design(d.get("name", "Design"), d.get("note", ""), _build(Ring, migrate_ring(d.get("ring"))))
                       for d in c["designs"]]
            dimming = _build(Dimming, c.get("dimming"))
        else:
            designs = [Design(c.get("friendly", "Design"), "", _build(Ring, migrate_ring(c.get("ring"))))]
            for k in ("start_led", "clockwise"):  # the ring's orientation moved to the hardware
                if k in (c.get("ring") or {}):
                    c.setdefault("hw", {})[k] = c["ring"][k]
            dimming = _build(Dimming, old)
            dimming.enabled = bool(old.get("enabled", True)) and c["name"] in (old.get("targets") or [])
        clocks.append(Clock(name=c["name"], friendly=c["friendly"], effect=c.get("effect", "Ring"),
                            note=c.get("note", ""), hw=_build(Hardware, c.get("hw")), designs=designs,
                            active=c.get("active", 0), dimming=dimming, id=c.get("id", ""),
                            previous_names=list(c.get("previous_names") or [])))
    return Project(clocks, {}, data.get("note", ""))


FOLD = {"ø": "o", "æ": "ae", "œ": "oe", "ß": "ss", "đ": "d", "ð": "d", "þ": "th", "ł": "l", "ı": "i"}


def ha_slug(text):
    """The part of an entity ID Home Assistant makes from a name: lower case ASCII, digits and _.
    Letters like å, ä and ö become a, a and o, as Home Assistant does it."""
    text = "".join(FOLD.get(c, c) for c in str(text).lower())
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_")


def slug(text):
    """A device name ESPHome accepts."""
    return ha_slug(text) or "clock"


def to_hex(rgb):
    return "#" + "".join(f"{max(0, min(255, int(v))):02x}" for v in rgb)


def from_hex(text):
    t = text.strip().lstrip("#")
    if len(t) != 6:
        raise ValueError("expected #RRGGBB")
    return [int(t[i:i + 2], 16) for i in (0, 2, 4)]


def new_clock(name="Clock"):
    return Clock(name=slug(name), friendly=name.strip() or "Clock", designs=[Design("New design")])


def _ramp(*stops):
    return [from_hex(s) for s in stops]


# Colour stops from the low end to the high end.
GRADIENTS = {
    "Cheap to expensive": [c[:] for c in PALETTE],
    "Green to red": _ramp("#00C853", "#7CFC00", "#FFD700", "#FFA500", "#FF4500", "#FF0040"),
    "Cold to hot": _ramp("#0000CD", "#1E90FF", "#40E0D0", "#7CFC00", "#FFD700", "#FFA500", "#FF0040"),
    "Colour-blind safe": _ramp("#440154", "#3B528B", "#21918C", "#5EC962", "#FDE725"),
    "Through the day": _ramp("#1A1A80", "#2A1060", "#FF6020", "#FFB040", "#FFE6B0", "#FFC860", "#FF5030",
                             "#6020A0"),
}

WEATHER = {"sunny": ("#FFB000", "Sunny"), "clear-night": ("#3020A0", "Clear night"),
           "partlycloudy": ("#FFE6A0", "Partly cloudy"), "cloudy": ("#8090B0", "Cloudy"),
           "fog": ("#C8C0B0", "Fog"), "rainy": ("#0064FF", "Rain"), "pouring": ("#0010FF", "Heavy rain"),
           "snowy": ("#E0F0FF", "Snow"), "snowy-rainy": ("#80D0FF", "Sleet"), "hail": ("#40FFE0", "Hail"),
           "lightning": ("#A000FF", "Thunder"), "lightning-rainy": ("#6000FF", "Thunder and rain"),
           "windy": ("#00D090", "Windy"), "windy-variant": ("#40A090", "Windy and cloudy"),
           "exceptional": ("#FF2000", "Exceptional")}
