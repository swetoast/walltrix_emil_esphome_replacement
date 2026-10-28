"""Turns the model into the files the repo holds. Every file is produced here and nowhere else."""

import base64
import os
import secrets as rnd
from dataclasses import asdict

from .model import Clock, Dimming, Project
from .storage import atomic_write

CFG_KEYS = ("mode", "entity", "attrs", "key", "t_start", "t_end", "scale", "lo", "hi", "palette",
            "below", "colors", "labels", "fallback", "missing", "marker", "dim")

# One Jinja program serves every mode. It reads its settings from the `cfg` block above it,
# which is also what the importer reads back, so a generated file round-trips exactly.
PROGRAM = """\
{%- set n = cfg.leds -%}
{%- set list_mode = cfg.mode in ['timeline', 'states'] -%}
{%- set ns = namespace(items=[], start=-1, s='') -%}
{%- if list_mode -%}
  {%- for a in cfg.attrs -%}
    {%- set ns.items = ns.items + (state_attr(cfg.entity, a) or []) -%}
  {%- endfor -%}
  {%- if cfg.t_start -%}
    {%- set t = now().timestamp() -%}
    {%- for s in ns.items -%}
      {%- if ns.start < 0 and as_timestamp(s[cfg.t_start]) <= t < as_timestamp(s[cfg.t_end]) -%}
        {%- set ns.start = loop.index0 -%}
      {%- endif -%}
    {%- endfor -%}
  {%- endif -%}
{%- endif -%}
{%- set ns.start = [ns.start, 0] | max -%}
{%- set v0 = states(cfg.entity) -%}
{%- set f0 = ((v0 | float(0)) * cfg.scale - cfg.lo) / (cfg.hi - cfg.lo) -%}
{%- set lit = (([[f0, 0] | max, 1] | min) * n) | round | int -%}
{%- for k in range(n) -%}
  {%- set idx = ns.start + k -%}
  {%- if list_mode -%}
    {%- set v = ns.items[idx][cfg.key] if idx < ns.items | length else none -%}
  {%- elif cfg.mode == 'gauge' and k >= lit -%}
    {%- set v = none -%}
  {%- elif v0 in ['unknown', 'unavailable'] -%}
    {%- set v = none -%}
  {%- else -%}
    {%- set v = v0 -%}
  {%- endif -%}
  {%- if v is none -%}
    {%- set c = cfg.missing -%}
  {%- elif cfg.mode in ['states', 'state'] -%}
    {%- set c = cfg.colors.get(v | string, cfg.fallback) -%}
  {%- else -%}
    {%- set x = (v | float(0)) * cfg.scale -%}
    {%- if cfg.below is not none and x < cfg.lo -%}
      {%- set c = cfg.below -%}
    {%- else -%}
      {%- set top = cfg.palette | length - 1 -%}
      {%- set p = ([[(x - cfg.lo) / (cfg.hi - cfg.lo), 0] | max, 1] | min) * top -%}
      {%- set i = p | int -%}
      {%- set j = [i + 1, top] | min -%}
      {%- set b = p - i -%}
      {%- set c = [cfg.palette[i][0] + (cfg.palette[j][0] - cfg.palette[i][0]) * b,
                   cfg.palette[i][1] + (cfg.palette[j][1] - cfg.palette[i][1]) * b,
                   cfg.palette[i][2] + (cfg.palette[j][2] - cfg.palette[i][2]) * b] -%}
    {%- endif -%}
  {%- endif -%}
  {%- if list_mode and k == 0 and cfg.marker == 'white' -%}
    {%- set c = [255, 255, 255] -%}
  {%- endif -%}
  {%- set d = cfg.dim if list_mode and k > 0 and cfg.marker != 'none' else 1.0 -%}
  {%- set ns.s = ns.s ~ '%02x%02x%02x' | format((c[0] * d) | int, (c[1] * d) | int, (c[2] * d) | int) -%}
{%- endfor -%}
{{ ns.s }}"""


def cfg_line(clock: Clock):
    """The template's settings, one per line, as a Jinja dict the program below reads."""
    ring = asdict(clock.ring)
    cfg = {k: ring[k] for k in CFG_KEYS}
    cfg["leds"] = clock.hw.leds
    body = ",\n".join(f"  {k!r}: {v!r}" for k, v in cfg.items())
    return "{%- set cfg = {\n" + body + "\n} -%}"


def header(source):
    return f"# Made with Ring Studio from {source}.ringstudio. Change it there.\n"


def jinja(clock: Clock):
    """The template body HA renders. Also what the live preview sends to HA."""
    if clock.ring.mode == "raw":
        return clock.ring.raw.strip()
    return cfg_line(clock) + "\n" + PROGRAM


def _indent(text, spaces):
    pad = " " * spaces
    return "\n".join(pad + line if line else line for line in text.splitlines())


def template_sensor(clock: Clock, indent=0):
    block = (f'- name: "{clock.friendly} Ring Colors"\n'
             f"  unique_id: {clock.name}_ring_colors\n"
             "  state: >\n" + _indent(jinja(clock), 4))
    return _indent(block, indent)


def template_file(clock: Clock, source="Untitled"):
    return header(source) + "template:\n  - sensor:\n" + template_sensor(clock, 6) + "\n"


def firmware_file(clock: Clock, source="Untitled"):
    hw, n = clock.hw, clock.hw.leds
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
"""


def automation_body(project: Project):
    d: Dimming = project.dimming
    targets = [c.brightness_entity for c in project.clocks if c.name in d.targets]
    if not d.enabled or not targets:
        return None
    ids = "\n".join(f"  - {t}" for t in targets)
    triggers = "".join(f"  - trigger: state\n    entity_id: {t}\n    from: \"unavailable\"\n" for t in targets)
    span = d.elev_high - d.elev_low
    return f"""alias: Ring Studio adaptive brightness
description: Adjust ring brightness with daylight and keep it dark overnight.
triggers:
  - trigger: time_pattern
    minutes: "/1"
  - trigger: homeassistant
    event: start
{triggers}
actions:
  - choose:
      - conditions:
          - condition: template
            value_template: "{{{{ now().hour < {d.night_end} or now().hour >= {d.night_start} }}}}"
        sequence:
          - action: number.set_value
            continue_on_error: true
            target:
              entity_id:
{_indent(ids, 14)}
            data:
              value: 0
    default:
      - condition: template
        value_template: "{{{{ is_number(state_attr('sun.sun', 'elevation')) }}}}"
      - action: number.set_value
        continue_on_error: true
        target:
          entity_id:
{_indent(ids, 10)}
        data:
          value: >
            {{% set elevation = state_attr('sun.sun', 'elevation') | float %}}
            {{% set fraction = [[(elevation + {-d.elev_low:g}) / {span:g}, 0] | max, 1] | min %}}
            {{{{ ({d.low} + {d.high - d.low} * fraction) | round(0) | int }}}}

mode: restart
"""


def gen_secret(key):
    if key == "api_key":
        return base64.b64encode(os.urandom(32)).decode()
    return rnd.token_hex(16)


def valid_api_key(value):
    try:
        return len(base64.b64decode(value, validate=True)) == 32
    except (ValueError, TypeError):
        return False


def secrets_file(project: Project, source="Untitled"):
    """Fills only keys that are absent, and keeps them in the project so they stay stable.
    An existing key is never replaced here, even if invalid: that is the Generate button's job."""
    s = project.secrets
    for k, v in (("wifi_ssid", "YOUR_WIFI_NAME"), ("wifi_password", "YOUR_WIFI_PASSWORD"), ("ap_password", "ringstudio")):
        s.setdefault(k, v)
    for key in ("api_key", "ota_password"):
        if not s.get(key):
            s[key] = gen_secret(key)
    return header(source) + "".join(f'{k}: "{_quote(v)}"\n' for k, v in s.items() if k in FIRMWARE_SECRETS)


FIRMWARE_SECRETS = ("wifi_ssid", "wifi_password", "ap_password", "api_key", "ota_password")


def _quote(value):
    return str(value).replace("\\", "\\\\").replace('"', '\\"')


def repo_files(project: Project, source="Untitled"):
    """Relative path -> text, in the config/ + homeassistant/ layout."""
    files = {"config/secrets.yaml": secrets_file(project, source)}
    for c in project.clocks:
        files[f"config/{c.name}.yaml"] = firmware_file(c, source)
        files[f"homeassistant/ha_{c.name}_ring.yaml"] = template_file(c, source)
    auto = automation_body(project)
    if auto:
        files["homeassistant/automation.yaml"] = header(source) + auto
    return files


def package_file(project: Project, source="Untitled"):
    """Everything Home Assistant needs, as one package for config/packages/."""
    out = [header(source), "template:\n  - sensor:\n"]
    out += [template_sensor(c, 6) + "\n" for c in project.clocks]
    auto = automation_body(project)
    if auto:
        lines = auto.rstrip("\n").splitlines()
        item = ["  - " + lines[0]] + [("    " + ln) if ln else ln for ln in lines[1:]]
        out.append("\nautomation:\n" + "\n".join(item) + "\n")
    return "".join(out)


def write_files(root, files):
    """Writes each file safely. Secrets files are made readable by the current user only."""
    base = os.path.realpath(root)
    for rel, text in files.items():
        path = os.path.realpath(os.path.join(base, rel))
        if not path.startswith(base + os.sep):
            raise ValueError(f"Refusing to write outside {root}: {rel}")
        atomic_write(path, text, secret=os.path.basename(rel) == "secrets.yaml")


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
