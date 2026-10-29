"""The clock's own page: getting it running, its brightness, its name and hardware. Also Apply to clock."""

import time
from dataclasses import asdict

import flet as ft

from .. import flashing, generate, project as projects, publish, setups, sun
from ..model import slug
from .kit import (ACCENT, ACCENT_BG, FAINT, GREEN, HW_KEYS, HW_NAME, HW_PRESET, LINE, SUB, SUNK, TEXT, WARN, attr,
                  button, caption, edited, field, firmware_hash, info, link, note, now, pick, segmented, since,
                  status_dot, template_hash, text)


class ClockPage:
    def clock_page(self):
        """The clock itself: getting it running, its brightness and its hardware. Designs live under it."""
        c = self.device
        shows = f"Shows {c.design.name}. {len(c.designs)} design{'s' if len(c.designs) != 1 else ''} to choose from."
        d = c.dimming
        nights = "on all night" if d.night_start >= 24 else f"off {d.night_start:02d} to {d.night_end:02d}"
        bright = f"Follows the sun · {nights}" if d.enabled else "Fixed, set from Home Assistant"
        device = f"{c.hw.pin} · {c.hw.leds} LEDs · {c.name}.local"
        head = ft.Row([text(c.friendly, 28, weight=ft.FontWeight.W_700), ft.Container(expand=True),
                       ft.IconButton(ft.Icons.STICKY_NOTE_2 if c.note else ft.Icons.STICKY_NOTE_2_OUTLINED,
                                     icon_color=ACCENT if c.note else SUB, tooltip=c.note or "Add a note, only for you",
                                     on_click=lambda _: self.note_dialog(c, f"Note for {c.friendly}"))])
        return [ft.Column([head, text(shows, color=SUB)], spacing=4),
                self.setup_card(c),
                self.section("bright", "Brightness", bright, self.bright_body),
                self.section("device", "Name and hardware", device, self.device_body)]

    # ---------- getting it running ----------
    def setup_card(self, c):
        """Getting a clock running, as a checklist that ticks itself off from what Home Assistant reports. Once
        everything is done it folds to one line."""
        st = self.clock_state(c) or {}
        sensor = any(s.get("entity_id") == c.colors_entity for s in self.states)
        backed = bool(self.mark("verified", c))
        flashed = bool(self.mark("flashed", c)) or st.get("found")
        stale = self.firmware_stale(c)
        rows = [
            (self.connected, "Connect Home Assistant", "Ring Studio reads your entities and sends designs through it.",
             ("Connect", self.connect_dialog)),
            (backed, "Back up the stock firmware", "The only way back to the original firmware. About a minute "
             "over USB.", ("Back up", self.firmware_dialog)),
            (flashed and not stale, "Update the clock" if stale else "Flash the clock",
             "Something the firmware holds changed since the last flash. Update over WiFi to send it." if stale
             else "Runs Ring Studio's firmware. Later updates go over WiFi." if flashed
             else "Set your WiFi, then flash over USB. Later updates go over WiFi.",
             ("Update" if stale else "Flash", self.firmware_dialog)),
            (st.get("found"), "Add it in Home Assistant", "Settings > Devices & services finds it as ESPHome and "
             "asks for the API key.", ("Copy API key", lambda _: self.copy_api_key())),
            (sensor, "Show a design", f"Apply a design to send it. It shows {c.design.name} once applied.",
             ("Apply", self.apply_dialog)),
        ]
        done = sum(bool(r[0]) for r in rows)
        ready = done == len(rows)

        def toggle(_):
            self.opened["checklist"] = not self.opened["checklist"]
            self.refresh_editor()

        if ready and not self.opened["checklist"]:
            return self.step_card("✓", "Ready", f"Shows {c.design.name}",
                                  link("Show the setup steps", toggle, SUB))
        lines = []
        for ok, title, words, (label, act) in rows:
            lines.append(ft.Row([
                ft.Icon(ft.Icons.CHECK_CIRCLE if ok else ft.Icons.RADIO_BUTTON_UNCHECKED, size=20,
                        color=GREEN if ok else FAINT),
                ft.Column([text(title, 14, TEXT if not ok else SUB, weight=ft.FontWeight.W_600),
                           caption(words)], spacing=2, tight=True, expand=True),
                ft.TextButton(label, on_click=act, style=ft.ButtonStyle(color=ACCENT if not ok else FAINT))],
                spacing=12))
        if ready:
            lines.append(link("Hide the setup steps", toggle, SUB))
        summary = "Ready" if ready else f"{done} of {len(rows)} done"
        return self.step_card("✓" if ready else len(rows) - done, "Setup", summary, ft.Column(lines, spacing=12))

    def copy_api_key(self):
        """Home Assistant asks for the clock's API key (its encryption key) when adding it."""
        generate.secrets_file(self.project)  # makes the key when there is none yet, never replaces one
        self.keep_secrets()
        key = self.project.secrets.get("api_key", "")
        if not generate.valid_api_key(key):
            self.toast("There is no valid API key yet. Open Flash to make one.")
            return
        self.copy(key, "the API key. Paste it when Home Assistant asks for the encryption key")

    def firmware_stale(self, c):
        """True when the firmware the app would build differs from the one flashed from here."""
        flashed = self.mark("flashed", c)
        if not flashed:
            return False
        try:
            return flashed != firmware_hash(c)
        except ValueError:
            return False

    # ---------- brightness ----------
    def bright_body(self):
        c = self.device
        d = c.dimming

        def toggle(e):
            d.enabled = bool(e.control.value)
            self.refresh_editor()

        parts = [ft.Row([ft.Column([text("Follow the sun"),
                                    caption("The clock dims itself as the sun goes down and turns the ring off at "
                                            "night. It follows the elevation of Home Assistant's sun.sun.")],
                                   spacing=2, expand=True),
                         ft.Switch(value=d.enabled, active_color=ACCENT, on_change=toggle)])]
        if d.enabled:
            parts += [ft.Row([attr(d, "night_start", "Off from (hour, 24 = never)", int, width=190),
                              attr(d, "night_end", "Back on at (hour)", int, width=150),
                              attr(d, "low", "Dimmest", int, width=110),
                              attr(d, "elev_low", "at sun angle °", float, width=130),
                              attr(d, "high", "Brightest", int, width=110),
                              attr(d, "elev_high", "at sun angle °", float, width=130)], wrap=True, spacing=14,
                             run_spacing=14, vertical_alignment=ft.CrossAxisAlignment.START)]
            self.curve.content = self.curve_view()
            parts.insert(1, self.curve)
        else:
            parts.append(caption("Set the brightness with the clock's Ring Brightness control in Home Assistant."))
        if self.firmware_stale(c):
            parts.append(note("Changed since the last flash, so the clock does not have it yet.",
                              ("Update the clock", lambda _: self.firmware_dialog())))
        else:
            parts.append(caption("Brightness is part of the firmware: after changing it, update the clock over WiFi."))
        return ft.Column(parts, spacing=20)

    def curve_view(self):
        """Brightness over today, estimated for Home Assistant's location the way sun.sun will report it. Half
        an hour per bar."""
        d = self.device.dimming
        if not self.place:
            return caption("Connect Home Assistant to see today's brightness curve.")
        lat, lon, where = self.place
        today = now()
        curve = sun.day_curve(d, lat, lon, today)
        top, h = max(d.high, 1), 72
        here = (today.hour * 60 + today.minute) // 30
        bars = [ft.Container(width=9, height=max(2, h * b / top), border_radius=2, tooltip=f"{t:%H:%M} · {b}",
                             bgcolor=(ACCENT if i == here else ft.Colors.with_opacity(0.55, ACCENT)) if b else LINE)
                for i, (t, b) in enumerate(curve)]
        lit = [(t, b) for t, b in curve if b]
        peak = max(lit, key=lambda x: x[1]) if lit else None
        if not lit:
            words = f"Today in {where}: off all day."
        elif d.night_start >= 24:
            words = f"Today in {where}: on day and night, brightest {peak[1]} at {peak[0]:%H:%M}."
        else:
            words = (f"Today in {where}: on from {lit[0][0]:%H:%M}, brightest {peak[1]} at {peak[0]:%H:%M}, "
                     f"off from {d.night_start:02d}:00.")
        ticks = ft.Row([caption(f"{x:02d}") for x in (0, 6, 12, 18, 24)], width=48 * 12 - 3,
                       alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
        return ft.Column([ft.Row(bars, spacing=3, vertical_alignment=ft.CrossAxisAlignment.END, height=h),
                          ticks, text(words, 13, SUB)], spacing=8)

    # ---------- name, orientation and hardware ----------
    def device_body(self):
        c, hw = self.device, self.device.hw

        def remove():
            self.project.clocks.pop(self.idx)
            self.idx = 0
            self.didx = self.device.active if self.device else None
            edited()
            self.refresh()

        name = field("Name", lambda: c.friendly, lambda v: None, width=320)
        name.controls[1].on_change = None
        name.controls[1].on_blur = lambda e: self.rename_clock(c, e.control.value)
        name.controls[1].on_submit = name.controls[1].on_blur

        def turn(v):
            hw.clockwise = v == "cw"
            self.refresh_editor()

        orientation = ft.Column([
            ft.Row([attr(hw, "start_led", "LED at 12 o'clock", int, width=150),
                    ft.Column([caption("LED order"), segmented({"cw": "Clockwise", "ccw": "Anticlockwise"},
                                                               "cw" if hw.clockwise else "ccw", turn)],
                              spacing=6, tight=True)], spacing=20, vertical_alignment=ft.CrossAxisAlignment.START),
            caption("Every design on this clock uses it. If the hands sit in the wrong place, change the LED at "
                    "12 o'clock; if they run backwards, change the order.")], spacing=6)
        olds = f" Before: {', '.join(c.previous_names)}." if c.previous_names else ""
        return ft.Column(self.device_status(c) + [
            ft.Column([name, caption(f"On the network and in ESPHome it is {c.name}, at {c.name}.local.{olds}")],
                      spacing=6),
            orientation,
            self.hardware(hw),
            ft.Row([button("Flash and back up", self.firmware_dialog, icon=ft.Icons.USB),
                    button("Remove clock", lambda _: self.confirm(
                        "Remove clock", f"Remove {c.friendly} and its {len(c.designs)} designs from this project? "
                        "Nothing in Home Assistant or on the clock is changed. Undo brings it back.",
                        "Remove", remove), danger=True)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)], spacing=24)

    def rename_clock(self, c, value):
        """One name: the display name, with the device name made from it. A clock that already runs Ring Studio
        firmware or has a design in Home Assistant gets a summary of what changes first."""
        friendly = projects.clean_label(value or "")
        if not friendly or friendly == c.friendly:
            return
        new = slug(friendly)
        if new == c.name:
            c.friendly = friendly
            self.refresh_editor()
            return
        if new in {x.name for x in self.project.clocks if x is not c}:
            self.toast(f"Another clock is already called {new}. Pick another name.")
            self.refresh_editor()
            return
        set_up = self.mark("flashed", c) or self.mark("applied", c) or (self.clock_state(c) or {}).get("found")

        def go():
            if set_up and c.name not in c.previous_names:
                c.previous_names.append(c.name)
            c.name, c.friendly = new, friendly
            self.refresh_editor()

        if not set_up:
            go()
            return
        body = ft.Column([
            text(f"{c.friendly} becomes {friendly}. This changes:", color=SUB),
            text(f"Device name: {c.name} to {new} ({new}.local)", 13, mono=True),
            text(f"Colour sensor: sensor.{c.name}_ring_colors to sensor.{new}_ring_colors", 13, mono=True),
            caption("Then: update the clock over WiFi (it is reached at its old address this once), and apply a "
                    "design. Applying removes the old colour sensor once the clock has its new name. The ring light "
                    "keeps its entity ID in Home Assistant."),
        ], spacing=10, tight=True)
        self.confirm(f"Rename {c.friendly}", body, "Rename", go, danger=False)

    def device_status(self, c):
        """Online state, firmware version and Identify, from Home Assistant."""
        st = self.clock_state(c)
        if not st:
            return []
        if not st["found"]:
            return [caption("Not in Home Assistant yet. After the first flash, add it under Settings, Devices "
                            "and services, where it shows up as discovered.")]
        version = st["version"]
        installed = flashing.tool_versions()["esphome"]
        words = ("Online" if st["online"] else "Offline" + (f" since {since(st['since'])}" if st["since"] else "")) \
            + (f" · ESPHome {version}" if version else "")
        row = ft.Row([status_dot(GREEN if st["online"] else FAINT, 10),
                      text(words, 13, TEXT if st["online"] else SUB, expand=True),
                      button("Identify", lambda _: self.identify(c), icon=ft.Icons.LIGHTBULB_OUTLINE,
                             disabled=not st["online"])], spacing=10)
        out = [row]
        if st["online"] and flashing.newer(installed, version):
            out.append(note(f"The clock runs ESPHome {version}. {installed} is installed here.",
                            ("Update over the air", lambda _: self.firmware_dialog())))
        elif st["online"] and not version:
            out.append(caption("Update over the air once to show the firmware version here."))
        return out

    def identify(self, c):
        st = self.clock_state(c)

        def work():
            try:
                self.ha.call("light", "turn_on", {"entity_id": st["light"], "effect": "Rainbow Test"})
                time.sleep(5)
                self.ha.call("light", "turn_on", {"entity_id": st["light"], "effect": c.effect})
            except RuntimeError as err:
                self.toast(str(err))
        self.toast(f"{c.friendly} shows a rainbow for 5 seconds.")
        self.page.run_thread(work)

    def hardware(self, hw):
        """The tested preset as one card. The raw fields only when asked for."""
        preset = asdict(HW_PRESET)
        matches = all(getattr(hw, k) == preset[k] for k in HW_KEYS)

        def use_preset(_):
            for k in HW_KEYS:
                setattr(hw, k, preset[k])
            self.refresh_editor()

        def toggle(_):
            self.opened["hw"] = not self.opened.get("hw")
            self.refresh_editor()

        summary = f"ESP8266 · {hw.pin} · {hw.leds} LEDs · {hw.method} · {hw.order}"
        face = ft.Container(width=34, height=34, border_radius=17, bgcolor="#F1EFEA",
                            content=ft.Container(border_radius=12, border=ft.Border.all(2.5, ACCENT), margin=5))
        head = ft.Row([face, ft.Column([text(HW_NAME if matches else "Custom hardware", weight=ft.FontWeight.W_600),
                                        text(summary, 12, SUB)], spacing=3, tight=True, expand=True),
                       ft.Row([ft.Icon(ft.Icons.CHECK, size=16, color="#7FD6E0"),
                               text("Tested on this clock", 13, "#7FD6E0")], spacing=6, tight=True) if matches
                       else link(f"Use {HW_NAME}", use_preset)], spacing=14)
        parts = [caption("Hardware"),
                 ft.Container(head, bgcolor=ACCENT_BG if matches else SUNK, border_radius=12,
                              border=ft.Border.all(1, "#2E5A63" if matches else LINE),
                              padding=ft.Padding.symmetric(horizontal=18, vertical=14)),
                 ft.TextButton("Hide custom hardware" if self.opened.get("hw") else "Custom hardware",
                               icon=ft.Icons.EXPAND_LESS if self.opened.get("hw") else ft.Icons.CHEVRON_RIGHT,
                               on_click=toggle, style=ft.ButtonStyle(color=SUB))]
        if self.opened.get("hw"):
            parts.append(ft.Row([
                attr(hw, "board", "Board", width=150), attr(hw, "pin", "Data pin", width=130),
                pick("Driver", hw.method, {m: m for m in ("bit_bang", "esp8266_uart", "esp8266_dma")},
                     lambda v: setattr(hw, "method", v), 170),
                attr(hw, "variant", "LED type", width=130),
                pick("Colour order", hw.order, {o: o for o in ("GRB", "RGB", "BRG", "GRBW")},
                     lambda v: setattr(hw, "order", v), 140),
                attr(hw, "gamma", "Gamma", float, width=100), attr(hw, "leds", "LEDs", int, width=100),
                attr(hw, "start_brightness", "Start brightness", int, width=140),
                attr(hw, "max_brightness", "Max brightness", int, width=140)], wrap=True, spacing=14,
                run_spacing=14, vertical_alignment=ft.CrossAxisAlignment.START))
        return ft.Column(parts, spacing=8)

    # ---------- apply ----------
    def apply_dialog(self, _=None):
        """Puts the open design on its clock: the one main action."""
        device = self.device
        if not device:
            return
        i = self.didx if self.didx is not None else device.active
        view = device.showing(i)
        if not self.connected:
            self.toast("Connect Home Assistant first. Applying sends the design through it.")
            self.connect_dialog()
            return
        try:
            projects.check(self.project)
        except projects.ProjectError as err:
            self.problems_dialog("Fix these before applying", err.problems)
            return
        log = ft.Column([caption("Sending...")], spacing=6)
        close = button("Close", self.close, disabled=True)
        extra = ft.Column(spacing=10)
        r = view.ring
        if r.made_from and not any(s.get("entity_id") == r.entity for s in self.states):
            extra.controls.append(info(f"{r.entity} is not in Home Assistant yet, so the ring stays dark until the "
                                       "package that makes it is added.", ft.Icons.EXTENSION_OUTLINED,
                                       ("Copy package", lambda _: self.copy(setups.package([r.made_from]),
                                                                            "the package"))))
        updated = not device.previous_names or (bool(self.mark("flashed", device))
                                                and not self.firmware_stale(device))

        def line(ok, words):
            log.controls.append(ft.Row([ft.Icon(ft.Icons.CHECK_CIRCLE if ok else ft.Icons.ERROR_OUTLINE, size=18,
                                                color=GREEN if ok else WARN),
                                        text(words, 13, TEXT if ok else WARN, expand=True)], spacing=10,
                                       vertical_alignment=ft.CrossAxisAlignment.START))
            self.page.update()

        def remove_old(_):
            try:
                publish.remove_old_automation(self.ha)
                extra.controls.append(text("Removed the old brightness automation.", 13, GREEN))
            except RuntimeError as err:
                extra.controls.append(text(str(err), 13, WARN))
            self.page.update()

        def work():
            log.controls.clear()
            ok = publish.apply(self.ha, view, line, updated=updated)
            if ok:
                device.active = i
                self.set_mark("applied", device, template_hash(view))
                self.states = self.ha.states()
                edited()
            log.controls.append(ft.Container(text(
                f"{device.friendly} now shows {view.design.name}." if ok else
                "It did not work. The lines above say why.", 14, GREEN if ok else WARN,
                weight=ft.FontWeight.W_600), padding=ft.Padding.only(top=6)))
            try:
                if publish.old_automation(self.ha):
                    extra.controls.append(note("The brightness automation from an earlier version is still in Home "
                                               "Assistant. The clock dims itself once it has this version's "
                                               "firmware. After updating the clock, remove the automation.",
                                               ("Remove it", remove_old)))
            except RuntimeError:
                pass
            close.disabled = False
            self.refresh()

        self.dialog(f"Apply {view.design.name} to {device.friendly}", ft.Column([log, extra], spacing=14, tight=True),
                    [close], 640, scrollable=True)
        self.page.run_thread(work)
