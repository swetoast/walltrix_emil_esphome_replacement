"""Project files: the projects folder, open and save, notes, and Save YAML files."""

import os
from datetime import datetime

import flet as ft

from .. import generate, project as projects
from ..model import Project
from .kit import (ACCENT, FAINT, MONO, PACKAGES_LINE, SUB, SUNK, TEXT, attr, box, button, caption, diff_view,
                  field, note, state_of, text, when)

MAX_RECENT = 8


class Files:
    @property
    def dirty(self):
        return state_of(self.project) != (self.saved or state_of(Project()))

    @property
    def source_name(self):
        """The project's file name without .ringstudio, for file headers and Save as."""
        return projects.name_of(self.path) if self.path else self.example or "Untitled"

    @property
    def project_name(self):
        if self.path:
            return projects.name_of(self.path)
        return f"{self.example} (example)" if self.example else "Untitled"

    def paint_title(self, update=True):
        self.title.value = self.project_name
        self.title.color = TEXT if self.path else SUB
        self.title_dot.visible = self.dirty
        self.page.title = f"{self.project_name}{' (unsaved)' if self.dirty else ''} · Ring Studio"
        if update:
            try:
                self.title.update()
                self.title_dot.update()
            except (RuntimeError, AssertionError):
                pass

    # ---------- the projects folder ----------
    @property
    def projects_dir(self):
        return self.s.get("projects_dir") or os.path.join(os.path.expanduser("~"), "Documents", "Ring Studio")

    def project_files(self):
        """(name, path, line, kind) for the sidebar: the projects folder newest first, then projects opened from
        elsewhere, then the examples. kind is folder, recent or example."""
        cache = getattr(self, "_listing", {})
        self._listing = cache

        def clocks(path):
            try:
                stamp = os.path.getmtime(path)
            except OSError:
                return None, None
            if cache.get(path, (None,))[0] != stamp:
                try:
                    n = len(projects.open_file(path).clocks)
                except (OSError, projects.ProjectError):
                    n = None
                cache[path] = (stamp, n)
            return cache[path][1], datetime.fromtimestamp(stamp)

        def line(n, t):
            count = "cannot be read" if n is None else f"{n} clock{'s' if n != 1 else ''}"
            return f"{count} · {when(t)}" if t else count

        out, seen = [], set()
        folder = self.projects_dir
        try:
            names = [f for f in os.listdir(folder) if f.endswith(projects.SUFFIX)]
        except OSError:
            names = []
        paths = sorted((os.path.join(folder, f) for f in names), key=lambda p: -os.path.getmtime(p))
        for p in paths:
            n, t = clocks(p)
            out.append((projects.name_of(p), p, line(n, t), "folder"))
            seen.add(os.path.realpath(p))
        for p in self.s.get("recent") or []:
            if os.path.exists(p) and os.path.realpath(p) not in seen:
                n, t = clocks(p)
                out.append((projects.name_of(p), p, line(n, t), "recent"))
                seen.add(os.path.realpath(p))
        for name, p, _ in projects.examples():
            n, _t = clocks(p)
            out.append((name, p, f"example · {line(n, None)}", "example"))
        return out

    def remember(self, path):
        """Projects outside the projects folder are listed too, newest first."""
        if os.path.dirname(os.path.realpath(path)) == os.path.realpath(self.projects_dir):
            return
        recent = [path] + [p for p in self.s.get("recent") or [] if p != path]
        self.save_setting("recent", recent[:MAX_RECENT])

    def projects_folder_dialog(self, _=None):
        async def choose(_):
            if path := await self.picker.get_directory_path(dialog_title="Projects folder"):
                self.save_setting("projects_dir", path)
                self.close()
                self.refresh()

        self.dialog("Projects folder", ft.Column([
            text("Every .ringstudio file in this folder is listed under Projects on the left. Save as starts here.",
                 color=SUB),
            text(self.projects_dir, 13, mono=True, selectable=True)], spacing=14, tight=True),
            [button("Close", self.close), button("Choose another folder", choose, primary=True)], 560)

    # ---------- open and save ----------
    def first_example(self):
        """On a first start, the example clock is open, so there is something to look at and change."""
        found = projects.examples()
        if not found:
            return Project()
        name, path, _ = found[0]
        project = projects.open_file(path)
        self.example, self.saved = name, state_of(project)
        self.save_setting("example", name)
        return project

    def adopt(self, project, path, example=None):
        """Makes `project` the open one. Secrets come from the keychain."""
        project.secrets = self.vault.all()
        self.project, self.path, self.idx, self.example = project, path, 0, example
        self.didx = project.clocks[0].active if project.clocks else None
        self.snap, self.preview_colors, self.at, self.sent = None, None, 0, False
        if path or example:
            self.saved = state_of(project)
        self.save_setting("project_path", path or "")
        self.save_setting("example", example or "")
        if path:
            self.remember(path)
        self.refresh()

    def unsaved_then(self, then):
        """Runs `then`, asking first when there are unsaved changes."""
        if not self.dirty or not self.project.clocks:
            then()
            return
        self.confirm("Unsaved changes", f"{self.project_name} has changes that are not saved to a project "
                     "file. Continue without saving them?", "Continue", then)

    def open_listed(self, path, kind, name):
        if kind == "example":
            if self.example == name and not self.path:
                return
            self.unsaved_then(lambda: (self.adopt(projects.open_file(path), None, example=name),
                                       self.toast(f"Opened {name}. Save as keeps it as your own project.")))
            return
        if path == self.path:
            return
        self.unsaved_then(lambda: self.open_path(path))

    def open_path(self, path):
        try:
            project = projects.open_file(path)
        except projects.ProjectError as err:
            self.dialog("Cannot open this project", ft.Column(
                [text("Nothing was changed. The file was rejected because:", color=SUB)]
                + [note(p) for p in err.problems[:12]], spacing=10, tight=True), [button("OK", self.close)])
            return
        except OSError as err:
            self.toast(f"Cannot read the file: {err}")
            return
        self.adopt(project, path)
        self.toast(f"Opened {projects.name_of(path)}.")

    def new_project(self, _=None):
        def go():
            self.saved = state_of(Project())
            self.adopt(Project(), None)
        self.unsaved_then(go)

    def open_project(self, _=None):
        async def pick():
            files = await self.picker.pick_files(dialog_title="Open project", file_type=ft.FilePickerFileType.CUSTOM,
                                                 allowed_extensions=[projects.SUFFIX.lstrip(".")],
                                                 initial_directory=self.projects_dir if os.path.isdir(
                                                     self.projects_dir) else None)
            if files:
                self.open_path(files[0].path)
        self.unsaved_then(lambda: self.page.run_task(pick))

    def save_project(self, _=None):
        if not self.path:
            self.save_project_as()
            return
        try:
            projects.check(self.project)
            projects.save(self.path, self.project)
        except projects.ProjectError as err:
            self.problems_dialog("Cannot save yet", err.problems)
            return
        except OSError as err:
            self.toast(f"Cannot save: {err}")
            return
        self.saved = state_of(self.project)
        self.remember(self.path)
        self.paint_title()
        self.side.content = self.sidebar()
        self.page.update()
        self.toast(f"Saved {projects.name_of(self.path)}. The previous version is kept as a .bak file.")

    def save_project_as(self, _=None):
        async def pick():
            try:
                os.makedirs(self.projects_dir, exist_ok=True)
            except OSError:
                pass
            path = await self.picker.save_file(dialog_title="Save project", file_name=self.source_name
                                               + projects.SUFFIX, file_type=ft.FilePickerFileType.CUSTOM,
                                               allowed_extensions=[projects.SUFFIX.lstrip(".")],
                                               initial_directory=self.projects_dir)
            if path:
                self.path = path if path.endswith(projects.SUFFIX) else path + projects.SUFFIX
                self.save_setting("project_path", self.path)
                self.example = None
                self.save_setting("example", "")
                self.save_project()
        self.page.run_task(pick)

    def problems_dialog(self, title, problems):
        self.dialog(title, ft.Column([note(p) for p in problems[:12]], spacing=10, tight=True),
                    [button("OK", self.close)])

    def notes_dialog(self, _=None):
        self.dialog("Project notes", ft.Column([
            text("Notes stay in the project file. They never reach the YAML files.", color=SUB),
            attr(self.project, "note", "", width=560, multiline=True, min_lines=6, max_lines=14,
                 hint_text="What these clocks are for, where they hang, what to remember next time")],
            spacing=14, tight=True), [button("Done", self.close, primary=True)])

    def keep_secrets(self):
        """Keys that saving or flashing generated are stored in the keychain so they stay the same."""
        placeholders = {"YOUR_WIFI_NAME", "YOUR_WIFI_PASSWORD"}
        self.vault.update({k: v for k, v in self.project.secrets.items() if v not in placeholders})

    # ---------- Save YAML files ----------
    def export_dialog(self, _=None):
        try:
            projects.check(self.project, for_export=True)
        except projects.ProjectError as err:
            self.problems_dialog("Fix these first", err.problems)
            return
        files = generate.repo_files(self.project, self.source_name)
        self.keep_secrets()
        listing = ft.Column(spacing=0)
        go = button("Save", None, primary=True)

        def where(rel):
            if rel == "config/secrets.yaml":
                return "ESPHome: WiFi and keys, next to the clock files"
            if rel.startswith("config/"):
                return "ESPHome: the clock's firmware"
            if rel.endswith("ring_studio_sources.yaml"):
                return "Home Assistant package: forecast and calendar sensors your designs read"
            return "Home Assistant package: the template sensor that colours the ring"

        def current(rel):
            path = os.path.join(self.s.get("repo") or "", rel)
            if not self.s.get("repo") or not os.path.exists(path):
                return None
            with open(path, encoding="utf-8") as fh:
                return fh.read()

        def status(rel):
            old = current(rel)
            return "New" if old is None else "Unchanged" if old == files[rel] else "Changed"

        def view(rel):
            if os.path.basename(rel) == "secrets.yaml":
                body = ft.Container(text("This file holds your WiFi password and keys, so it is not shown here. "
                                         "It is written readable only by your account.", color=SUB), width=500)
                self.dialog(rel, body, [button("Close", self.close)], 560)
                return
            old = current(rel)
            if old is None or old == files[rel]:
                body = box(value=files[rel], multiline=True, read_only=True, min_lines=22, text_size=12,
                           text_style=ft.TextStyle(font_family=MONO))
            else:
                body = ft.Container(diff_view(old, files[rel]), bgcolor=SUNK, border_radius=12, padding=12)
            self.dialog(rel + ("" if old is None or old == files[rel] else " · changes"), body,
                        [button("Close", self.close)], 860)

        def fill():
            states = {rel: status(rel) for rel in files}
            listing.controls = [ft.Container(ft.Row([ft.Column([text(rel, 13, mono=True), caption(where(rel))],
                                                               spacing=2, tight=True, expand=True),
                                                     text(st, 12, ACCENT if st != "Unchanged" else FAINT),
                                                     ft.TextButton("View", on_click=lambda _, rel=rel: view(rel))],
                                                    spacing=12),
                                             padding=ft.Padding.symmetric(horizontal=16, vertical=4))
                                for rel, st in states.items()]
            todo = [rel for rel, st in states.items() if st != "Unchanged"]
            go.content = f"Save {len(todo)} files" if todo else "Save"
            return todo

        async def choose(_):
            if path := await self.picker.get_directory_path():
                self.save_setting("repo", path)
                self.close()
                self.export_dialog()

        def export(_):
            if not self.s.get("repo"):
                self.toast("Choose a folder first")
                return
            todo = fill()
            try:
                generate.write_files(self.s["repo"], {rel: files[rel] for rel in todo})
                ignored = generate.protect_secrets(self.s["repo"])
            except (OSError, ValueError) as err:
                self.toast(f"Cannot write to the folder: {err}")
                return
            self.close()
            self.toast(f"Saved {len(todo)} files" + (", and added config/secrets.yaml to .gitignore"
                                                         if ignored else ""))
            if generate.secrets_committed(self.s["repo"]):
                self.problems_dialog("secrets.yaml is already in git", [
                    "Git already tracks config/secrets.yaml, so your WiFi password and keys are in the "
                    "repo's history. Stop tracking it with: git rm --cached config/secrets.yaml, then commit. "
                    "If the repo was ever pushed, generate new keys in the flash dialog and change your WiFi "
                    "password."])

        go.on_click = export
        fill()
        self.dialog("Save YAML files", ft.Column([
            text("Writes each clock's firmware and the Home Assistant template for the design it shows, as plain "
                 "YAML to import yourself. Apply to clock does the Home Assistant part for you, so use one or the "
                 "other.", color=SUB),
            ft.Row([field("Folder", lambda: self.s.get("repo", ""), lambda v: self.save_setting("repo", v),
                          width=460, mono=True),
                    ft.Container(button("Choose", choose), padding=ft.Padding.only(top=18))], spacing=10),
            ft.Container(listing, bgcolor=SUNK, border_radius=14, padding=ft.Padding.symmetric(vertical=8)),
            ft.Column([caption("Copy the files in homeassistant/ into Home Assistant's packages folder, "
                               "config/packages. Home Assistant reads packages only with this in configuration.yaml. "
                               "Add it once, then restart. If there already is a homeassistant: section, add only "
                               "the packages line inside it."),
                       ft.Container(text(PACKAGES_LINE, 12, mono=True, selectable=True), bgcolor=SUNK,
                                     border_radius=10, padding=12)], spacing=6)], spacing=20, tight=True,
            scroll=ft.ScrollMode.AUTO), [button("Cancel", self.close), go], 720)
