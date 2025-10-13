#!/usr/bin/env python3
"""
Main entry point for Aachen Termin Bot using the refactored modular architecture.
"""

# Add the src directory to the Python path
import sys
from pathlib import Path

# Insert src/ into sys.path
src_path = Path(__file__).parent / 'src'
sys.path.insert(0, str(src_path))

# Import and run the main program
from src.main import main

if __name__ == "__main__":
    main()
