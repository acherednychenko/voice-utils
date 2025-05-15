# OpenAI Realtime Transcription

A tool for real-time audio transcription using OpenAI's Realtime API.

## Features

- **Real-time Transcription**: Stream audio directly from your microphone to OpenAI's API
- **Keyboard Shortcuts**: Control recording with customizable keyboard shortcuts
- **Keystroke Simulation**: Type transcribed text into any application
- **Statistics Tracking**: Track transcription stats and session history
- **Logging**: Logs transcriptions and session details to files

## Quick Start

1. **Copy the entire folder** to any computer with Python installed
2. **Install dependencies:**
   ```
   pip install -r requirements.txt
   ```
3. **Create a `.env` file** with your OpenAI API key:
   ```
   OPENAI_API_KEY=your_api_key_here
   ```
4. **Run the application:**
   ```
   python realtime_transcription.py
   ```

## Keyboard Controls

By default:
- **Command+Shift+.** (period): Start/stop recording
- **Control+Shift+Q**: Exit the application

## Command Line Options

```
python realtime_transcription.py [OPTIONS]
```

Options:
- `--no-keystroke`: Disable keystroke simulation (won't type text into applications)
- `--debug`: Enable debug logging
- `--start-stop-keys KEY1+KEY2+...`: Customize the recording shortcut
- `--exit-keys KEY1+KEY2+...`: Customize the exit shortcut

Example:
```
python realtime_transcription.py --start-stop-keys=ctrl+alt+r --exit-keys=ctrl+alt+q
```

## Mac Accessibility Permissions

For keystroke simulation to work on macOS, you need to:

1. Go to System Settings > Privacy & Security > Accessibility
2. Add your terminal application to the list
3. Enable the checkbox next to it

## Logs and Statistics

The application stores logs and statistics in:
- Transcription logs: `data/transcription_logs/transcription_log.txt`
- Statistics: `data/transcription_logs/statistics.json`

## Troubleshooting

- **Keystroke simulation doesn't work**: Check accessibility permissions on macOS
- **Audio recording fails**: Verify your microphone settings
- **Connection errors**: Check your API key and internet connection

## License

For demonstration purposes only. 