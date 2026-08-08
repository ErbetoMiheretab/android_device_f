import logging
import subprocess
from dataclasses import dataclass
import time
from tenacity import retry, stop_after_attempt, wait_fixed

logger = logging.getLogger(__name__)


@dataclass
class DeviceInfo:
    """Info about and Android device"""

    serial: str
    model: str
    android_version: str
    state: str  # "device", "offline", "unauthorized"
    proxy: str | None = None


class ADBWrapper:
    """Wrapper around ADB commands with automatic retries"""

    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.adb_path = self._find_adb()

    def _find_adb(self) -> str:
        """FInd ADB executable path"""
        import shutil

        adb_path = shutil.which("adb")
        if not adb_path:
            raise RuntimeError("ADB not found in PATH")
        return adb_path

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(1))
    def execute_command(self, device_serial: str, command: list[str]) -> str:
        """
         Execute ADB command with retries

        Args:
            device_serial: Serial of the device
            command: ADB command arguments (e.g., ["shell", "echo", "hello"])

        Returns:
            Command output as string
        """
        full_command = [self.adb_path, "-s", device_serial] + command

        try:
            result = subprocess.run(
                full_command,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=True,
            )
            return result.stdout.strip()
        except subprocess.TimeoutExpired:
            logger.warning(f"ADB command timed out on {device_serial}: {command}")
            raise
        except subprocess.CalledProcessError as e:
            logger.error(f"ADB command failed on {device_serial}:{e.stderr}")
            raise

    def get_device_list(self) -> list[DeviceInfo]:
        """Get all connected devices"""
        result = subprocess.run(
            [self.adb_path, "devices", "-l"], capture_output=True, text=True, timeout=10
        )

        devices = []
        lines = result.stdout.strip().split("\n")[1:]  # Skip header

        for line in lines:
            if not line.strip():
                continue
            parts = line.split()

            if len(parts) >= 2:
                serial = parts[0]
                state = parts[1]

                # Parse device info from -l output
                model = "unknown"
                for part in parts[2:]:
                    if part.startswith("model:"):
                        model = part.split(":")[1]

                        break
                devices.append(
                    DeviceInfo(
                        serial=serial,
                        model=model,
                        android_version="unknown",
                        state=state,
                    )
                )
        return devices

    def ping_device(self, device_serial: str) -> bool:
        """Check if device is responsive"""

        try:
            self.execute_command(device_serial, ["shell", "echo", "ok"])
            return True
        except Exception:
            return False

    def get_device_properties(self, device_serial: str) -> dict[str, str]:
        """GEt device properties via getprop"""
        try:
            output = self.execute_command(device_serial, ["shell", "getprop"])

            props = {}
            for line in output.split("\n"):
                if ":" in line:
                    k, v = line.split(";", 1)
                    props[k.strip("[]")] = v.strip("[]")
            return props
        except Exception:
            return {}

    def install_app(self, device_serial: str, apk_path: str) -> bool:
        """Install APK on device"""
        try:
            self.execute_command(device_serial, ["install", "-r", apk_path])
            return True
        except Exception:
            return False

    def set_proxy(self, device_serial: str, proxy_host: str, proxy_port: int):
        """Set HTTP proxy on device"""
        # Android's proxy settings via settings command
        commands = [
            [
                "shell",
                "settings",
                "put",
                "global",
                "http_proxy",
                f"{proxy_host}:{proxy_port}",
            ],
            [
                "shell",
                "settings",
                "put",
                "global",
                "global_http_proxy_host",
                proxy_host,
            ],
            [
                "shell",
                "settings",
                "put",
                "global",
                "global_http_proxy_port",
                str(proxy_port),
            ],
        ]

        for cmd in commands:
            self.execute_command(device_serial, cmd)

        logger.info(f"Set proxy {proxy_host}:{proxy_port} on {device_serial}")

    def clear_proxy(self, device_serial: str):
        """Clear proxy settings on device"""
        commands = [
            ["shell", "settings", "delete", "global", "http_proxy"],
            ["shell", "settings", "delete", "global", "global_http_proxy_host"],
            ["shell", "settings", "delete", "global", "global_http_proxy_port"],
        ]

        for cmd in commands:
            try:
                self.execute_command(device_serial, cmd)
            except Exception:
                pass  # Ignore if setting doesn't exist

        logger.info(f"Cleared proxy on {device_serial}")

    def reboot_device(self, device_serial: str):
        """Reboot the device"""
        self.execute_command(device_serial, ["reboot"])

    def is_fully_booted(self, serial: str) -> bool:
        """Checks if Android OS package manager service is accessible."""
        try:
            # Check if sys.boot_completed is 1
            boot = self.execute_command(serial, ["shell", "getprop", "sys.boot_completed"])
            if boot.strip() != "1":
                return False

            # Check if package manager service is active
            pm = self.execute_command(serial, ["shell", "pm", "path", "android"])
            return "package:" in pm
        except Exception as e:
            logging.debug(f"[{serial}] Boot check attempt failed: {e}")
            return False

    def wait_for_boot(
        self, serial: str, timeout: int = 60, poll_interval: int = 2
    ) -> bool:
        """Polls until the device reports fully booted or times out."""
        logging.info(f"[{serial}] Checking framework readiness...")
        start_time = time.time()

        while time.time() - start_time < timeout:
            if self.is_fully_booted(serial):
                logging.info(f"[{serial}] Android framework is ready.")
                return True
            time.sleep(poll_interval)

        logging.error(f"[{serial}] Timed out waiting for boot completion.")
        return False
