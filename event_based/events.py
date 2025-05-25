"""Focused event classes for voice recording system."""

from dataclasses import dataclass
from enum import Enum
from typing import Optional
import uuid
from datetime import datetime


class InputSource(Enum):
    KEYBOARD = "keyboard"
    BLUETOOTH = "bluetooth"
    API = "api"
    
    def __str__(self):
        return self.value


# Recording Control Signals (to workflows)
@dataclass
class StartRecordingSignal:
    """Signal to start recording."""
    session_id: str
    source: InputSource
    timestamp: datetime = None

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now()


@dataclass
class StopRecordingSignal:
    """Signal to stop recording."""
    session_id: str
    source: InputSource
    timestamp: datetime = None

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now()


@dataclass
class CancelRecordingSignal:
    """Signal to cancel recording."""
    session_id: str
    source: InputSource
    reason: str = "user_cancelled"
    timestamp: datetime = None

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now()


@dataclass
class ExitSignal:
    """Signal to exit application."""
    source: InputSource
    timestamp: datetime = None

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now()


# Recording Events (published by workflows)
@dataclass
class RecordingStarted:
    """Published when recording actually starts."""
    session_id: str
    source: InputSource
    timestamp: datetime
    metadata: Optional[dict] = None


@dataclass
class RecordingStopped:
    """Published when recording stops."""
    session_id: str
    source: InputSource
    timestamp: datetime
    audio_file: str
    duration_seconds: float
    metadata: Optional[dict] = None


@dataclass
class FileSaved:
    """Published when audio file is saved."""
    session_id: str
    source: InputSource
    timestamp: datetime
    file_path: str
    file_size_bytes: int
    metadata: Optional[dict] = None


# Transcription Events (published by transcription workflows)
@dataclass
class TranscriptionStarted:
    """Published when transcription begins."""
    session_id: str
    source: InputSource
    timestamp: datetime
    file_path: str
    metadata: Optional[dict] = None


@dataclass
class TranscriptionDelta:
    """Published for each transcription delta/chunk."""
    session_id: str
    source: InputSource
    timestamp: datetime
    delta_text: str
    word_count: int
    confidence: float = 1.0
    metadata: Optional[dict] = None


@dataclass
class TranscriptionCompleted:
    """Published when transcription is complete."""
    session_id: str
    source: InputSource
    timestamp: datetime
    full_text: str
    word_count: int
    duration_seconds: float
    confidence: float = 1.0
    metadata: Optional[dict] = None


# Error Events
@dataclass
class RecordingFailed:
    """Published when recording fails."""
    session_id: str
    source: InputSource
    timestamp: datetime
    error_message: str
    error_code: str
    metadata: Optional[dict] = None


@dataclass
class TranscriptionFailed:
    """Published when transcription fails."""
    session_id: str
    source: InputSource
    timestamp: datetime
    error_message: str
    error_code: str
    file_path: str
    metadata: Optional[dict] = None 