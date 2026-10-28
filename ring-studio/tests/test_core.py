"""Proves the generic template renders exactly what the hand-written ones did, and that a repo round-trips."""

import copy
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
    assert any("No brightness automation" in n for n in project.report["weatherclock"])
    assert any("below the range" in n for n in project.report["energiklockan"])


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
    assert all("read exact" in " ".join(again.report[c.name]) for c in again.clocks)


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
    restored = project_from_dict(asdict(project))
    assert restored.secrets == {} and restored.clocks == project.clocks and restored.dimming == project.dimming
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


@pytest.mark.parametrize("key", ["price", "weather", "temperature", "battery", "calendar", "hands", "blank"])
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


# ---------- project files, secrets and safety ----------

def test_project_file_round_trip_keeps_notes_and_no_secrets(project):
    project = copy.deepcopy(project)
    from ring_studio import project as P
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
    from ring_studio import project as P
    change(project.clocks[0])
    with pytest.raises(P.ProjectError) as err:
        P.load(P.dump(project, "x"))
    assert any(problem in p for p in err.value.problems)


def test_names_are_cleaned_and_numbers_clamped(project):
    project = copy.deepcopy(project)
    from ring_studio import project as P
    c = project.clocks[0]
    c.name, c.friendly, c.effect, c.hw.leds = "../../evil", 'Bad"\nname: x', "Ring\\", 500
    again, _ = P.load(P.dump(project, "x"))
    c2 = again.clocks[0]
    assert c2.name == "evil" and '"' not in c2.friendly and "\n" not in c2.friendly
    assert c2.effect == "Ring" and c2.hw.leds == 42


def test_load_rejects_non_projects_and_newer_versions():
    from ring_studio import project as P
    for text in ["!!python/object/apply:os.system ['echo hi']", "just text", "ring_studio: 99\n"]:
        with pytest.raises(P.ProjectError):
            P.load(text)


def test_save_is_atomic_and_keeps_backup(project):
    project = copy.deepcopy(project)
    from ring_studio import project as P
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


def test_examples_open_and_export():
    from ring_studio import project as P
    folder = os.path.join(HERE, "..", "examples")
    found = sorted(f for f in os.listdir(folder) if f.endswith(".ringstudio"))
    assert len(found) == 7
    for name in found:
        p = P.open_file(os.path.join(folder, name))
        assert p.clocks and all(c.note for c in p.clocks)
        assert all(isinstance(t, str) for t in generate.repo_files(p).values())
        files = generate.repo_files(p, name[:-11])
        from ring_studio.importer import _Loader
        assert all(yaml.load(t, Loader=_Loader) for t in files.values())


def test_hands_layout_lights_the_hands():
    from ring_studio.model import STARTERS
    c = STARTERS["hands"][2]()
    at = datetime(2026, 10, 25, 15, 7, tzinfo=CET)
    s = render(generate.jinja(c), {}, {}, at)
    leds = [s[i:i + 6] for i in range(0, 216, 6)]
    assert leds[9] == "ffc35e"  # hour hand just past 3 o'clock, afternoon gold
    assert leds[4] == "ffe1ae"  # minute hand at 7 past, the same colour lightened
    assert leds[0] == leds[18] == leds[27] == "261d0e"  # quarter marks, dim
    assert leds[1] == "000000"  # the face
    c.ring.start_led, c.ring.clockwise = 5, False
    leds = [render(generate.jinja(c), {}, {}, at)[i:i + 6] for i in range(0, 216, 6)]
    assert leds[(5 - 9) % 36] == "ffc35e" and leds[(5 - 4) % 36] == "ffe1ae"


def test_detect_finds_the_mapping():
    from ring_studio.detect import fits, guess
    se3 = {"state": "0.43", "attributes": {**SE3, "unit_of_measurement": "SEK/kWh"}}
    fields, words = guess("timeline", se3)
    assert (fields["attrs"], fields["key"], fields["t_start"], fields["t_end"]) == \
        (["today", "tomorrow"], "SEK_per_kWh", "time_start", "time_end")
    assert fields["scale"] == 100.0 and fields["lo"] <= 0 < fields["hi"] and "today + tomorrow" in words
    weather = {"state": "sunny", "attributes": {"forecast": [
        {"datetime": "2026-10-25T15:00:00+01:00", "condition": "sunny", "temperature": 8.0}] * 3}}
    fields, _ = guess("states", weather)
    assert (fields["attrs"], fields["key"], fields["t_start"]) == (["forecast"], "condition", "")
    assert guess("gauge", {"state": "55", "attributes": {"unit_of_measurement": "%"}})[0]["hi"] == 100.0
    assert fits("timeline", se3) and not fits("states", se3) and fits("states", weather)
    assert fits("gauge", {"state": "21.5"}) and fits("state", {"state": "on"}) and not fits("gauge", {"state": "on"})


# ---------- security ----------

def test_token_is_never_sent_on_a_redirect():
    import http.server
    import threading
    from ring_studio import services
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
            services.HomeAssistant(f"http://127.0.0.1:{front.server_port}", "SECRET").states()
        assert seen == [(front.server_port, "Bearer SECRET")]  # the second server never saw anything
    finally:
        front.shutdown()
        back.shutdown()


def test_home_assistant_address_rules():
    from ring_studio import services
    for bad in ["file:///etc/passwd", "ftp://x", "homeassistant.local", "https://user:pw@ha.example.com"]:
        with pytest.raises(RuntimeError):
            services.check_url(bad)
    assert services.check_url(" https://ha.example.com:8123/ ") == "https://ha.example.com:8123"
    assert services.plain_http_warning("http://ha.example.com:8123")
    for fine in ["https://ha.example.com", "http://192.168.1.5:8123", "http://homeassistant.local:8123",
                 "http://localhost:8123", "http://homeassistant:8123"]:
        assert services.plain_http_warning(fine) is None
    with pytest.raises(RuntimeError, match="token"):
        services.HomeAssistant("https://ha.example.com", "").states()


def test_zip_import_refuses_escapes_and_bombs():
    import zipfile
    from ring_studio import importer
    with tempfile.TemporaryDirectory() as tmp:
        evil = os.path.join(tmp, "evil.zip")
        with zipfile.ZipFile(evil, "w") as zf:
            zf.writestr("../../outside.yaml", "x: 1")
        with pytest.raises(ValueError):
            importer.read_repo(evil)
        assert not os.path.exists(os.path.join(tmp, "..", "outside.yaml"))
        bomb = os.path.join(tmp, "bomb.zip")
        with zipfile.ZipFile(bomb, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("config/big.yaml", "a" * 3_000_000)
        with pytest.raises(ValueError):
            importer.read_repo(bomb)
        good = os.path.join(tmp, "good.zip")
        with zipfile.ZipFile(good, "w") as zf:
            for folder, _, names in os.walk(REPO):
                for n in names:
                    full = os.path.join(folder, n)
                    zf.write(full, os.path.relpath(full, REPO))
            zf.writestr("config/run_me.sh", "rm -rf /")
        before = set(os.listdir(tempfile.gettempdir()))
        project, where = importer.read_repo(good)
        assert len(project.clocks) == 2 and where == good
        assert not {d for d in set(os.listdir(tempfile.gettempdir())) - before if d.startswith("ringstudio_")}


def test_project_file_refuses_alias_bombs():
    from ring_studio import project as P
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
    from ring_studio import services, storage
    a, b = copy.deepcopy(project), copy.deepcopy(project)
    a.secrets, b.secrets = {}, {}
    generate.secrets_file(a)
    generate.secrets_file(b)
    assert a.secrets["ap_password"] != b.secrets["ap_password"] and len(a.secrets["ap_password"]) >= 12
    assert os.stat(storage.HOME).st_mode & 0o077 == 0
    os.makedirs(os.path.join(services.BUILD, "config"), exist_ok=True)
    open(os.path.join(services.BUILD, "config", "secrets.yaml"), "w").close()
    services.forget_build_secrets()
    assert not os.path.exists(os.path.join(services.BUILD, "config", "secrets.yaml"))


def test_tracked_secrets_are_spotted():
    with tempfile.TemporaryDirectory() as tmp:
        os.makedirs(os.path.join(tmp, ".git"))
        assert not generate.secrets_committed(tmp)
        with open(os.path.join(tmp, ".git", "index"), "wb") as fh:
            fh.write(b"DIRC....config/secrets.yaml\x00....")
        assert generate.secrets_committed(tmp)
