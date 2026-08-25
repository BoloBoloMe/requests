"""tests/api_client_cli 共享 fixture (M3 D014-4 fake HTTP 服务)."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))  # importlib 模式下同级 support 可导入

from support import CLI_TOKEN, FakeService, write_service_json


@pytest.fixture
def fake_service():
    service = FakeService().start()
    yield service
    service.stop()


@pytest.fixture
def service_data_dir(tmp_path, fake_service):
    """数据目录: .local/service.json 指向 fake 服务 (pid 存活)."""
    data_dir = tmp_path / "repo"
    write_service_json(data_dir, fake_service.port, CLI_TOKEN)
    return data_dir
