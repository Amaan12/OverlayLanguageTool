"""Configuration settings for Overlay Language Tool."""

import os
from pathlib import Path

# Base Paths
BASE_DIR = Path(__file__).resolve().parent
STORAGE_DIR = BASE_DIR / "data"
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = STORAGE_DIR / "vocab_vault.db"

# Interaction Settings
# Snappy debounce times for near-instant responsiveness
MOUSE_DEBOUNCE_MS = 30
KEYBOARD_DEBOUNCE_MS = 90
SELECTION_DEBOUNCE_MS = 30

# Hotkey combination to toggle overlay monitoring globally
TOGGLE_HOTKEY = "<ctrl>+<alt>+l"

# UI Settings - Docked Top-Right Panel
OVERLAY_WIDTH = 420
OVERLAY_HEIGHT = 510


# Network Settings
API_TIMEOUT_SECONDS = 4.0
DICTIONARY_API_URL = "https://api.dictionaryapi.dev/api/v2/entries/en/{word}"
