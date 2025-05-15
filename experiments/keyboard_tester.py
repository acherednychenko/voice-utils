import os
import time
import collections
from pynput import keyboard

class KeyboardTester:
    """Tool to test and visualize keyboard input for specialized keyboards like Moergo Glove80"""
    
    def __init__(self, duration=60, max_history=20):
        """
        Initialize keyboard tester
        
        Args:
            duration: Maximum duration to run the test in seconds
            max_history: Maximum number of key events to keep in history
        """
        self.duration = duration
        self.max_history = max_history
        self.active_keys = set()
        self.key_history = collections.deque(maxlen=max_history)
        self.running = False
        self.listener = None
    
    def _format_key(self, key):
        """Format a key object into a readable string"""
        # Special key handling
        if isinstance(key, keyboard.Key):
            return f"[{key.name}]"
        # Character keys
        elif hasattr(key, 'char'):
            if key.char:
                return key.char
            else:
                return f"[unknown]"
        # For other key types
        else:
            return str(key)
    
    def _on_press(self, key):
        """Handle key press events"""
        try:
            key_str = self._format_key(key)
            self.active_keys.add(key_str)
            
            # Record the event
            event = {"type": "press", "key": key_str, "time": time.time()}
            self.key_history.append(event)
            
            # Show current state
            self._display_state()
        except Exception as e:
            print(f"Error in key press handler: {e}")
    
    def _on_release(self, key):
        """Handle key release events"""
        try:
            key_str = self._format_key(key)
            if key_str in self.active_keys:
                self.active_keys.remove(key_str)
            
            # Record the event
            event = {"type": "release", "key": key_str, "time": time.time()}
            self.key_history.append(event)
            
            # Show current state
            self._display_state()
            
            # Check for exit key (Esc)
            if key == keyboard.Key.esc:
                self.running = False
                return False
        except Exception as e:
            print(f"Error in key release handler: {e}")
    
    def _display_state(self):
        """Display the current keyboard state"""
        os.system('cls' if os.name == 'nt' else 'clear')
        print("=== Keyboard Test Mode ===")
        print("Press ESC to exit\n")
        
        # Display currently pressed keys
        print("Currently Active Keys:")
        if self.active_keys:
            key_list = sorted(list(self.active_keys))
            print(" + ".join(key_list))
        else:
            print("None")
        
        # Display active key combination as it would be used
        if self.active_keys:
            combo = "+".join(sorted(list(self.active_keys)))
            print(f"\nCurrent Combination: {combo}")
            print("Use this string with --shortcut option")
        
        # Show recent history
        print("\nRecent Key Events (newest first):")
        for i, event in enumerate(reversed(self.key_history)):
            event_time = event["time"]
            event_type = "↓" if event["type"] == "press" else "↑"
            print(f"{i+1:2d}. {event_type} {event['key']}")
    
    def run(self):
        """Run the keyboard test"""
        self.running = True
        
        print("Starting keyboard test mode...")
        print("Press keys to see how they're detected...")
        print("Press ESC to exit")
        
        # Create and start the listener
        self.listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release
        )
        self.listener.start()
        
        # Run for specified duration or until ESC pressed
        start_time = time.time()
        try:
            while self.running and (time.time() - start_time < self.duration):
                time.sleep(0.1)
        except KeyboardInterrupt:
            pass
        finally:
            if self.listener.is_alive():
                self.listener.stop()
        
        print("\nKeyboard test completed.")


if __name__ == "__main__":
    # This allows running the keyboard tester directly
    print("Running keyboard tester standalone mode")
    tester = KeyboardTester()
    tester.run() 