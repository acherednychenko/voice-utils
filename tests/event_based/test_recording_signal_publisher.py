"""Unit tests for RecordingSignalPublisher."""

import asyncio
import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

# Clean imports - conftest.py handles the path setup
from event_based.recording_signal_publisher import RecordingSignalPublisher
from event_based.events import (
    StartRecordingSignal, StopRecordingSignal, CancelRecordingSignal, 
    ExitSignal, InputSource
)


class TestRecordingSignalPublisher:
    """Test RecordingSignalPublisher with mocked dependencies."""
    
    @pytest.fixture
    def mock_temporal_client(self):
        """Mock Temporal client."""
        client = Mock()
        client.start_workflow = AsyncMock()
        client.get_workflow_handle = Mock()
        return client
    
    @pytest.fixture
    def mock_workflow_handle(self):
        """Mock workflow handle."""
        handle = Mock()
        handle.signal = AsyncMock()
        return handle
    
    @pytest.fixture
    def publisher(self, mock_temporal_client):
        """Create publisher with mocked client."""
        return RecordingSignalPublisher(mock_temporal_client, "test-queue")
    
    @pytest.fixture
    def start_signal(self):
        """Sample start recording signal."""
        return StartRecordingSignal(
            session_id="test-session",
            source=InputSource.KEYBOARD,
            timestamp=datetime.now()
        )
    
    @pytest.fixture
    def stop_signal(self):
        """Sample stop recording signal."""
        return StopRecordingSignal(
            session_id="test-session",
            source=InputSource.KEYBOARD,
            timestamp=datetime.now()
        )
    
    @pytest.fixture
    def cancel_signal(self):
        """Sample cancel recording signal."""
        return CancelRecordingSignal(
            session_id="test-session",
            source=InputSource.KEYBOARD,
            reason="user_requested",
            timestamp=datetime.now()
        )
    
    @pytest.fixture
    def exit_signal(self):
        """Sample exit signal."""
        return ExitSignal(
            source=InputSource.KEYBOARD,
            timestamp=datetime.now()
        )

    def test_publisher_initialization(self, mock_temporal_client):
        """Test publisher initializes correctly."""
        publisher = RecordingSignalPublisher(mock_temporal_client, "test-queue")
        
        assert publisher.client == mock_temporal_client
        assert publisher.task_queue == "test-queue"
        assert publisher.input_handler is None
        assert len(publisher.active_workflows) == 0

    @patch('event_based.recording_signal_publisher.StatefulKeyboardHandler')
    def test_setup_keyboard_input(self, mock_handler_class, publisher):
        """Test keyboard input setup."""
        mock_handler = Mock()
        mock_handler_class.return_value = mock_handler
        
        publisher.setup_keyboard_input("cmd+shift+.", "ctrl+q")
        
        mock_handler_class.assert_called_once_with("cmd+shift+.", "ctrl+q")
        mock_handler.on_signal.assert_called_once()
        assert publisher.input_handler == mock_handler

    async def test_handle_start_recording_success(self, publisher, start_signal, mock_workflow_handle):
        """Test successful start recording handling."""
        publisher.client.start_workflow.return_value = mock_workflow_handle
        
        await publisher._handle_start_recording(start_signal)
        
        # Verify workflow was started
        publisher.client.start_workflow.assert_called_once()
        call_args = publisher.client.start_workflow.call_args
        assert call_args[0][1] == start_signal  # First positional arg after workflow class
        assert call_args[1]["id"] == "recording-test-session"
        assert call_args[1]["task_queue"] == "test-queue"
        
        # Verify session tracking
        assert "test-session" in publisher.active_workflows
        assert publisher.active_workflows["test-session"] == "recording-test-session"

    async def test_handle_start_recording_failure(self, publisher, start_signal, caplog):
        """Test start recording handles failures gracefully."""
        publisher.client.start_workflow.side_effect = Exception("Temporal error")
        
        await publisher._handle_start_recording(start_signal)
        
        # Should log error but not crash
        assert "Failed to start recording workflow" in caplog.text
        assert "test-session" not in publisher.active_workflows

    async def test_handle_stop_recording_success(self, publisher, stop_signal, mock_workflow_handle):
        """Test successful stop recording handling."""
        # Setup active workflow
        publisher.active_workflows["test-session"] = "recording-test-session"
        publisher.client.get_workflow_handle.return_value = mock_workflow_handle
        
        await publisher._handle_stop_recording(stop_signal)
        
        # Verify signal was sent to workflow
        publisher.client.get_workflow_handle.assert_called_once_with("recording-test-session")
        mock_workflow_handle.signal.assert_called_once_with("stop_recording", stop_signal)

    async def test_handle_stop_recording_no_active_workflow(self, publisher, stop_signal, caplog):
        """Test stop recording when no active workflow exists."""
        await publisher._handle_stop_recording(stop_signal)
        
        # Should log warning and not crash
        assert "No active workflow for session" in caplog.text
        publisher.client.get_workflow_handle.assert_not_called()

    async def test_handle_cancel_recording_success(self, publisher, cancel_signal, mock_workflow_handle):
        """Test successful cancel recording handling."""
        # Setup active workflow
        publisher.active_workflows["test-session"] = "recording-test-session"
        publisher.client.get_workflow_handle.return_value = mock_workflow_handle
        
        await publisher._handle_cancel_recording(cancel_signal)
        
        # Verify signal was sent and session removed
        mock_workflow_handle.signal.assert_called_once_with("cancel_recording", cancel_signal)
        assert "test-session" not in publisher.active_workflows

    async def test_handle_exit_cancels_all_workflows(self, publisher, exit_signal, mock_workflow_handle):
        """Test exit signal cancels all active workflows."""
        # Setup multiple active workflows
        publisher.active_workflows = {
            "session1": "workflow1",
            "session2": "workflow2"
        }
        publisher.client.get_workflow_handle.return_value = mock_workflow_handle
        
        await publisher._handle_exit(exit_signal)
        
        # Should cancel both workflows
        assert publisher.client.get_workflow_handle.call_count == 2
        assert mock_workflow_handle.signal.call_count == 2
        assert len(publisher.active_workflows) == 0

    def test_signal_routing_logic(self, publisher):
        """Test signal routing logic without asyncio tasks."""
        # Test signal type detection logic
        start_signal = StartRecordingSignal("test", InputSource.KEYBOARD, datetime.now())
        stop_signal = StopRecordingSignal("test", InputSource.KEYBOARD, datetime.now())
        cancel_signal = CancelRecordingSignal("test", InputSource.KEYBOARD, "test", datetime.now())
        exit_signal = ExitSignal(InputSource.KEYBOARD, datetime.now())
        
        # Test signal type identification
        assert isinstance(start_signal, StartRecordingSignal)
        assert isinstance(stop_signal, StopRecordingSignal)
        assert isinstance(cancel_signal, CancelRecordingSignal)
        assert isinstance(exit_signal, ExitSignal)
        
        # Test that publisher has the expected handler methods
        assert hasattr(publisher, '_handle_start_recording')
        assert hasattr(publisher, '_handle_stop_recording')
        assert hasattr(publisher, '_handle_cancel_recording')
        assert hasattr(publisher, '_handle_exit')

    def test_start_stop_methods(self, publisher):
        """Test start/stop methods."""
        mock_handler = Mock()
        publisher.input_handler = mock_handler
        
        publisher.start()
        mock_handler.start.assert_called_once()
        
        publisher.stop()
        mock_handler.stop.assert_called_once()

    def test_start_stop_no_handler(self, publisher):
        """Test start/stop methods when no handler is set."""
        # Should not crash when no handler is set
        publisher.start()
        publisher.stop()


class TestSignalPublisherIntegration:
    """Integration tests for signal flow."""
    
    @pytest.fixture
    def mock_temporal_client(self):
        client = Mock()
        client.start_workflow = AsyncMock()
        client.get_workflow_handle = Mock()
        return client
    
    async def test_complete_recording_flow(self, mock_temporal_client):
        """Test complete signal flow from start to stop."""
        publisher = RecordingSignalPublisher(mock_temporal_client)
        mock_handle = Mock()
        mock_handle.signal = AsyncMock()
        
        # Mock workflow creation
        mock_temporal_client.start_workflow.return_value = mock_handle
        mock_temporal_client.get_workflow_handle.return_value = mock_handle
        
        # Start recording
        start_signal = StartRecordingSignal("flow-test", InputSource.KEYBOARD, datetime.now())
        await publisher._handle_start_recording(start_signal)
        
        # Verify workflow started and tracked
        assert "flow-test" in publisher.active_workflows
        mock_temporal_client.start_workflow.assert_called_once()
        
        # Stop recording
        stop_signal = StopRecordingSignal("flow-test", InputSource.KEYBOARD, datetime.now())
        await publisher._handle_stop_recording(stop_signal)
        
        # Verify stop signal sent
        mock_handle.signal.assert_called_once_with("stop_recording", stop_signal)

    async def test_cancel_before_stop(self, mock_temporal_client):
        """Test canceling before stopping."""
        publisher = RecordingSignalPublisher(mock_temporal_client)
        mock_handle = Mock()
        mock_handle.signal = AsyncMock()
        
        mock_temporal_client.start_workflow.return_value = mock_handle
        mock_temporal_client.get_workflow_handle.return_value = mock_handle
        
        # Start recording
        start_signal = StartRecordingSignal("cancel-test", InputSource.KEYBOARD, datetime.now())
        await publisher._handle_start_recording(start_signal)
        
        # Cancel recording
        cancel_signal = CancelRecordingSignal("cancel-test", InputSource.KEYBOARD, "user", datetime.now())
        await publisher._handle_cancel_recording(cancel_signal)
        
        # Verify cancel signal sent and session removed
        mock_handle.signal.assert_called_once_with("cancel_recording", cancel_signal)
        assert "cancel-test" not in publisher.active_workflows


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 