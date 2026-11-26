#!/usr/bin/env python3
"""Guided setup: discover BedJet entities, generate scripts, optionally install.

This is the least manual path once the ESP32 is flashed and talking to
Home Assistant. It does not flash firmware or create a HomeKit Bridge.

    export HA_URL=http://homeassistant.local:8123
    export HA_TOKEN=your-long-lived-token
    python3 scripts/setup.py
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

from ha_client import HAError, die, get_credentials, load_dotenv


def repo_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def scripts_dir() -> str:
    return os.path.dirname(os.path.abspath(__file__))


def prompt(label: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default is not None else ""
    try:
        value = input(f"{label}{suffix}: ").strip()
    except EOFError:
        die("No input available. Re-run with flags (see --help) or a TTY.")
    if not value and default is not None:
        return default
    return value


def prompt_yes(label: str, default: bool = False) -> bool:
    hint = "Y/n" if default else "y/N"
    value = prompt(f"{label} ({hint})", "").lower()
    if not value:
        return default
    return value in {"y", "yes"}


def run_module(script_name: str, argv: list[str]) -> int:
    path = os.path.join(scripts_dir(), script_name)
    return subprocess.call([sys.executable, path, *argv], cwd=repo_root())


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Discover BedJet entities and generate (and optionally install) HA scripts."
    )
    parser.add_argument("--side-name", help='Siri name for the side, default "My Side"')
    parser.add_argument("--fan-name", help='Siri name for the fan, default "My BedJet"')
    parser.add_argument("--heat-temp", type=float, help="Heat target (default: 90)")
    parser.add_argument("--cool-temp", type=float, help="Cool target (default: entity min_temp)")
    parser.add_argument("--fan-percent", type=int, help="Fan percentage (default: 40)")
    parser.add_argument("--side", type=int, help="1-based climate entity if several are found")
    parser.add_argument("--install", action="store_true", help="Install scripts via the HA API without asking")
    parser.add_argument("--no-install", action="store_true", help="Never install; only generate files")
    parser.add_argument(
        "--out",
        default="homeassistant/generated",
        help="Output directory (default: homeassistant/generated)",
    )
    args = parser.parse_args()

    load_dotenv()
    os.chdir(repo_root())

    try:
        url, _token = get_credentials()
    except HAError as exc:
        die(str(exc))
    print(f"Using Home Assistant at {url}")
    print()

    discovered_path = "discovered.json"
    rc = run_module("discover_ha_entities.py", ["--write", discovered_path])
    if rc != 0:
        return rc

    with open(discovered_path, encoding="utf-8") as fh:
        discovered = json.load(fh)
    sides = discovered.get("sides") or []
    if not sides:
        return 1

    if len(sides) == 1:
        side_index = 1
    elif args.side:
        side_index = args.side
    else:
        print("More than one BedJet climate entity was found. Choose one to configure now.")
        print("Re-run this setup for the other side when you are ready.")
        side_index = int(prompt("Which side number", "1"))

    side = sides[side_index - 1]
    default_side_name = args.side_name or "My Side"
    default_fan_name = args.fan_name or "My BedJet"
    default_heat = args.heat_temp if args.heat_temp is not None else 90
    default_fan_pct = args.fan_percent if args.fan_percent is not None else 40
    default_cool = args.cool_temp if args.cool_temp is not None else side.get("min_temp") or 66

    if sys.stdin.isatty() and not all(
        v is not None
        for v in (args.side_name, args.fan_name, args.heat_temp, args.fan_percent)
    ):
        print()
        print("Choose short names. These become the Siri phrases:")
        print('  "Hey Siri, turn on Heat <side name>"')
        print('  "Hey Siri, set <fan name> to 60 percent"')
        side_name = prompt("Side name", default_side_name)
        fan_name = prompt("Fan name", default_fan_name)
        heat_temp = prompt("Heat temperature", str(default_heat))
        cool_temp = prompt("Cool temperature (lowest)", str(default_cool))
        fan_percent = prompt("Fan percentage", str(default_fan_pct))
    else:
        side_name = default_side_name
        fan_name = default_fan_name
        heat_temp = default_heat
        cool_temp = default_cool
        fan_percent = default_fan_pct

    generate_argv = [
        "--from",
        discovered_path,
        "--side",
        str(side_index),
        "--side-name",
        str(side_name),
        "--fan-name",
        str(fan_name),
        "--heat-temp",
        str(heat_temp),
        "--cool-temp",
        str(cool_temp),
        "--fan-percent",
        str(fan_percent),
        "--out",
        args.out,
    ]
    rc = run_module("generate_config.py", generate_argv)
    if rc != 0:
        return rc

    json_path = os.path.join(args.out, "scripts.json")
    should_install = args.install
    if not args.install and not args.no_install:
        if sys.stdin.isatty():
            should_install = prompt_yes(
                "Create/update these scripts on Home Assistant via the API now?",
                default=True,
            )
        else:
            should_install = False
            print("Non-interactive session: generated files only (pass --install to push).")

    if should_install:
        rc = run_module("install_ha_scripts.py", ["--from", json_path])
        if rc != 0:
            return rc
    else:
        print()
        print("Skipped API install. You can install later with:")
        print(f"  python3 scripts/install_ha_scripts.py --from {json_path}")
        print("Or copy the generated package into /config/packages/ on Home Assistant.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
