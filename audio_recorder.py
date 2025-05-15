import numpy as np
import sounddevice as sd
import threading


class AudioRecorder:
    """
    Handles recording audio from a microphone.
    Focus is only on capturing audio, with no file operations.
    """
    
    def __init__(self, samplerate=None, channels=1, dtype="int16"):
        """
        Initialize audio recorder with device settings.
        
        Args:
            samplerate: Sample rate to use (defaults to device default)
            channels: Number of audio channels (mono=1, stereo=2)
            dtype: Data type for audio samples
        """
        # Use default device sample rate if not specified
        if samplerate is None:
            self.samplerate = int(sd.query_devices(kind="input")["default_samplerate"])
        else:
            self.samplerate = int(samplerate)
        
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
            
            # Start the InputStream
            self.stream = sd.InputStream(
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
    
    def _audio_callback(self, indata, frames, time_info, status):
        """Callback function for the InputStream"""
        if self.is_recording:
            self.recorded_chunks.append(indata.copy()) 