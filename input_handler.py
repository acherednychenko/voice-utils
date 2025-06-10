import threading
import time
import logging
from pynput import keyboard
from enum import Enum, auto


class InputCommand(Enum):
    """Commands that can be triggered by various input methods"""

    # Command to start audio recording
    START_RECORDING = auto()

    # Command to stop audio recording and process the data
    STOP_RECORDING = auto()

    # Command to cancel current recording without processing
    CANCEL = auto()

    # Command to exit the application
    EXIT = auto()


class InputHandler:
    """
    Base class for all input handlers.
    Handles notifying registered callbacks when commands are triggered.
    """

    def __init__(self):
        self.command_callbacks = {
            InputCommand.START_RECORDING: [],
            InputCommand.STOP_RECORDING: [],
            InputCommand.CANCEL: [],
            InputCommand.EXIT: [],
        }

    def on_command(self, command, callback):
        """
        Register a callback for a specific command

        Args:
            command: The InputCommand to listen for
            callback: Function to call when command is triggered
        """
        if command in self.command_callbacks:
            self.command_callbacks[command].append(callback)

    def _trigger_command(self, command, *args, **kwargs):
        """
        Trigger callbacks for a specific command

        Args:
            command: The InputCommand being triggered
            *args, **kwargs: Arguments to pass to the callbacks
        """
        if command in self.command_callbacks:
            for callback in self.command_callbacks[command]:
                callback(*args, **kwargs)

    def start(self):
        """Start the input handler"""
        pass

    def stop(self):
        """Stop the input handler"""
        pass


class EnterKeyInputHandler(InputHandler):
    """
    Input handler that uses Enter key to start/stop recording.
    Presents a console interface.
    """

    def __init__(self):
        super().__init__()
        self.running = False
        self.recording = False

    def start(self):
        """Start monitoring for console input"""
        self.running = True
        while self.running:
            cmd = input("Press Enter to begin (or type 'q' to exit): ")
            if cmd.lower() == 'q':
                self._trigger_command(InputCommand.EXIT)
                self.running = False
                break

            if not self.recording:
                # Start recording
                print("Recording... (press Enter to stop)")
                self._trigger_command(InputCommand.START_RECORDING)
                self.recording = True

                # Wait for Enter to stop
                input()
                self._trigger_command(InputCommand.STOP_RECORDING)
                self.recording = False

    def stop(self):
        """Stop monitoring for console input"""
        self.running = False


class KeyboardShortcutHandler(InputHandler):
    """
    Input handler that uses keyboard shortcuts to trigger commands.
    """

    # Map of common shortcut names to pynput key combinations
    KEY_MAPPINGS = {
        "ctrl": keyboard.Key.ctrl,
        "ctrl_l": keyboard.Key.ctrl_l,
        "ctrl_r": keyboard.Key.ctrl_r,
        "shift": keyboard.Key.shift,
        "shift_l": keyboard.Key.shift_l,
        "shift_r": keyboard.Key.shift_r,
        "alt": keyboard.Key.alt,
        "alt_l": keyboard.Key.alt_l,
        "alt_r": keyboard.Key.alt_r,
        "cmd": keyboard.Key.cmd,
        "cmd_l": keyboard.Key.cmd_l,
        "cmd_r": keyboard.Key.cmd_r,
        "space": keyboard.Key.space,
        ".": ".",
        "w": "w",
        "esc": keyboard.Key.esc,
    }

    # Groups of equivalent keys (any key in the group counts as matching)
    KEY_EQUIVALENTS = {
        keyboard.Key.ctrl: [keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r],
        keyboard.Key.shift: [keyboard.Key.shift, keyboard.Key.shift_l, keyboard.Key.shift_r],
        keyboard.Key.alt: [keyboard.Key.alt, keyboard.Key.alt_l, keyboard.Key.alt_r],
        keyboard.Key.cmd: [keyboard.Key.cmd, keyboard.Key.cmd_l, keyboard.Key.cmd_r],
    }

    def __init__(
        self,
        record_shortcut="cmd+shift+.",
        exit_shortcut="ctrl+shift+q",
        cancel_shortcut="ctrl+shift+w",
        toggle_mode=False,
        min_recording_duration=1.0,
        cooldown_period=0.5,
    ):
        super().__init__()
        self.record_shortcut_str = record_shortcut
        self.exit_shortcut_str = exit_shortcut
        self.cancel_shortcut_str = cancel_shortcut
        self.record_keys = self._parse_key_combination(record_shortcut)
        self.exit_keys = self._parse_key_combination(exit_shortcut)
        self.cancel_keys = self._parse_key_combination(cancel_shortcut)

        self.pressed_keys = set()
        self.exit_requested = threading.Event()
        self.is_recording = False
        self.listener = None
        self.toggle_mode = toggle_mode

        # Timing controls
        self.min_recording_duration = min_recording_duration  # Minimum time recording must be active
        self.cooldown_period = cooldown_period  # Minimum time between recordings
        self.recording_start_time = 0
        self.last_recording_end_time = 0

        # For toggle mode
        self.last_shortcut_time = 0
        self.shortcut_cooldown = 0.5  # seconds

        # Setup logger
        self.logger = logging.getLogger(self.__class__.__name__)
        self._init_logger()

    def _init_logger(self):
        """Initialize logger with appropriate settings"""
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)

            # Only show warnings or higher in the console
            handler.setLevel(logging.WARNING)
            self.logger.addHandler(handler)

            # Keep the logger itself at DEBUG level in case we want to add a file handler later
            self.logger.setLevel(logging.DEBUG)

            # Prevent propagation to avoid duplicate logs
            self.logger.propagate = False

    def _parse_key_combination(self, combination_str):
        """Parse a key combination string into pynput key objects"""
        keys = []
        for key_str in combination_str.lower().split("+"):
            if key_str in self.KEY_MAPPINGS:
                keys.append(self.KEY_MAPPINGS[key_str])
            else:
                # For regular character keys
                keys.append(key_str)
        return keys

    def _is_key_in_combination(self, key, combination):
        """
        Check if a key is in a key combination, accounting for equivalent keys

        Args:
            key: The key to check
            combination: List of keys in the combination

        Returns:
            True if the key or an equivalent key is in the combination
        """
        # Direct match
        if key in combination:
            return True

        # Check if this key is an equivalent of any key in the combination
        for combo_key in combination:
            if combo_key in self.KEY_EQUIVALENTS and key in self.KEY_EQUIVALENTS[combo_key]:
                return True

        return False

    def _is_combination_pressed(self, combination):
        """
        Check if all keys in a combination are pressed, accounting for equivalent keys

        Args:
            combination: List of keys in the combination

        Returns:
            True if all keys in the combination are pressed
        """
        for combo_key in combination:
            # Special case for period "."
            if combo_key == ".":
                # Check for both "." and period key
                if "." not in self.pressed_keys and keyboard.KeyCode.from_char('.') not in self.pressed_keys:
                    return False
            # For non-modifier keys, exact match is required
            elif combo_key not in self.KEY_EQUIVALENTS:
                if combo_key not in self.pressed_keys:
                    return False
            # For modifier keys, any equivalent is acceptable
            else:
                if not any(k in self.pressed_keys for k in self.KEY_EQUIVALENTS[combo_key]):
                    return False
        return True

    def _on_key_press(self, key):
        """Handler for key press events"""
        try:
            # For regular character keys
            if hasattr(key, "char") and key.char:
                key_val = key.char.lower()
            else:
                key_val = key

            self.pressed_keys.add(key_val)
            # Use DEBUG level so it won't appear in console with default settings
            self.logger.debug(f"Key pressed: {key_val}, current pressed keys: {self.pressed_keys}")

            # Check for exit combination
            if self._is_combination_pressed(self.exit_keys):
                # Use DEBUG level instead of INFO to avoid console output
                self.logger.debug(f"Exit shortcut detected: {self.exit_shortcut_str}")
                self._trigger_command(InputCommand.EXIT)
                self.exit_requested.set()
                return False  # Stop listener

            # Check for cancel combination (only when recording)
            if self.is_recording and self._is_combination_pressed(self.cancel_keys):
                self.logger.debug(f"Cancel shortcut detected: {self.cancel_shortcut_str}")
                self.is_recording = False
                self.last_recording_end_time = time.time()
                self._trigger_command(InputCommand.CANCEL)
                return True  # Continue listening

            # Check if all required keys are pressed for recording
            if self._is_combination_pressed(self.record_keys):
                # In toggle mode, handle start/stop toggling on key press
                if self.toggle_mode:
                    # Add cooldown to prevent multiple triggers
                    current_time = time.time()
                    if current_time - self.last_shortcut_time > self.shortcut_cooldown:
                        self.last_shortcut_time = current_time

                        if not self.is_recording:
                            # Start recording if not already recording and cooldown has passed
                            if self._can_start_recording():
                                self.logger.debug(f"Start recording (toggle mode)")
                                self.is_recording = True
                                self.recording_start_time = current_time
                                self._trigger_command(InputCommand.START_RECORDING)
                            else:
                                remaining_cooldown = self.cooldown_period - (
                                    current_time - self.last_recording_end_time
                                )
                                self.logger.debug(
                                    f"Cannot start recording yet, {remaining_cooldown:.1f}s cooldown remaining"
                                )
                        else:
                            # Stop recording if already recording and minimum duration has passed
                            if self._can_stop_recording():
                                self.logger.debug(f"Stop recording (toggle mode)")
                                self.is_recording = False
                                self.last_recording_end_time = current_time
                                self._trigger_command(InputCommand.STOP_RECORDING)
                            else:
                                remaining_duration = self.min_recording_duration - (
                                    current_time - self.recording_start_time
                                )
                                self.logger.debug(
                                    f"Cannot stop recording yet, {remaining_duration:.1f}s minimum duration remaining"
                                )
                # In hold mode (default), start recording on key press if not recording
                elif not self.is_recording:
                    if self._can_start_recording():
                        self.logger.debug(f"Record shortcut detected: {self.record_shortcut_str}")
                        self.is_recording = True
                        self.recording_start_time = time.time()
                        self._trigger_command(InputCommand.START_RECORDING)
                    else:
                        remaining_cooldown = self.cooldown_period - (time.time() - self.last_recording_end_time)
                        self.logger.debug(f"Cannot start recording yet, {remaining_cooldown:.1f}s cooldown remaining")

        except Exception as e:
            # Keep error messages at ERROR level
            self.logger.error(f"Error in key press handler: {e}", exc_info=True)

        return True  # Continue listening

    def _on_key_release(self, key):
        """Handler for key release events"""
        try:
            # For regular character keys
            if hasattr(key, "char") and key.char:
                key_val = key.char.lower()
            else:
                key_val = key

            # Remove from pressed keys set
            if key_val in self.pressed_keys:
                self.pressed_keys.remove(key_val)

            # Use DEBUG level so it won't appear in console with default settings
            self.logger.debug(f"Key released: {key_val}, remaining pressed keys: {self.pressed_keys}")

            # Only process key release events if we're in hold mode (not toggle mode)
            # and we're currently recording
            if not self.toggle_mode and self.is_recording:
                # Check if minimum recording duration has passed before allowing stop
                if not self._can_stop_recording():
                    remaining_duration = self.min_recording_duration - (time.time() - self.recording_start_time)
                    self.logger.debug(
                        f"Cannot stop recording yet, {remaining_duration:.1f}s minimum duration remaining"
                    )
                    return True  # Continue listening, don't stop recording

                # Handle period key specially
                if key_val == "." or key_val == keyboard.KeyCode.from_char('.'):
                    if "." in self.record_keys:
                        # Use DEBUG level instead of INFO to avoid console output
                        self.logger.debug(f"Recording stopped - period key released")
                        self.is_recording = False
                        self.last_recording_end_time = time.time()
                        self._trigger_command(InputCommand.STOP_RECORDING)
                        return

                # Check if the released key is part of our shortcut
                for shortcut_key in self.record_keys:
                    if key_val == shortcut_key or (
                        shortcut_key in self.KEY_EQUIVALENTS and key_val in self.KEY_EQUIVALENTS[shortcut_key]
                    ):
                        # Use DEBUG level instead of INFO to avoid console output
                        self.logger.debug(f"Recording stopped - shortcut key released: {key_val}")
                        self.is_recording = False
                        self.last_recording_end_time = time.time()
                        self._trigger_command(InputCommand.STOP_RECORDING)
                        break

        except Exception as e:
            # Keep error messages at ERROR level
            self.logger.error(f"Error in key release handler: {e}", exc_info=True)

        return True  # Continue listening

    def start(self):
        """Start keyboard listener"""
        self.exit_requested.clear()
        self.pressed_keys.clear()
        self.is_recording = False

        print(f"Shortcut mode activated.")
        if self.toggle_mode:
            print(f"Press {self.record_shortcut_str} to start recording, press again to stop.")
        else:
            print(f"Hold down {self.record_shortcut_str} to record audio, release to transcribe.")
        print(f"Press {self.cancel_shortcut_str} to cancel current recording.")
        print(f"Press {self.exit_shortcut_str} to exit.")
        print(
            f"Timing: {self.min_recording_duration}s minimum recording, {self.cooldown_period}s cooldown between recordings."
        )
        print("Waiting for keyboard commands...")
        print()

        # Log the key combinations we're looking for at DEBUG level
        self.logger.debug(f"Watching for record shortcut: {self.record_shortcut_str}")
        self.logger.debug(f"Watching for cancel shortcut: {self.cancel_shortcut_str}")
        self.logger.debug(f"Watching for exit shortcut: {self.exit_shortcut_str}")
        self.logger.debug(f"Toggle mode: {self.toggle_mode}")

        # Start keyboard listener
        self.listener = keyboard.Listener(on_press=self._on_key_press, on_release=self._on_key_release)
        self.listener.start()

        # Wait for exit request
        self.exit_requested.wait()

    def stop(self):
        """Stop keyboard listener"""
        self.exit_requested.set()
        if self.listener and self.listener.is_alive():
            self.listener.stop()

    def is_running(self):
        """Check if the keyboard listener is running"""
        return self.listener is not None and self.listener.is_alive()

    @property
    def description(self):
        """Get description of this input handler"""
        return f"Hold {self.record_shortcut_str} to record, release to transcribe. Press {self.cancel_shortcut_str} to cancel recording. Press {self.exit_shortcut_str} to exit."

    def _can_start_recording(self):
        """Check if enough time has passed since last recording ended to start a new one"""
        if self.last_recording_end_time == 0:
            return True  # First recording
        return time.time() - self.last_recording_end_time >= self.cooldown_period

    def _can_stop_recording(self):
        """Check if recording has been active for minimum duration"""
        if self.recording_start_time == 0:
            return True  # Shouldn't happen, but allow stopping
        return time.time() - self.recording_start_time >= self.min_recording_duration
