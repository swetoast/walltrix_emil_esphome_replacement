"""The design editor: a header, then three steps. Data says what the ring reads, Colours what each value looks
like, Ring where the colours go."""

import copy

import flet as ft

from .. import detect, project as projects, setups
from ..model import GRADIENTS as GRADIENTS_NAMES, LIST_LAYOUTS, from_hex, to_hex
from ..project import MAX_PARTS
from .kit import (ACCENT, ACCENT_BG, CARD, DOMAIN_ICONS, FADE, FAINT, GREEN, LAYOUT_NAMES, MARKERS,
                  ON_ACCENT, PRESETS, RAISED, SUB, SUNK, TEXT, WARN, attr, box, button, caption, card, dot,
                  edited, field, info, link, note, num, percent_slider, pick, segmented, template_hash, text, tile)
from .preview import stop_values

TIME_LAYOUTS = ("hands", "day_arc")
VALUE_LAYOUTS = ("fill", "whole_ring", "compass", "countdown")


def group_of(r):
    if r.layout in TIME_LAYOUTS:
        return TIME_LAYOUTS
    if r.layout in LIST_LAYOUTS:
        return LIST_LAYOUTS
    if r.layout == "segments":
        return ("segments",)
    if r.layout == "raw":
        return ("raw",)
    return VALUE_LAYOUTS if r.colour_by != "values" else ("whole_ring",)


class DesignEditor:
    def editor_view(self):
        c = self.clock
        if not c:
            return self.no_clocks()
        if self.design is None:
            return self.clock_page()
        r = c.ring
        parts = [self.design_header(c), self.step_card(1, "Data", self.data_summary(r), self.data_body(r))]
        if r.layout != "raw":
            parts += [self.step_card(2, "Colours", "", self.colours_body(r), self.colour_rule(r)),
                      self.step_card(3, "Ring", LAYOUT_NAMES[r.layout][0], self.ring_body(r))]
        return parts

    # ---------- header ----------
    def applied_state(self, device, i):
        """"on" when design i is on the clock as it is now, "changed" when it is on the clock but edited since,
        "off" when another design is on the clock."""
        if i != device.active:
            return "off"
        if not self.mark("applied", device):
            return "new"
        try:
            same = self.mark("applied", device) == template_hash(device.showing(i))
        except (ValueError, TypeError, KeyError):
            same = False
        return "on" if same else "changed"

    def design_header(self, c):
        """The design's name (click to rename), whether it is on the clock with Apply next to it, and one line
        on what it shows. The note is behind an icon."""
        device, d, i = self.device, self.design, self.didx
        if self.renaming:
            def commit(e):
                self.renaming = False
                new = projects.clean_label(e.control.value or "")
                if new and new != d.name:
                    if new in {x.name for x in device.designs if x is not d}:
                        self.toast(f"{device.friendly} already has a design called {new}.")
                    else:
                        d.name = new
                self.refresh_editor()
            name = box(value=d.name, width=460, text_size=24, autofocus=True, on_submit=commit, on_blur=commit,
                       content_padding=ft.Padding.symmetric(horizontal=12, vertical=8))
        else:
            name = ft.Container(text(d.name, 28, weight=ft.FontWeight.W_700), tooltip="Click to rename", ink=True,
                                border_radius=8, on_click=lambda _: (setattr(self, "renaming", True),
                                                                     self.refresh_editor()))
        state = self.applied_state(device, i)
        if state == "on":
            badge = ft.Row([ft.Icon(ft.Icons.CHECK_CIRCLE, size=16, color=GREEN),
                            text(f"On {device.friendly}", 13, GREEN)], spacing=6, tight=True)
        elif state == "changed":
            badge = ft.Row([ft.Icon(ft.Icons.EDIT_NOTE, size=18, color=WARN),
                            text(f"On {device.friendly}, changes not applied yet", 13, WARN)], spacing=6, tight=True)
        elif state == "new":
            badge = text(f"The design for {device.friendly}, not applied yet", 13, SUB)
        else:
            badge = text(f"Not on {device.friendly}, which shows {device.design.name}", 13, SUB)

        def duplicate(_):
            copy_ = copy.deepcopy(d)
            names = {x.name for x in device.designs}
            base, n = f"{d.name} copy", 2
            copy_.name = base
            while copy_.name in names:
                copy_.name, n = f"{base} {n}", n + 1
            device.designs.append(copy_)
            edited()
            self.select(self.idx, len(device.designs) - 1)

        def delete():
            device.designs.pop(i)
            if device.active > i:
                device.active -= 1
            edited()
            self.select(self.idx, device.active)

        can_delete = i != device.active and len(device.designs) > 1
        tools = ft.Row([
            ft.IconButton(ft.Icons.STICKY_NOTE_2 if d.note else ft.Icons.STICKY_NOTE_2_OUTLINED,
                          icon_color=ACCENT if d.note else SUB, tooltip=d.note or "Add a note, only for you",
                          on_click=lambda _: self.note_dialog(d, f"Note for {d.name}")),
            ft.IconButton(ft.Icons.CONTENT_COPY, icon_color=SUB, tooltip="Duplicate this design", on_click=duplicate),
            ft.IconButton(ft.Icons.DELETE_OUTLINE, icon_color=SUB, disabled=not can_delete,
                          tooltip="Delete this design" if can_delete else
                          "This design is on the clock. Apply another one first.",
                          on_click=lambda _: self.confirm("Delete design", f"Delete {d.name}? Undo brings it back.",
                                                          "Delete", delete))], spacing=0, tight=True)
        status = ft.Row([badge] + ([link("Apply to clock", self.apply_dialog)] if state != "on" else []), spacing=8)
        return ft.Column([ft.Row([name, ft.Container(expand=True), tools]), status,
                          text(self.sentence(c), color=SUB)], spacing=4)

    def note_dialog(self, obj, title):
        def done(_):
            self.close()
            self.refresh_editor()
        self.dialog(title, ft.Column([
            caption("Only for you. Kept in the project file, never sent to the clock or Home Assistant."),
            attr(obj, "note", "", width=520, multiline=True, min_lines=4, max_lines=10)], spacing=10, tight=True),
            [button("Done", done, primary=True)], 560)

    def sentence(self, c):
        """What the design does, in one line."""
        r = c.ring
        what = f"the {r.value_attr} attribute" if r.value_attr else "the entity's state"
        steps = f", in {len(r.steps)} named steps" if r.colour_by == "steps" and r.steps else ""
        source = " + ".join(r.attrs) or "a list"
        return {
            "hands": "An analog clock. The hands light up in the colour for the time of day.",
            "day_arc": "A 24-hour face: day lit, night dim, sunrise and sunset marked, and now in white.",
            "raw": "A hand-written template, kept exactly as it was.",
            "from_now": f"One LED per item in {source}, starting at now. The colour follows {r.key or 'a value'}"
                        f"{steps}.",
            "dial_24h": f"A 24-hour dial of {r.key or 'values'} from {source}, midnight at the top{steps}.",
            "week": f"Seven sections, today at the top, each coloured by {r.key or 'a value'} for that day{steps}.",
            "fill": f"The ring fills up as {what} goes from {r.lo:g} to {r.hi:g}{steps}.",
            "whole_ring": f"The whole ring takes the colour of {what}" + (
                ", one colour per value." if r.colour_by == "values" else f"{steps}."),
            "compass": f"One LED points where {what} says"
                       + (f", coloured by {r.entity2}." if r.entity2 else "."),
            "countdown": f"One LED per minute until {what}, clockwise from the top.",
            "segments": f"{len(r.parts)} part{'s' if len(r.parts) != 1 else ''}, each in its entity's colour.",
        }[r.layout]

    def step_card(self, n, title, summary, body, right=None):
        mark = ft.Icon(ft.Icons.CHECK, size=16, color=ON_ACCENT) if n == "✓" else \
            text(str(n), 13, ON_ACCENT, ft.FontWeight.W_700)
        badge = ft.Container(mark, width=26, height=26, border_radius=13,
                             bgcolor=ACCENT, alignment=ft.Alignment.CENTER)
        head = [badge, text(title, 17, weight=ft.FontWeight.W_600), ft.Container(expand=True)]
        head += [text(summary, 13, SUB)] if summary else []
        head += [right] if right else []
        return card(ft.Column([ft.Row(head, spacing=12), body], spacing=18),
                    padding=ft.Padding.only(left=24, right=24, top=20, bottom=24))

    def section(self, key, title, summary, body):
        def toggle(_):
            self.opened[key] = not self.opened[key]
            self.refresh_editor()

        head = ft.Container(ft.Row([text(title, 17, weight=ft.FontWeight.W_600), ft.Container(expand=True),
                                    text(summary, 13, SUB),
                                    ft.Icon(ft.Icons.EXPAND_LESS if self.opened[key] else ft.Icons.EXPAND_MORE,
                                            color=SUB)], spacing=12),
                            padding=ft.Padding.symmetric(horizontal=24, vertical=20), on_click=toggle, ink=True,
                            border_radius=16)
        parts = [head]
        if self.opened[key]:
            parts.append(ft.Container(body(), padding=ft.Padding.only(left=24, right=24, bottom=28)))
        return card(ft.Column(parts, spacing=0))

    def more(self, key, label, body):
        """A second level inside a step, closed until asked for."""
        def toggle(_):
            self.opened[key] = not self.opened[key]
            self.refresh_editor()

        head = ft.Container(ft.Row([ft.Icon(ft.Icons.EXPAND_LESS if self.opened[key] else ft.Icons.EXPAND_MORE,
                                            color=FAINT, size=18), text(label, 13, SUB)], spacing=6, tight=True),
                            on_click=toggle, ink=True, border_radius=8, padding=6)
        return ft.Column([head, body()] if self.opened[key] else [head], spacing=12)

    # ---------- 1 data ----------
    def data_state(self, entity_id):
        """The entity's data: from Home Assistant when connected, sample data otherwise."""
        if not entity_id:
            return {}
        return self.state_map.get(entity_id) or {}

    def data_summary(self, r):
        if r.layout in TIME_LAYOUTS:
            return "The time" + (" and sun.sun" if r.layout == "day_arc" else "")
        if r.layout == "raw":
            return "Hand-written template"
        if r.layout == "segments":
            return f"{len(r.parts)} of {MAX_PARTS} parts"
        if r.layout in LIST_LAYOUTS:
            return f"{' + '.join(r.attrs) or 'no list'} · {r.key or 'no value'}"
        return r.value_attr or ("state" if r.entity else "")

    def data_body(self, r):
        if r.layout == "raw":
            return ft.Column([note("This template was not recognised, so it is kept exactly as is. Change it in the "
                                   "YAML view, or start over with an entity."),
                              box(value=r.raw, multiline=True, read_only=True, min_lines=10, text_size=12),
                              button("Start over with an entity", lambda _: self.confirm(
                                  "Start over?", "The hand-written template is replaced. Undo brings it back.",
                                  "Start over", lambda: self.entity_dialog()))], spacing=16)
        if r.layout in TIME_LAYOUTS:
            words = ("Home Assistant's clock drives the ring, and sun.sun says when the sun rises and sets."
                     if r.layout == "day_arc" else "Home Assistant's clock drives the ring: the hour and minute "
                                                   "hands light up.")
            return ft.Column([self.source_card(ft.Icons.SCHEDULE, "The time", "No entity needed"),
                              caption(words)], spacing=10)
        if r.layout == "segments":
            return self.parts_editor(r)
        parts = [self.entity_card(r)]
        if r.made_from and not (self.connected and self.data_state(r.entity)):
            parts.append(self.made_from_note(r))
        st = self.data_state(r.entity)
        if st:
            parts += [caption("Click what the ring should show. Everything here comes from the entity's data."),
                      self.data_tree(r, st)]
        elif r.entity and not r.made_from:
            parts.append(note("No data for this entity yet. Connect Home Assistant, or set the fields under More."))
        if r.layout == "compass":
            parts.append(self.second_entity(r))
        parts.append(self.more("advanced", "More: set every field yourself", lambda: self.advanced(r)))
        return ft.Column(parts, spacing=14)

    def source_card(self, icon, title, sub, right=None, on_click=None):
        on_click = on_click or (lambda _: self.entity_dialog())
        return ft.Container(ft.Row([
            ft.Icon(icon, color=ACCENT, size=22),
            ft.Column([text(title, 15, weight=ft.FontWeight.W_600), text(sub, 12, SUB, mono=True)], spacing=2,
                      tight=True, expand=True),
            right or ft.Container(),
            link("Change", on_click)], spacing=14), bgcolor=SUNK, border_radius=12, width=620, ink=True,
            padding=ft.Padding.only(left=16, right=8, top=12, bottom=12), on_click=on_click)

    def entity_card(self, r):
        """The chosen entity as people know it, with a button to change it."""
        if not r.entity:
            return button("Choose an entity", lambda _: self.entity_dialog(), primary=True, icon=ft.Icons.SEARCH)
        st = self.data_state(r.entity)
        name = (st.get("attributes") or {}).get("friendly_name") or r.entity
        domain = r.entity.split(".")[0]
        now_ = text(detect.shown_value(st) if st else "Not found", 13, SUB if st else WARN)
        return self.source_card(DOMAIN_ICONS.get(domain, ft.Icons.CIRCLE_OUTLINED), name, r.entity, now_)

    def made_from_note(self, r):
        source = r.made_from.split(" ")[0]
        return info(f"{r.entity} is a sensor Ring Studio's package makes from {source}, since Home Assistant only "
                    "hands out forecasts and calendar events to actions. Add the package once; Save YAML files "
                    "writes it too.", ft.Icons.EXTENSION_OUTLINED,
                    ("Copy package", lambda _: self.copy(setups.package([r.made_from]), "the package")))

    def data_tree(self, r, st):
        icons = {"number": ft.Icons.NUMBERS, "text": ft.Icons.TEXT_FIELDS, "time": ft.Icons.SCHEDULE,
                 "yes/no": ft.Icons.TOGGLE_ON_OUTLINED}
        current = detect.chosen(r)
        rows = []
        for node in detect.tree(st):
            path = node["path"]
            on = node["pick"] and (path == current or (path[0] == "list" and current[0] == "list"
                                                       and set(path[1]) == set(current[1]) and path[2] == current[2]))
            reading = r.layout in LIST_LAYOUTS and path[0] in ("group", "list") and set(path[1]) == set(r.attrs)
            tag = ({"compass": "Direction", "countdown": "Counts to"}.get(r.layout, "Colour by") if on else
                   "read" if reading and path[0] == "group" else
                   "start" if reading and node["name"] == r.t_start else
                   "end" if reading and node["name"] == r.t_end else "")
            icon = ft.Icons.LIST if node["kind"].startswith("list") else icons.get(node["kind"], ft.Icons.CIRCLE_OUTLINED)
            rows.append(ft.Container(ft.Row([
                ft.Icon(icon, size=16, color=ACCENT if on else FAINT),
                text(node["name"], 13, TEXT if node["pick"] else SUB, mono=True),
                text(node["kind"], 12, FAINT),
                ft.Container(expand=True),
                text(node["sample"], 12, SUB, mono=True, max_lines=1),
                ft.Container(text(tag, 12, ACCENT), width=70, alignment=ft.Alignment.CENTER_RIGHT)], spacing=10),
                padding=ft.Padding.only(left=10 + 28 * node["depth"], right=10, top=7, bottom=7), border_radius=8,
                bgcolor=ACCENT_BG if on else None, border=ft.Border.all(1, ACCENT if on else SUNK),
                ink=node["pick"], on_click=(lambda _, p=path: self.apply_path(p)) if node["pick"] else None,
                tooltip=None if node["pick"] or node["depth"] or path[0] == "group" else "Not something to colour by"))
        return ft.Container(ft.Column(rows, spacing=2), bgcolor=SUNK, border_radius=12, padding=8, width=620)

    def apply_path(self, path, announce=True):
        """Colours the ring by one row of the data tree. Colours the person set are kept where they still fit."""
        r = self.clock.ring
        st = self.data_state(r.entity)
        same = path == detect.chosen(r)
        fields, words, values = detect.choose(st, path, r)
        if r.layout == "compass" and path[0] != "list":  # the row is the direction; colours stay as they are
            fields = {"value_attr": fields.get("value_attr", "")}
        if same:  # clicking the current row again keeps the range the person set
            for k in ("lo", "hi", "scale"):
                fields.pop(k, None)
        elif "lo" in fields:
            r.stops_at = []  # the gradient spreads over the new range
        for k, v in fields.items():
            setattr(r, k, v)
        if r.colour_by == "values":
            self.add_states([str(v) for v in values if v not in (None, "")])
        edited()
        self.snap, self.preview_colors, self.at = None, None, 0
        self.refresh()
        if announce and words and not same:
            self.toast(words)

    def add_states(self, found):
        r = self.clock.ring
        for s in dict.fromkeys(found):
            if s not in r.colors and len(r.colors) < 40:
                r.colors[s] = from_hex(PRESETS[(len(r.colors) + 1) % len(PRESETS)])

    def use_entity(self, entity_id, announce=True):
        """Sets the entity and colours the ring by the most likely part of its data."""
        r = self.clock.ring
        r.entity, r.made_from, r.raw = entity_id, "", ""
        if r.layout in TIME_LAYOUTS + ("raw", "segments"):
            r.layout = "fill"
        st = self.data_state(entity_id)
        if st:
            self.apply_path(detect.default_path(st), announce)
            return
        edited()
        self.snap, self.preview_colors, self.at = None, None, 0
        self.refresh()

    def use_time(self):
        r = self.clock.ring
        if r.layout not in TIME_LAYOUTS:
            r.layout, r.entity, r.made_from, r.raw = "hands", "", "", ""
            if not r.palette or len(r.palette) < 3:
                r.palette = [c[:] for c in GRADIENTS_NAMES["Through the day"]]
            r.dim = min(r.dim, 0.15)
        edited()
        self.refresh()

    def second_entity(self, r):
        """Compass: what colours the LED. Distance for lightning, speed for wind."""
        st = self.data_state(r.entity2) if r.entity2 else {}
        numbers = {"": "its state"}
        numbers.update({k: k for k, v in (st.get("attributes") or {}).items() if detect._is_number(v)
                        and not isinstance(v, bool)})

        def set_attr(v):
            r.value2_attr = v or ""
        if not r.entity2:
            return ft.Column([caption("Colour"), ft.Row([
                text("One colour. Pick an entity to colour the LED by its value, such as wind speed or distance.",
                     13, SUB, expand=True),
                link("Choose", lambda _: self.entity_dialog(target="entity2"))])], spacing=6)
        name = (st.get("attributes") or {}).get("friendly_name") or r.entity2
        return ft.Column([caption("Colour from"), ft.Row([
            self.source_card(DOMAIN_ICONS.get(r.entity2.split(".")[0], ft.Icons.CIRCLE_OUTLINED), name, r.entity2,
                             on_click=lambda _: self.entity_dialog(target="entity2")),
        ]), ft.Row([pick("Value", r.value2_attr if r.value2_attr in numbers else "", numbers, set_attr, 220),
                    ft.Container(link("No colour entity", lambda _: (setattr(r, "entity2", ""),
                                                                    setattr(r, "value2_attr", ""),
                                                                    self.refresh_editor()), SUB),
                                 padding=ft.Padding.only(top=18))], spacing=14)], spacing=8)

    def parts_editor(self, r):
        """Segments: one entity per part, in order clockwise from the top."""
        rows = []
        for i, (entity, attr_, name) in enumerate(r.parts):
            st = self.data_state(entity)
            value = detect.shown_value(st) if st else "Not found"

            def put_name(v, i=i):
                r.parts[i][2] = projects.clean_label(v)

            def move(i, by):
                j = i + by
                if 0 <= j < len(r.parts):
                    r.parts[i], r.parts[j] = r.parts[j], r.parts[i]
                    self.refresh_editor()

            rows.append(ft.Row([
                text(str(i + 1), 13, FAINT, width=20),
                field("", lambda i=i: r.parts[i][2], put_name, width=200, hint_text="Name"),
                ft.Container(text(entity, 12, SUB, mono=True, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                             width=240, tooltip=entity),
                text(value, 12, SUB if st else WARN, width=90, max_lines=1),
                ft.IconButton(ft.Icons.ARROW_UPWARD, icon_size=16, icon_color=FAINT, tooltip="Earlier on the ring",
                              disabled=i == 0, on_click=lambda _, i=i: move(i, -1)),
                ft.IconButton(ft.Icons.DELETE_OUTLINE, icon_color=FAINT, tooltip="Remove part",
                              disabled=len(r.parts) < 2,
                              on_click=lambda _, i=i: (r.parts.pop(i), self.refresh_editor()))], spacing=8))
        per = self.clock.hw.leds // max(len(r.parts), 1)
        return ft.Column(rows + [
            link("+ Add part", lambda _: self.entity_dialog(target="part"), SUB) if len(r.parts) < MAX_PARTS
            else caption(f"A ring has room for {MAX_PARTS} parts."),
            caption(f"Clockwise from the top, {per} LEDs each" + (", with a dark LED between parts." if per >= 3 else
                                                                  "."))], spacing=6)

    def advanced(self, r):
        """Every field typed by hand, for entities without data here or for full control."""
        def layout(v):
            self.set_layout(v)

        rows = [pick("Layout", r.layout, {k: v[0] for k, v in LAYOUT_NAMES.items() if k != "raw"}, layout,
                     width=180),
                attr(r, "entity", "Entity", mono=True, width=360)]
        if r.layout in LIST_LAYOUTS:
            rows += [attr(r, "attrs", "List attributes", lambda s: [x.strip() for x in s.split(",") if x.strip()],
                          ", ".join), attr(r, "key", "Value key", mono=True),
                     attr(r, "t_start", "Start time key", mono=True), attr(r, "t_end", "End time key", mono=True)]
        else:
            rows.append(attr(r, "value_attr", "Value attribute (empty = state)", mono=True, width=240))
        if r.colour_by != "values":
            rows.append(attr(r, "scale", "Multiply by", float, fmt=lambda v: f"{v:g}", width=120))
        again = link("Detect from the data again", lambda _: self.use_entity(r.entity), icon=ft.Icons.AUTO_FIX_HIGH)
        again.disabled = not self.data_state(r.entity)
        tip = ("Leave the time keys empty when the first item is always now." if r.layout in LIST_LAYOUTS else
               "Multiply by is set from the unit, for example 100 to show SEK/kWh as öre.")
        return ft.Column([ft.Row(rows, wrap=True, spacing=14, run_spacing=14,
                                 vertical_alignment=ft.CrossAxisAlignment.START), caption(tip), again], spacing=10)

    # ---------- 2 colours ----------
    def colour_rule(self, r):
        if r.colour_by == "values" or r.layout in TIME_LAYOUTS + ("raw",) or (r.layout == "compass" and
                                                                               not r.entity2):
            return None

        def rule(v):
            if v == "steps" and not r.steps:  # start the steps from the gradient, so nothing is lost
                r.steps = [[round(a, 4), p[:], ""] for a, p in zip(stop_values(r), r.palette)]
            r.colour_by = v
            self.refresh_editor()

        return segmented({"gradient": "Gradient", "steps": "Steps"}, r.colour_by, rule)

    def colours_body(self, r):
        if r.layout == "hands":
            return ft.Column([self.gradient_editor(r),
                              caption("The colours are spread over the day, from midnight on the left back to "
                                      "midnight. The hour hand shows the colour for now, the minute hand a lighter "
                                      "version."),
                              ft.Row([self.color_chip("Face", lambda: r.missing, lambda v: setattr(r, "missing", v))],
                                     spacing=12)], spacing=16)
        if r.layout == "day_arc":
            def chip(key, label, default):
                return self.color_chip(label, lambda: r.colors.get(key, default),
                                       lambda v: r.colors.__setitem__(key, v))
            return ft.Row([chip("day", "Day", [96, 72, 32]), chip("night", "Night", [16, 20, 56]),
                           chip("sun", "Sunrise and sunset", [255, 128, 48]), chip("now", "Now", [255, 255, 255])],
                          wrap=True, spacing=12, run_spacing=12)
        if r.layout == "compass" and not r.entity2:
            return ft.Row([self.color_chip("Pointer", lambda: r.fallback, lambda v: setattr(r, "fallback", v)),
                           self.color_chip("Marks and the rest", lambda: r.missing,
                                           lambda v: setattr(r, "missing", v))], spacing=12)
        if r.colour_by == "values":
            body = self.map_editor(r)
            extra = lambda: ft.Row([  # noqa: E731
                self.color_chip("Any other value", lambda: r.fallback, lambda v: setattr(r, "fallback", v)),
                self.color_chip("No data", lambda: r.missing, lambda v: setattr(r, "missing", v))],
                wrap=True, spacing=12, run_spacing=12)
        else:
            body = self.steps_editor(r) if r.colour_by == "steps" else self.value_gradient(r)
            extra = lambda: ft.Row([  # noqa: E731
                self.color_chip("Below the first colour", lambda: r.below, lambda v: setattr(r, "below", v), True),
                self.color_chip("No data", lambda: r.missing, lambda v: setattr(r, "missing", v))],
                wrap=True, spacing=12, run_spacing=12)
        return ft.Column([body, self.more("more", "More colours", extra)], spacing=16)

    def value_gradient(self, r):
        width, at = 560, stop_values(r)
        first, last = at[0], at[-1]
        span = (last - first) or 1.0
        x = lambda v: max(0.0, min(1.0, (v - first) / span))  # noqa: E731

        def put(values, palette):
            order = sorted(range(len(values)), key=lambda i: values[i])
            r.stops_at = [values[i] for i in order]
            r.palette = [palette[i] for i in order]
            self.refresh_editor()

        def edit_stop(i):
            def done(colour, value=None):
                values, palette = list(at), [p[:] for p in r.palette]
                palette[i] = colour
                if value is not None:
                    values[i] = value
                put(values, palette)

            def remove():
                put(at[:i] + at[i + 1:], r.palette[:i] + r.palette[i + 1:])

            self.color_dialog(f"Colour at {num(at[i])}", r.palette[i], done, remove=remove if len(at) > 2 else None,
                              value=at[i])

        def add_at(v):
            i = next((k for k, a in enumerate(at) if a > v), len(at))
            if 0 < i < len(at):
                b = (v - at[i - 1]) / ((at[i] - at[i - 1]) or 1)
                colour = [round(p + (q - p) * b) for p, q in zip(r.palette[i - 1], r.palette[i])]
            else:
                colour = r.palette[0 if i == 0 else -1][:]
            put(at[:i] + [round(v, 4)] + at[i:], r.palette[:i] + [colour] + r.palette[i:])

        def add_gap(_):
            gaps = [(at[k + 1] - at[k], k) for k in range(len(at) - 1)]
            size, k = max(gaps) if gaps else (1, 0)
            add_at(at[k] + size / 2 if gaps else at[-1] + 1)

        def tap(e):
            add_at(first + (e.local_position.x - 15) / (width - 30) * span)

        def even(_):
            r.lo, r.hi, r.stops_at = first, last, []
            self.refresh_editor()

        values = self.data_values(r)
        ticks = [ft.Container(left=15 + x(v) * (width - 30) - 1, top=0, width=2, height=6, bgcolor=SUB, opacity=0.6)
                 for v in values if first <= v <= last]
        bar = ft.GestureDetector(ft.Container(width=width - 30, height=14, border_radius=7, gradient=ft.LinearGradient(
            colors=[to_hex(p) for p in r.palette], stops=[x(a) for a in at], begin=ft.Alignment.CENTER_LEFT,
            end=ft.Alignment.CENTER_RIGHT)), on_tap_down=tap, left=15, top=18, mouse_cursor=ft.MouseCursor.CLICK)
        dots, labels = [], []
        for i, (a, p) in enumerate(zip(at, r.palette)):
            dots.append(ft.Container(left=x(a) * (width - 30), top=10, width=30, height=30, border_radius=15,
                                     bgcolor=to_hex(p), border=ft.Border.all(3, CARD), ink=True,
                                     tooltip="Change colour or value",
                                     shadow=ft.BoxShadow(blur_radius=4, offset=ft.Offset(0, 2),
                                                         color=ft.Colors.with_opacity(0.5, "#000000")),
                                     on_click=lambda _, i=i: edit_stop(i)))
            labels.append(ft.Container(text(num(a), 12, TEXT, mono=True), left=x(a) * (width - 30) - 15, top=46,
                                       width=60, alignment=ft.Alignment.CENTER, on_click=lambda _, i=i: edit_stop(i)))
        outside = sum(1 for v in values if not first <= v <= last)
        unit = (self.data_state(r.entity).get("attributes") or {}).get("unit_of_measurement") or ""
        scaled = f" Values are multiplied by {r.scale:g} from {unit}." if r.scale != 1 and unit else ""
        hint = "Click the bar to add a colour there. Click a colour to change it or the value it sits at." + scaled
        if outside:
            hint += f" {outside} of the values are outside these colours."
        return ft.Column([
            ft.Row([caption("Ticks: the values in the data" if ticks else "Colours by value"), ft.Container(expand=True),
                    ft.TextButton("Spread evenly", on_click=even, style=FADE, disabled=not r.stops_at),
                    link("+ Add colour", add_gap, SUB)], width=width),
            ft.Stack(ticks + [bar] + dots + labels, width=width, height=70),
            caption(hint),
            ft.Row([caption("Presets")] + [self.gradient_chip(r, name, stops) for name, stops in GRADIENTS_NAMES.items()],
                   wrap=True, spacing=8, run_spacing=8, width=width + 80)], spacing=10)

    def data_values(self, r):
        """The numbers the colours will see (after Multiply by), for the ticks over the gradient."""
        st = self.data_state(r.entity)
        attrs = st.get("attributes") or {}
        if r.layout in LIST_LAYOUTS:
            raw = [i.get(r.key) for a in r.attrs for i in attrs.get(a) or [] if isinstance(i, dict)]
        elif r.layout == "compass":
            st2 = self.data_state(r.entity2)
            raw = [(st2.get("attributes") or {}).get(r.value2_attr) if r.value2_attr else st2.get("state")]
        elif r.layout == "segments":
            raw = [self.data_state(p[0]).get("state") for p in r.parts]
        else:
            raw = [attrs.get(r.value_attr) if r.value_attr else st.get("state")]
        out = []
        for v in raw:
            try:
                out.append(float(v) * r.scale)
            except (TypeError, ValueError):
                pass
        return out[:400]

    def steps_editor(self, r):
        def recolour(i):
            def done(colour, value=None):
                r.steps[i][1] = colour
                if value is not None:
                    r.steps[i][0] = value
                    r.steps.sort(key=lambda s: s[0])
                self.refresh_editor()

            self.color_dialog(f"Step from {r.steps[i][0]:g}", r.steps[i][1], done, value=r.steps[i][0],
                              remove=(lambda: (r.steps.pop(i), self.refresh_editor())) if len(r.steps) > 1 else None)

        def add(_):
            last = r.steps[-1][0] if r.steps else r.lo
            gap = (r.steps[-1][0] - r.steps[-2][0]) if len(r.steps) > 1 else max((r.hi - r.lo) / 4, 1)
            r.steps.append([round(last + gap, 4), from_hex(PRESETS[(len(r.steps) * 3 + 1) % len(PRESETS)]), ""])
            self.refresh_editor()

        def put_from(i, v):
            r.steps[i][0] = v

        def put_name(i, v):
            r.steps[i][2] = projects.clean_label(v)

        unit = "minutes left" if r.layout == "countdown" else "From"
        rows = [ft.Row([ft.Container(width=34), ft.Container(caption(unit), width=120), caption("Name")], spacing=12)]
        for i, (start, colour, name) in enumerate(r.steps):
            rows.append(ft.Row([
                dot(to_hex(colour), 32, tooltip="Change colour", on_click=lambda _, i=i: recolour(i)),
                field("", lambda i=i: r.steps[i][0], lambda v, i=i: put_from(i, v), float, lambda v: f"{v:g}",
                      width=120, mono=True),
                field("", lambda i=i: r.steps[i][2], lambda v, i=i: put_name(i, v), width=260,
                      hint_text="For example Cheap"),
                ft.IconButton(ft.Icons.DELETE_OUTLINE, icon_color=FAINT, tooltip="Remove step",
                              disabled=len(r.steps) < 2, on_click=lambda _, i=i: (r.steps.pop(i),
                                                                                  self.refresh_editor()))],
                spacing=12))
        parts = rows + [link("+ Add step", add, SUB)]
        starts = [s[0] for s in r.steps]
        if starts != sorted(starts):
            parts.append(note("The steps should go from low to high.",
                              ("Sort them", lambda _: (r.steps.sort(key=lambda s: s[0]), self.refresh_editor()))))
        elif len(r.steps) > 1:
            span = starts[-1] - starts[0] or 1
            tail = span / (len(starts) - 1)
            weights = [max(1, round(((starts[k + 1] if k + 1 < len(starts) else starts[k] + tail) - starts[k])
                                    / span * 100)) for k in range(len(starts))]
            parts.append(ft.Container(ft.Row([ft.Container(bgcolor=to_hex(s[1]), expand=w, height=14)
                                              for s, w in zip(r.steps, weights)], spacing=0),
                                      border_radius=7, clip_behavior=ft.ClipBehavior.HARD_EDGE, width=560))
        parts.append(caption("Each colour starts at its value and lasts until the next step. Values below the first "
                             "step use the first colour, unless Below the first colour is set under More colours."))
        return ft.Column(parts, spacing=8)

    def color_chip(self, label, get, put, optional=False):
        sw = dot(to_hex(get()) if get() else None, 18)

        def done(v):
            put(v)
            sw.bgcolor = to_hex(v) if v else "#000000"
            sw.update()

        return ft.Container(ft.Row([sw, text(label, 13)], spacing=10, tight=True), bgcolor=RAISED, border_radius=10,
                            padding=ft.Padding.symmetric(horizontal=14, vertical=12), ink=True,
                            on_click=lambda _: self.color_dialog(label, get(), done, optional))

    def gradient_editor(self, r):
        """Hands: colours spread evenly over the day."""
        width = 520

        def edit_stop(i):
            def done(v):
                r.palette[i] = v
                self.refresh_editor()

            def remove():
                r.palette.pop(i)
                self.refresh_editor()

            self.color_dialog(f"Colour {i + 1}", r.palette[i], done, remove=remove if len(r.palette) > 2 else None)

        def add(_):
            r.palette.append(r.palette[-1][:])
            self.refresh_editor()

        n = len(r.palette)
        dots = [ft.Container(left=i / (n - 1) * (width - 30), top=0, width=30, height=30, border_radius=15,
                             bgcolor=to_hex(p), border=ft.Border.all(3, CARD), ink=True, tooltip="Edit colour",
                             shadow=ft.BoxShadow(blur_radius=4, offset=ft.Offset(0, 2),
                                                 color=ft.Colors.with_opacity(0.5, "#000000")),
                             on_click=lambda _, i=i: edit_stop(i)) for i, p in enumerate(r.palette)]
        bar = ft.Container(left=15, top=8, width=width - 30, height=14, border_radius=7, gradient=ft.LinearGradient(
            colors=[to_hex(p) for p in r.palette], begin=ft.Alignment.CENTER_LEFT, end=ft.Alignment.CENTER_RIGHT))
        hours = [ft.Container(text(f"{round(i * 24 / n) % 24:02d}:00", 11, FAINT, mono=True),
                              left=i / (n - 1) * (width - 30) - 15, top=34, width=60, alignment=ft.Alignment.CENTER)
                 for i in range(n)]
        return ft.Column([ft.Row([caption("Colours through the day"), ft.Container(expand=True),
                                  link("+ Add colour", add, SUB)], width=width),
                          ft.Stack([bar] + dots + hours, width=width, height=54),
                          ft.Row([caption("Presets")] + [self.gradient_chip(r, name, stops)
                                                         for name, stops in GRADIENTS_NAMES.items()],
                                 wrap=True, spacing=8, run_spacing=8, width=width + 120)], spacing=10)

    def gradient_chip(self, r, name, stops):
        def use(_):
            if r.stops_at and r.layout != "hands":  # keep the ends the person set, spread the preset between them
                first, last = r.stops_at[0], r.stops_at[-1]
                r.stops_at = [first + (last - first) * i / (len(stops) - 1) for i in range(len(stops))]
            r.palette = [c[:] for c in stops]
            self.refresh_editor()

        same = r.palette == stops
        return ft.Container(ft.Row([ft.Container(width=34, height=10, border_radius=5, gradient=ft.LinearGradient(
            colors=[to_hex(p) for p in stops], begin=ft.Alignment.CENTER_LEFT, end=ft.Alignment.CENTER_RIGHT)),
            text(name, 12, TEXT if same else SUB)], spacing=8, tight=True), on_click=use, ink=True,
            border_radius=16, border=ft.Border.all(1, ACCENT if same else "#2A313B"),
            padding=ft.Padding.symmetric(horizontal=10, vertical=6))

    def state_note_dialog(self, r, key):
        def put(v):
            if v:
                r.state_notes[key] = v
            else:
                r.state_notes.pop(key, None)

        def done(_):
            self.close()
            self.refresh_editor()

        self.dialog(f"Note for {key}", ft.Column([
            caption("Only for you. Kept in the project file, never sent anywhere."),
            field("", lambda: r.state_notes.get(key, ""), put, width=520, multiline=True, min_lines=3,
                  max_lines=8, hint_text="For example: shows up a few times a year, so a strong colour is fine")],
            spacing=10, tight=True), [button("Done", done, primary=True)], 560)

    def seen_values(self, r):
        """The text values in the data now: list items, the state, or every part's state."""
        if r.layout == "segments":
            return [str(self.data_state(p[0]).get("state")) for p in r.parts if self.data_state(p[0])]
        st = self.data_state(r.entity)
        attrs = st.get("attributes") or {}
        if r.layout in LIST_LAYOUTS:
            values = [i.get(r.key) for a in r.attrs for i in attrs.get(a) or [] if isinstance(i, dict)]
        else:
            values = [attrs.get(r.value_attr) if r.value_attr else st.get("state")]
        return [str(v) for v in values if v not in (None, "")]

    def map_editor(self, r):
        def rename(old, new):
            r.colors = {(new if k == old else k): v for k, v in r.colors.items()}
            r.labels = {(new if k == old else k): v for k, v in r.labels.items()}
            r.state_notes = {(new if k == old else k): v for k, v in r.state_notes.items()}

        def add(states):
            for s in states:
                r.colors.setdefault(s, from_hex(PRESETS[(len(r.colors) + 1) % len(PRESETS)]))
            self.refresh_editor()

        def remove(key):
            r.colors.pop(key, None)
            r.labels.pop(key, None)
            r.state_notes.pop(key, None)
            self.refresh_editor()

        def fetch():
            try:
                entities = [p[0] for p in r.parts] if r.layout == "segments" else [r.entity]
                found = []
                for e in entities:
                    found += self.ha.seen_states(e, r.attrs if r.layout in LIST_LAYOUTS else [], r.key)
            except RuntimeError as err:
                self.toast(str(err))
                return
            new = [s for s in dict.fromkeys(found) if s not in r.colors]
            self.toast(f"Found {len(set(found))} values, {len(new)} new" if found else "No values found")
            add(new)

        def found_here(_):
            new = [v for v in dict.fromkeys(self.seen_values(r)) if v not in r.colors]
            self.toast(f"{len(new)} new values found" if new else "Every value in the data already has a colour")
            add(new)

        rows = []
        for key in list(r.colors):
            cell = [key]

            def recolor(v, cell=cell):
                r.colors[cell[0]] = v
                self.refresh_editor()

            rows.append(ft.Row([
                dot(to_hex(r.colors[key]), 30, tooltip="Change colour",
                    on_click=lambda _, cell=cell: self.color_dialog(cell[0], r.colors[cell[0]], recolor)),
                field("", lambda cell=cell: cell[0], lambda v, cell=cell: (rename(cell[0], v), cell.__setitem__(0, v)),
                      width=170, mono=True),
                field("", lambda cell=cell: r.labels.get(cell[0], ""),
                      lambda v, cell=cell: r.labels.__setitem__(cell[0], v), width=300,
                      hint_text="What this colour means"),
                ft.IconButton(ft.Icons.STICKY_NOTE_2 if r.state_notes.get(key) else ft.Icons.STICKY_NOTE_2_OUTLINED,
                              icon_color=ACCENT if r.state_notes.get(key) else FAINT,
                              tooltip=r.state_notes.get(key) or "Add a note", on_click=lambda _, cell=cell:
                              self.state_note_dialog(r, cell[0])),
                ft.IconButton(ft.Icons.DELETE_OUTLINE, icon_color=FAINT, tooltip="Remove value",
                              on_click=lambda _, k=key: remove(k))], spacing=12))
        have = bool(self.seen_values(r))
        head = ft.Row([caption("A colour for each value"), ft.Container(expand=True),
                       ft.TextButton("Add the values in the data", disabled=not have, on_click=found_here,
                                     style=ft.ButtonStyle(color=ACCENT)),
                       ft.TextButton("Values Home Assistant has seen",
                                     disabled=not (self.connected and (r.entity or r.parts)),
                                     on_click=lambda _: self.page.run_thread(fetch),
                                     style=ft.ButtonStyle(color=ACCENT))], width=640)
        return ft.Column([head] + rows + [link("+ Add value", lambda _: add([f"value{len(r.colors) + 1}"]), SUB)],
                         spacing=8)

    # ---------- 3 ring ----------
    def set_layout(self, layout):
        r = self.clock.ring
        if layout == r.layout:
            return
        if layout == "hands" and r.dim > 0.5:
            r.dim = 0.15  # Other LEDs from a list layout would make the quarter marks as bright as the hands
        if layout in LIST_LAYOUTS and r.layout not in LIST_LAYOUTS and r.dim < 0.3:
            r.dim = 0.55
        if layout == "countdown" and r.colour_by == "steps" and not r.steps:
            r.steps = [[0, [255, 0, 64], "Go now"], [4, [255, 176, 0], "Soon"], [7, [0, 200, 83], "Plenty of time"]]
        r.layout = layout
        edited()
        self.refresh()

    def ring_body(self, r):
        group = group_of(r)
        parts = []
        if len(group) > 1:
            parts.append(ft.Row([tile(*LAYOUT_NAMES[k], k == r.layout, lambda _, k=k: self.set_layout(k), 200 if len(group) < 4 else 142)
                                 for k in group], spacing=10, run_spacing=10, wrap=True))
        if r.layout in LIST_LAYOUTS:
            if r.layout == "dial_24h":
                per = self.clock.hw.leds / 24
                size = f"{per:g} LEDs" if per == int(per) else "1 or 2 LEDs, since the LEDs do not split evenly into 24"
                parts.append(caption(f"Every hour keeps its place: 00-01, 01-02 and so on, {size} each. The ring "
                                     "shows the next 24 hours, and the current hour is the bright one."))
            if r.layout == "week":
                parts.append(caption("Today at the top, then the next six days clockwise, with a dark LED between "
                                     "days. Each day shows its first item."))
            if r.layout != "from_now" and not r.t_start:
                parts.append(note("This layout needs the time of each item. Set the start time key under More in "
                                  "Data."))
            parts.append(ft.Row([segmented(MARKERS, r.marker, lambda v: (setattr(r, "marker", v),
                                                                         self.refresh_editor())),
                                 ft.Row([caption("Other LEDs"), percent_slider(r, "dim", 100)], spacing=4, tight=True)],
                                wrap=True, spacing=16, run_spacing=12))
        elif r.layout == "fill":
            parts.append(ft.Row([attr(r, "lo", "Empty at", float, fmt=lambda v: f"{v:g}", width=130),
                                 attr(r, "hi", "Full at", float, fmt=lambda v: f"{v:g}", width=130)], spacing=14))
        elif r.layout == "hands":
            parts.append(ft.Row([caption("Quarter marks"), percent_slider(r, "dim", 50)], spacing=4, tight=True))
        elif r.layout == "compass":
            parts.append(ft.Row([caption("Marks at north, east, south and west"), percent_slider(r, "dim", 50)],
                                spacing=4, tight=True))
            parts.append(caption("North is the LED at 12 o'clock. The LEDs either side of the pointer glow faintly."))
        elif r.layout == "countdown":
            parts.append(caption(f"One LED per minute, up to {self.clock.hw.leds} minutes, clockwise from the top. "
                                 "Each LED takes the colour for the minutes it stands for."))
        elif r.layout == "whole_ring" and r.colour_by == "values":
            parts.append(caption("Text colours the whole ring, one colour per value. To show text over time, pick a "
                                 "field inside a list in Data."))
        elif r.layout == "day_arc":
            parts.append(caption("Midnight at the top. The LED for now is white, and the sunrise and sunset LEDs "
                                 "move with the seasons."))
        parts.append(ft.Row([caption(f"Where 12 o'clock is and which way the LEDs run is set once for "
                                     f"{self.device.friendly}."),
                             link("Clock page", lambda _: self.select(self.idx, None, "device"), ACCENT)],
                            spacing=4, wrap=True))
        return ft.Column(parts, spacing=16)
