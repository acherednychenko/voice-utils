#!/usr/bin/env python3
"""
Unit tests for the keyboard_controller module.
"""
import unittest
import threading
import time
from unittest.mock import MagicMock, patch
from pynput import keyboard

from keyboard_controller import KeyboardController, KeyboardCommand


class TestKeyboardController(unittest.TestCase):
    """Tests for the KeyboardController class"""
    
    def test_parse_key_combination(self):
        """Test parsing key combinations from strings"""
        controller = KeyboardController()
        
        # Test simple combinations
        keys = controller._parse_key_combination("ctrl+a")
        self.assertIn(keyboard.Key.ctrl, keys)
        self.assertIn("a", keys)
        
        # Test with multiple modifiers
        keys = controller._parse_key_combination("ctrl+shift+alt+x")
        self.assertIn(keyboard.Key.ctrl, keys)
        self.assertIn(keyboard.Key.shift, keys)
        self.assertIn(keyboard.Key.alt, keys)
        self.assertIn("x", keys)
        
        # Test with period
        keys = controller._parse_key_combination("cmd+shift+.")
        self.assertIn(keyboard.Key.cmd, keys)
        self.assertIn(keyboard.Key.shift, keys)
        self.assertIn(".", keys)
    
    def test_on_command_registration(self):
        """Test registering command callbacks"""
        controller = KeyboardController()
        
        # Create mock callbacks
        start_callback = MagicMock()
        stop_callback = MagicMock()
        exit_callback = MagicMock()
        
        # Register callbacks
        controller.on_command(KeyboardCommand.START, start_callback)
        controller.on_command(KeyboardCommand.STOP, stop_callback)
        controller.on_command(KeyboardCommand.EXIT, exit_callback)
        
        # Verify callbacks were registered
        self.assertIn(start_callback, controller.command_callbacks[KeyboardCommand.START])
        self.assertIn(stop_callback, controller.command_callbacks[KeyboardCommand.STOP])
        self.assertIn(exit_callback, controller.command_callbacks[KeyboardCommand.EXIT])
    
    def test_trigger_command(self):
        """Test triggering commands calls registered callbacks"""
        controller = KeyboardController()
        
        # Create mock callbacks
        callback1 = MagicMock()
        callback2 = MagicMock()
        
        # Register callbacks
        controller.on_command(KeyboardCommand.START, callback1)
        controller.on_command(KeyboardCommand.START, callback2)
        
        # Trigger command
        controller._trigger_command(KeyboardCommand.START, "test_arg", keyword="test_kwarg")
        
        # Verify callbacks were called with arguments
        callback1.assert_called_once_with("test_arg", keyword="test_kwarg")
        callback2.assert_called_once_with("test_arg", keyword="test_kwarg")
    
    def test_is_combination_pressed(self):
        """Test checking if key combinations are pressed"""
        controller = KeyboardController()
        
        # Set up pressed keys
        controller.pressed_keys = {keyboard.Key.ctrl, keyboard.Key.shift, "a"}
        
        # Test matching combination
        self.assertTrue(controller._is_combination_pressed([keyboard.Key.ctrl, keyboard.Key.shift, "a"]))
        
        # Test partial match (missing one key)
        self.assertFalse(controller._is_combination_pressed([keyboard.Key.ctrl, keyboard.Key.shift, "b"]))
        
        # Test with equivalent keys (ctrl_l instead of ctrl)
        controller.pressed_keys = {keyboard.Key.ctrl_l, keyboard.Key.shift, "a"}
        self.assertTrue(controller._is_combination_pressed([keyboard.Key.ctrl, keyboard.Key.shift, "a"]))
    
    @patch('keyboard_controller.keyboard.Listener')
    def test_start_stop(self, mock_listener_class):
        """Test starting and stopping the controller"""
        # Mock the listener
        mock_listener = MagicMock()
        mock_listener_class.return_value = mock_listener
        
        controller = KeyboardController()
        
        # Create a thread to start the controller
        def start_controller():
            controller.start()
        
        # Start in a thread since it blocks until exit_requested
        thread = threading.Thread(target=start_controller)
        thread.daemon = True
        thread.start()
        
        # Wait for listener to be created
        time.sleep(0.1)
        
        # Verify listener was started
        mock_listener.start.assert_called_once()
        
        # Stop the controller
        controller.stop()
        
        # Wait for thread to complete
        thread.join(timeout=1.0)
        
        # Verify listener was stopped
        mock_listener.stop.assert_called_once()
    
    @patch('keyboard_controller.keyboard.Listener')
    def test_key_press_triggers_start(self, mock_listener_class):
        """Test that key press triggers START command"""
        # Mock the listener
        mock_listener = MagicMock()
        mock_listener_class.return_value = mock_listener
        
        controller = KeyboardController(start_stop_keys="ctrl+a")
        
        # Create mock callback
        start_callback = MagicMock()
        controller.on_command(KeyboardCommand.START, start_callback)
        
        # Simulate key presses
        controller.pressed_keys = {keyboard.Key.ctrl, "a"}
        
        # Call the key press handler
        controller._on_key_press(keyboard.Key.ctrl)
        controller._on_key_press(keyboard.KeyCode.from_char('a'))
        
        # Verify callback was called
        start_callback.assert_called_once()
    
    @patch('keyboard_controller.keyboard.Listener')
    def test_key_release_triggers_stop(self, mock_listener_class):
        """Test that key release triggers STOP command"""
        # Mock the listener
        mock_listener = MagicMock()
        mock_listener_class.return_value = mock_listener
        
        controller = KeyboardController(start_stop_keys="ctrl+a")
        
        # Create mock callback
        stop_callback = MagicMock()
        controller.on_command(KeyboardCommand.STOP, stop_callback)
        
        # Set active state and simulate pressed keys
        controller.active = True
        controller.pressed_keys = {keyboard.Key.ctrl}
        controller.start_stop_keys = [keyboard.Key.ctrl, "a"]
        
        # Call the key release handler with "a" key
        controller._on_key_release(keyboard.KeyCode.from_char('a'))
        
        # Verify callback was called
        stop_callback.assert_called_once()


if __name__ == "__main__":
    unittest.main() 