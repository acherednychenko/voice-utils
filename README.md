# Voice Transcription Module

A Python module for real-time speech transcription and voice command handling using OpenAI's API.

## Features

- Real-time audio transcription using OpenAI's API
- Voice command recognition and processing
- Keyboard shortcut control for starting/stopping recording
- **Cancel shortcut** for canceling recordings without processing
- **Timing controls** - minimum recording duration and cooldown periods
- Support for both toggle mode and hold-to-record mode
- Automatic keystroke simulation (type transcribed text into active window)
- Audio recording and visualization

## Installation

### Prerequisites

- Python 3.12 or higher
- [uv](https://github.com/astral-sh/uv) package manager
- An OpenAI API key with access to the API

### Installation

```bash
# Clone the repository
git clone <repository-url>


# Install with all dependencies
uv pip install -e .
```

### Alternative: Direct installation

```bash
# Install directly with uv
uv pip install -e .
```

## Usage

### Environment Setup

Create a `.env` file in the project root with your OpenAI API key:

```bash
# .env
OPENAI_API_KEY=your_api_key_here
```

### Voice App (Main Application)

The main voice app with full keyboard shortcut support:

```bash
# Basic usage
python voice_app.py

# Show all options
python voice_app.py --help

# Custom shortcuts and timing
python voice_app.py \
  --shortcut "cmd+shift+." \
  --cancel-shortcut "ctrl+shift+w" \
  --exit-shortcut "ctrl+shift+q" \
  --min-recording-duration 1.5 \
  --cooldown-period 0.8
```

### Keyboard Shortcuts

- **Recording**: `cmd+shift+.` (default) - Start/stop recording
- **Cancel**: `ctrl+shift+w` (default) - Cancel current recording without processing
- **Exit**: `ctrl+shift+q` (default) - Exit the application

### Timing Controls

- **Minimum recording duration**: Prevents accidental quick recordings (default: 1.0s)
- **Cooldown period**: Prevents rapid toggling between recordings (default: 0.5s)

### Realtime Transcription

For real-time transcription using OpenAI's Realtime API:

```bash
# Basic realtime transcription
python realtime_transcription.py

# With keystroke simulation
python realtime_transcription.py --keystroke

# With debug logging
python realtime_transcription.py --debug
```

## Configuration Options

All configuration is handled through command-line arguments (no separate config files):

```bash
python voice_app.py \
  --model gpt-4o-mini-transcribe \
  --language en \
  --with-clipboard \
  --min-recording-duration 2.0 \
  --cooldown-period 1.0 \
  --hold-mode
```

## Dependencies

All dependencies are managed through `pyproject.toml`:
- Core: `openai`, `python-dotenv`, `sounddevice`, `numpy`
- Audio: `soundfile`, `pydub` 
- Interface: `pynput`, `pyperclip`, `colorama`
- Networking: `websocket-client`

No separate `requirements.txt` files are needed.

## Development

```bash
# Install with development dependencies
uv pip install -e '.[dev]'

# Run tests
pytest

# Run component test
python -c "from input_handler import KeyboardShortcutHandler; h = KeyboardShortcutHandler(); print('✅ All imports successful')"
```

## Project Structure

```
voice-transcription-module/
├── voice_app.py              # Main voice application
├── realtime_transcription.py # Realtime transcription app
├── input_handler.py          # Keyboard input handling
├── audio_recorder.py         # Audio recording functionality
├── audio_processor.py        # Audio processing utilities
├── transcription_service.py  # OpenAI transcription service
├── utils.py                  # Utility functions
├── keyboard_controller.py    # Keyboard controller
├── pyproject.toml           # Project configuration
├── README.md                # This file
└── .env                     # Environment variables (create this)
```

## License

[MIT License](LICENSE) 