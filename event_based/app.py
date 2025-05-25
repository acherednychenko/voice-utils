"""Signal-based voice recording application."""

import asyncio
import logging
from temporalio.client import Client
from temporalio.worker import Worker

from .recording_signal_publisher import RecordingSignalPublisher
from .recording_workflow import (
    RecordingWorkflow, record_audio_activity, 
    stop_recording_activity, save_audio_file_activity
)


class VoiceRecordingApp:
    """
    Signal-based voice recording application.
    
    Flow:
    1. Keyboard → SignalPublisher → Temporal Workflows
    2. RecordingWorkflow reacts to signals 
    3. Activities do actual recording/saving
    4. Events published for external systems
    """
    
    def __init__(self):
        self.client = None
        self.worker = None
        self.publisher = None
        self.logger = logging.getLogger(self.__class__.__name__)
        
    async def setup(self):
        """Setup Temporal client, worker, and signal publisher."""
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # Connect to Temporal
        self.client = await Client.connect("localhost:7233")
        self.logger.info("Connected to Temporal")
        
        # Create worker
        self.worker = Worker(
            self.client,
            task_queue="voice-recording",
            workflows=[RecordingWorkflow],
            activities=[
                record_audio_activity,
                stop_recording_activity, 
                save_audio_file_activity
            ]
        )
        
        # Create signal publisher
        self.publisher = RecordingSignalPublisher(self.client, "voice-recording")
        self.publisher.setup_keyboard_input("cmd+shift+.", "ctrl+shift+q")
        
        self.logger.info("VoiceRecordingApp setup complete")
        
    async def run(self):
        """Run the application."""
        print("🎤 Signal-Based Voice Recording System")
        print("=" * 50)
        print("📋 Controls:")
        print("  Cmd+Shift+. : Start/Stop recording (stateful)")
        print("  Ctrl+Shift+Q : Exit")
        print("=" * 50)
        print("🔄 Signals → Workflows → Activities → Events")
        print("📊 Each recording session = separate workflow")
        print("🎯 Long-running recording controlled by signals")
        print("")
        
        try:
            # Start worker in background
            worker_task = asyncio.create_task(self.worker.run())
            self.logger.info("Worker started")
            
            # Start signal publisher (input handlers)
            self.publisher.start()
            
            # Keep running until interrupted
            await asyncio.sleep(float('inf'))
            
        except KeyboardInterrupt:
            print("\n🛑 Shutting down...")
        except Exception as e:
            self.logger.error(f"Application error: {e}")
        finally:
            await self.cleanup()
            
    async def cleanup(self):
        """Clean up resources."""
        if self.publisher:
            self.publisher.stop()
        if self.client:
            await self.client.close()
        self.logger.info("Cleanup complete")


async def main():
    """Main entry point."""
    app = VoiceRecordingApp()
    await app.setup()
    await app.run()


if __name__ == "__main__":
    asyncio.run(main()) 