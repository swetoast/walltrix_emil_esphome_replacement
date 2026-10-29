"""Flashing: ESPHome and esptool as subprocesses, serial ports, and the build folder."""

import glob
import json
import os
import shutil
import subprocess
import sys

from .storage import HOME

BUILD = os.path.join(HOME, "build")
TOOLS = {"esphome": "ESPHome", "esptool": "esptool"}


FROZEN = getattr(sys, "frozen", False)


TOOLS_VENV = os.path.join(HOME, "tools")


def base_python():
    """The Python installed on the computer."""
    return shutil.which("python3") or shutil.which("python") or shutil.which("py")


def venv_python():
    exe = os.path.join(TOOLS_VENV, "Scripts", "python.exe") if os.name == "nt" else \
        os.path.join(TOOLS_VENV, "bin", "python")
    return exe if os.path.exists(exe) else None


def python():
    """The Python that runs ESPHome and esptool. From source that is the Python running the app. In the
    packed app, ESPHome cannot live inside it, so it gets its own private environment in the app folder.
    That also works on Arch, Debian and Ubuntu, where pip may not install into the system Python."""
    return sys.executable if not FROZEN else venv_python()


def tool_versions():
    """Installed version per tool, or None when missing."""
    if FROZEN:
        exe = venv_python()
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
    """Installs or upgrades ESPHome and esptool. ESPHome fetches its own compiler toolchain the first time
    it builds. In the packed app this first creates the private environment from the system Python."""
    if FROZEN and not venv_python():
        base = base_python()
        if not base:
            on_line(PYTHON_MISSING)
            return 1
        on_line(f"Creating a private Python environment in {TOOLS_VENV}")
        done = subprocess.run([base, "-m", "venv", TOOLS_VENV], capture_output=True, text=True,
                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        for line in (done.stdout + done.stderr).splitlines():
            on_line(line)
        if done.returncode:
            on_line("On Debian and Ubuntu, install venv support with: sudo apt install python3-venv")
            return done.returncode
    return run(["pip", "install", "--upgrade", *TOOLS], on_line)


PYTHON_MISSING = ("Python was not found. Install Python 3.11 or newer: on Windows from python.org with "
                  "\"Add python.exe to PATH\" ticked, on Arch with: sudo pacman -S python, "
                  "on Debian or Ubuntu with: sudo apt install python3 python3-venv. Then try again.")


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
        on_line(PYTHON_MISSING if not base_python() else "ESPHome is not installed yet. Press Flash over USB "
                "or Back up stock and it installs first.")
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


def forget_build_secrets():
    """The flash build needs secrets.yaml while ESPHome runs. Afterwards it is deleted, so the only copies of
    your passwords are the keychain and the repo you exported to."""
    path = os.path.join(BUILD, "config", "secrets.yaml")
    if os.path.exists(path):
        os.remove(path)
