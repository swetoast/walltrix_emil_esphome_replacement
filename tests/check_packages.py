"""Render the example packages with made-up data and check the output.

Run from the repository root:
    pip install jinja2 pyyaml
    python tests/check_packages.py

Each ring is printed as 36 colour codes, and in a terminal with colour
support as a row of coloured blocks. The script exits with an error if a
ring is not 216 hex characters or misbehaves when data is missing.
"""
import datetime as dt
import math
import os
import re
import sys
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(__file__))
from ha_template_sim import render_package  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRICE = os.path.join(ROOT, "examples", "price-clock", "homeassistant", "price_clock.yaml")
WEATHER = os.path.join(ROOT, "examples", "weather-clock", "homeassistant", "weather_clock.yaml")
SKY = os.path.join(ROOT, "examples", "sky-clock", "homeassistant", "sky_clock.yaml")
ADGUARD = os.path.join(ROOT, "examples", "adguard-clock", "homeassistant", "adguard_clock.yaml")

TZ = ZoneInfo("Europe/Stockholm")
NOW = dt.datetime(2026, 10, 30, 7, 23, tzinfo=TZ)
HEX216 = re.compile(r"^[0-9A-F]{216}$")
failures = []


def show(name, available, state):
    blocks = ""
    if sys.stdout.isatty():
        for i in range(0, len(state), 6):
            r, g, b = (int(state[i + j:i + j + 2], 16) for j in (0, 2, 4))
            blocks += f"\x1b[48;2;{r};{g};{b}m  \x1b[0m"
    print(f"{name}  available={available}  length={len(state)}")
    if blocks:
        print("  " + blocks)
    print("  " + " ".join(state[i:i + 6] for i in range(0, len(state), 6)))


def expect(cond, message):
    if not cond:
        failures.append(message)
        print("  FAIL: " + message)


def price_slots(day):
    start = dt.datetime(2026, 10, day, 0, 0, tzinfo=TZ)
    slots = []
    for q in range(96):
        s = start + dt.timedelta(minutes=15 * q)
        slots.append({
            "time_start": s.isoformat(),
            "time_end": (s + dt.timedelta(minutes=15)).isoformat(),
            "SEK_per_kWh": round(0.55 + 0.7 * math.sin(q / 96 * 4 * math.pi), 4),
        })
    return slots


def forecast(hours):
    conditions = ["sunny", "partlycloudy", "cloudy", "rainy", "pouring", "clear-night", "snowy", "fog"]
    base = NOW.replace(minute=0)
    return [{
        "datetime": (base + dt.timedelta(hours=h)).astimezone(dt.timezone.utc).isoformat(),
        "condition": conditions[h % len(conditions)],
        "temperature": -6 + h * 1.2,
        "precipitation": [0, 0, 0.05, 0.2, 1, 3, 8, 0][h % 8],
    } for h in range(hours)]


def sun_attributes():
    def at(h, m):
        return dt.datetime(2026, 10, 30, h, m, tzinfo=TZ).astimezone(dt.timezone.utc).isoformat()
    return {"sun.sun": {"next_dawn": at(7, 20), "next_rising": at(7, 58),
                        "next_setting": at(16, 36), "next_dusk": at(17, 14)}}


def check_all_valid(results, label):
    for name, (available, state) in results.items():
        show(f"[{label}] {name}", available, state)
        expect(available, f"{label} {name}: not available")
        expect(bool(HEX216.match(state)), f"{label} {name}: not 216 hex characters")


# Every allowed face and interval, and how many LEDs one interval gets
FACES = [("minutes", 15, 9), ("minutes", 30, 18),
         ("hours", 60, 3), ("hours", 120, 6), ("hours", 180, 9), ("hours", 360, 18)]


def groups(state, size):
    leds = [state[i:i + 6] for i in range(0, 216, 6)]
    return [leds[g:g + size] for g in range(0, 36, size)]


def check_face(path, sensor, layout, interval, size, label, **kwargs):
    state = render_package(path, NOW, overrides={"layout": layout, "interval_minutes": interval},
                           **kwargs)[sensor][1]
    expect(bool(HEX216.match(state)), f"{label}: not 216 hex characters")
    blocks = groups(state, size)
    for g, block in enumerate(blocks):
        expect(len(set(block)) == 1, f"{label}: LEDs {g * size + 1} to {g * size + size} should be one interval")
    return state, blocks


# Price Clock
ENT = "sensor.swedish_spot_price_elpris_se3_forecast"
all_slots = price_slots(30) + price_slots(31)
price_attrs = {ENT: {"today": price_slots(30), "tomorrow": price_slots(31)}}
check_all_valid(render_package(PRICE, NOW, attributes=price_attrs), "price default")
for layout, interval, size in FACES:
    check_face(PRICE, "Price Clock Ring Colors", layout, interval, size, f"price {layout} {interval} min",
               attributes=price_attrs)


def price_of(starts, attrs_slots, layout="minutes", interval=15):
    """Colour the package gives an interval when only these slots exist."""
    chosen = [x for x in attrs_slots if x["time_start"][11:16] in starts and x["time_start"].startswith("2026-10-30")]
    return render_package(PRICE, NOW, attributes={ENT: {"today": chosen, "tomorrow": []}},
                          overrides={"layout": layout, "interval_minutes": interval})["Price Clock Ring Colors"][1]


# Default at 07:23: 12 to 3 is 08:00, 3 to 6 is 07:15 (now, bright), 6 to 9 is 07:30, 9 to 12 is 07:45
state = render_package(PRICE, NOW, attributes=price_attrs)["Price Clock Ring Colors"][1]
for q, start in enumerate(["08:00", "07:15", "07:30", "07:45"]):
    alone = price_of([start], all_slots)
    expect(alone[q * 54:q * 54 + 6] == state[q * 54:q * 54 + 6], f"price 15 min: quarter {q + 1} should be {start}")
bright = render_package(PRICE, NOW, attributes=price_attrs, overrides={"dim_others": 1.0})["Price Clock Ring Colors"][1]
expect(state[54:60] == bright[54:60] and state[0:6] != bright[0:6], "price 15 min: only the current quarter is bright")
# 30 min at 07:23: 12 to 6 is 07:00-07:30 (now), 6 to 12 is 07:30-08:00, each the average of two prices
state = render_package(PRICE, NOW, attributes=price_attrs, overrides={"interval_minutes": 30})["Price Clock Ring Colors"][1]
expect(state[0:6] == price_of(["07:00", "07:15"], all_slots, interval=30)[0:6], "price 30 min: 12 to 6 is 07:00 to 07:30")
expect(state[108:114] == price_of(["07:30", "07:45"], all_slots, interval=30)[108:114], "price 30 min: 6 to 12 is 07:30 to 08:00")
# No price for an interval gives no_data_color
late = dt.datetime(2026, 10, 30, 23, 50, tzinfo=TZ)
state = render_package(PRICE, late, attributes={ENT: {"today": price_slots(30), "tomorrow": None}})["Price Clock Ring Colors"][1]
expect(state[0:54] == "000000" * 9, "price: 00:00 tomorrow without tomorrow's prices should be no_data_color")
expect(not render_package(PRICE, NOW)["Price Clock Ring Colors"][0], "price: unavailable without the price sensor")

# Weather Clock
response = {"hourly": {"weather.forecast_home": {"forecast": forecast(48)}}}
sun = sun_attributes()
check_all_valid(render_package(WEATHER, NOW, attributes=sun, response=response), "weather default")
for name in ["Condition", "Temperature", "Rain"]:
    sensor = f"Weather Clock {name} Ring Colors"
    for layout, interval, size in FACES:
        check_face(WEATHER, sensor, layout, interval, size, f"weather {name} {layout} {interval} min",
                   attributes=sun, response=response)

# Default at 07:23: 3 LEDs per hour, the 3 LEDs at the 7 are 07:00 (now, bright), the 8 is 08:00,
# the 6 is 18:00. The forecast starts at 07:00: sunny, partlycloudy, cloudy, ...
state = render_package(WEATHER, NOW, attributes=sun, response=response)["Weather Clock Condition Ring Colors"][1]
hours = groups(state, 3)
expect(hours[7] == ["FFD700"] * 3, "weather: the 3 LEDs at the 7 are now (sunny, full brightness)")
expect(hours[8] == ["505A66"] * 3, "weather: the 3 LEDs at the 8 are 08:00 (partlycloudy, dimmed)")
# Forecast starting at the next hour: the current hour uses the first forecast hour instead of going dark
late_start = {"hourly": {"weather.forecast_home": {"forecast": forecast(49)[1:]}}}
state = render_package(WEATHER, NOW, attributes=sun, response=late_start)["Weather Clock Condition Ring Colors"][1]
expect(groups(state, 3)[7] != ["000000"] * 3, "weather: the current hour must not go dark")
# Past the end of the forecast gives no_data_color
short = {"hourly": {"weather.forecast_home": {"forecast": forecast(5)}}}
state = render_package(WEATHER, NOW, attributes=sun, response=short)["Weather Clock Condition Ring Colors"][1]
expect(groups(state, 3)[6] == ["000000"] * 3, "weather: 18:00 is past a 5 hour forecast and should be no_data_color")
# Forecast call failed: forecast rings unavailable, sun ring still works
for name, (available, _state) in render_package(WEATHER, NOW, attributes=sun).items():
    expect(not available, f"weather {name}: should be unavailable when the forecast call failed")

# Sky Clock Sun ring: every allowed face and interval
for layout, interval, size in FACES:
    check_face(SKY, "Sky Clock Sun Ring Colors", layout, interval, size, f"sky sun {layout} {interval} min",
               attributes=sun, states={"sensor.moon_phase": "full_moon"})
# Default at 07:23, 3 LEDs per hour: dawn 07:20, sunrise 07:58, sunset 16:36, dusk 17:14
state = render_package(SKY, NOW, attributes=sun, states={"sensor.moon_phase": "full_moon"})["Sky Clock Sun Ring Colors"][1]
hours = groups(state, 3)
for hour, want, label in [(7, "FF5A1E", "07:00 is now, morning, bright"), (8, "664800", "08:00 is day, dimmed"),
                          (4, "664800", "16:00 is day"), (5, "381050", "17:00 is evening"),
                          (6, "000619", "18:00 is night")]:
    expect(hours[hour] == [want] * 3, f"sky sun: the 3 LEDs at the {hour} should be {want}: {label}")
# Moon: lit LEDs per phase, counted from 12 o'clock
for phase, first, count in [("new_moon", None, 0), ("waxing_crescent", 0, 9), ("first_quarter", 0, 18),
                            ("waxing_gibbous", 0, 27), ("full_moon", 0, 36), ("waning_gibbous", 9, 27),
                            ("last_quarter", 18, 18), ("waning_crescent", 27, 9)]:
    sky = render_package(SKY, NOW, attributes=sun,
                         states={"sensor.moon_phase": phase})
    state = sky["Sky Clock Moon Ring Colors"][1]
    lit = [i for i in range(36) if state[i * 6:i * 6 + 6] != "000000"]
    want = [] if first is None else list(range(first, first + count))
    expect(lit == want, f"sky: {phase} should light {count} LEDs")
expect(not render_package(SKY, NOW, attributes=sun)["Sky Clock Moon Ring Colors"][0],
       "sky: moon ring unavailable without sensor.moon_phase")

# AdGuard Clock: blocked share of 36 LEDs, rounded, clockwise from 12 o'clock
for ratio, blocked in [("0", 0), ("7.89", 3), ("25", 9), ("50", 18), ("100", 36)]:
    net = render_package(ADGUARD, NOW, states={"sensor.adguard_home_dns_queries_blocked_ratio": ratio})
    available, state = net["AdGuard Clock Ring Colors"]
    leds = [state[i:i + 6] for i in range(0, 216, 6)]
    expect(available and leds == ["FF0080"] * blocked + ["00BFFF"] * (36 - blocked),
           f"adguard: {ratio} percent should be {blocked} blocked LEDs")
expect(not render_package(ADGUARD, NOW)["AdGuard Clock Ring Colors"][0], "adguard: unavailable without AdGuard Home")

print()
if failures:
    print(f"{len(failures)} check(s) failed")
    sys.exit(1)
print("All checks passed")
