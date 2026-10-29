"""Sun elevation and the brightness the adaptive brightness automation sets for it.

The elevation formula is the NOAA solar position approximation, good to a fraction of a degree,
which is plenty for a dimming curve. The clock itself uses sun.sun's elevation from Home Assistant; this
is only for the preview, which needs the elevation at times sun.sun does not report (later today, and the
day curve). `brightness` mirrors the script generate.sun_block puts on the clock.
"""

import math
from datetime import datetime, timedelta, timezone


def elevation(lat, lon, when):
    """Sun elevation in degrees at a moment (timezone-aware datetime)."""
    t = when.astimezone(timezone.utc)
    day = t.timetuple().tm_yday
    hour = t.hour + t.minute / 60 + t.second / 3600
    g = 2 * math.pi / 365 * (day - 1 + (hour - 12) / 24)
    eqtime = 229.18 * (0.000075 + 0.001868 * math.cos(g) - 0.032077 * math.sin(g)
                       - 0.014615 * math.cos(2 * g) - 0.040849 * math.sin(2 * g))
    decl = (0.006918 - 0.399912 * math.cos(g) + 0.070257 * math.sin(g) - 0.006758 * math.cos(2 * g)
            + 0.000907 * math.sin(2 * g) - 0.002697 * math.cos(3 * g) + 0.00148 * math.sin(3 * g))
    solar_minutes = hour * 60 + eqtime + 4 * lon
    angle = math.radians(solar_minutes / 4 - 180)
    phi = math.radians(lat)
    cos_zenith = math.sin(phi) * math.sin(decl) + math.cos(phi) * math.cos(decl) * math.cos(angle)
    return 90 - math.degrees(math.acos(max(-1.0, min(1.0, cos_zenith))))


def brightness(dimming, when, elev):
    """What the clock sets: 0 overnight, otherwise low to high as the sun climbs."""
    if when.hour < dimming.night_end or when.hour >= dimming.night_start:
        return 0
    span = dimming.elev_high - dimming.elev_low
    fraction = max(0.0, min(1.0, (elev - dimming.elev_low) / span)) if span else 1.0
    return int(math.floor(dimming.low + (dimming.high - dimming.low) * fraction + 0.5))  # like roundf on the clock


def day_curve(dimming, lat, lon, day, step=30):
    """(time, brightness) for every `step` minutes of the day `day` (a timezone-aware datetime)."""
    start = day.replace(hour=0, minute=0, second=0, microsecond=0)
    out = []
    for i in range(24 * 60 // step):
        t = start + timedelta(minutes=i * step)
        out.append((t, brightness(dimming, t, elevation(lat, lon, t))))
    return out


def at(dimming, lat, lon, when: datetime):
    return brightness(dimming, when, elevation(lat, lon, when))
