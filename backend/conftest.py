# backend/conftest.py
"""Put the backend/ dir on sys.path so tests import the `app` package."""
import os
import sys

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)
