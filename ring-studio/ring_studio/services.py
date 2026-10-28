"""Everything outside the app: Home Assistant over REST, ESPHome and esptool as subprocesses, settings on disk."""

import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

HOME = os.path.join(os.path.expanduser("~"), ".ring_studio")
SETTINGS = os.path.join(HOME, "settings.json")
DRAFT = os.path.join(HOME, "draft.json")


def _read(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def _write(path, data):
    os.makedirs(HOME, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
    if os.name != "nt":
        os.chmod(path, 0o600)


def load_settings():
    return _read(SETTINGS)


def save_settings(data):
    _write(SETTINGS, data)


def load_draft():
    """The work-in-progress project, or None. Real YAML is only written on export."""
    return _read(DRAFT) or None


def save_draft(data):
    _write(DRAFT, data)


def discard_draft():
    if os.path.exists(DRAFT):
        os.remove(DRAFT)


class HomeAssistant:
    def __init__(self, url, token):
        self.url, self.token = url.rstrip("/"), token

    def _call(self, method, path, body=None):
        req = urllib.request.Request(
            self.url + path, method=method, data=None if body is None else json.dumps(body).encode(),
            headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                raw = resp.read().decode()
        except urllib.error.HTTPError as err:
            raise RuntimeError(f"Home Assistant said {err.code}: {err.read().decode()[:300]}") from err
        except urllib.error.URLError as err:
            raise RuntimeError(f"Cannot reach Home Assistant: {err.reason}") from err
        try:
            return json.loads(raw)
        except ValueError:
            return raw

    def entities(self):
        """entity_id -> list attributes (names of attributes holding a list of dicts)."""
        out = {}
        for s in self._call("GET", "/api/states"):
            lists = [k for k, v in s.get("attributes", {}).items()
                     if isinstance(v, list) and v and isinstance(v[0], dict)]
            out[s["entity_id"]] = lists
        return dict(sorted(out.items()))

    def seen_states(self, entity, attrs, key):
        """Distinct values the entity reports: from its list items, its `options`, or its state."""
        s = self._call("GET", f"/api/states/{entity}")
        a = s.get("attributes", {})
        if attrs:
            values = [item.get(key) for name in attrs for item in a.get(name) or [] if isinstance(item, dict)]
        else:
            values = list(a.get("options") or []) + [s.get("state")]
        return list(dict.fromkeys(str(v) for v in values if v not in (None, "", "unknown", "unavailable")))

    def render(self, template):
        return str(self._call("POST", "/api/template", {"template": template})).strip()

    def reload(self):
        for domain in ("template", "automation"):
            self._call("POST", f"/api/services/{domain}/reload", {})


BUILD = os.path.join(HOME, "build")
TOOLS = {"esphome": "ESPHome", "esptool": "esptool"}


def tool_versions():
    """Installed version per tool, or None when missing."""
    from importlib import metadata
    out = {}
    for dist in TOOLS:
        try:
            out[dist] = metadata.version(dist)
        except metadata.PackageNotFoundError:
            out[dist] = None
    return out


def install_tools(on_line):
    """Installs or upgrades ESPHome and esptool into this Python. ESPHome fetches its own
    compiler toolchain the first time it builds."""
    return run(["pip", "install", "--upgrade", *TOOLS], on_line)


def serial_ports():
    try:
        from serial.tools import list_ports
        return [f"{p.device} · {p.description}" if p.description and p.description != "n/a" else p.device
                for p in list_ports.comports()]
    except ImportError:
        return []


def run(args, on_line, cwd=None):
    """Runs `python -m <args>` and streams output lines. Returns the exit code."""
    proc = subprocess.Popen([sys.executable, "-m", *args], cwd=cwd, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, text=True, bufsize=1,
                            encoding="utf-8", errors="replace")
    for line in proc.stdout:
        on_line(line.rstrip())
    return proc.wait()


def esptool(port, *args):
    return ["esptool", "--port", port, "--baud", "460800", *args]


BACKUP = ("read-flash", "0x0", "0x400000")
RESTORE = ("write-flash", "0x0")


def esphome(yaml_path, device):
    return ["esphome", "run", os.path.basename(yaml_path), "--device", device, "--no-logs"]
