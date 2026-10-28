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
    "hands": "Hands: clock hands, colour follows the time of day",
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
    state_notes: dict = field(default_factory=dict)
    fallback: list = field(default_factory=lambda: [100, 100, 100])
    missing: list = field(default_factory=lambda: [0, 0, 0])
    marker: str = "bright"
    dim: float = 0.55
    start_led: int = 0  # hands: the LED at 12 o'clock
    clockwise: bool = True  # hands and the 24-hour dial: LED numbers increase clockwise
    dial: str = ""  # list layouts: "" = one LED per item from now, "24h" = fixed 24-hour dial, midnight at top
    raw: str = ""


@dataclass
class Clock:
    name: str
    friendly: str
    effect: str = "Ring"
    note: str = ""
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
    secrets: dict = field(default_factory=dict)  # held in the system keychain, never in files
    report: dict = field(default_factory=dict)  # what Open repo noticed, per clock
    note: str = ""


def _build(cls, data):
    return cls(**{k: v for k, v in (data or {}).items() if k in cls.__dataclass_fields__})


def project_from_dict(data):
    clocks = [Clock(name=c["name"], friendly=c["friendly"], effect=c.get("effect", "Ring"), note=c.get("note", ""),
                    hw=_build(Hardware, c.get("hw")), ring=_build(Ring, c.get("ring")))
              for c in data.get("clocks", [])]
    return Project(clocks, _build(Dimming, data.get("dimming")), {}, data.get("report", {}), data.get("note", ""))


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


def _starter(name, effect, **ring):
    c = new_clock(name)
    c.effect = effect
    for k, v in ring.items():
        setattr(c.ring, k, v)
    return c


# Ready-made clocks for "Add clock": title, one line on what it shows, and a factory.
STARTERS = {
    "price": ("Electricity price", "15-minute spot prices, next 9 hours", lambda: _starter(
        "Price Clock", "Price Ring", mode="timeline", entity="sensor.swedish_spot_price_elpris_se3_forecast",
        attrs=["today", "tomorrow"], key="SEK_per_kWh", t_start="time_start", t_end="time_end", scale=100.0,
        lo=0.0, hi=100.0, below=[255, 255, 255])),
    "weather": ("Weather", "Hourly forecast, one LED per hour", lambda: _starter(
        "Weather Clock", "Weather Ring", mode="states", entity="sensor.weather_hourly", attrs=["forecast"],
        key="condition", t_start="datetime", dial="24h", colors={k: from_hex(v[0]) for k, v in WEATHER.items()},
        labels={k: v[1] for k, v in WEATHER.items()}, dim=0.4)),
    "temperature": ("Temperature", "Outdoor temperature fills the ring", lambda: _starter(
        "Temperature Clock", "Temperature Ring", mode="gauge", entity="sensor.outdoor_temperature",
        lo=-20.0, hi=30.0, palette=[c[:] for c in GRADIENTS["Cold to hot"]])),
    "battery": ("Battery", "A battery level fills the ring", lambda: _starter(
        "Battery Clock", "Battery Ring", mode="gauge", entity="sensor.phone_battery_level", lo=0.0, hi=100.0,
        palette=list(reversed([c[:] for c in GRADIENTS["Green to red"]])))),
    "calendar": ("Calendar", "Busy or free right now", lambda: _starter(
        "Calendar Clock", "Calendar Ring", mode="state", entity="calendar.home",
        colors={"on": [255, 0, 64], "off": [0, 200, 83]}, labels={"on": "Busy", "off": "Free"})),
    "hands": ("Clock hands", "Hour and minute hands, colours change through the day", lambda: _starter(
        "Hands Clock", "Hands Ring", mode="hands", entity="", palette=[c[:] for c in GRADIENTS["Through the day"]],
        missing=[0, 0, 0], dim=0.15, start_led=0, clockwise=True)),
    "blank": ("Blank", "Start from nothing", lambda: new_clock("Clock")),
}
