# AdGuard Clock

Shows how much of your network's DNS traffic AdGuard Home blocks.

## Files

| File | Goes to |
|---|---|
| [`esphome/adguard-clock.yaml`](esphome/adguard-clock.yaml) | ESPHome Device Builder, or `esphome run` |
| [`homeassistant/adguard_clock.yaml`](homeassistant/adguard_clock.yaml) | `/config/packages/adguard_clock.yaml` in Home Assistant |

## Data source

| Entity | Comes from |
|---|---|
| `sensor.adguard_home_dns_queries_blocked_ratio` | AdGuard Home integration |

Add the integration under Settings > Devices & services > Add integration > AdGuard Home. The sensor's value is the share of DNS queries blocked, in percent.

With more than one AdGuard Home server, Home Assistant adds `_2`, `_3` and so on to the second and later servers' sensors. Set `ratio_entity` to the one you want.

## What the ring shows

The full ring is 100 percent of the DNS queries:

- Blocked queries fill the ring clockwise from 12 o'clock in pink `#FF0080`.
- Allowed queries fill the rest in ice blue `#00BFFF`.

| Blocked | Blocked LEDs | On the face |
|---|---|---|
| 0 percent | 0 | |
| 7.89 percent | 3 | 12 to 1 |
| 25 percent | 9 | 12 to 3 |
| 50 percent | 18 | 12 to 6 |
| 100 percent | 36 | All |

One LED is 1/36 of the queries, about 2.8 percent. The number of blocked LEDs is the blocked share of 36, rounded: 7.89 percent of 36 is 2.84, so 3 LEDs.

The ring updates once a minute. If AdGuard Home is unreachable, the clock keeps the last colours.

## Line up with the face

For the blocked share to start at 12 o'clock, set `led_offset` and `clockwise` for your clock, see [Time on the ring](../../docs/guides/02-time-on-the-ring.md#line-the-face-up-with-your-clock).

## Common changes

| Want | Change |
|---|---|
| Other colours | `blocked_color` and `allowed_color` in `variables:`, see [Colours](../../docs/guides/03-colours.md) |
| A second AdGuard Home server | `ratio_entity: sensor.adguard_home_dns_queries_blocked_ratio_2` |

## Device

Besides the ring, the clock has Auto Brightness, night hours and diagnostics. See [Device entities](../../docs/reference/device-entities.md).
