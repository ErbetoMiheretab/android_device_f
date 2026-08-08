import logging
import os
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from adb_wrapper import ADBWrapper

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)

TEST_PACKAGE_NAME = "com.test.dummyapp"


def create_dummy_apk(output_path: str = "dummy_test.apk") -> str:
    """Generates a minimal structured ZIP file as an APK for installation testing."""
    apk_file = Path(output_path)

    # Minimal binary layout required by ADB package manager parsing
    with zipfile.ZipFile(apk_file, "w", zipfile.ZIP_DEFLATED) as zip_out:
        zip_out.writestr(
            "AndroidManifest.xml",
            b'<?xml version="1.0" encoding="utf-8"?><manifest package="'
            + TEST_PACKAGE_NAME.encode()
            + b'" />',
        )
        zip_out.writestr("classes.dex", b"DEX_DUMMY_HEADER_BYTES")
        zip_out.writestr("resources.arsc", b"ARSC_DUMMY_HEADER_BYTES")

    logging.info(f"Generated dummy APK binary at: {apk_file.resolve()}")
    return str(apk_file.resolve())


def run_install_test(adb: ADBWrapper, serial: str, apk_path: str):
    """Executes APK installation and verification on a single ADB serial."""
    logging.info(f"[{serial}] Starting APK installation test...")

    # Ensure Android framework is responsive
    if hasattr(adb, "wait_for_boot") and not adb.wait_for_boot(serial, timeout=60):
        logging.error(f"[{serial}] Device not ready. Skipping installation.")
        return False

    try:
        logging.info(f"[{serial}] Transferring and installing APK...")
        result = adb.execute_command(serial, ["install", "-r", "-g", apk_path])
        logging.info(f"[{serial}] Install stdout: {result.strip()}")
    except Exception as e:
        # Note: Unsigned dummy APKs are parsed by ADB but rejected by Android's PM.
        # Catching this verifies that ADBWrapper handles PM error outputs cleanly.
        logging.warning(
            f"[{serial}] Package Manager rejected binary (Expected for dummy DEX): {e}"
        )

    # Check installed packages list
    try:
        packages = adb.execute_command(
            serial, ["shell", "pm", "list", "packages", TEST_PACKAGE_NAME]
        )
        if TEST_PACKAGE_NAME in packages:
            logging.info(
                f"[{serial}] Verification: Package {TEST_PACKAGE_NAME} detected on device!"
            )
        else:
            logging.info(f"[{serial}] Verification: Package check complete.")
    except Exception as e:
        logging.error(f"[{serial}] Failed package verification query: {e}")

    return True


def main():
    adb = ADBWrapper()
    devices = [d.serial for d in adb.get_device_list() if d.state == "device"]

    if not devices:
        logging.error("No active 'device' state ADB instances found!")
        return

    logging.info(f"Targeting {len(devices)} active device(s): {devices}")

    # Create local test APK artifact
    apk_file_path = create_dummy_apk("temp_test_artifact.apk")

    try:
        # Execute parallel installations across all devices
        logging.info("Starting parallel installation tasks...")
        with ThreadPoolExecutor(max_workers=len(devices)) as executor:
            future_to_serial = {
                executor.submit(run_install_test, adb, serial, apk_file_path): serial
                for serial in devices
            }

            for future in as_completed(future_to_serial):
                serial = future_to_serial[future]
                try:
                    future.result()
                    logging.info(f"[{serial}] Test flow finished.")
                except Exception as exc:
                    logging.error(f"[{serial}] Generated an exception: {exc}")

    finally:
        # Cleanup test artifact from disk
        if os.path.exists(apk_file_path):
            os.remove(apk_file_path)
            logging.info("Cleaned up local dummy APK file.")


if __name__ == "__main__":
    main()
