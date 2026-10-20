"""Dictionary Engine: Multi-provider system with Free Dictionary API, Datamuse fallback,
and offline SQLite caching.
"""

import logging
import requests
from typing import Dict, Any, Optional, List
from config import DICTIONARY_API_URL, API_TIMEOUT_SECONDS
from storage.db import get_cached_word, set_cached_word

logger = logging.getLogger(__name__)

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

def lookup_word(word: str) -> Optional[Dict[str, Any]]:
    """Looks up a word from local SQLite cache, Free Dictionary API, or Datamuse fallback."""
    clean_word = word.strip().lower()
    if not clean_word:
        return None
        
    # 1. Check local SQLite cache first (0ms latency, offline)
    cached = get_cached_word(clean_word)
    if cached:
        return cached

    # 2. Try Primary: Free Dictionary API
    url = DICTIONARY_API_URL.format(word=clean_word)
    headers = {"User-Agent": USER_AGENT}
    try:
        response = requests.get(url, headers=headers, timeout=API_TIMEOUT_SECONDS)
        if response.status_code == 200:
            raw_data = response.json()
            parsed = parse_dictionary_response(clean_word, raw_data)
            if parsed:
                set_cached_word(clean_word, parsed)
                return parsed
        else:
            logger.info(f"Primary Dictionary API returned {response.status_code} for '{clean_word}'. Trying Datamuse fallback...")
    except requests.exceptions.RequestException as e:
        logger.info(f"Primary API connection failed for '{clean_word}': {e}. Trying Datamuse fallback...")

    # 3. Try Secondary Fallback: Datamuse API (high-availability, no Cloudflare blocks)
    fallback_data = fallback_lookup_datamuse(clean_word)
    if fallback_data:
        set_cached_word(clean_word, fallback_data)
        return fallback_data

    # 4. If neither service has the word
    return {
        "word": clean_word,
        "found": False,
        "message": f"No definition found for '{clean_word}'."
    }

def fallback_lookup_datamuse(word: str) -> Optional[Dict[str, Any]]:
    """Secondary dictionary provider via Datamuse API (fast, high-availability)."""
    try:
        def_url = f"https://api.datamuse.com/words?sp={word}&md=dp&max=1"
        r = requests.get(def_url, headers={"User-Agent": USER_AGENT}, timeout=API_TIMEOUT_SECONDS)
        if r.status_code != 200 or not r.json():
            return None
            
        data_list = r.json()
        item = data_list[0]
        raw_defs = item.get("defs", [])
        if not raw_defs:
            return None
            
        # Parse defs into meanings
        meanings_dict: Dict[str, List[str]] = {}
        pos_map = {
            "n": "noun", "v": "verb", "adj": "adjective", 
            "adv": "adverb", "u": "general"
        }
        for d in raw_defs:
            parts = d.split("\t", 1)
            if len(parts) == 2:
                pos_abbrev, text = parts
                pos = pos_map.get(pos_abbrev.strip(), pos_abbrev.strip())
            else:
                pos = "general"
                text = d
            meanings_dict.setdefault(pos, []).append(text.strip())
            
        meanings = []
        for pos, d_list in meanings_dict.items():
            meanings.append({
                "part_of_speech": pos,
                "definitions": d_list[:3],
                "examples": []
            })
            
        # Fetch synonyms & antonyms from Datamuse
        syn_r = requests.get(f"https://api.datamuse.com/words?rel_syn={word}&max=8", timeout=2.0)
        synonyms = [w["word"] for w in syn_r.json()] if syn_r.status_code == 200 else []
        
        ant_r = requests.get(f"https://api.datamuse.com/words?rel_ant={word}&max=8", timeout=2.0)
        antonyms = [w["word"] for w in ant_r.json()] if ant_r.status_code == 200 else []
        
        # Fetch related words (topic associations) from Datamuse
        rel_words = []
        try:
            rel_r = requests.get(f"https://api.datamuse.com/words?rel_trg={word}&max=8", timeout=1.5)
            if rel_r.status_code == 200:
                raw_rel = [w["word"].lower() for w in rel_r.json()]
                rel_words = [r for r in raw_rel if r != word and r not in synonyms and r not in antonyms]
            if not rel_words:
                ml_r = requests.get(f"https://api.datamuse.com/words?ml={word}&max=8", timeout=1.5)
                if ml_r.status_code == 200:
                    raw_ml = [w["word"].lower() for w in ml_r.json()]
                    rel_words = [r for r in raw_ml if r != word and r not in synonyms and r not in antonyms]
        except Exception:
            pass

        return {
            "word": word,
            "found": True,
            "phonetic": "",
            "audio_url": "",
            "meanings": meanings,
            "all_synonyms": synonyms,
            "all_antonyms": antonyms,
            "all_related": rel_words[:6]
        }
    except Exception as e:
        logger.error(f"Datamuse fallback error for '{word}': {e}")
        return None

def parse_dictionary_response(word: str, raw_entries: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Parses Free Dictionary API raw payload into a clean, compact schema."""
    if not raw_entries or not isinstance(raw_entries, list):
        return None
        
    first_entry = raw_entries[0]
    phonetic_text = first_entry.get("phonetic", "")
    audio_url = ""
    
    # Extract audio URL and fallback phonetic text
    for p in first_entry.get("phonetics", []):
        if not phonetic_text and p.get("text"):
            phonetic_text = p.get("text")
        if p.get("audio") and not audio_url:
            audio_url = p.get("audio")
            
    parsed_meanings = []
    all_synonyms: List[str] = []
    all_antonyms: List[str] = []
    
    for entry in raw_entries:
        for meaning in entry.get("meanings", []):
            pos = meaning.get("partOfSpeech", "general")
            defs: List[str] = []
            examples: List[str] = []
            
            meaning_syns = meaning.get("synonyms", [])
            meaning_ants = meaning.get("antonyms", [])
            all_synonyms.extend(meaning_syns)
            all_antonyms.extend(meaning_ants)
            
            for d in meaning.get("definitions", []):
                if d.get("definition"):
                    defs.append(d["definition"])
                if d.get("example"):
                    examples.append(d["example"])
                if d.get("synonyms"):
                    all_synonyms.extend(d["synonyms"])
                if d.get("antonyms"):
                    all_antonyms.extend(d["antonyms"])
            
            if defs:
                parsed_meanings.append({
                    "part_of_speech": pos,
                    "definitions": defs[:3],
                    "examples": examples[:2]
                })
                
    unique_synonyms = list(dict.fromkeys([s.lower() for s in all_synonyms if s.lower() != word]))
    unique_antonyms = list(dict.fromkeys([a.lower() for a in all_antonyms if a.lower() != word]))
    
    # If primary API didn't return synonyms or antonyms, enrich with Datamuse
    if not unique_synonyms or not unique_antonyms:
        try:
            if not unique_synonyms:
                syn_r = requests.get(f"https://api.datamuse.com/words?rel_syn={word}&max=8", timeout=1.5)
                if syn_r.status_code == 200:
                    unique_synonyms = [w["word"] for w in syn_r.json()]
            if not unique_antonyms:
                ant_r = requests.get(f"https://api.datamuse.com/words?rel_ant={word}&max=8", timeout=1.5)
                if ant_r.status_code == 200:
                    unique_antonyms = [w["word"] for w in ant_r.json()]
        except Exception:
            pass

    # Fetch related context/topic words
    related_words = []
    try:
        rel_r = requests.get(f"https://api.datamuse.com/words?rel_trg={word}&max=8", timeout=1.5)
        if rel_r.status_code == 200:
            raw_rel = [w["word"].lower() for w in rel_r.json()]
            related_words = [r for r in raw_rel if r != word and r not in unique_synonyms and r not in unique_antonyms]
        if not related_words:
            ml_r = requests.get(f"https://api.datamuse.com/words?ml={word}&max=8", timeout=1.5)
            if ml_r.status_code == 200:
                raw_ml = [w["word"].lower() for w in ml_r.json()]
                related_words = [r for r in raw_ml if r != word and r not in unique_synonyms and r not in unique_antonyms]
    except Exception:
        pass

    return {
        "word": word,
        "found": True,
        "phonetic": phonetic_text,
        "audio_url": audio_url,
        "meanings": parsed_meanings,
        "all_synonyms": unique_synonyms[:8],
        "all_antonyms": unique_antonyms[:8],
        "all_related": related_words[:6]
    }
