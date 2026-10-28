"""Reads a repo (folder or zip) in the config/ + homeassistant/ layout back into a Project.

Generated files carry a `cfg` line and are read exactly. Hand-written templates are read from
their literal `set` lines; anything unrecognised is kept verbatim as a raw clock.
"""

import ast
import glob
import os
import re
import tempfile
import zipfile

import yaml

from .model import Clock, Dimming, Hardware, Project, Ring, slug


class _Loader(yaml.SafeLoader):
    pass


_Loader.add_multi_constructor("!", lambda loader, suffix, node: f"!{suffix} {loader.construct_scalar(node)}"
                              if isinstance(node, yaml.ScalarNode) else None)


def _load(path):
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    return text, yaml.load(text, Loader=_Loader)


def _literal(text):
    try:
        return ast.literal_eval(text)
    except (ValueError, SyntaxError):
        return None


def _sets(jinja):
    """All `{% set name = <literal> %}` assignments whose value is a plain literal."""
    out = {}
    for name, value in re.findall(r"\{%-?\s*set\s+(\w+)\s*=\s*(.*?)\s*-?%\}", jinja, re.S):
        val = _literal(value)
        if val is not None:
            out.setdefault(name, val)
    return out


def _find_root(path):
    if zipfile.is_zipfile(path):
        tmp = tempfile.mkdtemp(prefix="ringstudio_")
        with zipfile.ZipFile(path) as zf:
            zf.extractall(tmp)
        path = tmp
    for cfg in glob.glob(os.path.join(path, "**", "config"), recursive=True) + [os.path.join(path, "config")]:
        if os.path.isdir(cfg):
            return os.path.dirname(cfg)
    raise FileNotFoundError("No config/ folder found")


def _firmware(path):
    _, doc = _load(path)
    lights = [l for l in doc.get("light", []) if l.get("platform") == "neopixelbus"]
    if not lights:
        return None
    light = lights[0]
    subs = doc.get("substitutions", {})
    name = str(subs.get("name") or doc["esphome"]["name"])
    pin = light.get("pin")
    method = light.get("method", "")
    number = next((n for n in doc.get("number", []) if n.get("id") == "ring_brightness"), {})
    effect = next((e["addressable_lambda"]["name"] for e in light.get("effects", [])
                   if "addressable_lambda" in e), "Ring")
    entity = next((t["entity_id"] for t in doc.get("text_sensor", []) if t.get("platform") == "homeassistant"), "")
    board = (doc.get("esp8266") or doc.get("esp32") or {}).get("board", "esp12e")
    hw = Hardware(board=board, pin=str(pin.get("number") if isinstance(pin, dict) else pin),
                  method=str(method.get("type") if isinstance(method, dict) else method or "bit_bang"),
                  variant=str(light.get("variant", "WS2812")), order=str(light.get("type", "GRB")),
                  gamma=float(light.get("gamma_correct", 2.8)), leds=int(light["num_leds"]),
                  max_brightness=int(number.get("max_value", 90)), start_brightness=int(number.get("initial_value", 40)))
    clock = Clock(name=slug(name), friendly=str(subs.get("friendly_name") or name), effect=effect, hw=hw)
    return clock, entity


def _templates(root):
    """unique_id -> state Jinja, from every template file under homeassistant/."""
    out = {}
    for path in glob.glob(os.path.join(root, "homeassistant", "*.yaml")):
        _, doc = _load(path)
        for block in (doc or {}).get("template", []) if isinstance(doc, dict) else []:
            for s in block.get("sensor", []):
                uid = s.get("unique_id") or slug(s.get("name", ""))
                out[uid] = (s.get("state", ""), os.path.relpath(path, root))
    return out


def read_ring(jinja):
    """Returns (Ring, how) where how is 'exact', 'pattern' or 'raw'."""
    m = re.search(r"\{%-?\s*set\s+cfg\s*=\s*(\{.*?\})\s*-?%\}", jinja, re.S)
    if m and (cfg := _literal(m.group(1))):
        fields = {k: v for k, v in cfg.items() if k in Ring.__dataclass_fields__}
        return Ring(**fields), "exact"
    sets = _sets(jinja)
    dim = re.search(r"if\s+k\s*==\s*0\s+else\s+([\d.]+)", jinja)
    dim = float(dim.group(1)) if dim else 1.0
    attrs = re.findall(r"state_attr\(\s*(?:\w+|'[^']+')\s*,\s*'(\w+)'\s*\)", jinja)
    lit_entity = re.search(r"state_attr\(\s*'([^']+)'", jinja)
    entity = sets.get("ent") or (lit_entity.group(1) if lit_entity else "")
    if "palette" in sets and "cap" in sets:
        val = re.search(r"\.(\w+)\s*\|\s*float\s*\)\s*\*\s*([\d.]+)", jinja)
        times = re.findall(r"as_timestamp\(\s*\w+\.(\w+)\s*\)", jinja)
        return Ring(mode="timeline", entity=entity, attrs=attrs, key=val.group(1) if val else "",
                    scale=float(val.group(2)) if val else 1.0, t_start=times[0] if times else "",
                    t_end=times[1] if len(times) > 1 else "", lo=0.0, hi=float(sets["cap"]),
                    palette=sets["palette"], dim=dim), "pattern"
    maps = [v for v in sets.values() if isinstance(v, dict) and v and all(isinstance(c, list) for c in v.values())]
    if maps and ".get(" in jinja:
        fb = re.search(r"\.get\(\s*\w+\s*,\s*(\[[^\]]*\])", jinja)
        key = re.search(r"\[k\]\.(\w+)", jinja)
        return Ring(mode="states", entity=entity, attrs=attrs, key=key.group(1) if key else "state",
                    colors=maps[0], fallback=_literal(fb.group(1)) if fb else [100, 100, 100], dim=dim), "pattern"
    return Ring(mode="raw", entity=entity, raw=jinja), "raw"


def _dimming(root, clocks):
    path = os.path.join(root, "homeassistant", "automation.yaml")
    if not os.path.exists(path):
        return Dimming(targets=[]), False
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    d = Dimming(targets=[c.name for c in clocks if c.brightness_entity in text])
    if m := re.search(r"hour\s*<\s*(\d+)\s*or\s*now\(\)\.hour\s*>=\s*(\d+)", text):
        d.night_end, d.night_start = int(m.group(1)), int(m.group(2))
    if m := re.search(r"\(elevation\s*\+\s*([-\d.]+)\)\s*/\s*([\d.]+)", text):
        d.elev_low = -float(m.group(1))
        d.elev_high = d.elev_low + float(m.group(2))
    if m := re.search(r"\(\s*(\d+)\s*\+\s*(\d+)\s*\*\s*fraction", text):
        d.low, d.high = int(m.group(1)), int(m.group(1)) + int(m.group(2))
    return d, True


def read_repo(path):
    """Returns (Project, root)."""
    root = _find_root(path)
    templates = _templates(root)
    project = Project()
    for fw in sorted(glob.glob(os.path.join(root, "config", "*.yaml"))):
        if os.path.basename(fw) == "secrets.yaml":
            continue
        found = _firmware(fw)
        if not found:
            continue
        clock, entity = found
        notes = [f"Firmware: {os.path.relpath(fw, root)}"]
        uid = entity.split(".", 1)[-1]
        if uid in templates:
            jinja, tpath = templates[uid]
            clock.ring, how = read_ring(jinja)
            notes.append(f"Template: {tpath} (read {how})")
            if how == "raw":
                notes.append("! Template not recognised; kept as is and not editable here.")
        else:
            notes.append(f"! No template produces {entity}.")
        r = clock.ring
        if r.mode == "timeline" and r.below is None and r.lo <= 0:
            notes.append("! Values below the range share the lowest colour (for example negative prices).")
        if clock.hw.leds * 6 > 255:
            notes.append("! More than 42 LEDs exceeds Home Assistant's 255 character state limit.")
        project.clocks.append(clock)
        project.notes[clock.name] = notes
    project.dimming, has_auto = _dimming(root, project.clocks)
    for c in project.clocks:
        if has_auto and c.name not in project.dimming.targets:
            project.notes[c.name].append("! No brightness automation targets this clock.")
    secrets_path = os.path.join(root, "config", "secrets.yaml")
    if os.path.exists(secrets_path):
        _, doc = _load(secrets_path)
        project.secrets = {k: str(v) for k, v in (doc or {}).items()}
    return project, root
