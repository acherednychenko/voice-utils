import sys
import threading
import time
import itertools


class SpinnerAnimation:
    """
    Simple ASCII spinner animation for console.
    Can be used to indicate ongoing processes like recording or transcribing.
    """
    
    def __init__(self, message="", frames=None, delay=0.1):
        """
        Initialize spinner animation
        
        Args:
            message: Text to display next to the spinner
            frames: Animation frames (characters or strings)
            delay: Time between animation frames in seconds
        """
        self.message = message
        self.delay = delay
        self.running = False
        self.spinner_thread = None
        
        # Default animation frames if none provided
        if frames is None:
            self.frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        else:
            self.frames = frames
    
    def start(self, message=None):
        """
        Start the spinner animation
        
        Args:
            message: Optional new message to display
        """
        if message is not None:
            self.message = message
            
        if self.running:
            return
            
        self.running = True
        self.spinner_thread = threading.Thread(target=self._spin_worker)
        self.spinner_thread.daemon = True
        self.spinner_thread.start()
    
    def stop(self, message=None, clear=True):
        """
        Stop the spinner animation
        
        Args:
            message: Optional final message to display
            clear: Whether to clear the animation line
        """
        self.running = False
        if self.spinner_thread:
            self.spinner_thread.join()
            
        if clear:
            sys.stdout.write("\r" + " " * (len(self.message) + 10))
            sys.stdout.write("\r")
            sys.stdout.flush()
            
        if message:
            sys.stdout.write(f"\r{message}\n")
            sys.stdout.flush()
    
    def update_message(self, message):
        """Update the message displayed with the spinner"""
        self.message = message
    
    def _spin_worker(self):
        """Worker thread that displays the animation"""
        spinner_cycle = itertools.cycle(self.frames)
        while self.running:
            frame = next(spinner_cycle)
            sys.stdout.write(f"\r{frame} {self.message}")
            sys.stdout.flush()
            time.sleep(self.delay)


class RecordingAnimator:
    """Helper class for voice recording animations and timing"""
    
    def __init__(self):
        """Initialize with different spinners for different states"""
        self.recording_spinner = SpinnerAnimation(
            message="Recording...", 
            frames=["🔴", "⭕", "⚪", "⭕"],
            delay=0.5
        )
        
        self.transcribing_spinner = SpinnerAnimation(
            message="Transcribing...",
            frames=["⣾", "⣽", "⣻", "⢿", "⡿", "⣟", "⣯", "⣷"],
            delay=0.1
        )
        
        # Timing-related variables
        self.recording_end_time = None
        self.transcription_start_time = None
    
    def start_recording(self):
        """Start recording animation"""
        self.recording_spinner.start()
    
    def stop_recording(self):
        """
        Stop recording animation and mark the recording end time
        
        Returns:
            Recording end timestamp (float)
        """
        self.recording_spinner.stop(clear=True)
        self.recording_end_time = time.time()
        return self.recording_end_time
    
    def start_transcribing(self, print_to_console=True):
        """
        Start transcribing animation and mark transcription start time
        
        Args:
            print_to_console: Whether to print the "Transcribing..." message
            
        Returns:
            Transcription start timestamp (float)
        """
        if print_to_console:
            # Start the spinner normally if we want to show it
            self.transcribing_spinner.start()
        else:
            # For hidden animation, we need to set it as running for state tracking
            # but we don't actually want to display anything
            self.transcribing_spinner.running = True
            self.transcribing_spinner.spinner_thread = None
        
        # Record transcription start time
        self.transcription_start_time = time.time()
        return self.transcription_start_time
    
    def stop_transcribing(self, text=None, print_to_console=True, error=False):
        """
        Stop transcribing animation, calculate elapsed time, and optionally show the text
        
        Args:
            text: Transcribed text to display
            print_to_console: Whether to print the result text
            error: Whether an error occurred during transcription
            
        Returns:
            Tuple of (elapsed_time_since_recording_end, elapsed_time_since_transcription_start)
        """
        # Always stop the spinner thread properly
        self.transcribing_spinner.running = False
        if self.transcribing_spinner.spinner_thread:
            self.transcribing_spinner.spinner_thread.join()
        
        # Clear the animation line
        sys.stdout.write("\r" + " " * (len(self.transcribing_spinner.message) + 10))
        sys.stdout.write("\r")
        sys.stdout.flush()
        
        # Calculate elapsed times
        now = time.time()
        transcription_time = now - (self.transcription_start_time or now)
        total_time = now - (self.recording_end_time or now)
        
        # Print the final message if requested
        if print_to_console:
            if text:
                sys.stdout.write(f"\rTranscription: {text}\n")
            elif error:
                sys.stdout.write("\rTranscription failed.\n")
            else:
                sys.stdout.write("\rTranscription complete.\n")
            sys.stdout.flush()
        
        # Return timing information
        return total_time, transcription_time


class TranscriptionVisualizer:
    """
    Unified component for visualizing the transcription process,
    handling both animation and token printing in a coordinated way.
    """
    
    def __init__(self):
        """Initialize the visualizer"""
        self.spinner = SpinnerAnimation(
            message="Transcribing...",
            frames=["⣾", "⣽", "⣻", "⢿", "⡿", "⣟", "⣯", "⣷"],
            delay=0.1
        )
        self.recording_end_time = None
        self.transcription_start_time = None
        self.is_streaming = False
        self.collected_text = ""
        
    def set_recording_end_time(self, timestamp=None):
        """Set the recording end time for timing calculations"""
        self.recording_end_time = timestamp or time.time()
    
    def start_transcribing(self):
        """Start the transcription visualization (spinner animation)"""
        self.transcription_start_time = time.time()
        self.spinner.start()
        self.is_streaming = False
        self.collected_text = ""
        
    def process_token(self, token):
        """
        Process an incoming token
        
        Args:
            token: Text token to display
        """
        # If this is the first token, stop the spinner and prepare for text
        if not self.is_streaming:
            # Stop spinner and clear the line
            self.spinner.running = False
            if self.spinner.spinner_thread:
                self.spinner.spinner_thread.join()
            
            # Clear the line
            sys.stdout.write("\r" + " " * (len(self.spinner.message) + 10) + "\r")
            sys.stdout.flush()
            
            # Now we're in streaming mode
            self.is_streaming = True
            print()  # Start on a fresh line
        
        # Add the token to our collected text and print it
        self.collected_text += token
        print(token, end="", flush=True)
    
    def finish_transcription(self):
        """
        Finish the transcription visualization, calculate time, etc.
        
        Returns:
            Tuple of (full_transcription_text, elapsed_time)
        """
        # Ensure we've exited animation mode
        if not self.is_streaming:
            self.spinner.stop(clear=True)
        
        # Calculate elapsed time
        now = time.time()
        total_time = now - (self.recording_end_time or now)
        
        # Add a newline for cleanliness but use write to avoid focus stealing
        sys.stdout.write("\n")
        
        # Use the terminal bell character to notify completion without stealing focus
        sys.stdout.write(f"\aCompleted in {total_time:.3f} s\n")
        sys.stdout.flush()
        
        return self.collected_text, total_time 