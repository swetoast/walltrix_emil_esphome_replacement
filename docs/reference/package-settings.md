# Package settings

Every setting in the `variables:` section of the example packages. The guides explain them with examples: [Time on the ring](../guides/02-time-on-the-ring.md) and [Colours](../guides/03-colours.md).

After editing, reload with Developer tools > YAML > Template entities.

## Shared by both packages

| Setting | Type | Price Clock default | Weather Clock default | Description |
|---|---|---|---|---|
| `layout` | `minutes` or `hours` | `minutes` | `hours` | The full ring is 60 minutes or 12 hours |
| `interval_minutes` | `minutes`: 15 or 30. `hours`: 60, 120, 180 or 360 | `15` | `60` | Length of one interval: 9, 18, 3, 6, 9 or 18 LEDs |
| `led_offset` | 0 to 35 | `0` | `0` | The LED under 12 o'clock |
| `clockwise` | `true` or `false` | `true` | `true` | LED numbers go up clockwise |
| `dim_others` | 0.0 to 1.0 | `0.55` | `0.4` | Brightness factor for every LED outside the current interval |
| `no_data_color` | colour | `"#000000"` | `"#000000"` | Intervals with no data |

## Price Clock

| Setting | Type | Default | Description |
|---|---|---|---|
| `price_entity` | entity ID | `sensor.swedish_spot_price_elpris_se3_forecast` | Price sensor. Needs `today` and `tomorrow` attributes, each a list of slots with `time_start`, `time_end` and `SEK_per_kWh`. |
| `price_colors` | gradient list | 9 steps from `[0, "#00BFFF"]` to `[100, "#FF0040"]` | Price in öre/kWh to colour, blended between steps |

Output: `sensor.price_clock_ring_colors`

## Weather Clock

| Setting | Type | Default | Description |
|---|---|---|---|
| `weather_entity` | entity ID | `weather.forecast_home` | Weather entity with an hourly forecast |
| `condition_colors` | map | 15 conditions | Weather condition to colour |
| `unknown_condition_color` | colour | `"#646464"` | Conditions missing from `condition_colors` |
| `temperature_colors` | gradient list | 9 steps from `[-15, "#4000FF"]` to `[30, "#FF0000"]` | °C to colour, blended between steps |
| `rain_colors` | step list | 5 steps from `[0, "#0A0A0A"]` to `[5, "#8000FF"]` | mm per hour to colour, highest step reached |
| `snow_color` | colour | `"#FFFFFF"` | Used instead of `rain_colors` when there is at least 0.1 mm at 0 °C or colder. The 0.1 mm limit is fixed in the template. |
| `sun_colors` | map with `night`, `morning`, `day`, `evening` | dark blue, orange, amber, purple | Part of the day to colour |

Outputs:

| Sensor | Ring Mode |
|---|---|
| `sensor.weather_clock_condition_ring_colors` | Condition |
| `sensor.weather_clock_temperature_ring_colors` | Temperature |
| `sensor.weather_clock_rain_ring_colors` | Rain |
| `sensor.weather_clock_sun_ring_colors` | Sun |

The sun ring's parts of the day come from `sun.sun`:

| Part | From | To |
|---|---|---|
| `morning` | dawn (`next_dawn`) | sunrise (`next_rising`) |
| `day` | sunrise | sunset (`next_setting`) |
| `evening` | sunset | dusk (`next_dusk`) |
| `night` | dusk | dawn |

## Value types

| Type | Written as | Example |
|---|---|---|
| colour | Quoted hex with `#` | `"#FF6000"` |
| gradient list | List of `[value, colour]`, values rising | `- [0, "#00FF00"]` |
| step list | List of `[threshold, colour]`, thresholds rising | `- [0.5, "#2060FF"]` |
| map | `name: colour` | `day: "#FFB400"` |
| entity ID | Plain text | `weather.forecast_home` |

## Triggers

Both packages are trigger-based template sensors that update:

- when Home Assistant starts
- every minute (`time_pattern`, `minutes: "/1"`)

The Weather Clock also calls `weather.get_forecasts` with `type: hourly` on each update, with `continue_on_error: true` so a failed call leaves the sensors unavailable instead of stopping the update.
