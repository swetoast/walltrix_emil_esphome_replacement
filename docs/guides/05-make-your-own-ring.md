# Make your own ring

Any Home Assistant data can drive the ring. The clock only needs a sensor whose state is 216 hex characters. This chapter builds a new ring step by step, using an indoor temperature sensor as the example.

## The contract

The clock accepts any sensor that:

1. Has a state of at least 216 characters.
2. Holds 36 colours as `RRGGBB` hex, LED 0 first.

Anything shorter (`unknown`, `unavailable`, an empty string) is ignored and the ring keeps its last colours.

## Step 1: start from an example

Copy the example package closest to what you want. A forecast-style ring (one value per hour) starts best from the Weather Clock temperature sensor. A ring with one colour per LED and no time dimension can be much simpler, as below.

## Step 2: a minimal ring

This package shows one colour on every LED, taken from an indoor temperature sensor. Save it as `/config/packages/indoor_ring.yaml`:

```yaml
template:
  - triggers:
      - trigger: homeassistant
        event: start
      - trigger: time_pattern
        minutes: "/1"
    variables:
      source_entity: sensor.living_room_temperature
      temperature_colors:
        - [18, "#0060FF"]
        - [21, "#00FF60"]
        - [24, "#FF6000"]
    sensor:
      - name: "Indoor Ring Colors"
        unique_id: indoor_ring_colors
        availability: >
          {{ is_number(states(source_entity)) }}
        state: >
          {%- set v = states(source_entity) | float(0) -%}
          {%- set stops = temperature_colors -%}
          {%- set g = namespace(hex=stops[0][1] | replace('#', '')) -%}
          {%- if v >= stops[-1][0] -%}
            {%- set g.hex = stops[-1][1] | replace('#', '') -%}
          {%- elif v > stops[0][0] -%}
            {%- for k in range(stops | count - 1) -%}
              {%- if stops[k][0] <= v < stops[k + 1][0] -%}
                {%- set f = (v - stops[k][0]) / (stops[k + 1][0] - stops[k][0]) -%}
                {%- set a = stops[k][1] | replace('#', '') -%}
                {%- set b = stops[k + 1][1] | replace('#', '') -%}
                {%- set g.hex = '%02X%02X%02X' | format(
                      ((a[0:2] | int(0, 16)) + ((b[0:2] | int(0, 16)) - (a[0:2] | int(0, 16))) * f) | int,
                      ((a[2:4] | int(0, 16)) + ((b[2:4] | int(0, 16)) - (a[2:4] | int(0, 16))) * f) | int,
                      ((a[4:6] | int(0, 16)) + ((b[4:6] | int(0, 16)) - (a[4:6] | int(0, 16))) * f) | int) -%}
              {%- endif -%}
            {%- endfor -%}
          {%- endif -%}
          {{ g.hex * 36 }}
```

`g.hex * 36` repeats the 6 character colour 36 times, giving the 216 characters the clock needs. Replace `sensor.living_room_temperature` with your own sensor.

## Step 3: point the clock at it

In the device config, change the `entity_id` of the Home Assistant text sensor that feeds the ring.

Price Clock (`price-clock.yaml`):

```yaml
text_sensor:
  - platform: homeassistant
    id: ring_colors
    entity_id: sensor.indoor_ring_colors
```

Weather Clock: replace one of the four sources instead, for example the Sun ring:

```yaml
  - platform: homeassistant
    id: sun_colors
    entity_id: sensor.indoor_ring_colors
```

Install the updated firmware over WiFi.

## Step 4: add time

To make each LED show a different time, reuse the time slot block from an example package. Every example sensor contains the same loop:

```jinja
{%- for i in range(36) -%}
  {#- 1. work out the interval t for LED i (layout, interval_minutes, led_offset, clockwise) -#}
  {#- 2. look up your data at time t -#}
  {#- 3. turn it into a colour -#}
  {#- 4. dim it unless is_now -#}
{%- endfor -%}
```

Copy the whole loop from the Weather Clock temperature sensor and change only step 2, the lookup, to read your own data. Steps 1, 3 and 4 then keep working with the same `variables:` settings described in [Time on the ring](02-time-on-the-ring.md) and [Colours](03-colours.md).

## Step 5: check it

1. Developer tools > Template: paste the `state:` template with the variables set at the top, and check the output is 216 characters.
2. Developer tools > States: check the sensor's state.
3. On the clock, Ring Data Valid should be on.

The offline checker in [Testing templates offline](../reference/testing.md) can render a package with made-up data before you put it in Home Assistant.
