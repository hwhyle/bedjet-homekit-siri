#!/usr/bin/env python3
"""Find BedJet climate and fan entities in a Home Assistant instance.

Reads HA_URL and HA_TOKEN from the environment or a .env file.
Never hardcode a token. The token is not printed.

Example:
    export HA_URL=http://homeassistant.local:8123
    export HA_TOKEN=your-long-lived-token
    python3 scripts/discover_ha_entities.py --write discovered.json
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from ha_client import HAError, die, get_json


BEDJET_PRESETS = {"boost", "ext ht", "m1", "m2", "m3"}
BEDJET_MODES = {"off", "heat", "fan_only", "dry"}


def looks_like_bedjet(entity: dict[str, Any]) -> bool:
    eid = (entity.get("entity_id") or "").lower()
    attrs = entity.get("attributes") or {}
    name = (attrs.get("friendly_name") or "").lower()
    blob = f"{eid} {name}"
    if "bedjet" in blob or "bed_jet" in blob or "bed jet" in blob:
        return True
    domain = eid.split(".", 1)[0]
    if domain == "climate":
        modes = {str(m).lower() for m in attrs.get("hvac_modes") or []}
        presets = {str(p).lower() for p in attrs.get("preset_modes") or []}
        if BEDJET_MODES.issubset(modes) and BEDJET_PRESETS.issubset(presets):
            return True
    return False


def pair_fans(
    climates: list[dict[str, Any]], fans: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Match each climate entity with the most likely fan entity."""
    unused = list(fans)
    pairs: list[dict[str, Any]] = []
    for climate in climates:
        cid = climate["entity_id"]
        stem = cid.split(".", 1)[1]
        best = None
        best_score = -1
        for fan in unused:
            fid = fan["entity_id"]
            fstem = fid.split(".", 1)[1]
            score = 0
            if fstem == stem + "_fan" or fstem == stem:
                score = 100
            elif stem in fstem or fstem.replace("_fan", "") == stem:
                score = 80
            else:
                # common prefix length
                common = 0
                for a, b in zip(stem, fstem):
                    if a != b:
                        break
                    common += 1
                score = common
            if score > best_score:
                best = fan
                best_score = score
        if best is not None and best_score >= 8:
            unused.remove(best)
            fan_entity = best
        else:
            fan_entity = None
        cattrs = climate.get("attributes") or {}
        fattrs = (fan_entity or {}).get("attributes") or {}
        pairs.append(
            {
                "climate_entity": cid,
                "climate_name": cattrs.get("friendly_name") or cid,
                "climate_state": climate.get("state"),
                "fan_entity": fan_entity["entity_id"] if fan_entity else None,
                "fan_name": fattrs.get("friendly_name") if fan_entity else None,
                "fan_state": fan_entity.get("state") if fan_entity else None,
                "min_temp": cattrs.get("min_temp"),
                "max_temp": cattrs.get("max_temp"),
                "hvac_modes": cattrs.get("hvac_modes"),
                "preset_modes": cattrs.get("preset_modes"),
                "fan_modes": cattrs.get("fan_modes"),
                "percentage_step": fattrs.get("percentage_step") if fan_entity else None,
            }
        )
    leftover = []
    for fan in unused:
        fattrs = fan.get("attributes") or {}
        leftover.append(
            {
                "fan_entity": fan["entity_id"],
                "fan_name": fattrs.get("friendly_name"),
                "fan_state": fan.get("state"),
            }
        )
    return pairs, leftover


def discover() -> dict[str, Any]:
    config = get_json("/api/config")
    states = get_json("/api/states")
    climates = [
        s
        for s in states
        if str(s.get("entity_id", "")).startswith("climate.") and looks_like_bedjet(s)
    ]
    fans = [
        s
        for s in states
        if str(s.get("entity_id", "")).startswith("fan.") and looks_like_bedjet(s)
    ]
    climates.sort(key=lambda s: s["entity_id"])
    fans.sort(key=lambda s: s["entity_id"])
    sides, leftover_fans = pair_fans(climates, fans)
    unit = ((config.get("unit_system") or {}).get("temperature")) or ""
    return {
        "ha_version": config.get("version"),
        "temperature_unit": unit,
        "sides": sides,
        "unpaired_fans": leftover_fans,
        "climate_count": len(climates),
        "fan_count": len(fans),
    }


def print_table(result: dict[str, Any]) -> None:
    unit = result.get("temperature_unit") or ""
    print(
        f"Home Assistant {result.get('ha_version') or '?'}  "
        f"temperature unit: {unit or 'unknown'}"
    )
    print()
    if not result["sides"]:
        print("No BedJet climate entities were found.")
        print()
        print("Tips:")
        print("  - Confirm the ESP32 is flashed, online, and adopted in ESPHome.")
        print("  - Climate entities usually appear once the BLE connection succeeds.")
        print("  - Names should contain 'BedJet', or match BedJet HVAC/preset modes.")
        return

    print(f"Found {len(result['sides'])} BedJet climate entity(ies):\n")
    for i, side in enumerate(result["sides"], start=1):
        print(f"  [{i}] Climate : {side['climate_entity']}")
        print(f"      Name    : {side['climate_name']}  (state: {side['climate_state']})")
        if side["min_temp"] is not None:
            print(
                f"      Range   : {side['min_temp']}–{side['max_temp']}{unit}  "
                f"modes: {', '.join(side.get('hvac_modes') or [])}"
            )
        if side["fan_entity"]:
            print(f"      Fan     : {side['fan_entity']}")
            print(f"      Fan name: {side['fan_name']}  (state: {side['fan_state']})")
        else:
            print("      Fan     : (none matched — pass --fan later when generating)")
        print()

    if result["unpaired_fans"]:
        print("Fan entities that look like a BedJet but were not paired:")
        for fan in result["unpaired_fans"]:
            print(f"  {fan['fan_entity']}  ({fan['fan_name']})")
        print()

    print("Next: generate Home Assistant scripts from this list:")
    print("  python3 scripts/generate_config.py --from discovered.json")
    print("Or run the guided setup:")
    print("  python3 scripts/setup.py")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="List BedJet climate/fan entities from the Home Assistant API."
    )
    parser.add_argument(
        "--write",
        "-o",
        default="discovered.json",
        help="Write discovery JSON here (default: discovered.json)",
    )
    parser.add_argument(
        "--no-write",
        action="store_true",
        help="Do not write a file; only print the report",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print JSON instead of a human-readable table",
    )
    args = parser.parse_args()

    try:
        result = discover()
    except HAError as exc:
        die(str(exc))

    if not args.no_write:
        with open(args.write, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=2)
            fh.write("\n")
        if not args.json:
            print(f"Wrote {args.write}\n")

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print_table(result)

    return 0 if result["sides"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
