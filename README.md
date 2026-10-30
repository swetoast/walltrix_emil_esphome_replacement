# Walltrix Emil: Esphome Replacement

Replacement firmware for the Walltrix Emil wall clock and its ring of 36 LEDs. The clock runs ESPHome and gets everything it shows from your own Home Assistant over the local network.

Home Assistant works out one colour per LED and the clock draws them. What the ring means (prices, weather, daylight, anything else) is decided by a Home Assistant package, so you can change it without touching the firmware.

## Examples

| Example | Shows | Data from | Ring |
|---|---|---|---|
| [Price Clock](examples/price-clock/) | Electricity spot price | A price sensor with 15 minute slots | 60 minutes, 15 minutes = 9 LEDs |
| [Weather Clock](examples/weather-clock/) | Condition, temperature, rain or daylight | `weather.forecast_home` and `sun.sun`, both in a default Home Assistant install | 12 hours, 1 hour = 3 LEDs |

Both examples run on the same hardware. Each example folder has its ESPHome config, its Home Assistant package and a README explaining what it shows.

## Documentation

**Getting started**
1. [Hardware](docs/getting-started/01-hardware.md)
2. [Back up and restore the original firmware](docs/getting-started/02-backup-and-restore.md)
3. [First flash](docs/getting-started/03-first-flash.md)
4. [Home Assistant setup](docs/getting-started/04-home-assistant.md)

**Guides**
1. [How the ring works](docs/guides/01-how-the-ring-works.md)
2. [Time on the ring](docs/guides/02-time-on-the-ring.md)
3. [Colours](docs/guides/03-colours.md)
4. [Brightness and night mode](docs/guides/04-brightness-and-night.md)
5. [Make your own ring](docs/guides/05-make-your-own-ring.md)

**Reference**
- [Device entities](docs/reference/device-entities.md)
- [Package settings](docs/reference/package-settings.md)
- [Testing templates offline](docs/reference/testing.md)

**Help**
- [Troubleshooting](docs/troubleshooting.md)
- [Upgrading from the earlier layout](docs/upgrading.md)

## Repository layout

```
.
├── README.md
├── LICENSE                     MIT
├── docs/
│   ├── getting-started/        Hardware, backup, flashing, Home Assistant
│   ├── guides/                 Time on the ring, colours, brightness, your own ring
│   ├── reference/              Every entity and every package setting
│   ├── troubleshooting.md
│   └── upgrading.md
├── examples/
│   ├── secrets.example.yaml    Template for secrets.yaml
│   ├── price-clock/
│   │   ├── README.md
│   │   ├── esphome/price-clock.yaml
│   │   └── homeassistant/price_clock.yaml
│   └── weather-clock/
│       ├── README.md
│       ├── esphome/weather-clock.yaml
│       └── homeassistant/weather_clock.yaml
└── tests/                      Offline check of the Home Assistant templates
```

## Quick start

1. [Back up the original firmware](docs/getting-started/02-backup-and-restore.md). Do not skip this.
2. Copy `examples/secrets.example.yaml` to `secrets.yaml` and fill it in.
3. [Flash](docs/getting-started/03-first-flash.md) `price-clock.yaml` or `weather-clock.yaml` over USB. Later updates go over WiFi.
4. Copy the matching package to `/config/packages/` and restart Home Assistant ([details](docs/getting-started/04-home-assistant.md)).
5. Add the clock in Home Assistant when it is discovered, using your `api_key`.

## License

MIT, see [LICENSE](LICENSE).
