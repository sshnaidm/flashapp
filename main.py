#!/usr/bin/env python3

"""
Main entry point for the Flashcard App.
This file is required by Buildozer for Android builds.
"""

if __name__ == "__main__":
    # Import and run the actual app
    from flashcard_app import FlashcardApp

    FlashcardApp().run()
