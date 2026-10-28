"""Data model. One Clock is one ESP device plus the Home Assistant template that colours it."""

from dataclasses import dataclass, field

PALETTE = [[0, 191, 255], [0, 112, 255], [0, 64, 255], [64, 0, 255], [128, 0, 255],
           [176, 0, 255], [255, 0, 255], [255, 0, 128], [255, 0, 64]]

# Modes: list modes colour one LED per list item, value modes use the entity state.
LIST_MODES = ("timeline", "states")
VALUE_MODES = ("gauge", "solid", "state")
MAP_MODES = ("states", "state")
MODES = {
    "timeline": "Timeline: list of numbers, one LED per item",
    "states": "States: list of states, one LED per item",
    "gauge": "Gauge: number fills the ring",
    "solid": "Solid: number colours the whole ring",
    "state": "State: one state colours the whole ring",
    "raw": "Raw: hand-written template, kept as is",
}
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


@dataclass
class Ring:
    mode: str = "timeline"
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
    fallback: list = field(default_factory=lambda: [100, 100, 100])
    missing: list = field(default_factory=lambda: [0, 0, 0])
    marker: str = "bright"
    dim: float = 0.55
    raw: str = ""


@dataclass
class Clock:
    name: str
    friendly: str
    effect: str = "Ring"
    hw: Hardware = field(default_factory=Hardware)
    ring: Ring = field(default_factory=Ring)

    @property
    def colors_entity(self):
        return f"sensor.{self.name}_ring_colors"

    @property
    def brightness_entity(self):
        return f"number.{self.name}_ring_brightness"


@dataclass
class Dimming:
    enabled: bool = True
    night_start: int = 23
    night_end: int = 6
    low: int = 10
    high: int = 90
    elev_low: float = -6
    elev_high: float = 30
    targets: list = field(default_factory=list)


@dataclass
class Project:
    clocks: list = field(default_factory=list)
    dimming: Dimming = field(default_factory=Dimming)
    secrets: dict = field(default_factory=dict)
    notes: dict = field(default_factory=dict)


def _build(cls, data):
    return cls(**{k: v for k, v in (data or {}).items() if k in cls.__dataclass_fields__})


def project_from_dict(data):
    clocks = [Clock(name=c["name"], friendly=c["friendly"], effect=c.get("effect", "Ring"),
                    hw=_build(Hardware, c.get("hw")), ring=_build(Ring, c.get("ring")))
              for c in data.get("clocks", [])]
    return Project(clocks, _build(Dimming, data.get("dimming")), data.get("secrets", {}), data.get("notes", {}))


def slug(text):
    out = "".join(c if c.isalnum() else "_" for c in text.lower()).strip("_")
    while "__" in out:
        out = out.replace("__", "_")
    return out or "clock"


def to_hex(rgb):
    return "#" + "".join(f"{max(0, min(255, int(v))):02x}" for v in rgb)


def from_hex(text):
    t = text.strip().lstrip("#")
    if len(t) != 6:
        raise ValueError("expected #RRGGBB")
    return [int(t[i:i + 2], 16) for i in (0, 2, 4)]


def new_clock(name="clock"):
    return Clock(name=slug(name), friendly=name.strip().title() or "Clock")
