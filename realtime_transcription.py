import os
import json
import websocket
import numpy as np
import sounddevice as sd
import dotenv
import threading
import queue
import logging
import base64
import argparse
import time
import datetime
from colorama import Fore, Style, init as colorama_init
from pathlib import Path
from pynput.keyboard import Controller as KeyboardTyper

# Import shared keyboard controller
from keyboard_controller import KeyboardController, KeyboardCommand, RecordingMode, parse_keyboard_args

# Setup logging
logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger("realtime_transcription")
logger.setLevel(logging.INFO)

# Initialize colorama for colored terminal output
colorama_init()

# Load environment variables
assert dotenv.load_dotenv(".env", override=True)

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY environment variable is not set")

# Audio settings
OPENAI_SAMPLE_RATE = 16000
CHANNELS = 1
DTYPE = "int16"

# Initialize keyboard controller for typing simulation
keyboard = KeyboardTyper()

# Path for statistics and logs
DATA_DIR = Path("data") / "transcription_logs"
STATS_FILE = DATA_DIR / "statistics.json"
LOG_FILE = DATA_DIR / "transcription_log.txt"

# Ensure directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Global statistics
stats = {"total_sessions": 0, "total_recording_time": 0, "total_characters_transcribed": 0, "sessions": []}

# Load existing statistics if available
if STATS_FILE.exists():
    try:
        with open(STATS_FILE, "r") as f:
            stats = json.load(f)
    except Exception as e:
        logger.error(f"Error loading statistics file: {e}")


class RealtimeAudioInput:
    def __init__(self, samplerate=OPENAI_SAMPLE_RATE, channels=CHANNELS, dtype=DTYPE, verbose=True):
        self.samplerate = samplerate
        self.channels = channels
        self.dtype = dtype
        self.is_recording = False
        self.audio_queue = queue.Queue()
        self.stream = None
        self.first_chunk_logged = False
        
        # Get device information
        device_info = self.get_device_info(verbose=verbose)
        self.selected_device = device_info["selected_device"]
        
        # Store device info for logging
        if verbose:
            logger.info(f"Selected recording device: [{self.selected_device['index']}] {self.selected_device['name']}")
            logger.info(f"Device sample rate: {self.selected_device['default_samplerate']} Hz")
            logger.info(f"Device channels: {self.selected_device['max_input_channels']}")
    
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
            logger.info("\nAvailable recording devices:")
            for device in recording_devices:
                logger.info(f"[{device['index']}] {device['name']} (Inputs: {device['max_input_channels']})")
            
            logger.info(f"\nSelected recording device: [{default_device['index']}] {default_device['name']}")
            logger.info(f"Default samplerate: {default_device['default_samplerate']} Hz\n")
        
        return {
            "available_devices": recording_devices,
            "selected_device": default_device
        }

    def start_recording(self):
        logger.info("Recording started")
        self.is_recording = True
        self.first_chunk_logged = False  # Reset for each new recording
        blocksize = int(0.02 * self.samplerate)
        logger.debug(f"Using blocksize: {blocksize} samples for InputStream")
        self.stream = sd.InputStream(
            device=self.selected_device["index"],
            samplerate=self.samplerate,
            channels=self.channels,
            dtype=self.dtype,
            callback=self._audio_callback,
            blocksize=blocksize,
        )
        self.stream.start()

    def stop_recording(self):
        logger.info("Recording stopped")
        self.is_recording = False
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None

    def _audio_callback(self, indata, frames, time_info, status):
        if self.is_recording:
            self.audio_queue.put(indata.copy())


class TranscriptionSession:
    def __init__(self):
        self.start_time = None
        self.end_time = None
        self.duration = 0
        self.characters_transcribed = 0
        self.transcribed_text = ""
        self.session_id = None

    def start(self):
        self.start_time = time.time()
        self.session_id = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        return self.session_id

    def stop(self):
        self.end_time = time.time()
        self.duration = self.end_time - self.start_time
        return self.duration

    def add_text(self, text):
        self.transcribed_text += text
        self.characters_transcribed += len(text)

    def get_stats(self):
        return {
            "session_id": self.session_id,
            "start_time": datetime.datetime.fromtimestamp(self.start_time).isoformat() if self.start_time else None,
            "end_time": datetime.datetime.fromtimestamp(self.end_time).isoformat() if self.end_time else None,
            "duration_seconds": self.duration,
            "characters_transcribed": self.characters_transcribed,
            "words_transcribed": len(self.transcribed_text.split()) if self.transcribed_text else 0,
        }

    def log_to_file(self):
        with open(LOG_FILE, "a") as f:
            f.write(f"\n{'=' * 80}\n")
            f.write(f"SESSION: {self.session_id}\n")
            f.write(f"Start time: {datetime.datetime.fromtimestamp(self.start_time).isoformat()}\n")
            f.write(f"Duration: {self.duration:.2f} seconds\n")
            f.write(f"Characters: {self.characters_transcribed}\n")
            f.write(f"Words: {len(self.transcribed_text.split()) if self.transcribed_text else 0}\n")
            f.write(f"{'=' * 80}\n\n")
            f.write(self.transcribed_text)
            f.write("\n\n")


def colorize(color, text):
    return color + text + Style.RESET_ALL


def type_text(text):
    """Simulate keystrokes to type text in the currently focused application"""
    for char in text:
        keyboard.type(char)
        time.sleep(0.01)  # Small delay between characters


# Global state for session
session_ready = threading.Event()
audio_input = RealtimeAudioInput()
ws_global = None
send_thread_global = None
current_session = None
enable_keystrokes = True


def on_message(ws, message):
    global current_session
    try:
        data = json.loads(message)
        if data.get("type") == "transcript.text.delta":
            # Handle legacy event format
            text = data["delta"]
            handle_transcription_text(text)
        elif data.get("type") == "conversation.item.input_audio_transcription.delta":
            # Handle newer event format
            text = data["delta"]
            # Add spaces after sentence endings
            for punct in [".", "?", "!", ",", ";", ":"]:
                text = text.replace(punct, f"{punct} ")
            handle_transcription_text(text)
        elif data.get("type") == "transcription_session.updated":
            logger.debug(f"Transcription session updated: {data}")
        elif data.get("type") == "transcription_session.created":
            logger.info("Session created. Configuring transcription...")
            # Configure transcription
            ws.send(
                json.dumps(
                    {
                        "type": "transcription_session.update",
                        "session": {
                            "input_audio_transcription": {
                                "model": "gpt-4o-mini-transcribe",
                                "language": "en",
                                "prompt": "Context, which you never need to mention in the output, but attend to it: Always transcribe in English. Context about speaker - technical person, software engineer, So I can use a lot of technical terms. ",
                            },
                            "input_audio_noise_reduction": {"type": "near_field"},
                            # "turn_detection": {
                            #     # "type": "server_vad",
                            #     # "threshold": 0.5,
                            #     # "prefix_padding_ms": 300,
                            #     # "silence_duration_ms": 500,
                            #     "type": "semantic_vad",
                            #     "eagerness": "high" #| "low" | "medium" | "high" | "auto", // optional
                            # }
                        },
                    }
                )
            )
            session_ready.set()
        else:
            # Log other events at DEBUG level
            logger.debug(f"Other event: {data}")
    except Exception as e:
        logger.error(f"Error parsing message: {e}")


def handle_transcription_text(text):
    global current_session

    # Print with yellow color
    print(colorize(Fore.YELLOW, text), end="", flush=True)

    # Type text if enabled
    if enable_keystrokes:
        type_text(text)

    # Update session statistics
    if current_session:
        current_session.add_text(text)


def on_error(ws, error):
    logger.error(f"WebSocket error: {error}")


def on_close(ws, close_status_code, close_msg):
    logger.warning(f"WebSocket closed (code={close_status_code}, msg={close_msg})")
    print("\nConnection closed")
    session_ready.clear()


def on_open(ws):
    logger.info("Connected to OpenAI Realtime API. Waiting for session creation...")
    # Do NOT send session.update for transcription sessions


def send_audio_loop(ws, current_audio_input):
    chunk_count = 0
    logger.info("Audio sending thread started.")
    while current_audio_input.is_recording:
        try:
            chunk = current_audio_input.audio_queue.get(timeout=0.1)
            if chunk is not None:
                if not current_audio_input.first_chunk_logged:
                    logger.debug(
                        f"First audio chunk: shape={chunk.shape}, sample_rate={current_audio_input.samplerate}"
                    )
                    current_audio_input.first_chunk_logged = True
                if ws.sock and ws.sock.connected:
                    # Encode audio as base64 and send as JSON message
                    audio_b64 = base64.b64encode(chunk.flatten()).decode("ascii")
                    msg = {"type": "input_audio_buffer.append", "audio": audio_b64}
                    ws.send(json.dumps(msg))
                    chunk_count += 1
                else:
                    logger.warning("WebSocket no longer connected, stopping audio send.")
                    break
        except queue.Empty:
            continue
        except websocket.WebSocketConnectionClosedException:
            logger.warning("WebSocket closed while trying to send audio.")
            break
        except Exception as e:
            logger.error(f"Error sending audio: {e}")
            break
    logger.info(f"Audio sending thread finished after {chunk_count} chunks.")


def update_statistics(session):
    global stats

    # Update global statistics
    stats["total_sessions"] += 1
    stats["total_recording_time"] += session.duration
    stats["total_characters_transcribed"] += session.characters_transcribed

    # Add session stats
    session_stats = session.get_stats()
    stats["sessions"].append(session_stats)

    # Save statistics to file
    try:
        with open(STATS_FILE, "w") as f:
            json.dump(stats, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving statistics: {e}")


def print_statistics():
    global stats

    print("\nTranscription Statistics:")
    print(f"Total sessions: {stats['total_sessions']}")
    print(f"Total recording time: {stats['total_recording_time']:.2f} seconds")
    print(f"Total characters transcribed: {stats['total_characters_transcribed']}")

    # Last session stats
    if stats["sessions"]:
        last_session = stats["sessions"][-1]
        print("\nLast session:")
        print(f"  Duration: {last_session['duration_seconds']:.2f} seconds")
        print(f"  Characters: {last_session['characters_transcribed']}")
        print(f"  Words: {last_session['words_transcribed']}")


def handle_start_recording():
    global ws_global, send_thread_global, audio_input, current_session

    if not ws_global or not ws_global.sock or not ws_global.sock.connected:
        logger.error("WebSocket not connected. Cannot start recording.")
        print(colorize(Fore.RED, "Error: Not connected to OpenAI API. Try restarting the app."))
        return

    # Create a new session
    current_session = TranscriptionSession()
    session_id = current_session.start()

    logger.info(f"Starting recording session: {session_id}")
    print(colorize(Fore.GREEN, "\n[Recording...] "))

    # Start recording
    audio_input.start_recording()
    send_thread_global = threading.Thread(target=send_audio_loop, args=(ws_global, audio_input))
    send_thread_global.daemon = True
    send_thread_global.start()


def handle_stop_recording():
    global ws_global, send_thread_global, audio_input, current_session

    if not audio_input.is_recording:
        return

    # Stop recording
    audio_input.stop_recording()
    print(colorize(Fore.GREEN, "[Stopped] "))

    # Finalize the session
    if current_session:
        duration = current_session.stop()
        logger.info(f"Recording session ended. Duration: {duration:.2f} seconds")

        # Wait for audio sending thread to complete
        if send_thread_global and send_thread_global.is_alive():
            logger.debug("Waiting for audio sending thread to complete...")
            send_thread_global.join(timeout=2.0)

        # Send commit marker
        if ws_global.sock and ws_global.sock.connected:
            try:
                logger.debug("Sending input_audio_buffer.commit marker")
                ws_global.send(json.dumps({"type": "input_audio_buffer.commit"}))
            except Exception as e:
                logger.error(f"Error sending input_audio_buffer.commit: {e}")

        # Log session to file
        current_session.log_to_file()

        # Update statistics
        update_statistics(current_session)

        # Print a newline for cleaner output
        print()


def handle_exit():
    global ws_global, audio_input

    logger.info("Exit requested")
    print(colorize(Fore.CYAN, "\nExiting application..."))

    # Stop recording if active
    if audio_input.is_recording:
        audio_input.stop_recording()

    # Close WebSocket
    if ws_global:
        ws_global.close()

    # Print final statistics
    print_statistics()

    # Exit the application
    os._exit(0)


def main():
    global ws_global, send_thread_global, audio_input, enable_keystrokes

    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Realtime audio transcription with OpenAI")
    parser.add_argument("--no-keystroke", action="store_true", help="Disable keystroke simulation")
    parser.add_argument("--debug", "-d", action="store_true", help="Enable debug logging")

    # Add keyboard controller arguments
    parser = parse_keyboard_args(parser)

    args = parser.parse_args()

    # Set logging level based on arguments
    if args.debug:
        logger.setLevel(logging.DEBUG)

    # Set keystroke simulation flag
    enable_keystrokes = not args.no_keystroke
    if enable_keystrokes:
        print(colorize(Fore.CYAN, "Keystroke simulation ENABLED - transcription will be typed in active window"))
    else:
        print(colorize(Fore.CYAN, "Keystroke simulation DISABLED"))

    # Connect to WebSocket
    ws = websocket.WebSocketApp(
        "wss://api.openai.com/v1/realtime?intent=transcription",
        header=[f"Authorization: Bearer {OPENAI_API_KEY}", "OpenAI-Beta: realtime=v1"],
        on_message=on_message,
        on_error=on_error,
        on_close=on_close,
        on_open=on_open,
    )
    ws_global = ws

    # Clear session ready flag
    session_ready.clear()

    # Start WebSocket connection
    ws_thread = threading.Thread(target=ws.run_forever)
    ws_thread.daemon = True
    ws_thread.start()

    # Wait for session to be established
    logger.info("Waiting for WebSocket connection and session to be established...")
    if not session_ready.wait(timeout=10):
        logger.error("Timeout waiting for session creation. Closing WebSocket.")
        if ws_global:
            ws_global.close()
        return

    logger.info("Session established. Ready for recording.")
    print(colorize(Fore.GREEN, "Connected to OpenAI API. Ready for recording!"))

    # Use TOGGLE mode by default for realtime transcription
    recording_mode = RecordingMode.TOGGLE
    if args.hold_mode:
        recording_mode = RecordingMode.HOLD

    # Set up keyboard controller with command handlers
    keyboard_controller = KeyboardController(
        start_stop_keys=args.start_stop_keys,
        exit_keys=args.exit_keys,
        recording_mode=recording_mode,
        log_level=logging.DEBUG if args.debug else logging.INFO,
    )

    # Register command handlers
    keyboard_controller.on_command(KeyboardCommand.START, handle_start_recording)
    keyboard_controller.on_command(KeyboardCommand.STOP, handle_stop_recording)
    keyboard_controller.on_command(KeyboardCommand.EXIT, handle_exit)

    try:
        # Start keyboard controller (this blocks until exit is requested)
        keyboard_controller.start()
    except KeyboardInterrupt:
        logger.info("Interrupted by user (KeyboardInterrupt)")
    finally:
        logger.info("Main loop finishing.")

        # Stop keyboard controller
        keyboard_controller.stop()

        # Stop recording if active
        if audio_input.is_recording:
            audio_input.stop_recording()

        # Close WebSocket
        if ws_global:
            ws_global.close()

        logger.info("Application exited.")


if __name__ == "__main__":
    main()
