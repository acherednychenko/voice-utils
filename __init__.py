"""
Voice input and transcription module.

This module provides tools for voice recording, transcription, and keyboard control.
"""

from .audio_recorder import AudioRecorder
from .audio_processor import AudioProcessor
from .keyboard_controller import KeyboardController, KeyboardCommand, RecordingMode
from .transcription_service import TranscriptionService
from .utils import RecordingAnimator, TranscriptionVisualizer

# Import main applications
from .voice_app import VoiceTranscriptionApp
from .realtime_transcription import main as run_realtime_transcription

__all__ = [
    'AudioRecorder',
    'AudioProcessor',
    'KeyboardController',
    'KeyboardCommand',
    'RecordingMode',
    'TranscriptionService',
    'RecordingAnimator',
    'TranscriptionVisualizer',
    'VoiceTranscriptionApp',
    'run_realtime_transcription',
] 