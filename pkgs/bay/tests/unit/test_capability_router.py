"""Unit tests for CapabilityRouter._require_capability().

Tests capability validation using runtime /meta response.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.adapters.base import BaseAdapter, RuntimeMeta
from app.errors import CapabilityNotSupportedError
from app.router.capability import CapabilityRouter


class FakeAdapter(BaseAdapter):
    """Fake adapter for testing capability validation."""

    def __init__(self, capabilities: dict | None = None) -> None:
        self._meta = RuntimeMeta(
            name="fake",
            version="1.0.0",
            api_version="v1",
            mount_path="/workspace",
            capabilities=capabilities or {},
        )

    async def get_meta(self) -> RuntimeMeta:
        return self._meta

    async def health(self) -> bool:
        return True

    def supported_capabilities(self) -> list[str]:
        return list(self._meta.capabilities.keys())


class TestRequireCapability:
    """Test CapabilityRouter._require_capability() method."""

    @pytest.fixture
    def mock_sandbox_mgr(self):
        """Create mock sandbox manager."""
        return AsyncMock()

    async def test_require_capability_passes_when_present(self, mock_sandbox_mgr):
        """_require_capability should pass silently when capability exists."""
        adapter = FakeAdapter(
            capabilities={
                "python": {"operations": ["exec"]},
                "shell": {"operations": ["exec"]},
            }
        )
        router = CapabilityRouter(mock_sandbox_mgr)

        # Should not raise
        await router._require_capability(adapter, "python")
        await router._require_capability(adapter, "shell")

    async def test_require_capability_raises_when_missing(self, mock_sandbox_mgr):
        """_require_capability should raise CapabilityNotSupportedError when missing."""
        adapter = FakeAdapter(
            capabilities={
                "shell": {"operations": ["exec"]},
            }
        )
        router = CapabilityRouter(mock_sandbox_mgr)

        with pytest.raises(CapabilityNotSupportedError) as exc_info:
            await router._require_capability(adapter, "python")

        error = exc_info.value
        assert error.details["capability"] == "python"
        assert "shell" in error.details["available"]
        assert "python" not in error.details["available"]

    async def test_require_capability_error_message(self, mock_sandbox_mgr):
        """Error should contain meaningful message."""
        adapter = FakeAdapter(
            capabilities={
                "filesystem": {"operations": ["read", "write"]},
            }
        )
        router = CapabilityRouter(mock_sandbox_mgr)

        with pytest.raises(CapabilityNotSupportedError) as exc_info:
            await router._require_capability(adapter, "terminal")

        error = exc_info.value
        assert "terminal" in str(error)
        assert error.message == "Runtime does not support capability: terminal"

    async def test_require_capability_with_empty_capabilities(self, mock_sandbox_mgr):
        """Should raise when runtime reports no capabilities."""
        adapter = FakeAdapter(capabilities={})
        router = CapabilityRouter(mock_sandbox_mgr)

        with pytest.raises(CapabilityNotSupportedError) as exc_info:
            await router._require_capability(adapter, "python")

        error = exc_info.value
        assert error.details["available"] == []

    async def test_require_filesystem_capability(self, mock_sandbox_mgr):
        """Test filesystem capability validation."""
        adapter = FakeAdapter(
            capabilities={
                "filesystem": {
                    "operations": ["create", "read", "write", "delete", "list"],
                },
            }
        )
        router = CapabilityRouter(mock_sandbox_mgr)

        # Should pass
        await router._require_capability(adapter, "filesystem")

        # python should fail
        with pytest.raises(CapabilityNotSupportedError):
            await router._require_capability(adapter, "python")
