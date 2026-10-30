# Brightness and night mode

Brightness is handled on the clock itself, so it keeps working while Home Assistant restarts. All settings are entities on the clock's device page in Home Assistant.

## Three brightness controls

| Control | Range | What it does |
|---|---|---|
| Ring Brightness | 0 to 90 | Scales every colour by value / 255 before drawing. This is the one to use. |
| Ring light brightness | 0 to 100 % | The light entity's own brightness. Leave it at 100 %. The clock sets it to 100 % at every boot. |
| Colours in the package | `#000000` to `#FFFFFF` | Brighter or darker colours, see [Colours](03-colours.md) |

They multiply. Ring Brightness 90 with light brightness 100 % and the colour `#FF0000` sends a red value of 255 x 90 / 255 = 90 to the LED.

## Auto Brightness

With the Auto Brightness switch on, the clock sets Ring Brightness from the sun's elevation once a minute and whenever `sun.sun` changes:

| Sun elevation | Ring Brightness |
|---|---|
| -6° or lower (dark, civil twilight) | Auto Brightness Min |
| Between -6° and +30° | Blends from Min to Max |
| +30° or higher | Auto Brightness Max |
| Inside night hours | 0, ring dark |

In formula form, outside night hours:

```
f = (elevation + 6) / 36, limited to 0..1
Ring Brightness = Min + (Max - Min) x f, rounded
```

With the defaults (Min 10, Max 90), the sun at 12° gives f = 0.5 and Ring Brightness 50.

Turn Auto Brightness off to set Ring Brightness by hand. The clock then leaves it alone.

## Night hours

| Setting | Default | Meaning |
|---|---|---|
| Night Start Hour | 23 | From this full hour the ring is dark |
| Night End Hour | 6 | From this full hour the ring lights again |

- Hours are whole hours, 0 to 23, in Home Assistant's time zone.
- Night may cross midnight (23 to 6) or not (1 to 5).
- Set both to the same hour to switch night mode off.
- Night mode is part of Auto Brightness. With Auto Brightness off, the ring stays at whatever Ring Brightness you set.

## Settings after a power cut

The ESP8266 keeps saved values in a small memory area that survives a restart but not a power cut. That applies to Ring Brightness, Auto Brightness, the night hours, Min and Max, and the Weather Clock's Ring Mode.

After a power cut they return to the defaults in the config. The defaults are chosen so the clock behaves sensibly straight away: Auto Brightness on, night 23 to 6, Min 10, Max 90.

To keep settings through power cuts, add this to the device config:

```yaml
esp8266:
  board: esp12e
  restore_from_flash: true
```

The trade-off is flash wear. Auto Brightness changes Ring Brightness many times a day, and ESPHome writes changed values to flash at most once a minute by default. Flash survives a limited number of writes, so only enable this if you need it.

Next: [Make your own ring](05-make-your-own-ring.md)
