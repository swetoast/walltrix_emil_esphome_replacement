# Testing templates offline

`tests/check_packages.py` renders both example packages with made-up prices, forecasts and sun times, without Home Assistant. Use it after editing colours or settings to catch mistakes before reloading Home Assistant.

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
| Weather Clock when the forecast call failed | Forecast rings unavailable, Sun ring still works |

The script exits with an error if any check fails.

## Limits

`tests/ha_template_sim.py` is a small stand-in for Home Assistant's template engine. It implements only the functions the packages use (`now`, `state_attr`, `states`, `is_number`, `as_timestamp`, `int` with base, `float` with default) and mimics how Home Assistant turns rendered variables into numbers. Passing here means the templates are logically right. Home Assistant is still the final check: after installing, look at the sensors in Developer tools > States.

## Trying your own data

Edit `NOW`, `price_slots()`, `forecast()` or `sun_attributes()` in `check_packages.py` to try other situations, for example negative prices, a heat wave or midsummer sun times.
