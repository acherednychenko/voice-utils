import asyncio
import random
import os
import tempfile
import argparse
import time
import threading
from abc import ABC, abstractmethod
import pyperclip

import numpy as np
import sounddevice as sd
import dotenv
import soundfile as sf
from pydub import AudioSegment
from pynput import keyboard

from agents import (
    Agent,
    function_tool,
    set_tracing_disabled,
)
from agents.voice import (
    AudioInput as AgentAudioInput,
    SingleAgentVoiceWorkflow,
    VoicePipeline,
)
from agents.extensions.handoff_prompt import prompt_with_handoff_instructions
from agents.voice import TTSModelSettings, VoicePipelineConfig
from openai import OpenAI

assert dotenv.load_dotenv(".env", override=True)

# Setup the OpenAI client and pipeline
client = OpenAI()

openai_sample_rate = 24000  # The standard sample rate for OpenAI TTS

input_device = sd.query_devices(kind="input")
output_device = sd.query_devices(kind="output")

in_samplerate = int(sd.query_devices(kind="input")["default_samplerate"])
out_samplerate = int(sd.query_devices(kind="output")["default_samplerate"])


class AudioInputInterface(ABC):
    """Abstract interface for audio input recording"""

    @abstractmethod
    def record(self) -> np.ndarray:
        """Record audio and return the numpy buffer"""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Return a description of how to use this input method"""
        pass


class EnterKeyAudioInput(AudioInputInterface):
    """Audio input that starts recording when called and stops on Enter key press"""

    def __init__(self, samplerate=in_samplerate, channels=1, dtype="int16"):
        self.samplerate = samplerate
        self.channels = channels
        self.dtype = dtype

    @property
    def description(self) -> str:
        return "Press Enter to start recording, then press Enter again to stop"

    def record(self) -> np.ndarray:
        print("Recording... (press Enter to stop)")
        recorded_chunks = []

        # Start streaming from microphone until Enter is pressed
        with sd.InputStream(
            samplerate=self.samplerate,
            channels=self.channels,
            dtype=self.dtype,
            callback=lambda indata, frames, time, status: recorded_chunks.append(
                indata.copy()
            ),
        ):
            input()  # Wait for Enter key

        # Concatenate chunks into single buffer
        if not recorded_chunks:
            return np.array([])

        return np.concatenate(recorded_chunks, axis=0)


class KeyboardShortcutAudioInput(AudioInputInterface):
    """Audio input that records while a keyboard shortcut is held down"""

    # Map of common shortcut names to pynput key combinations
    KEY_MAPPINGS = {
        "ctrl": keyboard.Key.ctrl,
        "shift": keyboard.Key.shift,
        "alt": keyboard.Key.alt,
        "cmd": keyboard.Key.cmd,
        "space": keyboard.Key.space,
        ".": ".",
        "esc": keyboard.Key.esc,
    }

    def __init__(
        self,
        key_combination="cmd+shift+.",
        exit_combination="ctrl+q",
        copy_to_clipboard=True,
        samplerate=in_samplerate,
        channels=1,
        dtype="int16",
    ):
        self.key_combination_str = key_combination
        self.exit_combination_str = exit_combination
        self.copy_to_clipboard = copy_to_clipboard
        self.keys = self._parse_key_combination(key_combination)
        self.exit_keys = self._parse_key_combination(exit_combination)
        self.samplerate = samplerate
        self.channels = channels
        self.dtype = dtype
        self.is_recording = False
        self.recorded_chunks = []
        self.pressed_keys = set()
        self.recording_done = threading.Event()
        self.exit_requested = threading.Event()
        self.processing_lock = threading.Lock()
        self.last_recording = None

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

    @property
    def description(self) -> str:
        clipboard_status = "ON" if self.copy_to_clipboard else "OFF"
        return f"Hold down {self.key_combination_str} to record audio, release to transcribe. Press {self.exit_combination_str} to exit. Copy to clipboard: {clipboard_status}"

    def _on_key_press(self, key):
        """Handler for key press events"""
        try:
            # For regular character keys
            if hasattr(key, "char") and key.char:
                key_val = key.char.lower()
            else:
                key_val = key

            self.pressed_keys.add(key_val)

            # Check for exit combination
            if all(k in self.pressed_keys for k in self.exit_keys):
                self.exit_requested.set()
                return False  # Stop listener

            # Check if all required keys are pressed for recording
            if all(k in self.pressed_keys for k in self.keys):
                if not self.is_recording:
                    self._start_recording()
        except Exception as e:
            print(f"Error in key press handler: {e}")

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

            # If any key from our combination is released, stop recording and process
            if key_val in self.keys and self.is_recording:
                self._stop_recording()
                self._process_current_recording()
        except Exception as e:
            print(f"Error in key release handler: {e}")

    def _process_current_recording(self):
        """Process the current recording if it's valid"""
        # Use a lock to prevent multiple simultaneous processing attempts
        if self.processing_lock.acquire(blocking=False):
            try:
                if self.recorded_chunks and len(self.recorded_chunks) > 0:
                    # Create a copy of the current chunks
                    chunks_to_process = self.recorded_chunks.copy()
                    self.recorded_chunks = []  # Clear for next recording

                    # Concatenate the chunks
                    recording = np.concatenate(chunks_to_process, axis=0)

                    # Only process if we have actual audio data
                    if len(recording) > 0:
                        self.last_recording = recording
                        # Signal that we have a recording to process
                        self.recording_done.set()
            finally:
                self.processing_lock.release()

    def run_continuous(self, save_format):
        """Run in continuous listening mode until exit is requested"""
        self.exit_requested.clear()

        print(f"Shortcut mode activated. {self.description}")
        print("Waiting for keyboard commands...\n")

        # Start keyboard listener
        listener = keyboard.Listener(
            on_press=self._on_key_press,
            on_release=self._on_key_release
        )
        listener.start()

        # Monitor for recordings or exit request
        while not self.exit_requested.is_set():
            # Wait for a recording to be completed, but with a timeout to check exit flag
            if self.recording_done.wait(timeout=0.5):
                self.recording_done.clear()  # Reset for next recording

                if self.last_recording is not None:
                    # Process the recording
                    process_audio(self.last_recording, save_format, self.copy_to_clipboard)
                    self.last_recording = None

        # Ensure the listener is stopped
        listener.stop()
        return False  # Signal to exit the main loop

    def record(self) -> np.ndarray:
        self.recorded_chunks = []
        self.is_recording = False
        self.pressed_keys = set()
        self.recording_done.clear()

        # Start keyboard listeners
        key_listener = keyboard.Listener(
            on_press=self._on_key_press, on_release=self._on_key_release
        )
        key_listener.start()

        # Set up audio stream
        with sd.InputStream(
            samplerate=self.samplerate,
            channels=self.channels,
            dtype=self.dtype,
            callback=self._audio_callback,
        ):
            print(f"Ready to record. {self.description}")

            # Wait until recording is completed or timeout after 5 minutes
            self.recording_done.wait(timeout=300)

        # Stop keyboard listener
        key_listener.stop()

        # Concatenate chunks into single buffer
        if not self.recorded_chunks or len(self.recorded_chunks) == 0:
            return np.array([])

        recording = np.concatenate(self.recorded_chunks, axis=0)
        self.recorded_chunks = []  # Clear for next recording
        return recording

    def _start_recording(self):
        print("Recording started...")
        self.is_recording = True

    def _stop_recording(self):
        print("Recording stopped.")
        self.is_recording = False

    def _audio_callback(self, indata, frames, time_info, status):
        if self.is_recording:
            self.recorded_chunks.append(indata.copy())


def save_audio(audio_data, sample_rate, output_format="wav"):
    """Save numpy audio data to file in specified format

    Args:
        audio_data: NumPy array containing audio data
        sample_rate: Sample rate of the audio data (must be integer)
        output_format: Format to save as ('wav' or 'mp3')

    Returns:
        Path to the saved file
    """
    # Ensure sample rate is an integer
    sample_rate = int(sample_rate)

    # Create a temporary filename with appropriate extension
    temp_dir = tempfile.gettempdir()
    random_id = int(random.random() * 10000)

    if output_format.lower() == "mp3":
        # For MP3, we need to first save as WAV, then convert
        temp_wav = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        sf.write(temp_wav.name, audio_data, sample_rate)

        output_path = os.path.join(temp_dir, f"audio_{random_id}.mp3")
        audio = AudioSegment.from_wav(temp_wav.name)
        audio.export(output_path, format="mp3")

        # Clean up temp file
        os.unlink(temp_wav.name)
    else:
        # Direct WAV save
        output_path = os.path.join(temp_dir, f"audio_{random_id}.wav")
        sf.write(output_path, audio_data, sample_rate)

    return output_path


def process_audio(recording, save_format, copy_to_clipboard=True):
    """Process recorded audio - save, transcribe and display results

    Args:
        recording: NumPy array of audio data
        save_format: Format to save audio in ("wav" or "mp3")
        copy_to_clipboard: Whether to copy transcription to clipboard
    """
    if len(recording) == 0:
        print("No audio recorded.")
        return

    # Save recording to file - measure time separately from the actual operation
    start_time = time.time()
    recording_path = save_audio(recording, in_samplerate, save_format)
    elapsed_time = time.time() - start_time
    print(f"Recording saved to: {recording_path} (took {elapsed_time:.3f} seconds)")

    # Open the file for transcription
    with open(recording_path, "rb") as audio_file:
        transcription = client.audio.transcriptions.create(
            model="gpt-4o-mini-transcribe",
            file=audio_file,
            response_format="text",
            prompt="Text is English, Ukrainian or Russian",
            stream=True,
        )

    # Collect the full transcription text
    print("Transcription: ", end="")
    full_text = ""
    for event in transcription:
        if event.type == "transcript.text.delta":
            full_text += event.delta
            print(event.delta, end="", flush=True)

    print("\n")

    # Copy to clipboard if requested
    if copy_to_clipboard and full_text:
        try:
            pyperclip.copy(full_text)
            print("Transcription copied to clipboard! ✓")
        except Exception as e:
            print(f"Failed to copy to clipboard: {e}")


async def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Voice assistant with audio recording")
    parser.add_argument(
        "--save-format",
        type=str,
        choices=["mp3", "wav"],
        default="wav",
        help="Format to save audio files (mp3 or wav)",
    )
    parser.add_argument(
        "--input-method",
        type=str,
        choices=["enter", "shortcut"],
        default="enter",
        help="Method to control recording",
    )
    parser.add_argument(
        "--shortcut",
        type=str,
        default="cmd+shift+.",
        help="Keyboard shortcut to use for recording (only with --input-method=shortcut)",
    )
    parser.add_argument(
        "--exit-shortcut",
        type=str,
        default="ctrl+q",
        help="Keyboard shortcut to exit the program in shortcut mode",
    )
    parser.add_argument(
        "--no-clipboard",
        action="store_true",
        help="Disable automatic copying of transcriptions to clipboard",
    )
    args = parser.parse_args()

    print(f"Audio will be saved in {args.save_format.upper()} format")

    # Create the appropriate input handler
    if args.input_method == "shortcut":
        audio_input = KeyboardShortcutAudioInput(
            key_combination=args.shortcut,
            exit_combination=args.exit_shortcut,
            copy_to_clipboard=not args.no_clipboard
        )

        print(f"Using input method: {audio_input.description}")
        print("Starting continuous shortcut mode...")

        # Use a separate audio stream that's always active
        with sd.InputStream(
            samplerate=in_samplerate,
            channels=1,
            dtype="int16",
            callback=audio_input._audio_callback,
        ):
            # Run the continuous shortcut mode
            audio_input.run_continuous(args.save_format)
    else:
        # Traditional Enter key mode
        audio_input = EnterKeyAudioInput()
        print(f"Using input method: {audio_input.description}")

        while True:
            # Check for input to either record or exit
            cmd = input("Press Enter to begin (or type 'q' to exit): ")
            if cmd.lower() == "q":
                print("Exiting...")
                break

            # Record audio using the selected input method
            recording = audio_input.record()
            process_audio(recording, args.save_format, not args.no_clipboard)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nProgram interrupted. Exiting...")
        exit(0)
