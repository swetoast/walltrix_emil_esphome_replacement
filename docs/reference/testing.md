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
| Price Clock, `now` and `clock` layouts | 216 hex characters |
| Price Clock in the evening without tomorrow's prices | LEDs past the last price use `no_data_color` |
| Price Clock without its price sensor | Sensor unavailable |
| Weather Clock, all four rings, `now`, `clock` and 15 minute slots | 216 hex characters each |
| Weather Clock with only 10 forecast hours | LEDs past the forecast use `no_data_color` |
| Weather Clock when the forecast call failed | Forecast rings unavailable, Sun ring still works |

The script exits with an error if any check fails.

## Limits

`tests/ha_template_sim.py` is a small stand-in for Home Assistant's template engine. It implements only the functions the packages use (`now`, `state_attr`, `states`, `is_number`, `as_timestamp`, `int` with base, `float` with default) and mimics how Home Assistant turns rendered variables into numbers. Passing here means the templates are logically right. Home Assistant is still the final check: after installing, look at the sensors in Developer tools > States.

## Trying your own data

Edit `NOW`, `price_slots()`, `forecast()` or `sun_attributes()` in `check_packages.py` to try other situations, for example negative prices, a heat wave or midsummer sun times.
