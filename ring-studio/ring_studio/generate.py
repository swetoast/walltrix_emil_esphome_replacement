"""Turns the model into the files the repo holds. Every file is produced here and nowhere else."""

import base64
import os
import secrets as rnd
from dataclasses import asdict

from .model import Clock, Project
from .storage import atomic_write

CFG_KEYS = ("layout", "entity", "attrs", "key", "t_start", "t_end", "value_attr", "entity2", "value2_attr", "scale",
            "lo", "hi", "palette", "below", "colors", "fallback", "missing", "marker", "dim", "colour_by", "stops_at")

# One Jinja program serves every layout. It reads its settings from the `cfg` block above it, so every setting is
# visible at the top of the exported template. `colour(v)` turns any value into a colour the same way for every
# layout: text by its own colour, numbers along the gradient or in steps.
PROGRAM = """\
{%- macro colour(v) -%}
  {%- set cn = namespace(c=none, done=false) -%}
  {%- set x = none if cfg.colour_by == 'values' or v is none else v | float(none) -%}
  {%- if v is none or (v | string) in ['unknown', 'unavailable', '', 'None'] -%}
    {%- set cn.c = cfg.missing -%}
  {%- elif cfg.colour_by == 'values' -%}
    {%- set cn.c = cfg.colors.get(v | string, cfg.fallback) -%}
  {%- elif x is none -%}
    {%- set cn.c = cfg.missing -%}
  {%- else -%}
    {%- set x = x * cfg.scale -%}
    {%- set first = cfg.steps[0][0] if cfg.colour_by == 'steps' and cfg.steps
                    else cfg.stops_at[0] if cfg.stops_at else cfg.lo -%}
    {%- if cfg.below is not none and x < first -%}
      {%- set cn.c = cfg.below -%}
    {%- elif cfg.colour_by == 'steps' and cfg.steps -%}
      {%- set cn.c = cfg.steps[0][1] -%}
      {%- for st in cfg.steps -%}
        {%- if x >= st[0] -%}
          {%- set cn.c = st[1] -%}
        {%- endif -%}
      {%- endfor -%}
    {%- else -%}
      {%- set an = namespace(at=cfg.stops_at) -%}
      {%- if not cfg.stops_at -%}
        {%- for i in range(cfg.palette | length) -%}
          {%- set an.at = an.at + [cfg.lo + (cfg.hi - cfg.lo) * i / ([cfg.palette | length - 1, 1] | max)] -%}
        {%- endfor -%}
      {%- endif -%}
      {%- set at = an.at -%}
      {%- set cn.c = cfg.palette[0] if x <= at[0] else cfg.palette[-1] -%}
      {%- for i in range(1, at | length) -%}
        {%- if not cn.done and at[i - 1] < x <= at[i] -%}
          {%- set b = (x - at[i - 1]) / ((at[i] - at[i - 1]) or 1) -%}
          {%- set cn.c = [cfg.palette[i - 1][0] + (cfg.palette[i][0] - cfg.palette[i - 1][0]) * b,
                          cfg.palette[i - 1][1] + (cfg.palette[i][1] - cfg.palette[i - 1][1]) * b,
                          cfg.palette[i - 1][2] + (cfg.palette[i][2] - cfg.palette[i - 1][2]) * b] -%}
          {%- set cn.done = true -%}
        {%- endif -%}
      {%- endfor -%}
    {%- endif -%}
  {%- endif -%}
  {{- cn.c | map('float') | map('round', 6) | join(',') -}}
{%- endmacro -%}
{%- set n = cfg.leds -%}
{%- set L = cfg.layout -%}
{%- set listy = L in ['from_now', 'dial_24h', 'week'] -%}
{%- set ns = namespace(items=[], start=-1, s='', v=none) -%}
{%- set t = now() -%}
{%- set midnight = t.replace(hour=0, minute=0, second=0, microsecond=0).timestamp() -%}
{%- if listy -%}
  {%- for a in cfg.attrs -%}
    {%- set ns.items = ns.items + (state_attr(cfg.entity, a) or []) -%}
  {%- endfor -%}
  {%- if L == 'from_now' and cfg.t_start and cfg.t_end -%}
    {%- for s in ns.items -%}
      {%- if ns.start < 0 and as_timestamp(s[cfg.t_start], 0) <= t.timestamp() < as_timestamp(s[cfg.t_end], 0) -%}
        {%- set ns.start = loop.index0 -%}
      {%- endif -%}
    {%- endfor -%}
  {%- endif -%}
{%- endif -%}
{%- set ns.start = [ns.start, 0] | max -%}
{%- set v0 = (state_attr(cfg.entity, cfg.value_attr) if cfg.value_attr else states(cfg.entity)) if cfg.entity else none -%}
{%- set v0 = none if (v0 | string) in ['unknown', 'unavailable', 'None'] else v0 -%}
{%- set c0 = colour(v0).split(',') | map('float') | list -%}
{%- if L == 'fill' -%}
  {%- set f0 = ((v0 | float(0)) * cfg.scale - cfg.lo) / ((cfg.hi - cfg.lo) or 1) -%}
  {%- set lit = (([[f0, 0] | max, 1] | min) * n) | round | int if v0 is not none else 0 -%}
{%- elif L == 'hands' -%}
  {%- set stops = cfg.palette | length -%}
  {%- set p = (t.hour * 60 + t.minute) / 1440 * stops -%}
  {%- set i = (p | int) % stops -%}
  {%- set j = (i + 1) % stops -%}
  {%- set b = p - (p | int) -%}
  {%- set day = [cfg.palette[i][0] + (cfg.palette[j][0] - cfg.palette[i][0]) * b,
                 cfg.palette[i][1] + (cfg.palette[j][1] - cfg.palette[i][1]) * b,
                 cfg.palette[i][2] + (cfg.palette[j][2] - cfg.palette[i][2]) * b] -%}
  {%- set hpos = ((((t.hour % 12) * 60 + t.minute) / 720 * n) | round | int) % n -%}
  {%- set mpos = ((t.minute / 60 * n) | round | int) % n -%}
{%- elif L == 'day_arc' -%}
  {%- set rise = ((as_timestamp(state_attr('sun.sun', 'next_rising'), 0) - midnight) % 86400) / 86400 -%}
  {%- set fall = ((as_timestamp(state_attr('sun.sun', 'next_setting'), 0) - midnight) % 86400) / 86400 -%}
  {%- set rise_led = ((rise * n) | round | int) % n -%}
  {%- set fall_led = ((fall * n) | round | int) % n -%}
  {%- set now_led = (((t.timestamp() - midnight) / 86400 * n) | int) % n -%}
{%- elif L == 'compass' -%}
  {%- set bearing = v0 | float(none) if v0 is not none else none -%}
  {%- set at = (((bearing % 360) / 360 * n) | round | int) % n if bearing is not none else -1 -%}
  {%- set v2 = (state_attr(cfg.entity2, cfg.value2_attr) if cfg.value2_attr else states(cfg.entity2))
               if cfg.entity2 else none -%}
  {%- set c2 = colour(v2).split(',') | map('float') | list if cfg.entity2 else cfg.fallback -%}
{%- elif L == 'countdown' -%}
  {%- set mins = v0 | float(none) if v0 is not none else none -%}
  {%- if mins is none and v0 is not none -%}
    {%- set ts = as_timestamp(v0, none) -%}
    {%- set mins = (ts - t.timestamp()) / 60 if ts is not none else none -%}
  {%- endif -%}
  {%- set lit = ([[mins, 0] | max, n] | min) | round(0, 'ceil') | int if mins is not none else 0 -%}
{%- elif L == 'segments' -%}
  {%- set m = cfg.parts | length -%}
  {%- set per = (n / m) | int if m else n -%}
{%- elif L == 'dial_24h' -%}
  {%- set hour0 = t.replace(minute=0, second=0, microsecond=0).timestamp() -%}
{%- endif -%}
{%- for k in range(n) -%}
  {%- set pos = ((k - cfg.start_led) if cfg.clockwise else (cfg.start_led - k)) % n -%}
  {%- set is_now = false -%}
  {%- set gap = false -%}
  {%- if L == 'hands' -%}
    {%- if pos == hpos -%}
      {%- set c = day -%}
    {%- elif pos == mpos -%}
      {%- set c = [(day[0] + 255) / 2, (day[1] + 255) / 2, (day[2] + 255) / 2] -%}
    {%- elif cfg.dim > 0 and (pos * 4) % n == 0 -%}
      {%- set c = [day[0] * cfg.dim, day[1] * cfg.dim, day[2] * cfg.dim] -%}
    {%- else -%}
      {%- set c = cfg.missing -%}
    {%- endif -%}
  {%- elif L == 'day_arc' -%}
    {%- set frac = pos / n -%}
    {%- set lit_day = (rise <= frac < fall) if rise < fall else (frac >= rise or frac < fall) -%}
    {%- if pos == now_led -%}
      {%- set c = cfg.colors.get('now', [255, 255, 255]) -%}
    {%- elif pos == rise_led or pos == fall_led -%}
      {%- set c = cfg.colors.get('sun', [255, 128, 48]) -%}
    {%- else -%}
      {%- set c = cfg.colors.get('day', [96, 72, 32]) if lit_day else cfg.colors.get('night', [16, 20, 56]) -%}
    {%- endif -%}
  {%- elif L == 'from_now' -%}
    {%- set idx = ns.start + pos -%}
    {%- set is_now = pos == 0 -%}
    {%- set c = colour(ns.items[idx].get(cfg.key) if idx < ns.items | length else none).split(',') | map('float') | list -%}
  {%- elif L == 'dial_24h' -%}
    {%- set rel = (((pos * 24 / n) | int) - t.hour) % 24 -%}
    {%- set is_now = rel == 0 -%}
    {%- set ns.v = none -%}
    {%- for want in ([rel, 1] if rel == 0 else [rel]) -%}
      {%- for s in ns.items -%}
        {%- if ns.v is none and s[cfg.t_start] is defined -%}
          {%- set ahead = as_timestamp(s[cfg.t_start], 0) - hour0 -%}
          {%- if ahead >= 0 and ((ahead / 3600) | int) == want -%}
            {%- set ns.v = s.get(cfg.key) -%}
          {%- endif -%}
        {%- endif -%}
      {%- endfor -%}
    {%- endfor -%}
    {%- set c = colour(ns.v).split(',') | map('float') | list -%}
  {%- elif L == 'week' -%}
    {%- set d = (pos * 7 / n) | int -%}
    {%- set is_now = d == 0 -%}
    {%- set gap = n >= 14 and ((pos + 1) * 7 / n) | int != d -%}
    {%- set ns.v = none -%}
    {%- for s in ns.items -%}
      {%- if ns.v is none and s[cfg.t_start] is defined
            and ((as_timestamp(s[cfg.t_start], 0) - midnight) // 86400) | int == d -%}
        {%- set ns.v = s.get(cfg.key) -%}
      {%- endif -%}
    {%- endfor -%}
    {%- set c = colour(ns.v).split(',') | map('float') | list -%}
  {%- elif L == 'fill' -%}
    {%- set c = c0 if pos < lit else cfg.missing -%}
  {%- elif L == 'whole_ring' -%}
    {%- set c = c0 -%}
  {%- elif L == 'compass' -%}
    {%- set off = (pos - at) % n -%}
    {%- if pos == at -%}
      {%- set c = c2 -%}
    {%- elif at >= 0 and off in [1, n - 1] -%}
      {%- set c = [c2[0] * 0.3, c2[1] * 0.3, c2[2] * 0.3] -%}
    {%- elif cfg.dim > 0 and (pos * 4) % n == 0 -%}
      {%- set c = [cfg.fallback[0] * cfg.dim, cfg.fallback[1] * cfg.dim, cfg.fallback[2] * cfg.dim] -%}
    {%- else -%}
      {%- set c = cfg.missing -%}
    {%- endif -%}
  {%- elif L == 'countdown' -%}
    {%- set c = colour(pos + 1).split(',') | map('float') | list if pos < lit else cfg.missing -%}
  {%- elif L == 'segments' -%}
    {%- set si = (pos / per) | int -%}
    {%- set gap = si >= m or (per >= 3 and pos % per == per - 1) -%}
    {%- if not gap -%}
      {%- set part = cfg.parts[si] -%}
      {%- set pv = state_attr(part[0], part[1]) if part[1] else states(part[0]) -%}
      {%- set c = colour(pv).split(',') | map('float') | list -%}
    {%- endif -%}
  {%- else -%}
    {%- set c = cfg.missing -%}
  {%- endif -%}
  {%- if gap -%}
    {%- set c = [0, 0, 0] -%}
  {%- elif listy and is_now and cfg.marker == 'white' -%}
    {%- set c = [255, 255, 255] -%}
  {%- endif -%}
  {%- set d = cfg.dim if listy and not is_now and cfg.marker != 'none' else 1.0 -%}
  {%- set ns.s = ns.s ~ '%02x%02x%02x' | format((c[0] * d) | int, (c[1] * d) | int, (c[2] * d) | int) -%}
{%- endfor -%}
{{ ns.s }}"""


def cfg_line(clock: Clock):
    """The template's settings, one per line, as a Jinja dict the program below reads."""
    ring = asdict(clock.ring)
    cfg = {k: ring[k] for k in CFG_KEYS}
    cfg["steps"] = [[s[0], s[1]] for s in clock.ring.steps]  # names are for people, not the template
    cfg["parts"] = [[p[0], p[1]] for p in clock.ring.parts]  # names are for people, not the template
    cfg["start_led"], cfg["clockwise"] = clock.hw.start_led, clock.hw.clockwise
    cfg["leds"] = clock.hw.leds
    body = ",\n".join(f"  {k!r}: {v!r}" for k, v in cfg.items())
    return "{%- set cfg = {\n" + body + "\n} -%}"


def header(source):
    return f"# Made with Ring Studio from {source}.ringstudio. Change it there.\n"


def jinja(clock: Clock):
    """The template body HA renders. Also what the live preview sends to HA."""
    if clock.ring.layout == "raw":
        return clock.ring.raw.strip()
    return cfg_line(clock) + "\n" + PROGRAM


def _indent(text, spaces):
    pad = " " * spaces
    return "\n".join(pad + line if line else line for line in text.splitlines())


def template_sensor(clock: Clock, indent=0):
    block = (f'- name: "{clock.friendly} Ring Colors"\n'
             f"  unique_id: {clock.name}_ring_colors\n"
             f"  default_entity_id: {clock.colors_entity}\n"
             "  state: >\n" + _indent(jinja(clock), 4))
    return _indent(block, indent)


def template_file(clock: Clock, source="Untitled"):
    return header(source) + "template:\n  - sensor:\n" + template_sensor(clock, 6) + "\n"


def sun_block(clock: Clock):
    """The clock dims itself from Home Assistant's sun.sun: its elevation attribute arrives over the API, and
    once a minute, and whenever it changes, the clock sets its own brightness. The same curve as
    sun.brightness. Without an elevation yet (just after starting), the brightness is left as it is."""
    d, hw = clock.dimming, clock.hw
    if not d.enabled:
        return "", ""
    span = (d.elev_high - d.elev_low) or 1
    sync = """    on_time_sync:
      then:
        - script.execute: follow_the_sun
"""
    block = f"""
sensor:
  - platform: homeassistant
    id: sun_elevation
    entity_id: sun.sun
    attribute: elevation
    internal: true
    on_value:
      then:
        - script.execute: follow_the_sun

script:
  - id: follow_the_sun
    mode: single
    then:
      - lambda: |-
          auto now = id(ha_time).now();
          float elevation = id(sun_elevation).state;
          if (!now.is_valid() || std::isnan(elevation))
            return;
          float level;
          if (now.hour < {d.night_end} || now.hour >= {d.night_start}) {{
            level = 0;
          }} else {{
            float f = (elevation - ({d.elev_low:g})) / {span:g};
            f = f < 0 ? 0 : (f > 1 ? 1 : f);
            level = {d.low} + {d.high - d.low} * f;
          }}
          level = roundf(level);
          if (level > {hw.max_brightness})
            level = {hw.max_brightness};
          if (id(ring_brightness).state != level) {{
            auto call = id(ring_brightness).make_call();
            call.set_value(level);
            call.perform();
          }}

interval:
  - interval: 60s
    then:
      - script.execute: follow_the_sun
"""
    return sync, block


def firmware_file(clock: Clock, source="Untitled"):
    hw, n = clock.hw, clock.hw.leds
    sync, sun = sun_block(clock)
    return header(source) + f"""substitutions:
  name: {clock.name}
  friendly_name: "{clock.friendly}"

esphome:
  name: ${{name}}
  friendly_name: ${{friendly_name}}
  on_boot:
    priority: -100
    then:
      - light.turn_on:
          id: ring
          brightness: 100%
          effect: "{clock.effect}"

esp8266:
  board: {hw.board}

logger:
  level: WARN
  baud_rate: 0

api:
  encryption:
    key: !secret api_key

ota:
  - platform: esphome
    password: !secret ota_password

wifi:
  ssid: !secret wifi_ssid
  password: !secret wifi_password
  ap:
    ssid: "{clock.friendly} Setup"
    password: !secret ap_password

captive_portal:

time:
  - platform: homeassistant
    id: ha_time
{sync}
text_sensor:
  - platform: homeassistant
    id: ring_colors
    entity_id: {clock.colors_entity}
  - platform: version
    name: "ESPHome Version"
    hide_timestamp: true

number:
  - platform: template
    name: "Ring Brightness"
    id: ring_brightness
    optimistic: true
    restore_value: true
    initial_value: {hw.start_brightness}
    min_value: 0
    max_value: {hw.max_brightness}
    step: 1
    mode: slider

light:
  - platform: neopixelbus
    id: ring
    name: "{clock.friendly} Ring"
    variant: {hw.variant}
    type: {hw.order}
    pin: {hw.pin}
    method:
      type: {hw.method}
    gamma_correct: {hw.gamma}
    num_leds: {n}
    default_transition_length: 300ms
    restore_mode: ALWAYS_ON
    effects:
      - addressable_lambda:
          name: "{clock.effect}"
          update_interval: 1s
          lambda: |-
            std::string s = id(ring_colors).state;
            if (s.length() < {n * 6})
              return;
            float scale = id(ring_brightness).state / 255.0f;
            for (int i = 0; i < {n}; i++) {{
              int r = (int) strtol(s.substr(i * 6, 2).c_str(), nullptr, 16);
              int g = (int) strtol(s.substr(i * 6 + 2, 2).c_str(), nullptr, 16);
              int b = (int) strtol(s.substr(i * 6 + 4, 2).c_str(), nullptr, 16);
              it[i] = Color((uint8_t)(r * scale), (uint8_t)(g * scale), (uint8_t)(b * scale));
            }}
      - addressable_rainbow:
          name: "Rainbow Test"
{sun}"""


def gen_secret(key):
    """From the operating system's secure random source."""
    if key == "api_key":
        return base64.b64encode(os.urandom(32)).decode()
    return rnd.token_urlsafe(12) if key == "ap_password" else rnd.token_hex(16)


def valid_api_key(value):
    try:
        return len(base64.b64decode(value, validate=True)) == 32
    except (ValueError, TypeError):
        return False


def secrets_file(project: Project, source="Untitled"):
    """Fills only keys that are absent, and keeps them in the project so they stay stable.
    An existing key is never replaced here, even if invalid: that is the Generate button's job."""
    s = project.secrets
    for k, v in (("wifi_ssid", "YOUR_WIFI_NAME"), ("wifi_password", "YOUR_WIFI_PASSWORD")):
        s.setdefault(k, v)
    # The fallback hotspot lets anyone nearby reach the clock's WiFi setup page, so it gets a random password
    # rather than a guessable default.
    for key in ("ap_password", "api_key", "ota_password"):
        if not s.get(key):
            s[key] = gen_secret(key)
    return header(source) + "".join(f'{k}: "{_quote(v)}"\n' for k, v in s.items() if k in FIRMWARE_SECRETS)


FIRMWARE_SECRETS = ("wifi_ssid", "wifi_password", "ap_password", "api_key", "ota_password")


def _quote(value):
    """Safe inside a double-quoted YAML string: no value can end the string or start a new line."""
    out = []
    for ch in str(value):
        if ch in '\\"':
            out.append("\\" + ch)
        elif ord(ch) < 32 or ord(ch) == 127:
            out.append(f"\\x{ord(ch):02x}")
        else:
            out.append(ch)
    return "".join(out)


def repo_files(project: Project, source="Untitled"):
    """Relative path -> text, in the config/ + homeassistant/ layout."""
    files = {"config/secrets.yaml": secrets_file(project, source)}
    for c in project.clocks:
        files[f"config/{c.name}.yaml"] = firmware_file(c, source)
        files[f"homeassistant/ha_{c.name}_ring.yaml"] = template_file(c, source)
    from .setups import package
    extra = package([d.ring.made_from for c in project.clocks for d in c.designs])
    if extra:
        files["homeassistant/ring_studio_sources.yaml"] = header(source) + extra
    return files


def write_files(root, files):
    """Writes each file safely. Secrets files are made readable by the current user only."""
    base = os.path.realpath(root)
    for rel, text in files.items():
        path = os.path.realpath(os.path.join(base, rel))
        if not path.startswith(base + os.sep):
            raise ValueError(f"Refusing to write outside {root}: {rel}")
        atomic_write(path, text, secret=os.path.basename(rel) == "secrets.yaml")


def secrets_committed(root):
    """True when git already tracks config/secrets.yaml, so .gitignore alone no longer protects it."""
    index = os.path.join(root, ".git", "index")
    try:
        with open(index, "rb") as fh:
            return b"config/secrets.yaml\x00" in fh.read()
    except OSError:
        return False


def protect_secrets(root):
    """In a git repo, makes sure config/secrets.yaml is ignored so it cannot be committed by accident.
    Returns True when it added the line."""
    if not os.path.isdir(os.path.join(root, ".git")):
        return False
    path = os.path.join(root, ".gitignore")
    lines = open(path, encoding="utf-8").read().splitlines() if os.path.exists(path) else []
    if any(ln.strip().lstrip("/") in ("config/secrets.yaml", "secrets.yaml", "**/secrets.yaml") for ln in lines):
        return False
    atomic_write(path, "\n".join(lines + ["config/secrets.yaml"]) + "\n")
    return True
