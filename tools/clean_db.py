#!/usr/bin/env python3
"""Clean dual_smart_thermostat entries from Home Assistant storage files."""

import json
import os
import sys

STORAGE_DIR = "/workspaces/dual_smart_thermostat/config/.storage"
DOMAIN = "dual_smart_thermostat"


def get_config_entry_ids():
    """Return the config entry IDs that belong to dual_smart_thermostat.

    The device registry stores opaque config entry IDs, so they have to be
    resolved from core.config_entries before devices can be matched.
    """
    file_path = os.path.join(STORAGE_DIR, "core.config_entries")

    if not os.path.exists(file_path):
        sys.exit(
            f"Config entries file not found ({file_path}); "
            "cannot match devices to dual_smart_thermostat"
        )

    with open(file_path, "r") as f:
        data = json.load(f)

    return {
        entry["entry_id"]
        for entry in data["data"]["entries"]
        if entry.get("domain") == DOMAIN
    }


def clean_entity_registry():
    """Remove dual_smart_thermostat entities from entity registry."""
    file_path = "/workspaces/dual_smart_thermostat/config/.storage/core.entity_registry"

    # Read the current file
    with open(file_path, "r") as f:
        data = json.load(f)

    # Filter out dual_smart_thermostat entities
    original_count = len(data["data"]["entities"])
    data["data"]["entities"] = [
        entity
        for entity in data["data"]["entities"]
        if entity.get("platform") != "dual_smart_thermostat"
    ]
    new_count = len(data["data"]["entities"])

    # Write back the cleaned data
    with open(file_path, "w") as f:
        json.dump(data, f, indent=2)

    print(
        f"Removed {original_count - new_count} dual_smart_thermostat entities from entity registry"
    )


def clean_device_registry():
    """Remove dual_smart_thermostat devices from device registry."""
    file_path = "/workspaces/dual_smart_thermostat/config/.storage/core.device_registry"

    if not os.path.exists(file_path):
        print("Device registry file not found")
        return

    # Read the current file
    with open(file_path, "r") as f:
        data = json.load(f)

    entry_ids = get_config_entry_ids()

    # Filter out devices linked to a dual_smart_thermostat config entry
    original_count = len(data["data"]["devices"])
    data["data"]["devices"] = [
        device
        for device in data["data"]["devices"]
        if not any(
            entry_id in entry_ids for entry_id in device.get("config_entries", [])
        )
    ]
    new_count = len(data["data"]["devices"])

    # Write back the cleaned data
    with open(file_path, "w") as f:
        json.dump(data, f, indent=2)

    print(
        f"Removed {original_count - new_count} dual_smart_thermostat devices from device registry"
    )


def clean_restore_state():
    """Remove dual_smart_thermostat entities from restore state."""
    file_path = "/workspaces/dual_smart_thermostat/config/.storage/core.restore_state"

    if not os.path.exists(file_path):
        print("Restore state file not found")
        return

    # Read the current file
    with open(file_path, "r") as f:
        data = json.load(f)

    # Filter out dual_smart_thermostat entities
    original_count = len(data["data"])
    filtered_data = []
    for state_entry in data["data"]:
        entity_id = state_entry.get("state", {}).get("entity_id", "")
        # Keep entities that are not climate entities or don't belong to dual_smart_thermostat
        if not entity_id.startswith("climate.") or "dual_smart_thermostat" not in str(
            state_entry
        ):
            filtered_data.append(state_entry)

    data["data"] = filtered_data
    new_count = len(data["data"])

    # Write back the cleaned data
    with open(file_path, "w") as f:
        json.dump(data, f, indent=2)

    print(
        f"Removed {original_count - new_count} dual_smart_thermostat states from restore state"
    )


if __name__ == "__main__":
    print("Cleaning Home Assistant database of dual_smart_thermostat entries...")
    clean_entity_registry()
    clean_device_registry()
    clean_restore_state()
    print("Cleanup complete!")
