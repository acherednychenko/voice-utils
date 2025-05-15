# Voice Module

A Python module for real-time speech transcription and voice command handling using OpenAI's API.

## Features

- Real-time audio transcription using OpenAI's API
- Voice command recognition and processing
- Keyboard shortcut control for starting/stopping recording
- Support for both toggle mode and hold-to-record mode
- Automatic keystroke simulation (type transcribed text into active window)
- Audio recording and visualization

## Installation

### Prerequisites

- Python 3.12 or higher
- An OpenAI API key with access to the Realtime API

### From GitHub

```bash
# Clone the repository
git clone https://github.com/yourusername/voice-module.git

# Navigate to the directory
cd voice-module

# Install with uv
uv pip install -e .
```

### As a Dependency

Add to your project's requirements:

```
git+https://github.com/yourusername/voice-module.git
```

Or in pyproject.toml:

```toml
dependencies = [
    "voice-module @ git+https://github.com/yourusername/voice-module.git"
]
```

## Usage

### Environment Setup

Create a `.env` file with your OpenAI API key:

```
OPENAI_API_KEY=your_api_key_here
```

### Voice App (Hold-to-Record)

The voice app allows you to record audio by holding down a keyboard shortcut:

```bash
# Run the voice app
python -m voice
```

### Realtime Transcription (Toggle Mode)

The realtime transcription app uses toggle mode (press once to start, press again to stop):

```bash
# Run the realtime transcription app
python -m realtime
```

### Command Line Options

Both apps support various command line options:

```bash
# Voice App with custom shortcut
python -m voice --shortcut="alt+shift+v"

# Realtime Transcription with debug logging
python -m realtime --debug

# Disable keystroke simulation
python -m realtime --no-keystroke

# Use hold mode instead of toggle
python -m realtime --hold-mode
```

## Development

### Testing

Run tests using pytest:

```bash
pytest
```

### Building

Build the package using hatch:

```bash
hatch build
```

## License

[MIT License](LICENSE) 