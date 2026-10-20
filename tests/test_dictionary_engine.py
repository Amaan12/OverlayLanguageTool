"""Unit tests for dictionary engine response parsing and retrieval."""

import unittest
from core.dictionary_engine import parse_dictionary_response, lookup_word

class TestDictionaryEngine(unittest.TestCase):
    def test_parse_response_structure(self):
        sample_raw = [{
            "word": "tenacious",
            "phonetic": "/təˈneɪ.ʃəs/",
            "phonetics": [
                {"text": "/təˈneɪ.ʃəs/", "audio": "https://api.dictionaryapi.dev/media/pronunciations/en/tenacious-us.mp3"}
            ],
            "meanings": [
                {
                    "partOfSpeech": "adjective",
                    "definitions": [
                        {
                            "definition": "Tending to keep a firm hold of something; clinging or adhering closely.",
                            "example": "A tenacious grip.",
                            "synonyms": ["persistent", "stubborn"],
                            "antonyms": ["yielding", "weak"]
                        }
                    ]
                }
            ]
        }]
        
        parsed = parse_dictionary_response("tenacious", sample_raw)
        self.assertIsNotNone(parsed)
        self.assertTrue(parsed["found"])
        self.assertEqual(parsed["word"], "tenacious")
        self.assertEqual(parsed["phonetic"], "/təˈneɪ.ʃəs/")
        self.assertEqual(parsed["audio_url"], "https://api.dictionaryapi.dev/media/pronunciations/en/tenacious-us.mp3")
        self.assertIn("persistent", parsed["all_synonyms"])
        self.assertIn("yielding", parsed["all_antonyms"])

    def test_lookup_word_live_and_cached(self):
        res = lookup_word("eloquent")
        self.assertIsNotNone(res)
        self.assertTrue(res.get("found", False))
        self.assertEqual(res.get("word"), "eloquent")
        self.assertTrue(len(res.get("meanings", [])) > 0)

if __name__ == "__main__":
    unittest.main()
