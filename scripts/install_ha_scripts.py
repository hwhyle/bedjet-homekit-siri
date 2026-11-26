#!/usr/bin/env python3
"""Create or update Home Assistant scripts from generate_config.py output.

Reads HA_URL and HA_TOKEN from the environment or a .env file.
This only writes the heat/cool scripts. It does not create or change a
HomeKit Bridge — do that in the Home Assistant UI (see the README).

Example:
    python3 scripts/install_ha_scripts.py --from homeassistant/generated/scripts.json
    python3 scripts/install_ha_scripts.py --from homeassistant/generated/scripts.json --dry-run
"""

from __future__ import annotations

import argparse
import json
import sys

from ha_client import HAError, die, request


def load_side_config(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    if "scripts" not in data:
        die(f"{path} does not contain a 'scripts' object. Pass scripts.json from generate_config.py.")
    return data


def install(object_id: str, payload: dict, dry_run: bool) -> None:
    path = f"/api/config/script/config/{object_id}"
    if dry_run:
        print(f"[dry-run] POST {path}  alias={payload.get('alias')}")
        return
    request("POST", path, body=payload)
    print(f"Installed script.{object_id}  ({payload.get('alias')})")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create or update BedJet heat/cool scripts via the Home Assistant API."
    )
    parser.add_argument(
        "--from",
        dest="source",
        default="homeassistant/generated/scripts.json",
        help="scripts.json from generate_config.py",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be sent without calling the API",
    )
    args = parser.parse_args()

    try:
        side_cfg = load_side_config(args.source)
    except FileNotFoundError:
        die(
            f"File not found: {args.source}\n"
            "Run generate_config.py first, or pass --from path/to/scripts.json"
        )
    except HAError as exc:
        die(str(exc))

    scripts = side_cfg["scripts"]
    try:
        for object_id, payload in scripts.items():
            install(object_id, payload, args.dry_run)
    except HAError as exc:
        die(str(exc))

    if args.dry_run:
        print("Dry run only — no changes were made.")
        return 0

    print()
    print("Scripts are in Home Assistant. Next:")
    print("  1. Settings -> Devices & Services -> Add Integration -> HomeKit Bridge.")
    print("  2. Include only these entities on a *new* bridge:")
    for object_id in scripts:
        print(f"       script.{object_id}")
    if side_cfg.get("fan_entity"):
        print(f"       {side_cfg['fan_entity']}")
    print("  3. Pair the bridge in the Apple Home app with the code from the")
    print("     Home Assistant persistent notification.")
    print("  See README.md for the full walkthrough.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
