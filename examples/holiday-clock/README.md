# Holiday Clock

Shows an animated theme on holidays and special days: fireworks that build up to midnight on New Year's Eve, a bonfire on Walpurgis Night, grave candles on All Saints' Day, candles and straw at Christmas. On other days the ring counts down to the next one.

Unlike the other examples, the clock draws the animation itself, 25 frames a second. Home Assistant decides which theme to show and with which colours. Colours can be changed in the package without installing new firmware.

## Files

| File | Goes to |
|---|---|
| [`esphome/holiday-clock.yaml`](esphome/holiday-clock.yaml) | ESPHome Device Builder, or `esphome run` |
| [`homeassistant/holiday_clock.yaml`](homeassistant/holiday_clock.yaml) | `/config/packages/holiday_clock.yaml` in Home Assistant |

## Data source

| Entity | Comes from |
|---|---|
| `calendar.sweden` | Holiday integration |

1. Settings > Devices & services > Add integration > Holiday. Pick your country.
2. Open the integration's options and tick the **de facto** category. Without it, Midsummer Eve, Christmas Eve and New Year's Eve are missing, because they are not public holidays.
3. Check the calendar's entity ID under Developer tools > States. It is named after the country, in Home Assistant's language. If it is not `calendar.sweden`, set `holiday_calendar` at the top of the package.

The package reads the next 38 days of the calendar once a minute with the `calendar.get_events` action. The Holiday integration has its holiday data built in, so this makes no requests outside Home Assistant.

Leave the **optional** category off. It adds half days such as "Day before Christmas Eve (from 2pm)", which have no theme.

## What the ring shows

| Day | Comes from | Theme |
|---|---|---|
| New Year's Eve, New Year's Day | Calendar | Rare sparkles in the afternoon. From 18:00, rockets climb from 6 and burst, more and more often after 23:00. The last minute fills the ring as a countdown, the last 10 seconds pulse. A white flash and a firework storm at midnight, calming down until 02:00 |
| Epiphany | Calendar | The star over Betlehem at 12 on a night blue ring. Three lights in gold, frankincense and myrrh walk up from 6, the star flares when they arrive |
| Shrove Tuesday | Package, 47 days before Easter | A semla: golden bun at the bottom, whipped cream on top, an almond line between, powdered sugar dusting down |
| Good Friday | Calendar | Black, with five deep red roses at 6 breathing very slowly |
| Holy Saturday, Easter Sunday, Easter Monday | Calendar | Pastel feather colours turning round the ring |
| Walpurgis Night (30 April) | Package | A bonfire at 6 throwing embers up the sides, under a pale spring evening sky |
| May Day | Calendar | Red banners marching round the ring in step |
| Ascension Day | Calendar | Sky blue light rising from 6 up to 12 on both sides |
| National Day | Calendar | Blue and yellow halves slowly turning, with a shimmer where they meet |
| Midsummer Eve, Midsummer Day | Calendar | Birch leaves in the wind, seven flowers in a wreath, and a warm light going round like the ring dance |
| Halloween (31 October) | Package | Dark, with smouldering lanterns, drifting cold lights and a slow red heartbeat. Now and then the ring goes black and something red rushes past |
| All Saints' Day | Calendar | Candles flickering at every hour mark, dark between, like lanterns on graves |
| Lucia (13 December) | Package | A crown of seven candles on the top half |
| Christmas Eve, Christmas Day, Second Day of Christmas | Calendar | Pine green with flickering candles, red apples, straw ornaments, straw glints and a star at 12 |

Holy Saturday is only in the calendar with the optional category. Pentecost has no theme; see [Add a day](#add-a-day) to give it one.

### Days that share a date

A day from the package gives way to a calendar holiday on the same date. Halloween has `from_hour: 18`, so when 31 October is All Saints' Day it shows the candles until 18:00 and Halloween after.

### Other days

`normal_day` sets what the ring shows on days without a theme:

| Value | Ring |
|---|---|
| `countdown` (default) | One LED per day left to the next themed day, clockwise from 12, in that day's accent colour. The last LED breathes. Shows nothing if the next one is more than `countdown_days` (at most 36) away |
| `glow` | Every LED in `glow_color` |
| `off` | Dark |

## Try a theme

The package adds `input_select.holiday_clock_preview`. Pick a theme there and the clock shows it at once; pick Auto to go back to the calendar. New Year in preview runs a three minute loop from 23:58:30 to 00:01:30, so the countdown and the midnight storm can be seen any day.

The sensor's attributes show what the package decided: `theme`, `holiday`, `next_holiday`, `next_date` and `days_left`.

## Line up with the face

Set `led_offset` and `clockwise` in the package for your clock, see [Time on the ring](../../docs/guides/02-time-on-the-ring.md#line-the-face-up-with-your-clock). The themes are placed on the face, so the star of Epiphany sits under 12 and the bonfire of Walpurgis Night under 6.

## Change colours

Each theme in `themes:` has a `pattern`, an `accent` used by the countdown, and a list of `colors`. The pattern uses the colours in this order:

| Pattern | Colours, in order |
|---|---|
| `newyear` | Firework colours, up to 10. The first is also the countdown fill |
| `epiphany` | Night, star, gold, frankincense, myrrh |
| `semla` | Cream, bun bottom, bun top, almond, sugar |
| `goodfriday` | Roses |
| `easter` | Colours that turn round the ring, up to 10 |
| `valborg` | Embers, flame, flame core, low sky, high sky, sparks |
| `mayday` | Banner, banner edge, gap |
| `ascension` | Sky, light |
| `national` | First half, second half |
| `midsummer` | Dark leaves, light leaves, dance light, then the seven flowers |
| `halloween` | Darkness, lanterns, first cold light, second cold light, blood red |
| `allsaints` | Candles |
| `lucia` | Candles, candle glow |
| `jul` | Pine, candles, apples, straw, star, glints |

The darkness in `epiphany`, `halloween` and `jul` is used as given, so keep those colours very dark. A pattern given fewer colours than it uses repeats the last one.

Several themes can share a pattern. For example, a second `newyear` theme with other colours can be used for another celebration.

## Add a day

A holiday from the calendar: add its event name to `holiday_names` with a theme. Use the name exactly as the calendar shows it under Developer tools > States, in `message`.

```yaml
      holiday_names:
        "Pentecost": ascension
```

A day the calendar does not have: add it to `extra_days`, either on a fixed date or a number of days from Easter Sunday.

```yaml
      extra_days:
        - name: "Cinnamon Bun Day"
          date: "10-04"
          theme: semla
```

After editing, reload with Developer tools > YAML > Template entities. A new option for the preview also needs the `input_select` options updated and a restart.

## What the clock receives

`sensor.holiday_clock_ring` is one line of text:

```
pattern|value|led_offset|clockwise|RRGGBB,RRGGBB,...
```

| Field | Meaning |
|---|---|
| `pattern` | One of the patterns above, or `countdown`, `glow` or `off` |
| `value` | Days left for `countdown`. 1 for a preview. 0 otherwise |
| `led_offset` | The LED under 12 o'clock |
| `clockwise` | 1 or 0 |
| colours | Up to 10 colours, comma separated |

For example `countdown|12|0|1|C00018` lights 12 LEDs in red, 12 days before Christmas Eve. If the sensor becomes unavailable or sends something the clock does not know, the clock keeps drawing the last theme it received.

## Things to know

- **Brightness:** the themes follow Ring Brightness, Auto Brightness and night hours like the other examples. A night that starts at 23 keeps the ring dark through midnight on New Year's Eve. For that night, set Night Start Hour and Night End Hour to the same hour, which turns night hours off, or turn Auto Brightness off.
- **New Year timing:** the countdown and the midnight flash use the clock's own time, which it gets from Home Assistant, so they land on the second.
- **Memory:** the animation keeps a fixed set of values and allocates no memory per frame. Watch Free Heap and Loop Time on the device page for the first day.

## Device

Besides the ring, the clock has Auto Brightness, night hours and diagnostics. See [Device entities](../../docs/reference/device-entities.md). Ring Data Valid is on when the clock has received a theme line with all five fields.
