# 1. Hardware

The firmware targets the Walltrix Emil wall clock. Opening the clock is not needed: everything, including the first flash, goes through its micro-USB port.

## Components

| Part | Detail | Where it appears in the config |
|---|---|---|
| Microcontroller | ESP8266EX with 4 MB flash | `esp8266: board: esp12e` |
| USB | Onboard CH340 USB to serial bridge with automatic reset | Used for the first flash only |
| LEDs | 36 x WS2812, GRB colour order, 800 kHz | `light: platform: neopixelbus`, `variant: WS2812`, `type: GRB`, `num_leds: 36` |
| LED data pin | GPIO12 | `pin: GPIO12`, `method: type: bit_bang` |
| Clock hands | Quartz movement on its own AA cell | Not connected to the electronics |

## The LED ring

The 36 LEDs sit behind the dial, 9 per quarter of the face. Read with the hour hand that is 3 LEDs per hour; read with the minute hand it is 9 LEDs per 15 minutes. See [Time on the ring](../guides/02-time-on-the-ring.md).

The LEDs are numbered 0 to 35 in the order the data travels along the strip. Which numeral LED 0 sits under, and whether the numbers run clockwise, depends on the unit. The firmware's LED Index Test effect shows both; see [Time on the ring](../guides/02-time-on-the-ring.md#line-the-face-up-with-your-clock).

## Limits

- **Memory.** The ESP8266 has only a few tens of kilobytes of free RAM while running. The examples are sized to fit with room to spare, and the Free Heap, Largest Free Block and Heap Fragmentation sensors let you watch it.
- **Saved settings.** By default saved settings survive a restart but not a power cut. See [Brightness and night mode](../guides/04-brightness-and-night.md#settings-after-a-power-cut).
- **No Bluetooth.** The ESP8266 has no Bluetooth, so Bluetooth proxy and similar features are not possible.

Next: [Back up and restore the original firmware](02-backup-and-restore.md)
