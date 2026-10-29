"""Ring Studio's one window: projects and clocks on the left, one editor in the middle, the live ring on the right.

The App is put together from one part per area of the screen (the mixins below). This file holds what they
share: the open project, undo, Home Assistant and dialogs.
"""

import os
import threading
import time

import flet as ft

from .. import homeassistant, project as projects, settings
from ..model import Project, project_from_dict
from ..storage import Secrets
from .clock import ClockPage
from .design import DesignEditor
from .dialogs import Dialogs
from .files import Files
from .flash import Flash
from .kit import (ACCENT, BAR, BG, HOOKS, OK, RAISED, SUB, WARN, button, caption, field, mounted, state_of, text)
from .new_design import NewDesign
from .preview import Preview
from .sidebar import Sidebar
from .yaml_view import YamlView


class App(Sidebar, DesignEditor, ClockPage, Preview, Dialogs, Files, Flash, NewDesign, YamlView):
    def __init__(self, page: ft.Page):
        self.page, self.s = page, settings.load_settings()
        self.vault = Secrets()
        draft = settings.load_draft() or {}
        old = {**draft.pop("secrets", {}), **({"ha_token": self.s.pop("ha_token")} if "ha_token" in self.s else {})}
        if old:  # secrets from before they moved to the keychain
            self.vault.update({k: v for k, v in old.items() if not self.vault.get(k)})
            settings.save_settings(self.s)
        self.path = self.s.get("project_path") if os.path.exists(self.s.get("project_path") or "") else None
        self.saved, restored, self.example = None, False, None
        if self.path:
            try:
                self.saved = state_of(projects.open_file(self.path))
            except (OSError, projects.ProjectError):
                self.path = None
        example = dict((n, p) for n, p, _ in projects.examples()).get(self.s.get("example") or "")
        if not self.path and example:  # the draft started from an example: compare against it
            self.example, self.saved = self.s["example"], state_of(projects.open_file(example))
        if draft.get("clocks") or draft.get("note"):
            try:  # the draft can hold half-typed values, so it is checked on save, apply and flash instead
                self.project = project_from_dict(draft)
            except (KeyError, TypeError, ValueError, AttributeError):
                self.project = Project()  # a damaged draft is not used
            restored = (self.path or self.example) is not None and state_of(self.project) != self.saved
        elif self.path:
            self.project = project_from_dict(self.saved)
        else:
            self.project = self.first_example()
        self.project.secrets = self.vault.all()
        self.idx, self.connected, self.timer = 0, False, None
        self.didx = self.project.clocks[0].active if self.project.clocks else None  # open design; None = clock page
        self.opened = {"bright": True, "device": False, "advanced": False, "more": False, "projects": True,
                       "checklist": False, "hw": False}
        self.recent = []  # colours picked this session, newest first
        self.renaming = False  # the design title is being edited
        self.view, self.yaml_text, self.yaml_tab, self.yaml_timer = "editor", None, "project", None
        self.code, self.yaml_status, self.yaml_issue = None, text("", 12, SUB), ft.Container(visible=False)
        self.preview_colors, self.preview_note = None, "Connect Home Assistant to see the live ring."
        self.snap, self.times, self.at, self.lines, self.sent, self.sample_for = None, [], 0, [], False, []
        self.states, self.place = [], None  # Home Assistant states and (lat, lon, name)
        self.curve = ft.Container()
        self.painting = threading.RLock()  # one page update at a time: the preview paints from a timer
        self.history, self.future, self.last, self.last_edit = [], [], state_of(self.project), 0.0
        self.title = text("", 17, weight=ft.FontWeight.W_700)
        self.title_dot = ft.Container(width=8, height=8, border_radius=4, bgcolor=WARN, tooltip="Unsaved changes")
        page.on_keyboard_event = self.on_key
        HOOKS[:] = [self.on_edit]
        self.picker = ft.FilePicker()
        self.clipboard = ft.Clipboard()
        page.services.extend([self.picker, self.clipboard])
        page.title, page.bgcolor, page.padding = "Ring Studio", BG, 0
        page.theme_mode, page.dark_theme = ft.ThemeMode.DARK, ft.Theme(color_scheme_seed=ACCENT)
        page.window.width, page.window.height, page.window.min_width = 1440, 940, 1080
        self.bar, self.side = ft.Container(), ft.Container(width=280)
        self.editor = ft.Column(scroll=ft.ScrollMode.AUTO, expand=True, spacing=20)
        self.preview = ft.Column(horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=18)
        page.add(ft.Column([self.bar, ft.Row([
            self.side,
            ft.Container(self.editor, expand=True, padding=ft.Padding.only(left=36, right=16, top=32, bottom=24)),
            ft.Container(self.preview, width=380, padding=ft.Padding.only(top=40, right=28))],
            expand=True, spacing=0, vertical_alignment=ft.CrossAxisAlignment.START)], expand=True, spacing=0))
        if self.s.get("ha_url") and self.vault.get("ha_token"):
            page.run_thread(self.connect)
        threading.Thread(target=self.poll, daemon=True).start()
        self.refresh()
        if restored:
            self.toast(f"Restored your unsaved changes to {self.project_name}.")

    # ---------- state ----------
    @property
    def device(self):
        """The clock that is open, as it is."""
        if not self.project.clocks:
            return None
        self.idx = max(0, min(self.idx, len(self.project.clocks) - 1))
        return self.project.clocks[self.idx]

    @property
    def clock(self):
        """The open clock with the open design on it: what the editor and the preview work on. Its design and
        hardware are the real ones, so edits through it stick. On the clock's own page, the design it shows."""
        d = self.device
        if not d:
            return None
        if self.didx is None or self.didx >= len(d.designs):
            return d
        return d.showing(self.didx)

    @property
    def design(self):
        d = self.device
        return d.designs[self.didx] if d and self.didx is not None and self.didx < len(d.designs) else None

    @property
    def ha(self):
        return homeassistant.HomeAssistant(self.s.get("ha_url", ""), self.vault.get("ha_token"))

    def save_setting(self, key, value):
        self.s[key] = value
        settings.save_settings(self.s)

    def mark(self, kind, c):
        """What the app remembers about a clock (applied, flashed, verified, backup), kept by the clock's id so a
        rename does not lose it. Records from before ids were kept under the device name and move over."""
        key = f"{kind}_{c.id}"
        if key not in self.s and f"{kind}_{c.name}" in self.s:
            self.save_setting(key, self.s.pop(f"{kind}_{c.name}"))
        return self.s.get(key)

    def set_mark(self, kind, c, value):
        self.save_setting(f"{kind}_{c.id}", value)

    # ---------- undo ----------
    def record(self, new_step=False):
        """Keeps an undo step per burst of typing (a pause of a second starts a new step).
        Bigger changes, like adding a clock or opening a project, are always a step of their own."""
        snap = state_of(self.project)
        if snap == self.last:
            return
        if new_step or time.monotonic() - self.last_edit > 1.0:
            self.history = (self.history + [self.last])[-50:]
            self.future.clear()
        self.last, self.last_edit = snap, 0.0 if new_step else time.monotonic()

    def step(self, back):
        src, dst = (self.history, self.future) if back else (self.future, self.history)
        if not src:
            self.toast("Nothing to undo" if back else "Nothing to redo")
            return
        dst.append(state_of(self.project))
        self.last = src.pop()
        self.project = project_from_dict(self.last)
        self.project.secrets = self.vault.all()
        self.idx = min(self.idx, max(len(self.project.clocks) - 1, 0))
        if self.didx is not None and self.device:
            self.didx = min(self.didx, len(self.device.designs) - 1)
        self.snap, self.preview_colors = None, None
        self.refresh()
        self.toast("Undone" if back else "Redone")

    def on_key(self, e):
        if not (e.ctrl or e.meta):
            return
        key = e.key.upper()
        if self.view == "yaml" and key in ("Z", "Y"):
            return  # the YAML editor has its own undo
        if key == "Z":
            self.step(back=not e.shift)
        elif key == "Y":
            self.step(back=False)
        elif key == "E" and self.project.clocks:
            self.apply_dialog()
        elif key == "S":
            self.save_project_as() if e.shift else self.save_project()

    def on_edit(self):
        self.record()
        settings.save_draft(state_of(self.project))
        self.paint_title()
        if mounted(self.curve):
            self.curve.content = self.curve_view()
            self.curve.update()
        self.schedule_preview()

    # ---------- painting ----------
    def refresh(self):
        with self.painting:
            self._refresh()
        self.schedule_preview(0)

    def _refresh(self):
        self.bar.content, self.side.content = self.top_bar(), self.sidebar()
        self.bar.bgcolor, self.bar.padding = BAR, ft.Padding.symmetric(horizontal=28, vertical=12)
        self.side.padding = ft.Padding.only(left=16, right=12, top=22, bottom=16)
        self.editor.controls = self.banner() + (self.editor_view() if self.view == "editor" else self.yaml_view())
        self.record(new_step=True)
        settings.save_draft(state_of(self.project))
        self.paint_title()
        self.preview.controls = self.preview_view()
        self.page.update()

    def refresh_editor(self):
        """After a change inside the editor: the editor and the sidebar repaint, the preview follows."""
        from .kit import edited
        edited()
        self.editor.controls = self.banner() + self.editor_view()
        self.side.content = self.sidebar()
        self.page.update()

    def toast(self, value):
        self.page.show_dialog(ft.SnackBar(text(value)))

    def dialog(self, title, content, actions, width=620, scrollable=False):
        dlg = ft.AlertDialog(title=text(title, 22, weight=ft.FontWeight.W_700), bgcolor=RAISED, scrollable=scrollable,
                             content=ft.Container(content, width=width), actions=actions,
                             shape=ft.RoundedRectangleBorder(radius=20))
        self.page.show_dialog(dlg)
        return dlg

    def close(self, _=None):
        self.page.pop_dialog()

    def confirm(self, title, body, label, on_yes, danger=True):
        def yes(_):
            self.close()
            on_yes()
        body = text(body, color=SUB) if isinstance(body, str) else body
        self.dialog(title, body, [button("Cancel", self.close), button(label, yes, danger=danger,
                                                                      primary=not danger)], 480)

    def copy(self, value, what):
        async def go():
            await self.clipboard.set(value)
            self.toast(f"Copied {what}.")
        self.page.run_task(go)

    # ---------- Home Assistant ----------
    def connect(self):
        try:
            self.states = self.ha.states()
            self.connected = True
            cfg = self.ha.config()
            self.place = (cfg["latitude"], cfg["longitude"], cfg.get("location_name") or "home")
        except (RuntimeError, KeyError, TypeError, ValueError) as err:
            self.connected, self.preview_note = False, str(err)
        self.refresh()

    def poll(self):
        """Refreshes clock status once a minute while connected."""
        while True:
            time.sleep(60)
            if not self.connected:
                continue
            try:
                self.states = self.ha.states()
            except RuntimeError:
                continue
            with self.painting:
                self.side.content = self.sidebar()
                self.page.update()

    @property
    def state_map(self):
        """entity_id -> {"state", "attributes"}: Home Assistant's when connected, the made-up one otherwise."""
        if self.connected:
            return {s["entity_id"]: s for s in self.states}
        from .. import sample
        from .kit import now
        return sample.catalogue(now())

    def clock_state(self, c):
        return homeassistant.clock_status(c, self.states) if self.connected else None

    def connect_dialog(self, _=None):
        out = text(f"Connected · {len(self.states)} entities" if self.connected else "", 13, OK)
        warn = text(homeassistant.plain_http_warning(self.s.get("ha_url", "")) or "", 12, WARN)

        def set_url(v):
            self.save_setting("ha_url", v.strip())
            warn.value = homeassistant.plain_http_warning(v) or ""
            warn.update()

        def go(_):
            try:
                homeassistant.check_url(self.s.get("ha_url", ""))
            except RuntimeError as err:
                out.value, out.color = str(err), WARN
                out.update()
                return
            out.value, out.color = "Connecting…", SUB
            out.update()
            self.connect()
            out.value = f"Connected · {len(self.states)} entities" if self.connected else self.preview_note
            out.color = OK if self.connected else WARN
            out.update()

        self.dialog("Home Assistant", ft.Column([
            text("Used for picking entities, the live preview and applying designs to clocks.", color=SUB),
            field("URL", lambda: self.s.get("ha_url", ""), set_url, width=560,
                  hint_text="https://homeassistant.local:8123"),
            warn,
            field("Long-lived access token", lambda: self.vault.get("ha_token"),
                  lambda v: self.vault.set("ha_token", v), width=560, password=True, can_reveal_password=True),
            caption(f"The token is kept in {self.vault.where}."),
            caption("Create one in Home Assistant under your profile, Security, Long-lived access tokens. Applying "
                    "designs needs a token from an administrator."),
            out], spacing=18, tight=True), [button("Close", self.close), button("Connect", go, primary=True)])


def main(page: ft.Page):
    App(page)
