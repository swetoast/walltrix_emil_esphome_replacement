# ESPHome Replacement

This is the complete guide to taking stock clock hardware off its original cloud firmware and running it locally over LAN using ESPHome and Home Assistant. The LED ring is driven entirely over your local network and requires no external cloud services.

This repository supports two distinct project builds using the same ESP8266 + 36-WS2812 LED hardware:

1. **EnergiKlockan (Electricity Prices)**: Displays Swedish SE3 spot prices at 15-minute resolution across the next 9 hours using a dynamic color gradient from ice blue to hot pink.
2. **WeatherClock (Hourly Forecast)**: Displays a 36-hour rolling weather forecast from `sensor.weather_hourly`, mapping 15 official weather states to distinct solid RGB colors.

---

## Repository File Structure


```

walltrix_emil_esphome_replacement/
├── config/
│   ├── energiklockan.yaml       # ESPHome config for price clock
│   ├── weatherclock.yaml        # ESPHome config for weather clock
│   └── secrets.yaml             # WiFi & encryption keys
├── homeassistant/
│   ├── ha_energiklockan_ring.yaml  # HA template for price ring
│   ├── ha_weatherclock_ring.yaml   # HA template for weather ring
│   └── automation.yaml             # Adaptive solar elevation dimming
└── readme.md

```

---

## The Original Firmware, in Brief

The internal board is an ESP8266EX with 4 MB of flash and an onboard CH340 USB-to-serial bridge, flashing over a standard micro-USB cable with no soldering required. The ring consists of 36 WS2812 LEDs running GRB color order at standard 800 kHz on GPIO12. The clock hands are powered separately by an AA cell quartz movement and operate independently of the ESP8266 microcontroller.

The stock firmware pulled Nord Pool prices over plain HTTP from a public cloud bucket. Replacing it with ESPHome establishes a secure, encrypted LAN connection between your clock and Home Assistant.

---

## Back Up the Original Firmware First

A bad firmware flash can normally be recovered through the serial bootloader, provided the hardware and serial connection still work. Take a full image first so that going back to stock is a single command.

With the clock plugged in and showing as `COM4` in a terminal:

```bash
pip install esptool
esptool --port COM4 flash-id
esptool --port COM4 --baud 460800 read-flash 0x0 0x400000 stock_full_4MB.bin

```

The backup should be exactly `4194304` bytes. Record a fingerprint so you can confirm it later:

```powershell
certutil -hashfile stock_full_4MB.bin SHA256

```

Keep `stock_full_4MB.bin` somewhere safe. That file is the entire original firmware.

---

## Restore the Original at Any Time

If you ever want the clock back exactly as it shipped, write the backup back:

```bash
esptool --port COM4 --baud 460800 write-flash 0x0 stock_full_4MB.bin

```

That restores the saved flash contents if the backup is valid and the serial bootloader is accessible.

---

## Replace with ESPHome

This is the first flash, done once over USB. Everything after it is wireless. The clock is on `COM4`.

1. Open PowerShell (**Start menu > type `powershell` > press Enter**).
2. Install ESPHome:
```bash
pip install esphome

```


3. Make a project folder:
```bash
mkdir D:\energyclock

```


4. Copy your chosen firmware config (`config/energiklockan.yaml` or `config/weatherclock.yaml`) and `config/secrets.yaml` into your project directory.
5. Go into the folder:
```bash
cd D:\energyclock

```


6. Open `secrets.yaml` and fill in your WiFi details:
```bash
notepad secrets.yaml

```


Change `YOUR_WIFI_NAME` and `YOUR_WIFI_PASSWORD` to your real WiFi credentials. Save with **Ctrl+S** and close.
7. Flash the board:
* For EnergiKlockan:
```bash
esphome run energiklockan.yaml

```


* For WeatherClock:
```bash
esphome run weatherclock.yaml

```




When prompted, choose the `COM4` serial option using the arrow keys and press **Enter**.
8. When compilation and flashing finish, Home Assistant will discover the device under **Settings > Devices & Services**. Click **Configure** and enter the key listed under `api_key` in `secrets.yaml`.

After this initial flash, wireless (OTA) updates are enabled and the USB cable is no longer required.

---

## Confirm the LED Data Pin

The ring responds on `GPIO12` using `method: bit_bang`, `gamma_correct: 1.0`, WS2812, and GRB color settings.

Select **Rainbow Test** under light effects for a hardware test at 10% brightness. Return to **Price Ring** or **Weather Ring** and 100% light brightness afterwards; **Ring Brightness** handles the separate template color scaling.

---

## Home Assistant Setup

### Option 1: EnergiKlockan (Spot Price Ring)

1. Add the contents of `homeassistant/ha_energiklockan_ring.yaml` to your Home Assistant `configuration.yaml` under `template:`.
2. Reload template entities or restart Home Assistant to create `sensor.energiklockan_ring_colors`.
3. Interacts with:
* `light.energiklockan_ring`: Controls power state (on/off), overall brightness, and active effect selection (`Price Ring` or `Rainbow Test`).
* `number.energiklockan_ring_brightness`: Slider (0–90) scaling RGB values.



### Option 2: WeatherClock (Hourly Weather Ring)

1. Add the contents of `homeassistant/ha_weatherclock_ring.yaml` to your Home Assistant `configuration.yaml` under `template:`.
2. Reload template entities or restart Home Assistant to create `sensor.weatherclock_ring_colors`.
3. Interacts with:
* `light.weatherclock_ring`: Controls power state (on/off), overall brightness, and active effect selection (`Weather Ring` or `Rainbow Test`).
* `number.weatherclock_ring_brightness`: Slider (0–90) scaling RGB values.



---

## Dynamic Daylight Brightness Automation (`homeassistant/automation.yaml`)

Both clock variants can utilize `homeassistant/automation.yaml` for dynamic ring dimming based on solar elevation:

- **Overnight (23:00 to 06:00)**: `number.*_ring_brightness` is set strictly to `0` (off).
- **Daytime**: Brightness scales automatically between `10` and `90` based on the sun's position:
  - At solar elevation <= -6° (civil twilight/dawn), brightness is `10`.
  - At solar elevation >= 30° (full daylight), brightness reaches `90`.

Import `homeassistant/automation.yaml` into Home Assistant to enable automatic dimming.

---

## Color Logic Summary

### EnergiKlockan Spot Prices (15-Minute Resolution)

* **Negative prices**: Ice blue (`#00BFFF`).
* **0 to 100 öre/kWh**: Gradient through blue, purple, magenta, and hot pink (`#FF0040`).
* LED 0 (current quarter-hour) displays at 100% brightness; LEDs 1–35 display at 55% dimmed brightness.

### WeatherClock Forecast (36-Hour Hourly Resolution)

* Maps 15 Home Assistant weather states (`sunny`, `rainy`, `snowy`, `cloudy`, etc.) to solid RGB values.
* LED 0 (current hour) displays at 100% brightness; LEDs 1–35 display at 40% dimmed brightness.

---

## Troubleshooting

* **Ring dark, Rainbow Test works**: Check that the corresponding template sensor (`sensor.energiklockan_ring_colors` or `sensor.weatherclock_ring_colors`) is active and producing a 216-character state string.
* **Ring dark, Rainbow Test also dark**: Check power connections, GPIO12 configuration, and ensure the light entity (`light.energiklockan_ring` or `light.weatherclock_ring`) is turned on in Home Assistant.
* **Colors look swapped**: Change `type: GRB` in the YAML configuration to `RGB` or `BRG` and reflash.
* **Device not discovered in Home Assistant**: Confirm WiFi credentials in `secrets.yaml`. If connection fails, the board broadcasts a local fallback hotspot (`Energiklockan Setup` or `WeatherClock Setup`).

---

## Going Back

If you ever want stock again, the restore command above rewrites the original `stock_full_4MB.bin` image and the clock returns to its factory state.
