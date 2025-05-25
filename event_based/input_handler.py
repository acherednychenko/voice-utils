"""Stateful input handler that tracks recording state."""

import logging
from enum import Enum, auto
from typing import Callable, List
from pynput import keyboard

from .events import (
    StartRecordingSignal, StopRecordingSignal, 
    CancelRecordingSignal, ExitSignal, InputSource
)


class RecordingState(Enum):
    IDLE = auto()
    RECORDING = auto()


class StatefulKeyboardHandler:
    """
    Stateful keyboard handler that tracks recording state.
    
    Same key combination does different things based on current state:
    - When IDLE + activation key → publish StartRecordingSignal
    - When RECORDING + activation key → publish StopRecordingSignal
    """
    
    def __init__(self, activation_shortcut="cmd+shift+.", exit_shortcut="ctrl+shift+q"):
        self.activation_shortcut = activation_shortcut
        self.exit_shortcut = exit_shortcut
        self._activation_keys = self._parse_key_combination(activation_shortcut)
        self._exit_keys = self._parse_key_combination(exit_shortcut)
        self._pressed_keys = set()
        self._listener = None
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # State tracking
        self.recording_state = RecordingState.IDLE
        self.current_session_id = None
        
        # Event callbacks
        self._signal_callbacks: List[Callable] = []
        
        self.logger.info(f"Stateful keyboard handler initialized")
        self.logger.info(f"Activation: {activation_shortcut}, Exit: {exit_shortcut}")
        
    def on_signal(self, callback: Callable):
        """Register callback for recording signals."""
        self._signal_callbacks.append(callback)
        
    def _emit_signal(self, signal):
        """Emit signal to all registered callbacks."""
        for callback in self._signal_callbacks:
            try:
                callback(signal)
            except Exception as e:
                self.logger.error(f"Signal callback failed: {e}")
                
    def _parse_key_combination(self, combo_str):
        """Parse key combination string."""
        key_map = {
            "ctrl": keyboard.Key.ctrl, "shift": keyboard.Key.shift,
            "alt": keyboard.Key.alt, "cmd": keyboard.Key.cmd,
            "space": keyboard.Key.space, ".": ".", "esc": keyboard.Key.esc,
        }
        return [key_map.get(k, k) for k in combo_str.lower().split("+")]
        
    def _is_combo_pressed(self, combo):
        """Check if key combination is pressed."""
        return all(k in self._pressed_keys for k in combo)
        
    def _on_key_press(self, key):
        """Handle key press events."""
        self._pressed_keys.add(key)
        
        # Check for activation shortcut
        if self._is_combo_pressed(self._activation_keys):
            self._handle_activation()
            
        # Check for exit shortcut
        if self._is_combo_pressed(self._exit_keys):
            self._handle_exit()
            
    def _on_key_release(self, key):
        """Handle key release events."""
        self._pressed_keys.discard(key)
        
    def _handle_activation(self):
        """Handle activation key press based on current state."""
        if self.recording_state == RecordingState.IDLE:
            # Start new recording session
            import uuid
            session_id = f"session-{str(uuid.uuid4())}"
            self.current_session_id = session_id
            self.recording_state = RecordingState.RECORDING
            
            signal = StartRecordingSignal(session_id, InputSource.KEYBOARD)
            self.logger.info(f"🎤 Starting recording: {session_id}")
            print(f"🎤 Starting recording session: {session_id}")
            self._emit_signal(signal)
            
        elif self.recording_state == RecordingState.RECORDING:
            # Stop current recording session
            if self.current_session_id:
                signal = StopRecordingSignal(self.current_session_id, InputSource.KEYBOARD)
                self.logger.info(f"⏹️ Stopping recording: {self.current_session_id}")
                print(f"⏹️ Stopping recording session: {self.current_session_id}")
                self._emit_signal(signal)
                
            self.recording_state = RecordingState.IDLE
            self.current_session_id = None
            
    def _handle_exit(self):
        """Handle exit key press."""
        if self.recording_state == RecordingState.RECORDING and self.current_session_id:
            # Cancel current recording before exit
            signal = CancelRecordingSignal(
                self.current_session_id, 
                InputSource.KEYBOARD, 
                "exit_requested"
            )
            self.logger.info(f"🛑 Cancelling recording due to exit: {self.current_session_id}")
            print(f"🛑 Cancelling recording session: {self.current_session_id}")
            self._emit_signal(signal)
            
        # Emit exit signal
        exit_signal = ExitSignal(InputSource.KEYBOARD)
        self.logger.info("🛑 Exit requested")
        print("🛑 Exit requested")
        self._emit_signal(exit_signal)
        
        self.recording_state = RecordingState.IDLE
        self.current_session_id = None
        
    def get_state_info(self) -> dict:
        """Get current state information."""
        return {
            "recording_state": self.recording_state.name,
            "current_session_id": self.current_session_id,
            "activation_shortcut": self.activation_shortcut,
            "exit_shortcut": self.exit_shortcut
        }
        
    def start(self):
        """Start keyboard listener."""
        self._listener = keyboard.Listener(
            on_press=self._on_key_press,
            on_release=self._on_key_release
        )
        self._listener.start()
        self.logger.info("Stateful keyboard handler started")
        
    def stop(self):
        """Stop keyboard listener."""
        if self._listener:
            self._listener.stop()
            self._listener = None
        self.logger.info("Stateful keyboard handler stopped") 