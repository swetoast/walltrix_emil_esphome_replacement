"""Settings and the draft on disk. Neither ever holds a secret: those live in the keychain (storage.Secrets)."""

import os

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
