"""New design: nine setups that find their own data, plus Blank. Pick one, answer a question or two, check the
ring, create."""

from dataclasses import replace

import flet as ft

from .. import sample, setups
from ..model import new_clock
from ..render import Snapshot, needed
from .kit import (CARD, FACE, FAINT, GREEN, LINE, LIFT, SUB, TOP_EDGE, button, caption, edited, info, link, note,
                  now, pick, ring_view, segmented, text)
from .preview import sample_sun


class NewDesign:
    def new_design_dialog(self, idx=None):
        """A new design for a clock. It opens straight away; the clock keeps showing its current design until
        this one is applied."""
        idx = self.idx if idx is None or not isinstance(idx, int) else idx
        if not self.project.clocks:
            self.project.clocks.append(new_clock("My Clock"))
            idx = 0
        device = self.project.clocks[idx]
        states = self.state_map
        ui = {"key": None, "answers": {}, "pick": 0}
        holder = ft.Container(width=760)
        create = button("Create", None, primary=True)
        back = button("Back", None)
        found_cache = {}

        def status(key):
            if key not in found_cache:
                found_cache[key] = setups.status(key, states)
            return found_cache[key]

        def gallery():
            tiles = []
            for key, s in setups.SETUPS.items():
                ok, line = status(key)
                swatch = [ft.Container(width=14, height=14, border_radius=7, bgcolor=col, border=ft.Border.all(1, LINE))
                          for col in s.swatch] or [ft.Icon(ft.Icons.ADD, color=SUB, size=14)]
                tiles.append(ft.Container(ft.Column([
                    ft.Row(swatch, spacing=4), text(s.title, 15, weight=ft.FontWeight.W_600), caption(s.sub),
                    text(line, 12, GREEN if ok else FAINT, max_lines=2)], spacing=6, tight=True),
                    width=238, height=132, padding=16, bgcolor=CARD, border_radius=14, border=TOP_EDGE, shadow=LIFT,
                    ink=True, on_click=lambda _, key=key: open_setup(key)))
            words = ("Each one looks through your Home Assistant for its data." if self.connected else
                     "Each one looks for its data. Until Home Assistant is connected, that is the example data.")
            holder.content = ft.Column([
                text(f"{words} The clock keeps showing {device.design.name} until you apply the new design.",
                     color=SUB),
                ft.Row(tiles, wrap=True, spacing=12, run_spacing=12)], spacing=16, tight=True)
            create.visible = back.visible = False

        def open_setup(key):
            ui.update(key=key, answers=setups.defaults(key), pick=0)
            if key == "blank":
                make()
                return
            questions()
            self.page.update()

        def answer(qkey, value):
            ui["answers"][qkey] = value
            ui["pick"] = 0
            questions()
            self.page.update()

        def questions():
            key, s = ui["key"], setups.SETUPS[ui["key"]]
            cands = setups.find(key, ui["answers"], states)
            cand = cands[min(ui["pick"], len(cands) - 1)] if cands else None
            parts = [ft.Row([ft.IconButton(ft.Icons.ARROW_BACK, icon_color=SUB, tooltip="All setups",
                                           on_click=lambda _: (gallery(), self.page.update())),
                             text(s.title, 20, weight=ft.FontWeight.W_700)], spacing=6)]
            for q in s.questions:
                parts.append(ft.Column([caption(q.label), segmented(dict(q.options), ui["answers"][q.key],
                                                                    lambda v, k=q.key: answer(k, v))],
                                       spacing=6, tight=True))
            if key == "board" and cands:
                names = [p[2] for p in setups.board_parts(ui["answers"]["show"], states)]
                parts.append(ft.Column([caption(f"{len(names)} found, all picked. Change them after creating."),
                                        text(", ".join(names), 13, SUB)], spacing=4, tight=True))
            elif s.pick and cands:
                options = {str(i): c.label for i, c in enumerate(cands[:40])}
                parts.append(ft.Column([pick(s.pick, str(ui["pick"]), options,
                                             lambda v: (ui.__setitem__("pick", int(v)), questions(),
                                                        self.page.update()), 420),
                                        caption(f"{len(cands)} match. The best one is picked; change it here."
                                                if len(cands) > 1 else "Found one, picked for you.")],
                                       spacing=4, tight=True))
            if not cands and key != "clock":
                parts.append(note(f"Nothing found for this. It needs {s.needs}." if s.needs else "Nothing found."))
            if cand and cand.source and cand.entity not in states:
                parts.append(info(f"Adds {cand.entity}: Home Assistant only hands out forecasts and calendar events "
                                  "to actions, so a small package makes this sensor. Add it once; Save YAML files "
                                  "writes it too.", ft.Icons.EXTENSION_OUTLINED,
                                  ("Copy package", lambda _: self.copy(setups.package(
                                      [f"{cand.source} {made_kind(key, ui['answers'])}"]), "the package"))))
            parts.append(text(setups.sentence(key, ui["answers"]), 14))
            ring = preview(key, cand)
            holder.content = ft.Row([ft.Column(parts, spacing=16, tight=True, expand=True),
                                     ft.Column([ring, caption("With your data" if self.connected and cand and
                                                              cand.entity in states else "With sample data")],
                                               horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10)],
                                    spacing=24, vertical_alignment=ft.CrossAxisAlignment.START)
            create.visible = back.visible = True
            create.disabled = key == "board" and not cands
            ui["cand"] = cand

        def preview(key, cand):
            try:
                d = setups.build(key, ui["answers"], cand, states)
                c = replace(device, designs=[d], active=0, ring=None)
                data = {e: states[e] for e in needed(d.ring) if e in states}
                data.update(sample.fake(d.ring, now(), set(data)))
                if d.ring.layout == "day_arc" and "sun.sun" not in data:
                    data["sun.sun"] = sample_sun()
                colours = Snapshot(c, data).colors(now())
            except (ValueError, RuntimeError, KeyError, TypeError):
                colours = [FACE] * device.hw.leds
            return ring_view(colours, size=220, first_big=False)

        def make(_=None):
            d = setups.build(ui["key"], ui["answers"], ui.get("cand"), states)
            names = {x.name for x in device.designs}
            base, n = d.name, 2
            while d.name in names:
                d.name, n = f"{base} {n}", n + 1
            device.designs.append(d)
            self.close()
            edited()
            self.select(idx, len(device.designs) - 1)

        create.on_click = make
        back.on_click = lambda _: (gallery(), self.page.update())
        gallery()
        self.dialog(f"New design for {device.friendly}", holder, [link("Cancel", self.close, SUB), back, create],
                    780, scrollable=True)


def made_kind(key, answers):
    if key == "weather":
        return "daily" if answers.get("ring") == "week" else "hourly"
    if key == "week":
        return "week"
    return "hours"
