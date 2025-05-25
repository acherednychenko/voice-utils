"""Signal-based recording workflow."""

import asyncio
import logging
from datetime import datetime, timedelta
from temporalio import workflow, activity

from .events import (
    StartRecordingSignal, StopRecordingSignal, CancelRecordingSignal,
    RecordingStarted, RecordingStopped, FileSaved, RecordingFailed
)


@workflow.defn
class RecordingWorkflow:
    """
    Signal-based recording workflow.
    
    Starts when receiving StartRecordingSignal, then reacts to:
    - stop_recording signal
    - cancel_recording signal
    
    Controls a long-running recording activity that runs in background.
    """
    
    def __init__(self):
        self.recording_task = None
        self.session_id = None
        self.source = None
        self.is_recording = False
        
        # Signal handlers
        self.stop_signal_received = False
        self.cancel_signal_received = False
        self.cancel_reason = None
        
    @workflow.run
    async def run(self, start_signal: StartRecordingSignal) -> FileSaved:
        """
        Main workflow - starts recording and waits for stop/cancel signals.
        """
        self.session_id = start_signal.session_id
        self.source = start_signal.source
        
        workflow.logger.info(f"🎤 Recording workflow started: {self.session_id}")
        
        try:
            # Start the recording activity (long-running in background)
            self.recording_task = asyncio.create_task(
                workflow.execute_activity(
                    record_audio_activity,
                    self.session_id,
                    start_to_close_timeout=timedelta(minutes=30),  # Max recording time
                    heartbeat_timeout=timedelta(seconds=5)  # For cancellation
                )
            )
            
            # Publish recording started event
            await self._publish_event(
                RecordingStarted(self.session_id, self.source, workflow.now())
            )
            
            self.is_recording = True
            
            # Wait for signals or recording completion
            while self.is_recording:
                # Check if recording completed naturally
                if self.recording_task.done():
                    break
                    
                # Check for stop signal
                if self.stop_signal_received:
                    workflow.logger.info("Stop signal received, stopping recording")
                    await self._stop_recording()
                    break
                    
                # Check for cancel signal  
                if self.cancel_signal_received:
                    workflow.logger.info(f"Cancel signal received: {self.cancel_reason}")
                    await self._cancel_recording()
                    break
                    
                # Wait a bit before checking again
                await asyncio.sleep(0.1)
            
            # Get recording result
            if not self.recording_task.cancelled():
                audio_file_path = await self.recording_task
                
                # Save the file
                saved_file = await workflow.execute_activity(
                    save_audio_file_activity,
                    audio_file_path,
                    start_to_close_timeout=timedelta(seconds=30)
                )
                
                # Publish file saved event
                file_saved_event = FileSaved(
                    session_id=self.session_id,
                    source=self.source, 
                    timestamp=workflow.now(),
                    file_path=saved_file["file_path"],
                    file_size_bytes=saved_file["file_size_bytes"]
                )
                
                await self._publish_event(file_saved_event)
                
                workflow.logger.info(f"✅ Recording completed: {self.session_id}")
                return file_saved_event
            else:
                workflow.logger.info(f"🛑 Recording cancelled: {self.session_id}")
                return None
                
        except Exception as e:
            workflow.logger.error(f"❌ Recording failed: {e}")
            
            # Publish failure event
            await self._publish_event(
                RecordingFailed(
                    session_id=self.session_id,
                    source=self.source,
                    timestamp=workflow.now(),
                    error_message=str(e),
                    error_code="recording_error"
                )
            )
            raise
    
    @workflow.signal
    async def stop_recording(self, signal: StopRecordingSignal):
        """Signal handler for stop recording."""
        workflow.logger.info(f"Received stop signal for: {signal.session_id}")
        self.stop_signal_received = True
        
    @workflow.signal  
    async def cancel_recording(self, signal: CancelRecordingSignal):
        """Signal handler for cancel recording."""
        workflow.logger.info(f"Received cancel signal for: {signal.session_id}, reason: {signal.reason}")
        self.cancel_signal_received = True
        self.cancel_reason = signal.reason
        
    async def _stop_recording(self):
        """Stop the recording gracefully."""
        if self.recording_task and not self.recording_task.done():
            # Send heartbeat signal to activity to stop gracefully
            await workflow.execute_activity(
                stop_recording_activity,
                self.session_id,
                start_to_close_timeout=timedelta(seconds=10)
            )
            
        self.is_recording = False
        
        # Publish recording stopped event
        await self._publish_event(
            RecordingStopped(
                session_id=self.session_id,
                source=self.source,
                timestamp=workflow.now(),
                audio_file="temp_file",  # Will be updated with actual file
                duration_seconds=0.0  # Will be calculated
            )
        )
        
    async def _cancel_recording(self):
        """Cancel the recording."""
        if self.recording_task and not self.recording_task.done():
            self.recording_task.cancel()
            
        self.is_recording = False
        
    async def _publish_event(self, event):
        """Publish event to external systems."""
        workflow.logger.info(f"📡 Publishing: {type(event).__name__}")

        # TODO: Integrate with external event bus, webhook, etc.


# Activity definitions for actual audio recording

@activity.defn
async def record_audio_activity(session_id: str) -> str:
    """
    Long-running activity that records audio using AudioRecorder.
    
    Uses heartbeats to check for cancellation signals from workflow.
    """
    import asyncio
    import time
    import os
    import wave
    import numpy as np
    from temporalio import activity
    
    # Import the existing AudioRecorder
    import sys
    sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
    from audio_recorder import AudioRecorder
    
    activity.logger.info(f"🎙️ Starting audio recording for: {session_id}")
    
    # Create recorder and start recording
    recorder = AudioRecorder(samplerate=44100, channels=1, dtype="int16", verbose=False)
    temp_file = f"/tmp/{session_id}.wav"
    
    try:
        # Start recording
        recorder.start_recording()
        activity.logger.info(f"Recording started for: {session_id}")
        
        # Keep recording until cancelled or max time reached
        start_time = time.time()
        while recorder.is_active():
            # Send heartbeat to check for cancellation from workflow
            activity.heartbeat()
            
            # Check for max recording time (5 minutes)
            elapsed = time.time() - start_time
            if elapsed > 300:
                activity.logger.info(f"Max recording time reached for: {session_id}")
                break
                
            # Wait between heartbeat checks
            await asyncio.sleep(0.5)
            
    except asyncio.CancelledError:
        activity.logger.info(f"Recording cancelled for: {session_id}")
        raise
    except Exception as e:
        activity.logger.error(f"Recording failed for {session_id}: {e}")
        raise
    finally:
        # Always stop recording and save what we have
        if recorder.is_active():
            recorder.stop_recording()
        
        # Save recorded data to file
        audio_data = recorder.get_recording()
        if len(audio_data) > 0:
            # Save as WAV file
            with wave.open(temp_file, 'wb') as wav_file:
                wav_file.setnchannels(recorder.channels)
                wav_file.setsampwidth(2)  # 16-bit = 2 bytes
                wav_file.setframerate(recorder.samplerate)
                wav_file.writeframes(audio_data.tobytes())
            
            activity.logger.info(f"Recording saved to: {temp_file}")
        else:
            activity.logger.warning(f"No audio data recorded for: {session_id}")
        
    return temp_file


@activity.defn
async def stop_recording_activity(session_id: str):
    """Activity to gracefully stop recording."""
    from temporalio import activity
    activity.logger.info(f"⏹️ Gracefully stopping recording: {session_id}")
    # The actual stopping is handled by heartbeat cancellation in record_audio_activity


@activity.defn  
async def save_audio_file_activity(temp_file_path: str) -> dict:
    """Save temporary audio file to permanent location."""
    import os
    import shutil
    from temporalio import activity
    
    # Generate permanent file path
    session_id = os.path.basename(temp_file_path).replace(".wav", "")
    permanent_path = f"/saved/recordings/{session_id}.wav"
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(permanent_path), exist_ok=True)
    
    # Move file
    shutil.move(temp_file_path, permanent_path)
    
    # Get file size
    file_size = os.path.getsize(permanent_path)
    
    activity.logger.info(f"💾 Saved recording: {permanent_path} ({file_size} bytes)")
    
    return {
        "file_path": permanent_path,
        "file_size_bytes": file_size
    } 