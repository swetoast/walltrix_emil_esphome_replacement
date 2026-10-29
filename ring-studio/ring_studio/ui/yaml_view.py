"""The YAML view: the whole project as text to edit, and the files it makes, read only."""

import threading

import flet as ft
import flet_code_editor as fce

from .. import generate, project as projects, setups
from .kit import (ACCENT, BG, CODE_THEME, FAINT, GREEN, MONO, RAISED, SUB, SUNK, TEXT, WARN, WARN_BG, box, button,
                  caption, card, edited, state_of, text)


class YamlView:
    def set_view(self, view):
        if view == self.view:
            return
        self.view, self.yaml_text, self.yaml_tab = view, None, "project"
        self.refresh()

    def yaml_files(self):
        """The firmware of the open clock and the template of the open design, read only."""
        c = self.clock
        if not c:
            return {}
        try:
            firmware = generate.firmware_file(c, self.source_name)
        except (ValueError, KeyError, TypeError, AttributeError) as err:
            firmware = f"# The firmware cannot be made yet: {err}\n"
        out = {f"{c.name}.yaml": firmware, "Template": generate.template_file(c, self.source_name)}
        if c.ring.made_from:
            out["Package"] = setups.package([c.ring.made_from])
        return out

    def yaml_view(self):
        if self.yaml_text is not None:  # keep what is being typed, unless something else changed the project
            parsed, _ = projects.read(self.yaml_text)
            if parsed and state_of(parsed) != state_of(self.project):
                self.yaml_text = None
        if self.yaml_text is None:
            self.yaml_text = projects.dump(self.project, self.source_name)
        files = self.yaml_files()
        if self.yaml_tab not in files:
            self.yaml_tab = "project"
        editing = self.yaml_tab == "project"

        def tab(key, label):
            on = key == self.yaml_tab
            lock = [] if key == "project" else [ft.Icon(ft.Icons.LOCK_OUTLINE, size=13, color=FAINT,
                                                        tooltip="Read only, made from the project")]
            return ft.Container(ft.Row([text(label, 13, TEXT if on else SUB)] + lock, spacing=6, tight=True), ink=True,
                                padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                                border=ft.Border.only(bottom=ft.BorderSide(2, ACCENT if on else BG)),
                                on_click=lambda _: self.pick_tab(key))

        tabs = [tab("project", f"{self.source_name}.ringstudio")] + [tab(k, k) for k in files]
        self.code = fce.CodeEditor(
            value=self.yaml_text if editing else files[self.yaml_tab], language=fce.CodeLanguage.YAML,
            code_theme=CODE_THEME, read_only=not editing, autocomplete=editing,
            autocomplete_words=projects.WORDS, text_style=ft.TextStyle(font_family=MONO, size=13, height=1.5),
            gutter_style=fce.GutterStyle(background_color=SUNK, text_style=ft.TextStyle(color=FAINT, size=12),
                                         show_folding_handles=True),
            on_change=self.yaml_changed if editing else None, height=640)
        if editing:
            self.yaml_check(self.yaml_text, apply=False)
        else:
            self.yaml_status.value, self.yaml_status.color = "Made from the project. Change it there.", SUB
            self.yaml_issue.visible = False
        hint = ("Type and the preview follows. Autocomplete offers field names and values. Everything here also "
                "shows in the Editor view. Notes belong in the note fields: # comments are not kept."
                if editing else "This is what Save YAML files writes for the open clock. Secrets are left out.")
        return [ft.Row([text("YAML", 28, weight=ft.FontWeight.W_700), ft.Container(expand=True), self.yaml_status,
                        button("Save YAML files", self.export_dialog, icon=ft.Icons.FOLDER_ZIP_OUTLINED)],
                       spacing=16),
                ft.Row(tabs, spacing=2, wrap=True),
                ft.Container(self.code, border_radius=12, border=ft.Border.all(1, RAISED),
                             clip_behavior=ft.ClipBehavior.HARD_EDGE),
                self.yaml_issue, caption(hint)] + ([self.field_reference()] if editing else [])

    def pick_tab(self, key):
        self.yaml_tab = key
        self.editor.controls = self.banner() + self.yaml_view()
        self.page.update()

    def yaml_changed(self, e):
        self.yaml_text = e.control.value or ""
        if self.yaml_timer:
            self.yaml_timer.cancel()
        self.yaml_timer = threading.Timer(0.4, self.yaml_typed)
        self.yaml_timer.daemon = True
        self.yaml_timer.start()

    def yaml_typed(self):
        with self.painting:
            self.yaml_check(self.yaml_text)

    def yaml_check(self, value, apply=True):
        """Applies the text when it is a good project. Otherwise marks the lines and keeps the last good version."""
        project, problems = projects.read(value)
        if project:
            self.code.issues = []
            self.yaml_status.value, self.yaml_status.color = "Valid · applied", GREEN
            self.yaml_issue.visible = False
            if apply and state_of(project) != state_of(self.project):
                project.secrets = self.project.secrets
                self.project = project
                self.idx = min(self.idx, max(len(project.clocks) - 1, 0))
                if self.didx is not None and self.device:
                    self.didx = min(self.didx, len(self.device.designs) - 1)
                self.snap, self.preview_colors = None, None
                self.side.content = self.sidebar()
                edited()
        else:
            self.code.issues = [fce.Issue(line=line, message=msg, type=fce.IssueType.ERROR) for line, msg in problems]
            n = len(problems)
            self.yaml_status.value, self.yaml_status.color = f"{n} problem{'s' if n > 1 else ''}", WARN
            line, msg = problems[0]
            more = f" And {n - 1} more, marked in the margin." if n > 1 else ""
            self.yaml_issue.content = ft.Row([text(f"Line {line + 1}", 13, WARN, mono=True),
                                              text(f"{msg[:1].upper()}{msg[1:]} The preview shows the last valid "
                                                   f"version.{more}", 13, WARN, expand=True)], spacing=12)
            self.yaml_issue.visible, self.yaml_issue.bgcolor, self.yaml_issue.border_radius = True, WARN_BG, 10
            self.yaml_issue.padding = ft.Padding.symmetric(horizontal=14, vertical=12)
        if apply:
            self.page.update()

    def field_reference(self):
        rows = ft.Column(spacing=0)

        def paint(query=""):
            words = query.lower().split()
            rows.controls = [ft.Container(ft.Row([text(k, 12, "#7FD6E0", mono=True, width=230),
                                                  text(d, 12, SUB, expand=True)],
                                                 spacing=12, vertical_alignment=ft.CrossAxisAlignment.START),
                                          padding=ft.Padding.symmetric(vertical=6),
                                          border=ft.Border.only(bottom=ft.BorderSide(1, RAISED)))
                             for k, d in projects.FIELDS if all(w in (k + " " + d).lower() for w in words)]

        def search(e):
            paint(e.control.value or "")
            rows.update()

        paint()
        return card(ft.Column([ft.Row([text("Fields", 15, weight=ft.FontWeight.W_600), ft.Container(expand=True),
                                       box(hint_text="Search fields", width=260, on_change=search,
                                           prefix_icon=ft.Icons.SEARCH)]), rows], spacing=10), padding=20)
