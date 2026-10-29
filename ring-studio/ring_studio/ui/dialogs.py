"""The entity picker and the colour picker."""

import colorsys

import flet as ft

from .. import detect
from ..model import from_hex, to_hex
from .kit import (ACCENT, ACCENT_BG, BG, DOMAIN_ICONS, FAINT, LAYOUT_NAMES, LINE, MONO, PRESETS, SUB, SUNK, TEXT,
                  box, button, caption, edited, now, segmented, text)


class Dialogs:
    def entity_dialog(self, _=None, target="entity"):
        """Every entity Home Assistant has, with its attributes. The ones that fit come first. `target` is what
        the pick is for: the design's entity, the compass's colour entity (entity2), or a new segment (part).
        For the design's entity, the time is offered too, for the clock faces."""
        r = self.clock.ring
        layout = r.layout if target == "entity" else "fill" if target == "entity2" else "whole_ring"
        fit_name = {"entity2": "a number", "part": "a segment"}.get(target, LAYOUT_NAMES.get(layout, ("this",))[0])
        current = {"entity": r.entity, "entity2": r.entity2}.get(target, "")
        ui = {"query": "", "only": True, "picked": current}
        rows = ft.ListView(height=440, spacing=2)
        count = caption("")
        detail = ft.Column(spacing=10, scroll=ft.ScrollMode.AUTO, height=500)
        loaded = caption("")
        use = button("Use this entity", None, primary=True)
        pool_all = list(self.state_map.values()) if self.connected else \
            [{"entity_id": e, **s} for e, s in self.state_map.items()]

        def name_of(st):
            return (st.get("attributes") or {}).get("friendly_name") or st["entity_id"]

        def fits(st):
            return detect.fits(layout, st) if target != "part" else st.get("state") not in (None, "unavailable")

        def paint_list():
            words = ui["query"].lower().split()
            pool = [st for st in pool_all if all(w in (st["entity_id"] + " " + name_of(st)).lower() for w in words)]
            fit = sorted((st for st in pool if fits(st)), key=name_of)
            shown = fit if ui["only"] else fit + sorted((st for st in pool if st not in fit), key=name_of)
            rows.controls = []
            if target == "entity" and (not words or any(w in "the time clock hands sun day" for w in words)):
                rows.controls.append(self.time_row(lambda: (self.close(), self.use_time())))
            rows.controls += [self.entity_row(st, st["entity_id"] == ui["picked"], fits(st),
                                              lambda st=st: pick(st["entity_id"])) for st in shown[:150]]
            count.value = (f"{len(shown)} {'entity' if len(shown) == 1 else 'entities'}" if len(shown) <= 150 else
                           f"Showing 150 of {len(shown)}. Type to narrow it down.") + \
                (f" that suit {fit_name}." if ui["only"] else ".")
            if not shown and ui["only"]:
                count.value = f"Nothing here suits {fit_name}. Switch to All entities."

        def paint_detail():
            st = next((s for s in pool_all if s["entity_id"] == ui["picked"]), None)
            use.disabled = not st
            if not st:
                detail.controls = [text("Pick an entity on the left to see its data.", color=SUB)]
                return
            _, words = detect.guess(layout, st)
            attrs = [ft.Container(ft.Column([
                ft.Row([text(n, 13, mono=True, weight=ft.FontWeight.W_600), text(v, 12, SUB, expand=True)],
                       spacing=10, vertical_alignment=ft.CrossAxisAlignment.START)]
                + ([text(sample, 11, FAINT, mono=True)] if sample else []), spacing=2, tight=True),
                padding=ft.Padding.symmetric(vertical=6)) for n, v, sample in detect.attribute_rows(st)]
            detail.controls = [
                text(name_of(st), 18, weight=ft.FontWeight.W_700), text(st["entity_id"], 12, SUB, mono=True),
                ft.Row([text("Now", 12, FAINT), text(detect.shown_value(st), 14)], spacing=10)] + (
                [ft.Container(ft.Row([ft.Icon(ft.Icons.AUTO_FIX_HIGH, size=16, color=ACCENT),
                                      text(words, 12, TEXT, expand=True)], spacing=8,
                                     vertical_alignment=ft.CrossAxisAlignment.START),
                              bgcolor=ACCENT_BG, border_radius=10, padding=12)] if words and target == "entity" else []
            ) + [caption("Attributes")] + (attrs or [text("No attributes.", 12, SUB)])

        def pick(entity_id):
            ui["picked"] = entity_id
            paint_list()
            paint_detail()
            self.page.update()

        def search(e):
            ui["query"] = e.control.value or ""
            paint_list()
            rows.update()
            count.update()

        def scope(v):
            ui["only"] = v == "fit"
            paint_list()
            filters.content = seg()
            self.page.update()

        def seg():
            return segmented({"fit": f"Suits {fit_name}", "all": "All entities"}, "fit" if ui["only"] else "all",
                             scope)

        def reload(_):
            def work():
                loaded.value = "Loading…"
                self.page.update()
                try:
                    self.states = self.ha.states()
                    pool_all[:] = self.states
                    loaded.value = f"{len(self.states)} entities, loaded {now():%H:%M}"
                except RuntimeError as err:
                    loaded.value = str(err)
                paint_list()
                paint_detail()
                self.page.update()
            self.page.run_thread(work)

        def done(_):
            self.close()
            chosen = ui["picked"]
            if target == "entity":
                self.use_entity(chosen)
            elif target == "entity2":
                r.entity2, r.value2_attr = chosen, ""
                if r.colour_by == "values":
                    r.colour_by = "gradient"
                self.refresh_editor()
            else:
                st = next((s for s in pool_all if s["entity_id"] == chosen), {})
                r.parts.append([chosen, "", name_of(st)[:40] if st else chosen.split(".")[1]])
                self.add_states([str(st.get("state"))] if st and r.colour_by == "values" else [])
                self.refresh_editor()

        use.on_click = done
        filters = ft.Container(seg())
        loaded.value = (f"{len(pool_all)} entities from Home Assistant" if self.connected else
                        "Example entities with sample data. Connect Home Assistant for your own.")
        paint_list()
        paint_detail()
        left = ft.Column([box(hint_text="Search by name or entity ID", autofocus=True, on_change=search, width=430,
                              prefix_icon=ft.Icons.SEARCH),
                          ft.Row([filters], spacing=8), count, rows], spacing=10, width=430)
        right = ft.Container(detail, width=440, bgcolor=SUNK, border_radius=14, padding=18)
        title = {"entity2": "Colour the pointer by", "part": "Add a part"}.get(target, "Choose what the ring shows")
        self.dialog(title, ft.Column([
            ft.Row([loaded, ft.Container(expand=True)] + (
                [ft.TextButton("Reload from Home Assistant", icon=ft.Icons.REFRESH, on_click=reload,
                               style=ft.ButtonStyle(color=SUB))] if self.connected else [])),
            ft.Row([left, right], spacing=20, vertical_alignment=ft.CrossAxisAlignment.START)], spacing=8, tight=True),
            [button("Cancel", self.close), use], 900)

    def time_row(self, on_pick):
        on = self.clock.ring.layout in ("hands", "day_arc")
        return ft.Container(ft.Row([
            ft.Icon(ft.Icons.SCHEDULE, size=18, color=ACCENT),
            ft.Column([text("The time", 13, TEXT), text("Clock hands or the day arc, no entity needed", 11, FAINT)],
                      spacing=1, tight=True, expand=True)], spacing=12),
            bgcolor=ACCENT_BG if on else None, border=ft.Border.all(1, ACCENT if on else BG), border_radius=10,
            padding=ft.Padding.symmetric(horizontal=12, vertical=8), ink=True, on_click=lambda _: on_pick())

    def entity_row(self, st, picked, fits, on_pick):
        domain = st["entity_id"].split(".")[0]
        name = (st.get("attributes") or {}).get("friendly_name") or st["entity_id"]
        return ft.Container(ft.Row([
            ft.Icon(DOMAIN_ICONS.get(domain, ft.Icons.CIRCLE_OUTLINED), size=18, color=ACCENT if fits else FAINT),
            ft.Column([text(name, 13, TEXT if fits else SUB, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                       text(st["entity_id"], 11, FAINT, mono=True, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)],
                      spacing=1, tight=True, expand=True),
            text(detect.shown_value(st), 12, SUB, max_lines=1, width=110, text_align=ft.TextAlign.RIGHT)],
            spacing=12), bgcolor=ACCENT_BG if picked else None, border=ft.Border.all(1, ACCENT if picked else BG),
            border_radius=10, padding=ft.Padding.symmetric(horizontal=12, vertical=8), ink=True,
            on_click=lambda _: on_pick())

    def color_dialog(self, title, current, on_done, optional=False, remove=None, value=None):
        """Pick any colour: hue, saturation and brightness sliders, a hex value, recent colours and presets.
        With `value`, the dialog also edits the value the colour sits at, and on_done gets (colour, value)."""
        start = current or [255, 176, 0]
        h0, s0, v0 = colorsys.rgb_to_hsv(*[c / 255 for c in start])
        hsv = {"h": h0 * 360, "s": s0 * 100, "v": v0 * 100}
        swatch = ft.Container(width=96, height=96, border_radius=48, border=ft.Border.all(2, LINE))
        on_ring = [ft.Container(width=16, height=16, border_radius=8) for _ in range(5)]
        hexbox = box(value=to_hex(start).upper(), width=130, text_style=ft.TextStyle(font_family=MONO))
        at = box(value=f"{value:g}" if value is not None else "", width=130, text_style=ft.TextStyle(font_family=MONO))
        tracks = {k: ft.Container(height=12, border_radius=6) for k in "hsv"}
        sliders = {}

        def rgb(h=None, s_=None, v=None):
            h = hsv["h"] if h is None else h
            s_ = hsv["s"] if s_ is None else s_
            v = hsv["v"] if v is None else v
            return [round(x * 255) for x in colorsys.hsv_to_rgb((h % 360) / 360, s_ / 100, v / 100)]

        def grad(cols):
            return ft.LinearGradient(colors=[to_hex(c) for c in cols], begin=ft.Alignment.CENTER_LEFT,
                                     end=ft.Alignment.CENTER_RIGHT)

        def paint(from_hex_box=False):
            c = to_hex(rgb())
            swatch.bgcolor = c
            swatch.shadow = ft.BoxShadow(blur_radius=24, color=ft.Colors.with_opacity(0.6, c))
            for dot_, f in zip(on_ring, (1, 0.75, 0.55, 0.4, 0.25)):
                dot_.bgcolor = to_hex([x * f for x in rgb()])
            tracks["h"].gradient = grad([rgb(h=x) for x in range(0, 361, 60)])
            tracks["s"].gradient = grad([rgb(s_=0), rgb(s_=100)])
            tracks["v"].gradient = grad([[0, 0, 0], rgb(v=100)])
            if not from_hex_box:
                hexbox.value, hexbox.error = c.upper(), None

        def slide(key):
            def changed(e):
                hsv[key] = e.control.value
                paint()
                self.page.update()
            return changed

        def set_rgb(c, from_box=False):
            h, s_, v = colorsys.rgb_to_hsv(*[x / 255 for x in c])
            hsv.update(h=h * 360, s=s_ * 100, v=v * 100)
            for k in "hsv":
                sliders[k].value = hsv[k]
            paint(from_hex_box=from_box)
            self.page.update()

        def typed(e):
            try:
                set_rgb(from_hex(e.control.value.strip()), True)
            except ValueError:
                pass

        def finish(colour):
            got = None
            if value is not None:
                try:
                    got = float(at.value.replace(",", "."))
                except ValueError:
                    at.error = "A number"
                    at.update()
                    return
            self.close()
            if colour:
                self.recent[:] = [colour] + [c for c in self.recent if c != colour][:9]
            on_done(colour, got) if value is not None else on_done(colour)
            edited()

        def apply(_):
            try:
                finish(from_hex(hexbox.value.strip()))
            except ValueError:
                hexbox.error = "Use #RRGGBB"
                hexbox.update()

        hexbox.on_change = typed
        rows = []
        for key, label, top in (("h", "Hue", 360), ("s", "Saturation", 100), ("v", "Brightness", 100)):
            sliders[key] = ft.Slider(min=0, max=top, value=max(0, min(top, hsv[key])),
                                     active_color=ft.Colors.TRANSPARENT, thumb_color="#FFFFFF",
                                     inactive_color=ft.Colors.TRANSPARENT, on_change=slide(key))
            rows.append(ft.Column([caption(label),
                                   ft.Container(tracks[key], padding=ft.Padding.symmetric(horizontal=24)),
                                   ft.Container(sliders[key], margin=ft.Margin.only(top=-14))], spacing=4, tight=True))
        paint()

        def chips(cols):
            return ft.Row([ft.Container(width=28, height=28, border_radius=8, bgcolor=to_hex(c),
                                        tooltip=to_hex(c).upper(), border=ft.Border.all(1, LINE), ink=True,
                                        on_click=lambda _, c=c: set_rgb(c))
                           for c in cols], wrap=True, spacing=8, run_spacing=8, width=470)

        top = ft.Row([swatch, ft.Column([caption("How it looks on the ring, brightest to dimmest"),
                                         ft.Row(on_ring, spacing=6),
                                         ft.Row([hexbox] + ([ft.Column([caption("At value"), at], spacing=4,
                                                                       tight=True)] if value is not None else []),
                                                spacing=14, vertical_alignment=ft.CrossAxisAlignment.END)],
                                        spacing=10, tight=True)], spacing=20)
        body = [top] + rows
        if self.recent:
            body.append(ft.Column([caption("Recent"), chips(self.recent)], spacing=8, tight=True))
        body.append(ft.Column([caption("Presets"), chips([from_hex(h) for h in PRESETS])], spacing=8, tight=True))
        actions = []
        if remove:
            actions.append(button("Remove", lambda _: (self.close(), remove()), danger=True))
        if optional:
            actions.append(button("No colour", lambda _: (self.close(), on_done(None), edited())))
        actions += [button("Cancel", self.close), button("Apply", apply, primary=True)]
        self.dialog(title, ft.Column(body, spacing=16, tight=True), actions, 520, scrollable=True)
