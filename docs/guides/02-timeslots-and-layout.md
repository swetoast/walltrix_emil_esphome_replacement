# Time slots and LED layout

Before a package can colour an LED, it gives the LED a time. The data shown on that LED is the data for that time. Two layouts decide how LEDs get their times.

| Layout | LED 0 means | Each LED covers | Span | Settings used |
|---|---|---|---|---|
| `now` (default) | The current slot | `slot_minutes` | 36 x `slot_minutes` | `slot_minutes` |
| `clock` | Whatever time the hour hand points at | 20 minutes | 12 hours | `led_offset`, `clockwise` |

Set the layout at the top of the package:

```yaml
    variables:
      layout: now
```

## The `now` layout

LED 0 is the slot you are in now, LED 1 the next slot, and so on around the ring.

```
LED time = start of the current slot + LED number x slot_minutes
```

Slots start on round clock times. With `slot_minutes: 15` they start at :00, :15, :30 and :45, so at 07:23 LED 0 covers 07:15 to 07:30, LED 1 covers 07:30 to 07:45, and LED 35 covers 16:00 to 16:15.

### Choosing `slot_minutes`

Use a value that divides an hour evenly:

| `slot_minutes` | Span of 36 LEDs | Good for |
|---|---|---|
| 5 | 3 hours | Very short term |
| 10 | 6 hours | |
| 15 | 9 hours | Price Clock default, matches 15 minute price slots |
| 20 | 12 hours | Half a day |
| 30 | 18 hours | |
| 60 | 36 hours | Weather Clock default, matches the hourly forecast |

Other values work but slots then stop lining up with round clock times.

### What an LED shows when slots and data differ

An LED shows the data at the start of its slot. It does not average.

- **Price Clock with `slot_minutes: 60`**: each LED shows the price of the first 15 minutes of its hour, not the hourly average.
- **Weather Clock with `slot_minutes: 15`**: four LEDs in a row share one forecast hour and show the same colour.
- **Sun ring**: an LED takes the part of the day (night, morning, day, evening) at the start of its slot. With 60 minute slots, sunrise at 07:58 shows on the 08:00 LED.

### Example: Price Clock covering 12 hours

```yaml
      layout: now
      slot_minutes: 20
```

Each LED now shows the price at the start of its 20 minute slot, covering 12 hours ahead.

## The `clock` layout

Each LED shows what happens when the hour hand reaches it. The ring always covers the next 12 hours, read like the clock face itself. At 07:23 the LED at the 7:20 mark shows now, the LED at the 9 shows 09:00, and the LED at the 7, one step behind now, shows 19:00.

- `slot_minutes` is ignored. Each LED is always 20 minutes, three per hour mark.
- The LED the hour hand is on counts as now, so it is not dimmed.

For this to line up, the package must know where LED 0 is and which way the numbering runs.

| Setting | Meaning |
|---|---|
| `led_offset` | Number of the LED under 12 o'clock |
| `clockwise` | `true` if LED numbers increase clockwise, `false` if they increase counter-clockwise |

### Find LED 0 and the direction

1. In Home Assistant, open the clock's Ring light and pick the LED Index Test effect.
2. Three LEDs light up: white is LED 0, red is LED 1, green is LED 2.
3. Note the numeral the white LED sits under, and whether red is clockwise from white.

Then look up the settings. `h` is the numeral under the white LED, with 12 counted as 0:

| Red LED is | `clockwise` | `led_offset` |
|---|---|---|
| Clockwise from white | `true` | `(36 - 3 x h) mod 36` |
| Counter-clockwise from white | `false` | `3 x h` |

Common cases:

| White LED under | Red LED is | `clockwise` | `led_offset` |
|---|---|---|---|
| 12 | Clockwise | `true` | 0 |
| 3 | Clockwise | `true` | 27 |
| 6 | Clockwise | `true` | 18 |
| 9 | Clockwise | `true` | 9 |
| 12 | Counter-clockwise | `false` | 0 |
| 3 | Counter-clockwise | `false` | 9 |
| 6 | Counter-clockwise | `false` | 18 |
| 9 | Counter-clockwise | `false` | 27 |

If the white LED sits between two numerals, use the nearest one and check: after reloading, the LED nearest the hour hand should be the bright one.

Switch the effect back to Price Ring or Weather Ring when done.

### Example: Weather Clock on the clock face

```yaml
      layout: clock
      led_offset: 27
      clockwise: true
```

## After changing a setting

Developer tools > YAML > Template entities. The new layout shows on the ring within a minute.

Next: [Colours](03-colours.md)
