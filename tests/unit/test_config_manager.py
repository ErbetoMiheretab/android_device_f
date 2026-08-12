import pytest
import yaml

from src.core.config_manager import (
    ConfigManager,
    DeviceConfig,
    OrchestratorConfig,
    ProxyConfig,
)

# ── Pydantic model unit tests ─────────────────────────────────────────────────


class TestDeviceConfig:
    def test_valid_physical(self):
        d = DeviceConfig(device_id="d1", type="physical")
        assert d.ram_mb == 2048  # default

    def test_valid_ldplayer(self):
        DeviceConfig(device_id="d1", type="ldplayer")

    def test_invalid_type_raises(self):
        with pytest.raises(ValueError, match="Invalid device type"):
            DeviceConfig(device_id="d1", type="emulator")


class TestProxyConfig:
    def test_to_url_with_auth(self):
        p = ProxyConfig(host="1.2.3.4", port=1080, username="u", password="p")
        assert p.to_url() == "sock5://u:p@1.2.3.4:1080"

    def test_to_url_without_auth(self):
        p = ProxyConfig(host="1.2.3.4", port=1080)
        assert p.to_url() == "sock5://1.2.3.4:1080"


# ── ConfigManager file I/O tests ──────────────────────────────────────────────


@pytest.fixture
def config_mgr(tmp_path):
    return ConfigManager(config_dir=str(tmp_path))


@pytest.fixture
def valid_orchestrator_yaml(tmp_path):
    data = {
        "devices": [{"device_id": "d1", "type": "physical"}],
        "proxies": [{"host": "10.0.0.1", "port": 8080}],
    }
    p = tmp_path / "orchestrator.yml"
    p.write_text(yaml.dump(data))
    return tmp_path


class TestConfigManagerLoad:
    def test_load_valid_config(self, valid_orchestrator_yaml):
        mgr = ConfigManager(config_dir=str(valid_orchestrator_yaml))
        cfg = mgr.load_orchestrator_config()
        assert isinstance(cfg, OrchestratorConfig)
        assert cfg.devices[0].device_id == "d1"
        assert cfg.proxies[0].host == "10.0.0.1"

    def test_load_creates_default_when_missing(self, config_mgr, tmp_path):
        # No orchestrator.yml exists — should auto-create and return config
        cfg = config_mgr.load_orchestrator_config()
        assert isinstance(cfg, OrchestratorConfig)
        assert (tmp_path / "orchestrator.yml").exists()

    def test_load_invalid_yaml_raises(self, tmp_path):
        (tmp_path / "orchestrator.yml").write_text("not: valid: yaml: !!!")
        mgr = ConfigManager(config_dir=str(tmp_path))
        with pytest.raises(Exception):
            mgr.load_orchestrator_config()

    def test_load_extra_fields_forbidden(self, tmp_path):
        data = {
            "devices": [{"device_id": "d1", "type": "physical"}],
            "proxies": [],
            "unknown_field": True,  # OrchestratorConfig has extra="forbid"
        }
        (tmp_path / "orchestrator.yml").write_text(yaml.dump(data))
        mgr = ConfigManager(config_dir=str(tmp_path))
        with pytest.raises(Exception):
            mgr.load_orchestrator_config()


class TestDeviceConfigRoundtrip:
    def test_save_and_load_device_config(self, config_mgr, tmp_path):
        (tmp_path / "templates").mkdir()
        device = DeviceConfig(device_id="dev-42", type="ldplayer", ram_mb=4096)
        config_mgr.save_device_config(device)
        loaded = config_mgr.load_device_config("dev-42")
        assert loaded is not None
        assert loaded.device_id == "dev-42"
        assert loaded.ram_mb == 4096

    def test_load_nonexistent_device_returns_none(self, config_mgr):
        result = config_mgr.load_device_config("ghost-device")
        assert result is None
