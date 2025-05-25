"""Publisher that sends signals to Temporal workflows."""

import asyncio
import logging
from typing import Dict, Optional
from temporalio.client import Client

from .events import (
    StartRecordingSignal, StopRecordingSignal, 
    CancelRecordingSignal, ExitSignal, InputSource
)
from .input_handler import StatefulKeyboardHandler


class RecordingSignalPublisher:
    """
    Publishes input signals to Temporal recording workflows.
    Manages the bridge between input handlers and workflows.
    """
    
    def __init__(self, temporal_client: Client, task_queue: str = "voice-recording"):
        self.client = temporal_client
        self.task_queue = task_queue
        self.input_handler: Optional[StatefulKeyboardHandler] = None
        self.active_workflows: Dict[str, str] = {}  # session_id -> workflow_id
        self.logger = logging.getLogger(self.__class__.__name__)
        
    def setup_keyboard_input(self, activation_shortcut="cmd+shift+.", exit_shortcut="ctrl+shift+q"):
        """Setup keyboard input handler."""
        self.input_handler = StatefulKeyboardHandler(activation_shortcut, exit_shortcut)
        self.input_handler.on_signal(self._handle_signal)
        self.logger.info(f"Keyboard input setup: {activation_shortcut}, {exit_shortcut}")
        
    def _handle_signal(self, signal):
        """Handle signals from input sources."""
        self.logger.info(f"Received signal: {type(signal).__name__}")
        
        if isinstance(signal, StartRecordingSignal):
            asyncio.create_task(self._handle_start_recording(signal))
        elif isinstance(signal, StopRecordingSignal):
            asyncio.create_task(self._handle_stop_recording(signal))
        elif isinstance(signal, CancelRecordingSignal):
            asyncio.create_task(self._handle_cancel_recording(signal))
        elif isinstance(signal, ExitSignal):
            asyncio.create_task(self._handle_exit(signal))
            
    async def _handle_start_recording(self, signal: StartRecordingSignal):
        """Start a new recording workflow."""
        try:
            from .recording_workflow import RecordingWorkflow
            
            workflow_id = f"recording-{signal.session_id}"
            
            # Start the recording workflow
            handle = await self.client.start_workflow(
                RecordingWorkflow.run,
                signal,
                id=workflow_id,
                task_queue=self.task_queue
            )
            
            self.active_workflows[signal.session_id] = workflow_id
            self.logger.info(f"Started workflow {workflow_id} for session {signal.session_id}")
            
        except Exception as e:
            self.logger.error(f"Failed to start recording workflow: {e}")

            
    async def _handle_stop_recording(self, signal: StopRecordingSignal):
        """Send stop signal to recording workflow."""
        try:
            workflow_id = self.active_workflows.get(signal.session_id)
            if not workflow_id:
                self.logger.warning(f"No active workflow for session: {signal.session_id}")
                return
                
            # Get workflow handle and send signal
            handle = self.client.get_workflow_handle(workflow_id)
            await handle.signal("stop_recording", signal)
            
            self.logger.info(f"Sent stop signal to workflow {workflow_id}")
            
        except Exception as e:
            self.logger.error(f"Failed to stop recording: {e}")

            
    async def _handle_cancel_recording(self, signal: CancelRecordingSignal):
        """Send cancel signal to recording workflow."""
        try:
            workflow_id = self.active_workflows.get(signal.session_id)
            if not workflow_id:
                self.logger.warning(f"No active workflow for session: {signal.session_id}")
                return
                
            # Get workflow handle and send signal
            handle = self.client.get_workflow_handle(workflow_id)
            await handle.signal("cancel_recording", signal)
            
            self.logger.info(f"Sent cancel signal to workflow {workflow_id}")
            
            # Remove from active workflows
            self.active_workflows.pop(signal.session_id, None)
            
        except Exception as e:
            self.logger.error(f"Failed to cancel recording: {e}")

            
    async def _handle_exit(self, signal: ExitSignal):
        """Handle exit signal - cancel all active recordings."""
        self.logger.info("Exit signal received, cancelling all recordings")

        
        # Cancel all active workflows
        for session_id, workflow_id in list(self.active_workflows.items()):
            try:
                handle = self.client.get_workflow_handle(workflow_id)
                cancel_signal = CancelRecordingSignal(session_id, signal.source, "exit_requested")
                await handle.signal("cancel_recording", cancel_signal)
            except Exception as e:
                self.logger.error(f"Failed to cancel workflow {workflow_id}: {e}")
                
        self.active_workflows.clear()
        
    def start(self):
        """Start input handlers."""
        if self.input_handler:
            self.input_handler.start()
        self.logger.info("RecordingSignalPublisher started")
        
    def stop(self):
        """Stop input handlers."""
        if self.input_handler:
            self.input_handler.stop()
        self.logger.info("RecordingSignalPublisher stopped") 