# BedJet in Apple Home and Siri (via Home Assistant)

Control a [BedJet](https://www.bedjet.com/) V3 from Apple Home and Siri using
Home Assistant and an ESP32 running [ESPHome](https://esphome.io/).

This repository is a reusable template. It is not tied to one house, one
ESP32, or one BedJet. Helper scripts discover your BedJet's BLE MAC address
and your Home Assistant entity IDs so you only have to pick short names and
a couple of temperatures.

This is an unofficial project and is not affiliated with BedJet or Apple.

## What you get

- An ESPHome firmware template that talks to one or two BedJet V3 units over
  Bluetooth LE and exposes a **climate** entity (mode + temperature) and a
  **fan** entity (percentage) in Home Assistant.
- Home Assistant scripts: **Heat \<Side\>** and **Cool \<Side\>**.
- A dedicated **HomeKit Bridge** that exposes those scripts plus the fan, so
  you can say:
  - *"Hey Siri, turn on Heat My Side"*
  - *"Hey Siri, turn on Cool My Side"*
  - *"Hey Siri, set My BedJet to 60 percent"*
  - *"Hey Siri, turn off My BedJet"*

## Prerequisites

- A BedJet **V3** (the ESPHome component does not support V2).
- An **ESP32 board with Bluetooth LE**, placed close enough to the BedJet
  for a reliable BLE connection (original ESP32, ESP32-S3, or ESP32-C3).
- [Home Assistant](https://www.home-assistant.io/) with the ESPHome
  integration (Home Assistant OS, Container, or Supervised are all fine).
- An iPhone or iPad and a Home hub (HomePod, Apple TV, or iPad) if you want
  Siri to work when you are away from home.
- Python 3.9+ on the machine you use to run the helper scripts. The Home
  Assistant helpers use the standard library only. The BLE scanner needs
  `bleak` (`pip install -r scripts/requirements.txt`).

You should also know that **only one BLE client can be connected to a
BedJet at a time**. While the ESP32 is connected, the official BedJet
mobile app will not be able to control that unit. The template includes a
disconnect switch so you can free the radio when you want the app.

## Quick start

1. **Flash the ESP32** with `esphome/bedjet-proxy.yaml` (one unit) or
   `esphome/bedjet-proxy-dual.yaml` (two units). See
   [Step-by-step](#step-by-step) for secrets, board type, and MAC addresses.
2. When the device is online in Home Assistant, create a long-lived access
   token (Profile → Security) and put it in your environment — never in git:

   ```bash
   cp .env.example .env   # then edit .env
   # or:
   export HA_URL=http://homeassistant.local:8123
   export HA_TOKEN=your-long-lived-token
   ```

3. Discover entities, generate scripts, and optionally install them:

   ```bash
   python3 scripts/setup.py
   ```

   The same thing, split into steps:

   ```bash
   python3 scripts/discover_ha_entities.py --write discovered.json
   python3 scripts/generate_config.py --from discovered.json \
     --side-name "My Side" --fan-name "My BedJet"
   python3 scripts/install_ha_scripts.py --from homeassistant/generated/scripts.json
   ```

4. Create a **new** HomeKit Bridge that includes only those scripts and the
   fan, then pair it in the Apple Home app. Details are in
   [homeassistant/HOMEKIT.md](homeassistant/HOMEKIT.md).

## What you must change

| Variable | Where | Auto-discovered? | Example |
| --- | --- | --- | --- |
| BedJet BLE MAC address(es) | `esphome/bedjet-proxy.yaml` substitutions | **Yes** — `python3 scripts/discover_bedjet_ble.py`, or ESPHome logs | `AA:BB:CC:DD:EE:FF` |
| ESP32 board type | same file, `board:` | **No** — read the label on the board | `esp32dev`, `esp32-s3-devkitc-1`, `esp32-c3-devkitm-1` |
| Wi-Fi SSID and password | `esphome/secrets.yaml` | **No** | — |
| ESPHome API encryption key | `esphome/secrets.yaml` | **No** — generate with `openssl rand -base64 32` | — |
| OTA and fallback-AP passwords | `esphome/secrets.yaml` | **No** — choose unique passwords | — |
| Home Assistant URL | `HA_URL` env or `.env` | **No** — you already know it | `http://homeassistant.local:8123` |
| Home Assistant long-lived token | `HA_TOKEN` env or `.env` | **No** — create it in your profile | — |
| Climate and fan entity IDs | generated scripts / package | **Yes** — `discover_ha_entities.py` | `climate.bedjet_proxy_my_bedjet` |
| Lowest cool temperature | generated scripts | **Yes** — uses the climate entity's `min_temp` | often `66` (°F) |
| Siri side name | `setup.py` / `--side-name` | **No** — pick a short name | `My Side` |
| Siri fan name | `setup.py` / `--fan-name`, and optionally rename in HA / Home | **No** — pick a short name | `My BedJet` |
| Heat temperature | `--heat-temp` (default 90) | Default is fine to start | `90` |
| Fan percentage | `--fan-percent` (default 40) | Default is fine to start | `40` |
| HomeKit pairing code | Home Assistant notification | **Shown by Home Assistant** when the bridge is created | `XXX-XX-XXX` |

Copy `esphome/secrets.yaml.example` to `esphome/secrets.yaml` and
`.env.example` to `.env`. Both real files are gitignored. Never commit
tokens, Wi-Fi passwords, API keys, or pairing codes.

## Step-by-step

### 1. Find the BedJet MAC address

On a computer **near the BedJet** that has Bluetooth:

```bash
pip install -r scripts/requirements.txt
python3 scripts/discover_bedjet_ble.py
```

If the scanner is not an option, flash the ESP32 with a placeholder MAC,
watch the ESPHome logs, and look for a `BEDJET` advertisement and its
address, then update the substitution and flash again.

Close the BedJet mobile app while scanning or connecting — only one BLE
client can be attached at a time.

### 2. Flash ESPHome

1. Copy `esphome/secrets.yaml.example` to `esphome/secrets.yaml` and fill
   in Wi-Fi, an API key (`openssl rand -base64 32`), and passwords.
2. Edit the substitutions at the top of `esphome/bedjet-proxy.yaml`
   (or the dual-unit file): MAC address, short display name, and `board`.
3. Adopt the YAML in the ESPHome dashboard, or compile and flash with the
   ESPHome CLI / web flasher.
4. Add the new device in Home Assistant when it appears (ESPHome
   integration). You should get `climate.` and `fan.` entities shortly
   after the BLE connection succeeds.

If you already have an ESP32 nearby running as a Bluetooth proxy, you can
**add the `ble_client` / `bedjet` sections from the template to that
device's existing YAML** instead of flashing a second board. BedJet
control uses the ESPHome `bedjet` component on the ESP32 itself; it does
not go through Home Assistant's Bluetooth proxy stack.

The templates intentionally omit a device-level `friendly_name` so entity
names stay short enough for Siri.

### 3. Generate and install the Home Assistant scripts

Create a long-lived access token in Home Assistant (Profile → Security).
Export `HA_URL` and `HA_TOKEN` (or use a `.env` file) and run
`python3 scripts/setup.py`.

Default script behavior, matching a known-good setup:

- **Heat \<Side\>**: climate mode `heat`, target 90°F (or your unit), fan 40%.
- **Cool \<Side\>**: climate mode `fan_only` (this is how BedJet "cool"
  appears in Home Assistant), lowest allowed temperature, fan 40%. The
  temperature step uses `continue_on_error` because `fan_only` sometimes
  rejects a target temperature.

To configure a second BedJet (the other side of the bed), run setup again
with a different `--side` and `--side-name`.

If you would rather not use the API, copy the generated package from
`homeassistant/generated/bedjet_siri.yaml` into `/config/packages/` and
enable packages:

```yaml
# configuration.yaml
homeassistant:
  packages: !include_dir_named packages
```

Hand-edited templates with `CHANGE_ME` placeholders also live in
`homeassistant/`.

### 4. Expose them to Apple Home

Follow [homeassistant/HOMEKIT.md](homeassistant/HOMEKIT.md). The short
version: add a **new** HomeKit Bridge, include **only** the two scripts
and the fan (not the climate entity), then pair with the code in the
Home Assistant persistent notification.

## Helper scripts

| Script | What it does |
| --- | --- |
| `scripts/discover_bedjet_ble.py` | BLE scan for BedJet MAC addresses (`bleak`) |
| `scripts/discover_ha_entities.py` | Lists BedJet climate/fan entities via the HA REST API |
| `scripts/generate_config.py` | Fills in a package, `scripts.yaml`, a HomeKit snippet, and `scripts.json` |
| `scripts/install_ha_scripts.py` | Creates or updates the scripts through the HA API |
| `scripts/setup.py` | Walks through discovery → generate → optional install |

All Home Assistant scripts read `HA_URL` and `HA_TOKEN` from the
environment or `.env`. They never hardcode a token and they never print
it. `install_ha_scripts.py --dry-run` shows what would be posted without
making changes.

These helpers cannot configure ESP32 board type, Wi-Fi, or a HomeKit
Bridge. Those stay manual (board label, your network, and the Home
Assistant UI).

## Troubleshooting

**No BedJet in the BLE scan.** Stand closer, make sure the unit is powered,
quit the BedJet app, and try `--duration 20 --all`. You can also read the
MAC from ESPHome's `esp32_ble_tracker` logs.

**Climate or fan entities never appear.** Check that the ESP32 is online,
the MAC is correct, and the BLE connection switch is on. The ESP32 needs
to be close to the BedJet. Look at the ESPHome logs for connection errors.

**Cool mode does not reach the temperature you asked for.** This is a
known quirk. BedJet "cool" is `fan_only` in Home Assistant (it blows room
air; there is no compressor). A request for the lowest set point may be
ignored or the reported temperature may sit higher — in one test a 66°F
request landed around 74°F. The cool script still attempts the lowest
`min_temp` and continues if the temperature call fails. You can raise fan
speed to move more air.

**Siri does not understand the name.** Short names work better. Rename the
fan in Home Assistant and again in the Apple Home app if a long ESPHome
prefix is still showing. Avoid a device-level `friendly_name` in ESPHome.

**The HomeKit pairing code is rejected.** Use the current code in the
Home Assistant persistent notification for *this* bridge. If you have more
than one bridge, pick the new BedJet one, not an older "HASS Bridge". If
it still fails, unpair or reset only the new BedJet bridge so Home
Assistant issues a fresh code. Leave any other HomeKit bridges alone.

**The BedJet app cannot connect.** Turn off the BLE connection switch
exposed by the ESPHome template, use the app, then turn the switch back
on.

**OTA firmware updates time out with two BedJets.** The dual-unit template
disconnects both BLE clients at the start of OTA. You can also toggle the
switches off by hand before an update.

**`homeassistant.local` works in Safari but not in Chrome.** Chrome's
built-in async DNS can send `.local` lookups to a unicast DNS resolver
that does not know mDNS names. Disable
`chrome://flags/#built-in-async-dns`, or use the Home Assistant IP address,
or add a local DNS record for the hostname. This is optional and only
matters if you browse Home Assistant over a `.local` URL in Chrome.

## Climate modes and range

The ESPHome BedJet climate entity typically reports:

- HVAC modes: `off`, `heat`, `fan_only`, `dry`
- Presets: `boost`, `EXT HT`, `M1`, `M2`, `M3`
- Temperature range: about **66–109°F** (the helpers read the actual
  `min_temp` / `max_temp` from your entity)

`fan_only` is the mode used for cooling. `boost` is BedJet turbo heat;
`EXT HT` is extended heat.

## Security

- Do not commit `.env`, `esphome/secrets.yaml`, tokens, pairing codes, or
  generated files that contain your real entity IDs if you consider those
  private (`homeassistant/generated/` is gitignored).
- Give the long-lived token only to the machine that runs the helper
  scripts, and revoke it if it leaks.
- This project talks to *your* Home Assistant over the URL you set. The
  helpers will not work against someone else's system unless they set
  their own `HA_URL` and `HA_TOKEN`.

## License

[MIT](LICENSE)
