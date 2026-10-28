# Ring Studio

A desktop app for LED ring clocks running ESPHome. It builds the ESPHome
firmware config, the Home Assistant template that colours the ring and the
brightness automation, from any Home Assistant entity. It also installs ESPHome
and esptool for you and flashes, backs up and restores the clock.

The clock itself stays simple. It shows whatever colours Home Assistant sends.
Changing what a clock shows only changes the Home Assistant template, so there
is no reflash.

Your work lives in a project file (`.ringstudio`) with notes for yourself.
Export turns it into clean YAML. Passwords and keys are kept in your system's
keychain, never in project files.

## Install and run

You need Python 3.11 or newer.

1. Unzip the folder anywhere.
2. Start the app:
   - **Windows:** double-click `run.bat`.
   - **Linux and macOS:** open a terminal in the folder and run `./run.sh`.

The first start creates a private Python environment (`.venv`) in the folder
and installs what the app needs into it. Later starts are quick. Nothing is
installed into the system Python, so this works on systems where pip may not
touch it, such as Arch, Debian 12 and Ubuntu 23.04 and newer.

ESPHome itself is installed the first time you flash or back up a clock.

To start from an example, choose **File, Open project** and pick one from the
`examples` folder (see Examples below).

### Arch Linux

Install Python and the two libraries the window needs, then run `./run.sh`:

```sh
sudo pacman -S --needed python gtk3 libsecret
```

- **Passwords and keys** go in GNOME Keyring or KWallet when one of them is
  running. On a window manager without either, they go in a file only your
  account can read (see Passwords and keys).
- **USB:** Arch gives the serial port to the `uucp` group. Add yourself once,
  then log out and back in:

  ```sh
  sudo usermod -aG uucp $USER
  ```

  The flash dialog also spots this and shows the command for your system.
- The CH340 USB chip needs no driver, it is part of the Arch kernel.

### Debian and Ubuntu

```sh
sudo apt install python3 python3-venv libgtk-3-0 libsecret-1-0
```

USB access needs the `dialout` group: `sudo usermod -aG dialout $USER`, then log
out and back in.

### Windows app

To get a `Ring Studio.exe` you can double-click:

1. Open a terminal in this folder on Windows.
2. Run `build_windows.bat`.
3. The app is in `dist\Ring Studio.exe`.

### Linux app

1. Open a terminal in this folder.
2. Run `./build_linux.sh`.
3. The app is in `dist/Ring Studio`, with a `Ring Studio.desktop` launcher next
   to it.

Both builds use the `.venv` folder too, so they also work on Arch.

The built apps still need Python on the computer for flashing, because ESPHome
is a Python program. The first flash creates a private environment for it in
the app's folder. If Python is missing, the flash dialog says how to install
it.

## The window

Everything happens in one window.

- **Top bar.** The **File** menu, the project name (a yellow dot means unsaved
  changes), undo and redo, the Home Assistant connection and Export.
- **Left.** Your clocks, each with a dot that is green when the clock is
  online. Click one to edit it. **Add clock** offers ready-made clocks:
  electricity price, weather, temperature, battery, calendar, clock hands or
  blank.
- **Middle.** The selected clock: its name, a notes box, and three sections you
  can fold away:
  - **What it shows.** Pick an entity and a layout, then set the colours.
  - **Brightness.** Night off and dimming that follows the sun. A bar chart
    shows today's brightness every half hour at your Home Assistant location.
    Set "Off from" to 24 to keep the ring on all night, dimmed by the sun.
  - **Device.** Online or offline, the firmware version and **Identify**,
    which shows a rainbow on that clock for 5 seconds. If the ESPHome
    installed here is newer than the clock's, a note offers the update. Then
    name, LED hardware, flashing, WiFi and keys. The hardware is one preset,
    EnergiKlockan EMIL (GPIO12, 36 LEDs, bit_bang, GRB). Open Custom
    hardware to change the raw values.
- **Right.** A live preview of the ring. At the current time Home Assistant
  renders the template, so the preview is exactly what the clock shows.

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
| Hands | the time | an analog clock: the hour and minute hands light up |

Numbers use a gradient bar. Click a dot on the bar to change that colour, or
pick a preset: cheap to expensive, green to red, cold to hot, or colour-blind
safe.

### The Hands layout

The ring becomes an analog clock and needs no entity, since Home Assistant's
clock drives it.

- **The hour hand** lights in the colour for the time of day. **The minute
  hand** lights in a lighter version of the same colour.
- **Colours through the day** is a gradient whose stops are spread evenly over
  24 hours, starting at midnight. The "Through the day" preset goes deep blue at
  night, orange at sunrise, warm white at midday, gold in the afternoon, red at
  sunset and purple in the evening.
- **Quarter marks** light 12, 3, 6 and 9 o'clock faintly. Set them to 0 to turn
  them off.
- **Face** is the colour of every other LED, black by default.
- **LED at 12 o'clock** and **LED order** match the ring on your wall. If the
  hands point to the wrong place, change the LED at 12 o'clock. If they move
  backwards, switch the order. Use **Send this to the clock** to check.

The template updates once a minute. With 36 LEDs, the minute hand moves one LED
every 1 to 2 minutes and the hour hand one LED every 20 minutes.

States use a table: a colour swatch, the state value, a definition in plain
words, and a note button for anything you want to remember about that state. **Fetch states from Home Assistant** fills in the values the entity
actually reports.

### Starter clocks

| Starter | Entity it starts with | Layout |
| --- | --- | --- |
| Electricity price | `sensor.swedish_spot_price_elpris_se3_forecast` | Timeline, 15-minute prices |
| Weather | `sensor.weather_hourly` | States, one LED per hour |
| Temperature | `sensor.outdoor_temperature` | Gauge, -20 to 30, cold to hot |
| Battery | `sensor.phone_battery_level` | Gauge, 0 to 100, red to green |
| Calendar | `calendar.home` | State, busy red, free green |
| Clock hands | none | Hands, colours through the day |
| Blank | none | Timeline |

Change the entity to your own after adding the clock.

The Weather starter colours every Home Assistant weather state. The colours are
picked for WS2812 LEDs: warm colours for dry daytime, blues for rain (deeper
for heavier), whites and cyans for snow and ice, purple for thunder, green for
wind, and red only for exceptional weather.

| State | Shown as | Colour |
| --- | --- | --- |
| sunny | Sunny | `#FFB000` |
| clear-night | Clear night | `#3020A0` |
| partlycloudy | Partly cloudy | `#FFE6A0` |
| cloudy | Cloudy | `#8090B0` |
| fog | Fog | `#C8C0B0` |
| rainy | Rain | `#0064FF` |
| pouring | Heavy rain | `#0010FF` |
| snowy | Snow | `#E0F0FF` |
| snowy-rainy | Sleet | `#80D0FF` |
| hail | Hail | `#40FFE0` |
| lightning | Thunder | `#A000FF` |
| lightning-rainy | Thunder and rain | `#6000FF` |
| windy | Windy | `#00D090` |
| windy-variant | Windy and cloudy | `#40A090` |
| exceptional | Exceptional | `#FF2000` |

LEDs never match a screen exactly. Use **Send this to the clock** to check
colours on the wall.

## Projects and notes

The **File** menu has New project, Open project, Save, Save as, Project notes
and Open repo.

A project is one `.ringstudio` file holding every clock, its colours, state
definitions, brightness settings, hardware and notes. It is plain YAML with
readable names, so you can also edit it by hand or keep it in git:

```yaml
ring_studio: 1
name: Home Clocks
note: Two clocks, one in the hallway and one in the kitchen.
clocks:
- name: weather_clock
  display_name: Weather Clock
  note: Hourly forecast, one LED per hour.
  hardware:
    data_pin: GPIO12
    leds: 36
  shows:
    layout: states
    entity: sensor.weather_hourly
    states:
      sunny:
        colour: '#FFB000'
        means: Sunny
        note: ''
```

Notes go in three places: the project (File, Project notes), each clock (the
box under its name) and each state (the note button on its row). Notes are
real fields in the file, so saving never loses or moves them. They are never
exported.

### Saving is safe

- Save writes to a temporary file first and only swaps it in once it is
  complete, so a crash or a full disk never leaves a broken project.
- The previous version is kept next to it as `<name>.ringstudio.bak`.
- Every edit is also autosaved to a draft. If the app closes before you save,
  your changes are restored the next time it starts, and a message says so.

### Opening a project is safe

A project file can come from someone else, so the app checks it before using
anything in it:

- It is read with a safe YAML reader that cannot run code.
- Pins must look like `GPIO12`. Driver, LED type and colour order must be one
  of the known values. Entities must look like `sensor.something`. These values
  end up inside the ESPHome firmware, so anything else could add components
  you did not ask for.
- Device names are turned into plain names (`../../x` becomes `x`), so export
  can never write outside the folder you chose.
- Display and effect names lose quotes, backslashes and line breaks.
- Numbers and colours are pulled back into range, for example at most 42 LEDs.

If anything fails, nothing changes and the app lists every problem in plain
words.

## Passwords and keys

WiFi, the hotspot password, the API key, the OTA password and the Home
Assistant token are never stored in project files or the draft. The app keeps
them in the system keychain:

| System | Where |
| --- | --- |
| Windows | Windows Credential Manager |
| macOS | Keychain |
| Linux desktop | GNOME Keyring or KWallet |
| Linux without a keychain | `~/.config/ring-studio/secrets.json`, readable only by your account |

**WiFi and keys** says which one is in use. Keys are generated only when they
are missing, or when you press Generate. An existing key is never replaced on
export. Keys found in an opened repo only fill keys you do not have yet, so a
repo with placeholder keys never overwrites yours.

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

**Restore stock** writes the backup back to the clock. It is greyed out until
a backup exists.

### USB on Linux

The flash dialog spots the two common problems and shows the fix:

- **No permission for the port.** Add yourself to the group that owns it,
  usually `dialout` (`uucp` on Arch): `sudo usermod -aG dialout $USER`, then
  log out and back in.
- **The port appears and then disappears.** On Ubuntu the braille service
  brltty takes over CH340 chips. Remove it with `sudo apt remove brltty`, then
  plug the clock in again.

Every job shows as a list of steps that tick off as they finish, with a
progress bar. **Show details** opens the full output. If a step fails, the
details open by themselves.

## Export

Export checks the project first and lists anything to fix. Then it writes
clean YAML: no notes, no explanations, only what ESPHome and Home Assistant
need, plus one first line saying where the file came from:

```yaml
# Made with Ring Studio from Home Clocks.ringstudio. Change it there.
```

Each Home Assistant template starts with its settings, one per line, followed
by the program that turns them into colours. The settings are part of the
template, and they are also how Open repo reads an exported repo back exactly.

**Export** writes into your repo folder. It shows every file as New,
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

Every file is written safely, the same way as Save. `secrets.yaml` is readable
only by your account. If the repo folder is a git repository, export adds
`config/secrets.yaml` to `.gitignore` so it cannot be committed by accident.

Files it writes:

    config/<name>.yaml                      ESPHome firmware
    config/secrets.yaml                     WiFi and keys
    homeassistant/ha_<name>_ring.yaml       template sensor
    homeassistant/automation.yaml           adaptive brightness
    <packages folder>/ring_studio.yaml      everything for Home Assistant in one file

## What the firmware has

Each clock's ESPHome config contains:

- **The ring light** with two effects: the one that shows Home Assistant's
  colours (named after the clock, for example Price Ring) and Rainbow Test.
  Identify uses Rainbow Test.
- **Ring Brightness**, a number the brightness automation sets.
- **ESPHome Version**, a sensor the app reads to show the firmware version.
  Clocks flashed before this sensor existed need one update over the air
  before the version shows.
- Home Assistant time, the encrypted API, OTA updates, and a fallback hotspot
  named after the clock if WiFi is unavailable.

## Keyboard

| Keys | Does |
| --- | --- |
| Ctrl+S | Save |
| Ctrl+Shift+S | Save as |
| Ctrl+Z | Undo |
| Ctrl+Y or Ctrl+Shift+Z | Redo |
| Ctrl+E | Export |

## Examples

The `examples` folder has ready-made projects. Open one, change the entities to
your own, then export.

| File | What it has |
| --- | --- |
| `Home Clocks.ringstudio` | a price clock and a weather clock together |
| `Price Clock.ringstudio` | 15-minute electricity prices |
| `Weather Clock.ringstudio` | the hourly forecast with the weather colours above |
| `Temperature Clock.ringstudio` | outdoor temperature as a gauge |
| `Battery Clock.ringstudio` | a battery level as a gauge |
| `Calendar Clock.ringstudio` | busy or free from a calendar |
| `Hands Clock.ringstudio` | an analog clock whose hands change colour through the day, on all night |

## Where the app keeps its files

| System | Folder |
| --- | --- |
| Windows | `%USERPROFILE%\.ring_studio` |
| macOS | `~/Library/Application Support/Ring Studio` |
| Linux | `~/.config/ring-studio` |

The folder holds settings, the draft, stock backups and the build folder used
for flashing.

## Opening an existing repo

**File, Open repo** takes a folder or a zip with the `config/` and
`homeassistant/` layout. Each matched set of files becomes a clock. The report
lists what it noticed, such as a clock no automation targets, with a one-click
fix where there is one. Save it as a project afterwards to keep notes with it.

Templates written by this app start with their settings block and are read back
exactly. Hand-written templates in the palette and `cap` style or the colour
map style are read from their `set` lines. Anything else is kept as it is.

## Tests

    pip install pytest
    python -m pytest tests
