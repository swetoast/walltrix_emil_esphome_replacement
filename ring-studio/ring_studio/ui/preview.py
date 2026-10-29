"""The ring on the right: live from Home Assistant, worked out for a later time, or on sample data."""

import threading

import flet as ft

from .. import generate, sample, sun
from ..model import LIST_LAYOUTS, to_hex
from ..render import Snapshot, needed
from .kit import (ACCENT, FACE, FAINT, GREEN, LINE, SUB, button, caption, day_name, dim, link, now, num, ring_view,
                  status_dot, text)


def stop_values(r):
    """The value each gradient colour sits at. Without set values they spread evenly from low to high."""
    if r.stops_at and len(r.stops_at) == len(r.palette):
        return list(r.stops_at)
    n = len(r.palette)
    return [r.lo + (r.hi - r.lo) * i / max(n - 1, 1) for i in range(n)]


class Preview:
    def schedule_preview(self, delay=0.6):
        if self.timer:
            self.timer.cancel()
        self.timer = threading.Timer(delay, self.render_preview)
        self.timer.daemon = True
        self.timer.start()

    def render_preview(self):
        """Fetches every entity the design reads once, then paints. Moving the time slider only repaints.
        Entities that do not exist yet (or everything, before Home Assistant is connected) get sample data."""
        c = self.clock
        if not c:
            return
        try:
            want = needed(c.ring)
            states, have = {}, {s["entity_id"] for s in self.states} if self.connected else set()
            if self.connected:
                for e in want:
                    if e in have:
                        states[e] = self.ha.state(e)
            else:
                known = sample.catalogue(now())
                states = {e: known[e] for e in want if e in known}
            missing = [e for e in want if e not in states]
            states.update(sample.fake(c.ring, now(), set(states)))
            if c.ring.layout == "day_arc" and "sun.sun" not in states:
                states["sun.sun"] = sample_sun()
            self.sample_for = missing
            self.snap = Snapshot(c, states)
            self.times = self.snap.times(now())
            self.at = min(self.at, len(self.times) - 1)
        except (RuntimeError, ValueError) as err:
            self.snap, self.preview_colors, self.preview_note = None, None, str(err)
        self.paint()

    def paint(self):
        with self.painting:
            self._paint()

    def _paint(self):
        c = self.clock
        if not c or not self.snap:
            self.preview.controls = self.preview_view()
            self.page.update()
            return
        try:
            if self.at == 0 and self.connected and not self.sample_for:
                s, n = self.ha.render(generate.jinja(c)), c.hw.leds
                if len(s) != n * 6:
                    raise ValueError(f"The template returned {len(s)} characters instead of {n * 6}.")
                self.preview_colors = ["#" + s[i:i + 6] for i in range(0, n * 6, 6)]
                self.preview_note = "Live from Home Assistant"
            else:
                self.preview_colors = self.snap.colors(self.times[self.at])
                if self.sample_for and self.connected:
                    self.preview_note = (f"Sample data: {', '.join(self.sample_for)} is not in Home Assistant yet")
                elif self.connected:
                    self.preview_note = "Worked out from Home Assistant data"
                else:
                    self.preview_note = "Sample data. Connect Home Assistant to see your own."
            self.lines = self.snap.details(self.times[self.at], now())
        except (RuntimeError, ValueError) as err:
            self.preview_colors, self.lines, self.preview_note = None, [], str(err)
        self.preview.controls = self.preview_view()
        self.page.update()

    def back_to_now(self, _=None):
        self.at, self.sent = 0, False
        self.page.run_thread(self.paint)

    def send_to_clock(self, _=None):
        c, colors = self.clock, self.preview_colors

        def work():
            try:
                self.ha.show(c.colors_entity, "".join(x[1:] for x in colors))
                self.sent = True
            except RuntimeError as err:
                self.toast(str(err))
            self.paint()
        self.page.run_thread(work)

    def stop_sending(self, _=None):
        c = self.clock

        def work():
            try:
                self.ha.update(c.colors_entity)
            except RuntimeError as err:
                self.toast(str(err))
            self.sent = False
            self.at = 0
            self.paint()
        self.page.run_thread(work)

    def preview_view(self):
        c = self.clock
        if not c:
            return []
        colors = self.preview_colors if self.preview_colors and len(self.preview_colors) == c.hw.leds \
            else [FACE] * c.hw.leds
        live = bool(self.preview_colors)
        timed = self.snap is not None and len(self.times) > 1
        at = self.times[self.at] if timed else None
        d, glow, loc = c.dimming, None, self.place
        if live and loc and d.enabled:
            level = min(sun.at(d, loc[0], loc[1], at or now()), c.hw.max_brightness)
            glow = f"Brightness {level} of {min(d.high, c.hw.max_brightness)}" if level else \
                f"Off at night, {d.night_start:02d}:00 to {d.night_end:02d}:00"
            colors = [dim(col, level / max(min(d.high, c.hw.max_brightness), 1)) for col in colors]
        centre = (f"{at:%H:%M}", ("Now · " if self.at == 0 else "") + day_name(at)) if timed else None
        dot_colour = (GREEN if self.connected and not self.sample_for else "#E9C46A") if live else FAINT
        out = [ring_view(colors, tips=self.lines if live else None, centre=centre,
                         first_big=c.ring.layout == "from_now"),
               self.legend(c),
               ft.Row([status_dot(dot_colour), text(self.preview_note, 12, SUB, max_lines=3, width=300)], spacing=8,
                      tight=True)]
        if glow:
            out.append(ft.Row([ft.Icon(ft.Icons.LIGHT_MODE_OUTLINED, size=14, color=SUB), text(glow, 12, SUB)],
                              spacing=8, tight=True))
        if live:
            out.append(caption("Point at an LED to see what it shows."))
        if timed:
            def slide(e):
                self.at = int(e.control.value)
                self.page.run_thread(self.paint)
            last = self.times[-1]
            out.append(ft.Column([
                ft.Row([caption("Preview time"), text(f"{day_name(at)} {at:%H:%M}", 12)],
                       alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Slider(min=0, max=len(self.times) - 1, divisions=len(self.times) - 1,
                          value=min(self.at, len(self.times) - 1), active_color=ACCENT, on_change_end=slide),
                ft.Row([caption("Now"), caption(f"{day_name(last)} {last:%H:%M}")],
                       alignment=ft.MainAxisAlignment.SPACE_BETWEEN)]
                + ([ft.Row([link("Back to now", self.back_to_now, SUB)], alignment=ft.MainAxisAlignment.CENTER)]
                   if self.at else []), width=320, spacing=4))
        if live and self.sent:
            out.append(ft.Container(ft.Row([
                ft.Column([text("On the wall for now, as a try", 13, "#B5EAF0"),
                           caption("Back to normal at the next update, within a minute.")], spacing=2, expand=True),
                button("Stop", self.stop_sending)], spacing=12), width=320, bgcolor="#13282C", border_radius=12,
                border=ft.Border.all(1, "#2E5A63"), padding=ft.Padding.symmetric(horizontal=14, vertical=10)))
        elif live and self.connected and self.clock_on_ha(c):
            out.append(ft.Container(button("Try on clock", self.send_to_clock, icon=ft.Icons.ARROW_FORWARD),
                                    width=320, alignment=ft.Alignment.CENTER))
        return out

    def clock_on_ha(self, c):
        """True when the clock's colour sensor exists, so a try can be sent to it."""
        return any(s.get("entity_id") == c.colors_entity for s in self.states)

    def legend(self, c):
        """What the colours mean, under the ring."""
        r = c.ring
        if r.layout == "hands":
            stops = len(r.palette)
            items = [(to_hex(r.palette[round(h / 24 * stops) % stops]), f"{h:02d}:00") for h in (0, 6, 12, 18)]
        elif r.layout == "day_arc":
            items = [(to_hex(r.colors.get(k, d)), label) for k, d, label in (
                ("day", [96, 72, 32], "Day"), ("night", [16, 20, 56], "Night"),
                ("sun", [255, 128, 48], "Sunrise, sunset"), ("now", [255, 255, 255], "Now"))]
        elif r.layout == "raw":
            items = []
        elif r.colour_by == "values":
            items = [(to_hex(v), r.labels.get(k) or k or "Empty") for k, v in r.colors.items()][:10]
            if r.layout in LIST_LAYOUTS + ("segments",) and r.fallback and not r.colors:
                items.append((to_hex(r.fallback), "Any value"))
        elif r.colour_by == "steps" and r.steps:
            items = [(to_hex(colour), f"{name} from {start:g}" if name else f"from {start:g}")
                     for start, colour, name in r.steps]
            if r.below:
                items.append((to_hex(r.below), f"below {r.steps[0][0]:g}"))
        else:
            at = stop_values(r)
            pick_ = range(len(at)) if len(at) <= 5 else (0, len(at) // 2, len(at) - 1)
            items = [(to_hex(r.palette[i]), num(at[i])) for i in pick_]
            if r.below:
                items.append((to_hex(r.below), f"below {at[0]:g}"))
        chips = [ft.Row([ft.Container(width=10, height=10, border_radius=5, bgcolor=col,
                                      border=ft.Border.all(1, LINE)), text(t, 12, SUB)],
                        spacing=6, tight=True) for col, t in items]
        return ft.Row(chips, wrap=True, spacing=14, run_spacing=8, width=320, alignment=ft.MainAxisAlignment.CENTER)


def sample_sun():
    """sun.sun for the preview before Home Assistant is connected: sunrise 07:30, sunset 16:45 today."""
    from datetime import timedelta
    t = now()
    rise = t.replace(hour=7, minute=30, second=0, microsecond=0)
    fall = t.replace(hour=16, minute=45, second=0, microsecond=0)
    rise, fall = (rise if rise > t else rise + timedelta(days=1)), (fall if fall > t else fall + timedelta(days=1))
    return {"state": "above_horizon" if rise > fall else "below_horizon",
            "attributes": {"next_rising": rise.isoformat(), "next_setting": fall.isoformat()}}
