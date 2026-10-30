# Sky Clock

Shows night, dawn, day and dusk for the coming 12 hours, or the current moon phase.

## Files

| File | Goes to |
|---|---|
| [`esphome/sky-clock.yaml`](esphome/sky-clock.yaml) | ESPHome Device Builder, or `esphome run` |
| [`homeassistant/sky_clock.yaml`](homeassistant/sky_clock.yaml) | `/config/packages/sky_clock.yaml` in Home Assistant |

## Data sources

| Entity | Comes from | Used for |
|---|---|---|
| `sun.sun` | Sun, part of `default_config` | Sun ring: `next_dawn`, `next_rising`, `next_setting` and `next_dusk` |
| `sensor.moon_phase` | Moon integration | Moon ring |

Add the Moon integration under Settings > Devices & services > Add integration > Moon. It needs no setup.

## Two rings

Pick one with the Ring Mode select on the clock's device page. Both rings update once a minute.

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

### Moon

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

## Line up with the face

For the hours and the start of the moon to sit in the right place, set `led_offset` and `clockwise` for your clock, see [Time on the ring](../../docs/guides/02-time-on-the-ring.md#line-the-face-up-with-your-clock).

## Common changes

| Want | Change |
|---|---|
| The dark part of the moon faintly visible | `moon_dark_color: "#050510"` |
| Other colours | Edit the colours in `variables:`, see [Colours](../../docs/guides/03-colours.md) |

## Device

Besides the rings, the clock has Auto Brightness, night hours and diagnostics. See [Device entities](../../docs/reference/device-entities.md).
