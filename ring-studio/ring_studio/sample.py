"""Made-up data for the example entities, so the examples show something before Home Assistant is connected.

The data is built around the current time, the same shape Home Assistant reports it in: 15-minute prices for
today and tomorrow, an hourly forecast in UTC starting at the next hour, a temperature, a battery level and a
calendar.
"""

import math
from datetime import timedelta, timezone

PRICE = "sensor.swedish_spot_price_elpris_se3_forecast"
WEATHER = "sensor.weather_hourly"


def _price(hour):
    """A typical autumn day in SEK per kWh: cheap at night, a morning peak and a higher evening peak."""
    ore = 18 + 40 * math.exp(-((hour - 8) ** 2) / 3) + 75 * math.exp(-((hour - 18) ** 2) / 4) \
        - 12 * math.exp(-((hour - 3) ** 2) / 5)
    return round(ore / 100, 5)


def _sky(hour):
    if hour < 6 or hour >= 21:
        return "clear-night" if hour % 5 else "cloudy"
    if hour < 9:
        return "fog"
    if hour < 12:
        return "partlycloudy"
    if hour < 15:
        return "sunny"
    if hour < 18:
        return "rainy" if hour == 16 else "cloudy"
    return "partlycloudy"


def states(now):
    """entity_id -> {"state", "attributes"}, as Home Assistant would report it at `now`."""
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    prices = {}
    for day, name in ((0, "today"), (1, "tomorrow")):
        start = midnight + timedelta(days=day)
        prices[name] = [{"time_start": (start + timedelta(minutes=15 * i)).isoformat(),
                         "time_end": (start + timedelta(minutes=15 * (i + 1))).isoformat(),
                         "SEK_per_kWh": _price((15 * i) / 60)} for i in range(96)]
    next_hour = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    forecast = [{"datetime": (next_hour + timedelta(hours=i)).astimezone(timezone.utc).isoformat(),
                 "condition": _sky((next_hour + timedelta(hours=i)).hour),
                 "temperature": round(7 + 3 * math.sin((next_hour.hour + i - 9) / 24 * 2 * math.pi), 1),
                 "precipitation": 0.6 if _sky((next_hour + timedelta(hours=i)).hour) == "rainy" else 0.0}
                for i in range(48)]
    return {
        PRICE: {"state": str(_price(now.hour + now.minute / 60)),
                "attributes": {**prices, "unit_of_measurement": "SEK/kWh", "friendly_name": "Sample prices"}},
        WEATHER: {"state": _sky(now.hour), "attributes": {"forecast": forecast, "friendly_name": "Sample forecast"}},
        "sensor.outdoor_temperature": {"state": "7.4", "attributes": {"unit_of_measurement": "°C"}},
        "sensor.phone_battery_level": {"state": "64", "attributes": {"unit_of_measurement": "%"}},
        "calendar.home": {"state": "on", "attributes": {"message": "Sample event", "friendly_name": "Home"}},
    }


def state(entity, now):
    """Sample data for one entity, or None when there is none."""
    return states(now).get(entity)


def catalogue(now):
    """A small made-up Home Assistant, used to show the setups before Home Assistant is connected and in tests:
    one or more entities for every setup."""
    out = states(now)
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    door = lambda name, dc, on: {"state": "on" if on else "off",  # noqa: E731
                                 "attributes": {"device_class": dc, "friendly_name": name}}
    out.update({
        "weather.home": {"state": _sky(now.hour), "attributes": {
            "friendly_name": "Home", "temperature": 7.4, "temperature_unit": "°C", "wind_bearing": 225,
            "wind_speed": 6.0, "wind_speed_unit": "m/s", "precipitation_unit": "mm"}},
        "sensor.blitzortung_lightning_azimuth": {"state": "292", "attributes": {"unit_of_measurement": "°",
                                                                                "friendly_name": "Lightning azimuth"}},
        "sensor.blitzortung_lightning_distance": {"state": "18", "attributes": {"unit_of_measurement": "km",
                                                                                 "friendly_name": "Lightning distance"}},
        "binary_sensor.front_door": door("Front door", "door", False),
        "binary_sensor.back_door": door("Back door", "door", True),
        "binary_sensor.kitchen_window": door("Kitchen window", "window", False),
        "binary_sensor.garage_door": door("Garage door", "garage_door", False),
        "binary_sensor.internet": door("Internet", "connectivity", True),
        "plant.monstera": {"state": "problem", "attributes": {"friendly_name": "Monstera"}},
        "plant.basil": {"state": "ok", "attributes": {"friendly_name": "Basil"}},
        "person.anna": {"state": "home", "attributes": {"friendly_name": "Anna"}},
        "person.erik": {"state": "not_home", "attributes": {"friendly_name": "Erik"}},
        "sensor.hall_motion_battery": {"state": "14", "attributes": {"device_class": "battery",
                                                                     "unit_of_measurement": "%",
                                                                     "friendly_name": "Hall motion battery"}},
        "sensor.radon": {"state": "86", "attributes": {"unit_of_measurement": "Bq/m³", "friendly_name": "Radon"}},
        "sensor.next_tram": {"state": (now + timedelta(minutes=12)).replace(microsecond=0).isoformat(),
                             "attributes": {"device_class": "timestamp", "friendly_name": "Next tram departure"}},
        "timer.laundry": {"state": "active", "attributes": {
            "finishes_at": (now + timedelta(minutes=25)).replace(microsecond=0).isoformat(),
            "friendly_name": "Laundry"}},
        "sensor.dishwasher_finish": {"state": (now + timedelta(minutes=40)).replace(microsecond=0).isoformat(),
                                     "attributes": {"device_class": "timestamp", "friendly_name": "Dishwasher finish"}},
        "calendar.work": {"state": "off", "attributes": {"message": "Planning", "friendly_name": "Work"}},
        "calendar.waste_collection": {"state": "off", "attributes": {"friendly_name": "Waste collection"}},
        "sensor.work_shifts": {"state": "Day", "attributes": {"friendly_name": "Work shifts", "shifts": [
            {"date": (midnight + timedelta(days=d)).isoformat(), "shift": s}
            for d, s in enumerate(["Day", "Day", "Night", "Night", "Off", "Off", "Day"])]}},
    })
    return out


_HOURS_BUSY = {9: "Stand-up", 10: "Planning", 13: "Dentist", 18: "Football"}
_WEEK = ["", "Restavfall", "", "", "Matavfall", "", ""]


def _item_value(key, ring, when, daily, i):
    hour = when.hour
    if key == "condition":
        return ["sunny", "cloudy", "rainy", "partlycloudy", "snowy", "sunny", "fog"][i % 7] if daily else _sky(hour)
    if key == "temperature":
        return round(7 + 3 * math.sin((hour - 9) / 24 * 2 * math.pi) + (i if daily else 0) * 0.8 - 3, 1)
    if key == "precipitation":
        return [0, 0.4, 3.2, 0, 0, 6.1, 0.1][i % 7] if daily else (round(max(0.0, math.sin(i / 3)) * 2, 1))
    if key == "uv_index":
        return [3, 5, 1, 6, 2, 8, 4][i % 7] if daily else max(0, round(7 * math.sin((hour - 6) / 14 * math.pi)))
    if key == "event":
        return _WEEK[i % 7] if daily else _HOURS_BUSY.get(hour, "")
    if ring.colour_by == "values":
        keys = list(ring.colors) or ["on"]
        return keys[i % len(keys)]
    return round(ring.lo + (ring.hi - ring.lo) * (0.5 + 0.45 * math.sin(i / 4)), 2) / (ring.scale or 1)


def fake(ring, now, have=()):
    """Made-up states for the entities a ring reads that are not in `have`, so a new design shows something
    before its data exists. Returns entity_id -> {"state", "attributes"}."""
    out = {}
    L = ring.layout
    e = ring.entity
    if e and e not in have:
        if L in ("from_now", "dial_24h", "week"):
            daily = L == "week"
            midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
            first = midnight if daily or ring.key == "event" else now.replace(minute=0, second=0, microsecond=0)
            step = timedelta(days=1) if daily else timedelta(hours=1)
            items = []
            for i in range(7 if daily else 48):
                when = first + step * i
                item = {ring.t_start or "datetime": when.isoformat(), ring.key or "value":
                        _item_value(ring.key, ring, when, daily, i)}
                if ring.t_end:
                    item[ring.t_end] = (when + step).isoformat()
                items.append(item)
            out[e] = {"state": "ok", "attributes": {(ring.attrs or ["forecast"])[0]: items}}
        elif L == "countdown":
            at = (now + timedelta(minutes=12)).replace(microsecond=0).isoformat()
            out[e] = ({"state": "active", "attributes": {ring.value_attr: at}} if ring.value_attr
                      else {"state": at, "attributes": {}})
        elif L == "compass":
            out[e] = {"state": "225", "attributes": {ring.value_attr: 225} if ring.value_attr else {}}
        else:
            value = (list(ring.colors) or ["on"])[0] if ring.colour_by == "values" else \
                round(ring.lo + (ring.hi - ring.lo) * 0.6, 2)
            out[e] = {"state": str(value), "attributes": {ring.value_attr: value} if ring.value_attr else {}}
    if L == "compass" and ring.entity2 and ring.entity2 not in have:
        v = round(ring.lo + (ring.hi - ring.lo) * 0.3, 1)
        prev = out.get(ring.entity2, {"state": str(v), "attributes": {}})
        if ring.value2_attr:
            prev["attributes"] = {**prev["attributes"], ring.value2_attr: v}
        out[ring.entity2] = prev
    keys = list(ring.colors) or ["on", "off"]
    for i, part in enumerate(ring.parts):
        if part[0] not in have:
            out[part[0]] = {"state": keys[i % len(keys)] if ring.colour_by == "values" else str(15 + 30 * i),
                            "attributes": {}}
    return out
