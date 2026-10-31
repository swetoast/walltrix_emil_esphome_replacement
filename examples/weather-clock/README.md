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
- Every hour is at full brightness (`dim_others: 1`). Set `dim_others` below 1 to dim every hour except the current one, for example 0.4 for 40 percent.
- Met.no's forecast usually starts at the next full hour. The current hour then uses that first forecast hour, so it does not go dark.

For the hours to sit under the right numerals, set `led_offset` and `clockwise` for your clock, see [Time on the ring](../../docs/guides/02-time-on-the-ring.md#line-the-face-up-with-your-clock).

### Condition

One colour per Home Assistant weather condition.

| Condition | Colour |
|---|---|
| `sunny` | Gold `#FFD700` |
| `clear-night` | Dim grey `#333333` |
| `partlycloudy` | Warm white `#EDECC7` |
| `cloudy` | Grey `#83888C` |
| `fog` | Light grey `#D5D5D8` |
| `rainy` | Blue `#1E90FF` |
| `pouring` | Blue `#4589FD` |
| `snowy` | White `#F8FCFF` |
| `snowy-rainy` | White `#F5FAFF` |
| `hail` | Ice blue `#CFE2F3` |
| `lightning` | Red `#FF1414` |
| `lightning-rainy` | Salmon `#FA8279` |
| `windy` | Violet `#7D4BF5` |
| `windy-variant` | Violet `#7D4BF5` |
| `exceptional` | Green `#50FF00` |
| anything else | Grey `#646464` |

### Temperature

A blended scale in °C, every 2.5 degrees. Pale blue for frost, deeper blue towards 10, green for mild weather, then amber to red:

| °C | Colour |
|---|---|
| -15 or below | Ice white `#E4F0FF` |
| -10 | Pale blue `#CEE4FF` |
| -5 | Light blue `#B2D2FF` |
| 0 | Sky blue `#9DC4FF` |
| 5 | Blue `#77A9FF` |
| 10 | Bright blue `#4EB0FF` |
| 12.5 | Teal `#3CD2E6` |
| 15 | Mint `#3CFFA0` |
| 17.5 | Green `#40FF40` |
| 20 | Yellow green `#A8FF3C` |
| 22.5 | Amber `#FFD060` |
| 25 | Orange `#FF7A50` |
| 30 or above | Red `#FF085C` |

The package has steps at every 2.5 degrees; the table shows the main ones.

### Rain

Precipitation per hour, in bands. The scale depends on what falls:

| mm per hour | Rain | Snow | Sleet or hail |
|---|---|---|---|
| under 0.1 | Nearly off `#0A0A0A` | Nearly off | Nearly off |
| 0.1 | Pale blue `#B2D2FF` | Dim white `#707070` | `#7088A8` |
| 0.5 | `#7BAEFF` | `#A0A0A0` | `#98B4D8` |
| 1 | `#4E8CFF` | `#D0D0D0` | `#C0D8FF` |
| 2.5 | `#1F5CFF` | White `#FFFFFF` | `#E0ECFF` |
| 5 | Deep blue `#0030FF` | | |
| 10 or more | Darkest blue `#0000E0` | | |

Snow is used when the forecast says `snowy`, or at 0 °C or colder. Sleet or hail is used when it says `snowy-rainy` or `hail`. Everything else is rain.

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
