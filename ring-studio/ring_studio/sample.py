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
                 "temperature": round(7 + 3 * math.sin((next_hour.hour + i - 9) / 24 * 2 * math.pi), 1)}
                for i in range(48)]
    return {
        PRICE: {"state": str(_price(now.hour + now.minute / 60)),
                "attributes": {**prices, "unit_of_measurement": "SEK/kWh", "friendly_name": "Sample prices"}},
        WEATHER: {"state": _sky(now.hour), "attributes": {"forecast": forecast, "friendly_name": "Sample forecast"}},
        "sensor.outdoor_temperature": {"state": "7.4", "attributes": {"unit_of_measurement": "°C"}},
        "sensor.phone_battery_level": {"state": "64", "attributes": {"unit_of_measurement": "%"}},
        "calendar.home": {"state": "on", "attributes": {"message": "Sample event"}},
    }


def state(entity, now):
    """Sample data for one entity, or None when there is none."""
    return states(now).get(entity)
