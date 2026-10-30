# Device entities

Every entity the firmware creates. Entity IDs are prefixed with the device's friendly name: `price_clock_`, `weather_clock_`, `sky_clock_`, `adguard_clock_` or `holiday_clock_`. The tables use `<clock>` for that prefix.

## Controls

| Entity | Type | Range or options | Default | Saved | Description |
|---|---|---|---|---|---|
| `light.<clock>_ring` | Light | on/off, brightness, effect | on, 100 %, the clock's ring effect | no | The LED ring. Always turns on at boot. |
| `number.<clock>_ring_brightness` | Number | 0 to 90 | 40 | yes | Scales colours by value / 255. Set by Auto Brightness when it is on. |
| `switch.<clock>_auto_brightness` | Switch | on/off | on | yes | Follows the sun and applies night hours |
| `number.<clock>_night_start_hour` | Number | 0 to 23 | 23 | yes | Ring dark from this hour |
| `number.<clock>_night_end_hour` | Number | 0 to 23 | 6 | yes | Ring lights from this hour |
| `number.<clock>_auto_brightness_min` | Number | 0 to 90 | 10 | yes | Ring Brightness in the dark |
| `number.<clock>_auto_brightness_max` | Number | 0 to 90 | 90 | yes | Ring Brightness in full daylight |
| `select.weather_clock_ring_mode` | Select | Condition, Temperature, Rain | Condition | yes | Weather Clock only. Which ring to show. |
| `select.sky_clock_ring_mode` | Select | Sun, Moon Phase, Moon Up, Sun and Moon, Moon Light, Moon Position, Full Moon | Sun | yes | Sky Clock only. Which ring to show. |
| `button.<clock>_restart` | Button | | | | Restarts the clock |
| `button.<clock>_restart_safe_mode` | Button | | | | Restarts into safe mode, which only waits for an OTA update. Use it if a bad update keeps crashing the clock. |

Saved values survive a restart. They survive a power cut only with `restore_from_flash: true`, see [Brightness and night mode](../guides/04-brightness-and-night.md#settings-after-a-power-cut).

## Light effects

| Effect | Clock | What it shows |
|---|---|---|
| Price Ring | Price Clock | Colours from `sensor.price_clock_ring_colors` |
| Weather Ring | Weather Clock | Colours from the sensor chosen by Ring Mode |
| Sky Ring | Sky Clock | Colours from the sensor chosen by Ring Mode |
| AdGuard Ring | AdGuard Clock | Colours from `sensor.adguard_clock_ring_colors` |
| Holiday Ring | Holiday Clock | The theme named by `sensor.holiday_clock_ring`, animated at 25 frames a second |
| Rainbow Test | All | Moving rainbow on all LEDs, for checking the hardware |
| LED Index Test | All | LED 0 white, LED 1 red, LED 2 green, rest off. For finding `led_offset` and `clockwise` |

## Ring data

| Entity | Unit | Description |
|---|---|---|
| `binary_sensor.<clock>_ring_data_valid` | on/off | On when the active colour sensor holds a full 216 character string. Holiday Clock: on when the theme line has all five fields |
| `sensor.<clock>_ring_data_age` | min | Minutes since the active colour sensor last actually changed. A reconnect that resends the same colours does not reset it. Unknown until the first data arrives. |
| `sensor.<clock>_ring_power_estimate` | W | Estimated LED power from the colours being shown, assuming about 1 mA idle per LED, 20 mA per colour channel at full and a 5 V supply. Use it for trends, not as a measurement. |

Ring Data Age climbing past a few minutes means the template sensor in Home Assistant stopped updating. The ring keeps showing its last colours meanwhile.

## Network and system

| Entity | Unit | Description |
|---|---|---|
| `binary_sensor.<clock>_status` | | Connected to Home Assistant |
| `sensor.<clock>_wifi_signal` | dBm | WiFi signal strength |
| `sensor.<clock>_wifi_signal_percent` | % | Same, as 0 to 100 (2 x (dBm + 100)) |
| `sensor.<clock>_ip_address` | | |
| `sensor.<clock>_connected_ssid` | | WiFi network name |
| `sensor.<clock>_connected_bssid` | | Address of the access point in use |
| `sensor.<clock>_mac_address` | | |
| `sensor.<clock>_uptime` | s | Seconds since boot |
| `sensor.<clock>_uptime_readable` | | Uptime as text |
| `sensor.<clock>_esphome_version` | | Firmware ESPHome version |
| `sensor.<clock>_last_reset_reason` | | Why the clock last restarted |

## Memory

| Entity | Unit | Description |
|---|---|---|
| `sensor.<clock>_free_heap` | B | Free RAM |
| `sensor.<clock>_largest_free_block` | B | Largest single free block of RAM |
| `sensor.<clock>_heap_fragmentation` | % | How scattered the free RAM is |
| `sensor.<clock>_loop_time` | ms | Main loop time as reported by ESPHome's debug component. High values mean something is blocking the clock. |

On an ESP8266, a steadily falling Largest Free Block or rising fragmentation over days points to a memory leak and eventually a crash. The examples draw the ring without allocating memory each second, so these should stay flat.

## Built-in safety nets

These are ESPHome defaults and need no configuration:

- If the clock cannot reach Home Assistant for 15 minutes, it restarts (`api: reboot_timeout`).
- If it cannot join WiFi for 15 minutes, it restarts (`wifi: reboot_timeout`).
- If it crashes repeatedly at boot, it starts in safe mode and waits for an OTA update.
