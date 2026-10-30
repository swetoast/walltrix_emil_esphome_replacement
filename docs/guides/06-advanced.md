# Advanced

Optional additions to the clock firmware. None of them need extra hardware. Each section has the YAML to add to the device config (`price-clock.yaml` or `weather-clock.yaml`) and explains how to use it.

All snippets were checked together with `esphome config` on ESPHome 2026.10.1. They have not all been tested on a running clock. Add one at a time, install, and check that the clock still works before adding the next.

## Before you add anything

- **Memory.** The ESP8266 has little RAM. After each addition, watch Free Heap and Largest Free Block on the device page for a day. If they drop a lot, remove what you added last.
- **Where the YAML goes.** If a snippet starts with a key that already exists in the config, such as `api:`, `button:`, `sensor:` or `effects:`, add only the lines under it to the existing section. Do not create a second `button:` section.
- **Weather Clock.** The snippets use the Price Clock names. On the Weather Clock, replace `"Price Ring"` with `"Weather Ring"`.

## Contents

| Section | What you get |
|---|---|
| [Alerts from Home Assistant](#alerts-from-home-assistant) | Home Assistant flashes the ring |
| [More light effects](#more-light-effects) | Pulse, Color Wipe, Scan, Twinkle, Random Twinkle, Fireworks, Flicker |
| [Supply voltage](#supply-voltage) | The voltage at the ESP8266 chip |
| [Ring energy today](#ring-energy-today) | Estimated LED energy per day in kWh |
| [Factory reset button](#factory-reset-button) | Erase all settings and WiFi details |
| [SNTP time](#sntp-time) | A second time source next to Home Assistant |
| [Syslog](#syslog) | Send the clock's warnings to a syslog server |
| [WLED](#wled) | Drive the ring from WLED-compatible apps |
| [E1.31](#e131) | Drive the ring from E1.31 software |
| [Split the ring into separate lights](#split-the-ring-into-separate-lights) | Parts of the ring as their own light entities |

## Alerts from Home Assistant

Adds an action that Home Assistant can call to flash the ring red a set number of times. After the flashes the ring goes back to Price Ring.

Add to the device config:

```yaml
api:
  actions:
    - action: alert
      variables:
        times: int
      then:
        - if:
            condition:
              lambda: 'return id(ring_brightness).state > 0;'
            then:
              - light.turn_on:
                  id: ring
                  effect: "Alert"
              - delay: !lambda 'return times * 750;'
              - light.turn_on:
                  id: ring
                  effect: "Price Ring"
```

and the Alert effect under `effects:` of the light:

```yaml
      - strobe:
          name: "Alert"
          colors:
            - state: true
              brightness: 35%
              red: 100%
              green: 0%
              blue: 0%
              duration: 500ms
            - state: false
              duration: 250ms
```

How it works:

- One flash is 500 ms on and 250 ms off, so the action waits `times x 750` ms before switching back.
- `brightness: 35%` matches the brightest the normal ring gets (Ring Brightness 90). Raise it for a stronger alert.
- The `if` skips the alert while Ring Brightness is 0, so it does not flash at night.

After installing, Home Assistant has a new action named after the device: `esphome.price_clock_alert` (`esphome.weather_clock_alert` on the Weather Clock). The `-` in the device name becomes `_`.

Try it in Developer tools > Actions:

```yaml
action: esphome.price_clock_alert
data:
  times: 3
```

Or use it in an automation, for example three flashes at 07:00 on weekdays:

```yaml
alias: Clock alert at 07:00
triggers:
  - trigger: time
    at: "07:00:00"
conditions:
  - condition: time
    weekday: [mon, tue, wed, thu, fri]
actions:
  - action: esphome.price_clock_alert
    data:
      times: 3
```

To change the colour, edit `red`, `green` and `blue` in the Alert effect. They are percentages, not hex codes.

## More light effects

Built-in ESPHome effects. Add any of them under `effects:` of the light. They show up in the effect list of the Ring light in Home Assistant.

```yaml
      - pulse:
          name: "Pulse"
          transition_length: 1s
          update_interval: 2s
      - addressable_color_wipe:
          name: "Color Wipe"
      - addressable_scan:
          name: "Scan"
          move_interval: 100ms
          scan_width: 3
      - addressable_twinkle:
          name: "Twinkle"
      - addressable_random_twinkle:
          name: "Random Twinkle"
      - addressable_fireworks:
          name: "Fireworks"
      - addressable_flicker:
          name: "Flicker"
```

| Effect | What it does | Colour comes from |
|---|---|---|
| Pulse | The whole ring fades in and out | The light's colour |
| Color Wipe | New colours enter at LED 0 and move along the ring | Random colours |
| Scan | A dot of 3 LEDs moves back and forth | The light's colour |
| Twinkle | Random LEDs light up briefly | The light's colour |
| Random Twinkle | Like Twinkle with random colours | Random colours |
| Fireworks | Sparks start at random LEDs and fade out | The light's colour |
| Flicker | Every LED flickers slightly around one colour | The light's colour |

Things to know:

- These effects are not scaled by Ring Brightness. The clock turns the light on at 100 % at boot, which is very bright. Lower the Ring light's brightness in Home Assistant before using them.
- Auto Brightness and night hours do not affect them.
- To get the normal ring back, select Price Ring (or Weather Ring) as the effect.

## Supply voltage

The ESP8266 can measure the voltage at its own chip.

```yaml
sensor:
  - platform: adc
    pin: VCC
    name: "Supply Voltage"
```

- This only works if nothing is connected to the chip's `A0` pin. If something is, the reading is wrong.
- It measures the chip's 3.3 V supply, not the 5 V from the USB cable.
- After installing, check the value. Around 3.3 V means it works. A value far from 3.3 V means `A0` is in use on your board; remove the sensor.

Use it as a check on the chip's power supply.

## Ring energy today

Turns Ring Power Estimate into an energy total that resets at midnight.

Give the existing Ring Power Estimate sensor an id by adding the `id:` line:

```yaml
  - platform: template
    name: "Ring Power Estimate"
    id: ring_power
```

Then add under `sensor:`:

```yaml
  - platform: total_daily_energy
    name: "Ring Energy Today"
    power_id: ring_power
    unit_of_measurement: "kWh"
    state_class: total_increasing
    device_class: energy
    accuracy_decimals: 3
    filters:
      - multiply: 0.001
```

- It uses the clock's time source to know when midnight is.
- The value is an estimate, built on the same assumptions as Ring Power Estimate.
- Home Assistant can make the same total without changing the firmware: Settings > Devices & services > Helpers > Integral sensor on `sensor.price_clock_ring_power_estimate`. Use this section only if you want the total on the clock itself.

## Factory reset button

Adds a button that erases everything the clock has saved and restarts it.

```yaml
button:
  - platform: factory_reset
    name: "Factory Reset"
```

What gets erased:

- Ring Brightness, Auto Brightness, night hours, Min, Max and Ring Mode go back to their defaults.
- WiFi details entered through the fallback hotspot are erased. WiFi details from `secrets.yaml` are part of the firmware and stay.

Use it before giving the clock to someone else. The erase cannot be undone.

## SNTP time

Adds a second time source that gets the time from NTP servers instead of Home Assistant.

```yaml
time:
  - platform: sntp
    id: sntp_time
```

Add it as a second item in the existing `time:` list, after the `homeassistant` entry.

- Without `servers:`, ESPHome uses `0.pool.ntp.org`, `1.pool.ntp.org` and `2.pool.ntp.org`, which means traffic to the internet. To keep it local, list your own NTP server, for example your router:

  ```yaml
    - platform: sntp
      id: sntp_time
      servers:
        - 192.168.1.1
  ```

- ESPHome tries to take the time zone from the computer that builds the firmware. If that is wrong, add `timezone: Europe/Stockholm` (or your own zone).
- Auto Brightness and night hours keep using Home Assistant's time and `sun.sun`. Adding SNTP does not change how the ring behaves.

When it helps: the clock knows the time even if it starts while Home Assistant is down, for example for syslog timestamps. Once the clock has the time it keeps counting on its own, so a short Home Assistant restart does not need SNTP.

## Syslog

Sends the clock's log messages to a syslog server on your network.

```yaml
udp:
  addresses: 192.168.1.10

syslog:
  time_id: ha_time
  level: WARN
```

- Replace `192.168.1.10` with the address of your syslog server. Messages go to UDP port 514.
- The configs set `logger: level: WARN`, so only warnings and errors exist to send. `level: WARN` here matches that.
- `time_id: ha_time` timestamps messages with Home Assistant's time. If you added SNTP, you can use `time_id: sntp_time` instead.

## WLED

Lets apps that speak the WLED realtime protocol, such as LedFx or Prismatik, drive the ring over the network.

Add at the top level of the config:

```yaml
wled:
```

and under `effects:` of the light:

```yaml
      - wled:
```

How to use it:

1. Select the WLED effect on the Ring light in Home Assistant.
2. In the app, add a UDP device with the clock's IP address (see `sensor.price_clock_ip_address`) and port 21324. In LedFx and Prismatik, use the data prefix `0201`.
3. The app now controls all 36 LEDs. Select Price Ring again to go back.

The clock listens on UDP port 21324 while this is installed.

## E1.31

Lets E1.31 software, such as Jinx! or Hyperion.NG, drive the ring.

Add at the top level of the config:

```yaml
e131:
  method: multicast
```

and under `effects:` of the light:

```yaml
      - e131:
          universe: 1
          channels: RGB
```

How to use it:

1. Select the E1.31 effect on the Ring light in Home Assistant.
2. In the software, set up a 36 pixel RGB output on universe 1. With `method: multicast` the clock joins the multicast group for universe 1. With `method: unicast`, send to the clock's IP address.
3. Select Price Ring again to go back.

36 RGB LEDs use 108 of the 512 channels in the universe. The clock listens on UDP port 5568.

## Split the ring into separate lights

The `partition` platform makes part of the ring its own light entity in Home Assistant, for example the 9 LEDs of one quarter.

```yaml
light:
  - platform: partition
    name: "Ring 12 to 3"
    segments:
      - id: ring
        from: 0
        to: 8
```

- `from` and `to` are LED numbers on the strip (0 to 35), the same numbers the LED Index Test shows. They match the face only if LED 0 sits under 12 and the LEDs are numbered clockwise.
- The Ring light and the partition light write to the same LEDs, and ESPHome's documentation warns that they can conflict. Price Ring redraws all 36 LEDs every second, so expect it to overwrite the partition while it runs. The documentation suggests marking the original light `internal: true`, but that removes the Ring light, and with it Price Ring, from Home Assistant.

Use this only if you want to drive the ring as separate lights from Home Assistant instead of using Price Ring or Weather Ring.

## See also

- [Device entities](../reference/device-entities.md): every entity the standard firmware creates
- [Troubleshooting](../troubleshooting.md)
- ESPHome documentation: [Native API](https://esphome.io/components/api/), [Light effects](https://esphome.io/components/light/), [ADC](https://esphome.io/components/sensor/adc/), [Total Daily Energy](https://esphome.io/components/sensor/total_daily_energy/), [Factory Reset Button](https://esphome.io/components/button/factory_reset/), [SNTP](https://esphome.io/components/time/sntp/), [Syslog](https://esphome.io/components/syslog/), [Light Partition](https://esphome.io/components/light/partition/)
