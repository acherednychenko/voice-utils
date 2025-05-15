#!/usr/bin/env python3
"""
Main entry point for voice module.
"""

import sys
import argparse

def main():
    """Main entry point when module is run directly."""
    parser = argparse.ArgumentParser(description="Voice transcription tools")
    parser.add_argument(
        "app", 
        choices=["realtime", "voice"], 
        default="voice",
        nargs="?",
        help="Which application to run: realtime=Realtime API transcription, voice=Full voice app"
    )
    
    # Parse just the first argument to determine which app to run
    args, remaining_args = parser.parse_known_args()
    
    # Set sys.argv to the remaining args for the target app to parse
    sys.argv = [sys.argv[0]] + remaining_args
    
    if args.app == "realtime":
        from .realtime_transcription import main
        main()
    else:
        from .voice_app import main
        main()

if __name__ == "__main__":
    main() 