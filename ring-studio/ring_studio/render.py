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
        self.timed = bool(r.mode in LIST_MODES and r.t_start and self.items)

    def times(self, now):
        """Start times of the items from the one running now to the last, for the time slider."""
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

    def details(self, at):
        """One line per LED: which item or value it shows."""
        r, n = self.clock.ring, self.clock.hw.leds
        if r.mode not in LIST_MODES:
            label = r.labels.get(self.state) if r.mode == "state" else None
            return [f"{label} ({self.state})" if label else f"{self.state} {self.unit}".strip()] * n
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
            label = r.labels.get(str(value)) if r.mode == "states" else None
            shown = f"{label} ({value})" if label else f"{value:g} {self.unit}".strip() \
                if isinstance(value, (int, float)) else str(value)
            out.append(f"{_when(when, at)} · {shown}" if when else f"Item {start + k + 1} · {shown}")
        return out

    @property
    def unit(self):
        """The entity's own unit, as Home Assistant reports it."""
        return str(self.attrs.get("unit_of_measurement") or "")


def _when(t, now):
    day = "Today" if t.date() == now.date() else "Tomorrow" if t.date() == (now + timedelta(days=1)).date() \
        else t.strftime("%a")
    return f"{day} {t:%H:%M}"
