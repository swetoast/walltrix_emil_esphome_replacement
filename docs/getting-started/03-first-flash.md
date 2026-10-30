# 3. First flash

The first flash goes over USB. After that, every update goes over WiFi (OTA).

## Choose an example

| Example | ESPHome config | Device name | Fallback hotspot |
|---|---|---|---|
| Price Clock | `examples/price-clock/esphome/price-clock.yaml` | `price-clock` | `Price Clock Setup` |
| Weather Clock | `examples/weather-clock/esphome/weather-clock.yaml` | `weather-clock` | `Weather Clock Setup` |

To run several clocks, give each one its own `name` and `friendly_name` under `substitutions:` at the top of the config.

## Prepare secrets.yaml

Copy `examples/secrets.example.yaml` to `secrets.yaml` next to the device config and fill in:

| Key | Value |
|---|---|
| `wifi_ssid` | Your WiFi name |
| `wifi_password` | Your WiFi password |
| `ap_password` | Password for the fallback hotspot, at least 8 characters |
| `api_key` | 32 random bytes in base64, for example from `openssl rand -base64 32` |

`api_key` encrypts both the Home Assistant connection and OTA updates. Home Assistant asks for it when you add the clock.

If you use ESPHome Device Builder, it already has one `secrets.yaml` for all your devices. Add the four keys there instead.

## Flash with the command line

```bash
pip install esphome
mkdir clock
cd clock
```

Copy the device config and `secrets.yaml` into the folder, then run one of:

```bash
esphome run price-clock.yaml
esphome run weather-clock.yaml
```

When asked how to upload, choose the serial port (for example `COM4`) and press Enter. The first build takes a few minutes because ESPHome downloads its toolchain.

## Flash with ESPHome Device Builder

1. Create a new device.
2. Replace its YAML with the contents of `price-clock.yaml` or `weather-clock.yaml` and save.
3. Install with the clock connected over USB.

## After the first flash

1. The clock joins your WiFi.
2. Home Assistant discovers it under Settings > Devices & services.
3. Select Configure and enter the `api_key`.

If the clock cannot join WiFi, it opens its fallback hotspot. Connect with `ap_password` and enter the WiFi details on the page that opens.

## Check the LEDs

Open the clock's Ring light entity in Home Assistant and pick the Rainbow Test effect. All 36 LEDs should cycle through colours. Switch back to Price Ring or Weather Ring afterwards. The ring stays dark in those effects until the Home Assistant package is installed; that is the next chapter.

## How OTA updates are protected

```yaml
ota:
  - platform: esphome
    encryption:
```

With no key given, `encryption:` reuses the key from `api:`. ESPHome recommends this over the older `password:` option, which costs more flash and RAM.

Next: [Home Assistant setup](04-home-assistant.md)
