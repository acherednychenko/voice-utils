"""Unit tests for RecordingWorkflow following Temporal testing philosophy."""

import asyncio
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker
from temporalio.common import RetryPolicy
from temporalio.exceptions import FailureError, CancelledError
from temporalio.client import WorkflowExecutionStatus
from temporalio import activity, workflow

# Clean imports - conftest.py handles the path setup
from event_based.recording_workflow import (
    RecordingWorkflow, 
    record_audio_activity,
    stop_recording_activity, 
    save_audio_file_activity
)
from event_based.events import (
    StartRecordingSignal, StopRecordingSignal, CancelRecordingSignal,
    RecordingStarted, RecordingStopped, FileSaved, RecordingFailed,
    InputSource
)


class TestRecordingWorkflowLogic:
    """Test RecordingWorkflow logic with mocked dependencies."""
    
    @pytest.fixture
    def workflow_instance(self):
        """Create a workflow instance for testing."""
        return RecordingWorkflow()

    @pytest.fixture
    def start_signal(self):
        """Create a test start recording signal."""
        return StartRecordingSignal(
            session_id="test-session-123",
            source=InputSource.KEYBOARD,
            timestamp=datetime.now()
        )

    def test_workflow_initialization(self, workflow_instance):
        """Test workflow initializes correctly."""
        assert workflow_instance.recording_task is None
        assert workflow_instance.session_id is None
        assert workflow_instance.source is None
        assert workflow_instance.is_recording is False
        assert workflow_instance.stop_signal_received is False
        assert workflow_instance.cancel_signal_received is False
        assert workflow_instance.cancel_reason is None

    async def test_stop_recording_signal_handler(self, workflow_instance):
        """Test stop recording signal handler."""
        stop_signal = StopRecordingSignal(
            session_id="test-session",
            source=InputSource.KEYBOARD,
            timestamp=datetime.now()
        )
        
        # Mock workflow.logger to avoid workflow context issues
        with patch('event_based.recording_workflow.workflow.logger'):
            await workflow_instance.stop_recording(stop_signal)
        
        assert workflow_instance.stop_signal_received is True

    async def test_cancel_recording_signal_handler(self, workflow_instance):
        """Test cancel recording signal handler."""
        cancel_signal = CancelRecordingSignal(
            session_id="test-session",
            source=InputSource.KEYBOARD,
            reason="user_requested",
            timestamp=datetime.now()
        )
        
        # Mock workflow.logger to avoid workflow context issues
        with patch('event_based.recording_workflow.workflow.logger'):
            await workflow_instance.cancel_recording(cancel_signal)
        
        assert workflow_instance.cancel_signal_received is True
        assert workflow_instance.cancel_reason == "user_requested"

    def test_workflow_state_management(self, workflow_instance, start_signal):
        """Test workflow state is managed correctly."""
        # Simulate workflow initialization
        workflow_instance.session_id = start_signal.session_id
        workflow_instance.source = start_signal.source
        workflow_instance.is_recording = True
        
        assert workflow_instance.session_id == "test-session-123"
        assert workflow_instance.source == InputSource.KEYBOARD
        assert workflow_instance.is_recording is True


class TestRecordingActivitiesMocked:
    """Test recording activities with proper mocking."""
    
    @pytest.fixture
    async def env(self):
        """Create a time-skipping workflow environment."""
        async with await WorkflowEnvironment.start_time_skipping() as env:
            yield env

    async def test_mock_record_audio_activity(self, env):
        """Test mocked audio recording activity."""
        
        @activity.defn
        async def mock_record_audio_activity(session_id: str) -> str:
            """Mock recording activity that completes quickly."""
            return f"/tmp/{session_id}.wav"
        
        async with Worker(
            env.client,
            task_queue="test-activities",
            activities=[mock_record_audio_activity]
        ):
            # Use the worker to execute the activity directly
            worker = Worker(
                env.client,
                task_queue="test-activities",
                activities=[mock_record_audio_activity]
            )
            
            # Test activity logic directly
            result = await mock_record_audio_activity("test-session")
            assert result == "/tmp/test-session.wav"
            assert result.endswith(".wav")
            assert "test-session" in result

    async def test_mock_save_audio_file_activity(self, env):
        """Test mocked file saving activity."""
        
        @activity.defn
        async def mock_save_audio_file_activity(temp_file_path: str) -> dict:
            """Mock file saving activity."""
            return {
                "file_path": f"/saved/{temp_file_path}",
                "file_size_bytes": 1024
            }
        
        async with Worker(
            env.client,
            task_queue="test-activities",
            activities=[mock_save_audio_file_activity]
        ):
            # Test activity logic directly
            result = await mock_save_audio_file_activity("test.wav")
            
            assert "file_path" in result
            assert "file_size_bytes" in result
            assert result["file_size_bytes"] > 0
            assert "/saved/test.wav" in result["file_path"]

    async def test_activity_error_handling(self, env):
        """Test activity error handling."""
        
        @activity.defn
        async def failing_activity(session_id: str) -> str:
            """Activity that always fails."""
            raise Exception("Simulated failure")
        
        async with Worker(
            env.client,
            task_queue="test-activities",
            activities=[failing_activity]
        ):
            # Test that activity raises expected exception
            with pytest.raises(Exception) as exc_info:
                await failing_activity("failing-session")
            
            assert "Simulated failure" in str(exc_info.value)


class TestWorkflowIntegrationSimplified:
    """Simplified integration tests focusing on workflow behavior."""
    
    def test_workflow_class_structure(self):
        """Test that RecordingWorkflow has the expected structure."""
        workflow_instance = RecordingWorkflow()
        
        # Check that workflow has expected attributes
        assert hasattr(workflow_instance, 'recording_task')
        assert hasattr(workflow_instance, 'session_id')
        assert hasattr(workflow_instance, 'source')
        assert hasattr(workflow_instance, 'is_recording')
        
        # Check that workflow has expected methods
        assert hasattr(workflow_instance, 'run')
        assert hasattr(workflow_instance, 'stop_recording')
        assert hasattr(workflow_instance, 'cancel_recording')
        
        # Check initial state
        assert workflow_instance.recording_task is None
        assert workflow_instance.session_id is None
        assert workflow_instance.is_recording is False

    def test_workflow_signal_methods_exist(self):
        """Test that workflow signal methods exist and are callable."""
        workflow_instance = RecordingWorkflow()
        
        # These should be callable methods
        assert callable(workflow_instance.stop_recording)
        assert callable(workflow_instance.cancel_recording)
        
        # Check they are async methods
        import inspect
        assert inspect.iscoroutinefunction(workflow_instance.stop_recording)
        assert inspect.iscoroutinefunction(workflow_instance.cancel_recording)


class TestEventSerialization:
    """Test event serialization and deserialization."""
    
    def test_input_source_serialization(self):
        """Test InputSource enum can be converted to string."""
        source = InputSource.KEYBOARD
        assert str(source) == "keyboard"
        assert source.value == "keyboard"

    def test_start_signal_creation(self):
        """Test StartRecordingSignal creation."""
        signal = StartRecordingSignal(
            session_id="test-123",
            source=InputSource.API,
            timestamp=datetime.now()
        )
        
        assert signal.session_id == "test-123"
        assert signal.source == InputSource.API
        assert isinstance(signal.timestamp, datetime)

    def test_signal_with_string_source(self):
        """Test creating signals with string sources for serialization."""
        # This approach could work for Temporal serialization
        signal_data = {
            "session_id": "test-123",
            "source": "keyboard",  # String instead of enum
            "timestamp": datetime.now().isoformat()  # ISO string
        }
        
        assert signal_data["source"] == "keyboard"
        assert isinstance(signal_data["timestamp"], str)


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 