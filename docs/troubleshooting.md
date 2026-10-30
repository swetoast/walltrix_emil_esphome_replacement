# Troubleshooting

## The ring is dark

Work through these in order.

1. **Is it night?** With Auto Brightness on, the ring is dark between Night Start Hour and Night End Hour. Turn Auto Brightness off and set Ring Brightness to 40 to test.
2. **Is the light on?** `light.<clock>_ring` must be on, at 100 % brightness, with the clock's ring effect selected (Price Ring, Weather Ring, Sky Ring or AdGuard Ring).
3. **Do the LEDs work?** Pick the Rainbow Test effect. If the ring stays dark, see [Rainbow Test is also dark](#rainbow-test-is-also-dark).
4. **Is there data?** Check `binary_sensor.<clock>_ring_data_valid`. If it is off, the colour sensor in Home Assistant has no valid value: see [Ring Data Valid is off](#ring-data-valid-is-off).
5. **Are the colours too dark?** At low Ring Brightness, dark colours such as `#001040` round down to nearly off. See [Colours](guides/03-colours.md#colours-that-do-not-look-right).

## Ring Data Valid is off

The clock has not received a full 216 character colour string.

- Developer tools > States: find the `*_ring_colors` sensor. It should be 216 hex characters.
- If it does not exist, the package was not loaded. Check that `configuration.yaml` loads packages and that you restarted. See [Home Assistant setup](getting-started/04-home-assistant.md).
- If it is `unavailable`, its data source is missing:
  - Price Clock: check `price_entity` exists and has a `today` attribute.
  - Weather Clock: check `weather_entity` exists. Met.no may name it something other than `weather.forecast_home`.
  - Sky Clock: the Moon ring needs the Moon integration (`sensor.moon_phase`).
  - AdGuard Clock: check `ratio_entity` exists. With two AdGuard Home servers, the second one's sensor ends in `_2`.
- Settings > System > Logs: template errors name the sensor and the line.
- Weather Clock and Sky Clock: check Ring Mode. Each mode reads its own sensor.

## Ring Data Age keeps rising

The colour sensor stopped changing. The ring keeps showing the last colours.

- Check the sensor's last update time in Developer tools > States.
- If Home Assistant is fine, check `binary_sensor.<clock>_status`. If the clock is disconnected, it restarts by itself after 15 minutes.

## Rainbow Test is also dark

- Check the USB power supply. A weak supply can run the ESP but not the LEDs.
- The config must have `pin: GPIO12` and `method: type: bit_bang`. Other pins and methods do not drive this ring.
- Check `binary_sensor.<clock>_status`. If the clock is offline, nothing it is told reaches it.

## Colours are swapped

Red shows as green or the reverse: the LED colour order setting is wrong for your unit. In the device config, change

```yaml
    type: GRB
```

to `RGB` and install. If colours are still wrong, try `BRG`.

## The ring looks rotated

The package's `led_offset` or `clockwise` does not match your clock. Use the LED Index Test effect as described in [Time on the ring](guides/02-time-on-the-ring.md#line-the-face-up-with-your-clock).

## The clock is not discovered

- Check `wifi_ssid` and `wifi_password` in `secrets.yaml`.
- If the clock cannot join WiFi it opens the `Price Clock Setup` or `Weather Clock Setup` hotspot (`Sky Clock Setup` and `AdGuard Clock Setup` for the other two). Connect with `ap_password` and enter WiFi details there.
- The ESP8266 only supports 2.4 GHz WiFi.

## Home Assistant asks for an encryption key

Enter `api_key` from `secrets.yaml`. It must be exactly the key the clock was built with.

## A wireless update is refused

- Check that `api_key` in `secrets.yaml` has not changed since the last install. OTA uses the same key.
- If it still fails, install once over USB as in [First flash](getting-started/03-first-flash.md). Updates after that work over WiFi again.

## The clock keeps restarting

Check `sensor.<clock>_last_reset_reason`.

- Repeated crashes at boot make the clock start in safe mode, where it only waits for an update. Install a working config over WiFi.
- Falling Largest Free Block or rising Heap Fragmentation before each restart points to memory pressure. If you added your own lambdas, check that they do not create strings or other objects every second.
