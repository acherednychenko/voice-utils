import os
import logging
from openai import OpenAI


class TranscriptionService:
    """
    Handles transcription of audio data using various services.
    Currently supports OpenAI's transcription API.
    """
    
    def __init__(self, client=None, model="gpt-4o-mini-transcribe", language="en", log_level=logging.INFO):
        """
        Initialize the transcription service.
        
        Args:
            client: OpenAI client (created if None)
            model: The model to use for transcription
            language: Language code for transcription hints
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        """
        self.client = client or OpenAI()
        self.model = model
        self.language = language
        
        # Set up logging
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(log_level)
        
        # Remove any existing handlers to prevent duplicates
        if self.logger.handlers:
            for handler in self.logger.handlers:
                self.logger.removeHandler(handler)
                
        # Add a single handler and prevent propagation to root logger
        self.logger.propagate = False
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        
        self.logger.debug(f"Initialized TranscriptionService with model={model}, language={language}")
    
    def transcribe_file(self, file_path, stream=True):
        """
        Transcribe audio from a file path.
        
        Args:
            file_path: Path to the audio file
            stream: Whether to stream results or wait for full transcription
            
        Returns:
            If stream=True: Generator yielding transcript chunks
            If stream=False: Full transcript text
        """
        # Check if file exists
        if not os.path.exists(file_path):
            self.logger.error(f"Audio file not found: {file_path}")
            raise FileNotFoundError(f"Audio file not found: {file_path}")
        
        self.logger.debug(f"Transcribing file: {file_path} (stream={stream})")
        prompt_formatted = f"Context, which you don't need to mention in the output, but attend to it: Text is in {self.language}, use only this (these) language (s). Context about speaker - technical person, software engineer, So I can use a lot of technical terms."
        
        # Open the file for transcription
        with open(file_path, "rb") as audio_file:
            if stream:
                # Stream the transcription results
                self.logger.debug(f"Starting streaming transcription with model {self.model}")
                transcription = self.client.audio.transcriptions.create(
                    model=self.model,
                    file=audio_file,
                    response_format="text",
                    prompt=prompt_formatted,
                    stream=True,
                )
                
                # Return the generator directly
                return transcription
            else:
                # Get the full transcription at once
                self.logger.debug(f"Starting non-streaming transcription with model {self.model}")
                transcription = self.client.audio.transcriptions.create(
                    model=self.model,
                    file=audio_file,
                    response_format="text",
                    prompt=prompt_formatted,
                )
                
                self.logger.debug(f"Transcription complete: {len(transcription.text)} characters")
                return transcription.text
    
    def collect_stream_to_text(self, transcription_stream):
        """
        Collect a streaming transcription into a single text string.
        
        Args:
            transcription_stream: Stream from transcribe_file(stream=True)
            
        Returns:
            Complete transcription text
        """
        self.logger.debug("Collecting streaming transcription to text")
        full_text = ""
        chunks_count = 0
        
        for event in transcription_stream:
            if event.type == "transcript.text.delta":
                full_text += event.delta
                chunks_count += 1
        
        self.logger.debug(f"Collected {chunks_count} chunks, total length: {len(full_text)} characters")
        return full_text
    
    def transcribe_and_print(self, file_path, stream=True, visualizer=None):
        """
        Transcribe audio and print results in real-time if streaming
        
        Args:
            file_path: Path to the audio file
            stream: Whether to stream results
            visualizer: Optional TranscriptionVisualizer to handle token presentation
            
        Returns:
            Transcription text
        """
        self.logger.debug(f"Transcribing and printing: {file_path}")
        
        if stream:
            full_text = ""
            
            transcription = self.transcribe_file(file_path, stream=True)
            chunks_count = 0
            
            # If we have a visualizer, use that, otherwise print directly
            if visualizer:
                for event in transcription:
                    if event.type == "transcript.text.delta":
                        visualizer.process_token(event.delta)
                        full_text += event.delta
                        chunks_count += 1
                
                self.logger.debug(f"Processed {chunks_count} streaming chunks through visualizer")
            else:
                # Start with a fresh line to avoid conflicts with animation
                print()
                
                for event in transcription:
                    if event.type == "transcript.text.delta":
                        print(event.delta, end="", flush=True)
                        full_text += event.delta
                        chunks_count += 1
                
                self.logger.debug(f"Printed {chunks_count} streaming chunks directly")
            
            return full_text
        else:
            text = self.transcribe_file(file_path, stream=False)
            # Don't print here - let the caller handle it
            return text 