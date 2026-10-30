# Price Clock

Shows the electricity spot price for the coming hours. Cheap periods are blue, expensive ones pink, so you can see at a glance when to run the dishwasher.

## Files

| File | Goes to |
|---|---|
| [`esphome/price-clock.yaml`](esphome/price-clock.yaml) | ESPHome Device Builder, or `esphome run` |
| [`homeassistant/price_clock.yaml`](homeassistant/price_clock.yaml) | `/config/packages/price_clock.yaml` in Home Assistant |

## What the ring shows

With the default settings:

- LED 0 is the current 15 minute price slot, at full brightness.
- LEDs 1 to 35 are the following 35 slots, dimmed to 55 percent.
- Together they cover the next 9 hours.
- LEDs after the last known price stay off. In the afternoon, before tomorrow's prices are published, the end of the ring can be dark.

| Price (öre/kWh) | Colour |
|---|---|
| 0 or below | Ice blue `#00BFFF` |
| 25 | Blue `#0040FF` |
| 50 | Purple `#8000FF` |
| 75 | Magenta `#FF00FF` |
| 100 or above | Hot pink `#FF0040` |

Prices in between are blended. The full scale has 9 steps, see [Colours](../../docs/guides/03-colours.md#gradient-lists).

## Data source

`price_entity` must point to a sensor with two attributes, `today` and `tomorrow`, each a list of slots like:

```yaml
- time_start: "2026-10-30T07:15:00+01:00"
  time_end: "2026-10-30T07:30:00+01:00"
  SEK_per_kWh: 0.4231
```

The default, `sensor.swedish_spot_price_elpris_se3_forecast`, is the SE3 forecast sensor of the Swedish Spot Price integration. Another price integration works as long as it provides this shape; otherwise adapt the three field names in the template.

`tomorrow` may be empty or missing. Those LEDs then use `no_data_color`.

## Common changes

| Want | Change |
|---|---|
| Cover 12 hours | `slot_minutes: 20` |
| Cover 36 hours with hourly LEDs | `slot_minutes: 60` (each LED shows the first 15 minutes of its hour) |
| Read the ring like the clock face | `layout: clock` plus `led_offset` and `clockwise`, see [Time slots and LED layout](../../docs/guides/02-timeslots-and-layout.md#the-clock-layout) |
| Different price range | Edit the values in `price_colors` |
| No highlight on now | `dim_others: 1.0` |
| Another price area | Point `price_entity` at its sensor, for example the SE4 one |

## Device

Besides the ring, the clock has Auto Brightness, night hours and diagnostics. See [Device entities](../../docs/reference/device-entities.md).
