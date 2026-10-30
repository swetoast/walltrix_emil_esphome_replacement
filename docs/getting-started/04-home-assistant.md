# 4. Home Assistant setup

The ring's colours are made in Home Assistant by a package: one YAML file that adds template sensors. The clock subscribes to those sensors and draws what they contain.

## Turn on packages

If `configuration.yaml` does not load packages yet, add:

```yaml
homeassistant:
  packages: !include_dir_named packages
```

If you already have a `homeassistant:` section, add only the `packages:` line inside it. Create the folder `/config/packages/` if it does not exist.

## Copy the package

| Example | Copy | To |
|---|---|---|
| Price Clock | `examples/price-clock/homeassistant/price_clock.yaml` | `/config/packages/price_clock.yaml` |
| Weather Clock | `examples/weather-clock/homeassistant/weather_clock.yaml` | `/config/packages/weather_clock.yaml` |
| Sky Clock | `examples/sky-clock/homeassistant/sky_clock.yaml` | `/config/packages/sky_clock.yaml` |
| AdGuard Clock | `examples/adguard-clock/homeassistant/adguard_clock.yaml` | `/config/packages/adguard_clock.yaml` |
| Holiday Clock | `examples/holiday-clock/homeassistant/holiday_clock.yaml` | `/config/packages/holiday_clock.yaml` |

A package carries its own `template:` section, so it does not clash with templates already in `configuration.yaml`.

## Check the data source

Each package reads one or two entities. Make sure they exist under Developer tools > States before restarting.

| Example | Setting at the top of the package | Default | Notes |
|---|---|---|---|
| Price Clock | `price_entity` | `sensor.swedish_spot_price_elpris_se3_forecast` | Needs `today` and `tomorrow` attributes, see the [Price Clock README](../../examples/price-clock/README.md#data-source) |
| Weather Clock | `weather_entity` | `weather.forecast_home` | Created by Met.no during onboarding. The ID follows the location name chosen then, so it can differ |
| Sky Clock | (fixed) | `sun.sun` | Always present, part of `default_config` |
| Sky Clock | `moon_entity` | `sensor.moon_phase` | Add the Moon integration: Settings > Devices & services > Add integration > Moon. It needs no setup |
| Sky Clock | `moon_details_entity` | `sensor.moon_details` | Your own moon sensor with rise, set, position, illumination and next full moon. See the [Sky Clock README](../../examples/sky-clock/README.md#data-sources) |
| AdGuard Clock | `ratio_entity` | `sensor.adguard_home_dns_queries_blocked_ratio` | Add the AdGuard Home integration. With more than one AdGuard Home server, the second one's sensors get `_2` at the end |
| Holiday Clock | `holiday_calendar` | `calendar.sweden` | Add the Holiday integration and tick the de facto category in its options. The ID follows the country name in Home Assistant's language, see the [Holiday Clock README](../../examples/holiday-clock/README.md#data-source) |

## Restart and confirm

1. Developer tools > YAML > Check configuration.
2. Restart Home Assistant. The first time packages are added a full restart is needed. After later edits, Developer tools > YAML > Template entities is enough.
3. Developer tools > States, search for `ring_colors`. Each sensor must show exactly 216 characters of hex. The Holiday Clock is different: `sensor.holiday_clock_ring` holds one line such as `countdown|12|0|1|C00018`, see the [Holiday Clock README](../../examples/holiday-clock/README.md#what-the-clock-receives).

| Example | Sensor | Used by Ring Mode |
|---|---|---|
| Price Clock | `sensor.price_clock_ring_colors` | (only ring) |
| Weather Clock | `sensor.weather_clock_condition_ring_colors` | Condition |
| Weather Clock | `sensor.weather_clock_temperature_ring_colors` | Temperature |
| Weather Clock | `sensor.weather_clock_rain_ring_colors` | Rain |
| Sky Clock | `sensor.sky_clock_sun_ring_colors` | Sun |
| Sky Clock | `sensor.sky_clock_moon_ring_colors` | Moon Phase |
| Sky Clock | `sensor.sky_clock_moon_up_ring_colors` | Moon Up |
| Sky Clock | `sensor.sky_clock_sun_and_moon_ring_colors` | Sun and Moon |
| Sky Clock | `sensor.sky_clock_moon_light_ring_colors` | Moon Light |
| Sky Clock | `sensor.sky_clock_moon_position_ring_colors` | Moon Position |
| Sky Clock | `sensor.sky_clock_full_moon_ring_colors` | Full Moon |
| AdGuard Clock | `sensor.adguard_clock_ring_colors` | (only ring) |
| Holiday Clock | `sensor.holiday_clock_ring` | (only ring) |

All sensors update once a minute. The Weather Clock gets its forecast through the `weather.get_forecasts` action, which returns the Met.no integration's stored forecast, so this adds no extra requests to Met.no.

## Add the clock

When the clock is on WiFi, Home Assistant lists it as discovered under Settings > Devices & services. Select Configure and enter the `api_key`. The ring lights up within a minute.

The clock reads `sun.sun` itself for Auto Brightness. ESPHome devices may read Home Assistant entities without extra setup.

## When data is missing

- The packages are trigger-based template sensors, which keep their last value across Home Assistant restarts.
- If the source is unavailable, the colour sensor becomes unavailable. The clock keeps the last colours it drew and Ring Data Valid turns off.
- LEDs whose time is beyond the available data get `no_data_color`, black by default. On the Price Clock this is normal in the afternoon, before tomorrow's prices are published.

Next: [How the ring works](../guides/01-how-the-ring-works.md)
