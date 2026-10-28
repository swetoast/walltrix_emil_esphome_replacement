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

### Windows app

To get a `Ring Studio.exe` you can double-click:

1. Open a terminal in this folder on Windows.
2. Run `build_windows.bat`.
3. The app is in `dist\Ring Studio.exe`.

Flashing still needs Python on the computer, because ESPHome is a Python
program. If Python is missing, the flash dialog says so. Install it from
python.org and tick "Add python.exe to PATH".

## The window

Everything happens in one window.

- **Top bar.** Undo and redo, Home Assistant connection, Open repo and
  Export. A short status shows when the draft was saved.
- **Left.** Your clocks, each with a dot that is green when the clock is
  online. Click one to edit it. **Add clock** offers ready-made clocks:
  electricity price, weather, temperature, battery, calendar or blank.
- **Middle.** The selected clock in three sections you can fold away:
  - **What it shows.** Pick an entity and a layout, then set the colours.
  - **Brightness.** Night off and dimming that follows the sun. A bar chart
    shows today's brightness every half hour at your Home Assistant location.
  - **Device.** Online or offline, the firmware version and **Identify**,
    which shows a rainbow on that clock for 5 seconds. If the ESPHome
    installed here is newer than the clock's, a note offers the update. Then
    name, LED hardware, flashing, WiFi and keys. The hardware is one preset,
    EnergiKlockan EMIL (GPIO12, 36 LEDs, bit_bang, GRB). Open Custom
    hardware to change the raw values.
- **Right.** A live preview of the ring. Home Assistant renders the template,
  so the preview is exactly what the clock will show.

### The preview

- **Point at an LED** to see what it shows, in the entity's own unit, for
  example `LED 4 · Today 18:45 · 0.423 SEK/kWh` or `Item 1 · Sunny (sunny)`.
- **Brightness.** For clocks that follow the sun, the ring is dimmed the way
  the automation would dim it at that time, and a line says the level.
- **Preview time.** For lists with times, like the price clock, drag the
  slider to see the ring at any later time the data covers. The app fetches
  the entity once and works the colours out itself. At "now" Home Assistant
  renders them.
- **Send this to the clock** shows the previewed colours on the real ring, so
  you can judge them on the wall. It sets the ring colours sensor in Home
  Assistant directly. The template puts the real colours back at its next
  update, within a minute. Press Stop to go back straight away.

### Layouts

| Layout | Input | What the ring does |
| --- | --- | --- |
| Timeline | a list of numbers with times | one LED per item, starting at now (the price clock) |
| States | a list of states | one LED per item (the weather clock) |
| Gauge | one number | the number fills the ring |
| Solid | one number | the whole ring takes the number's colour |
| State | one state | the whole ring takes the state's colour |

Numbers use a gradient bar. Click a dot on the bar to change that colour, or
pick a preset: cheap to expensive, green to red, cold to hot, or colour-blind
safe.
States use a table: a colour swatch, the state value and a definition in plain
words. **Fetch states from Home Assistant** fills in the values the entity
actually reports.

## Flashing

Open **Device**, then **Flash and back up**. The dialog lists anything that
would make the flash fail and links straight to the fix.

1. Plug the clock in over USB. The app finds its USB chip (CH340) and picks
   that serial port. Press the refresh button if you plugged it in after
   opening the dialog.
2. Press **Back up stock** once. The app reads all 4 MB, saves it in
   `~/.ring_studio/backups/`, then compares the file with the clock. The
   backup line turns green when the check passes.
3. Press **Flash over USB**. The first compile downloads the ESP8266 toolchain
   and takes a few minutes.
4. After that, use **Update over the air**. No cable needed.

**Restore stock** writes the backup back to the clock.

Every job shows as a list of steps that tick off as they finish, with a
progress bar. **Show details** opens the full output. If a step fails, the
details open by themselves.

## Export

**Export** writes real YAML into your repo folder. It shows every file as New,
Changed or Unchanged, and only writes the ones that differ. Press View to read
a file before writing it. For a changed file, View shows only what changed,
removed lines in red and added lines in green.

**Send straight to Home Assistant** writes one package file into Home
Assistant's `packages` folder and reloads templates and automations. A network
share works, for example `\\server\config\packages`. Home Assistant reads
packages only with this in `configuration.yaml`. Add it once, then restart
Home Assistant:

```yaml
homeassistant:
  packages: !include_dir_named packages
```

If `configuration.yaml` already has a `homeassistant:` section, add only the
`packages:` line inside it.

Files it writes:

    config/<name>.yaml                      ESPHome firmware
    config/secrets.yaml                     WiFi and keys
    homeassistant/ha_<name>_ring.yaml       template sensor
    homeassistant/automation.yaml           adaptive brightness

Keys are generated only when they are missing, or when you press Generate in
WiFi and keys. An existing key is never replaced on export.

## Keyboard

| Keys | Does |
| --- | --- |
| Ctrl+Z | Undo |
| Ctrl+Y or Ctrl+Shift+Z | Redo |
| Ctrl+E | Export |

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
