"""
Config management with YAML and env  var
"""

from pathlib import Path

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, field_validator

load_dotenv()


class DeviceConfig(BaseModel):
    device_id: str
    type: str
    proxy: str | None = None
    ram_mb: int = 2048

    @field_validator("type")
    def validate_type(cls, v):
        if v not in ["physical", "ldplayer"]:
            raise ValueError(f"Invalid device type: {v}")
        return v


class ProxyConfig(BaseModel):
    """Proxy config"""

    host: str
    port: int
    type: str = "sock5"  # or "http"
    username: str | None = None
    password: str | None = None
    enabled: bool = True

    def to_url(self) -> str:
        """Convert to proxy URL format"""
        if self.username and self.password:
            return (
                f"{self.type}://{self.username}:{self.password}@{self.host}:{self.port}"
            )
        return f"{self.type}://{self.host}:{self.port}"


class OrchestratorConfig(BaseModel):
    """Main orchestrator configuration"""

    devices: list[DeviceConfig]
    proxies: list[ProxyConfig]
    health_check_interval: int = 10  # seconds
    auto_restart: bool = True
    max_restart_attempts: int = 5
    proxy_failover_enabled: bool = True
    log_level: str = "INFO"

    class Config:
        extra = "forbid"


class ConfigManager:
    """Load and manage configurations"""

    def __init__(self, config_dir: str = "config"):
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(exist_ok=True)

    def load_orchestrator_config(self) -> OrchestratorConfig:
        """Load main orch config"""
        config_path = self.config_dir / "orchestrator.yml"

        if not config_path.exists():
            # Create default config
            self._create_default_config()

        with open(config_path) as f:
            data = yaml.safe_load(f)

        return OrchestratorConfig(**data)

    def _create_default_config(self):
        """Create default configuration files"""
        default_config = {
            "devices": [
                {
                    "device_id": "device-001",
                    "type": "ldplayer",
                    "proxy": "192.168.1.100:8080",
                    "resolution": "1080x1920",
                    "ram_mb": 2048,
                }
            ],
            "proxies": [
                {
                    "host": "192.168.1.100",
                    "port": 8080,
                    "type": "socks5",
                    "enabled": True,
                }
            ],
            "health_check_interval": 10,
            "auto_restart": True,
            "max_restart_attempts": 5,
            "proxy_failover_enabled": True,
            "log_level": "INFO",
        }

        config_path = self.config_dir / "orchestrator.yml"

        with open(config_path, "w") as f:
            yaml.dump(default_config, f, default_flow_style=False)

        print(f"Created default config at {config_path}")

    def save_device_config(self, device_conf: DeviceConfig):
        """Save device-specific configuration"""
        device_path = self.config_dir / "templates" / f"{device_conf.device_id}.yaml"
        with open(device_path, "w") as f:
            yaml.dump(device_conf.model_dump(), f)

    def load_device_config(self, device_id: str) -> DeviceConfig | None:
        """Load device-specific configuration"""
        device_path = self.config_dir / "templates" / f"{device_id}.yaml"
        if not device_path.exists():
            return None

        with open(device_path) as f:
            data = yaml.safe_load(f)

        return DeviceConfig(**data)
