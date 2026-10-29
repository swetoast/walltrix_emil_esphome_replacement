"""Checks the colours the template produces, the project files, the examples and the security rules."""

import copy
import itertools
import json
import os
import tempfile
from datetime import datetime, timedelta, timezone

import pytest
import yaml

from ring_studio import generate, sample
from ring_studio import project as P
from ring_studio.model import Clock, Design, Project, Ring
from ring_studio.render import render

HERE = os.path.dirname(__file__)
SE3 = json.load(open(os.path.join(HERE, "fixtures", "se3_forecast.json"), encoding="utf-8"))
WEATHER_REAL = json.load(open(os.path.join(HERE, "fixtures", "weather_hourly.json"), encoding="utf-8"))
WEATHER = [{"condition": c} for c in
           ["sunny", "partlycloudy", "cloudy", "rainy", "pouring", "clear-night", "fog", "snowy", "windy",
            "lightning", "hail", "exceptional", "something-new"] * 2]
CET = timezone(timedelta(hours=1))


class _Loader(yaml.SafeLoader):
    """Reads ESPHome YAML, which uses tags such as !secret."""


_Loader.add_multi_constructor("!", lambda loader, suffix, node: f"!{suffix}")


@pytest.fixture(scope="module")
def project():
    """The Home Clocks project from version 1 of the file format: two clocks, one design each."""
    return P.open_file(os.path.join(HERE, "fixtures", "home_clocks_v1.ringstudio"))


STARTER = {"price": ("price", {}), "weather": ("weather", {"ring": "dial_24h"}),
           "temperature": ("value", "sensor.outdoor_temperature"), "battery": ("value", "sensor.phone_battery_level"),
           "calendar": ("calendar", {"show": "now"}), "hands": ("clock", {}), "blank": ("blank", {})}


def starter(key):
    """A clock showing a design made by one of the setups from the made-up Home Assistant."""
    from ring_studio import setups
    kind, how = STARTER[key]
    states = sample.catalogue(datetime(2026, 10, 25, 15, 7, tzinfo=CET))
    if isinstance(how, str):
        cand = setups.Candidate(how, how)
        how = {}
    else:
        found = setups.find(kind, how, states)
        cand = found[0] if found else None
    return Clock(name="t", friendly="T", ring=setups.build(kind, how, cand, states).ring)


def clock(project, name):
    return next(c for c in project.clocks if c.name == name)


def leds(out):
    return [tuple(int(out[i + j:i + j + 2], 16) for j in (0, 2, 4)) for i in range(0, len(out), 6)]


def gradient(palette, f):
    top = len(palette) - 1
    p = max(0.0, min(1.0, f)) * top
    i = int(p)
    j = min(i + 1, top)
    b = p - i
    return [palette[i][k] + (palette[j][k] - palette[i][k]) * b for k in range(3)]


def test_home_clocks_example(project):
    assert [c.name for c in project.clocks] == ["price_clock", "weather_clock"]
    price, weather = clock(project, "price_clock"), clock(project, "weather_clock")
    assert (price.hw.pin, price.hw.method, price.hw.leds, price.hw.order) == ("GPIO12", "bit_bang", 36, "GRB")
    assert price.ring.layout == "from_now" and price.ring.attrs == ["today", "tomorrow"]
    assert (price.ring.key, price.ring.t_start, price.ring.t_end) == ("SEK_per_kWh", "time_start", "time_end")
    assert weather.ring.layout == "dial_24h" and weather.ring.colour_by == "values" and len(weather.ring.colors) == 15
    assert all(c.dimming.enabled and c.dimming.night_start == 23 for c in project.clocks)  # from version 1


@pytest.mark.parametrize("hour", [0, 2, 8, 15, 17, 23])
def test_price_timeline_colours(project, hour):
    """Worked out independently here: LED k shows the 15-minute price k slots after the one running now."""
    c = clock(project, "price_clock")
    r = c.ring
    now = datetime(2026, 10, 25, hour, 7, tzinfo=CET)
    items = SE3["today"] + SE3["tomorrow"]
    start = next(i for i, s in enumerate(items) if datetime.fromisoformat(s["time_start"]) <= now
                 < datetime.fromisoformat(s["time_end"]))
    want = []
    for k in range(36):
        if start + k >= len(items):
            colour = r.missing
        else:
            x = items[start + k]["SEK_per_kWh"] * r.scale
            colour = r.below if r.below is not None and x < r.lo else gradient(r.palette, (x - r.lo) / (r.hi - r.lo))
        d = 1.0 if k == 0 else r.dim
        want.append(tuple(int(v * d) for v in colour))
    assert leds(render(generate.jinja(c), {}, {r.entity: SE3}, now)) == want


def test_weather_dial_with_real_forecast(project):
    """Toast's real hourly forecast (UTC, starting at the next hour) on the 24-hour dial at 18:28."""
    c = copy.deepcopy(clock(project, "weather_clock"))
    r = c.ring
    now = datetime(2026, 10, 28, 18, 28, tzinfo=CET)
    out = leds(render(generate.jinja(c), {}, {r.entity: WEATHER_REAL}, now))
    by_utc = {datetime.fromisoformat(f["datetime"]): f["condition"] for f in WEATHER_REAL["forecast"]}

    def expected(hour):
        local = now.replace(minute=0) + timedelta(hours=(hour - now.hour) % 24)
        if hour == now.hour:
            local += timedelta(hours=1)  # no forecast for the current hour yet: it uses the next one
        return r.colors[by_utc[local.astimezone(timezone.utc)]]

    for k in range(36):
        hour = int(k * 24 / 36)
        d = 1.0 if hour == now.hour else r.dim
        assert out[k] == tuple(int(v * d) for v in expected(hour)), k


@pytest.mark.parametrize("layout,value,lit", [("fill", "25", 9), ("whole_ring", "25", 36), ("fill", "unavailable", 0)])
def test_value_layouts(layout, value, lit):
    c = Clock(name="t", friendly="T", ring=Ring(layout=layout, entity="sensor.x", lo=0, hi=100))
    out = render(generate.jinja(c), {"sensor.x": value}, {}, datetime.now(CET))
    leds = [out[i:i + 6] for i in range(0, 216, 6)]
    assert sum(led != "000000" for led in leds) == lit


def test_state_mode_and_markers():
    c = Clock(name="t", friendly="T", ring=Ring(layout="whole_ring", colour_by="values", entity="binary_sensor.door",
                                                colors={"on": [255, 0, 0], "off": [0, 255, 0]}))
    assert render(generate.jinja(c), {"binary_sensor.door": "on"}, {}, datetime.now(CET)) == "ff0000" * 36
    c = Clock(name="t", friendly="T", ring=Ring(layout="from_now", entity="s", attrs=["l"], key="v", marker="white",
                                                below=[0, 0, 255]))
    out = render(generate.jinja(c), {}, {"s": {"l": [{"v": -1}] * 36}}, datetime.now(CET))
    assert out[:6] == "ffffff" and out[6:12] == "00008c"


def test_generated_yaml_parses(project):
    project = copy.deepcopy(project)
    project.secrets = {"api_key": "replacethis"}
    for text in generate.repo_files(project).values():
        yaml.load(text, Loader=yaml.BaseLoader)
    assert project.secrets["api_key"] == "replacethis"  # an existing key is never silently replaced
    fresh = Project([Clock(name="t", friendly="T")])
    generate.secrets_file(fresh)
    key = fresh.secrets["api_key"]
    assert generate.valid_api_key(key)
    generate.secrets_file(fresh)
    assert fresh.secrets["api_key"] == key  # stable across exports


def test_yaml_loaded_template_renders_the_same(project):
    c = clock(project, "price_clock")
    state = yaml.safe_load(generate.template_file(c))["template"][0]["sensor"][0]["state"]
    attrs = {c.ring.entity: SE3}
    now = datetime(2026, 10, 25, 17, 7, tzinfo=CET)
    assert render(state, {}, attrs, now) == render(generate.jinja(c), {}, attrs, now)


def test_draft_round_trip_keeps_definitions(project):
    from dataclasses import asdict
    from ring_studio.model import project_from_dict
    project = copy.deepcopy(project)
    project.secrets = {"wifi_password": "hunter2"}
    restored = project_from_dict(asdict(project))
    assert restored.secrets == {} and restored.clocks == project.clocks
    assert clock(restored, "weather_clock").ring.labels["pouring"] == "Heavy rain"


def test_snapshot_matches_template_and_explains_leds(project):
    from ring_studio.render import Snapshot
    c = clock(project, "price_clock")
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
    w = copy.deepcopy(clock(project, "weather_clock"))
    w.ring.layout, w.ring.t_start = "from_now", ""  # one LED per item, the first item is now
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


@pytest.mark.parametrize("key", ["price", "weather", "temperature", "battery", "calendar", "hands", "blank"])
def test_starters_render(key):
    c = starter(key)
    out = render(generate.jinja(c), {c.ring.entity: "12"}, {}, datetime(2026, 10, 25, 15, 7, tzinfo=CET))
    assert len(out) == 216


def test_clock_status_and_versions(project):
    from ring_studio import flashing, homeassistant
    c = clock(project, "price_clock")
    states = [{"entity_id": "light.price_clock_price_ring", "state": "on", "last_changed": "x",
               "attributes": {"effect_list": ["Price Ring", "Rainbow Test"]}},
              {"entity_id": "sensor.price_clock_esphome_version", "state": "2025.12.2", "attributes": {}}]
    st = homeassistant.clock_status(c, states)
    assert st["online"] and st["light"] == "light.price_clock_price_ring" and st["version"] == "2025.12.2"
    assert not homeassistant.clock_status(clock(project, "weather_clock"), states)["found"]
    assert flashing.newer("2026.10.1", "2025.12.2") and not flashing.newer("2025.12.2", "2025.12.2 Oct 1 2025")
    assert not flashing.newer(None, "2025.12.2")


# ---------- project files, secrets and safety ----------

def test_project_file_round_trip_keeps_notes_and_no_secrets(project):
    project = copy.deepcopy(project)
    project.note = "Hallway and kitchen"
    project.clocks[0].note = "Above the coffee machine"
    project.clocks[1].ring.state_notes = {"fog": "Rare here"}
    project.secrets = {"wifi_password": "hunter2", "api_key": "x"}
    text = P.dump(project, "Home")
    assert "hunter2" not in text and "api_key" not in text
    again, name = P.load(text)
    assert name == "Home" and again.note == project.note and again.clocks[0].note == project.clocks[0].note
    assert again.clocks[1].ring.state_notes == {"fog": "Rare here"} and again.secrets == {}
    assert again.clocks == project.clocks and P.dump(again, "Home") == text


@pytest.mark.parametrize("change, problem", [
    (lambda c: setattr(c.hw, "pin", "GPIO12\nhttp_request:"), "data pin"),
    (lambda c: setattr(c.hw, "board", "esp12e\n  framework: x"), "board"),
    (lambda c: setattr(c.hw, "variant", "WS2812\nwifi:"), "LED type"),
    (lambda c: setattr(c.ring, "entity", "sensor.x\n- platform: y"), "entity"),
    (lambda c: setattr(c.ring, "key", "a b"), "data key"),
])
def test_bad_values_are_rejected(project, change, problem):
    project = copy.deepcopy(project)
    change(project.clocks[0])
    with pytest.raises(P.ProjectError) as err:
        P.load(P.dump(project, "x"))
    assert any(problem in p for p in err.value.problems)


def test_names_are_cleaned_and_numbers_clamped(project):
    project = copy.deepcopy(project)
    c = project.clocks[0]
    c.name, c.friendly, c.effect, c.hw.leds = "../../evil", 'Bad"\nname: x', "Ring\\", 500
    again, _ = P.load(P.dump(project, "x"))
    c2 = again.clocks[0]
    assert c2.name == "evil" and '"' not in c2.friendly and "\n" not in c2.friendly
    assert c2.effect == "Ring" and c2.hw.leds == 42


def test_load_rejects_non_projects_and_newer_versions():
    for text in ["!!python/object/apply:os.system ['echo hi']", "just text", "ring_studio: 99\n"]:
        with pytest.raises(P.ProjectError):
            P.load(text)


def test_save_is_atomic_and_keeps_backup(project):
    project = copy.deepcopy(project)
    with tempfile.TemporaryDirectory() as tmp:
        path = P.save(os.path.join(tmp, "Home"), project)
        assert path.endswith(".ringstudio")
        project.note = "second"
        P.save(path, project)
        assert P.open_file(path).note == "second" and P.open_file(path + ".bak").note != "second"
        assert sorted(os.listdir(tmp)) == ["Home.ringstudio", "Home.ringstudio.bak"]


def test_secrets_file_fallback_is_private():
    from ring_studio.storage import Secrets
    with tempfile.TemporaryDirectory() as tmp:
        vault = Secrets(tmp, use_keyring=False)
        vault.set("wifi_password", "hunter2")
        assert Secrets(tmp, use_keyring=False).get("wifi_password") == "hunter2"
        assert os.stat(os.path.join(tmp, "secrets.json")).st_mode & 0o077 == 0
        vault.set("wifi_password", "")
        assert vault.get("wifi_password") == ""


def test_export_is_clean_and_safe(project):
    project = copy.deepcopy(project)
    project.secrets = {"wifi_ssid": "Home", "wifi_password": 'p"w', "ap_password": "a", "api_key": "k",
                       "ota_password": "o", "ha_token": "never"}
    files = generate.repo_files(project, "Home")
    for rel, text in files.items():
        lines = text.splitlines()
        assert lines[0] == "# Made with Ring Studio from Home.ringstudio. Change it there."
        assert not any(ln.lstrip().startswith("#") for ln in lines[1:]), rel
    assert "ha_token" not in files["config/secrets.yaml"]
    assert yaml.safe_load(files["config/secrets.yaml"])["wifi_password"] == 'p"w'
    with tempfile.TemporaryDirectory() as tmp:
        with pytest.raises(ValueError):
            generate.write_files(tmp, {"../escape.yaml": "x"})
        os.mkdir(os.path.join(tmp, ".git"))
        generate.write_files(tmp, files)
        assert generate.protect_secrets(tmp) and not generate.protect_secrets(tmp)
        assert "config/secrets.yaml" in open(os.path.join(tmp, ".gitignore")).read()
        assert os.stat(os.path.join(tmp, "config", "secrets.yaml")).st_mode & 0o077 == 0


def test_example_clock_designs_preview_on_sample_data():
    from ring_studio import sample
    found = P.examples()
    assert [n for n, _, _ in found] == ["Example Clock"]
    now = datetime(2026, 10, 28, 18, 28, tzinfo=CET)
    data = sample.states(now)
    p = P.open_file(found[0][1])
    assert len(p.clocks) == 1 and len(p.clocks[0].designs) == 6 and p.clocks[0].design.name == "Electricity price"
    files = generate.repo_files(p, "Example Clock")
    assert all(yaml.load(t, Loader=_Loader) for t in files.values())
    for i, d in enumerate(p.clocks[0].designs):
        c = p.clocks[0].showing(i)
        assert d.note and (c.ring.entity in data or c.ring.layout == "hands"), d.name
        st = data.get(c.ring.entity, {})
        out = render(generate.jinja(c), {c.ring.entity: st.get("state")}, {c.ring.entity: st.get("attributes")}, now)
        assert len(out) == 216 and out != "000000" * 36, d.name


def test_hands_layout_lights_the_hands():
    c = starter("hands")
    at = datetime(2026, 10, 25, 15, 7, tzinfo=CET)
    s = render(generate.jinja(c), {}, {}, at)
    leds = [s[i:i + 6] for i in range(0, 216, 6)]
    assert leds[9] == "ffc35e"  # hour hand just past 3 o'clock, afternoon gold
    assert leds[4] == "ffe1ae"  # minute hand at 7 past, the same colour lightened
    assert leds[0] == leds[18] == leds[27] == "261d0e"  # quarter marks, dim
    assert leds[1] == "000000"  # the face
    c.hw.start_led, c.hw.clockwise = 5, False
    leds = [render(generate.jinja(c), {}, {}, at)[i:i + 6] for i in range(0, 216, 6)]
    assert leds[(5 - 9) % 36] == "ffc35e" and leds[(5 - 4) % 36] == "ffe1ae"


def test_detect_finds_the_mapping():
    from ring_studio.detect import fits, guess
    se3 = {"state": "0.43", "attributes": {**SE3, "unit_of_measurement": "SEK/kWh"}}
    fields, words = guess("from_now", se3)
    assert (fields["attrs"], fields["key"], fields["t_start"], fields["t_end"]) == \
        (["today", "tomorrow"], "SEK_per_kWh", "time_start", "time_end")
    assert fields["scale"] == 100.0 and fields["lo"] <= 0 < fields["hi"] and "today + tomorrow" in words
    weather = {"state": "sunny", "attributes": {"forecast": [
        {"datetime": "2026-10-25T15:00:00+01:00", "condition": "sunny", "temperature": 8.0}] * 3}}
    fields, _ = guess("dial_24h", weather, text=True)
    assert (fields["attrs"], fields["key"], fields["t_start"]) == (["forecast"], "condition", "datetime")
    assert guess("fill", {"state": "55", "attributes": {"unit_of_measurement": "%"}})[0]["hi"] == 100.0
    assert fits("from_now", se3) and not fits("from_now", se3, text=True) and fits("week", weather, text=True)
    assert fits("fill", {"state": "21.5"}) and fits("whole_ring", {"state": "on"}) and not fits("fill", {"state": "on"})


# ---------- security ----------

def test_token_is_never_sent_on_a_redirect():
    import http.server
    import threading
    from ring_studio import homeassistant
    seen = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            seen.append((self.server.server_port, self.headers.get("Authorization")))
            if self.server.server_port == front.server_port:
                self.send_response(302)
                self.send_header("Location", f"http://127.0.0.1:{back.server_port}/api/states")
                self.end_headers()
            else:
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"[]")

        def log_message(self, *a):
            pass

    front = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    back = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    for srv in (front, back):
        threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        with pytest.raises(RuntimeError, match="redirect"):
            homeassistant.HomeAssistant(f"http://127.0.0.1:{front.server_port}", "SECRET").states()
        assert seen == [(front.server_port, "Bearer SECRET")]  # the second server never saw anything
    finally:
        front.shutdown()
        back.shutdown()


def test_home_assistant_address_rules():
    from ring_studio import homeassistant
    for bad in ["file:///etc/passwd", "ftp://x", "homeassistant.local", "https://user:pw@ha.example.com"]:
        with pytest.raises(RuntimeError):
            homeassistant.check_url(bad)
    assert homeassistant.check_url(" https://ha.example.com:8123/ ") == "https://ha.example.com:8123"
    assert homeassistant.plain_http_warning("http://ha.example.com:8123")
    for fine in ["https://ha.example.com", "http://192.168.1.5:8123", "http://homeassistant.local:8123",
                 "http://localhost:8123", "http://homeassistant:8123"]:
        assert homeassistant.plain_http_warning(fine) is None
    with pytest.raises(RuntimeError, match="token"):
        homeassistant.HomeAssistant("https://ha.example.com", "").states()


def test_project_file_refuses_alias_bombs():
    bomb = "ring_studio: 1\na: &a [x, x, x, x, x, x, x, x, x]\nb: &b [*a, *a, *a, *a, *a, *a, *a, *a]\n"
    with pytest.raises(P.ProjectError):
        P.load(bomb)


def test_secret_values_cannot_break_out_of_secrets_yaml(project):
    project = copy.deepcopy(project)
    project.secrets = {"wifi_ssid": 'Home"\nota_password: "hijack', "wifi_password": "a\\b\t\x00c",
                       "api_key": "k", "ota_password": "real"}
    doc = yaml.safe_load(generate.secrets_file(project))
    assert doc["wifi_ssid"] == 'Home"\nota_password: "hijack' and doc["ota_password"] == "real"
    assert doc["wifi_password"] == "a\\b\t\x00c"


def test_defaults_are_random_and_private_files_stay_private(project):
    from ring_studio import flashing, storage
    a, b = copy.deepcopy(project), copy.deepcopy(project)
    a.secrets, b.secrets = {}, {}
    generate.secrets_file(a)
    generate.secrets_file(b)
    assert a.secrets["ap_password"] != b.secrets["ap_password"] and len(a.secrets["ap_password"]) >= 12
    assert os.stat(storage.HOME).st_mode & 0o077 == 0
    os.makedirs(os.path.join(flashing.BUILD, "config"), exist_ok=True)
    open(os.path.join(flashing.BUILD, "config", "secrets.yaml"), "w").close()
    flashing.forget_build_secrets()
    assert not os.path.exists(os.path.join(flashing.BUILD, "config", "secrets.yaml"))


def test_tracked_secrets_are_spotted():
    with tempfile.TemporaryDirectory() as tmp:
        os.makedirs(os.path.join(tmp, ".git"))
        assert not generate.secrets_committed(tmp)
        with open(os.path.join(tmp, ".git", "index"), "wb") as fh:
            fh.write(b"DIRC....config/secrets.yaml\x00....")
        assert generate.secrets_committed(tmp)


def test_24_hour_dial_keeps_every_hour_in_place():
    c = starter("weather")
    c.ring.colors = {f"h{h:02d}": [h * 10, 0, 0] for h in range(24)}
    c.ring.marker = "none"
    at = datetime(2026, 10, 25, 15, 7, tzinfo=CET)
    first = at.replace(minute=0)
    forecast = [{"datetime": (first + timedelta(hours=i)).isoformat(), "condition": f"h{(15 + i) % 24:02d}"}
                for i in range(30)]
    out = render(generate.jinja(c), {}, {c.ring.entity: {"forecast": forecast}}, at)
    leds = [int(out[i:i + 2], 16) for i in range(0, 216, 6)]
    assert leds == [int(k * 24 / 36) * 10 for k in range(36)]  # LED k always shows hour floor(k / 1.5)
    assert leds[0] == leds[1] == 0 and leds[2] == 10 and leds[35] == 230  # 00-01 at the top, 23-24 last
    c.ring.marker, c.ring.dim = "bright", 0.5
    out = render(generate.jinja(c), {}, {c.ring.entity: {"forecast": forecast}}, at)
    leds = [int(out[i:i + 2], 16) for i in range(0, 216, 6)]
    assert leds[23] == 150 and leds[24] == 80  # 15-16 is now and full brightness, 16-17 is dimmed
    tomorrow = render(generate.jinja(c), {}, {c.ring.entity: {"forecast": forecast[:3]}}, at)
    assert tomorrow[:6] == "000000"  # no forecast yet for 00-01 tomorrow, so that LED is dark


def test_24_hour_dial_with_utc_forecast_starting_next_hour():
    """Home Assistant's hourly forecast is in UTC and starts at the next hour: the current hour borrows it."""
    from ring_studio.render import Snapshot
    c = starter("weather")
    c.ring.marker = "none"
    at = datetime(2026, 10, 28, 18, 28, tzinfo=CET)  # 17:28 UTC
    kinds = ["cloudy", "rainy", "fog"]
    first = datetime(2026, 10, 28, 18, 0, tzinfo=timezone.utc)  # 19:00 in Sweden
    forecast = [{"datetime": (first + timedelta(hours=i)).isoformat(), "condition": kinds[i % 3]} for i in range(48)]
    out = render(generate.jinja(c), {}, {c.ring.entity: {"forecast": forecast}}, at)
    leds = [out[i:i + 6] for i in range(0, 216, 6)]
    colour = {k: "%02x%02x%02x" % tuple(c.ring.colors[k]) for k in kinds}

    def hour(h):
        return [k for k in range(36) if int(k * 24 / 36) == h]

    assert all(leds[k] == colour["cloudy"] for k in hour(18))  # now: borrows the 19:00 forecast
    assert all(leds[k] == colour["cloudy"] for k in hour(19))  # 18:00 UTC is 19-20 in Sweden
    assert all(leds[k] == colour["rainy"] for k in hour(20))
    assert all(leds[k] == colour["fog"] for k in hour(21))
    assert all(leds[k] == colour["rainy"] for k in hour(17))  # 17-18 tomorrow, 22 hours ahead
    lines = Snapshot(c, {"state": "cloudy", "attributes": {"forecast": forecast}}).details(at, at)
    assert lines[hour(20)[0]] == "20-21 Today · Rain (rainy)"
    assert lines[hour(3)[0]].startswith("03-04 Tomorrow")


@pytest.mark.parametrize("dim, top", [(0.55, 50), (1.0, 50), (-0.2, 100), (None, 100), (0.3, 100)])
def test_percent_sliders_never_go_out_of_range(dim, top):
    """Switching a clock to Hands once crashed: "Other LEDs" at 55 % went into the 0 to 50 % Quarter marks slider."""
    from ring_studio.ui.kit import percent_slider
    ring = Ring(dim=dim)
    slider = percent_slider(ring, "dim", top)
    assert 0 <= slider.value <= slider.max == top


def _solid(ring, value, attrs=None):
    c = Clock(name="t", friendly="T", ring=ring)
    out = render(generate.jinja(c), {"sensor.x": value}, attrs or {}, datetime.now(CET))
    return out[:6]


def test_steps_colour_bands():
    ring = Ring(layout="whole_ring", entity="sensor.x", lo=0, hi=100, colour_by="steps",
                steps=[[0, [0, 200, 83], "Cheap"], [50, [255, 215, 0], "Normal"], [150, [255, 0, 64], "Pricey"]])
    assert _solid(ring, "10") == "00c853"
    assert _solid(ring, "50") == "ffd700"
    assert _solid(ring, "149.9") == "ffd700"
    assert _solid(ring, "400") == "ff0040"
    ring.below = [0, 0, 255]
    assert _solid(ring, "-3") == "0000ff"


def test_gradient_stops_at_values():
    ring = Ring(layout="whole_ring", entity="sensor.x", lo=0, hi=100, palette=[[0, 0, 0], [200, 0, 0], [200, 200, 200]],
                stops_at=[0, 10, 100])
    assert _solid(ring, "5") == "640000"  # halfway between the first two stops, not a twentieth of the way
    assert _solid(ring, "55") == "c86464"
    assert _solid(ring, "1000") == "c8c8c8"
    assert _solid(ring, "-1") == "000000"


def test_value_attribute():
    ring = Ring(layout="whole_ring", entity="sensor.x", lo=0, hi=10, palette=[[0, 0, 0], [250, 0, 0]], value_attr="level")
    assert _solid(ring, "99", {"sensor.x": {"level": 5}}) == "7d0000"
    assert _solid(ring, "99", {"sensor.x": {}}) == "000000"  # missing attribute: the no-data colour


def test_new_fields_round_trip():
    ring = Ring(layout="fill", entity="sensor.x", lo=0, hi=50, colour_by="steps", value_attr="level",
                steps=[[0, [0, 200, 83], "Low"], [20, [255, 0, 64], "High"]],
                palette=[[0, 0, 0], [255, 255, 255]], stops_at=[0, 30])
    text = P.dump(Project([Clock(name="t", friendly="T", ring=ring)]))
    assert "value_attribute: level" in text and "means: Low" in text and "at: 30" in text
    back = P.load(text)[0].clocks[0].ring
    assert back.steps == ring.steps and back.stops_at == [0.0, 30.0] and back.value_attr == "level"
    assert back.colour_by == "steps"


@pytest.mark.parametrize("change", [
    {"colour_by": "rainbow"}, {"stops_at": [0]}, {"stops_at": [10, 0]},
    {"colour_by": "steps", "steps": []}, {"steps": [[5, [0, 0, 0], ""], [1, [0, 0, 0], ""]]},
    {"steps": [["x", [0, 0, 0]]]}, {"value_attr": "bad key"}])
def test_bad_new_fields(change):
    ring = Ring(layout="whole_ring", entity="sensor.x", palette=[[0, 0, 0], [1, 1, 1]])
    for k, v in change.items():
        setattr(ring, k, v)
    with pytest.raises(P.ProjectError):
        P.check(Project([Clock(name="t", friendly="T", ring=ring)]))


def test_data_tree_and_choices():
    from ring_studio import detect, sample
    now = datetime(2026, 10, 25, 15, 7, tzinfo=CET)
    price = sample.state(sample.PRICE, now)
    rows = detect.tree(price)
    names = [r["name"] for r in rows]
    assert names[:2] == ["state", "today + tomorrow"] and "SEK_per_kWh" in names and "friendly_name" not in names
    path = detect.default_path(price)
    assert path == ("list", ("today", "tomorrow"), "SEK_per_kWh")
    fields, _, values = detect.choose(price, path, Ring())
    assert fields["layout"] == "from_now" and fields["t_start"] == "time_start" and fields["scale"] == 100
    assert len(values) == 192
    weather = sample.state(sample.WEATHER, now)
    fields, _, values = detect.choose(weather, ("list", ("forecast",), "condition"), Ring())
    assert fields["layout"] == "from_now" and fields["colour_by"] == "values" and fields["t_start"] == "datetime"
    assert "sunny" in values
    fields, _, _ = detect.choose(weather, ("state",), Ring())
    assert fields["layout"] == "whole_ring" and fields["colour_by"] == "values"
    fields, _, _ = detect.choose({"state": "3", "attributes": {"level": 40}}, ("attr", "level"), Ring(layout="whole_ring"))
    assert fields == {"layout": "whole_ring", "value_attr": "level", "attrs": [], "scale": 1.0, "lo": 0.0, "hi": 40.0,
                      "colour_by": "gradient"}


def test_entity_ids_follow_home_assistant_naming():
    """The firmware reads the colours sensor and the automation sets the brightness number by entity ID, so both
    must be the IDs Home Assistant really creates, also when the display name differs from the device name."""
    from ring_studio.model import ha_slug, slug
    assert [ha_slug(t) for t in ("Price Clock", "Kök Klocka", "Øst Ærø", "Straße", "A/B (test) 2")] == \
        ["price_clock", "kok_klocka", "ost_aero", "strasse", "a_b_test_2"]
    assert slug("Kök klocka") == "kok_klocka"  # ESPHome device names are ASCII only
    c = Clock(name="kitchen_clock", friendly="Kök Klocka")
    assert c.colors_entity == "sensor.kitchen_clock_ring_colors"
    sensor = yaml.safe_load(generate.template_file(c))["template"][0]["sensor"][0]
    assert sensor["default_entity_id"] == c.colors_entity and sensor["unique_id"] == "kitchen_clock_ring_colors"


def test_home_assistant_gets_only_a_template_and_the_clock_dims_itself(project):
    files = generate.repo_files(copy.deepcopy(project))
    for rel, text in files.items():
        if rel.startswith("homeassistant/"):
            assert list(yaml.safe_load(text)) == ["template"]
    firmware = yaml.load(files["config/price_clock.yaml"], Loader=_Loader)
    sun = firmware["sensor"][0]
    assert (sun["platform"], sun["entity_id"], sun["attribute"]) == ("homeassistant", "sun.sun", "elevation")
    assert "sun" not in firmware  # Home Assistant's sun.sun, not a sun calculation of its own
    assert firmware["script"][0]["id"] == "follow_the_sun"
    assert "now.hour < 6 || now.hour >= 23" in firmware["script"][0]["then"][0]["lambda"]
    c = copy.deepcopy(clock(project, "price_clock"))
    c.dimming.enabled = False
    assert "sun.sun" not in generate.firmware_file(c)


class FakeHA:
    """Just enough of Home Assistant's helper, automation and registry API to check publish's decisions."""

    def __init__(self, admin=True):
        self.admin, self.helpers, self.entities, self.registry, self.automations = admin, {}, {}, {}, {}
        self.removed = []

    def current_user(self):
        return {"name": "Toast", "is_admin": self.admin}

    def template_helpers(self):
        return {name: entry for name, (entry, _) in self.helpers.items()}

    def states(self):
        return [{"entity_id": e, **s} for e, s in self.entities.items()]

    def state(self, entity_id):
        return {"entity_id": entity_id, **self.entities[entity_id]}

    def render(self, template):
        return render(template, {}, {}, datetime.now(CET))

    def add_template_sensor(self, name, template):
        from ring_studio.model import ha_slug
        entity = "sensor." + ha_slug(name)
        assert entity not in self.registry, "would create a _2 entity"
        self.helpers[name] = (f"entry{len(self.helpers)}", template)
        self.entities[entity] = {"state": self.render(template), "attributes": {}}

    def update_template_sensor(self, entry_id, template):
        from ring_studio.model import ha_slug
        name = next(n for n, (e, _) in self.helpers.items() if e == entry_id)
        self.helpers[name] = (entry_id, template)
        self.entities["sensor." + ha_slug(name)]["state"] = self.render(template)

    def registry_entry(self, entity_id):
        return self.registry.get(entity_id)

    def remove_registry_entry(self, entity_id):
        self.removed.append(entity_id)
        del self.registry[entity_id], self.entities[entity_id]

    def automation(self, automation_id):
        return self.automations.get(automation_id)

    def save_automation(self, automation_id, config):
        self.automations[automation_id] = config
        self.entities["automation.ring_studio_adaptive_brightness"] = {"state": "on",
                                                                       "attributes": {"id": automation_id}}

    def delete_automation(self, automation_id):
        del self.automations[automation_id]


def _raw_clock():
    return Clock(name="kitchen_clock", friendly="Kök Klocka", ring=Ring(layout="raw", raw="{{ '00ff00' * 36 }}"))


def test_apply_creates_then_updates_one_helper_per_clock():
    from ring_studio import publish
    from ring_studio.model import Design
    ha, lines = FakeHA(), []
    say = lambda ok, line: lines.append((ok, line))  # noqa: E731
    c = _raw_clock()
    assert publish.apply(ha, c, say, wait=0)
    assert ha.entities["sensor.kitchen_clock_ring_colors"]["state"] == "00ff00" * 36
    c.designs.append(Design("Red", "", Ring(layout="raw", raw="{{ 'ff0000' * 36 }}")))
    assert publish.apply(ha, c.showing(1), say, wait=0)  # switching design updates the same helper
    assert list(ha.helpers) == ["Kitchen Clock Ring Colors"] and "ff0000" in ha.helpers["Kitchen Clock Ring Colors"][1]
    assert any("Updated the helper" in line for _, line in lines)


def test_apply_never_duplicates_or_takes_over():
    from ring_studio import publish
    ha = FakeHA()
    ha.entities["sensor.kitchen_clock_ring_colors"] = {"state": "00ff00" * 36, "attributes": {}}  # a YAML file
    ha.registry["sensor.kitchen_clock_ring_colors"] = {"platform": "template", "unique_id": "kitchen_clock_ring_colors"}
    assert not publish.apply(ha, _raw_clock(), wait=0)
    assert not ha.helpers and not ha.removed
    # the YAML file was removed: only a restored leftover with Ring Studio's unique ID is cleared
    ha.entities["sensor.kitchen_clock_ring_colors"] = {"state": "unavailable", "attributes": {"restored": True}}
    ha.registry["sensor.kitchen_clock_ring_colors"]["unique_id"] = "somebody_elses"
    assert not publish.apply(ha, _raw_clock(), wait=0) and not ha.removed
    ha.registry["sensor.kitchen_clock_ring_colors"]["unique_id"] = "kitchen_clock_ring_colors"
    assert publish.apply(ha, _raw_clock(), wait=0)
    assert ha.removed == ["sensor.kitchen_clock_ring_colors"] and "Kitchen Clock Ring Colors" in ha.helpers


def test_apply_needs_an_administrator():
    from ring_studio import publish
    lines = []
    assert not publish.apply(FakeHA(admin=False), _raw_clock(), lambda ok, line: lines.append(line), wait=0)
    assert "not an administrator" in lines[0]


def test_two_clocks_with_the_same_effect_keep_their_own_status():
    from ring_studio import homeassistant
    a, b = Clock(name="kitchen_clock", friendly="Kök Klocka"), Clock(name="hall_clock", friendly="Hall Clock")
    states = [{"entity_id": "light.kok_klocka_ring", "state": "on", "last_changed": "x",
               "attributes": {"effect_list": ["Ring", "Rainbow Test"]}},
              {"entity_id": "light.hall_clock_ring", "state": "unavailable", "last_changed": "y",
               "attributes": {"effect_list": ["Ring", "Rainbow Test"]}}]
    assert homeassistant.clock_status(a, states)["online"] and not homeassistant.clock_status(b, states)["online"]
    assert homeassistant.clock_status(Clock(name="x", friendly="Renamed"), states)["found"] is False  # ambiguous
    assert homeassistant.clock_status(Clock(name="x", friendly="Renamed"), states[:1])["found"]  # the only one


# ---------- the five newer layouts ----------

NOW = datetime(2026, 10, 29, 15, 7, tzinfo=CET)


def _leds(ring, states=None, attrs=None, leds=36, start=0, clockwise=True):
    c = Clock(name="t", friendly="T", ring=ring)
    c.hw.leds, c.hw.start_led, c.hw.clockwise = leds, start, clockwise
    out = render(generate.jinja(c), states or {}, attrs or {}, NOW)
    assert len(out) == leds * 6
    return [out[i:i + 6] for i in range(0, leds * 6, 6)]


def test_compass_lights_the_direction_and_colours_it_by_the_second_value():
    ring = Ring(layout="compass", entity="weather.home", value_attr="wind_bearing", entity2="weather.home",
                value2_attr="wind_speed", colour_by="steps", dim=0.3, fallback=[100, 100, 100],
                steps=[[0, [0, 200, 83], "Calm"], [8, [255, 215, 0], "Breezy"], [14, [255, 0, 64], "Strong"]])
    leds = _leds(ring, attrs={"weather.home": {"wind_bearing": 90, "wind_speed": 10}})
    assert leds[9] == "ffd700"  # east is a quarter of the way round, breezy
    assert leds[8] == leds[10] == "4c4000"  # the neighbours glow at 30 %
    assert leds[0] == leds[18] == leds[27] == "1e1e1e"  # north, south and west marks
    assert leds[1] == "000000"
    flipped = _leds(ring, attrs={"weather.home": {"wind_bearing": 90, "wind_speed": 10}}, start=4, clockwise=False)
    assert flipped[(4 - 9) % 36] == "ffd700"  # the clock's orientation is respected
    assert _leds(ring, attrs={"weather.home": {}})[9] == "1e1e1e"  # no direction: only the east mark


def test_countdown_lights_one_led_per_minute_left():
    ring = Ring(layout="countdown", entity="sensor.next_tram", colour_by="steps",
                steps=[[0, [255, 0, 64], "Go"], [4, [255, 215, 0], "Soon"], [7, [0, 200, 83], "Plenty"]])
    leds = _leds(ring, {"sensor.next_tram": (NOW + timedelta(minutes=8, seconds=10)).isoformat()})
    assert leds[:9] == ["ff0040"] * 3 + ["ffd700"] * 3 + ["00c853"] * 3 and set(leds[9:]) == {"000000"}
    assert _leds(ring, {"sensor.next_tram": "2"})[:3] == ["ff0040", "ff0040", "000000"]  # minutes as a number
    assert set(_leds(ring, {"sensor.next_tram": (NOW - timedelta(minutes=1)).isoformat()})) == {"000000"}  # gone


def test_segments_give_each_entity_its_own_part_with_gaps():
    ring = Ring(layout="segments", colour_by="values", colors={"on": [255, 0, 64], "off": [0, 200, 83]},
                missing=[40, 40, 40], parts=[["binary_sensor.front", "", "Front door"], ["binary_sensor.back", "", ""],
                                             ["binary_sensor.window", "", ""], ["binary_sensor.garage", "", ""]])
    leds = _leds(ring, {"binary_sensor.front": "off", "binary_sensor.back": "on", "binary_sensor.window": "off",
                        "binary_sensor.garage": "unavailable"})
    assert leds[0:8] == ["00c853"] * 8 and leds[8] == "000000"  # 9 LEDs a part, the last one a gap
    assert leds[9:17] == ["ff0040"] * 8 and leds[27:35] == ["282828"] * 8  # unavailable shows the no-data colour


def test_week_dial_puts_each_day_in_its_own_section():
    days = ["sunny", "rainy", "cloudy", "sunny", "fog", "snowy", "windy"]
    forecast = [{"datetime": (NOW.replace(hour=12, minute=0) + timedelta(days=d)).isoformat(), "condition": c}
                for d, c in enumerate(days)]
    colours = {"sunny": [255, 176, 0], "rainy": [0, 100, 255], "cloudy": [128, 144, 176], "fog": [200, 192, 176],
               "snowy": [224, 240, 255], "windy": [0, 208, 144]}
    ring = Ring(layout="week", entity="sensor.daily", attrs=["forecast"], key="condition", t_start="datetime",
                colour_by="values", colors=colours, dim=0.5)
    leds = _leds(ring, attrs={"sensor.daily": {"forecast": forecast}})
    for k in range(36):
        d = int(k * 7 / 36)
        if int((k + 1) * 7 / 36) != d:
            assert leds[k] == "000000", k  # the last LED of each day is a gap
        else:
            f = 1.0 if d == 0 else 0.5  # today full, the rest dimmed
            assert leds[k] == "%02x%02x%02x" % tuple(int(v * f) for v in colours[days[d]]), k


def test_day_arc_marks_sunrise_sunset_and_now():
    ring = Ring(layout="day_arc", colour_by="values",
                colors={"day": [100, 80, 30], "night": [10, 10, 40], "sun": [255, 128, 48], "now": [255, 255, 255]})
    sun_attrs = {"sun.sun": {"next_rising": "2026-10-30T07:12:00+01:00", "next_setting": "2026-10-29T16:48:00+01:00"}}
    leds = _leds(ring, attrs=sun_attrs)
    rise, fall, here = round(7.2 / 24 * 36), round(16.8 / 24 * 36), int((15 + 7 / 60) / 24 * 36)
    assert leds[rise] == leds[fall] == "ff8030" and leds[here] == "ffffff"
    assert leds[0] == "0a0a28" and leds[(rise + fall) // 2 + 1] == "64501e"


def test_old_layout_names_still_open():
    from ring_studio.model import migrate_ring
    assert migrate_ring({"mode": "states", "dial": "24h"}) == {"layout": "dial_24h", "colour_by": "values"}
    assert migrate_ring({"mode": "gauge"}) == {"layout": "fill"}
    assert migrate_ring({"layout": "state"}) == {"layout": "whole_ring", "colour_by": "values"}
    assert migrate_ring({"layout": "compass"}) == {"layout": "compass"}


def test_snapshot_explains_the_new_layouts():
    from ring_studio.render import Snapshot
    ring = Ring(layout="compass", entity="weather.home", value_attr="wind_bearing", entity2="weather.home",
                value2_attr="wind_speed")
    c = Clock(name="t", friendly="T", ring=ring)
    snap = Snapshot(c, {"weather.home": {"state": "sunny", "attributes": {"wind_bearing": 225, "wind_speed": 6,
                                                                            "wind_speed_unit": "m/s"}}})
    lines = snap.details(NOW)
    assert lines[round(225 / 360 * 36)].startswith("SW (225°)") and lines[0] == "North"
    seg = Clock(name="t", friendly="T", ring=Ring(layout="segments", colour_by="values", parts=[
        ["binary_sensor.front", "", "Front door"], ["binary_sensor.back", "", "Back door"]]))
    lines = Snapshot(seg, {"binary_sensor.front": {"state": "off"}, "binary_sensor.back": {"state": "on"}}).details(NOW)
    assert lines[0] == "Front door · off" and lines[18] == "Back door · on" and lines[17] == "Gap"


def every_setup():
    from ring_studio import setups
    for key, s in setups.SETUPS.items():
        for combo in itertools.product(*[[o[0] for o in q.options] for q in s.questions]):
            yield key, dict(zip([q.key for q in s.questions], combo))


@pytest.mark.parametrize("key,answers", list(every_setup()))
def test_every_setup_builds_a_design_that_shows_something(key, answers):
    from ring_studio import setups
    now = datetime(2026, 10, 25, 15, 7, tzinfo=CET)
    states = sample.catalogue(now)
    found = setups.find(key, answers, states)
    d = setups.build(key, answers, found[0] if found else None, states)
    c = Clock(name="t", friendly="T", designs=[d])
    p = Project(clocks=[c])
    P.check(p)  # raises when anything is wrong
    data = {**states, **sample.fake(d.ring, now, states)}
    out = render(generate.jinja(c), {e: v["state"] for e, v in data.items()},
                 {e: v["attributes"] for e, v in data.items()}, now)
    assert len(out) == 216
    if key != "blank":
        assert out != "000000" * 36, (key, answers)
    assert setups.sentence(key, answers)
    again, _ = P.load(P.dump(p))
    assert again.clocks[0].design.ring == d.ring


def test_setups_find_their_data_and_say_what_they_need():
    from ring_studio import setups
    states = sample.catalogue(datetime(2026, 10, 25, 15, 7, tzinfo=CET))
    assert setups.status("price", states) == (True, "Found: Sample prices")
    assert setups.status("price", {})[0] is False
    assert "Nord Pool" in setups.status("price", {})[1]
    doors = setups.find("board", {"show": "doors"}, states)
    assert doors[0].label == "4 found, all picked"
    week = setups.find("weather", {"ring": "week"}, states)
    assert week[0].entity == "sensor.home_daily_forecast" and week[0].source == "weather.home"
    bins = setups.find("week", {"show": "bins"}, states)
    assert bins[0].source == "calendar.waste_collection"
    backup = {"sensor.backup_next_scheduled_automatic_backup": {"state": "2026-10-26T04:45:00+00:00",
              "attributes": {"device_class": "timestamp"}}}
    assert setups.find("countdown", {"to": "departure"}, backup) == []
    assert setups.find("countdown", {"to": "departure"}, states)[0].entity == "sensor.next_tram"
    d = setups.build("weather", {"ring": "week"}, week[0], states)
    assert d.ring.made_from == "weather.home daily" and d.ring.layout == "week"
    assert setups.made_from_entity(d.ring.made_from) == d.ring.entity


def test_packages_for_data_only_an_action_hands_out():
    from ring_studio import setups
    text = setups.package(["weather.home hourly", "calendar.home week", "weather.home hourly", ""])
    doc = yaml.safe_load(text)
    assert len(doc["template"]) == 2
    weather, cal = doc["template"]
    assert weather["action"][0]["action"] == "weather.get_forecasts"
    assert weather["sensor"][0]["default_entity_id"] == "sensor.home_hourly_forecast"
    assert {"trigger": "state", "entity_id": "weather.home"} in weather["trigger"]
    assert cal["sensor"][0]["default_entity_id"] == "sensor.home_week"
    assert "days" in cal["sensor"][0]["attributes"]
    assert setups.package([]) == ""
    p = Project(clocks=[Clock(name="t", friendly="T", designs=[
        setups.build("calendar", {"show": "hours"}, setups.Candidate("sensor.home_hours", "x", "calendar.home"), {})])])
    files = generate.repo_files(p)
    assert "sensor.home_hours" in files["homeassistant/ring_studio_sources.yaml"]
    bad = Project(clocks=[Clock(name="t", friendly="T", designs=[Design("x", "", Ring(made_from="light.x on"))])])
    with pytest.raises(P.ProjectError, match="made_from"):
        P.check(bad)
