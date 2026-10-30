# How the ring works

The work is split in two. Home Assistant decides what each LED shows. The clock only draws it.

```
Home Assistant                                       Clock (ESPHome)
--------------                                       ---------------
data source (price, forecast, sun)
        |
        v
package template sensor, every minute
  1. give each LED its interval    (time on the ring)
  2. look up the data for it
  3. turn the value into a colour  (colours)
  4. dim LEDs outside the current interval
        |
        v
216 character text  ---------------------------->   split into 36 colours
"RRGGBB" x 36                                        scale by Ring Brightness
                                                     draw on LEDs 0 to 35
```

Keeping the logic in Home Assistant means you change colours, intervals or data source by editing a package and reloading template entities. The firmware stays the same.

## The colour string

The sensor's state is 216 characters: 36 colours of 6 hexadecimal digits, one per LED, LED 0 first.

```
00BFFF 0070FF 0040FF ... FF0040
LED 0  LED 1  LED 2      LED 35
```

Spaces are shown here for reading only; the real string has none. Each 6 digit block is `RRGGBB`: red, green and blue from `00` (off) to `FF` (full). `FF0000` is red, `00FF00` green, `0000FF` blue, `FFFFFF` white, `000000` off. Upper and lower case both work.

Home Assistant allows a state of up to 255 characters, so 216 fits.

## What the clock does with it

Every second the clock's ring effect (Price Ring, Weather Ring, Sky Ring or AdGuard Ring):

1. Checks the string is at least 216 characters. If not (for example `unavailable`), it changes nothing and the LEDs keep their last colours.
2. Splits it into 36 colours.
3. Multiplies every channel by `Ring Brightness / 255`.
4. Writes the result to the LEDs.

Ring Brightness goes from 0 to 90, so the brightest the ring gets is 90/255, about 35 percent of each colour. Full WS2812 brightness is too bright for a wall clock. See [Brightness and night mode](04-brightness-and-night.md).

## Three kinds of setting

Every package starts with a `variables:` section. The settings fall into three groups, each with its own chapter:

| Group | Settings | Chapter |
|---|---|---|
| Time | `layout`, `interval_minutes`, `led_offset`, `clockwise` | [Time on the ring](02-time-on-the-ring.md) |
| Colour | `price_colors`, `temperature_colors`, `rain_colors`, `condition_colors`, `sun_colors`, `snow_color`, `no_data_color`, `unknown_condition_color` | [Colours](03-colours.md) |
| Emphasis | `dim_others` | [Colours](03-colours.md#highlighting-now) |

All settings in one table: [Package settings](../reference/package-settings.md).

Next: [Time on the ring](02-time-on-the-ring.md)
