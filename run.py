#!/usr/bin/env python3
"""Start Retro Companion:  python run.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from companion.dashboard import main

if __name__ == "__main__":
    main()
