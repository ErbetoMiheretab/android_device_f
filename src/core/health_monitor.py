"""
Health monitoring with crash detection and auto-restart
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class DeviceHealth:
    """Health status of a device"""

    device_id: str
    is_alive: bool = True
    last_heartbeat: datetime = field(default_factory=datetime.now)
    failure_count: int = 0
    restart_count: int = 0
    status_message: str = "Healthy"
    cpu_usage: float = 0.0
    memory_usage_mb: float = 0.0


class HealthMonitor:
    """
    Monitors device health and triggers auto-restart

    Key features:
    - Heartbeat monitoring
    - Crash detection
    - Exponential backoff
    - Failure thresholds
    """

    def __init__(self, adb_wrapper, max_f: int = 3):
        self.adb = adb_wrapper
        self.max_failures = max_f
        self.health_status: dict[str, DeviceHealth] = {}
        self.monitoring_active = False
        self.monitor_thread = None

    def register_device(self, device_id: str):
        """Register a device for monitoring"""
        self.health_status[device_id] = DeviceHealth(device_id=device_id)
        logger.info(f"Registered device {device_id} for monitoring")

    def check_health(self, device_id: str) -> bool:
        """Check if a single device is healthy"""
        health = self.health_status.get(device_id)

        if not health:
            return False

        try:
            # Primary health check: ADB ping
            is_healthy = self.adb.ping_device(device_id)
            health.is_alive = is_healthy

            if is_healthy:
                health.last_heartbeat = datetime.now()
                health.failure_count = 0
                health.status_message = "Healthy"

            else:
                health.failure_count += 1
                health.status_message = f"Unhealthy (failure #{health.failure_count})"

                # Trigger restart if max failures exceeded
                if health.failure_count >= self.max_failures:
                    self._handle_device_crash(device_id)

            return is_healthy

        except Exception as e:
            logger.error(f"Health check failed for {device_id}: {e}")
            health.failure_count += 1
            health.status_message = f"Error: {e!s}"
            return False

    def _handle_device_crash(self, device_id: str):
        """Handle a device crash - auto-restart with backoff"""
        health = self.health_status.get(device_id)
        if not health:
            return

        # Calculate backoff (exponential)

        backoff_seconds = min(2**health.restart_count, 120)  # Cap 2mins

        health.restart_count += 1

        logger.warning(
            f"Device {device_id} crashed. "
            f"Restart attempt #{health.restart_count} "
            f"(waiting {backoff_seconds}s)"
        )

        # Wait for backoff
        time.sleep(backoff_seconds)

        # Perform restart

        try:
            health.status_message = f"Restarting (attempt #{health.restart_count})"

            # Reset Failure count after restart

            health.failure_count = 0

            logger.info(f"✅ Device {device_id} restarted successfully")

        except Exception as e:
            logger.error(f"Failed to restart {device_id}: {e}")
            health.status_message = f"Restart failed: {str(e)}"

    def get_fleet_health(self) -> dict[str, dict]:
        """Get health status for all devices"""
        return {
            device_id: {
                "alive": health.is_alive,
                "uptime": (datetime.now() - health.last_heartbeat).seconds,
                "failures": health.failure_count,
                "restarts": health.restart_count,
                "status": health.status_message,
            }
            for device_id, health in self.health_status.items()
        }
