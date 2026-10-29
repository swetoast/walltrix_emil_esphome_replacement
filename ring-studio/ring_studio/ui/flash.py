"""Flash, update, back up and restore a clock, with its WiFi and keys in the same place."""

import os
import re
import time
from datetime import datetime

import flet as ft

from .. import flashing, generate, project as projects, storage
from .kit import (ACCENT, CARD, GREEN, LINE, MONO, OK, ON_ACCENT, SUB, SUNK, TEXT, WARN, box, button, caption, field,
                  firmware_hash, link, note, text)


class Flash:
    def wifi_section(self, on_change):
        """WiFi and keys. Stored in the keychain, never in project files or the draft. Folded to one line once
        WiFi is set."""
        sec = self.project.secrets
        generate.secrets_file(self.project)  # makes missing keys, never replaces one
        self.keep_secrets()
        put = lambda k: (lambda v: (sec.__setitem__(k, v), self.vault.set(k, v), on_change()))  # noqa: E731
        wifi_set = sec.get("wifi_ssid", "YOUR_WIFI_NAME") not in ("", "YOUR_WIFI_NAME")
        key_ok = generate.valid_api_key(sec.get("api_key", ""))
        holder = ft.Container()
        api_box = box(value=sec.get("api_key", ""), read_only=True, password=True, can_reveal_password=True,
                      width=440, text_style=ft.TextStyle(font_family=MONO))

        def shown(key):
            value = sec.get(key, "")
            return "" if value in ("YOUR_WIFI_NAME", "YOUR_WIFI_PASSWORD") else value

        def regen(key):
            def go():
                sec[key] = generate.gen_secret(key)
                self.vault.set(key, sec[key])
                api_box.value = sec.get("api_key", "")
                self.toast(f"New {key.replace('_', ' ')} made. Flash over USB so the clock gets it.")
                on_change()
                paint(True)
            self.confirm("Make a new key", "The clock keeps its old key until you flash it over USB, and Home "
                         "Assistant will ask for the new one. Continue?", "Make new key", go)

        def paint(open_):
            if not open_:
                holder.content = ft.Row([ft.Icon(ft.Icons.WIFI, size=18, color=SUB),
                                         text(f"WiFi: {sec.get('wifi_ssid')}" if wifi_set else "WiFi is not set", 13,
                                              TEXT if wifi_set else WARN, expand=True),
                                         text("API key ready" if key_ok else "API key missing", 12,
                                              OK if key_ok else WARN),
                                         link("Change" if wifi_set else "Set WiFi", lambda _: (paint(True),
                                                                                              self.page.update()))],
                                        spacing=10)
                return
            holder.content = ft.Column([
                ft.Row([ft.Icon(ft.Icons.LOCK_OUTLINE, size=16, color=SUB),
                        text(f"Stored in {self.vault.where}. Never in project files or the draft.", 12, SUB,
                             expand=True)], spacing=8),
                ft.Row([field("WiFi name", lambda: shown("wifi_ssid"), put("wifi_ssid"), width=300,
                              hint_text="Your network's name"),
                        field("WiFi password", lambda: shown("wifi_password"), put("wifi_password"), width=300,
                              password=True, can_reveal_password=True)], spacing=14, wrap=True),
                field("Fallback hotspot password", lambda: sec.get("ap_password", ""), put("ap_password"), width=300,
                      password=True, can_reveal_password=True),
                caption("The clock opens its own hotspot with this password when it cannot join your WiFi."),
                ft.Column([caption("API key. Home Assistant asks for it as the encryption key when you add the "
                                   "clock."),
                           ft.Row([api_box, link("Copy", lambda _: self.copy(sec.get("api_key", ""), "the API key"))],
                                  spacing=8)], spacing=6),
                ft.Row([link("Make a new API key", lambda _: regen("api_key"), SUB),
                        link("Make a new OTA password", lambda _: regen("ota_password"), SUB)], spacing=4)],
                spacing=12, tight=True)

        paint(not wifi_set)
        return ft.Container(holder, bgcolor=SUNK, border_radius=12, padding=ft.Padding.symmetric(horizontal=16,
                                                                                                 vertical=12))

    def firmware_dialog(self, _=None):
        """Flash, update, back up and restore. Each job shows as steps; the raw log is one click away."""
        c, st = self.device, {"steps": [], "port": None}
        generate.secrets_file(self.project)  # makes missing keys before anything checks them, never replaces one
        self.keep_secrets()
        backup = {"path": self.mark("backup", c) or os.path.join(storage.HOME, "backups", f"{c.name}_stock_4MB.bin")}
        log = ft.ListView(height=180, spacing=2, auto_scroll=True)
        log_box = ft.Container(log, bgcolor=SUNK, border_radius=12, padding=12, visible=False)
        rows = ft.Column(spacing=0)
        progress = ft.ProgressBar(value=None, color=ACCENT, bgcolor=SUNK, bar_height=6, border_radius=3)
        steps_box = ft.Container(ft.Column([rows, ft.Container(progress, padding=ft.Padding.only(left=38))],
                                           spacing=6), bgcolor=CARD, border_radius=14, visible=False,
                                 padding=ft.Padding.symmetric(horizontal=14, vertical=10))
        tools = text("", 12, SUB)
        port_dd = ft.Dropdown(width=340, dense=True, filled=True, fill_color=SUNK, border_color=SUNK, text_size=14,
                              focused_border_color=ACCENT, border_radius=10,
                              content_padding=ft.Padding.symmetric(horizontal=14, vertical=10))
        port_hint = text("", 12, SUB)
        backup_name = text("", 13, mono=True)
        backup_state = text("", 12, SUB)
        problems = ft.Column(spacing=8)
        buttons = []

        def details(_=None, show=None):
            log_box.visible = not log_box.visible if show is None else show
            more.content = "Hide details" if log_box.visible else "Show details"
            more.icon = ft.Icons.EXPAND_LESS if log_box.visible else ft.Icons.CHEVRON_RIGHT
            self.page.update()

        more = ft.TextButton("Show details", icon=ft.Icons.CHEVRON_RIGHT, on_click=details, visible=False,
                             style=ft.ButtonStyle(color=SUB))

        def check_secrets():
            sec = self.project.secrets
            problems.controls = []
            if not generate.valid_api_key(sec.get("api_key", "")):
                problems.controls.append(note("The API key is invalid, so the flash will fail. Make a new one "
                                              "under WiFi."))
            if 0 < len(sec.get("wifi_password", "")) < 8:
                problems.controls.append(note("The WiFi password is shorter than 8 characters, which ESPHome "
                                              "refuses."))
            if sec.get("wifi_ssid", "YOUR_WIFI_NAME") in ("", "YOUR_WIFI_NAME"):
                problems.controls.append(note("WiFi is not set, so the clock will only open its fallback hotspot."))
            try:
                problems.update()
            except (RuntimeError, AssertionError):
                pass

        # ---- ports and backup ----
        def fill_ports(_=None):
            ports, saved = flashing.serial_ports(), self.s.get("port")
            found = ports[0] if ports and flashing.is_clock_port(ports[0]) else None
            fallback = "COM4" if os.name == "nt" else "/dev/ttyUSB0"
            choice = found if found and saved not in ports else saved or (ports[0] if ports else fallback)
            port_dd.options = [ft.DropdownOption(key=p, text=p) for p in dict.fromkeys(ports + [choice])]
            port_dd.value = st["port"] = choice
            port_hint.value = ("Found the clock's USB chip and picked it for you." if choice == found else
                               "No USB serial port found. Plug the clock in and press refresh." if not ports else "")
            port_hint.color = "#7FD6E0" if choice == found else WARN if not ports else SUB
            if problem := flashing.port_problem(choice, ports):
                port_hint.value, port_hint.color = problem, WARN
            port_hint.width = 360
            self.page.update()

        def set_port(e):
            st["port"] = e.control.value
            self.save_setting("port", st["port"])

        port_dd.on_select = set_port

        def paint_backup():
            path = backup["path"]
            backup_name.value = os.path.basename(path)
            exists = os.path.exists(path)
            if exists:
                when = datetime.fromtimestamp(os.path.getmtime(path))
                checked = self.mark("verified", c) == f"{path}|{os.path.getmtime(path)}"
                backup_state.value = (f"Backed up {when:%d %b %H:%M} · {os.path.getsize(path) / 1048576:.1f} MB · "
                                      + ("checked against the clock" if checked else "not checked yet"))
                backup_state.color = GREEN if checked else SUB
            else:
                backup_state.value, backup_state.color = "No backup yet. Back up before the first USB flash.", WARN
            b_restore.disabled = not exists

        async def change_backup(_):
            if path := await self.picker.save_file(dialog_title="Backup file", file_name=os.path.basename(
                    backup["path"]), file_type=ft.FilePickerFileType.CUSTOM, allowed_extensions=["bin"]):
                backup["path"] = path
                self.set_mark("backup", c, path)
                paint_backup()
                self.page.update()

        # ---- jobs ----
        def paint_steps():
            marks = {"todo": (None, LINE, "#6F7A86"), "now": (None, ACCENT, TEXT), "done": (ft.Icons.CHECK, GREEN, TEXT),
                     "fail": (ft.Icons.CLOSE, WARN, WARN)}
            rows.controls = []
            for title, sub, state, took in st["steps"]:
                icon, col, fg = marks[state]
                badge = ft.Container(ft.Icon(icon, size=14, color=ON_ACCENT) if icon else None, width=24, height=24,
                                     border_radius=12, bgcolor=col if icon else None,
                                     border=None if icon else ft.Border.all(2, col), alignment=ft.Alignment.CENTER)
                rows.controls.append(ft.Container(ft.Row([
                    badge, ft.Column([text(title, 14, fg, ft.FontWeight.W_600 if state == "now" else None),
                                      caption(sub)], spacing=2, tight=True, expand=True),
                    text(took or "", 12, SUB)], spacing=14), padding=ft.Padding.symmetric(vertical=8)))

        def out(line):
            log.controls.append(text(line, 12, SUB, mono=True, selectable=True))
            if m := re.search(r"\((\d{1,3}) ?%\)|\b(\d{1,3})%", line):
                progress.value = min(int(m.group(1) or m.group(2)), 100) / 100
            self.page.update()

        def busy(on):
            for b in buttons:
                b.disabled = on
            port_dd.disabled = on
            if not on:
                paint_backup()
            self.page.update()

        def job(*steps):
            st["steps"] = [[title, sub, "todo", None] for title, sub, _ in steps]
            log.controls.clear()
            steps_box.visible = more.visible = True

            def work():
                busy(True)
                code = 0
                for i, (title, _, step) in enumerate(steps):
                    st["steps"][i][2], progress.value, began = "now", None, time.monotonic()
                    paint_steps()
                    out(f"> {title}")
                    try:
                        code = step()
                    except OSError as err:
                        out(str(err))
                        code = 1
                    took = int(time.monotonic() - began)
                    st["steps"][i][2:] = ["fail" if code else "done", f"{took // 60}:{took % 60:02d}" if took >= 60
                                          else f"{took} s"]
                    if code:
                        out(f"Stopped: {title} failed (exit {code}).")
                        if problem := flashing.port_problem(st["port"] or "", flashing.serial_ports()):
                            out(problem)
                            port_hint.value, port_hint.color = problem, WARN
                        details(show=True)
                        break
                progress.value = 1 if not code else 0
                flashing.forget_build_secrets()
                paint_steps()
                paint_tools()
                busy(False)
                self.refresh_editor()
            self.page.run_thread(work)

        def paint_tools():
            v = flashing.tool_versions()
            tools.value = (f"ESPHome {v['esphome']} · esptool {v['esptool']}" if all(v.values())
                           else "ESPHome is not installed yet. It installs the first time you flash.")
            tools.color = SUB if all(v.values()) else WARN

        def port():
            return (st["port"] or "").split(" · ")[0]

        def install():
            return ("Install tools", "Already installed" if all(flashing.tool_versions().values())
                    else "ESPHome and esptool, into this Python",
                    lambda: 0 if all(flashing.tool_versions().values()) else flashing.install_tools(out))

        def prepare():
            def step():
                try:
                    projects.check(self.project, for_export=True)
                except projects.ProjectError as err:
                    for problem in err.problems:
                        out(problem)
                    return 1
                generate.write_files(flashing.BUILD, generate.repo_files(self.project, self.source_name))
                self.keep_secrets()
                out(f"Wrote config to {flashing.BUILD}")
                return 0
            return "Prepare config", f"{c.name}.yaml and secrets", step

        def esphome(command, title, sub, device=None):
            def step():
                code = flashing.run(flashing.esphome(command, f"{c.name}.yaml", device and device()), out,
                                    cwd=os.path.join(flashing.BUILD, "config"))
                if not code and command == "upload":  # remember what the clock has, to spot needed updates
                    self.set_mark("flashed", c, firmware_hash(c))
                return code
            return title, sub, step

        def esptool(title, sub, args, after=None):
            def step():
                if args == flashing.RESTORE and not os.path.exists(backup["path"]):
                    out(f"No backup file at {backup['path']}.")
                    return 1
                os.makedirs(os.path.dirname(os.path.abspath(backup["path"])), exist_ok=True)
                code = flashing.run(flashing.esptool(port(), *args, backup["path"]), out)
                if os.path.exists(backup["path"]):
                    storage.private(backup["path"])  # the stock firmware holds its old WiFi settings
                if not code and after:
                    after()
                return code
            return title, sub, step

        def checked():
            p = backup["path"]
            storage.private(p)
            self.set_mark("verified", c, f"{p}|{os.path.getmtime(p)}")

        # Over the air the clock is reached at the address it has now: after a rename that is its old name.
        reach = (c.previous_names[-1] if c.previous_names and self.firmware_stale(c) else c.name) + ".local"
        compile_step = esphome("compile", "Compile firmware", "The first build downloads the ESP8266 toolchain")
        b_flash = button("Flash over USB", lambda _: job(install(), prepare(), compile_step, esphome(
            "upload", "Upload over USB", "About 30 seconds", port)), primary=True)
        b_ota = button("Update over WiFi", lambda _: job(install(), prepare(), compile_step, esphome(
            "upload", "Upload over WiFi", f"To {reach}", lambda: reach if reach != f"{c.name}.local" else "OTA")))
        b_backup = button("Back up stock", lambda _: job(
            install(), esptool("Read 4 MB from the clock", "About a minute", flashing.BACKUP),
            esptool("Check the backup", "Compares the file with the clock", flashing.VERIFY, checked)))
        b_restore = button("Restore stock", lambda _: self.confirm(
            "Restore stock firmware", "This replaces the ESPHome firmware with the backup. Continue?", "Restore",
            lambda: job(install(), esptool("Write the backup to the clock", "About a minute", flashing.RESTORE))),
            danger=True)
        buttons += [b_backup, b_flash, b_ota, b_restore]

        check_secrets()
        paint_tools()
        paint_backup()
        port_col = ft.Column([caption("Serial port"), ft.Row([port_dd, ft.IconButton(
            ft.Icons.REFRESH, tooltip="Look for ports again", on_click=fill_ports, icon_color=SUB)], spacing=6),
            port_hint], spacing=6, tight=True)
        backup_col = ft.Column([caption("Stock backup"), ft.Container(ft.Row([
            ft.Container(backup_name, expand=True), link("Change", change_backup, SUB)]),
            bgcolor=SUNK, border_radius=10, width=300, padding=ft.Padding.only(left=14, right=4)), backup_state],
            spacing=6, tight=True)
        self.dialog(f"Flash {c.friendly}", ft.Column([
            self.wifi_section(check_secrets), problems,
            ft.Row([port_col, backup_col], spacing=16, vertical_alignment=ft.CrossAxisAlignment.START),
            caption("The first flash goes over USB. After that, updates go over WiFi."),
            ft.Row([ft.Row([b_flash, b_ota, b_backup], spacing=10, tight=True), b_restore],
                   alignment=ft.MainAxisAlignment.SPACE_BETWEEN, wrap=True),
            steps_box, more, log_box, tools], spacing=16, tight=True),
            [button("Close", self.close)], 780, scrollable=True)
        fill_ports()
