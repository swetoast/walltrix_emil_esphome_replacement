"""Proves the generic template renders exactly what the hand-written ones did, and that a repo round-trips."""

import json
import os
import tempfile
from datetime import datetime, timedelta, timezone

import jinja2.sandbox
import pytest
import yaml

from ring_studio import generate
from ring_studio.importer import read_repo
from ring_studio.model import Clock, Project, Ring

HERE = os.path.dirname(__file__)
REPO = os.path.join(HERE, "fixtures", "repo")
SE3 = json.load(open(os.path.join(HERE, "fixtures", "se3_forecast.json"), encoding="utf-8"))
WEATHER = [{"condition": c} for c in
           ["sunny", "partlycloudy", "cloudy", "rainy", "pouring", "clear-night", "fog", "snowy", "windy",
            "lightning", "hail", "exceptional", "something-new"] * 2]
CET = timezone(timedelta(hours=1))


def render(jinja, states, attrs, now):
    """Renders a state template with the handful of Home Assistant helpers it uses."""
    env = jinja2.sandbox.ImmutableSandboxedEnvironment()
    env.globals.update(
        now=lambda: now,
        states=lambda e: states.get(e, "unknown"),
        state_attr=lambda e, a: attrs.get(e, {}).get(a),
        as_timestamp=lambda s: datetime.fromisoformat(s).timestamp(),
    )
    return env.from_string(jinja).render().strip()


def original_state(name):
    doc = yaml.safe_load(open(os.path.join(REPO, "homeassistant", f"ha_{name}_ring.yaml"), encoding="utf-8"))
    return doc["template"][0]["sensor"][0]["state"]


@pytest.fixture(scope="module")
def project():
    return read_repo(REPO)[0]


def clock(project, name):
    return next(c for c in project.clocks if c.name == name)


def test_import_reads_both_clocks(project):
    assert [c.name for c in project.clocks] == ["energiklockan", "weatherclock"]
    e, w = clock(project, "energiklockan"), clock(project, "weatherclock")
    assert (e.hw.pin, e.hw.method, e.hw.leds, e.hw.order, e.hw.gamma) == ("GPIO12", "bit_bang", 36, "GRB", 1.0)
    assert e.effect == "Price Ring" and w.effect == "Weather Ring"
    assert e.ring.mode == "timeline" and e.ring.attrs == ["today", "tomorrow"]
    assert (e.ring.key, e.ring.scale, e.ring.hi, e.ring.dim) == ("SEK_per_kWh", 100.0, 100.0, 0.55)
    assert (e.ring.t_start, e.ring.t_end) == ("time_start", "time_end")
    assert w.ring.mode == "states" and w.ring.entity == "sensor.weather_hourly" and w.ring.attrs == ["forecast"]
    assert len(w.ring.colors) == 15 and w.ring.fallback == [100, 100, 100] and w.ring.dim == 0.4
    d = project.dimming
    assert (d.night_start, d.night_end, d.low, d.high, d.elev_low, d.elev_high) == (23, 6, 10, 90, -6, 30)
    assert d.targets == ["energiklockan"]
    assert any("No brightness automation" in n for n in project.notes["weatherclock"])
    assert any("below the range" in n for n in project.notes["energiklockan"])


@pytest.mark.parametrize("hour", [0, 2, 8, 15, 17, 23])
def test_price_template_matches_original(project, hour):
    c = clock(project, "energiklockan")
    attrs = {c.ring.entity: SE3}
    now = datetime(2026, 10, 25, hour, 7, tzinfo=CET)
    want = render(original_state("energiklockan"), {}, attrs, now)
    got = render(generate.jinja(c), {}, attrs, now)
    assert len(got) == 216 and got == want


def test_weather_template_matches_original(project):
    c = clock(project, "weatherclock")
    attrs = {"sensor.weather_hourly": {"forecast": WEATHER}}
    now = datetime(2026, 10, 25, 12, tzinfo=CET)
    want = render(original_state("weatherclock"), {}, attrs, now)
    assert render(generate.jinja(c), {}, attrs, now) == want and len(want) == 216


@pytest.mark.parametrize("mode,value,lit", [("gauge", "25", 9), ("solid", "25", 36), ("gauge", "unavailable", 0)])
def test_value_modes(mode, value, lit):
    c = Clock(name="t", friendly="T", ring=Ring(mode=mode, entity="sensor.x", lo=0, hi=100))
    out = render(generate.jinja(c), {"sensor.x": value}, {}, datetime.now(CET))
    leds = [out[i:i + 6] for i in range(0, 216, 6)]
    assert sum(led != "000000" for led in leds) == lit


def test_state_mode_and_markers():
    c = Clock(name="t", friendly="T", ring=Ring(mode="state", entity="binary_sensor.door",
                                                colors={"on": [255, 0, 0], "off": [0, 255, 0]}))
    assert render(generate.jinja(c), {"binary_sensor.door": "on"}, {}, datetime.now(CET)) == "ff0000" * 36
    c = Clock(name="t", friendly="T", ring=Ring(mode="timeline", entity="s", attrs=["l"], key="v", marker="white",
                                                below=[0, 0, 255]))
    out = render(generate.jinja(c), {}, {"s": {"l": [{"v": -1}] * 36}}, datetime.now(CET))
    assert out[:6] == "ffffff" and out[6:12] == "00008c"


def test_round_trip(project):
    with tempfile.TemporaryDirectory() as tmp:
        generate.write_files(tmp, generate.repo_files(project))
        again = read_repo(tmp)[0]
    assert [c.ring for c in again.clocks] == [c.ring for c in project.clocks]
    assert [c.hw for c in again.clocks] == [c.hw for c in project.clocks]
    assert [c.effect for c in again.clocks] == [c.effect for c in project.clocks]
    assert again.dimming == project.dimming
    assert all("read exact" in " ".join(again.notes[c.name]) for c in again.clocks)


def test_generated_yaml_parses(project):
    project.dimming.targets = ["energiklockan", "weatherclock"]
    for text in list(generate.repo_files(project).values()) + [generate.package_file(project)]:
        yaml.load(text, Loader=yaml.BaseLoader)
    assert project.secrets["api_key"] == "replacethis"  # an existing key is never silently replaced
    fresh = Project([Clock(name="t", friendly="T")])
    generate.secrets_file(fresh)
    key = fresh.secrets["api_key"]
    assert generate.valid_api_key(key)
    generate.secrets_file(fresh)
    assert fresh.secrets["api_key"] == key  # stable across exports


def test_yaml_loaded_template_renders_the_same(project):
    c = clock(project, "energiklockan")
    state = yaml.safe_load(generate.template_file(c))["template"][0]["sensor"][0]["state"]
    attrs = {c.ring.entity: SE3}
    now = datetime(2026, 10, 25, 17, 7, tzinfo=CET)
    assert render(state, {}, attrs, now) == render(generate.jinja(c), {}, attrs, now)


def test_draft_round_trip_keeps_definitions(project):
    from dataclasses import asdict
    from ring_studio.model import project_from_dict
    w = clock(project, "weatherclock")
    w.ring.labels = {"sunny": "Sunny", "pouring": "Heavy rain"}
    assert project_from_dict(asdict(project)) == project
    with tempfile.TemporaryDirectory() as tmp:
        generate.write_files(tmp, generate.repo_files(project))
        again = read_repo(tmp)[0]
    assert clock(again, "weatherclock").ring.labels == w.ring.labels
