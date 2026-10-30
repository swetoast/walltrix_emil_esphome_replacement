# Sky Clock

Shows the sun and the moon: night, dawn, day and dusk for the coming 12 hours, the moon phase, when the moon is up, how much of it is lit, where it is, and how long until the next full moon.

## Files

| File | Goes to |
|---|---|
| [`esphome/sky-clock.yaml`](esphome/sky-clock.yaml) | ESPHome Device Builder, or `esphome run` |
| [`homeassistant/sky_clock.yaml`](homeassistant/sky_clock.yaml) | `/config/packages/sky_clock.yaml` in Home Assistant |

## Data sources

| Entity | Comes from | Used for |
|---|---|---|
| `sun.sun` | Sun, part of `default_config` | Sun ring: `next_dawn`, `next_rising`, `next_setting` and `next_dusk` |
| `sensor.moon_phase` | Moon integration | Moon Phase ring |
| `moon_details_entity` | A moon sensor you set at the top of the package | Moon Up, Sun and Moon, Moon Light, Moon Position and Full Moon rings |

Add the Moon integration under Settings > Devices & services > Add integration > Moon. It needs no setup.

The Moon integration only gives the phase. The other five moon rings need a moon sensor with these attributes:

| Attribute | Example | Used by |
|---|---|---|
| `moonrise` | `2026-10-30T18:24:31+01:00` | Moon Up, Sun and Moon |
| `moonset` | `2026-10-30T13:38:09+01:00` | Moon Up, Sun and Moon |
| `moon_azimuth_deg` | `299.48` | Moon Position |
| `moon_altitude_deg` | `14.28` | Moon Position |
| `illumination_fraction` | `77.62` (percent) | Moon Light |
| `next_full_moon` | `2026-11-24T14:53:29+00:00` | Full Moon |

Set `moon_details_entity` to that sensor. Without it those five rings are unavailable, and the Sun and Moon Phase rings still work.

## Seven rings

Pick one with the Ring Mode select on the clock's device page. All rings update once a minute.

| Ring Mode | Shows | LEDs |
|---|---|---|
| Sun | Part of the day per hour | 12 hours, 3 LEDs per hour |
| Moon Phase | The phase | A quarter of the moon = 9 LEDs |
| Moon Up | When the moon is above the horizon | 12 hours, 3 LEDs per hour |
| Sun and Moon | Sun up, moon up or both, per hour | 12 hours, 3 LEDs per hour |
| Moon Light | How much of the moon is lit | 36 LEDs = 100 percent |
| Moon Position | Where the moon is | Compass, 10 degrees per LED |
| Full Moon | Days until the next full moon | 1 LED per day |

### Sun

12 hours, read like the hour hand. One hour is 3 LEDs, coloured by the part of the day:

| Part | From | To | Colour |
|---|---|---|---|
| Night | dusk | dawn | Dark blue `#001040` |
| Morning | dawn | sunrise | Orange `#FF5A1E` |
| Day | sunrise | sunset | Amber `#FFB400` |
| Evening | sunset | dusk | Purple `#8C28C8` |

- Each hour lights the 3 LEDs at its place on the face: 07:00 to 08:00 lights the 3 LEDs from the 7 to the 8.
- An hour that has ended shows the same hour 12 hours later, so the ring always holds the coming 12 hours.
- The current hour is at full brightness and read at the current time, the rest at 40 percent and read at the start of their hour.

Example at 07:23 with dawn 07:20, sunrise 07:58, sunset 16:36 and dusk 17:14:

| On the face | Hour | Part |
|---|---|---|
| 7 to 8 | 07:00 (now) | Morning, full brightness |
| 8 to 9 | 08:00 | Day |
| 4 to 5 | 16:00 | Day |
| 5 to 6 | 17:00 | Evening |
| 6 to 7 | 18:00 | Night |

To change the interval, for example 2 hours per 6 LEDs, see [Time on the ring](../../docs/guides/02-time-on-the-ring.md#intervals-and-leds).

### Moon Phase

The lit part of the ring is the lit part of the moon. One quarter of the face, 9 LEDs, is a quarter of the moon.

| Phase | LEDs lit | On the face |
|---|---|---|
| New moon | 0 | |
| Waxing crescent | 9 | 12 to 3 |
| First quarter | 18 | 12 to 6 |
| Waxing gibbous | 27 | 12 to 9 |
| Full moon | 36 | All |
| Waning gibbous | 27 | 3 to 12 |
| Last quarter | 18 | 6 to 12 |
| Waning crescent | 9 | 9 to 12 |

Waxing fills the ring clockwise from 12, waning empties it clockwise from 12. The lit part is pale blue `#C8D2FF`, the dark part is off.

### Moon Up

12 hours, 3 LEDs per hour, like the Sun ring. An hour is pale blue `#C8D2FF` if the moon is above the horizon at the start of the hour, dark blue `#001040` if not. The current hour is read at the current time and shown at full brightness.

Only today's moonrise and moonset are known. Later hours assume the moon rises and sets 50 minutes later each day, the average for the moon, so hours far from today can be off by some minutes.

Example at 10:59 with moonset 13:38 and moonrise 18:24:

| On the face | Hours | Moon |
|---|---|---|
| 10 to 2 | 10:00 (now) to 13:00 | Up |
| 2 to 7 | 14:00 to 18:00 | Down (18:00 starts before the 18:24 moonrise) |
| 7 to 10 | 19:00 to 21:00 | Up |

### Sun and Moon

12 hours, 3 LEDs per hour. Each hour shows what is above the horizon at its start:

| Above the horizon | Colour |
|---|---|
| Sun and moon | White `#FFFFFF` |
| Sun only | Amber `#FFB400` |
| Moon only | Pale blue `#C8D2FF` |
| Neither | Off |

Sunrise and sunset come from `sun.sun`, moonrise and moonset from the moon sensor.

### Moon Light

The lit share of the moon, filled clockwise from 12. 36 LEDs = 100 percent, 9 LEDs = 25 percent. The share of 36 is rounded: 77.62 percent lights 28 LEDs. This is finer than the Moon Phase ring, which only has 9, 18, 27 or 36.

### Moon Position

The ring is a compass, 12 = north, 3 = east, 6 = south, 9 = west, 10 degrees per LED. One LED lights where the moon is: pale blue `#C8D2FF` above the horizon, dark blue `#001040` below. At 299.48 degrees the moon is at the 10.

### Full Moon

1 LED per day left until the next full moon, filled clockwise from 12. A started day counts as a day: 25 days and 5 hours left lights 26 LEDs. The ring empties as the full moon gets closer. A lunar month is about 29.5 days, so it never needs more than 30 LEDs.

## Line up with the face

For the hours and the start of the moon to sit in the right place, set `led_offset` and `clockwise` for your clock, see [Time on the ring](../../docs/guides/02-time-on-the-ring.md#line-the-face-up-with-your-clock).

## Common changes

| Want | Change |
|---|---|
| The dark part of the moon faintly visible | `moon_dark_color: "#050510"` |
| Other colours | Edit the colours in `variables:`, see [Colours](../../docs/guides/03-colours.md) |

## Device

Besides the rings, the clock has Auto Brightness, night hours and diagnostics. See [Device entities](../../docs/reference/device-entities.md).
