# Pair the BedJet scripts and fan with Apple Home

Create a **new, dedicated HomeKit Bridge** that includes only the BedJet
scripts and the BedJet fan. Do not add these entities to an existing
bridge, and do not change an existing HomeKit entry.

## Recommended: Home Assistant UI

1. Confirm the scripts exist (Developer Tools → States, search `script.heat_`
   and `script.cool_`) and that the fan entity is present.
2. Optionally rename the fan in Home Assistant to a short Siri name such as
   **My BedJet**: Settings → Devices & Services → Entities → the fan →
   pencil icon. Long ESPHome prefixes make Siri less reliable.
3. Settings → Devices & Services → **Add Integration** → **HomeKit Bridge**.
4. When asked what to include, choose **include only specific entities**
   (wording may vary slightly by Home Assistant version). Select:
   - `script.heat_my_side` (or whatever IDs you generated, e.g. Heat My Side)
   - `script.cool_my_side`
   - the BedJet **fan** entity
   Do **not** include the climate entity. The scripts handle heat/cool, and
   the fan handles "set to 60 percent". The climate entity is awkward in
   Apple Home.
5. Finish the setup. Home Assistant will show a **persistent notification**
   with an 8-digit HomeKit pairing code (format `XXX-XX-XXX`) and the
   bridge name.
6. On an iPhone or iPad: open the **Home** app → Add Accessory →
   **More Options** (or "I Don't Have a Code or Cannot Scan") → select the
   new bridge. Enter the code from the notification.
7. Assign the accessories to the bedroom (or whichever room you want Siri
   to use). If a name looks long or ugly, rename it in the Home app — Siri
   uses the Home app name.

If the pairing code is rejected, open Home Assistant notifications and
use the **current** code for that exact bridge (codes can be rotated).
Reset or unpair only this new BedJet bridge; leave any other HomeKit
bridges alone.

## YAML alternative

See `homekit.yaml` in this folder, or the generated
`homeassistant/generated/homekit.yaml`. Restart Home Assistant after adding
it, then pair as in steps 5–7 above. Prefer a new list entry and a unique
`port` so an existing YAML or UI bridge is not disturbed.

## Siri phrases

Once the accessories show up in Apple Home:

- "Hey Siri, turn on Heat My Side"
- "Hey Siri, turn on Cool My Side"
- "Hey Siri, set My BedJet to 60 percent"
- "Hey Siri, turn off My BedJet"

Replace "My Side" / "My BedJet" with the names you chose.

If Siri cannot find a script by name, create an iOS Shortcut with that
phrase and have it run the matching Home accessory.
