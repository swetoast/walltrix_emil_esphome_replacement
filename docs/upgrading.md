# Upgrading from the earlier layout

The earlier version of this repository had `config/`, `homeassistant/` and a single `readme.md`. This page lists what changed and what to do with a clock that already runs an older build.

## What moved

| Before | Now |
|---|---|
| `config/<device>.yaml` | `examples/price-clock/esphome/price-clock.yaml` and `examples/weather-clock/esphome/weather-clock.yaml` |
| `config/secrets.yaml` | `examples/secrets.example.yaml`. Your real `secrets.yaml` is ignored by git. |
| `homeassistant/ha_*_ring.yaml` | `examples/*/homeassistant/*.yaml`, now Home Assistant packages |
| `homeassistant/automation.yaml` | Removed. Brightness runs on the clock (Auto Brightness). |
| `readme.md` | `README.md` plus the chapters in `docs/` |

## New names

The examples now use English names throughout:

| | Price Clock | Weather Clock |
|---|---|---|
| ESPHome `name` | `price-clock` | `weather-clock` |
| Friendly name | Price Clock | Weather Clock |
| Colour sensors | `sensor.price_clock_ring_colors` | `sensor.weather_clock_condition_ring_colors`, `_temperature_`, `_rain_`, `_sun_` |
| Ring light | `light.price_clock_ring` | `light.weather_clock_ring` |
| Hotspot | Price Clock Setup | Weather Clock Setup |

A new `name` makes Home Assistant see a new device with new entity IDs. Dashboards and automations that used the old entities need updating.

To keep your existing device and entity IDs instead, set the old values under `substitutions:` before installing:

```yaml
substitutions:
  name: your-old-device-name
  friendly_name: "Your Old Friendly Name"
```

and point the clock's `homeassistant` text sensor at the colour sensor name your package creates.

## Step by step

1. **Remove the old templates.** Delete the old ring `template:` blocks from `configuration.yaml`. Leaving them in next to the packages gives duplicate sensors.
2. **Remove the old automation.** If you imported the old adaptive brightness automation, delete it. It would keep overriding the clock's own Auto Brightness.
3. **Install the package** as in [Home Assistant setup](getting-started/04-home-assistant.md).
4. **Install the new firmware.** See [OTA updates](#ota-updates) below.
5. **Clean up.** Old entities that no longer exist show as unavailable. Remove them under Settings > Entities.

## OTA updates

Older builds protected OTA with `password: !secret ota_password`. The new configs use

```yaml
ota:
  - platform: esphome
    encryption:
```

which reuses the API encryption key. A clock still running the password build may refuse the first wireless install of the new build. If it does, install once over USB as in [First flash](getting-started/03-first-flash.md). Every update after that works over WiFi. You can then delete `ota_password` from `secrets.yaml`.

## Weather Clock data source

The earlier Weather Clock read a custom `sensor.weather_hourly` with a `forecast` attribute. The new package calls `weather.get_forecasts` on `weather.forecast_home` directly, so that helper sensor is no longer needed. The condition colours are unchanged.

## Behaviour that stayed the same

With default settings, the Price Clock ring looks the same as before: 15 minute slots, the current slot first at full brightness, the rest at 55 percent, the same colour scale. Each LED can differ from the old output by at most 1 step out of 255 per colour channel, from rounding. The Weather Clock condition ring gives the same output as before for the same forecast.
