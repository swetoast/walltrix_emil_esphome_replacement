"""Renders a ring template on this computer, the way Home Assistant does, at any moment.

Home Assistant can only render a template at the current time. To preview a later time the app
fetches the entity once and renders here. The tests prove both give the same colours.
"""

from datetime import datetime, timedelta

import jinja2.sandbox

from . import generate
from .model import LIST_LAYOUTS


_NO_DEFAULT = object()


def _as_timestamp(value, default=_NO_DEFAULT):
    """Home Assistant's as_timestamp: a datetime or an ISO text to seconds, or the default when it is not one."""
    try:
        return (value if isinstance(value, datetime) else datetime.fromisoformat(str(value))).timestamp()
    except (TypeError, ValueError):
        if default is _NO_DEFAULT:
            raise ValueError(f"as_timestamp got {value!r}") from None
        return default


def render(template, states, attrs, now):
    """Renders with the Home Assistant helpers the ring templates use."""
    env = jinja2.sandbox.ImmutableSandboxedEnvironment()
    env.globals.update(
        now=lambda: now,
        states=lambda e: states.get(e, "unknown"),
        state_attr=lambda e, a: attrs.get(e, {}).get(a),
        as_timestamp=_as_timestamp,
    )
    return env.from_string(template).render().strip()


def needed(ring):
    """Every entity a design reads, so the preview can fetch them all."""
    out = [ring.entity, ring.entity2] + [p[0] for p in ring.parts]
    if ring.layout == "day_arc":
        out.append("sun.sun")
    return list(dict.fromkeys(e for e in out if e))


COMPASS = ("N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW")


class Snapshot:
    """The entities a design reads, as Home Assistant reported them: enough to render and explain any moment.
    `states` is entity_id -> {"state", "attributes"}; one such dict alone is taken as the design's entity."""

    def __init__(self, clock, states):
        if isinstance(states, dict) and ("state" in states or "attributes" in states):
            states = {clock.ring.entity: states}
        self.clock, self.all = clock, {k: v or {} for k, v in (states or {}).items()}
        r = clock.ring
        main = self.all.get(r.entity, {})
        self.state, self.attrs = main.get("state", "unknown"), main.get("attributes", {}) or {}
        self.items = [i for a in (r.attrs if r.layout in LIST_LAYOUTS else []) for i in self.attrs.get(a) or []
                      if isinstance(i, dict)]
        self.timed = bool(r.layout in LIST_LAYOUTS and r.t_start and self.items) or r.layout in ("hands", "day_arc")

    def times(self, now):
        """Moments for the time slider: the item starts ahead, or every half hour for the clock faces."""
        if self.clock.ring.layout in ("hands", "day_arc"):
            first = now.replace(minute=0 if now.minute < 30 else 30, second=0, microsecond=0)
            return [now] + [first + timedelta(minutes=30 * i) for i in range(1, 49)]
        if not self.timed:
            return [now]
        starts = (self._t(item, self.clock.ring.t_start) for item in self.items)
        return [now] + sorted(t for t in starts if t and t > now)

    @staticmethod
    def _t(item, key):
        try:
            return datetime.fromisoformat(str(item.get(key)))
        except (TypeError, ValueError):
            return None

    def colors(self, at):
        s = render(generate.jinja(self.clock), {e: v.get("state", "unknown") for e, v in self.all.items()},
                   {e: v.get("attributes", {}) or {} for e, v in self.all.items()}, at)
        n = self.clock.hw.leds
        if len(s) != n * 6:
            raise ValueError(f"The template returned {len(s)} characters instead of {n * 6}.")
        return ["#" + s[i:i + 6] for i in range(0, n * 6, 6)]

    def _value(self, entity, attr):
        st = self.all.get(entity, {})
        v = (st.get("attributes") or {}).get(attr) if attr else st.get("state")
        return "unknown" if v is None else v

    def shown(self, value, unit=None):
        """A value as people read it: its meaning, its step name, or the number with its unit."""
        r, unit = self.clock.ring, self.unit if unit is None else unit
        label = r.labels.get(str(value)) if r.colour_by == "values" else step_name(r, value)
        number = f"{value:g} {unit}".strip() if isinstance(value, (int, float)) and not isinstance(value, bool) \
            else f"{value} {unit}".strip() if r.colour_by != "values" else str(value)
        return f"{label} ({number})" if label else number

    def _pos(self, k):
        hw, n = self.clock.hw, self.clock.hw.leds
        return ((k - hw.start_led) if hw.clockwise else (hw.start_led - k)) % n

    def details(self, at, today=None):
        """One line per LED: what it shows. Days are named relative to `today` (the real current time), not to
        the moment being previewed."""
        today = today or at
        r, n = self.clock.ring, self.clock.hw.leds
        layout = r.layout
        if layout == "hands":
            return hand_details(n, at, self.clock.hw.start_led, self.clock.hw.clockwise, r.dim)
        if layout == "dial_24h":
            return self.dial_details(at, today)
        if layout == "from_now":
            return self.list_details(at, today)
        if layout == "week":
            return self.week_details(at)
        if layout == "day_arc":
            return self.arc_details(at)
        if layout == "segments":
            per = max(n // max(len(r.parts), 1), 1)
            out = []
            for k in range(n):
                si = self._pos(k) // per
                if si >= len(r.parts) or (per >= 3 and self._pos(k) % per == per - 1):
                    out.append("Gap")
                    continue
                e, a, name = (list(r.parts[si]) + ["", ""])[:3]
                unit = (self.all.get(e, {}).get("attributes") or {}).get("unit_of_measurement") or ""
                out.append(f"{name or e} · {self.shown(self._value(e, a), unit)}")
            return out
        if layout == "countdown":
            v = self._value(r.entity, r.value_attr)
            try:
                mins = float(v)
            except (TypeError, ValueError):
                when = self._t({"t": v}, "t")
                mins = (when - at).total_seconds() / 60 if when else None
            if mins is None:
                return ["Nothing to count down to"] * n
            return [f"{p + 1} min" + (" left" if p == 0 else "") if p < mins else "Free" for p in map(self._pos, range(n))]
        if layout == "compass":
            try:
                bearing = float(self._value(r.entity, r.value_attr)) % 360
            except (TypeError, ValueError):
                return ["No direction yet"] * n
            at_led = round(bearing / 360 * n) % n
            second = ""
            if r.entity2:
                unit = (self.all.get(r.entity2, {}).get("attributes") or {}).get("unit_of_measurement") or ""
                second = ", " + self.shown(self._value(r.entity2, r.value2_attr), unit)
            word = COMPASS[round(bearing / 22.5) % 16]
            return [f"{word} ({bearing:g}°){second}" if self._pos(k) == at_led
                    else ["North", "East", "South", "West"][self._pos(k) * 4 // n] if self._pos(k) * 4 % n == 0
                    else "Face" for k in range(n)]
        if layout in ("fill", "whole_ring"):
            return [self.shown(self._value(r.entity, r.value_attr))] * n
        return [""] * n

    def list_details(self, at, today):
        r, n = self.clock.ring, self.clock.hw.leds
        start = 0
        if self.timed:
            for i, item in enumerate(self.items):
                a, b = self._t(item, r.t_start), self._t(item, r.t_end)
                if a and b and a <= at < b:
                    start = i
                    break
        out = []
        for k in range(n):
            idx = start + self._pos(k)
            if idx >= len(self.items):
                out.append("No data yet")
                continue
            item = self.items[idx]
            when = self._t(item, r.t_start) if r.t_start else None
            shown = self.shown(item.get(r.key))
            out.append(f"{_when(when, today)} · {shown}" if when else f"Item {idx + 1} · {shown}")
        return out

    def week_details(self, at):
        r, n = self.clock.ring, self.clock.hw.leds
        midnight = at.replace(hour=0, minute=0, second=0, microsecond=0)
        out = []
        for k in range(n):
            pos = self._pos(k)
            d = int(pos * 7 / n)
            if n >= 14 and int((pos + 1) * 7 / n) != d:
                out.append("Gap")
                continue
            day = midnight + timedelta(days=d)
            item = next((i for i in self.items if (t := self._t(i, r.t_start))
                         and int((t.timestamp() - midnight.timestamp()) // 86400) == d), None)
            name = "Today" if d == 0 else "Tomorrow" if d == 1 else f"{day:%A}"
            out.append(f"{name} · {self.shown(item.get(r.key))}" if item else f"{name} · nothing")
        return out

    def arc_details(self, at):
        n = self.clock.hw.leds
        sun_attrs = self.all.get("sun.sun", {}).get("attributes") or {}
        midnight = at.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()

        def frac(key):
            t = self._t(sun_attrs, key)
            return ((t.timestamp() - midnight) % 86400) / 86400 if t else None

        rise, fall = frac("next_rising"), frac("next_setting")
        now_led = int((at.timestamp() - midnight) / 86400 * n) % n
        out = []
        for k in range(n):
            pos = self._pos(k)
            hour = f"{int(pos * 24 / n):02d}:{int(pos * 1440 / n) % 60:02d}"
            if pos == now_led:
                out.append(f"Now, {at:%H:%M}")
            elif rise is not None and pos == round(rise * n) % n:
                out.append(f"Sunrise, {int(rise * 24):02d}:{int(rise * 1440) % 60:02d}")
            elif fall is not None and pos == round(fall * n) % n:
                out.append(f"Sunset, {int(fall * 24):02d}:{int(fall * 1440) % 60:02d}")
            elif rise is None or fall is None:
                out.append(hour)
            else:
                f = pos / n
                day = rise <= f < fall if rise < fall else (f >= rise or f < fall)
                out.append(f"{hour} · {'Day' if day else 'Night'}")
        return out

    def _item_at(self, start):
        r = self.clock.ring
        return next((i for i in self.items if (t := self._t(i, r.t_start)) and start <= t < start + timedelta(hours=1)),
                    None)

    def dial_details(self, at, today):
        """The 24-hour dial: LED k always shows the hour floor(k * 24 / n), from the next 24 hours."""
        r, n = self.clock.ring, self.clock.hw.leds
        hour0 = at.replace(minute=0, second=0, microsecond=0)
        out = []
        for k in range(n):
            hour = int(self._pos(k) * 24 / n)
            start = hour0 + timedelta(hours=(hour - at.hour) % 24)
            item = self._item_at(start) or (self._item_at(start + timedelta(hours=1)) if start == hour0 else None)
            span = f"{hour:02d}-{(hour + 1) % 24:02d}"
            if item is None:
                out.append(f"{span} · no data yet")
                continue
            out.append(f"{span} {_when(start, today).split(' ')[0]} · {self.shown(item.get(r.key))}")
        return out

    @property
    def unit(self):
        """The entity's own unit, as Home Assistant reports it."""
        return str(self.attrs.get("unit_of_measurement") or "")


def step_name(ring, value):
    """The name of the step a number falls in, when the ring is coloured by named steps."""
    if ring.colour_by != "steps" or not ring.steps:
        return None
    try:
        x = float(value) * ring.scale
    except (TypeError, ValueError):
        return None
    name = None
    for start, _, label in ring.steps:
        if x >= start:
            name = label
    return name or None


def _when(t, now):
    day = "Today" if t.date() == now.date() else "Tomorrow" if t.date() == (now + timedelta(days=1)).date() \
        else t.strftime("%a")
    return f"{day} {t:%H:%M}"


def hand_positions(n, at):
    """Where the hour and minute hands point, counted clockwise from 12 o'clock (same maths as the template)."""
    hour = round(((at.hour % 12) * 60 + at.minute) / 720 * n) % n
    minute = round(at.minute / 60 * n) % n
    return hour, minute


def hand_details(n, at, start, clockwise, marks):
    hour, minute = hand_positions(n, at)
    out = []
    for k in range(n):
        pos = ((k - start) if clockwise else (start - k)) % n
        mark = marks > 0 and pos * 4 % n == 0
        out.append(f"Hour hand, {at:%H:%M}" if pos == hour else f"Minute hand, {at:%H:%M}" if pos == minute
                   else f"Quarter mark, {pos * 12 // n or 12} o'clock" if mark else "Face")
    return out
