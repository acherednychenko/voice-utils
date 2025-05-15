import threading
import logging
import time
from enum import Enum, auto
from pynput import keyboard


class KeyboardCommand(Enum):
    """Commands that can be triggered by keyboard shortcuts"""
    
    # Command to start recording or action
    START = auto()
    
    # Command to stop recording or action
    STOP = auto()
    
    # Command to exit the application
    EXIT = auto()


class RecordingMode(Enum):
    """Recording activation modes"""
    
    # Hold mode: press and hold to record, release to stop
    HOLD = auto()
    
    # Toggle mode: press once to start, press again to stop
    TOGGLE = auto()


class KeyboardController:
    """
    Keyboard controller that triggers callbacks based on keyboard shortcuts.
    Handles shortcut parsing, key tracking, and event dispatching.
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
        "esc": keyboard.Key.esc,
    }
    
    # Groups of equivalent keys (any key in the group counts as matching)
    KEY_EQUIVALENTS = {
        keyboard.Key.ctrl: [keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r],
        keyboard.Key.shift: [keyboard.Key.shift, keyboard.Key.shift_l, keyboard.Key.shift_r],
        keyboard.Key.alt: [keyboard.Key.alt, keyboard.Key.alt_l, keyboard.Key.alt_r],
        keyboard.Key.cmd: [keyboard.Key.cmd, keyboard.Key.cmd_l, keyboard.Key.cmd_r],
    }
    
    def __init__(self, start_stop_keys="cmd+shift+.", exit_keys="ctrl+shift+q", 
                 recording_mode=RecordingMode.TOGGLE, log_level=logging.INFO):
        """
        Initialize the keyboard controller with customizable shortcuts
        
        Args:
            start_stop_keys: Keyboard shortcut string for starting/stopping (format: "key1+key2+...")
            exit_keys: Keyboard shortcut string for exiting (format: "key1+key2+...")
            recording_mode: RecordingMode.HOLD for press-and-hold or RecordingMode.TOGGLE for click-to-toggle
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        """
        # Parse shortcuts
        self.start_stop_keys_str = start_stop_keys
        self.exit_keys_str = exit_keys
        self.start_stop_keys = self._parse_key_combination(start_stop_keys)
        self.exit_keys = self._parse_key_combination(exit_keys)
        
        # Set recording mode
        self.recording_mode = recording_mode
        
        # State tracking
        self.pressed_keys = set()
        self.active = False
        self.listener = None
        self.exit_requested = threading.Event()
        
        # Toggle mode state
        self.last_shortcut_time = 0
        self.shortcut_cooldown = 0.5  # seconds
        self.shortcut_pressed = False
        
        # Callbacks
        self.command_callbacks = {
            KeyboardCommand.START: [],
            KeyboardCommand.STOP: [],
            KeyboardCommand.EXIT: []
        }
        
        # Setup logger
        self.logger = logging.getLogger(self.__class__.__name__)
        self._setup_logger(log_level)
    
    def _setup_logger(self, log_level):
        """Initialize logger with appropriate settings"""
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            
            # Only show warnings or higher in the console by default
            handler.setLevel(logging.WARNING)
            self.logger.addHandler(handler)
            
            # Set log level
            self.logger.setLevel(log_level)
            
            # Prevent propagation to avoid duplicate logs
            self.logger.propagate = False
    
    def on_command(self, command, callback):
        """
        Register a callback for a specific command
        
        Args:
            command: The KeyboardCommand to listen for
            callback: Function to call when command is triggered
        """
        if command in self.command_callbacks:
            self.command_callbacks[command].append(callback)
    
    def _trigger_command(self, command, *args, **kwargs):
        """
        Trigger callbacks for a specific command
        
        Args:
            command: The KeyboardCommand being triggered
            *args, **kwargs: Arguments to pass to the callbacks
        """
        if command in self.command_callbacks:
            for callback in self.command_callbacks[command]:
                callback(*args, **kwargs)
    
    def _parse_key_combination(self, combination_str):
        """
        Parse a key combination string into pynput key objects
        
        Args:
            combination_str: String in format "key1+key2+..."
            
        Returns:
            List of pynput keys
        """
        keys = []
        for key_str in combination_str.lower().split("+"):
            if key_str in self.KEY_MAPPINGS:
                keys.append(self.KEY_MAPPINGS[key_str])
            else:
                # For regular character keys
                keys.append(key_str)
        return keys
    
    def _is_combination_pressed(self, combination):
        """
        Check if all keys in a combination are pressed
        
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
    
    def _is_key_in_combination(self, key, combination):
        """Check if a key is part of a combination"""
        # Direct match
        if key in combination:
            return True
            
        # Check equivalent keys
        for combo_key in combination:
            if combo_key in self.KEY_EQUIVALENTS and key in self.KEY_EQUIVALENTS[combo_key]:
                return True
                
        return False
    
    def _on_key_press(self, key):
        """
        Handler for key press events
        
        Args:
            key: The pressed key
            
        Returns:
            True to continue listening, False to stop
        """
        try:
            # For regular character keys
            if hasattr(key, "char") and key.char:
                key_val = key.char.lower()
            else:
                key_val = key
                
            self.pressed_keys.add(key_val)
            self.logger.debug(f"Key pressed: {key_val}, current pressed keys: {self.pressed_keys}")
            
            # Check for exit combination
            if self._is_combination_pressed(self.exit_keys):
                self.logger.debug(f"Exit shortcut detected: {self.exit_keys_str}")
                self._trigger_command(KeyboardCommand.EXIT)
                self.exit_requested.set()
                return False  # Stop listener
            
            # Check for shortcut combination
            is_shortcut = self._is_combination_pressed(self.start_stop_keys)
            
            # TOGGLE MODE
            if self.recording_mode == RecordingMode.TOGGLE and is_shortcut:
                # Handle shortcut press with cooldown
                current_time = time.time()
                if current_time - self.last_shortcut_time > self.shortcut_cooldown:
                    self.last_shortcut_time = current_time
                    # Toggle recording state
                    if not self.active:
                        self.logger.debug(f"START command triggered (toggle mode)")
                        self.active = True
                        self._trigger_command(KeyboardCommand.START)
                    else:
                        self.logger.debug(f"STOP command triggered (toggle mode)")
                        self.active = False
                        self._trigger_command(KeyboardCommand.STOP)
                else:
                    # Skip rapid presses during cooldown
                    self.logger.debug(f"Ignoring shortcut press during cooldown period ({current_time - self.last_shortcut_time:.2f}s)")
            
            # HOLD MODE - only start if not already active
            elif self.recording_mode == RecordingMode.HOLD and is_shortcut and not self.active:
                self.logger.debug(f"START command triggered (hold mode)")
                self.active = True
                self._trigger_command(KeyboardCommand.START)
                
        except Exception as e:
            self.logger.error(f"Error in key press handler: {e}", exc_info=True)
        
        return True  # Continue listening
    
    def _on_key_release(self, key):
        """
        Handler for key release events
        
        Args:
            key: The released key
            
        Returns:
            True to continue listening, False to stop
        """
        try:
            # For regular character keys
            if hasattr(key, "char") and key.char:
                key_val = key.char.lower()
            else:
                key_val = key
                
            # Remove from pressed keys
            if key_val in self.pressed_keys:
                self.pressed_keys.remove(key_val)
                
            self.logger.debug(f"Key released: {key_val}, remaining pressed keys: {self.pressed_keys}")
            
            # In HOLD mode only: check if a shortcut key was released
            if self.recording_mode == RecordingMode.HOLD and self.active:
                # Check if the released key is part of our shortcut
                if key_val == "." or key_val == keyboard.KeyCode.from_char('.'):
                    if "." in self.start_stop_keys:
                        self.logger.debug(f"STOP command triggered - period key released (hold mode)")
                        self.active = False
                        self._trigger_command(KeyboardCommand.STOP)
                        return True
                
                # Check any other shortcut key
                for shortcut_key in self.start_stop_keys:
                    if key_val == shortcut_key or (
                        shortcut_key in self.KEY_EQUIVALENTS and 
                        key_val in self.KEY_EQUIVALENTS[shortcut_key]
                    ):
                        self.logger.debug(f"STOP command triggered - shortcut key released: {key_val} (hold mode)")
                        self.active = False
                        self._trigger_command(KeyboardCommand.STOP)
                        break
                
        except Exception as e:
            self.logger.error(f"Error in key release handler: {e}", exc_info=True)
        
        return True  # Continue listening
    
    def start(self):
        """Start keyboard listener and wait for commands"""
        self.exit_requested.clear()
        self.pressed_keys.clear()
        self.active = False
        self.last_shortcut_time = 0
        
        # Log the key combinations we're looking for
        self.logger.debug(f"Watching for start/stop shortcut: {self.start_stop_keys_str}")
        self.logger.debug(f"Watching for exit shortcut: {self.exit_keys_str}")
        self.logger.debug(f"Recording mode: {self.recording_mode}")
        
        # Start keyboard listener
        self.listener = keyboard.Listener(
            on_press=self._on_key_press, 
            on_release=self._on_key_release
        )
        self.listener.start()
        
        # Display instructions
        print(f"Keyboard shortcuts activated:")
        if self.recording_mode == RecordingMode.HOLD:
            print(f"• Press and hold {self.start_stop_keys_str} to record, release to stop")
        else:
            print(f"• Press {self.start_stop_keys_str} to start, press again to stop")
        print(f"• Press {self.exit_keys_str} to exit")
        print()
        
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


# Command line argument parsing helper functions
def parse_keyboard_args(parser):
    """
    Add keyboard controller arguments to an ArgumentParser
    
    Args:
        parser: argparse.ArgumentParser instance
        
    Returns:
        Modified parser with keyboard arguments added
    """
    parser.add_argument(
        "--start-stop-keys", 
        type=str, 
        default="cmd+shift+.",
        help="Keyboard shortcut to start/stop (format: key1+key2+...)"
    )
    parser.add_argument(
        "--exit-keys", 
        type=str, 
        default="ctrl+shift+q",
        help="Keyboard shortcut to exit (format: key1+key2+...)"
    )
    parser.add_argument(
        "--hold-mode",
        action="store_true",
        help="Use hold mode (press and hold to record, release to stop) instead of toggle mode"
    )
    return parser


# Unit testing utility
def test_key_parsing():
    """Test the keyboard shortcut parsing functionality"""
    controller = KeyboardController()
    
    # Test basic key parsing
    keys = controller._parse_key_combination("ctrl+shift+a")
    assert keyboard.Key.ctrl in keys
    assert keyboard.Key.shift in keys
    assert "a" in keys
    
    # Test with period
    keys = controller._parse_key_combination("cmd+shift+.")
    assert keyboard.Key.cmd in keys
    assert keyboard.Key.shift in keys
    assert "." in keys
    
    print("Key parsing tests passed!") 