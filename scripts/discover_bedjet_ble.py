#!/usr/bin/env python3
"""Scan for nearby BedJet V3 units and print their BLE MAC addresses.

Run this on a computer near the BedJet that has Bluetooth (a laptop is
typical). It does not need to run on the Home Assistant host.

Requires the bleak package:  pip install -r scripts/requirements.txt

The BedJet BLE service UUID is used as a primary filter; the advertised
name is used as a fallback, because some units show up as "BEDJET".
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

# Official ESPHome BedJet service UUID (ASCII suffix is "BedJet").
BEDJET_SERVICE_UUID = "00001000-bed0-0080-aa55-4265644a6574"


def is_bedjet(name: str | None, service_uuids: list[str] | None) -> bool:
    if name and "bedjet" in name.lower():
        return True
    for uuid in service_uuids or []:
        if uuid.lower() == BEDJET_SERVICE_UUID:
            return True
    return False


async def scan(duration: float) -> list[dict]:
    try:
        from bleak import BleakScanner
    except ImportError:
        print(
            "The bleak package is required for a BLE scan.\n"
            "Install it with:  pip install bleak\n"
            "Or:              pip install -r scripts/requirements.txt\n\n"
            "If you cannot scan from this computer, flash the ESPHome template\n"
            "with a placeholder MAC, watch the ESP logs for lines from\n"
            "esp32_ble_tracker mentioning BEDJET, then put that MAC in the YAML.",
            file=sys.stderr,
        )
        raise SystemExit(2)

    print(f"Scanning for {duration:.0f}s… stay near the BedJet.", file=sys.stderr)
    devices = await BleakScanner.discover(timeout=duration, return_adv=True)
    found: list[dict] = []
    others: list[dict] = []
    for device, adv in devices.values():
        uuids = list(adv.service_uuids or [])
        row = {
            "address": device.address,
            "name": device.name or adv.local_name or "",
            "rssi": adv.rssi,
            "service_uuids": uuids,
            "is_bedjet": is_bedjet(device.name or adv.local_name, uuids),
        }
        if row["is_bedjet"]:
            found.append(row)
        else:
            others.append(row)

    found.sort(key=lambda r: r["rssi"] or -999, reverse=True)
    others.sort(key=lambda r: r["rssi"] or -999, reverse=True)
    return found, others


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Find nearby BedJet BLE MAC addresses."
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=10.0,
        help="Scan length in seconds (default: 10)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Also list other nearby BLE devices (useful if the name is unexpected)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON instead of a table",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Also write JSON results to this file",
    )
    args = parser.parse_args()

    found, others = asyncio.run(scan(args.duration))
    if not args.all:
        others = []

    payload = {"bedjets": found, "other_devices": others if args.all else []}

    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
            fh.write("\n")

    if args.json:
        print(json.dumps(payload, indent=2))
        return 0 if found else 1

    if not found:
        print("No BedJet devices were found.")
        print()
        print("Tips:")
        print("  - Stand closer and plug the BedJet in so it is advertising.")
        print("  - Close the BedJet mobile app; only one BLE client can connect.")
        print("  - Re-run with --duration 20 --all to see every nearby BLE device.")
        print("  - Or watch ESPHome logs after a flash: look for 'BEDJET' and a MAC.")
        if args.all and others:
            print()
            print("Other nearby BLE devices:")
            for row in others:
                print(f"  {row['address']:17}  RSSI={row['rssi']!s:>4}  {row['name'] or '(no name)'}")
        return 1

    print(f"Found {len(found)} BedJet device(s):\n")
    print(f"  {'MAC address':<17}  {'RSSI':>4}  Name")
    print(f"  {'-' * 17}  {'-' * 4}  {'-' * 20}")
    for row in found:
        print(f"  {row['address']:<17}  {row['rssi']!s:>4}  {row['name'] or '(no name)'}")
    print()
    print("Paste each MAC into esphome/bedjet-proxy.yaml (or bedjet-proxy-dual.yaml)")
    print("as a substitution, then flash the ESP32.")
    if args.all and others:
        print()
        print("Other nearby BLE devices:")
        for row in others:
            print(f"  {row['address']:17}  RSSI={row['rssi']!s:>4}  {row['name'] or '(no name)'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
