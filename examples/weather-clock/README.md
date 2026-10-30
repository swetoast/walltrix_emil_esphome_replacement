# Weather Clock

Shows the weather for the coming 12 hours, 3 LEDs per hour, from the Met.no forecast that a default Home Assistant install provides. No extra integrations or helper sensors are needed.

## Files

| File | Goes to |
|---|---|
| [`esphome/weather-clock.yaml`](esphome/weather-clock.yaml) | ESPHome Device Builder, or `esphome run` |
| [`homeassistant/weather_clock.yaml`](homeassistant/weather_clock.yaml) | `/config/packages/weather_clock.yaml` in Home Assistant |

## Data sources

| Entity | Comes from | Used for |
|---|---|---|
| `weather.forecast_home` | Met.no, set up automatically during Home Assistant onboarding | Condition, temperature and rain, from the hourly forecast |
| `sun.sun` | Sun, part of `default_config` | The clock's Auto Brightness |

Met.no names the weather entity after the location name chosen during setup. If yours is not `weather.forecast_home`, change `weather_entity` at the top of the package.

## Three rings

Pick one with the Ring Mode select on the clock's device page.

All three rings are 12 hours, read like the hour hand. One forecast hour is 3 LEDs:

- Each hour lights the 3 LEDs at its place on the face: 07:00 to 08:00 lights the 3 LEDs from the 7 to the 8.
- An hour that has ended shows the same hour 12 hours later, so the ring always holds the coming 12 hours.
- The current hour is at full brightness, the rest at 40 percent.
- Met.no's forecast usually starts at the next full hour. The current hour then uses that first forecast hour, so it does not go dark.

For the hours to sit under the right numerals, set `led_offset` and `clockwise` for your clock, see [Time on the ring](../../docs/guides/02-time-on-the-ring.md#line-the-face-up-with-your-clock).

### Condition

One colour per Home Assistant weather condition.

| Condition | Colour |
|---|---|
| `sunny` | Gold `#FFD700` |
| `clear-night` | Night blue `#0F2043` |
| `partlycloudy` | Pale blue `#C8E1FF` |
| `cloudy` | Slate grey `#708090` |
| `fog` | Light grey `#BEBECD` |
| `rainy` | Blue `#1E90FF` |
| `pouring` | Deep blue `#0000CD` |
| `snowy` | White `#F0F8FF` |
| `snowy-rainy` | Lilac `#AA82E6` |
| `hail` | Plum `#DDA0DD` |
| `lightning` | Pink `#FF1493` |
| `lightning-rainy` | Indigo `#4B0082` |
| `windy` | Turquoise `#40E0D0` |
| `windy-variant` | Teal `#008B8B` |
| `exceptional` | Red orange `#FF4500` |
| anything else | Grey `#646464` |

### Temperature

A blended scale in °C:

| °C | Colour |
|---|---|
| -15 or below | Violet `#4000FF` |
| -5 | Blue `#0060FF` |
| 0 | Cyan `#00C0FF` |
| 5 | Mint `#00FFA0` |
| 10 | Green `#40FF00` |
| 15 | Lime `#C0FF00` |
| 20 | Amber `#FFC000` |
| 25 | Orange `#FF6000` |
| 30 or above | Red `#FF0000` |

### Rain

Precipitation per hour, in bands:

| mm per hour | Colour |
|---|---|
| under 0.1 | Nearly off `#0A0A0A` |
| 0.1 to 0.5 | Light blue `#60A0FF` |
| 0.5 to 2 | Blue `#2060FF` |
| 2 to 5 | Deep blue `#0020FF` |
| 5 or more | Purple `#8000FF` |
| 0.1 or more at 0 °C or colder | Snow, white `#FFFFFF` |

## Common changes

| Want | Change |
|---|---|
| Line the hours up with the numerals | `led_offset` and `clockwise`, see [Time on the ring](../../docs/guides/02-time-on-the-ring.md#line-the-face-up-with-your-clock) |
| 2 hours per 6 LEDs | `interval_minutes: 120` |
| Other combinations | See [Time on the ring](../../docs/guides/02-time-on-the-ring.md#intervals-and-leds) |
| Different colours | Edit the lists in `variables:`, see [Colours](../../docs/guides/03-colours.md) |
| Start on another ring after a power cut | Change `initial_option` of Ring Mode in `weather-clock.yaml` |

## Device

Besides the rings, the clock has Auto Brightness, night hours and diagnostics. See [Device entities](../../docs/reference/device-entities.md).
