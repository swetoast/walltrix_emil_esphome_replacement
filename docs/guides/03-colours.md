# Colours

All colours live in the `variables:` section at the top of each package. Edit them there, then reload template entities (Developer tools > YAML > Template entities).

## Writing a colour

Colours are written as hex codes, the same format colour pickers use:

```yaml
no_data_color: "#000000"
```

- `#RRGGBB`: red, green, blue, each `00` to `FF`.
- Always put the code in quotes. Without quotes YAML reads `#` as the start of a comment.
- Keep the `#`. Home Assistant turns template variables into numbers when it can, and a code like `"123456"` without `#` would become the number 123456.

Some useful values:

| Colour | Code |
|---|---|
| Off | `#000000` |
| White | `#FFFFFF` |
| Red | `#FF0000` |
| Orange | `#FF6000` |
| Yellow | `#FFC000` |
| Green | `#00FF00` |
| Cyan | `#00C0FF` |
| Blue | `#0000FF` |
| Purple | `#8000FF` |
| Pink | `#FF0080` |

## Three kinds of colour setting

| Kind | Used for | How a value becomes a colour |
|---|---|---|
| Gradient | `price_colors`, `temperature_colors` | Blends between the two nearest steps |
| Steps | `rain_colors` | Takes the highest step reached, no blending |
| Map | `condition_colors`, `sun_colors` | Looks up a name |

### Gradient lists

A list of `[value, colour]` pairs, values from low to high:

```yaml
      price_colors:
        - [0, "#00BFFF"]
        - [12.5, "#0070FF"]
        - [25, "#0040FF"]
        - [37.5, "#4000FF"]
        - [50, "#8000FF"]
        - [62.5, "#B000FF"]
        - [75, "#FF00FF"]
        - [87.5, "#FF0080"]
        - [100, "#FF0040"]
```

- A value exactly on a step gets that step's colour.
- A value between two steps gets a blend. At 56.25 öre, halfway between 50 (`#8000FF`) and 62.5 (`#B000FF`), red is halfway between `80` and `B0`, which is `98`, so the LED gets `#9800FF`.
- Below the first step uses the first colour, so negative prices are `#00BFFF`.
- Above the last step uses the last colour, so anything over 100 öre is `#FF0040`.

Units: `price_colors` is in öre per kWh (SEK x 100). `temperature_colors` is in °C.

**Example: a simple green, yellow, red price scale up to 200 öre**

```yaml
      price_colors:
        - [0, "#00FF00"]
        - [100, "#FFC000"]
        - [200, "#FF0000"]
```

**Example: a tighter temperature scale for winter**

```yaml
      temperature_colors:
        - [-20, "#8000FF"]
        - [-10, "#0000FF"]
        - [0, "#00C0FF"]
        - [5, "#00FF00"]
        - [10, "#FFC000"]
```

You can use any number of steps, but at least two.

### Step lists

A list of `[threshold, colour]` pairs. Each LED takes the colour of the highest threshold its value reaches:

```yaml
      rain_colors:
        - [0, "#0A0A0A"]
        - [0.1, "#60A0FF"]
        - [0.5, "#2060FF"]
        - [2, "#0020FF"]
        - [5, "#8000FF"]
      snow_color: "#FFFFFF"
```

| Rain in the hour | Colour |
|---|---|
| under 0.1 mm | `#0A0A0A`, nearly off |
| 0.1 to under 0.5 mm | `#60A0FF`, light blue |
| 0.5 to under 2 mm | `#2060FF` |
| 2 to under 5 mm | `#0020FF`, deep blue |
| 5 mm or more | `#8000FF`, purple |
| 0.1 mm or more at 0 °C or colder | `snow_color` |

Step lists suit data where a few clear bands read better than a smooth blend.

### Maps

A name with a colour:

```yaml
      sun_colors:
        night: "#001040"
        morning: "#FF5A1E"
        day: "#FFB400"
        evening: "#8C28C8"
```

`condition_colors` works the same way with Home Assistant's weather conditions: `sunny`, `clear-night`, `partlycloudy`, `cloudy`, `fog`, `rainy`, `pouring`, `snowy`, `snowy-rainy`, `hail`, `lightning`, `lightning-rainy`, `windy`, `windy-variant` and `exceptional`. A condition missing from the map uses `unknown_condition_color`.

Keep the names exactly as shown. The colours are yours to change.

## Highlighting now

```yaml
      dim_others: 0.55
```

The LEDs of the current interval are drawn at full colour. Every other LED is multiplied by `dim_others`:

| `dim_others` | Effect |
|---|---|
| `1.0` | No highlight, all LEDs equal |
| `0.55` | Others at 55 percent (Price Clock default) |
| `0.4` | Others at 40 percent (Weather Clock default) |
| `0.0` | Only the current interval is lit |

## Colours that do not look right

- **Dark colours disappear.** The clock scales everything by Ring Brightness / 255 (at most about 35 percent). A colour like `#001040` at low brightness can round down to almost nothing. Brighten the colour or raise the Auto Brightness minimum.
- **Blends look uneven.** WS2812 LEDs are not colour calibrated, and `gamma_correct: 1.0` sends values straight through. Adjusting a step's colour by eye on the real clock works better than calculating.
- **Red and green are swapped.** The LED colour order is wrong. See [Troubleshooting](../troubleshooting.md#colours-are-swapped).

Next: [Brightness and night mode](04-brightness-and-night.md)
