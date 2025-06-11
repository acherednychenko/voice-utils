import os
import argparse
import threading
import logging
import dotenv
import pyperclip
import time
import sys
from pynput.keyboard import Controller as KeyboardTyper

# Revert to using the original input handler implementation
from audio_recorder import AudioRecorder
from audio_processor import AudioProcessor
from input_handler import InputCommand, KeyboardShortcutHandler
from transcription_service import TranscriptionService
from utils import RecordingAnimator, TranscriptionVisualizer
from keyboard_controller import RecordingMode


class VoiceTranscriptionApp:
    """
    Main application that coordinates audio recording, processing and transcription.
    """

    def __init__(self, log_level=logging.INFO):
        """
        Initialize the voice transcription application

        Args:
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        """
        # Parse command-line arguments first
        self.args = self._parse_arguments()
        assert dotenv.load_dotenv(".env", override=True)

        # Override log level if specified in args
        if hasattr(self.args, 'log_level'):
            level_name = self.args.log_level.upper()
            numeric_level = getattr(logging, level_name, None)
            if isinstance(numeric_level, int):
                log_level = numeric_level

        # Setup logging
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(log_level)

        # Remove any existing handlers to prevent duplicates
        if self.logger.handlers:
            for handler in self.logger.handlers:
                self.logger.removeHandler(handler)

        # Add a single handler and prevent propagation to root logger
        self.logger.propagate = False
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

        self.logger.debug("Initializing VoiceTranscriptionApp")

        # Initialize components
        self.recorder = AudioRecorder()
        self.transcription_service = TranscriptionService(
            language=self.args.language, model=self.args.model, log_level=log_level
        )

        # Visualization components
        self.recording_animator = RecordingAnimator()
        self.transcription_visualizer = TranscriptionVisualizer()

        # Initialize keyboard typer if needed
        self.keyboard_typer = KeyboardTyper() if self.args.simulate_typing else None

        # Set up keyboard shortcut handler with toggle mode if requested
        self.logger.info(f"Using keyboard shortcut input handler: {self.args.shortcut}")
        self.input_handler = KeyboardShortcutHandler(
            record_shortcut=self.args.shortcut,
            exit_shortcut=self.args.exit_shortcut,
            cancel_shortcut=self.args.cancel_shortcut,
            toggle_mode=not self.args.hold_mode,
            min_recording_duration=self.args.min_recording_duration,
            cooldown_period=self.args.cooldown_period,
        )

        # Register command callbacks
        self.input_handler.on_command(InputCommand.START_RECORDING, self._handle_start_recording)
        self.input_handler.on_command(InputCommand.STOP_RECORDING, self._handle_stop_recording)
        self.input_handler.on_command(InputCommand.CANCEL, self._handle_cancel)
        self.input_handler.on_command(InputCommand.EXIT, self._handle_exit)

        # State variables
        self.exit_requested = threading.Event()

    def _parse_arguments(self):
        """Parse command-line arguments"""
        parser = argparse.ArgumentParser(description="Voice transcription application")

        # Input method configuration
        parser.add_argument(
            "--shortcut",
            type=str,
            default="cmd+shift+.",
            help="Keyboard shortcut to use for recording",
        )
        parser.add_argument(
            "--exit-shortcut",
            type=str,
            default="ctrl+shift+q",
            help="Keyboard shortcut to exit the program",
        )
        parser.add_argument(
            "--cancel-shortcut",
            type=str,
            default="ctrl+shift+w",
            help="Keyboard shortcut to cancel current recording without processing",
        )
        parser.add_argument(
            "--min-recording-duration",
            type=float,
            default=1.0,
            help="Minimum duration (in seconds) a recording must be active before it can be stopped (default: 1.0)",
        )
        parser.add_argument(
            "--cooldown-period",
            type=float,
            default=0.5,
            help="Minimum time (in seconds) to wait between recordings (default: 0.5)",
        )
        parser.add_argument(
            "--model",
            type=str,
            choices=["gpt-4o-mini-transcribe", "gpt-4o-transcribe"],
            default="gpt-4o-mini-transcribe",
            help="Model to use for transcription",
        )
        parser.add_argument(
            "--hold-mode",
            action="store_true",
            help="Use hold mode: press and hold to record, release to stop (default is toggle mode: press to start, press again to stop)",
        )

        # Audio file handling
        parser.add_argument(
            "--save-format",
            type=str,
            choices=["mp3", "wav"],
            default="wav",
            help="Format to save audio files",
        )
        parser.add_argument(
            "--file",
            type=str,
            help="Process an existing audio file instead of recording",
        )
        parser.add_argument(
            "--output-dir",
            type=str,
            help="Directory to save recordings (default: system temp dir)",
        )

        # Transcription options
        parser.add_argument(
            "--language",
            type=str,
            default="en",
            help="Language hint for transcription (e.g., 'en', 'ua')",
        )
        parser.add_argument(
            "--with-clipboard",
            action="store_true",
            help="Enable automatic copying of transcriptions to clipboard (copying is disabled by default)",
        )
        parser.add_argument(
            "--no-type",
            action="store_true",
            help="Disable simulating keyboard typing of transcribed text (typing is enabled by default)",
        )
        parser.add_argument(
            "--streaming",
            type=bool,
            default=False,
            help="Enable streaming of transcription (disabled by default)",
        )

        # Logging options
        parser.add_argument(
            "--log-level",
            type=str,
            choices=["debug", "info", "warning", "error", "critical"],
            default="info",
            help="Set logging level",
        )

        args = parser.parse_args()

        # Set simulate_typing based on the absence of no-type flag
        args.simulate_typing = not args.no_type

        return args

    def run(self):
        """Run the application"""
        # If processing an existing file
        if self.args.file:
            self.logger.info(f"Processing existing file: {self.args.file}")
            self._process_existing_file(self.args.file)
            return

        # Print startup info
        print(f"Voice Transcription App")
        print(f"Audio will be saved in {self.args.save_format.upper()} format")
        print(f"Using keyboard shortcut: {self.args.shortcut}")
        print(f"Cancel shortcut: {self.args.cancel_shortcut}")
        print(f"Exit shortcut: {self.args.exit_shortcut}")
        print(
            f"Mode: {'Hold mode (press and hold to record)' if self.args.hold_mode else 'Toggle mode (press to start/stop)'}"
        )
        print(f"Minimum recording duration: {self.args.min_recording_duration}s")
        print(f"Cooldown period between recordings: {self.args.cooldown_period}s")
        print(f"Clipboard copying: {'Disabled' if not self.args.with_clipboard else 'Enabled'}")
        print(f"Keyboard typing simulation: {'Enabled' if self.args.simulate_typing else 'Disabled'}")
        print()

        # Start the input handler
        try:
            self.logger.info("Starting input handler")
            self.input_handler.start()
        except KeyboardInterrupt:
            self.logger.info("Received keyboard interrupt")
            print("\nProgram interrupted. Exiting...")
        except Exception as e:
            self.logger.error(f"Error in input handler: {e}", exc_info=True)
        finally:
            self.logger.info("Stopping input handler")
            self.input_handler.stop()

    def _handle_start_recording(self):
        """Handle START_RECORDING command"""
        self.logger.debug("Handling START_RECORDING command")
        self.recorder.start_recording()

        # Start recording animation
        self.recording_animator.start_recording()

    def _handle_stop_recording(self):
        """Handle STOP_RECORDING command"""
        self.logger.debug("Handling STOP_RECORDING command")
        self.recorder.stop_recording()

        # Stop recording animation
        self.recording_animator.stop_recording()

        # Mark recording end time for the transcription visualizer
        self.transcription_visualizer.set_recording_end_time(time.time())

        # Get the recording
        audio_data = self.recorder.get_recording()
        if len(audio_data) == 0:
            self.logger.warning("No audio data recorded")
            print("No audio recorded.")
            return

        # Process the recording
        self.logger.debug(f"Processing recording ({len(audio_data)} samples)")
        self._process_audio_data(audio_data)

    def _handle_cancel(self):
        """Handle CANCEL command"""
        self.logger.debug("Handling CANCEL command")
        # Stop recording if active
        if self.recorder.is_active():
            self.logger.debug("Stopping active recording")
            self.recorder.stop_recording()
            self.recording_animator.stop_recording()

        print("Recording canceled.")

    def _handle_exit(self):
        """Handle EXIT command"""
        self.logger.info("Handling EXIT command")
        # Stop recording if active
        if self.recorder.is_active():
            self.logger.debug("Stopping active recording")
            self.recorder.stop_recording()
            self.recording_animator.stop_recording()

        print("Exiting...")
        self.exit_requested.set()

    def _type_text(self, text):
        """Simulate keystrokes to type the transcribed text"""
        if not self.args.simulate_typing or not self.keyboard_typer:
            return
        # self.logger.debug(f"Typing text: {text}")
        words = text.split()
        for i, word in enumerate(words):
            self.keyboard_typer.type(word)
            if i < len(words) - 1:  # Add space between words, but not after the last word
                self.keyboard_typer.type(' ')
            time.sleep(0.005)  # Small delay between words

    def _process_token(self, token):
        """Process a token from the transcription stream"""
        # Display token in console
        self.transcription_visualizer.process_token(token)

        # Type the token if typing simulation is enabled
        if self.args.simulate_typing:
            self._type_text(token)

    def _process_audio_data(self, audio_data):
        """Process recorded audio data"""
        # Save the audio file
        self.logger.debug(f"Saving audio data, format={self.args.save_format}")
        file_path = AudioProcessor.save_audio(
            audio_data, self.recorder.get_sample_rate(), self.args.save_format, output_dir=self.args.output_dir
        )
        self.logger.debug(f"Recording saved to: {file_path}")

        # Start the transcription visualization
        self.transcription_visualizer.start_transcribing()

        # Transcribe the audio using the unified visualizer
        self.logger.debug(f"Transcribing audio file with streaming:{self.args.streaming}: {file_path}")
        transcription = self.transcription_service.transcribe_and_print(
            file_path,
            stream=self.args.streaming,
            visualizer=self.transcription_visualizer,
            token_callback=self._process_token if self.args.simulate_typing else None,
        )

        # Finalize the transcription
        self.transcription_visualizer.finish_transcription()

        # Copy to clipboard if enabled
        if self.args.with_clipboard and transcription:
            try:
                pyperclip.copy(transcription)
                self.logger.debug("Transcription copied to clipboard! ✓")
            except Exception as e:
                self.logger.error(f"Failed to copy to clipboard: {e}")

        # Print a final newline for cleaner output
        print()

    def _process_existing_file(self, file_path):
        """Process an existing audio file"""
        if not os.path.exists(file_path):
            self.logger.error(f"File not found: {file_path}")
            print(f"Error: File not found at {file_path}")
            return

        self.logger.info(f"Processing existing file: {file_path}")

        # For existing files, mark recording end time as now
        self.transcription_visualizer.set_recording_end_time(time.time())

        # Start the transcription visualization
        self.transcription_visualizer.start_transcribing()

        # Transcribe the audio using the unified visualizer
        self.logger.debug(f"Transcribing audio file with streaming:{self.args.streaming}: {file_path}")
        transcription = self.transcription_service.transcribe_and_print(
            file_path,
            stream=self.args.streaming,
            visualizer=self.transcription_visualizer,
            token_callback=self._process_token if self.args.simulate_typing else None,
        )

        # Finalize the transcription
        self.transcription_visualizer.finish_transcription()

        # Copy to clipboard if enabled
        if self.args.with_clipboard and transcription:
            try:
                pyperclip.copy(transcription)
                self.logger.debug("Transcription copied to clipboard! ✓")
            except Exception as e:
                self.logger.error(f"Failed to copy to clipboard: {e}")

        # Print a final newline for cleaner output
        print()

        # Show a prompt to indicate the app is ready for next command
        print("Ready for next recording (use shortcut or press Ctrl+Shift+Q to exit)...")


def main():
    """Main entry point"""
    # Configure root logger once
    root_logger = logging.getLogger()

    # Remove any existing handlers to avoid duplicates
    if root_logger.handlers:
        for handler in root_logger.handlers:
            root_logger.removeHandler(handler)

    # Add a single handler to the root logger
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)

    # Disable propagation for third-party loggers that might be noisy
    for logger_name in ['pynput', 'openai', 'httpx']:
        logger = logging.getLogger(logger_name)
        logger.propagate = False
        logger.setLevel(logging.WARNING)

    app = VoiceTranscriptionApp()
    app.run()


if __name__ == "__main__":
    main()
