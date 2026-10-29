"""Home Assistant over REST and its websocket API. Every request goes only to the address the user typed: no
redirects are followed, certificates are always checked, and the token is never sent anywhere else."""

import ipaddress
import json
import urllib.error
import urllib.parse
import urllib.request

from websockets.exceptions import WebSocketException
from websockets.sync.client import connect

from .model import ha_slug


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Never follows a redirect: the token must only ever go to the address the user typed."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(req.full_url, code, f"redirect to {newurl}", headers, fp)


_OPENER = urllib.request.build_opener(_NoRedirect)
MAX_RESPONSE = 50_000_000
PROBLEMS = {401: "The token was not accepted. Make a new long-lived token and paste it again.",
            403: "The token is not allowed to do this. Use a token from an administrator account.",
            404: "Home Assistant has no such entity or page. Check the entity ID and the address."}


def check_url(url):
    """Only http and https addresses with a host. Anything else (file:, ftp:, a typo) is refused."""
    parts = urllib.parse.urlsplit(url.strip())
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise RuntimeError("The address must start with https:// or http:// followed by the host, "
                           "for example https://homeassistant.local:8123")
    if parts.username or parts.password:
        raise RuntimeError("Leave the user name and password out of the address. The token is enough.")
    return url.strip().rstrip("/")


def plain_http_warning(url):
    """A warning when the token would cross a network unencrypted, or None when that is safe enough."""
    parts = urllib.parse.urlsplit(url.strip())
    if parts.scheme != "http" or not parts.hostname:
        return None
    host = parts.hostname
    try:
        if ipaddress.ip_address(host).is_private or ipaddress.ip_address(host).is_loopback:
            return None
    except ValueError:
        if host == "localhost" or host.endswith((".local", ".lan", ".home.arpa")) or "." not in host:
            return None
    return ("This address uses http, so the token travels unencrypted over the internet. "
            "Use the https address of your Home Assistant.")


class HomeAssistant:
    def __init__(self, url, token):
        self.url, self.token = url.rstrip("/"), token

    def _call(self, method, path, body=None, missing=False):
        """One request. With `missing`, a 404 returns None instead of raising."""
        if not self.token:
            raise RuntimeError("No token yet. Paste a long-lived access token in the Home Assistant dialog.")
        req = urllib.request.Request(
            check_url(self.url) + path, method=method, data=None if body is None else json.dumps(body).encode(),
            headers={"Content-Type": "application/json"})
        req.add_unredirected_header("Authorization", f"Bearer {self.token}")
        try:
            with _OPENER.open(req, timeout=15) as resp:
                raw = resp.read(MAX_RESPONSE).decode("utf-8", "replace")
        except urllib.error.HTTPError as err:
            if missing and err.code == 404:
                return None
            if err.code == 400:  # Home Assistant says what was wrong
                try:
                    detail = json.loads(err.read(100_000).decode("utf-8", "replace")).get("message")
                except (ValueError, AttributeError, OSError):
                    detail = None
                raise RuntimeError(f"Home Assistant refused it: {detail}" if detail else
                                   "Home Assistant refused it (error 400).") from None
            if 300 <= err.code < 400:
                raise RuntimeError(f"Home Assistant answered with a redirect ({err.msg}). Use that address "
                                   "directly. The token was not sent on.") from None
            raise RuntimeError(PROBLEMS.get(err.code, f"Home Assistant answered with error {err.code}.")) from None
        except urllib.error.URLError as err:
            raise RuntimeError(f"Cannot reach Home Assistant at {self.url}: {err.reason}") from None
        except (TimeoutError, OSError) as err:
            raise RuntimeError(f"Cannot reach Home Assistant at {self.url}: {err}") from None
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

    # Sending to Home Assistant: the same API the Helpers page and the automation editor use.
    def template_helpers(self):
        """Template helpers by title -> entry_id."""
        entries = self._call("GET", "/api/config/config_entries/entry?domain=template") or []
        return {e["title"]: e["entry_id"] for e in entries if isinstance(e, dict) and "title" in e}

    def add_template_sensor(self, name, template):
        flow = self._call("POST", "/api/config/config_entries/flow",
                          {"handler": "template", "show_advanced_options": False})
        step = self._call("POST", f"/api/config/config_entries/flow/{flow['flow_id']}", {"next_step_id": "sensor"})
        done = self._call("POST", f"/api/config/config_entries/flow/{step['flow_id']}",
                          {"name": name, "state": template})
        _flow_done(done)

    def update_template_sensor(self, entry_id, template):
        step = self._call("POST", "/api/config/config_entries/options/flow", {"handler": entry_id})
        if step.get("type") == "form" and step.get("step_id") not in (None, "sensor"):
            raise RuntimeError(f"The helper is not a template sensor ({step.get('step_id')}).")
        _flow_done(self._call("POST", f"/api/config/config_entries/options/flow/{step['flow_id']}",
                              {"state": template}))

    def automation(self, automation_id):
        """The automation as saved by the automation editor, or None when it is not in automations.yaml."""
        return self._call("GET", f"/api/config/automation/config/{automation_id}", missing=True)

    def save_automation(self, automation_id, config):
        self._call("POST", f"/api/config/automation/config/{automation_id}", config)

    def delete_automation(self, automation_id):
        self._call("DELETE", f"/api/config/automation/config/{automation_id}")

    def websocket(self, commands):
        """Runs commands over Home Assistant's websocket API and returns their results. Used only for the entity
        registry, which has no REST API. Certificates are checked as for every other request."""
        url = check_url(self.url)
        url = ("wss" if url.startswith("https") else "ws") + url[url.index(":"):] + "/api/websocket"
        try:
            with connect(url, open_timeout=15, close_timeout=5, max_size=MAX_RESPONSE) as ws:
                json.loads(ws.recv(15))
                ws.send(json.dumps({"type": "auth", "access_token": self.token}))
                if json.loads(ws.recv(15)).get("type") != "auth_ok":
                    raise RuntimeError(PROBLEMS[401])
                out = []
                for i, cmd in enumerate(commands, 1):
                    ws.send(json.dumps({"id": i, **cmd}))
                    while True:
                        msg = json.loads(ws.recv(30))
                        if msg.get("id") == i and msg.get("type") == "result":
                            break
                    if not msg.get("success"):
                        raise RuntimeError(f"Home Assistant refused it: {(msg.get('error') or {}).get('message')}")
                    out.append(msg.get("result"))
                return out
        except (OSError, TimeoutError, WebSocketException, ValueError) as err:
            raise RuntimeError(f"Cannot reach Home Assistant at {self.url}: {err}") from None

    def current_user(self):
        """{"name", "is_admin", ...} for the user the token belongs to."""
        return self.websocket([{"type": "auth/current_user"}])[0] or {}

    def registry_entry(self, entity_id):
        try:
            return self.websocket([{"type": "config/entity_registry/get", "entity_id": entity_id}])[0]
        except RuntimeError as err:
            if "not found" in str(err).lower():
                return None
            raise

    def remove_registry_entry(self, entity_id):
        self.websocket([{"type": "config/entity_registry/remove", "entity_id": entity_id}])

    def remove_helper(self, entry_id):
        """Deletes a helper Ring Studio made, by its config entry."""
        self._call("DELETE", f"/api/config/config_entries/entry/{entry_id}")


def _flow_done(result):
    if not isinstance(result, dict) or result.get("type") != "create_entry":
        errors = (result or {}).get("errors") if isinstance(result, dict) else None
        raise RuntimeError("Home Assistant did not accept the template" + (f": {errors}" if errors else "."))


def clock_status(clock, states):
    """What Home Assistant knows about a clock: its ring light, whether it is online, its firmware version.

    The light is the one with Ring Studio's effects whose entity ID starts with the clock's display name, the way
    Home Assistant names ESPHome entities, or with a name the clock had before (Home Assistant keeps entity IDs
    when a device is renamed). Otherwise a light with the clock's effect is used, but only when
    exactly one has it, so one clock never reports another one's state."""
    ours = [s for s in states if s["entity_id"].startswith("light.")
            and clock.effect in (s.get("attributes", {}).get("effect_list") or [])
            and "Rainbow Test" in s["attributes"]["effect_list"]]
    names = [ha_slug(clock.friendly), clock.name] + list(reversed(clock.previous_names))
    named = [s for n in names for s in ours if s["entity_id"].startswith(f"light.{n}_")]
    light = named[0] if named else ours[0] if len(ours) == 1 else None
    version = next((s["state"] for n in names for s in states if s["entity_id"].startswith(f"sensor.{n}_")
                    and s["entity_id"].endswith("_esphome_version")
                    and s["state"] not in ("unknown", "unavailable")), None)
    if not light:
        return {"found": False, "online": False, "light": None, "version": version, "since": None}
    online = light["state"] not in ("unavailable", "unknown")
    return {"found": True, "online": online, "light": light["entity_id"], "version": version,
            "since": light.get("last_changed")}
