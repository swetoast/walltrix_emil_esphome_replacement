# Time on the ring

The ring is read like the clock face. Two settings decide what it shows: which hand the ring follows, and how long one interval is.

## The two faces

| `layout` | The full ring is | One quarter (12 to 3) is | Read it like |
|---|---|---|---|
| `minutes` | 60 minutes | 15 minutes | The minute hand |
| `hours` | 12 hours | 3 hours | The hour hand |

The ring has 36 LEDs, so one quarter is 9 LEDs.

## Intervals and LEDs

`interval_minutes` sets how long one interval is. Each interval lights a block of LEDs starting at its place on the face.

| `layout` | `interval_minutes` | Interval | LEDs per interval | On the face | Intervals on the ring |
|---|---|---|---|---|---|
| `minutes` | 15 | 15 minutes | 9 | 12 to 3 | 4 |
| `minutes` | 30 | 30 minutes | 18 | 12 to 6 | 2 |
| `hours` | 60 | 1 hour | 3 | 12 to 1 | 12 |
| `hours` | 120 | 2 hours | 6 | 12 to 2 | 6 |
| `hours` | 180 | 3 hours | 9 | 12 to 3 | 4 |
| `hours` | 360 | 6 hours | 18 | 12 to 6 | 2 |

Use only these combinations. Other values do not divide the ring evenly.

The examples use:

| Example | `layout` | `interval_minutes` | LEDs per interval |
|---|---|---|---|
| Price Clock | `minutes` | 15 | 9 |
| Weather Clock | `hours` | 60 | 3 |
| Sky Clock, Sun ring | `hours` | 60 | 3 |

## Which interval an LED shows

Every LED shows the next interval at its place on the face that has not ended yet.

Price Clock at 07:23, `minutes` face, 15 minute intervals:

| On the face | LEDs | Shows | |
|---|---|---|---|
| 12 to 3 | 1 to 9 | 08:00 to 08:15 | 07:00 to 07:15 has ended, so the next hour |
| 3 to 6 | 10 to 18 | 07:15 to 07:30 | Current interval, full brightness |
| 6 to 9 | 19 to 27 | 07:30 to 07:45 | |
| 9 to 12 | 28 to 36 | 07:45 to 08:00 | |

LEDs here are counted 1 to 36 clockwise from 12 o'clock.

Weather Clock at 07:23, `hours` face, 1 hour intervals:

| On the face | Shows | |
|---|---|---|
| 7 to 8 | 07:00 to 08:00 | Current interval, full brightness |
| 8 to 9 | 08:00 to 09:00 | |
| ... | ... | |
| 6 to 7 | 18:00 to 19:00 | 06:00 to 07:00 has ended, so the evening |

So the ring always holds the coming 60 minutes (`minutes` face) or the coming 12 hours (`hours` face).

All LEDs of the current interval are at full brightness. All other LEDs are multiplied by `dim_others`.

## Data that does not match the interval

| Data | Interval | What the LEDs show |
|---|---|---|
| 15 minute prices | 15 minutes | The price |
| 15 minute prices | 30 minutes or longer | The average of the prices inside the interval |
| Hourly forecast | 1 hour | The forecast hour |
| Hourly forecast | 2, 3 or 6 hours | The forecast hour the interval starts in |
| Hourly forecast | 15 or 30 minutes | The forecast hour the interval falls in |
| Sun | any | The part of the day at the start of the interval |

For the current interval, the forecast and the sun are read at the current time instead of the start. Met.no's hourly forecast usually starts at the next full hour; the current hour then uses that first forecast hour, so it does not go dark.

An interval with no data gets `no_data_color`, black by default. On the Price Clock this happens late in the evening, before tomorrow's prices are published.

## Line the face up with your clock

The package must know which LED sits under 12 o'clock and which way the LEDs are numbered.

| Setting | Meaning |
|---|---|
| `led_offset` | Number of the LED under 12 o'clock, counting from 0 |
| `clockwise` | `true` if LED numbers go up clockwise, `false` if they go up counter-clockwise |

### Find LED 0 and the direction

1. In Home Assistant, open the clock's Ring light and pick the LED Index Test effect.
2. Three LEDs light up: white is LED 0, red is LED 1, green is LED 2.
3. Note the numeral the white LED sits under, and whether red is clockwise from white.
4. Look up the settings below.
5. Switch the effect back to the clock's ring effect (Price Ring, Weather Ring, Sky Ring or AdGuard Ring).

| White LED under | Red LED is | `clockwise` | `led_offset` |
|---|---|---|---|
| 12 | Clockwise from white | `true` | 0 |
| 3 | Clockwise from white | `true` | 27 |
| 6 | Clockwise from white | `true` | 18 |
| 9 | Clockwise from white | `true` | 9 |
| 12 | Counter-clockwise from white | `false` | 0 |
| 3 | Counter-clockwise from white | `false` | 9 |
| 6 | Counter-clockwise from white | `false` | 18 |
| 9 | Counter-clockwise from white | `false` | 27 |

For any other numeral `h` (12 counts as 0): clockwise, `led_offset` is `(36 - 3 x h) mod 36`; counter-clockwise, `led_offset` is `3 x h`.

## Change a setting

Edit the `variables:` section at the top of the package:

```yaml
      layout: hours
      interval_minutes: 120
      led_offset: 0
      clockwise: true
```

Then reload with Developer tools > YAML > Template entities. The ring changes within a minute.

## Rings that do not show time

The Sky Clock's Moon ring and the AdGuard Clock use the same 36 LEDs, but not for time.

| Ring | The full ring is | One quarter (9 LEDs) is | One LED is |
|---|---|---|---|
| Sky Clock, Moon | The whole moon | A quarter of the moon | |
| AdGuard Clock | 100 percent of the DNS queries | 25 percent | 1/36 of the queries |

They use `led_offset` and `clockwise` the same way, so 12 o'clock is the start of the moon and the start of the blocked share. The Sky Clock's Sun ring shows time like the Weather Clock: 12 hours, 3 LEDs per hour. See the [Sky Clock](../../examples/sky-clock/README.md) and [AdGuard Clock](../../examples/adguard-clock/README.md) READMEs.

Next: [Colours](03-colours.md)
