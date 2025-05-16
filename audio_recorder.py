import numpy as np
import sounddevice as sd
import threading


class AudioRecorder:
    """
    Handles recording audio from a microphone.
    Focus is only on capturing audio, with no file operations.
    """
    
    def __init__(self, samplerate=None, channels=1, dtype="int16", verbose=True):
        """
        Initialize audio recorder with device settings.
        
        Args:
            samplerate: Sample rate to use (defaults to device default)
            channels: Number of audio channels (mono=1, stereo=2)
            dtype: Data type for audio samples
            verbose: If True, print information about selected recording device
        """
        
        # Get device information
        device_info = self.get_device_info(verbose=verbose)
        default_device = device_info["selected_device"]
        
        # Use default device sample rate if not specified
        if samplerate is None:
            self.samplerate = int(default_device["default_samplerate"])
        else:
            self.samplerate = int(samplerate)
        
        # Store the selected device for reference
        self.selected_device = default_device
        
        self.channels = channels
        self.dtype = dtype
        self.stream = None
        self.recorded_chunks = []
        self.is_recording = False
        self.recording_lock = threading.Lock()
    
    def start_recording(self):
        """Start recording audio from microphone"""
        with self.recording_lock:
            if self.is_recording:
                return  # Already recording
            
            # Clear previous recording data
            self.recorded_chunks = []
            self.is_recording = True
            
            # Start the InputStream using the selected device
            self.stream = sd.InputStream(
                device=self.selected_device["index"],
                samplerate=self.samplerate,
                channels=self.channels,
                dtype=self.dtype,
                callback=self._audio_callback
            )
            self.stream.start()
            return True
    
    def stop_recording(self):
        """Stop the current recording"""
        with self.recording_lock:
            if not self.is_recording:
                return False  # Not recording
            
            self.is_recording = False
            
            # Stop and close the stream
            if self.stream:
                self.stream.stop()
                self.stream.close()
                self.stream = None
            
            return True
    
    def get_recording(self):
        """
        Get the current recording as a NumPy array.
        
        Returns:
            NumPy array of audio data, or empty array if no recording.
        """
        with self.recording_lock:
            if not self.recorded_chunks:
                return np.array([])
            
            return np.concatenate(self.recorded_chunks, axis=0)
    
    def is_active(self):
        """Check if recording is currently active"""
        return self.is_recording
    
    def get_sample_rate(self):
        """Get the current sample rate"""
        return self.samplerate
    
    @staticmethod
    def get_device_info(verbose=False):
        """
        Get information about available recording devices and the selected device.
        
        Args:
            verbose: If True, print the device information
            
        Returns:
            Dictionary containing information about devices and the selected device
        """
        # Get all devices
        devices = sd.query_devices()
        recording_devices = [device for device in devices if device['max_input_channels'] > 0]
        
        # Get default input device
        default_device = sd.query_devices(kind="input")
        
        if verbose:
            print("\nAvailable recording devices:")
            for device in recording_devices:
                print(f"[{device['index']}] {device['name']} (Inputs: {device['max_input_channels']})")
            
            print(f"\nSelected recording device: [{default_device['index']}] {default_device['name']}")
            print(f"Default samplerate: {default_device['default_samplerate']} Hz\n")
        
        return {
            "available_devices": recording_devices,
            "selected_device": default_device
        }
    
    @staticmethod
    def print_device_info():
        """Print available recording devices and the currently selected device (for backward compatibility)"""
        AudioRecorder.get_device_info(verbose=True)
    
    def _audio_callback(self, indata, frames, time_info, status):
        """Callback function for the InputStream"""
        if self.is_recording:
            self.recorded_chunks.append(indata.copy()) 