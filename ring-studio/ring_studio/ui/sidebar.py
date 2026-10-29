"""The top bar, the sidebar (projects, then clocks with their designs, then Home Assistant) and the welcome banner."""

import flet as ft

from ..model import new_clock, slug
from .kit import (ACCENT, ACCENT_BG, CARD, FAINT, GREEN, LINE, RAISED, SUB, TEXT, TOP_EDGE, WARN,
                  button, dot, edited, link, ring_color, segmented, since, status_dot, text)


class Sidebar:
    # ---------- top bar ----------
    def top_bar(self):
        logo = ft.Container(width=26, height=26, border_radius=13, border=ft.Border.all(4, ACCENT))

        def item(label, icon, act, keys=""):
            return ft.PopupMenuItem(content=ft.Row([ft.Icon(icon, size=18, color=SUB), text(label, 14),
                                                    ft.Container(expand=True), text(keys, 12, FAINT)],
                                                   spacing=12, width=250), on_click=act)

        menu = ft.PopupMenuButton(
            content=ft.Container(ft.Row([text("File", 14), ft.Icon(ft.Icons.ARROW_DROP_DOWN, color=SUB, size=18)],
                                        spacing=2, tight=True), padding=ft.Padding.symmetric(horizontal=10, vertical=8)),
            bgcolor=RAISED, menu_position=ft.PopupMenuPosition.UNDER, items=[
                item("New project", ft.Icons.ADD, self.new_project),
                item("Open project…", ft.Icons.FOLDER_OPEN, self.open_project),
                item("Save", ft.Icons.SAVE_OUTLINED, self.save_project, "Ctrl+S"),
                item("Save as…", ft.Icons.SAVE_AS_OUTLINED, self.save_project_as, "Ctrl+Shift+S"),
                ft.PopupMenuItem(),
                item("Undo", ft.Icons.UNDO, lambda _: self.step(True), "Ctrl+Z"),
                item("Redo", ft.Icons.REDO, lambda _: self.step(False), "Ctrl+Y"),
                ft.PopupMenuItem(),
                item("Project notes…", ft.Icons.STICKY_NOTE_2_OUTLINED, self.notes_dialog),
                item("Projects folder…", ft.Icons.FOLDER_OUTLINED, self.projects_folder_dialog),
                item("Getting started", ft.Icons.HELP_OUTLINE, self.show_welcome)])
        self.paint_title(update=False)
        return ft.Row([logo, text("Ring Studio", 17, weight=ft.FontWeight.W_700),
                       ft.Container(width=1, height=22, bgcolor=LINE), menu,
                       ft.Row([self.title, self.title_dot], spacing=10, tight=True),
                       ft.Container(expand=True),
                       segmented({"editor": "Editor", "yaml": "YAML"}, self.view, self.set_view),
                       button("Apply to clock", self.apply_dialog, primary=True, disabled=not self.project.clocks)],
                      spacing=14)

    # ---------- sidebar ----------
    def select(self, idx, didx, open_section=None):
        """Opens a design (didx) or the clock's own page (didx None)."""
        self.idx, self.didx, self.renaming = idx, didx, False
        self.at, self.sent, self.snap, self.preview_colors = 0, False, None, None
        self.yaml_text = None
        if open_section:
            self.opened[open_section] = True
        self.refresh()

    def heading(self, label, right=None, on_click=None, open_=None):
        parts = []
        if open_ is not None:
            parts.append(ft.Icon(ft.Icons.EXPAND_MORE if open_ else ft.Icons.CHEVRON_RIGHT, size=16, color=FAINT))
        parts += [text(label, 12, FAINT, ft.FontWeight.W_600), ft.Container(expand=True)]
        if right:
            parts.append(text(right, 12, FAINT))
        return ft.Container(ft.Row(parts, spacing=6), padding=ft.Padding.only(left=8, right=8, top=6, bottom=6),
                            on_click=on_click, ink=bool(on_click), border_radius=8)

    def projects_list(self):
        found = self.project_files()

        def toggle(_):
            self.opened["projects"] = not self.opened["projects"]
            self.side.content = self.sidebar()
            self.page.update()

        items = [self.heading("PROJECTS", str(len(found)), toggle, self.opened["projects"])]
        if not self.opened["projects"]:
            return items
        for name, path, sub, kind in found:
            on = (path == self.path) if kind != "example" else (self.example == name and not self.path)
            items.append(ft.Container(ft.Column([
                text(name, 13, TEXT, ft.FontWeight.W_600 if on else None, max_lines=1,
                     overflow=ft.TextOverflow.ELLIPSIS),
                text(sub, 11, SUB)], spacing=1, tight=True),
                bgcolor=ACCENT_BG if on else None, border_radius=10, ink=True, tooltip=path,
                padding=ft.Padding.only(left=30, right=10, top=7, bottom=7),
                on_click=lambda _, p=path, k=kind, n=name: self.open_listed(p, k, n)))
        items.append(ft.Row([link("+ New project", self.new_project, SUB), link("Open other…", self.open_project, SUB)],
                            spacing=0))
        return items

    def clock_line(self, c):
        """The clock's state as a dot and a short word, and what it shows."""
        st = self.clock_state(c)
        if st is None:
            return None, f"Shows {c.design.name}"
        if not st["found"]:
            return FAINT, "Not set up"
        if st["online"]:
            return GREEN, f"Online · shows {c.design.name}"
        return WARN, "Offline" + (f" since {since(st['since'])}" if st["since"] else "")

    def sidebar(self):
        items = self.projects_list()
        items += [ft.Container(height=1, bgcolor=CARD, margin=ft.Margin.symmetric(vertical=8)),
                  self.heading("CLOCKS")]
        for i, c in enumerate(self.project.clocks):
            colour, line = self.clock_line(c)
            on = i == self.idx and self.didx is None
            sub = ft.Row(([status_dot(colour)] if colour else []) + [text(line, 12, SUB, expand=True, max_lines=1,
                                                                           overflow=ft.TextOverflow.ELLIPSIS)],
                         spacing=6)
            items.append(ft.Container(
                ft.Row([dot(ring_color(c.ring), 26),
                        ft.Column([text(c.friendly, weight=ft.FontWeight.W_600, max_lines=1,
                                        overflow=ft.TextOverflow.ELLIPSIS), sub], spacing=2, tight=True, expand=True),
                        ft.Icon(ft.Icons.SETTINGS_OUTLINED, size=16, color=SUB if on else FAINT)], spacing=12),
                bgcolor=ACCENT_BG if on else None, border_radius=12, padding=10, ink=True,
                tooltip="The clock: setup, brightness and hardware", on_click=lambda _, i=i: self.select(i, None)))
            for j, d in enumerate(c.designs):
                picked = i == self.idx and self.didx == j
                items.append(ft.Container(ft.Row([
                    ft.Container(width=10, height=10, border_radius=5, bgcolor=ring_color(d.ring),
                                 border=ft.Border.all(1, LINE)),
                    text(d.name, 13, TEXT if picked else SUB, expand=True, max_lines=1,
                         overflow=ft.TextOverflow.ELLIPSIS),
                    text("On the clock", 11, GREEN) if j == c.active else ft.Container()], spacing=10),
                    bgcolor=ACCENT_BG if picked else None, border_radius=10, ink=True,
                    padding=ft.Padding.only(left=26, right=10, top=8, bottom=8),
                    on_click=lambda _, i=i, j=j: self.select(i, j)))
            items.append(ft.Container(link("+  New design", lambda _, i=i: self.new_design_dialog(i), FAINT),
                                      padding=ft.Padding.only(left=14, bottom=4)))
        items.append(link("+  Add clock", lambda _: self.add_clock(), SUB))
        ha = ft.Container(ft.Row([status_dot(GREEN if self.connected else FAINT),
                                  text("Home Assistant" if self.connected else "Connect Home Assistant", 13,
                                       TEXT if self.connected else SUB, expand=True),
                                  text(f"{len(self.states)} entities" if self.connected else "", 11, FAINT)],
                                 spacing=10),
                          padding=ft.Padding.symmetric(horizontal=12, vertical=12), border_radius=10, ink=True,
                          border=ft.Border.all(1, LINE), on_click=self.connect_dialog,
                          tooltip="Address and token")
        return ft.Column([ft.Column(items, spacing=2, scroll=ft.ScrollMode.AUTO, expand=True), ha], spacing=10)

    def add_clock(self):
        taken = {x.name for x in self.project.clocks}
        n = len(self.project.clocks) + 1
        while slug(f"Clock {n}") in taken:
            n += 1
        self.project.clocks.append(new_clock(f"Clock {n}"))
        edited()
        self.select(len(self.project.clocks) - 1, None, "device")
        self.toast(f"Added Clock {n}. Name it and set it up here, then give it a design.")

    # ---------- welcome ----------
    def show_welcome(self, _=None):
        self.save_setting("welcomed", False)
        self.refresh()

    def banner(self):
        """What a new user sees above the editor until they close it: what this is and how to carry on."""
        if self.s.get("welcomed"):
            return []

        def done(_):
            self.save_setting("welcomed", True)
            self.refresh()

        def then(action):
            return lambda _: (self.save_setting("welcomed", True), action())

        name = self.example or "Example Clock"
        words = (f"You are looking at {name}: one clock with designs running on sample data. Pick a design on the "
                 "left and change it, connect Home Assistant to use your own sensors, then set up your clock from "
                 "its page.")
        return [ft.Container(ft.Row([
            ft.Column([text("Welcome to Ring Studio", 16, weight=ft.FontWeight.W_700), text(words, 13, SUB),
                       ft.Row([button("Connect Home Assistant", then(self.connect_dialog), primary=True),
                               button("Set up the clock", then(lambda: self.select(0, None)))], spacing=12,
                              wrap=True)], spacing=10, expand=True),
            ft.IconButton(ft.Icons.CLOSE, icon_color=SUB, tooltip="Close. File > Getting started brings it back.",
                          on_click=done)], vertical_alignment=ft.CrossAxisAlignment.START),
            bgcolor=CARD, border_radius=16, border=TOP_EDGE, padding=ft.Padding.only(left=22, right=8, top=16, bottom=18))]

    def no_clocks(self):
        return [ft.Container(ft.Column([
            text("No clocks yet", 24, weight=ft.FontWeight.W_700),
            text("Add a clock, or open Example Clock under Projects on the left.", color=SUB),
            ft.Row([button("Add a clock", lambda _: self.add_clock(), primary=True)], spacing=12)],
            spacing=16), padding=ft.Padding.only(top=60))]
