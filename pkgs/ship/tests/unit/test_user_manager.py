"""
Unit tests for user_manager module (command execution).
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from pathlib import Path


# Mark all tests in this module as unit tests
pytestmark = pytest.mark.unit


class TestBackgroundProcessRegistry:
    """Test background process management"""

    def test_generate_process_id(self):
        """Test process ID generation"""
        from app.components.user_manager import generate_process_id
        
        pid1 = generate_process_id()
        pid2 = generate_process_id()
        
        # Should be 8 characters
        assert len(pid1) == 8
        assert len(pid2) == 8
        # Should be unique
        assert pid1 != pid2

    def test_register_and_get_processes(self):
        """Test registering and retrieving background processes"""
        from app.components.user_manager import (
            register_background_process,
            get_background_processes,
            _background_processes,
        )
        
        # Clear existing processes
        _background_processes.clear()
        
        # Create a mock process
        mock_process = MagicMock()
        mock_process.returncode = None
        mock_process.pid = 12345
        
        register_background_process(
            process_id="test1234",
            pid=12345,
            command="sleep 10",
            process=mock_process,
        )
        
        processes = get_background_processes()
        assert len(processes) == 1
        assert processes[0]["process_id"] == "test1234"
        assert processes[0]["pid"] == 12345
        assert processes[0]["command"] == "sleep 10"
        assert processes[0]["status"] == "running"
        
        # Clean up
        _background_processes.clear()


class TestProcessResult:
    """Test ProcessResult dataclass"""

    def test_success_result(self):
        """Test creating a successful result"""
        from app.components.user_manager import ProcessResult
        
        result = ProcessResult(
            success=True,
            stdout="Hello, World!",
            stderr="",
            return_code=0,
            pid=123,
        )
        
        assert result.success is True
        assert result.stdout == "Hello, World!"
        assert result.stderr == ""
        assert result.return_code == 0

    def test_failure_result(self):
        """Test creating a failure result"""
        from app.components.user_manager import ProcessResult
        
        result = ProcessResult(
            success=False,
            stdout="",
            stderr="Error occurred",
            return_code=1,
            error="Command failed",
        )
        
        assert result.success is False
        assert result.error == "Command failed"
        assert result.return_code == 1


class TestBackgroundProcessEntry:
    """Test BackgroundProcessEntry class"""

    def test_status_running(self):
        """Test status when process is running"""
        from app.components.user_manager import BackgroundProcessEntry
        
        mock_process = MagicMock()
        mock_process.returncode = None
        
        entry = BackgroundProcessEntry(
            process_id="test1234",
            pid=123,
            command="sleep 10",
            process=mock_process,
        )
        
        assert entry.status == "running"

    def test_status_completed(self):
        """Test status when process completed successfully"""
        from app.components.user_manager import BackgroundProcessEntry
        
        mock_process = MagicMock()
        mock_process.returncode = 0
        
        entry = BackgroundProcessEntry(
            process_id="test1234",
            pid=123,
            command="echo hello",
            process=mock_process,
        )
        
        assert entry.status == "completed"

    def test_status_failed(self):
        """Test status when process failed"""
        from app.components.user_manager import BackgroundProcessEntry
        
        mock_process = MagicMock()
        mock_process.returncode = 1
        
        entry = BackgroundProcessEntry(
            process_id="test1234",
            pid=123,
            command="false",
            process=mock_process,
        )
        
        assert entry.status == "failed"
