"""Everything outside the app: Home Assistant over REST, ESPHome and esptool as subprocesses, settings on disk."""

import glob
import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request

from .storage import HOME, read_json, write_json

SETTINGS = os.path.join(HOME, "settings.json")
DRAFT = os.path.join(HOME, "draft.json")


def load_settings():
    return read_json(SETTINGS)


def save_settings(data):
    write_json(SETTINGS, {k: v for k, v in data.items() if k != "ha_token"})


def load_draft():
    """The work in progress, or None. It never holds secrets. Real YAML is only written on export."""
    return read_json(DRAFT) or None


def save_draft(data):
    write_json(DRAFT, data)


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

    def states(self):
        return self._call("GET", "/api/states")

    def config(self):
        """Location and time zone, for the brightness curve."""
        return self._call("GET", "/api/config")

    def call(self, domain, service, data):
        self._call("POST", f"/api/services/{domain}/{service}", data)

    @staticmethod
    def entities(states):
        """entity_id -> list attributes (names of attributes holding a list of dicts)."""
        out = {}
        for s in states:
            lists = [k for k, v in s.get("attributes", {}).items()
                     if isinstance(v, list) and v and isinstance(v[0], dict)]
            out[s["entity_id"]] = lists
        return dict(sorted(out.items()))

    def state(self, entity):
        return self._call("GET", f"/api/states/{entity}")

    def show(self, entity, value):
        """Overrides an entity's state until its template next updates. Used to test colours on the clock."""
        current = self.state(entity)
        self._call("POST", f"/api/states/{entity}", {"state": value, "attributes": current.get("attributes", {})})

    def update(self, entity):
        self._call("POST", "/api/services/homeassistant/update_entity", {"entity_id": entity})

    def seen_states(self, entity, attrs, key):
        """Distinct values the entity reports: from its list items, its `options`, or its state."""
        s = self.state(entity)
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


FROZEN = getattr(sys, "frozen", False)


def python():
    """The Python that runs ESPHome and esptool. In the packed .exe that is the Python installed on the
    computer, since ESPHome is a Python program and cannot live inside the .exe."""
    if not FROZEN:
        return sys.executable
    return shutil.which("python3") or shutil.which("python") or shutil.which("py")


def tool_versions():
    """Installed version per tool, or None when missing."""
    if FROZEN:
        exe = python()
        if not exe:
            return {dist: None for dist in TOOLS}
        probe = ("import importlib.metadata as m, json\nout = {}\nfor d in %r:\n"
                 "    try: out[d] = m.version(d)\n    except Exception: out[d] = None\nprint(json.dumps(out))")
        try:
            done = subprocess.run([exe, "-c", probe % (list(TOOLS),)], capture_output=True, text=True, timeout=30,
                                  creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            return json.loads(done.stdout)
        except (OSError, ValueError, subprocess.SubprocessError):
            return {dist: None for dist in TOOLS}
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


USB_CHIPS = ("CH340", "CH341", "CP210", "USB-SERIAL", "USB2.0-SER")


def serial_ports():
    """Ports as "COM4 · description", the clock's USB chip first."""
    try:
        from serial.tools import list_ports
    except ImportError:
        return []
    ports = [f"{p.device} · {p.description}" if p.description and p.description != "n/a" else p.device
             for p in list_ports.comports()]
    return sorted(ports, key=lambda p: not any(chip in p.upper() for chip in USB_CHIPS))


def is_clock_port(port):
    return any(chip in port.upper() for chip in USB_CHIPS)


def run(args, on_line, cwd=None):
    """Runs `python -m <args>` and streams output lines. Returns the exit code."""
    exe = python()
    if not exe:
        on_line("Python was not found. Install Python 3.11 or newer from python.org, tick "
                "\"Add python.exe to PATH\", then try again.")
        return 1
    proc = subprocess.Popen([exe, "-m", *args], cwd=cwd, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, text=True, bufsize=1,
                            encoding="utf-8", errors="replace",
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    for line in proc.stdout:
        on_line(line.rstrip())
    return proc.wait()


def esptool(port, *args):
    return ["esptool", "--port", port, "--baud", "460800", *args]


BACKUP = ("read-flash", "0x0", "0x400000")
RESTORE = ("write-flash", "0x0")
VERIFY = ("verify-flash", "0x0")


def esphome(command, yaml_name, device=None):
    """`esphome compile <yaml>` or `esphome upload <yaml> --device <port or OTA>`."""
    return ["esphome", command, yaml_name] + (["--device", device] if device else [])


def clock_status(clock, states):
    """What Home Assistant knows about a clock: its ring light, whether it is online, its firmware version.

    The light is found by its effects, so it does not matter how Home Assistant named it."""
    light = next((s for s in states if s["entity_id"].startswith("light.")
                  and clock.effect in (s.get("attributes", {}).get("effect_list") or [])
                  and "Rainbow Test" in s["attributes"]["effect_list"]), None)
    version = next((s["state"] for s in states if s["entity_id"].startswith(f"sensor.{clock.name}")
                    and s["entity_id"].endswith("_esphome_version")
                    and s["state"] not in ("unknown", "unavailable")), None)
    if not light:
        return {"found": False, "online": False, "light": None, "version": version, "since": None}
    online = light["state"] not in ("unavailable", "unknown")
    return {"found": True, "online": online, "light": light["entity_id"], "version": version,
            "since": light.get("last_changed")}


def newer(installed, running):
    """True when the installed ESPHome is newer than the one the clock runs."""
    def parts(v):
        return [int(x) for x in "".join(c if c.isdigit() or c == "." else " " for c in v).split()[0].split(".")
                if x.isdigit()]
    try:
        return bool(installed and running) and parts(installed) > parts(running)
    except IndexError:
        return False


def ch340_plugged_in():
    """True when Linux sees a CH340 USB chip (vendor 1a86), whether or not it got a serial port."""
    for vendor in glob.glob("/sys/bus/usb/devices/*/idVendor"):
        try:
            with open(vendor, encoding="ascii") as fh:
                if fh.read().strip() == "1a86":
                    return True
        except OSError:
            continue
    return False


def port_problem(port, ports):
    """Plain-words help for the two common Linux USB problems, or None."""
    if not sys.platform.startswith("linux"):
        return None
    if not ports and ch340_plugged_in():
        return ("The clock's USB chip is plugged in but has no serial port. On Ubuntu the braille service brltty "
                "takes it over. Remove it with: sudo apt remove brltty, then plug the clock in again.")
    dev = port.split(" · ")[0]
    if dev.startswith("/dev/") and os.path.exists(dev) and not os.access(dev, os.R_OK | os.W_OK):
        import grp
        group = grp.getgrgid(os.stat(dev).st_gid).gr_name
        return (f"Your account may not use {dev}. Add yourself to the {group} group with: "
                f"sudo usermod -aG {group} $USER, then log out and back in.")
    return None
