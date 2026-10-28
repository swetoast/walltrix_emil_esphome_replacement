"""Proves the generic template renders exactly what the hand-written ones did, and that a repo round-trips."""

import json
import os
import tempfile
from datetime import datetime, timedelta, timezone

import pytest
import yaml

from ring_studio import generate
from ring_studio.render import render
from ring_studio.importer import read_repo
from ring_studio.model import Clock, Project, Ring

HERE = os.path.dirname(__file__)
REPO = os.path.join(HERE, "fixtures", "repo")
SE3 = json.load(open(os.path.join(HERE, "fixtures", "se3_forecast.json"), encoding="utf-8"))
WEATHER = [{"condition": c} for c in
           ["sunny", "partlycloudy", "cloudy", "rainy", "pouring", "clear-night", "fog", "snowy", "windy",
            "lightning", "hail", "exceptional", "something-new"] * 2]
CET = timezone(timedelta(hours=1))


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


def test_snapshot_matches_template_and_explains_leds(project):
    from ring_studio.render import Snapshot
    c = clock(project, "energiklockan")
    now = datetime(2026, 10, 25, 15, 7, tzinfo=CET)
    snap = Snapshot(c, {"state": "1", "attributes": {**SE3, "unit_of_measurement": "SEK/kWh"}})
    times = snap.times(now)
    assert times[0] == now and all(a < b for a, b in zip(times, times[1:])) and len(times) > 30
    later = times[8]
    want = render(generate.jinja(c), {}, {c.ring.entity: SE3}, later)
    assert "".join(x[1:] for x in snap.colors(later)) == want
    lines = snap.details(now)
    assert len(lines) == 36 and lines[0].startswith("Today 15:00") and "SEK/kWh" in lines[0]


def test_snapshot_states_use_definitions(project):
    from ring_studio.render import Snapshot
    w = clock(project, "weatherclock")
    w.ring.labels = {"sunny": "Sunny"}
    snap = Snapshot(w, {"state": "sunny", "attributes": {"forecast": WEATHER}})
    now = datetime(2026, 10, 25, 15, 7, tzinfo=CET)
    assert snap.times(now) == [now]
    assert snap.details(now)[0] == "Item 1 · Sunny (sunny)"
    assert len(snap.colors(now)) == 36


def test_sun_elevation_and_brightness():
    from ring_studio import sun
    from ring_studio.model import Dimming
    stockholm = timezone(timedelta(hours=2))
    noon = datetime(2026, 6, 21, 13, 0, tzinfo=stockholm)  # solar noon is near 13:10 local
    assert abs(sun.elevation(59.33, 18.07, noon) - 54.0) < 1.0
    assert sun.elevation(57.72, 12.94, datetime(2026, 12, 21, 0, 0, tzinfo=CET)) < -40
    d = Dimming()
    assert sun.brightness(d, datetime(2026, 1, 1, 23, 30, tzinfo=CET), 10) == 0
    assert sun.brightness(d, datetime(2026, 1, 1, 12, 0, tzinfo=CET), 30) == 90
    assert sun.brightness(d, datetime(2026, 1, 1, 12, 0, tzinfo=CET), 12) == 50
    curve = sun.day_curve(d, 57.72, 12.94, datetime(2026, 10, 28, 10, 0, tzinfo=CET))
    assert len(curve) == 48 and curve[0][1] == 0 and max(b for _, b in curve) > 40


@pytest.mark.parametrize("key", ["price", "weather", "temperature", "battery", "calendar", "blank"])
def test_starters_render(key):
    from ring_studio.model import STARTERS
    c = STARTERS[key][2]()
    out = render(generate.jinja(c), {c.ring.entity: "12"}, {}, datetime(2026, 10, 25, 15, 7, tzinfo=CET))
    assert len(out) == 216


def test_clock_status_and_versions(project):
    from ring_studio import services
    c = clock(project, "energiklockan")
    states = [{"entity_id": "light.energiklockan_price_ring", "state": "on", "last_changed": "x",
               "attributes": {"effect_list": ["Price Ring", "Rainbow Test"]}},
              {"entity_id": "sensor.energiklockan_esphome_version", "state": "2025.12.2", "attributes": {}}]
    st = services.clock_status(c, states)
    assert st["online"] and st["light"] == "light.energiklockan_price_ring" and st["version"] == "2025.12.2"
    assert not services.clock_status(clock(project, "weatherclock"), states)["found"]
    assert services.newer("2026.10.1", "2025.12.2") and not services.newer("2025.12.2", "2025.12.2 Oct 1 2025")
    assert not services.newer(None, "2025.12.2")
