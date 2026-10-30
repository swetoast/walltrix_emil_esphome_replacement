# Price Clock

Shows the electricity spot price for the coming 60 minutes, one 15 minute price per quarter of the face. Cheap prices are blue, expensive ones pink.

## Files

| File | Goes to |
|---|---|
| [`esphome/price-clock.yaml`](esphome/price-clock.yaml) | ESPHome Device Builder, or `esphome run` |
| [`homeassistant/price_clock.yaml`](homeassistant/price_clock.yaml) | `/config/packages/price_clock.yaml` in Home Assistant |

## What the ring shows

The ring is 60 minutes, read like the minute hand. One 15 minute price is 9 LEDs:

| On the face | LEDs | Price |
|---|---|---|
| 12 to 3 | 1 to 9 | :00 to :15 |
| 3 to 6 | 10 to 18 | :15 to :30 |
| 6 to 9 | 19 to 27 | :30 to :45 |
| 9 to 12 | 28 to 36 | :45 to :00 |

- The current 15 minutes are at full brightness, the rest at 55 percent.
- A quarter that has ended shows the same quarter of the next hour, so the ring always holds the coming 60 minutes.
- For the quarters to start at 12 o'clock, set `led_offset` and `clockwise` for your clock, see [Time on the ring](../../docs/guides/02-time-on-the-ring.md#line-the-face-up-with-your-clock).

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
| 30 minutes per 18 LEDs, average of two prices | `interval_minutes: 30` |
| 12 hours, 1 hour per 3 LEDs, average of four prices | `layout: hours`, `interval_minutes: 60` |
| Other combinations | See [Time on the ring](../../docs/guides/02-time-on-the-ring.md#intervals-and-leds) |
| Different price range | Edit the values in `price_colors` |
| No highlight on now | `dim_others: 1.0` |
| Another price area | Point `price_entity` at its sensor, for example the SE4 one |

## Device

Besides the ring, the clock has Auto Brightness, night hours and diagnostics. See [Device entities](../../docs/reference/device-entities.md).
