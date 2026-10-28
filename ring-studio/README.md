# Ring Studio

A desktop app for LED ring clocks running ESPHome. It builds the ESPHome
firmware config, the Home Assistant template that colours the ring and the
brightness automation, from any Home Assistant entity. It also installs ESPHome
and esptool for you and flashes, backs up and restores the clock.

The clock itself stays simple. It shows whatever colours Home Assistant sends.
Changing what a clock shows only changes the Home Assistant template, so there
is no reflash.

## Install and run

You need Python 3.11 or newer.

1. Unzip the folder anywhere.
2. Open a terminal in that folder.
3. Run:

       pip install -r requirements.txt
       python -m ring_studio

If ESPHome or esptool is missing later, the app installs them the first time
you flash or back up.

## The window

Everything happens in one window.

- **Top bar.** Home Assistant connection, Open repo and Export. A short status
  shows when the draft was saved.
- **Left.** Your clocks. Click one to edit it, or add a new one.
- **Middle.** The selected clock in three sections you can fold away:
  - **What it shows.** Pick an entity and a layout, then set the colours.
  - **Brightness.** Night off and dimming that follows the sun.
  - **Device.** Name, LED hardware, flashing, WiFi and keys.
- **Right.** A live preview of the ring. Home Assistant renders the template,
  so the preview is exactly what the clock will show.

### Layouts

| Layout | Input | What the ring does |
| --- | --- | --- |
| Timeline | a list of numbers with times | one LED per item, starting at now (the price clock) |
| States | a list of states | one LED per item (the weather clock) |
| Gauge | one number | the number fills the ring |
| Solid | one number | the whole ring takes the number's colour |
| State | one state | the whole ring takes the state's colour |

Numbers use a gradient bar. Click a dot on the bar to change that colour.
States use a table: a colour swatch, the state value and a definition in plain
words. **Fetch states from Home Assistant** fills in the values the entity
actually reports.

## Flashing

Open **Device**, then **Flash and back up**. The dialog lists anything that
would make the flash fail and links straight to the fix.

1. Plug the clock in over USB and pick its serial port.
2. Press **Back up stock** once. The 4 MB backup is saved in
   `~/.ring_studio/backups/`.
3. Press **Flash over USB**. The first compile downloads the ESP8266 toolchain
   and takes a few minutes.
4. After that, use **Update over the air**. No cable needed.

**Restore stock** writes the backup back to the clock.

## Export

**Export** writes real YAML into your repo folder. It shows every file as New,
Changed or Unchanged, and only writes the ones that differ. Press View to read
a file before writing it. Optionally it also writes one package file for
`config/packages/` and reloads templates and automations in Home Assistant.

Files it writes:

    config/<name>.yaml                      ESPHome firmware
    config/secrets.yaml                     WiFi and keys
    homeassistant/ha_<name>_ring.yaml       template sensor
    homeassistant/automation.yaml           adaptive brightness

Keys are generated only when they are missing, or when you press Generate in
WiFi and keys. An existing key is never replaced on export.

## Drafts

Every edit is saved to a draft in `~/.ring_studio/` and the draft is resumed
the next time the app starts. YAML is only written when you export. Opening a
repo replaces the draft.

## Opening an existing repo

**Open repo** takes a folder or a zip with the `config/` and `homeassistant/`
layout. Each matched set of files becomes a clock. The report lists what it
noticed, such as a clock no automation targets, with a one-click fix where
there is one.

Templates written by this app start with a single `cfg` line and are read back
exactly. Hand-written templates in the palette and `cap` style or the colour
map style are read from their `set` lines. Anything else is kept as it is.

## Tests

    pip install pytest
    python -m pytest tests
