"""Unit tests for text extraction and word parsing."""

import unittest
from core.text_extractor import extract_first_word

class TestTextExtractor(unittest.TestCase):
    def test_single_word(self):
        self.assertEqual(extract_first_word("ubiquitous"), "ubiquitous")
        self.assertEqual(extract_first_word("  Eloquent  "), "eloquent")

    def test_multiple_words_takes_first(self):
        self.assertEqual(extract_first_word("perseverance and determination"), "perseverance")
        self.assertEqual(extract_first_word("apple banana orange"), "apple")

    def test_punctuation_and_quotes(self):
        self.assertEqual(extract_first_word('"magnificent" results'), "magnificent")
        self.assertEqual(extract_first_word('(meticulous)'), "meticulous")
        self.assertEqual(extract_first_word('...fascinating story...'), "fascinating")

    def test_hyphenated_and_contractions(self):
        self.assertEqual(extract_first_word("well-known author"), "well-known")
        self.assertEqual(extract_first_word("don't worry"), "don't")

    def test_empty_or_invalid(self):
        self.assertIsNone(extract_first_word(""))
        self.assertIsNone(extract_first_word("   \n\t  "))
        self.assertIsNone(extract_first_word("12345 67890"))
        self.assertIsNone(extract_first_word("!@#$%^&*()"))

if __name__ == "__main__":
    unittest.main()
