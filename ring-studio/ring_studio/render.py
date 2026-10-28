"""Renders a ring template on this computer, the way Home Assistant does, at any moment.

Home Assistant can only render a template at the current time. To preview a later time the app
fetches the entity once and renders here. The tests prove both give the same colours.
"""

from datetime import datetime, timedelta

import jinja2.sandbox

from . import generate
from .model import LIST_MODES


def render(template, states, attrs, now):
    """Renders with the Home Assistant helpers the ring templates use."""
    env = jinja2.sandbox.ImmutableSandboxedEnvironment()
    env.globals.update(
        now=lambda: now,
        states=lambda e: states.get(e, "unknown"),
        state_attr=lambda e, a: attrs.get(e, {}).get(a),
        as_timestamp=lambda s: datetime.fromisoformat(str(s)).timestamp(),
    )
    return env.from_string(template).render().strip()


class Snapshot:
    """One entity as Home Assistant reported it: enough to render and explain any moment."""

    def __init__(self, clock, state):
        self.clock, self.state = clock, state.get("state", "unknown")
        self.attrs = state.get("attributes", {})
        r = clock.ring
        self.items = [i for a in (r.attrs if r.mode in LIST_MODES else []) for i in self.attrs.get(a) or []
                      if isinstance(i, dict)]
        self.timed = bool(r.mode in LIST_MODES and r.t_start and self.items) or r.mode == "hands"

    def times(self, now):
        """Start times of the items from the one running now to the last, for the time slider."""
        if self.clock.ring.mode == "hands":  # every half hour through the next day
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
        s = render(generate.jinja(self.clock), {self.clock.ring.entity: self.state},
                   {self.clock.ring.entity: self.attrs}, at)
        n = self.clock.hw.leds
        if len(s) != n * 6:
            raise ValueError(f"The template returned {len(s)} characters instead of {n * 6}.")
        return ["#" + s[i:i + 6] for i in range(0, n * 6, 6)]

    def details(self, at, today=None):
        """One line per LED: which item or value it shows. Days are named relative to `today` (the real
        current time), not to the moment being previewed."""
        today = today or at
        r, n = self.clock.ring, self.clock.hw.leds
        if r.mode == "hands":
            return hand_details(n, at, r.start_led, r.clockwise, r.dim)
        if r.mode in LIST_MODES and r.dial == "24h":
            return self.dial_details(at, today)
        if r.mode not in LIST_MODES:
            value = self.attrs.get(r.value_attr) if r.value_attr else self.state
            value = "unknown" if value is None else str(value)
            label = r.labels.get(value) if r.mode == "state" else step_name(r, value)
            return [f"{label} ({value})" if label else f"{value} {self.unit}".strip()] * n
        start = 0
        if self.timed:
            for i, item in enumerate(self.items):
                a, b = self._t(item, r.t_start), self._t(item, r.t_end)
                if a and b and a <= at < b:
                    start = i
                    break
        out = []
        for k in range(n):
            if start + k >= len(self.items):
                out.append("No data yet")
                continue
            item = self.items[start + k]
            value = item.get(r.key)
            when = self._t(item, r.t_start) if r.t_start else None
            label = r.labels.get(str(value)) if r.mode == "states" else step_name(r, value)
            shown = f"{label} ({value:g} {self.unit})".replace(" )", ")") if label and isinstance(value, (int, float)) \
                else f"{label} ({value})" if label else f"{value:g} {self.unit}".strip() \
                if isinstance(value, (int, float)) else str(value)
            out.append(f"{_when(when, today)} · {shown}" if when else f"Item {start + k + 1} · {shown}")
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
            pos = ((k - r.start_led) if r.clockwise else (r.start_led - k)) % n
            hour = int(pos * 24 / n)
            start = hour0 + timedelta(hours=(hour - at.hour) % 24)
            item = self._item_at(start) or (self._item_at(start + timedelta(hours=1)) if start == hour0 else None)
            span = f"{hour:02d}-{(hour + 1) % 24:02d}"
            if item is None:
                out.append(f"{span} · no forecast yet")
                continue
            value = item.get(r.key)
            label = r.labels.get(str(value)) if r.mode == "states" else step_name(r, value)
            shown = f"{label} ({value})" if label else f"{value} {self.unit}".strip()
            out.append(f"{span} {_when(start, today).split(' ')[0]} · {shown}")
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
