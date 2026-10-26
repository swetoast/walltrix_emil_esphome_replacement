# EnergiKlockan: local price-ring replacement

This is the complete guide to taking the clock off its stock cloud firmware and
running it on ESPHome instead, so the LED ring is driven entirely by your own
Home Assistant over the LAN. The clock needs no cloud price service. Values from
`secrets.yaml` are included in the compiled firmware; keep them private.

The ring shows the Swedish SE3 spot price at 15-minute resolution: 36 LEDs, each
one a quarter-hour slot, covering the next nine hours. Prices use neon blue,
purple and pink; negative prices use ice blue, and the current slot is
the brightest so you can read "now" at a glance.

There are three files alongside this guide:

- `energiklockan.yaml`, the ESPHome firmware config.
- `secrets.yaml`, your WiFi and the pre-generated keys.
- `ha_energiklockan_ring.yaml`, the Home Assistant template that produces the
  colours.

## The original firmware, in brief

The board is an ESP8266EX with 4 MB of flash and a CH340 USB-serial bridge, so
it flashes over the micro-USB cable with nothing to solder. The ring is 36
WS2812 LEDs, GRB order, standard 800 kHz. The clock hands are a separate quartz
movement on the AA cell and have nothing to do with the electronics, so the
replacement never affects timekeeping.

The stock firmware pulled Nord Pool prices over plain HTTP from a public cloud
bucket, kept its settings in a small on-device filesystem, and could update
itself over the internet. It also carried outbound hooks for MQTT, a webhook and
email, with a mail account password embedded in the image. The replacement
removes all of that and replaces the cloud link with your Home Assistant on the
LAN. The full teardown is in `energiklockan-original-firmware.md`.

## Back up the original first

A bad firmware flash can normally be recovered through the serial bootloader,
provided the hardware and serial connection still work. Take a full image first
so that going back to stock is a single command.

With the clock plugged in and showing as COM4, in a terminal:

    pip install esptool
    esptool --port COM4 flash-id
    esptool --port COM4 --baud 460800 read-flash 0x0 0x400000 stock_full_4MB.bin

The backup should be exactly 4194304 bytes. Record a fingerprint so you can
confirm it later:

    certutil -hashfile stock_full_4MB.bin SHA256

Keep `stock_full_4MB.bin` somewhere safe. That file is the entire original
firmware.

## Restore the original at any time

If you ever want the clock back exactly as it shipped, write the backup back:

    esptool --port COM4 --baud 460800 write-flash 0x0 stock_full_4MB.bin

That restores the saved flash contents if the backup is valid and the serial
bootloader is accessible.

## Replace with ESPHome

This is the first flash, done once over USB. Everything after it is wireless.
The clock is on COM4.

1. Open PowerShell. Start menu, type `powershell`, press Enter.

2. Install ESPHome. This takes a few minutes:

       pip install esphome

3. Make a project folder:

       mkdir D:\energyclock

4. Put `energiklockan.yaml` and `secrets.yaml` into `D:\energyclock`.

5. Go into the folder:

       cd D:\energyclock

6. Open `secrets.yaml` and fill in your WiFi:

       notepad secrets.yaml

   Change `YOUR_WIFI_NAME` and `YOUR_WIFI_PASSWORD` to your real WiFi. Save with
   Ctrl+S and close.

7. Flash it:

       esphome run energiklockan.yaml

   The first run compiles for a few minutes, which is normal. When it asks how to
   upload, choose the COM4 serial option with the arrow keys and press Enter. If
   the `esphome` command is not recognised, use `python -m esphome run
   energiklockan.yaml` instead.

8. When it finishes, Home Assistant shows a new device, Energiklockan, under
   Settings, Devices and Services. Add it. If it asks for an encryption key,
   paste the line after `api_key:` from `secrets.yaml`.

After this, ESPHome offers wireless uploads and the cable is no longer needed.

## Confirm the LED data pin

The ring responded on GPIO12 with `method: bit_bang`, `gamma_correct: 1.0`,
WS2812 and GRB settings. These settings are included in `energiklockan.yaml`.

Select **Rainbow Test** for a hardware test at 10% light brightness with gamma
1.0. A dark ring alone does not prove a wrong pin: power, brightness and output
settings also matter. Return to **Price Ring** and 100% light brightness afterwards;
**Ring Brightness** applies the separate colour scaling.

## Set up the price ring in Home Assistant

The firmware is a thin display. All the logic lives in Home Assistant, in one
template sensor.

1. Add the template. Open `ha_energiklockan_ring.yaml`, and paste its contents
   into your Home Assistant configuration (under your existing `template:` key,
   or the whole block if you have none). Reload template entities or restart
   Home Assistant. You now have `sensor.energiklockan_ring_colors`, a
   216-character colour string.

2. The firmware already imports that sensor, so once it exists the ring starts
   showing prices. The "Price Ring" effect is on by default at boot.

3. The device exposes two controls in Home Assistant:
   - **Energiklockan Ring**, the light itself, for on and off.
   - **Ring Brightness**, a slider from 0 to 90. This scales the RGB values;
     it is not a measured power limit or a guarantee against brownouts.

That is the whole setup. The template recomputes as each quarter-hour passes and
as prices update, and the device repaints to match.

## How the colours are decided

The template reads the `today` and `tomorrow` 15-minute arrays from
`sensor.swedish_spot_price_elpris_se3_forecast`, finds the slot that contains the
current time, and takes that slot plus the next 35. Each slot becomes a colour:

- Below zero: ice blue (`#00BFFF`).
- Zero up to the cap: a smooth gradient through `#00BFFF`, `#0070FF`,
  `#0040FF`, `#4000FF`, `#8000FF`, `#B000FF`, `#FF00FF`, `#FF0080` and
  `#FF0040`, from low to high prices.
- The cap is 100 ore/kWh by default, set near the top of the template as
  `cap = 100.0`. Lower it to make the ring reach hot pink sooner and show more colour
  range on cheap days.

The current slot is sent at full brightness and the rest slightly dimmed, so the
present moment reads as the brightest point on the ring.

## Optional: switch the ring off overnight

The stock clock turned its ring off between 20:00 and 06:00. If you want that,
the cleanest way is a Home Assistant automation that turns the Energiklockan Ring
light off at 20:00 and on at 06:00. It is left out by default because the evening
is when prices peak and the ring is most useful, but the option is yours.

## Troubleshooting

- **Ring dark, rainbow works.** The Home Assistant template is not set up yet, or
  `sensor.energiklockan_ring_colors` has no value. Check it exists and has a
  216-character state.
- **Ring dark, rainbow also dark.** Check power, brightness and the working
  GPIO12, `bit_bang` and gamma 1.0 settings. Darkness alone does not identify the cause.
- **Colours look swapped.** Change `type: GRB` in `energiklockan.yaml` to `RGB`
  or `BRG` until a known colour looks right.
- **A dead channel, or white never shows.** This alone does not establish RGBW
  hardware. Keep the working WS2812/GRB settings unless hardware evidence says otherwise.
- **Device not discovered in Home Assistant.** Confirm it joined WiFi. It falls
  back to a local hotspot named "Energiklockan Setup" if the WiFi details are
  wrong.

## Going back

If you ever want stock again, the restore command above rewrites the original
image and the clock is exactly as it was.
