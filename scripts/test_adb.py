# scripts/test_adb.py
"""
Test script to verify ADB wrapper works
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.adb_wrapper import ADBWrapper


def main():
    print("Testing ADB connection...")

    # Initialize ADB
    adb = ADBWrapper()

    # Get devices
    devices = adb.get_device_list()
    print(f"\nFound {len(devices)} device(s):")
    for device in devices:
        print(f"  - {device.serial} ({device.state})")

    if devices:
        # Test ping on first device
        device = devices[0]
        print(f"\n Testing ping on {device.serial}...")
        if adb.ping_device(device.serial):
            print(" Device is responsive")
        else:
            print(" Device is not responsive")

        # Get device properties
        print("\n Getting device properties...")
        props = adb.get_device_properties(device.serial)
        print(f"  Model: {props.get('ro.product.model', 'unknown')}")
        print(f"  Android: {props.get('ro.build.version.release', 'unknown')}")

    print("\n Test complete")


if __name__ == "__main__":
    main()
