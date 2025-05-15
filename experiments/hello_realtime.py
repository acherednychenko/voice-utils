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
from colorama import Fore, Style, init as colorama_init
from pynput.keyboard import Controller as KeyboardController

# Setup logging - Change default level to INFO but set logger to DEBUG
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s: %(message)s')
logger = logging.getLogger("hello_realtime")
logger.setLevel(logging.INFO)  # Main logger stays at INFO


assert dotenv.load_dotenv(".env", override=True)

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY environment variable is not set")

# Use 16kHz for maximum compatibility
OPENAI_SAMPLE_RATE = 16000
CHANNELS = 1
DTYPE = "int16"

colorama_init()

# Initialize keyboard controller for typing simulation
keyboard = KeyboardController()

# Global flag for keystroke simulation
enable_keystrokes = False

class RealtimeAudioInput:
    def __init__(self, samplerate=OPENAI_SAMPLE_RATE, channels=CHANNELS, dtype=DTYPE):
        self.samplerate = samplerate
        self.channels = channels
        self.dtype = dtype
        self.is_recording = False
        self.audio_queue = queue.Queue()
        self.stream = None
        self.first_chunk_logged = False

    def start_recording(self):
        logger.info("Recording started (will stop on user Enter)")
        self.is_recording = True
        self.first_chunk_logged = False # Reset for each new recording
        blocksize = int(0.02 * self.samplerate) 
        logger.info(f"Using blocksize: {blocksize} samples for InputStream")
        self.stream = sd.InputStream(
            samplerate=self.samplerate,
            channels=self.channels,
            dtype=self.dtype,
            callback=self._audio_callback,
            blocksize=blocksize
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

# Global state for session
session_ready = threading.Event()
audio_input = RealtimeAudioInput() # Instantiate here
ws_global = None
send_thread_global = None # Renamed to avoid conflict with local var in main

def colorize(color, text):
    return color + text + Style.RESET_ALL

def type_text(text):
    """Simulate keystrokes to type text in the currently focused application"""
    if enable_keystrokes:
        logger.info(colorize(Fore.CYAN, f"Typing: {text}"))
        # Type with small delay to prevent overwhelming the target application
        for char in text:
            keyboard.type(char)
            time.sleep(0.01)  # Small delay between characters

def on_message(ws, message):
    # Log raw messages at DEBUG level
    # logger.debug(f"WebSocket message received: {message}")
    try:
        data = json.loads(message)
        if data.get("type") == "transcript.text.delta":
            # Mustard/yellow for transcription
            assert False, "Not implemented"
            # print(colorize(Fore.RED, data["delta"]), end="", flush=True)
        elif data.get("type") == "conversation.item.input_audio_transcription.delta":
            # Also handle this newer event format
            text = data["delta"]
            # Add spaces after sentence endings
            for punct in [".", "?", "!", ",", ";", ":"]:
                text = text.replace(punct, f"{punct} ")
            print(colorize(Fore.YELLOW, text), end="", flush=True)
            logger.debug(f"Transcription: {text}")
            
            # Simulate keystrokes if enabled
            type_text(text)
            
        elif data.get("type") == "transcription_session.updated":
            logger.info(colorize(Fore.LIGHTBLACK_EX, f"Transcription session updated: {data}"))
        elif data.get("type") == "transcription_session.created":
            logger.info(colorize(Fore.LIGHTBLACK_EX, "Session created. Configuring transcription..."))
            # Configure transcription using correct format for transcription sessions
            ws.send(json.dumps({
                "type": "transcription_session.update",
                "session": {
                    "input_audio_transcription": {
                        "model": "gpt-4o-mini-transcribe",
                        # "model": "gpt-4o-transcribe",
                        # "model": "whisper-1",
                        # "language": ["en","pl"],
                        "language": "en",
                    },
                    "input_audio_noise_reduction": {
                        "type": "near_field"
                    },
                    # "turn_detection": {
                    #     "type": "server_vad",
                    #     "threshold": 0.5,
                    #     "prefix_padding_ms": 300,
                    #     "silence_duration_ms": 500,
                    #     # "create_response": True
                    # }
                }
            }))
            session_ready.set()
        else:
            # Log other events at DEBUG level
            logger.debug(colorize(Fore.LIGHTBLACK_EX, f"Other event: {data}"))
    except Exception as e:
        logger.error(colorize(Fore.RED, f"Error parsing message: {e}"))

def on_error(ws, error):
    logger.error(colorize(Fore.RED, f"WebSocket error: {error}"))

def on_close(ws, close_status_code, close_msg):
    logger.warning(f"WebSocket closed (code={close_status_code}, msg={close_msg})")
    print("\nConnection closed")
    session_ready.clear() # Clear event if connection closes

def on_open(ws):
    logger.info(colorize(Fore.LIGHTBLACK_EX, "Connected to OpenAI Realtime API. Waiting for session creation..."))
    # Do NOT send session.update for transcription sessions

def send_audio_loop(ws, current_audio_input):
    chunk_count = 0
    logger.info("Audio sending thread started.")
    while current_audio_input.is_recording:
        try:
            chunk = current_audio_input.audio_queue.get(timeout=0.1)
            if chunk is not None:
                if not current_audio_input.first_chunk_logged:
                    logger.info(f"First audio chunk: dtype={chunk.dtype}, shape={chunk.shape}, sample_rate={current_audio_input.samplerate}, first_samples={chunk.flatten()[:10]}")
                    current_audio_input.first_chunk_logged = True
                if ws.sock and ws.sock.connected:
                    # Encode audio as base64 and send as JSON message
                    audio_b64 = base64.b64encode(chunk.flatten()).decode("ascii")
                    msg = {
                        "type": "input_audio_buffer.append",
                        "audio": audio_b64
                    }
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

def main():
    global ws_global, send_thread_global, audio_input, enable_keystrokes

    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Realtime audio transcription with OpenAI")
    parser.add_argument("--keystroke", "-k", action="store_true", help="Enable keystroke simulation (types transcription into active window)")
    parser.add_argument("--debug", "-d", action="store_true", help="Enable debug logging")
    args = parser.parse_args()
    
    # Set logging level based on arguments
    if args.debug:
        logger.setLevel(logging.DEBUG)
        
    # Set keystroke simulation flag
    enable_keystrokes = args.keystroke
    if enable_keystrokes:
        logger.info(colorize(Fore.CYAN, "Keystroke simulation ENABLED - transcription will be typed in active window"))
        logger.info(colorize(Fore.CYAN, "Click in the target application window before speaking"))
        logger.info(colorize(Fore.CYAN, "Press Ctrl+C to exit at any time"))

    ws = websocket.WebSocketApp(
        "wss://api.openai.com/v1/realtime?intent=transcription",
        header=[
            f"Authorization: Bearer {OPENAI_API_KEY}",
            "OpenAI-Beta: realtime=v1"
        ],
        on_message=on_message,
        on_error=on_error,
        on_close=on_close,
        on_open=on_open
    )
    ws_global = ws

    session_ready.clear() # Clear at the start of main

    ws_thread = threading.Thread(target=ws.run_forever)
    ws_thread.daemon = True
    ws_thread.start()

    logger.info("Waiting for WebSocket connection and session to be established...")
    if not session_ready.wait(timeout=10): # Wait for on_message to set it
        logger.error("Timeout waiting for session creation. Closing WebSocket.")
        if ws_global:
            ws_global.close()
        return
    logger.info("Session established. Ready for user input.")

    try:
        while True:
            cmd = input("\nPress Enter to begin recording (or type 'q' to exit): ")
            if cmd.lower() == 'q':
                logger.info("Exiting on user request.")
                break

            # Session is already established, directly start recording
            audio_input.start_recording() # Uses the global audio_input
            send_thread_global = threading.Thread(target=send_audio_loop, args=(ws_global, audio_input))
            send_thread_global.daemon = True
            send_thread_global.start()

            input("Press Enter to stop recording: ") # Blocks until user presses Enter again
            audio_input.stop_recording()

            if send_thread_global and send_thread_global.is_alive():
                logger.info("Waiting for audio sending thread to complete...")
                send_thread_global.join(timeout=2.0) # Wait for send_audio_loop to finish

            if ws_global.sock and ws_global.sock.connected:
                try:
                    logger.info("Sending input_audio_buffer.commit marker")
                    ws_global.send(json.dumps({"type": "input_audio_buffer.commit"}))
                except Exception as e:
                    logger.error(f"Error sending input_audio_buffer.commit: {e}")
            else:
                logger.warning("WebSocket not connected, cannot send input_audio_buffer.commit.")

    except KeyboardInterrupt:
        logger.info("Interrupted by user (KeyboardInterrupt)")
    finally:
        logger.info("Main loop finishing. Closing WebSocket.")
        if audio_input.is_recording: # Ensure recording is stopped
            audio_input.stop_recording()
        if send_thread_global and send_thread_global.is_alive():
            send_thread_global.join(timeout=1.0)
        if ws_global:
            ws_global.close()
        logger.info("Application exited.")

if __name__ == "__main__":
    main()

