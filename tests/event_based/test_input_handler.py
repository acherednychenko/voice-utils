"""Unit tests for StatefulKeyboardHandler."""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime

# Clean imports - conftest.py handles the path setup
from event_based.input_handler import StatefulKeyboardHandler, RecordingState
from event_based.events import (
    StartRecordingSignal, StopRecordingSignal, CancelRecordingSignal,
    ExitSignal, InputSource
)


class TestStatefulKeyboardHandler:
    """Test StatefulKeyboardHandler state management and signal emission."""
    
    @pytest.fixture
    def handler(self):
        """Create handler with test shortcuts."""
        return StatefulKeyboardHandler(
            activation_shortcut="cmd+shift+.",
            exit_shortcut="ctrl+shift+q"
        )
    
    @pytest.fixture
    def signal_callback(self):
        """Mock signal callback."""
        return Mock()

    def test_initialization(self, handler):
        """Test handler initializes correctly."""
        assert handler.activation_shortcut == "cmd+shift+."
        assert handler.exit_shortcut == "ctrl+shift+q"
        assert handler.recording_state == RecordingState.IDLE
        assert handler.current_session_id is None
        assert handler._signal_callbacks == []

    def test_on_signal_registration(self, handler, signal_callback):
        """Test signal callback registration."""
        handler.on_signal(signal_callback)
        assert signal_callback in handler._signal_callbacks

    def test_state_transitions_idle_to_recording(self, handler, signal_callback):
        """Test state transition from IDLE to RECORDING."""
        handler.on_signal(signal_callback)
        
        # Simulate activation key press when IDLE
        handler._handle_activation()
        
        # Should transition to RECORDING and emit StartRecordingSignal
        assert handler.recording_state == RecordingState.RECORDING
        assert handler.current_session_id is not None
        
        signal_callback.assert_called_once()
        call_args = signal_callback.call_args[0][0]
        assert isinstance(call_args, StartRecordingSignal)
        assert call_args.session_id == handler.current_session_id
        assert call_args.source == InputSource.KEYBOARD

    def test_state_transitions_recording_to_idle(self, handler, signal_callback):
        """Test state transition from RECORDING to IDLE."""
        handler.on_signal(signal_callback)
        
        # First transition to RECORDING
        handler._handle_activation()
        signal_callback.reset_mock()
        
        # Second activation key press should stop recording
        handler._handle_activation()
        
        # Should transition back to IDLE and emit StopRecordingSignal
        assert handler.recording_state == RecordingState.IDLE
        assert handler.current_session_id is None
        
        signal_callback.assert_called_once()
        call_args = signal_callback.call_args[0][0]
        assert isinstance(call_args, StopRecordingSignal)
        assert call_args.source == InputSource.KEYBOARD

    def test_exit_signal_from_idle(self, handler, signal_callback):
        """Test exit signal when in IDLE state."""
        handler.on_signal(signal_callback)
        
        # Handle exit key when IDLE
        handler._handle_exit()
        
        # Should emit ExitSignal
        signal_callback.assert_called_once()
        call_args = signal_callback.call_args[0][0]
        assert isinstance(call_args, ExitSignal)
        assert call_args.source == InputSource.KEYBOARD

    def test_exit_signal_from_recording(self, handler, signal_callback):
        """Test exit signal when in RECORDING state."""
        handler.on_signal(signal_callback)
        
        # Start recording first
        handler._handle_activation()
        signal_callback.reset_mock()
        
        # Handle exit key when RECORDING
        handler._handle_exit()
        
        # Should emit CancelRecordingSignal then ExitSignal
        assert signal_callback.call_count == 2
        
        # First call should be cancel signal
        cancel_call = signal_callback.call_args_list[0][0][0]
        assert isinstance(cancel_call, CancelRecordingSignal)
        assert cancel_call.reason == "exit_requested"
        
        # Second call should be exit signal
        exit_call = signal_callback.call_args_list[1][0][0]
        assert isinstance(exit_call, ExitSignal)

    def test_session_id_generation(self, handler, signal_callback):
        """Test session ID generation and consistency."""
        handler.on_signal(signal_callback)
        
        # Start recording
        handler._handle_activation()
        session_id = handler.current_session_id
        
        # Stop recording  
        handler._handle_activation()
        
        # Start recording again
        handler._handle_activation()
        new_session_id = handler.current_session_id
        
        # Session IDs should be different
        assert session_id != new_session_id
        assert new_session_id is not None

    def test_no_callback_registered(self, handler):
        """Test handler gracefully handles no callback."""
        # Should not crash when no callback is registered
        handler._handle_activation()
        handler._handle_exit()

    @patch('event_based.input_handler.keyboard.Listener')
    def test_start_keyboard_listener(self, mock_listener_class, handler):
        """Test keyboard listener startup."""
        mock_listener = Mock()
        mock_listener_class.return_value = mock_listener
        
        handler.start()
        
        # Should create and start a Listener
        mock_listener_class.assert_called_once()
        mock_listener.start.assert_called_once()
        
        # Verify the listener was created with correct callbacks
        call_args = mock_listener_class.call_args
        assert 'on_press' in call_args[1]
        assert 'on_release' in call_args[1]

    @patch('event_based.input_handler.keyboard.Listener')
    def test_stop_keyboard_listener(self, mock_listener_class, handler):
        """Test keyboard listener shutdown."""
        mock_listener = Mock()
        mock_listener_class.return_value = mock_listener
        
        # Start first to create the listener
        handler.start()
        
        # Now stop it
        handler.stop()
        
        mock_listener.stop.assert_called_once()

    def test_multiple_activation_presses(self, handler, signal_callback):
        """Test rapid activation key presses."""
        handler.on_signal(signal_callback)
        
        # Multiple rapid presses should alternate states
        handler._handle_activation()  # IDLE -> RECORDING
        assert handler.recording_state == RecordingState.RECORDING
        
        handler._handle_activation()  # RECORDING -> IDLE
        assert handler.recording_state == RecordingState.IDLE
        
        handler._handle_activation()  # IDLE -> RECORDING
        assert handler.recording_state == RecordingState.RECORDING
        
        # Should have emitted start, stop, start signals
        assert signal_callback.call_count == 3
        
        signal_types = [type(call[0][0]) for call in signal_callback.call_args_list]
        assert signal_types == [StartRecordingSignal, StopRecordingSignal, StartRecordingSignal]

    def test_state_consistency(self, handler, signal_callback):
        """Test state remains consistent across operations."""
        handler.on_signal(signal_callback)
        
        # Initial state
        assert handler.recording_state == RecordingState.IDLE
        assert handler.current_session_id is None
        
        # Start recording
        handler._handle_activation()
        session_id = handler.current_session_id
        assert handler.recording_state == RecordingState.RECORDING
        assert session_id is not None
        
        # Exit while recording
        handler._handle_exit()
        assert handler.recording_state == RecordingState.IDLE
        assert handler.current_session_id is None

    def test_signal_timing(self, handler, signal_callback):
        """Test signal timing and session ID consistency."""
        handler.on_signal(signal_callback)
        
        # Start recording
        handler._handle_activation()
        start_signal = signal_callback.call_args[0][0]
        session_id = start_signal.session_id
        
        signal_callback.reset_mock()
        
        # Stop recording
        handler._handle_activation()
        stop_signal = signal_callback.call_args[0][0]
        
        # Session IDs should match
        assert stop_signal.session_id == session_id
        assert isinstance(stop_signal.timestamp, datetime)

    def test_interrupted_recording_session(self, handler):
        """Test complete interrupted recording session."""
        signals_received = []
        
        def capture_signal(signal):
            signals_received.append(signal)
            
        handler.on_signal(capture_signal)
        
        # Simulate interrupted session
        handler._handle_activation()  # Start
        handler._handle_exit()        # Exit while recording
        
        # Should emit 3 signals: start, cancel, exit
        assert len(signals_received) == 3
        
        # Verify signal types and order
        assert isinstance(signals_received[0], StartRecordingSignal)
        assert isinstance(signals_received[1], CancelRecordingSignal)
        assert isinstance(signals_received[2], ExitSignal)
        
        # Verify cancel signal has correct reason
        cancel_signal = signals_received[1]
        assert cancel_signal.reason == "exit_requested"


class TestRecordingState:
    """Test RecordingState enum."""
    
    def test_recording_state_values(self):
        """Test RecordingState enum values."""
        # auto() generates integer values starting from 1
        assert RecordingState.IDLE.value == 1
        assert RecordingState.RECORDING.value == 2

    def test_recording_state_string_representation(self):
        """Test RecordingState string representation."""
        assert RecordingState.IDLE.name == "IDLE"
        assert RecordingState.RECORDING.name == "RECORDING"


class TestKeyboardHandlerIntegration:
    """Integration tests for keyboard handler with real-like scenarios."""
    
    def test_complete_recording_session(self):
        """Test complete recording session flow."""
        handler = StatefulKeyboardHandler("test+key", "exit+key")
        signals_received = []
        
        def capture_signal(signal):
            signals_received.append(signal)
        
        handler.on_signal(capture_signal)
        
        # Simulate complete session
        handler._handle_activation()  # Start
        handler._handle_activation()  # Stop
        
        assert len(signals_received) == 2
        
        start_signal = signals_received[0]
        stop_signal = signals_received[1]
        
        assert isinstance(start_signal, StartRecordingSignal)
        assert isinstance(stop_signal, StopRecordingSignal)
        assert start_signal.session_id == stop_signal.session_id


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 