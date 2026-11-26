#!/usr/bin/env python3
"""Generate Home Assistant scripts (and a package file) for BedJet + Siri.

Reads discovery output from discover_ha_entities.py and fills in names,
temperatures, and fan speeds. Nothing in the output is specific to one
household unless you pass those values in.

Examples:
    python3 scripts/generate_config.py --from discovered.json
    python3 scripts/generate_config.py --from discovered.json \\
        --side-name "My Side" --fan-name "My BedJet" --heat-temp 90 --fan-percent 40
    python3 scripts/generate_config.py --from discovered.json --side 2 --side-name "Other Side"
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from typing import Any


def die(message: str, code: int = 1) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(code)


def number(value):
    """Render whole-number temperatures/percents without a trailing .0."""
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def slugify(name: str) -> str:
    slug = name.strip().lower()
    slug = slug.replace("'", "").replace("’", "")
    slug = re.sub(r"[^a-z0-9]+", "_", slug)
    return slug.strip("_") or "my_side"


def yaml_quote(value: str) -> str:
    if value == "":
        return '""'
    if re.search(r'[:#{}[\],&*?|<>=!%@`\'"]', value) or value[0].isspace() or value[-1].isspace():
        return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return value


def load_discovered(path: str) -> dict[str, Any]:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def pick_side(discovered: dict[str, Any], index: int | None) -> dict[str, Any]:
    sides = discovered.get("sides") or []
    if not sides:
        die("No BedJet sides in the discovery file. Re-run discover_ha_entities.py.")
    if index is None:
        if len(sides) == 1:
            return sides[0]
        die(
            f"Discovery found {len(sides)} BedJet climate entities. "
            "Pass --side N to choose one (1-based), or run setup.py."
        )
    if index < 1 or index > len(sides):
        die(f"--side must be between 1 and {len(sides)}")
    return sides[index - 1]


def script_payload(
    *,
    alias: str,
    icon: str,
    description: str,
    climate_entity: str,
    fan_entity: str | None,
    hvac_mode: str,
    temperature: float | int | None,
    fan_percent: int,
    continue_on_temp_error: bool = False,
) -> dict[str, Any]:
    sequence: list[dict[str, Any]] = [
        {
            "action": "climate.set_hvac_mode",
            "target": {"entity_id": climate_entity},
            "data": {"hvac_mode": hvac_mode},
        }
    ]
    if temperature is not None:
        temp_step: dict[str, Any] = {
            "action": "climate.set_temperature",
            "target": {"entity_id": climate_entity},
            "data": {"temperature": temperature},
        }
        if continue_on_temp_error:
            temp_step["continue_on_error"] = True
        sequence.append(temp_step)
    sequence.append(
        {
            "action": "climate.set_fan_mode",
            "target": {"entity_id": climate_entity},
            "data": {"fan_mode": f"{int(fan_percent)}%"},
        }
    )
    if fan_entity:
        sequence.append(
            {
                "action": "fan.set_percentage",
                "target": {"entity_id": fan_entity},
                "data": {"percentage": int(fan_percent)},
            }
        )
    return {
        "alias": alias,
        "icon": icon,
        "mode": "restart",
        "description": description,
        "sequence": sequence,
    }


def render_sequence(sequence: list[dict[str, Any]], indent: int) -> list[str]:
    pad = " " * indent
    lines: list[str] = []
    for step in sequence:
        lines.append(f"{pad}- action: {step['action']}")
        entity = step["target"]["entity_id"]
        lines.append(f"{pad}  target:")
        lines.append(f"{pad}    entity_id: {entity}")
        lines.append(f"{pad}  data:")
        for key, value in step["data"].items():
            if isinstance(value, str):
                rendered = yaml_quote(value)
            else:
                rendered = str(value)
            lines.append(f"{pad}    {key}: {rendered}")
        if step.get("continue_on_error"):
            lines.append(f"{pad}  continue_on_error: true")
    return lines


def render_script_entry(object_id: str, payload: dict[str, Any], indent: int) -> str:
    pad = " " * indent
    lines = [
        f"{pad}{object_id}:",
        f"{pad}  alias: {yaml_quote(payload['alias'])}",
        f"{pad}  icon: {payload['icon']}",
        f"{pad}  mode: {payload['mode']}",
        f"{pad}  description: {yaml_quote(payload['description'])}",
        f"{pad}  sequence:",
    ]
    lines.extend(render_sequence(payload["sequence"], indent + 4))
    return "\n".join(lines)


def build_side_config(args: argparse.Namespace, side: dict[str, Any], unit: str) -> dict[str, Any]:
    climate = args.climate or side.get("climate_entity")
    fan = args.fan if args.fan is not None else side.get("fan_entity")
    if not climate:
        die("No climate entity. Pass --climate or a discovery file that includes one.")

    side_name = args.side_name
    fan_name = args.fan_name
    heat_temp = number(args.heat_temp)
    fan_percent = number(args.fan_percent)
    cool_temp = args.cool_temp
    if cool_temp is None and side.get("min_temp") is not None:
        cool_temp = side["min_temp"]
    if cool_temp is None:
        cool_temp = 66
    cool_temp = number(cool_temp)

    heat_id = args.heat_id or f"heat_{slugify(side_name)}"
    cool_id = args.cool_id or f"cool_{slugify(side_name)}"

    unit_label = unit or "°"
    heat_alias = f"Heat {side_name}"
    cool_alias = f"Cool {side_name}"
    heat_desc = (
        f"Set {fan_name} to heat at {heat_temp}{unit_label} with fan at {fan_percent}%."
    )
    cool_desc = (
        f"Set {fan_name} to cool (fan_only) at the lowest temp ({cool_temp}{unit_label}) "
        f"with fan at {fan_percent}%."
    )

    heat = script_payload(
        alias=heat_alias,
        icon="mdi:heat-wave",
        description=heat_desc,
        climate_entity=climate,
        fan_entity=fan,
        hvac_mode="heat",
        temperature=heat_temp,
        fan_percent=fan_percent,
    )
    cool = script_payload(
        alias=cool_alias,
        icon="mdi:snowflake",
        description=cool_desc,
        climate_entity=climate,
        fan_entity=fan,
        hvac_mode="fan_only",
        temperature=cool_temp,
        fan_percent=fan_percent,
        continue_on_temp_error=True,
    )
    return {
        "side_name": side_name,
        "fan_name": fan_name,
        "climate_entity": climate,
        "fan_entity": fan,
        "heat_temp": heat_temp,
        "cool_temp": cool_temp,
        "fan_percent": fan_percent,
        "temperature_unit": unit,
        "heat_id": heat_id,
        "cool_id": cool_id,
        "scripts": {heat_id: heat, cool_id: cool},
    }


def render_package(side_cfg: dict[str, Any]) -> str:
    scripts = side_cfg["scripts"]
    fan = side_cfg["fan_entity"]
    lines = [
        "# Generated by scripts/generate_config.py — review, then copy into",
        "# Home Assistant as a package (see README) or install with",
        "# scripts/install_ha_scripts.py.",
        "#",
        f"# Side        : {side_cfg['side_name']}",
        f"# Fan name    : {side_cfg['fan_name']}",
        f"# Climate     : {side_cfg['climate_entity']}",
        f"# Fan entity  : {fan or '(none)'}",
        f"# Heat / Cool : {side_cfg['heat_temp']} / {side_cfg['cool_temp']}{side_cfg['temperature_unit']}",
        f"# Fan speed   : {side_cfg['fan_percent']}%",
        "",
        "script:",
    ]
    for object_id, payload in scripts.items():
        lines.append(render_script_entry(object_id, payload, 2))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_scripts_yaml(side_cfg: dict[str, Any]) -> str:
    """Stand-alone scripts.yaml fragment (no top-level 'script:' key)."""
    lines = [
        "# Generated by scripts/generate_config.py",
        "# Merge into configuration.yaml under 'script:' or use the package file.",
        "",
    ]
    for object_id, payload in side_cfg["scripts"].items():
        lines.append(render_script_entry(object_id, payload, 0))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_homekit_snippet(side_cfg: dict[str, Any]) -> str:
    fan = side_cfg["fan_entity"]
    include = [
        f"script.{side_cfg['heat_id']}",
        f"script.{side_cfg['cool_id']}",
    ]
    if fan:
        include.append(fan)
    lines = [
        "# Optional YAML alternative to the HomeKit Bridge UI flow in the README.",
        "# If you already have a HomeKit Bridge, add a *new* list entry rather",
        "# than editing an existing one, so other accessories stay untouched.",
        "# A dedicated port avoids colliding with an existing bridge.",
        "",
        "homekit:",
        "  - name: BedJet Bridge",
        "    port: 21065",
        "    filter:",
        "      include_entities:",
    ]
    for eid in include:
        lines.append(f"        - {eid}")
    lines.append("    entity_config:")
    if fan:
        lines.append(f"      {fan}:")
        lines.append(f"        name: {yaml_quote(side_cfg['fan_name'])}")
    lines.append(f"      script.{side_cfg['heat_id']}:")
    lines.append(f"        name: {yaml_quote('Heat ' + side_cfg['side_name'])}")
    lines.append(f"      script.{side_cfg['cool_id']}:")
    lines.append(f"        name: {yaml_quote('Cool ' + side_cfg['side_name'])}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate Home Assistant BedJet scripts from discovered entities."
    )
    parser.add_argument(
        "--from",
        dest="source",
        default="discovered.json",
        help="JSON from discover_ha_entities.py (default: discovered.json)",
    )
    parser.add_argument(
        "--side",
        type=int,
        help="Which discovered climate entity to use (1-based). Optional if only one was found.",
    )
    parser.add_argument("--climate", help="Override climate entity_id")
    parser.add_argument("--fan", help="Override fan entity_id")
    parser.add_argument(
        "--side-name",
        default="My Side",
        help='Short name used in Siri phrases, e.g. "My Side" -> "Hey Siri, turn on Heat My Side"',
    )
    parser.add_argument(
        "--fan-name",
        default="My BedJet",
        help='Short name for the fan in Apple Home, e.g. "My BedJet"',
    )
    parser.add_argument("--heat-temp", type=float, default=90, help="Heat target temperature (default: 90)")
    parser.add_argument(
        "--cool-temp",
        type=float,
        help="Cool target temperature (default: the climate entity's min_temp)",
    )
    parser.add_argument("--fan-percent", type=int, default=40, help="Fan percentage (default: 40)")
    parser.add_argument("--heat-id", help="Script object id for heat (default: heat_<slug>)")
    parser.add_argument("--cool-id", help="Script object id for cool (default: cool_<slug>)")
    parser.add_argument(
        "--out",
        default="homeassistant/generated",
        help="Output directory (default: homeassistant/generated)",
    )
    args = parser.parse_args()

    if args.climate and not os.path.isfile(args.source):
        discovered = {"sides": [{}], "temperature_unit": ""}
        side: dict[str, Any] = {}
    else:
        if not os.path.isfile(args.source):
            die(
                f"Discovery file not found: {args.source}\n"
                "Run: python3 scripts/discover_ha_entities.py --write discovered.json"
            )
        discovered = load_discovered(args.source)
        side = pick_side(discovered, args.side)

    unit = discovered.get("temperature_unit") or ""
    side_cfg = build_side_config(args, side, unit)

    out_dir = args.out
    os.makedirs(out_dir, exist_ok=True)
    package_path = os.path.join(out_dir, "bedjet_siri.yaml")
    scripts_path = os.path.join(out_dir, "scripts.yaml")
    homekit_path = os.path.join(out_dir, "homekit.yaml")
    json_path = os.path.join(out_dir, "scripts.json")

    with open(package_path, "w", encoding="utf-8") as fh:
        fh.write(render_package(side_cfg))
    with open(scripts_path, "w", encoding="utf-8") as fh:
        fh.write(render_scripts_yaml(side_cfg))
    with open(homekit_path, "w", encoding="utf-8") as fh:
        fh.write(render_homekit_snippet(side_cfg))
    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(side_cfg, fh, indent=2)
        fh.write("\n")

    print(f"Wrote {package_path}")
    print(f"Wrote {scripts_path}")
    print(f"Wrote {homekit_path}")
    print(f"Wrote {json_path}")
    print()
    print("Install the scripts either by:")
    print(f"  - Copying {package_path} into /config/packages/ on Home Assistant, or")
    print("  - python3 scripts/install_ha_scripts.py --from", json_path)
    print()
    print("Then expose these entities on a *new* HomeKit Bridge (see README):")
    print(f"  script.{side_cfg['heat_id']}")
    print(f"  script.{side_cfg['cool_id']}")
    if side_cfg["fan_entity"]:
        print(f"  {side_cfg['fan_entity']}")
    else:
        print("  (no fan entity was found — Siri percentage control will be missing)")
    print()
    print("Siri phrases once the bridge is paired:")
    print(f'  "Hey Siri, turn on Heat {side_cfg["side_name"]}"')
    print(f'  "Hey Siri, turn on Cool {side_cfg["side_name"]}"')
    if side_cfg["fan_entity"]:
        print(f'  "Hey Siri, set {side_cfg["fan_name"]} to 60 percent"')
        print(f'  "Hey Siri, turn off {side_cfg["fan_name"]}"')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
