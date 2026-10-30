# Weather Clock

Shows the weather for the coming hours, using only what a default Home Assistant install provides: the Met.no forecast and the Sun integration. No extra integrations or helper sensors are needed.

## Files

| File | Goes to |
|---|---|
| [`esphome/weather-clock.yaml`](esphome/weather-clock.yaml) | ESPHome Device Builder, or `esphome run` |
| [`homeassistant/weather_clock.yaml`](homeassistant/weather_clock.yaml) | `/config/packages/weather_clock.yaml` in Home Assistant |

## Data sources

| Entity | Comes from | Used for |
|---|---|---|
| `weather.forecast_home` | Met.no, set up automatically during Home Assistant onboarding | Condition, temperature and rain, from the hourly forecast |
| `sun.sun` | Sun, part of `default_config` | Sun ring, and the clock's Auto Brightness |

Met.no names the weather entity after the location name chosen during setup. If yours is not `weather.forecast_home`, change `weather_entity` at the top of the package.

## Four rings

Pick one with the Ring Mode select on the clock's device page. With default settings each LED is one hour: LED 0 is the current hour at full brightness and LEDs 1 to 35 are the next 35 hours at 40 percent.

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

### Sun

The part of the day at each LED's time:

| Part | From | To | Colour |
|---|---|---|---|
| Night | dusk | dawn | Dark blue `#001040` |
| Morning | dawn | sunrise | Orange `#FF5A1E` |
| Day | sunrise | sunset | Amber `#FFB400` |
| Evening | sunset | dusk | Purple `#8C28C8` |

With 36 hourly LEDs the sun ring shows a day and a half, so you see tonight, tomorrow's daylight and the next evening.

## Common changes

| Want | Change |
|---|---|
| Next 9 hours in 15 minute steps | `slot_minutes: 15` |
| Read the ring like the clock face | `layout: clock` plus `led_offset` and `clockwise`, see [Time slots and LED layout](../../docs/guides/02-timeslots-and-layout.md#the-clock-layout) |
| Different colours | Edit the lists in `variables:`, see [Colours](../../docs/guides/03-colours.md) |
| Start on another ring after a power cut | Change `initial_option` of Ring Mode in `weather-clock.yaml` |

## Device

Besides the rings, the clock has Auto Brightness, night hours and diagnostics. See [Device entities](../../docs/reference/device-entities.md).
