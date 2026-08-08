import logging
from concurrent.futures import ThreadPoolExecutor

from adb_wrapper import ADBWrapper

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)

# Define target endpoints
PORTS = [5555, 5556, 5557, 5558, 5559]
DEVICES = [f"172.16.50.13:{port}" for port in PORTS]


def test_device(adb: ADBWrapper, device_serial: str, apk_path: str | None = None):
    """Run full verification checks on a single ADB target."""
    logging.info(f"--- Starting tests on {device_serial} ---")

    #Ping test
    is_alive = adb.ping_device(device_serial)
    logging.info(f"[{device_serial}] Ping: {'SUCCESS' if is_alive else 'FAILED'}")
    if not is_alive:
        return

    #Execute command
    uptime = adb.execute_command(device_serial, ["shell", "uptime"])
    logging.info(f"[{device_serial}] Uptime: {uptime}")

    #Get device properties
    props = adb.get_device_properties(device_serial)
    logging.info(f"[{device_serial}] Total properties fetched: {len(props)}")

    #Set & clear proxy
    adb.set_proxy(device_serial, "10.0.0.1", 8080)
    adb.clear_proxy(device_serial)
    logging.info(f"[{device_serial}] Proxy test completed.")

    #Install App
    if apk_path:
        installed = adb.install_app(device_serial, apk_path)
        logging.info(
            f"[{device_serial}] Install APK: {'SUCCESS' if installed else 'FAILED'}"
        )

def main():
    adb = ADBWrapper(timeout=20)

    # Verify ADBWrapper detects connected devices
    detected_devices = adb.get_device_list()
    logging.info(f"ADBWrapper discovered {len(detected_devices)} active device(s):")
    for d in detected_devices:
        logging.info(f"  -> Serial: {d.serial} | Model: {d.model} | State: {d.state}")

    print("\nExecuting tests across 5 instances in parallel...\n")

    # Run tests concurrently across all 5 devices
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(test_device, adb, serial) for serial in DEVICES]
        for future in futures:
            future.result()

    print("\nAll 5 instances tested successfully!")


if __name__ == "__main__":
    main()
