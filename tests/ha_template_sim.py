"""Small stand-in for Home Assistant's template engine.

Implements only what the example packages use: now(), state_attr(),
states(), is_number(), as_timestamp, int with base, float with default,
and HA's habit of turning rendered variables into native types.
It is a check, not a replacement for Home Assistant itself.
"""
import ast
import datetime as dt

import jinja2
import yaml


def as_timestamp(value, default=None):
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, dt.datetime):
        return value.timestamp()
    try:
        return dt.datetime.fromisoformat(str(value)).timestamp()
    except Exception:
        if default is None:
            raise
        return default


def to_int(value, default=None, base=10):
    try:
        return int(value, base) if isinstance(value, str) else int(value)
    except Exception:
        if default is None:
            raise
        return default


def to_float(value, default=None):
    try:
        return float(value)
    except Exception:
        if default is None:
            raise
        return default


def is_number(value):
    try:
        float(value)
        return True
    except Exception:
        return False


def make_env():
    env = jinja2.Environment(undefined=jinja2.StrictUndefined)
    env.filters.update({"int": to_int, "float": to_float, "as_timestamp": as_timestamp})
    env.globals.update({"as_timestamp": as_timestamp, "int": to_int, "float": to_float,
                        "is_number": is_number})
    return env


def _native(text):
    try:
        return ast.literal_eval(text)
    except Exception:
        return text


def _render_vars(env, value, ctx):
    if isinstance(value, str):
        return _native(env.from_string(value).render(**ctx).strip())
    if isinstance(value, list):
        return [_render_vars(env, v, ctx) for v in value]
    if isinstance(value, dict):
        return {k: _render_vars(env, v, ctx) for k, v in value.items()}
    return value


def render_package(path, now, attributes=None, states=None, response=None, overrides=None):
    """Render every sensor in a package. Returns {name: (available, state)}."""
    env = make_env()
    attributes = attributes or {}
    states = states or {}
    config = yaml.safe_load(open(path, encoding="utf-8"))
    results = {}
    for block in config["template"]:
        ctx = {
            "now": lambda: now,
            "state_attr": lambda e, a: attributes.get(e, {}).get(a),
            "states": lambda e: states.get(e, "unknown"),
        }
        if response is not None:
            ctx.update(response)
        variables = dict(block.get("variables", {}))
        variables.update(overrides or {})
        ctx.update(_render_vars(env, variables, ctx))
        for sensor in block["sensor"]:
            available = env.from_string(sensor.get("availability", "true")).render(**ctx).strip()
            state = env.from_string(sensor["state"]).render(**ctx).strip()
            results[sensor["name"]] = (available == "True", state)
    return results
