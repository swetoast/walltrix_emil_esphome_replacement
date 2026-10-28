"""Where the app keeps things on disk, how it writes them safely, and where secrets live.

Secrets (WiFi, API and OTA keys, the Home Assistant token) never go in project files or the draft.
They go in the system keychain: Windows Credential Manager, macOS Keychain, or GNOME Keyring /
KWallet on Linux. Without a keychain they go in a file only the current user can read.
"""

import json
import os
import sys
import tempfile

APP = "Ring Studio"
SECRET_KEYS = ("wifi_ssid", "wifi_password", "ap_password", "api_key", "ota_password", "ha_token")


def app_dir():
    """Per-OS folder for settings, the draft, backups and builds."""
    home = os.path.expanduser("~")
    if sys.platform == "darwin":
        return os.path.join(home, "Library", "Application Support", APP)
    if os.name == "nt":
        return os.path.join(home, ".ring_studio")
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(home, ".config")
    path = os.path.join(base, "ring-studio")
    old = os.path.join(home, ".ring_studio")
    if os.path.isdir(old) and not os.path.exists(path):
        os.makedirs(base, exist_ok=True)
        os.replace(old, path)
    return path


HOME = app_dir()


def private(path):
    """Readable by the current user only. Windows profile folders already are."""
    if os.name != "nt":
        os.chmod(path, 0o600)


def atomic_write(path, text, backup=False, secret=False):
    """Writes to a temporary file next to `path`, then swaps it in. A crash or full disk never leaves a
    half-written file. With `backup`, the previous version is kept as `<path>.bak`."""
    folder = os.path.dirname(os.path.abspath(path))
    os.makedirs(folder, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".tmp_", dir=folder)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        if secret:
            private(tmp)
        if backup and os.path.exists(path):
            os.replace(path, path + ".bak")
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def read_json(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def write_json(path, data, secret=True):
    atomic_write(path, json.dumps(data, indent=2), secret=secret)


class Secrets:
    """Secrets in the system keychain, or in a private file when there is none."""

    def __init__(self, folder=HOME, use_keyring=True):
        self.file = os.path.join(folder, "secrets.json")
        self.ring = _keyring() if use_keyring else None

    @property
    def where(self):
        if self.ring:
            return _KEYRING_NAMES.get(type(self.ring).__name__, f"the system keychain ({type(self.ring).__name__})")
        return f"a file only your account can read: {self.file}"

    def get(self, key, default=""):
        if self.ring:
            try:
                value = self.ring.get_password(APP, key)
                return default if value is None else value
            except Exception:  # noqa: BLE001  keyring backends raise their own error types
                pass
        return read_json(self.file).get(key, default)

    def set(self, key, value):
        if self.ring:
            try:
                if value:
                    self.ring.set_password(APP, key, value)
                else:
                    self._forget(key)
                return
            except Exception:  # noqa: BLE001
                self.ring = None
        data = read_json(self.file)
        if value:
            data[key] = value
        else:
            data.pop(key, None)
        write_json(self.file, data)

    def _forget(self, key):
        try:
            self.ring.delete_password(APP, key)
        except Exception:  # noqa: BLE001  deleting a missing entry raises
            pass

    def all(self):
        return {k: v for k in SECRET_KEYS if (v := self.get(k))}

    def update(self, values):
        for k in SECRET_KEYS:
            if k in values:
                self.set(k, values[k])


_KEYRING_NAMES = {"WinVaultKeyring": "Windows Credential Manager", "Keyring": "the macOS Keychain",
                  "SecretServiceKeyring": "GNOME Keyring or KWallet (Secret Service)",
                  "DBusKeyring": "KWallet"}


def _keyring():
    """The system keychain, or None when there is no usable one (headless Linux, minimal desktops)."""
    try:
        import keyring
        from keyring.backends import fail
        ring = keyring.get_keyring()
        if isinstance(ring, fail.Keyring) or getattr(ring, "priority", 0) < 1:
            return None
        if type(ring).__name__ == "ChainerBackend":
            usable = [b for b in ring.backends if getattr(b, "priority", 0) >= 1]
            return usable[0] if usable else None
        return ring
    except Exception:  # noqa: BLE001  import errors and backend probing errors alike
        return None
