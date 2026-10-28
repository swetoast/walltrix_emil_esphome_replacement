# Ring Studio

Design, preview and flash LED ring clocks that show Home Assistant data. The
clocks run ESPHome and talk only to your Home Assistant, never to the internet.

![Ring Studio previewing tomorrow's electricity prices on a price clock](docs/main-window.png)

## Highlights

- Colour a 36 LED ring from any Home Assistant entity: electricity prices, the
  weather forecast, a temperature, a battery level, a calendar or the time.
- Preview the ring at any time the data covers, then push the preview to the
  real clock to check it on the wall.
- Build any clock from scratch: click any value in an entity's data, then pick
  any colour, as a smooth gradient or as named steps from a value up.
- Prefer text? Switch to the YAML view and write the whole project by hand,
  with autocomplete and problems marked on their line.
- Pick entities by name. The app reads their data and fills in the settings.
- Back up, flash and restore the clock over USB, then update it over WiFi.
  ESPHome is installed for you.
- Keep your work in a project file with notes. Export writes clean YAML.
- Passwords and keys stay in your system keychain.
- Runs on Windows, Linux (including Arch) and macOS.

## How it works

Home Assistant does the work. A template sensor turns your entity into 36
colours, one per LED, and the clock shows the colours it receives. Changing
what a clock shows only changes the template, so the clock is not reflashed
for that.

Ring Studio writes both parts: the ESPHome firmware for the clock, and the Home
Assistant template and brightness automation. It previews the result with live
data from your Home Assistant.

## Requirements

| | |
| --- | --- |
| Python | 3.11 or newer |
| Home Assistant | a recent version and a [long-lived access token](https://www.home-assistant.io/docs/authentication/#managing-account-access) |
| Clock | an ESP8266 with a WS2812 ring. Tested on the EnergiKlockan EMIL (GPIO12, 36 LEDs) |
| Cable | a USB data cable for the first flash. Later updates go over WiFi |

## Install

Download this folder, then start the app:

- **Windows:** double-click `run.bat`.
- **Linux and macOS:** open a terminal in the folder and run `./run.sh`.

The first start creates a private Python environment in `.venv` and installs
what the app needs into it. Nothing is installed into your system Python.

On **Arch Linux**, install these packages first:

```sh
sudo pacman -S --needed python gtk3 libsecret
```

On **Debian and Ubuntu**:

```sh
sudo apt install python3 python3-venv libgtk-3-0 libsecret-1-0
```

## Quick start

The app opens with the Home Clocks example and sample data, so you can try
everything before connecting anything. A short welcome explains the three ways
in, and **File** > **Getting started** shows it again.

![The welcome on first start, over the Home Clocks example](docs/welcome.png)

1. Look around: pick a clock on the left, click what it shows in **Data**,
   change its **Colours** and drag **Preview time**. **File** > **Open example** has six more examples, and
   **Add clock** starts a clock from a ready-made one.
2. Click **Connect Home Assistant**. Enter its address and paste a long-lived
   access token.
3. In **Data**, click **Change** and pick your entity. The app colours the ring
   by the most likely value. Click another value in the data to use that one.
4. Check the ring on the right. Drag **Preview time** to see later hours.
5. Plug in the clock. In **Device**, click **Flash and back up**, then
   **Back up stock**, then **Flash over USB**.
6. In Home Assistant, open **Settings** > **Devices & services**. The clock is
   found automatically. When asked for the encryption key, paste the API key
   shown in **WiFi and keys**.
7. Click **Export** and write the files to your Home Assistant config, or turn
   on **Send straight to Home Assistant**.

> [!WARNING]
> Back up the stock firmware before the first flash. It is the only way back to
> the original firmware.

![The Add a clock dialog with seven starters](docs/add-clock.png)

## Using Ring Studio

### Building a clock

![The editor with Data, Colours and Ring, coloured by four named steps](docs/build-a-clock.png)

Each clock is set up in three steps.

**1 Data.** Choose **An entity** or **The time (clock hands)**. For an entity,
the app lists everything it holds: the state, every attribute and the fields
inside its lists, each with a sample value. Click the one the ring should show.
What you click decides the rest:

| You click | The ring shows |
| --- | --- |
| a number inside a list | one LED per item, coloured by that number |
| a text inside a list | one LED per item, one colour per text value |
| the state or an attribute holding a number | the number, as a fill or on the whole ring |
| the state or an attribute holding text | the whole ring, one colour per text value |

Times inside lists are found by themselves and tagged **start** and **end**.
**Advanced** shows every field to type by hand, for entities the app has no
data for yet.

**2 Colours.** Numbers are coloured in one of two ways:

- **Gradient**: colours blend smoothly from one value to the next. Click the
  bar to add a colour at that value, or click a colour to change it or the
  value it sits at. Ticks above the bar show the values in the data, so you can
  see where they fall. **Spread evenly** puts the colours back at equal
  distances.
- **Steps**: each colour starts at its **From** value and lasts until the next
  step, for example Cheap from 0, Normal from 50, Pricey from 100. Step names
  show in the legend and when you point at an LED.

**Multiply values by** scales every value first, for example 100 to work in
öre instead of SEK. **Below the first colour** and **No data** set the colours
for values under the range and for LEDs without data.

Text gets a table with a colour, the value, what it means in plain words and
an optional note. **Add the values in the data** adds every value the entity
holds right now.

**3 Ring.** How the colours are laid out:

| Data | Choices |
| --- | --- |
| a list | **From now**, one LED per item, or a **24-hour dial** |
| one number | **Fill**, with **Empty at** and **Full at**, or **Whole ring** |
| the time | **Quarter marks** and the hands |

The 24-hour dial puts midnight at the top and keeps every hour in its place,
00-01, 01-02 and so on, showing the next 24 hours. With 36 LEDs the hours take
1 or 2 LEDs each, because 36 does not split evenly into 24. The current hour is
the bright one. If the hours or hands sit in the wrong place, change **LED at
12 o'clock** or **LED order**.

### Picking colours

![The colour picker with hue, saturation and brightness](docs/colour-picker.png)

Any colour works. Drag **Hue**, **Saturation** and **Brightness**, type a hex
value, or click a recent colour or a preset. The row of dots shows the colour
as the ring shows it, from full brightness to dim. For gradient colours and
steps, **At value** moves the colour to another value.

### The YAML view

![The YAML view with a problem marked on line 25](docs/yaml-view.png)

Click **YAML** at the top to edit the whole project as text. Everything the
editor can do is here, and the editor shows whatever you type.

- Changes apply as you type. The preview follows every valid version.
- A problem is marked on its line, with what is wrong. Until it is fixed, the
  preview keeps the last valid version.
- Autocomplete offers field names and values. **Fields** lists every field with
  what it takes, and has a search.
- The other tabs show what **Export** writes for the selected clock: the
  ESPHome firmware, the Home Assistant template and the automation. They are
  read only. Secrets are never shown.
- Notes belong in the `note` fields. YAML comments starting with `#` are not
  kept.

### Choosing an entity

Click **Change** next to the entity to open the picker.

![The entity picker showing the attributes of the hourly weather sensor](docs/entity-picker.png)

- Search by name or entity ID.
- **Fits** lists only entities whose data suits the clock.
  **All entities** lists everything.
- Click an entity to see its value, its attributes and what the app will set.
- **Reload from Home Assistant** fetches fresh data.

### Preview

Before Home Assistant is connected, the examples preview with sample data, and
the line under the ring says so. Once connected, the preview uses your data.

- Point at an LED to see its time and value, for example
  `LED 13 · Tomorrow 17:30 · 0.26335 SEK/kWh`, or on a 24-hour dial
  `LED 1 · 00-01 Tomorrow · Partly cloudy (partlycloudy)`.
- Drag **Preview time** to see the ring later today or tomorrow.
- For clocks that follow the sun, the preview is dimmed as the clock will be at
  that time.
- **Send this to the clock** shows the preview on the real ring until the
  template next updates, within a minute. **Stop** ends it at once.

### Hands layout

![The Hands layout with the day colour gradient](docs/hands-layout.png)

The ring becomes an analog clock. It needs no entity.

- The hour hand shows the colour for the time of day. The minute hand shows a
  lighter version of the same colour.
- The colours are spread over 24 hours, starting at midnight. The hour under
  each colour shows where it falls.
- **Quarter marks** light 12, 3, 6 and 9 o'clock. Set them to 0 to turn them
  off.
- If the hands point to the wrong place, change **LED at 12 o'clock**. If they
  move backwards, switch **LED order**.

### Brightness

One shared automation dims the ring with the sun and turns it off at night. A
bar chart shows today's brightness every half hour at your Home Assistant
location. Set **Off from** to 24 to keep the ring on all night.

### Projects and notes

**File** has New project, Open project, Open example, Save, Save as, Project
notes and Getting started. A project is one `.ringstudio` file in plain YAML:

```yaml
ring_studio: 1
name: Home Clocks
clocks:
- name: weather_clock
  display_name: Weather Clock
  note: Hourly forecast, one LED per hour.
  shows:
    layout: states
    entity: sensor.weather_hourly
    states:
      sunny:
        colour: '#FFB000'
        means: Sunny
- name: price_clock
  display_name: Price Clock
  shows:
    layout: timeline
    entity: sensor.swedish_spot_price_elpris_se3_forecast
    list_attributes: [today, tomorrow]
    item_key: SEK_per_kWh
    multiply_by: 100
    colour_by: steps
    steps:
    - {from: 0, colour: '#00C853', means: Cheap}
    - {from: 50, colour: '#FFD700', means: Normal}
    - {from: 100, colour: '#FF7800', means: Pricey}
```

Notes can go on the project, on each clock and on each state. They stay in the
project file and are never exported.

Each save keeps the previous version as `<name>.ringstudio.bak`. Edits are also
kept in a draft, so unsaved changes come back if the app closes.

An example opens as "(example)" in the title. **Save** asks where to keep your
own copy, so the examples themselves never change.

### Flashing

![The flash dialog after a stock backup](docs/flash-dialog.png)

**Device** > **Flash and back up** lists anything that would make the flash
fail, with a button to fix it.

| Button | What it does |
| --- | --- |
| Back up stock | reads all 4 MB from the clock and checks the copy |
| Flash over USB | compiles and flashes ESPHome. The first compile downloads the toolchain and takes a few minutes |
| Update over the air | the same over WiFi, after the first flash |
| Restore stock | writes the backup back to the clock |

Each job shows its steps with a progress bar. **Show details** opens the full
output, and opens by itself if a step fails.

### Export

**Export** writes only the files that are new or changed. **View** shows a
file, or only the changed lines of a changed file.

| File | Contents |
| --- | --- |
| `config/<name>.yaml` | ESPHome firmware |
| `config/secrets.yaml` | WiFi and keys |
| `homeassistant/ha_<name>_ring.yaml` | template sensor |
| `homeassistant/automation.yaml` | brightness automation |
| `<packages folder>/ring_studio.yaml` | everything for Home Assistant in one package |

Exported files have no notes or comments, only a first line naming the project
they came from.

**Send straight to Home Assistant** writes the package into Home Assistant's
packages folder, for example `\\server\config\packages`, and reloads it.
Packages must be turned on once in `configuration.yaml`:

```yaml
homeassistant:
  packages: !include_dir_named packages
```

### Keyboard shortcuts

| Keys | Action |
| --- | --- |
| `Ctrl`+`S` | Save |
| `Ctrl`+`Shift`+`S` | Save as |
| `Ctrl`+`Z` | Undo (in the YAML view, undo typing) |
| `Ctrl`+`Y` | Redo |
| `Ctrl`+`E` | Export |

## Examples

Seven example projects come with the app. Open them with **File** > **Open
example**, change the entities to your own, then save your own copy. Until Home
Assistant is connected they preview with sample data.

![The six example clocks](docs/examples.png)

| Example | Contents |
| --- | --- |
| Home Clocks | the price clock and the weather clock together |
| Price Clock | 15-minute electricity prices for SE3 |
| Weather Clock | the hourly forecast on a 24-hour dial |
| Temperature Clock | outdoor temperature as a gauge, -20 to 30 |
| Battery Clock | a battery level as a gauge |
| Calendar Clock | red while a calendar event is on, green when free |
| Hands Clock | an analog clock that stays on all night |

<details>
<summary>Weather colours</summary>

Warm colours are dry daytime, blues are rain, whites and cyans are snow and ice,
purple is thunder, green is wind and red is exceptional weather.

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

</details>

The screenshots were taken from the app with sample Home Assistant data at
15:07. The previews are dimmed by the brightness automation for that time of
day.

## Security

WiFi passwords, API and OTA keys and the Home Assistant token are kept in the
system keychain: Windows Credential Manager, macOS Keychain, or GNOME Keyring or
KWallet on Linux. Without a keychain they go in
`~/.config/ring-studio/secrets.json`, readable only by your account. They are
never written to project files, the draft or the settings.

<details>
<summary>Details</summary>

- The token goes only to the address you entered, never on a redirect, and
  certificates are always checked. A plain `http://` address outside your home
  network shows a warning.
- The fallback hotspot gets a random password, so nobody nearby can join it and
  change the clock's WiFi.
- Project files from other people are checked before use. Pins, boards,
  entities and names that could change the firmware are refused.
- `secrets.yaml` is readable only by you, is added to `.gitignore` in git repos
  and is never shown in **View**. Export warns if git already tracks it.
- The app folder, stock backups and the flash build are readable only by you.
  The build's copy of `secrets.yaml` is deleted after each flash.
- ESPHome and esptool run with fixed arguments, never through a shell.

</details>

## Troubleshooting

| Problem | Fix |
| --- | --- |
| "The token was not accepted" | Make a new long-lived token in your Home Assistant profile and paste it again. |
| No serial port on Ubuntu | The braille service takes the CH340 chip. Run `sudo apt remove brltty` and plug the clock in again. |
| Permission denied on the port | Add yourself to the port's group and log in again: `sudo usermod -aG dialout $USER` (`uucp` on Arch). |
| "Python was not found" when flashing from a built app | Install Python 3.11 or newer. On Windows, tick "Add python.exe to PATH". |
| The hands or the dial hours are in the wrong place | Change **LED at 12 o'clock** or **LED order**. |
| The clock does not appear in Home Assistant | Check the WiFi name and password in **WiFi and keys**, then flash again. |

## Where the app keeps its files

| System | Folder |
| --- | --- |
| Windows | `%USERPROFILE%\.ring_studio` |
| macOS | `~/Library/Application Support/Ring Studio` |
| Linux | `~/.config/ring-studio` |

The folder holds settings, the draft, stock backups and the flash build.

## Building a standalone app

Run `build_windows.bat` on Windows or `./build_linux.sh` on Linux. The app is
written to `dist/`. Flashing from a built app still needs Python on the
computer, because ESPHome is a Python program.

## Development

```sh
python -m venv .venv
.venv/bin/pip install -r requirements.txt pytest
.venv/bin/python -m pytest tests
```

The tests work out the expected colours independently and compare them with
the template, including a real hourly forecast on the 24-hour dial. They also
check the examples, project files and the security rules above.

## Feedback

Bug reports and ideas are welcome as GitHub issues.
