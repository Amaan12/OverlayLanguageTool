"""Unit tests for SQLite database operations and vocabulary storage."""

import unittest
import os
from storage.db import (
    init_db, set_cached_word, get_cached_word, 
    save_to_vault, is_word_in_vault, remove_from_vault, get_all_vault_words
)

class TestDatabase(unittest.TestCase):
    def setUp(self):
        init_db()

    def test_cache_roundtrip(self):
        sample_data = {
            "word": "serendipity",
            "phonetic": "/ˌsɛr.ənˈdɪp.ɪ.ti/",
            "meanings": [{"part_of_speech": "noun", "definitions": ["A fortunate discovery."]}]
        }
        set_cached_word("serendipity", sample_data)
        cached = get_cached_word("serendipity")
        self.assertIsNotNone(cached)
        self.assertEqual(cached["word"], "serendipity")
        self.assertEqual(cached["phonetic"], "/ˌsɛr.ənˈdɪp.ɪ.ti/")

    def test_vault_operations(self):
        # Save to vault
        saved = save_to_vault(
            word="lucid",
            phonetic="/ˈluː.sɪd/",
            part_of_speech="adjective",
            definition="Expressed clearly; easy to understand.",
            example="A lucid explanation.",
            synonyms="clear, coherent",
            antonyms="confusing, ambiguous"
        )
        self.assertTrue(saved)
        self.assertTrue(is_word_in_vault("lucid"))

        # Verify in all words list
        all_words = get_all_vault_words()
        words_list = [w["word"] for w in all_words]
        self.assertIn("lucid", words_list)

        # Remove from vault
        removed = remove_from_vault("lucid")
        self.assertTrue(removed)
        self.assertFalse(is_word_in_vault("lucid"))

if __name__ == "__main__":
    unittest.main()
