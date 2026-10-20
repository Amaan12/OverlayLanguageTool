"""SQLite database layer for caching dictionary responses and managing user vocabulary."""

import sqlite3
import json
import logging
from typing import Optional, Dict, Any, List
from config import DB_PATH

logger = logging.getLogger(__name__)

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initializes tables for dictionary cache and user saved vocabulary."""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Word Cache Table (for instant 0ms offline lookups)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS word_cache (
                word TEXT PRIMARY KEY,
                data_json TEXT NOT NULL,
                cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # User Saved Vocabulary Vault Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS vocab_vault (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                word TEXT NOT NULL,
                phonetic TEXT,
                part_of_speech TEXT,
                definition TEXT NOT NULL,
                example TEXT,
                synonyms TEXT,
                antonyms TEXT,
                notes TEXT,
                saved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(word)
            )
        """)
        conn.commit()

def get_cached_word(word: str) -> Optional[Dict[str, Any]]:
    """Retrieves cached word payload if it exists."""
    clean_word = word.strip().lower()
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT data_json FROM word_cache WHERE word = ?", (clean_word,))
            row = cursor.fetchone()
            if row:
                return json.loads(row["data_json"])
    except Exception as e:
        logger.error(f"Error reading cache for '{word}': {e}")
    return None

def set_cached_word(word: str, data: Dict[str, Any]):
    """Caches word data for offline and instant retrieval."""
    clean_word = word.strip().lower()
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO word_cache (word, data_json) VALUES (?, ?)",
                (clean_word, json.dumps(data))
            )
            conn.commit()
    except Exception as e:
        logger.error(f"Error caching word '{word}': {e}")

def save_to_vault(word: str, phonetic: str, part_of_speech: str, definition: str, 
                  example: str = "", synonyms: str = "", antonyms: str = "", notes: str = "") -> bool:
    """Saves a word to user's personal learning vault."""
    clean_word = word.strip().lower()
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO vocab_vault 
                (word, phonetic, part_of_speech, definition, example, synonyms, antonyms, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (clean_word, phonetic, part_of_speech, definition, example, synonyms, antonyms, notes))
            conn.commit()
            return True
    except Exception as e:
        logger.error(f"Error saving '{word}' to vault: {e}")
        return False

def remove_from_vault(word: str) -> bool:
    """Removes a word from the user's personal vault."""
    clean_word = word.strip().lower()
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM vocab_vault WHERE word = ?", (clean_word,))
            conn.commit()
            return True
    except Exception as e:
        logger.error(f"Error deleting '{word}' from vault: {e}")
        return False

def is_word_in_vault(word: str) -> bool:
    """Checks if a word is already starred in the vault."""
    clean_word = word.strip().lower()
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM vocab_vault WHERE word = ?", (clean_word,))
            return cursor.fetchone() is not None
    except Exception as e:
        logger.error(f"Error checking vault status for '{word}': {e}")
        return False

def get_all_vault_words() -> List[Dict[str, Any]]:
    """Retrieves all saved vocabulary words."""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM vocab_vault ORDER BY saved_at DESC")
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Error fetching vault words: {e}")
        return []
