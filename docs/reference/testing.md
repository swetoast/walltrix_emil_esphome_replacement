# Testing templates offline

`tests/check_packages.py` renders the example packages with made-up prices, forecasts, sun times and holidays, without Home Assistant. Use it after editing colours or settings to catch mistakes before reloading Home Assistant.

## Run it

From the repository root:

```bash
pip install jinja2 pyyaml
python tests/check_packages.py
```

In a terminal with colour support, each ring is drawn as a row of 36 coloured blocks, followed by the colour codes.

## What it checks

| Scenario | Expected |
|---|---|
| Both packages, every ring, every allowed `layout` and `interval_minutes` | 216 hex characters, and each interval's LEDs (9, 18, 3, 6, 9 or 18) are one colour |
| Price Clock default at 07:23 | 12 to 3 is 08:00, 3 to 6 is 07:15 and the only bright quarter, 6 to 9 is 07:30, 9 to 12 is 07:45 |
| Price Clock with 30 minutes at 07:23 | 12 to 6 is the average of 07:00 and 07:15, 6 to 12 the average of 07:30 and 07:45 |
| Price Clock at 23:50 without tomorrow's prices | 12 to 3 (00:00) uses `no_data_color` |
| Price Clock without its price sensor | Sensor unavailable |
| Weather Clock default at 07:23 | The 3 LEDs from the 7 to the 8 are 07:00 and bright, the 3 from the 8 to the 9 are 08:00 and dimmed |
| Weather Clock when the forecast starts at the next hour | The current hour does not go dark |
| Weather Clock with only 5 forecast hours | 18:00 (6 to 7) uses `no_data_color` |
| Weather Clock when the forecast call failed | All three rings unavailable |
| Sky Clock Sun ring, every allowed `layout` and `interval_minutes` | Each interval's LEDs are one colour |
| Sky Clock Sun ring at 07:23 | The 7 is morning and bright, the 8 and the 4 are day, the 5 is evening, the 6 is night |
| Sky Clock, all 8 moon phases | 0, 9, 18, 27 or 36 LEDs lit, from the right place on the face |
| Sky Clock without `sensor.moon_phase` | Moon Phase ring unavailable |
| Sky Clock moon rings at 10:59 (moonset 13:38, moonrise 18:24) | Moon Up: 10 to 13 up, 14 to 18 down, 19 to 21 up. Sun and Moon: 10:00 both, 14:00 sun, 17:00 neither, 19:00 moon. Moon Light: 77.62 percent = 28 LEDs. Moon Position: 299.48 degrees at the 10. Full Moon: 26 LEDs |
| Sky Clock without the moon details sensor | The five moon detail rings unavailable |
| AdGuard Clock at 0, 7.89, 25, 50 and 100 percent | 0, 3, 9, 18 and 36 blocked LEDs, the rest allowed |
| AdGuard Clock without AdGuard Home | Sensor unavailable |
| Holiday Clock on 30 October, 1 December and 13 December | One LED left to All Saints' Day, 12 LEDs to Lucia in her accent colour, then Lucia |
| Holiday Clock on 31 October at 12:00 and 19:00 | All Saints' Day by day, Halloween from 18:00 |
| Holiday Clock on Christmas Eve, New Year's Eve, Good Friday, Walpurgis Night and Shrove Tuesday 2027 | The matching theme. Shrove Tuesday falls 47 days before Easter Sunday |
| Holiday Clock with Swedish event names | Same themes as with English names |
| Holiday Clock preview, every theme | A well formed line with value 1 |
| Holiday Clock in July, with `led_offset` 5 and anticlockwise, and with `normal_day: glow` | `off\|0\|5\|0\|000000`, and `glow\|0\|0\|1\|201810` |
| Holiday Clock without the calendar | Sensor unavailable |

The script exits with an error if any check fails.

## Limits

`tests/ha_template_sim.py` is a small stand-in for Home Assistant's template engine. It implements only the functions the packages use (`now`, `today_at`, `state_attr`, `states`, `is_number`, `as_timestamp`, `strptime`, `timedelta`, `int` with base, `float` with default), runs `variables` steps in a package's actions, and mimics how Home Assistant turns rendered variables into numbers and lists. Passing here means the templates are logically right. Home Assistant is still the final check: after installing, look at the sensors in Developer tools > States.

## Trying your own data

Edit `NOW`, `price_slots()`, `forecast()`, `sun_attributes()` or `HOLIDAYS` in `check_packages.py` to try other situations, for example negative prices, a heat wave or midsummer sun times.
