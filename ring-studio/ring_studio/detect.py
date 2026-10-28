"""Works out how an entity's data maps onto the ring, so nobody has to type attribute and key names.

Everything here reads a Home Assistant state ({"entity_id", "state", "attributes"}) that the app already
has. Nothing is fetched.
"""

import math
from datetime import datetime

from .model import LIST_MODES

NUMBER_HINTS = ("price", "value", "kwh", "temp", "level", "power", "state", "amount")
TEXT_HINTS = ("condition", "state", "status", "summary")
START_HINTS = ("start", "from", "begin", "datetime", "time")
END_HINTS = ("end", "to", "until", "stop")


def _is_time(value):
    if not isinstance(value, str) or len(value) < 10:
        return False
    try:
        datetime.fromisoformat(value)
        return True
    except ValueError:
        return False


def _is_number(value):
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return True
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False


def list_groups(attrs):
    """Attributes holding lists of records, grouped by the keys their records share (today + tomorrow)."""
    groups = {}
    for name, value in attrs.items():
        if isinstance(value, list) and value and isinstance(value[0], dict):
            groups.setdefault(tuple(sorted(value[0])), []).append(name)
    return sorted(groups.items(), key=lambda g: -sum(len(attrs[n]) for n in g[1]))


def _pick(keys, hints):
    for hint in hints:
        for k in keys:
            if hint in k.lower():
                return k
    return keys[0] if keys else ""


def _nice(value, up):
    """Rounds to a tidy number in the right direction: 0.83 up -> 1, 37 up -> 40, -7 down -> -10."""
    if value == 0:
        return 0.0
    step = 10 ** math.floor(math.log10(abs(value)))
    return float((math.ceil if up else math.floor)(value / step) * step)


def guess(mode, state):
    """Settings for `mode` from the entity's data, and one plain sentence describing what was found.

    Returns (fields, sentence). `fields` only holds what could be worked out."""
    attrs = state.get("attributes", {}) or {}
    fields, found = {}, []
    if mode in LIST_MODES:
        groups = list_groups(attrs)
        if not groups:
            return {}, "This entity has no list of values, so it suits Gauge, Solid or State better."
        keys, names = groups[0]
        items = [i for n in names for i in attrs[n] if isinstance(i, dict)]
        sample = items[0]
        times = [k for k in keys if _is_time(sample.get(k))]
        numbers = [k for k in keys if k not in times and _is_number(sample.get(k))]
        texts = [k for k in keys if k not in times and k not in numbers and isinstance(sample.get(k), str)]
        fields["attrs"] = names
        found.append(" + ".join(names))
        key = _pick(numbers, NUMBER_HINTS) if mode == "timeline" else _pick(texts or numbers, TEXT_HINTS)
        if key:
            fields["key"] = key
            found.append(f"value {key}")
        if len(times) >= 2:
            start = _pick(times, START_HINTS)
            end = _pick([t for t in times if t != start], END_HINTS)
            fields["t_start"], fields["t_end"] = start, end
            found.append(f"times {start} to {end}")
        else:
            fields["t_start"] = fields["t_end"] = ""
            found.append("no start and end times, so the first item is now")
        if mode == "timeline" and key:
            values = [float(i[key]) for i in items if _is_number(i.get(key))]
            fields.update(_range(values, state))
    elif mode in ("gauge", "solid"):
        unit = attrs.get("unit_of_measurement") or ""
        if unit == "%":
            fields.update(scale=1.0, lo=0.0, hi=100.0)
            found.append("a percentage, 0 to 100")
        elif _is_number(attrs.get("min")) and _is_number(attrs.get("max")):
            fields.update(scale=1.0, lo=float(attrs["min"]), hi=float(attrs["max"]))
            found.append(f"its own range, {fields['lo']:g} to {fields['hi']:g}")
        elif not _is_number(state.get("state")):
            return {}, "This entity's state is not a number, so it suits the State layout better."
        else:
            return {}, "This entity does not say its range. Set the low and high ends in Data mapping."
    else:
        return {}, ""
    return fields, "Found " + ", ".join(found) + "."


def _range(values, state):
    """Low and high ends that cover the data, after any multiplier the unit suggests."""
    if not values:
        return {}
    unit = (state.get("attributes", {}) or {}).get("unit_of_measurement") or ""
    scale = 100.0 if "/kWh" in unit and max(abs(v) for v in values) < 10 else 1.0
    lo, hi = min(values) * scale, max(values) * scale
    lo = 0.0 if lo >= 0 else _nice(lo, up=False)
    hi = _nice(hi, up=True) if hi > lo else lo + 1
    return {"scale": scale, "lo": lo, "hi": hi}


def fits(mode, state):
    """Whether an entity suits a layout, for sorting the picker."""
    attrs = state.get("attributes", {}) or {}
    value = state.get("state")
    if mode in LIST_MODES:
        for keys, names in list_groups(attrs):
            sample = attrs[names[0]][0]
            kinds = [_is_number(sample[k]) for k in keys if not _is_time(sample.get(k))]
            if (mode == "timeline" and any(kinds)) or (mode == "states" and not all(kinds)):
                return True
        return False
    if mode in ("gauge", "solid"):
        return _is_number(value)
    if mode == "state":
        return value not in (None, "unknown", "unavailable") and not _is_number(value)
    return False


def shown_value(state):
    """The entity's current value as people read it: "0.43 SEK/kWh", "sunny", "48 entries"."""
    attrs = state.get("attributes", {}) or {}
    value = str(state.get("state", ""))
    unit = attrs.get("unit_of_measurement") or ""
    return f"{value} {unit}".strip()[:40]


def attribute_rows(state, limit=40):
    """The entity's attributes as (name, summary, sample) for the picker. Lists show their size and one item."""
    rows = []
    for name, value in list((state.get("attributes") or {}).items())[:limit]:
        if isinstance(value, list) and value and isinstance(value[0], dict):
            sample = ", ".join(f"{k}: {v}" for k, v in list(value[0].items())[:6])
            rows.append((name, f"list of {len(value)} items", sample[:160]))
        elif isinstance(value, list):
            rows.append((name, f"list of {len(value)}", ", ".join(map(str, value[:8]))[:160]))
        else:
            rows.append((name, str(value)[:120], ""))
    return rows
