import os
import tempfile
import random
import datetime
import numpy as np
import soundfile as sf
from pydub import AudioSegment


class AudioProcessor:
    """
    Handles audio file operations including saving, loading, and format conversion.
    Works with both raw audio data and file paths.
    """
    
    @staticmethod
    def save_audio(audio_data, sample_rate, output_format="wav", output_dir=None, filename=None):
        """
        Save numpy audio data to file in specified format
        
        Args:
            audio_data: NumPy array containing audio data
            sample_rate: Sample rate of the audio data (must be integer)
            output_format: Format to save as ('wav' or 'mp3')
            output_dir: Directory to save file (defaults to temp directory)
            filename: Base filename (without extension, timestamp added if not provided)
            
        Returns:
            Path to the saved file
        """
        # Ensure sample rate is an integer
        sample_rate = int(sample_rate)
        
        # Use temp directory if not specified
        if output_dir is None:
            output_dir = tempfile.gettempdir()
        
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # Generate filename with timestamp if not provided
        if filename is None:
            # Create timestamp in format YYYY-MM-DD_HH-MM-SS
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            random_suffix = f"_{int(random.random() * 1000):03d}"
            filename = f"audio_{timestamp}{random_suffix}"
        
        # Full path for the output file
        if output_format.lower() == "mp3":
            # For MP3, we need to first save as WAV, then convert
            temp_wav = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            sf.write(temp_wav.name, audio_data, sample_rate)
            
            output_path = os.path.join(output_dir, f"{filename}.mp3")
            audio = AudioSegment.from_wav(temp_wav.name)
            audio.export(output_path, format="mp3")
            
            # Clean up temp file
            os.unlink(temp_wav.name)
        else:
            # Direct WAV save
            output_path = os.path.join(output_dir, f"{filename}.wav")
            sf.write(output_path, audio_data, sample_rate)
        
        return output_path
    
    @staticmethod
    def load_audio(file_path):
        """
        Load audio data from a file path
        
        Args:
            file_path: Path to audio file (wav, mp3, etc.)
            
        Returns:
            Tuple of (audio_data, sample_rate) where audio_data is a NumPy array
        """
        file_ext = os.path.splitext(file_path)[1].lower()
        
        if file_ext == '.wav':
            # Direct loading for WAV
            audio_data, sample_rate = sf.read(file_path)
            return audio_data, sample_rate
        
        elif file_ext == '.mp3':
            # For MP3, convert to WAV first
            temp_wav = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            temp_wav_path = temp_wav.name
            temp_wav.close()
            
            # Convert to WAV using pydub
            audio = AudioSegment.from_mp3(file_path)
            audio.export(temp_wav_path, format="wav")
            
            # Load the WAV
            audio_data, sample_rate = sf.read(temp_wav_path)
            
            # Clean up temp file
            os.unlink(temp_wav_path)
            
            return audio_data, sample_rate
        
        else:
            raise ValueError(f"Unsupported audio format: {file_ext}")
    
    @staticmethod
    def convert_format(file_path, target_format):
        """
        Convert audio file to a different format
        
        Args:
            file_path: Path to source audio file
            target_format: Target format ('wav' or 'mp3')
            
        Returns:
            Path to the converted file
        """
        # Get file information
        dir_path = os.path.dirname(file_path)
        base_name = os.path.splitext(os.path.basename(file_path))[0]
        
        # Create output path
        output_path = os.path.join(dir_path, f"{base_name}.{target_format}")
        
        # Convert using pydub
        audio = AudioSegment.from_file(file_path)
        audio.export(output_path, format=target_format)
        
        return output_path 