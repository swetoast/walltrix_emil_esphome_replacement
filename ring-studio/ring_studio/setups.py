"""Ready-made setups for "New design". Each one finds its own data among the Home Assistant entities, asks one
or two short questions and builds a Design from the answers.

`states` everywhere is entity_id -> {"state", "attributes"}, as Home Assistant reports it.

Some data cannot be read by a template on its own: since Home Assistant 2024.3 weather forecasts and calendar
events are only handed out by an action (weather.get_forecasts, calendar.get_events), and template helpers cannot
call actions. For those, the design reads a small sensor that a package makes (`package()`), and the ring's
`made_from` names where that sensor gets its data.
"""

from dataclasses import dataclass, field
from datetime import datetime

from . import detect
from .model import GRADIENTS, PALETTE, WEATHER, Design, Ring, from_hex

GREEN, AMBER, RED, OFF = [0, 200, 83], [255, 176, 0], [255, 0, 64], [0, 0, 0]
DISTINCT = [from_hex(h) for h in ("#FFB000", "#3020A0", "#00C853", "#FF0040", "#1E90FF", "#FF00FF", "#7CFC00",
                                  "#40E0D0", "#FF6020", "#C8C0B0", "#8000FF", "#FFE6A0")]


@dataclass
class Question:
    key: str
    label: str
    options: list  # [(value, label)], the first is the default


@dataclass
class Candidate:
    """An entity the setup can use. `source` is set when the entity is made by a package from another one."""
    entity: str
    label: str
    source: str = ""


@dataclass
class Setup:
    key: str
    title: str
    sub: str
    swatch: list
    questions: list = field(default_factory=list)
    pick: str = ""  # label of the entity dropdown; empty when there is nothing to pick
    needs: str = ""  # what to install when nothing is found


def _attrs(s):
    return (s or {}).get("attributes") or {}


def _dc(s):
    return _attrs(s).get("device_class") or ""


def _unit(s):
    return _attrs(s).get("unit_of_measurement") or ""


def _domain(e):
    return e.split(".", 1)[0]


def name_of(entity, states):
    return _attrs(states.get(entity)).get("friendly_name") or entity


def _number(v):
    return detect._is_number(v) and v not in ("nan", "inf")


def _time(v):
    try:
        datetime.fromisoformat(str(v))
        return len(str(v)) >= 10
    except ValueError:
        return False


def _rank(entities, words):
    """Entities whose id holds one of the words first, in the words' order, then the rest by id."""
    def score(e):
        low = e.lower()
        hits = [i for i, w in enumerate(words) if w in low]
        return (hits[0] if hits else len(words), e)
    return sorted(entities, key=score)


def _lists(state):
    """(attribute names, item keys, items) for the entity's biggest group of list attributes, or None."""
    groups = detect.list_groups(_attrs(state))
    if not groups:
        return None
    keys, names = groups[0]
    items = [i for n in names for i in _attrs(state)[n] if isinstance(i, dict)]
    return names, keys, items


def _spacing(items, t_key):
    """Hours between the first two items, or None."""
    times = []
    for i in items[:2]:
        try:
            times.append(datetime.fromisoformat(str(i.get(t_key))))
        except ValueError:
            return None
    if len(times) < 2:
        return None
    try:
        return abs((times[1] - times[0]).total_seconds()) / 3600
    except TypeError:
        return None


# ---------------------------------------------------------------- the setups

SETUPS = {
    "price": Setup("price", "Electricity price", "Prices ahead, cheap to expensive",
                   ["#00BFFF", "#4000FF", "#B000FF", "#FF00FF", "#FF0040"],
                   [Question("show", "Show", [("all", "All prices"), ("cheap", "Cheapest hours only")]),
                    Question("ring", "On the ring", [("from_now", "From now"), ("dial_24h", "24 hours")])],
                   "Price entity", "a price integration such as Nord Pool or Swedish Spot Price"),
    "weather": Setup("weather", "Weather", "Conditions, temperature, rain or sun strength",
                     ["#FFB000", "#8090B0", "#0064FF", "#3020A0", "#E0F0FF"],
                     [Question("show", "Show", [("condition", "Conditions"), ("temperature", "Temperature"),
                                                ("precipitation", "Rain"), ("uv_index", "Sun strength")]),
                      Question("ring", "On the ring", [("from_now", "From now"), ("dial_24h", "24 hours"),
                                                       ("week", "Week")])],
                     "Weather entity", "a weather integration such as Met.no or SMHI"),
    "direction": Setup("direction", "Direction", "Wind or lightning on a compass", ["#40E0D0", "#FFD700", "#FF0040"],
                       [Question("show", "Show", [("wind", "Wind"), ("lightning", "Lightning")])],
                       "Direction from", "a weather integration, or Blitzortung for lightning"),
    "value": Setup("value", "One value", "Any sensor, colours from its type",
                   ["#0000CD", "#40E0D0", "#7CFC00", "#FFD700", "#FF0040"],
                   [Question("ring", "On the ring", [("fill", "Fill"), ("whole_ring", "Whole ring")])],
                   "Which value", "any sensor with a number"),
    "board": Setup("board", "Status board", "Up to 12 things at a glance",
                   ["#00C853", "#00C853", "#FF0040", "#00C853", "#FFD700"],
                   [Question("show", "Show", [("doors", "Doors and windows"), ("people", "Who's home"),
                                              ("batteries", "Batteries"), ("plants", "Plants"),
                                              ("network", "Network")])],
                   "", "door, person, battery, plant or connectivity entities"),
    "countdown": Setup("countdown", "Countdown", "Minutes to a departure or a finish", ["#00C853", "#FFD700", "#FF0040"],
                       [Question("to", "Count down to", [("departure", "Next departure"), ("timer", "A timer"),
                                                         ("appliance", "An appliance")])],
                       "Count down to", "a departure sensor, a timer helper or an appliance with a finish time"),
    "week": Setup("week", "Week", "Seven days: shifts or bin days", ["#FFB000", "#3020A0", "#2C333C", "#FFB000"],
                  [Question("show", "Show", [("shifts", "Shifts"), ("bins", "Bin days")])],
                  "Schedule", "a calendar or a schedule sensor"),
    "calendar": Setup("calendar", "Calendar", "Busy hours today, or busy right now", ["#FF0040", "#00C853"],
                      [Question("show", "Show", [("hours", "Today's busy hours"), ("now", "Busy or free now")])],
                      "Calendar", "a calendar"),
    "clock": Setup("clock", "Clock", "Hands, or hands with sunrise and sunset",
                   ["#1A1A80", "#FF6020", "#FFE6B0", "#FF5030", "#6020A0"],
                   [Question("show", "Show", [("hands", "Hands"), ("sun", "Hands with sunrise and sunset")])]),
    "blank": Setup("blank", "Blank", "Start from nothing", []),
}


def defaults(key):
    return {q.key: q.options[0][0] for q in SETUPS[key].questions}


# ---------------------------------------------------------------- finding entities

def _price_lists(states):
    out = []
    for e, s in states.items():
        if _domain(e) != "sensor":
            continue
        found = _lists(s)
        if not found:
            continue
        _, keys, items = found
        sample = items[0]
        if any(_time(sample.get(k)) for k in keys) and any(_number(sample.get(k)) for k in keys):
            words = (e + " " + _unit(s)).lower()
            if any(w in words for w in ("price", "pris", "nordpool", "spot", "tibber", "kwh", "energy")):
                out.append(e)
    return _rank(out, ["spot_price", "nordpool", "price", "tibber"])


def _forecast_lists(states, daily, key=""):
    """List sensors holding a forecast with one item per hour (or per day when `daily`), whose items have `key`."""
    out = []
    for e, s in states.items():
        found = _lists(s)
        if _domain(e) == "weather" or not found:
            continue
        names, keys, items = found
        if "datetime" not in keys or not ({"condition", "temperature"} & set(keys)):
            continue
        if key and not any(key in i for i in items):
            continue
        hours = _spacing(items, "datetime")
        if hours is None or (hours >= 20) == daily:
            out.append(e)
    return sorted(out)


def forecast_sensor(weather, daily):
    obj = weather.split(".", 1)[1]
    return f"sensor.{obj}_{'daily' if daily else 'hourly'}_forecast"


def events_sensor(calendar, days):
    obj = calendar.split(".", 1)[1]
    return f"sensor.{obj}_{'week' if days else 'hours'}"


def _calendars(states, words=()):
    return _rank([e for e in states if _domain(e) == "calendar"], list(words))


def _with_source(entity, source, states, what):
    """A sensor made by a package from `source`; ready when it already exists."""
    if entity in states:
        return Candidate(entity, name_of(entity, states))
    return Candidate(entity, f"{name_of(source, states)} (adds {what})", source)


def find(key, answers, states):
    """Candidates for the setup, best first."""
    a = {**defaults(key), **(answers or {})}
    pick = []
    if key == "price":
        pick = [Candidate(e, name_of(e, states)) for e in _price_lists(states)]
    elif key == "weather":
        daily = a["ring"] == "week"
        ready = [Candidate(e, name_of(e, states)) for e in _forecast_lists(states, daily, a["show"])]
        made = [_with_source(forecast_sensor(w, daily), w, states, "a forecast sensor")
                for w in sorted(e for e in states if _domain(e) == "weather")]
        pick = ready + [c for c in made if c.entity not in {r.entity for r in ready}]
    elif key == "direction":
        if a["show"] == "wind":
            pick = [Candidate(e, name_of(e, states)) for e in sorted(states)
                    if _domain(e) == "weather" and "wind_bearing" in _attrs(states[e])]
            pick += [Candidate(e, name_of(e, states)) for e in sorted(states) if _domain(e) == "sensor"
                     and (_dc(states[e]) == "wind_direction" or "wind_direction" in e or "wind_bearing" in e)]
        else:
            pick = [Candidate(e, name_of(e, states)) for e in sorted(states)
                    if _domain(e) == "sensor" and "lightning" in e and "azimuth" in e]
    elif key == "value":
        nums = [e for e, s in states.items() if _domain(e) in ("sensor", "input_number", "number")
                and _number(s.get("state"))]
        order = [t[0] for t in TYPES] + ["other"]
        nums.sort(key=lambda e: (order.index(_type_of(states[e])[0]), e))
        pick = [Candidate(e, f"{name_of(e, states)}" + (f" ({_unit(states[e])})" if _unit(states[e]) else ""))
                for e in nums]
    elif key == "board":
        parts = board_parts(a["show"], states)
        if parts:
            pick = [Candidate(parts[0][0], f"{len(parts)} found, all picked")]
    elif key == "countdown":
        pick = [Candidate(e, name_of(e, states)) for e in _countdowns(a["to"], states)]
    elif key == "week":
        words = ["shift", "work", "schema", "periodical", "jobb"] if a["show"] == "shifts" else \
            ["waste", "bin", "garbage", "sopor", "avfall", "trash", "recycl"]
        lists = [e for e, s in states.items() if _domain(e) == "sensor" and _schedule_list(s)]
        lists = [e for e in _rank(lists, words) if any(w in e.lower() for w in words)]
        pick = [Candidate(e, name_of(e, states)) for e in lists]
        pick += [_with_source(events_sensor(c, True), c, states, "a week sensor") for c in _calendars(states, words)]
    elif key == "calendar":
        cals = _calendars(states)
        if a["show"] == "now":
            pick = [Candidate(c, name_of(c, states)) for c in cals]
        else:
            pick = [_with_source(events_sensor(c, False), c, states, "an hours sensor") for c in cals]
    elif key == "clock":
        pick = [Candidate("sun.sun", "sun.sun")] if a["show"] == "sun" else []
    return pick


def status(key, states):
    """(found, text) for the tile: what the setup found, or what it needs."""
    s = SETUPS[key]
    if key == "blank":
        return False, "Needs nothing"
    if key == "clock":
        return True, "Uses the time and sun.sun"
    if key == "value":
        n = len(find(key, {}, states))
        return (True, "Any sensor") if n else (False, "Needs " + s.needs)
    found = []
    for q in s.questions[:1]:
        for value, label in q.options:
            cands = find(key, {q.key: value}, states)
            if cands:
                found.append((label, cands))
    if not found:
        return False, "Needs " + s.needs
    if key == "board":
        return True, "Found: " + ", ".join(label.lower() for label, _ in found[:3])
    cands = found[0][1]
    first = (cands[0].source and name_of(cands[0].source, states)) or cands[0].label
    more = len({c.source or c.entity for _, cs in found for c in cs}) - 1
    return True, f"Found: {first}" + (f" and {more} more" if more > 0 else "")


# ---------------------------------------------------------------- one value: colours by type

TYPES = [  # (name, test, lo, hi, palette or steps)
    ("temperature", lambda s: _dc(s) == "temperature" or _unit(s) in ("°C", "°F")),
    ("battery", lambda s: _dc(s) == "battery"),
    ("humidity", lambda s: _dc(s) in ("humidity", "moisture")),
    ("carbon_dioxide", lambda s: _dc(s) == "carbon_dioxide" or _unit(s) == "ppm"),
    ("radon", lambda s: "radon" in str(_attrs(s).get("friendly_name", "")).lower() or _unit(s) in ("Bq/m³", "pCi/L")),
    ("aqi", lambda s: _dc(s) == "aqi"),
    ("power", lambda s: _dc(s) == "power" or _unit(s) in ("W", "kW")),
    ("percent", lambda s: _unit(s) == "%"),
]


def _type_of(state):
    for name, test in TYPES:
        if test(state):
            return name, _unit(state)
    return "other", _unit(state)


def value_ring(state, layout):
    kind, unit = _type_of(state)
    r = Ring(layout=layout)
    ramp = lambda name: [c[:] for c in GRADIENTS[name]]  # noqa: E731
    if kind == "temperature":
        r.lo, r.hi = (0.0, 90.0) if unit == "°F" else (-20.0, 30.0)
        r.palette = ramp("Cold to hot")
    elif kind in ("battery", "percent"):
        r.lo, r.hi, r.palette = 0.0, 100.0, list(reversed(ramp("Green to red")))
        if kind == "battery":
            r.colour_by, r.steps = "steps", [[0, RED[:], "Low"], [20, AMBER[:], "Getting low"], [50, GREEN[:], "Fine"]]
    elif kind == "humidity":
        r.lo, r.hi, r.palette = 0.0, 100.0, [from_hex("#FFB000"), from_hex("#00C853"), from_hex("#0064FF")]
    elif kind == "carbon_dioxide":
        r.lo, r.hi = 400.0, 2000.0
        r.colour_by, r.steps = "steps", [[0, GREEN[:], "Fresh"], [1000, AMBER[:], "Stuffy"], [1500, RED[:], "Air out"]]
    elif kind == "radon":
        r.lo, r.hi = 0.0, 400.0
        limit = 5.4 if unit == "pCi/L" else 200
        r.colour_by, r.steps = "steps", [[0, GREEN[:], "Low"], [limit / 2, AMBER[:], "Raised"],
                                         [limit, RED[:], "Above the reference level"]]
    elif kind == "aqi":
        r.lo, r.hi = 0.0, 300.0
        r.colour_by, r.steps = "steps", [[0, GREEN[:], "Good"], [51, from_hex("#FFD700"), "Moderate"],
                                         [101, from_hex("#FF8000"), "Unhealthy for some"],
                                         [151, RED[:], "Unhealthy"], [201, from_hex("#8000FF"), "Very unhealthy"]]
    elif kind == "power":
        r.lo, r.hi, r.palette = 0.0, 3000.0 if unit == "W" else 3.0, ramp("Green to red")
    else:
        fields, _ = detect.guess("fill", state)
        r.lo, r.hi = fields.get("lo", 0.0), fields.get("hi", 0.0)
        if r.hi <= r.lo:
            v = float(state.get("state") or 0)
            r.lo, r.hi = (0.0, detect._nice(v * 2, True) or 100.0) if v >= 0 else (detect._nice(v * 2, False), 0.0)
        r.palette = [c[:] for c in PALETTE]
    return r


# ---------------------------------------------------------------- status board and countdown

BOARDS = {  # what to look for, and the colour of each state
    "doors": (lambda e, s: _domain(e) == "binary_sensor" and _dc(s) in ("door", "window", "garage_door", "opening"),
              {"on": RED, "off": GREEN}, {"on": "Open", "off": "Closed"}),
    "people": (lambda e, s: _domain(e) == "person", {"home": GREEN, "not_home": [40, 40, 40]},
               {"home": "Home", "not_home": "Away"}),
    "batteries": (lambda e, s: _domain(e) == "sensor" and _dc(s) == "battery" and _number(s.get("state")), {}, {}),
    "plants": (lambda e, s: _domain(e) == "plant" or (_domain(e) == "binary_sensor" and _dc(s) == "problem"
                                                       and "plant" in e),
               {"ok": GREEN, "problem": RED, "off": GREEN, "on": RED},
               {"ok": "Fine", "problem": "Needs care", "off": "Fine", "on": "Needs care"}),
    "network": (lambda e, s: _domain(e) == "binary_sensor" and _dc(s) == "connectivity",
                {"on": GREEN, "off": RED}, {"on": "Connected", "off": "Down"}),
}


def board_parts(show, states):
    test = BOARDS[show][0]
    found = sorted(e for e, s in states.items() if test(e, s))
    return [[e, "", name_of(e, states)] for e in found[:12]]


DEPARTURE_WORDS = ("departure", "avgang", "vasttrafik", "trafiklab", "resrobot", "sl_", "bus", "tram", "train",
                   "metro", "ferry", "transport")


def _countdowns(to, states):
    out = []
    for e, s in states.items():
        d = _domain(e)
        if to == "timer":
            if d == "timer":
                out.append(e)
        elif d == "sensor":
            low = e.lower()
            is_time = _dc(s) == "timestamp" or _time(s.get("state"))
            if to == "departure" and is_time and any(w in low for w in DEPARTURE_WORDS):
                out.append(e)
            elif to == "appliance" and ((is_time and any(w in low for w in ("finish", "end", "done", "complet")))
                                        or (_unit(s) == "min" and "remain" in low)):
                out.append(e)
    return _rank(out, ["departure", "next", "finish", "remain"])


def _schedule_list(state):
    """A sensor whose list items have a time and a text, like shifts or collection days."""
    found = _lists(state)
    if not found:
        return None
    _, keys, items = found
    sample = items[0]
    times = [k for k in keys if _time(sample.get(k))]
    texts = [k for k in keys if k not in times and isinstance(sample.get(k), str) and not _number(sample.get(k))]
    if not times or not texts or "condition" in keys:
        return None
    return detect._pick(times, detect.START_HINTS), detect._pick(texts, ("shift", "type", "summary", "name", "event"))


# ---------------------------------------------------------------- building the design

def build(key, answers, candidate, states):
    """The Design for the answers. `candidate` is the picked Candidate (or None)."""
    s = SETUPS[key]
    a = {**defaults(key), **(answers or {})}
    e = candidate.entity if candidate else ""
    st = states.get(e, {})
    if key == "blank":
        return Design("New design")
    if key == "price":
        r = Ring(layout=a["ring"], entity=e, below=[255, 255, 255])
        fields, _ = detect.guess("from_now", st) if st else ({}, "")
        for k, v in fields.items():
            setattr(r, k, v)
        if a["show"] == "cheap":
            values = sorted(float(i[r.key]) * r.scale for i in (_lists(st) or ([], [], []))[2]
                            if _number(i.get(r.key)))
            cut = round(values[len(values) // 3], 2) if values else (r.lo + r.hi) / 3
            r.colour_by, r.below = "steps", None
            r.steps = [[r.lo if values and values[0] >= r.lo else round(values[0], 2) if values else r.lo,
                        GREEN[:], "Cheap"], [cut, OFF[:], "Not cheap"]]
        return Design("Cheapest hours" if a["show"] == "cheap" else s.title, "", r)
    if key == "weather":
        show = a["show"]
        r = Ring(layout=a["ring"], entity=e, attrs=["forecast"], key=show, t_start="datetime")
        if candidate and candidate.source:
            r.made_from = f"{candidate.source} {'daily' if a['ring'] == 'week' else 'hourly'}"
        src = states.get(candidate.source if candidate and candidate.source else e, {})
        if show == "condition":
            r.colour_by, r.dim = "values", 0.7 if a["ring"] == "week" else 0.4
            r.colors = {k: from_hex(v[0]) for k, v in WEATHER.items()}
            r.labels = {k: v[1] for k, v in WEATHER.items()}
        elif show == "temperature":
            hot = _attrs(src).get("temperature_unit") == "°F"
            r.lo, r.hi = (0.0, 90.0) if hot else (-20.0, 30.0)
            r.palette = [c[:] for c in GRADIENTS["Cold to hot"]]
        elif show == "precipitation":
            inch = _attrs(src).get("precipitation_unit") == "in"
            k = 0.04 if inch else 1
            r.colour_by = "steps"
            r.steps = [[0, OFF[:], "Dry"], [0.1 * k, from_hex("#80D0FF"), "A little"],
                       [1 * k, from_hex("#0064FF"), "Rain"], [4 * k, from_hex("#0010FF"), "Heavy"]]
        else:
            r.colour_by = "steps"
            r.steps = [[0, OFF[:], "None"], [1, GREEN[:], "Low"], [3, from_hex("#FFD700"), "Moderate"],
                       [6, from_hex("#FF8000"), "High"], [8, RED[:], "Very high"],
                       [11, from_hex("#8000FF"), "Extreme"]]
        title = {"condition": "Weather", "temperature": "Temperature ahead", "precipitation": "Rain",
                 "uv_index": "Sun strength"}[show]
        return Design(title + (" this week" if a["ring"] == "week" else ""), "", r)
    if key == "direction":
        if a["show"] == "wind":
            if _domain(e) == "weather":
                r = Ring(layout="compass", entity=e, value_attr="wind_bearing", entity2=e, value2_attr="wind_speed")
                unit = _attrs(st).get("wind_speed_unit") or "m/s"
            else:
                speed = e.replace("direction", "speed").replace("bearing", "speed")
                r = Ring(layout="compass", entity=e, entity2=speed if speed in states else "")
                unit = _unit(states.get(speed)) or "m/s"
            r.hi = {"km/h": 70.0, "mph": 45.0, "kn": 40.0}.get(unit, 20.0)
            r.palette = [from_hex("#40E0D0"), from_hex("#7CFC00"), from_hex("#FFD700"), RED[:]]
            return Design("Wind", "", r)
        dist = e.replace("azimuth", "distance")
        r = Ring(layout="compass", entity=e, entity2=dist if dist in states else "", lo=0.0, hi=100.0,
                 palette=[RED[:], from_hex("#FF8C00"), from_hex("#504000")])
        return Design("Lightning", "", r)
    if key == "value":
        r = value_ring(st, a["ring"])
        r.entity = e
        return Design(name_of(e, states) if e else s.title, "", r)
    if key == "board":
        _, colours, labels = BOARDS[a["show"]]
        r = Ring(layout="segments", parts=board_parts(a["show"], states), colour_by="values",
                 colors={k: v[:] for k, v in colours.items()}, labels=dict(labels))
        if a["show"] == "batteries":
            r.colour_by, r.steps = "steps", [[0, RED[:], "Low"], [20, AMBER[:], "Getting low"],
                                             [50, GREEN[:], "Fine"]]
        title = dict(SETUPS["board"].questions[0].options)[a["show"]]
        return Design(title, "", r)
    if key == "countdown":
        r = Ring(layout="countdown", entity=e, colour_by="steps")
        if _domain(e) == "timer":
            r.value_attr = "finishes_at"
        if a["to"] == "departure":
            r.steps = [[0, RED[:], "Go now"], [4, AMBER[:], "Soon"], [7, GREEN[:], "Plenty of time"]]
        else:
            r.steps = [[0, AMBER[:], "Nearly done"], [4, GREEN[:], "Running"]]
        return Design({"departure": "Next departure", "timer": "Timer", "appliance": "Appliance"}[a["to"]], "", r)
    if key == "week":
        if candidate and candidate.source:
            r = Ring(layout="week", entity=e, attrs=["days"], key="event", t_start="start", colour_by="values",
                     made_from=candidate.source + " week", fallback=AMBER[:], marker="bright")
        else:
            t_key, text_key = _schedule_list(st) or ("start", "summary")
            names = (_lists(st) or ([], [], []))[0]
            r = Ring(layout="week", entity=e, attrs=list(names), key=text_key, t_start=t_key, colour_by="values",
                     fallback=AMBER[:])
            seen = []
            for item in (_lists(st) or ([], [], []))[2]:
                v = str(item.get(text_key, ""))
                if v and v not in seen:
                    seen.append(v)
            r.colors = {v: DISTINCT[i % len(DISTINCT)][:] for i, v in enumerate(seen[:12])}
        return Design("Shifts" if a["show"] == "shifts" else "Bin days", "", r)
    if key == "calendar":
        if a["show"] == "now":
            r = Ring(layout="whole_ring", entity=e, colour_by="values", colors={"on": RED[:], "off": GREEN[:]},
                     labels={"on": "Busy", "off": "Free"})
            return Design("Busy or free", "", r)
        r = Ring(layout="dial_24h", entity=e, attrs=["hours"], key="event", t_start="start", colour_by="values",
                 fallback=RED[:], missing=OFF[:], marker="white", dim=1.0)
        if candidate and candidate.source:
            r.made_from = candidate.source + " hours"
        return Design("Busy hours", "", r)
    if key == "clock":
        if a["show"] == "sun":
            return Design("Day and night", "", Ring(layout="day_arc"))
        return Design("Clock hands", "", Ring(layout="hands", palette=[c[:] for c in GRADIENTS["Through the day"]],
                                              missing=OFF[:], dim=0.15))
    raise KeyError(key)


def sentence(key, answers):
    """One line on what the design will show."""
    a = {**defaults(key), **(answers or {})}
    if key == "price":
        if a["show"] == "cheap":
            return "Only the cheapest third of the prices is lit, the rest stay dark."
        return ("Every hour of the day in its own place, midnight at the top." if a["ring"] == "dial_24h"
                else "One LED per price, starting at now.")
    if key == "weather":
        what = {"condition": "Conditions", "temperature": "Temperature", "precipitation": "Rain",
                "uv_index": "Sun strength"}[a["show"]]
        where = {"from_now": "from now, one LED per hour.", "dial_24h": "for every hour, midnight at the top.",
                 "week": "for the next seven days, today at the top."}[a["ring"]]
        return f"{what} {where}"
    if key == "direction":
        return ("The LED at the strikes' direction, red when close." if a["show"] == "lightning"
                else "The LED where the wind comes from, coloured by its strength.")
    if key == "value":
        return ("The whole ring in the value's colour." if a["ring"] == "whole_ring"
                else "The value fills the ring, with colours that suit its type.")
    if key == "board":
        return {"doors": "One segment per door or window: green closed, red open.",
                "people": "One segment per person: green at home.",
                "batteries": "One segment per battery: red below 20 %, amber below 50 %.",
                "plants": "One segment per plant: red when it needs care.",
                "network": "One segment per connection: red when it is down."}[a["show"]]
    if key == "countdown":
        return ("One LED per minute left, red when it is time to go." if a["to"] == "departure"
                else "One LED per minute left until it finishes.")
    if key == "week":
        return ("Each day in its shift colour, today at the top." if a["show"] == "shifts"
                else "Collection days lit, today at the top.")
    if key == "calendar":
        return ("Red while an event is on, green when free." if a["show"] == "now"
                else "Busy hours of today lit on the 24-hour dial.")
    if key == "clock":
        return ("A 24-hour face: day lit, night dim, sunrise and sunset marked, the time in white."
                if a["show"] == "sun" else "An analog clock whose colours change through the day.")
    return "An empty design to build yourself."


# ---------------------------------------------------------------- packages for data a template cannot fetch

_HEAD = """\
  - trigger:
      - trigger: time_pattern
        minutes: /{every}
      - trigger: homeassistant
        event: start
      - trigger: state
        entity_id: {source}
    action:
"""

_ZONE = "{% set z = now().replace(microsecond=0).isoformat()[19:] %}"
_WHEN = ("{% set s = (e.start ~ ('T00:00:00' ~ z if e.start | length == 10 else '')) | as_datetime %}"
         "{% set f = (e.end ~ ('T00:00:00' ~ z if e.end | length == 10 else '')) | as_datetime %}")


def _forecast_package(weather, kind):
    sensor = forecast_sensor(weather, kind == "daily")
    obj = sensor.split(".", 1)[1]
    return (_HEAD.format(every=30, source=weather) +
            f"      - action: weather.get_forecasts\n"
            f"        target:\n"
            f"          entity_id: {weather}\n"
            f"        data:\n"
            f"          type: {kind}\n"
            f"        response_variable: answer\n"
            f"    sensor:\n"
            f"      - name: {obj.replace('_', ' ').title()}\n"
            f"        unique_id: ring_studio_{obj}\n"
            f"        default_entity_id: {sensor}\n"
            f"        state: \"{{{{ now().isoformat() }}}}\"\n"
            f"        attributes:\n"
            f"          forecast: \"{{{{ answer['{weather}'].forecast }}}}\"\n")


def _events_package(calendar, kind):
    """A sensor with one item per hour of today and tomorrow (hours) or per day of the week ahead (week), each
    holding the summary of the event that covers it, or an empty text. Hours skip all-day events, since they
    do not make an hour busy; days prefer them, since bin days and shifts are often all-day."""
    week = kind == "week"
    sensor = events_sensor(calendar, week)
    obj = sensor.split(".", 1)[1]
    n, step = (7, "days") if week else (48, "hours")
    body = ("{% set z = now().replace(microsecond=0).isoformat()[19:] %}"
            f"{{% set ev = answer['{calendar}'].events %}}"
            "{% set ns = namespace(out=[]) %}"
            f"{{% for i in range({n}) %}}"
            f"{{% set a = today_at() + timedelta({step}=i) %}}{{% set b = a + timedelta({step}=1) %}}"
            "{% set hit = namespace(day='', timed='') %}"
            "{% for e in ev %}" + _WHEN +
            "{% if s < b and f > a %}"
            "{% if e.start | length == 10 %}{% set hit.day = hit.day or e.summary %}"
            "{% else %}{% set hit.timed = hit.timed or e.summary %}{% endif %}"
            "{% endif %}{% endfor %}"
            + ("{% set ns.out = ns.out + [{'start': a.isoformat(), 'event': hit.day or hit.timed}] %}" if week else
               "{% set ns.out = ns.out + [{'start': a.isoformat(), 'event': hit.timed}] %}")
            + "{% endfor %}{{ ns.out }}")
    return (_HEAD.format(every=15, source=calendar) +
            f"      - action: calendar.get_events\n"
            f"        target:\n"
            f"          entity_id: {calendar}\n"
            f"        data:\n"
            f"          start_date_time: \"{{{{ today_at() }}}}\"\n"
            f"          duration:\n"
            f"            days: {7 if week else 2}\n"
            f"        response_variable: answer\n"
            f"    sensor:\n"
            f"      - name: {obj.replace('_', ' ').title()}\n"
            f"        unique_id: ring_studio_{obj}\n"
            f"        default_entity_id: {sensor}\n"
            f"        state: \"{{{{ answer['{calendar}'].events | count }}}}\"\n"
            f"        attributes:\n"
            f"          {'days' if week else 'hours'}: >-\n"
            f"            {body}\n")


def package(sources):
    """A Home Assistant package making the sensors that designs read with `made_from`. `sources` is a list of
    made_from texts like "weather.home hourly" or "calendar.home week". Empty when there are none."""
    parts = []
    for src in dict.fromkeys(s for s in sources if s):
        entity, _, kind = src.partition(" ")
        if _domain(entity) == "weather" and kind in ("hourly", "daily"):
            parts.append(_forecast_package(entity, kind))
        elif _domain(entity) == "calendar" and kind in ("hours", "week"):
            parts.append(_events_package(entity, kind))
    if not parts:
        return ""
    return ("# Sensors Ring Studio's designs read. Weather forecasts and calendar events are only handed out by\n"
            "# an action, so these sensors fetch them on a timer. Put this file in your packages folder.\n"
            "template:\n" + "".join(parts))


def made_from_entity(made_from):
    """The sensor a made_from text produces."""
    entity, _, kind = (made_from or "").partition(" ")
    if _domain(entity) == "weather":
        return forecast_sensor(entity, kind == "daily")
    if _domain(entity) == "calendar":
        return events_sensor(entity, kind == "week")
    return ""
