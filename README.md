# 📖 Overlay Language Tool (Windows)

An intelligent, non-intrusive desktop overlay that instantly surfaces definitions, pronunciations, synonyms, antonyms, and related words for any selected word across any application on Windows.

Designed for language learners, writers, and students who want to build vocabulary effortlessly without switching tabs or losing reading focus.

---

## 🎯 What This Repo Does

When active, **Overlay Language Tool** runs silently in your Windows system tray. Whenever you highlight a word anywhere in the operating system—whether in a web browser, PDF document, code editor, eBook, or chat application—it instantly opens an elegant dark card docked flush in the top-right corner of your screen showing:

1. **Word Definition & Part of Speech**: Clear, numbered explanations and usage examples.
2. **First-Word Isolation**: If you highlight an entire sentence or phrase, it automatically parses and defines the first word.
3. **Persistent Synonyms & Antonyms**: Vibrant clickable chips displayed prominently outside the scrollbar.
4. **Contextual Related Words**: Thematic associations (e.g. for *coffee*: *espresso, arabica, beans, roasting*) so you can expand your vocabulary even when direct synonyms don't exist.
5. **Universal Pronunciation**: One-click native audio pronunciation (`🔊`) with an automatic Windows SAPI text-to-speech fallback.
6. **Focus-Free Display (`WS_EX_NOACTIVATE`)**: Appears above active apps without stealing keyboard or window focus, so your typing or reading is never interrupted.
7. **Smart Activity Auto-Hide**: Disappears automatically whenever you type, press arrow keys, scroll the mouse wheel, right-click, switch windows, or click empty space.
8. **Vocabulary Vault & Anki Exporter**: Star words with 1 click to save them into a local study bank, with search and CSV/Anki export capabilities.

---

## 📦 Dependencies & What Needs to Be Installed

This application runs on **Python 3.10+ on Windows**. It relies on four primary external libraries:

| Dependency | Purpose | Why It's Needed |
|---|---|---|
| **`PyQt6`** | User Interface | Provides the frameless floating card, animations, audio playback (`QMediaPlayer`), and system tray icon. |
| **`pynput`** | Global Input Hooks | Listens for global mouse drags/double-clicks, keyboard cursor selections (`Shift + Arrows`), and deselect events across all Windows apps. |
| **`pywin32`** | Windows OS Integration | Injects native Win32 window styles (`WS_EX_NOACTIVATE`, `WS_EX_TOPMOST`) and provides built-in Windows SAPI speech synthesis. |
| **`requests`** | Lexical APIs | Fetches definitions, phonetics, audio, and synonyms from Free Dictionary API and Datamuse API with anti-blocking headers. |

All dependencies are defined in [`requirements.txt`](requirements.txt):
```txt
PyQt6>=6.6.0
pynput>=1.7.6
requests>=2.31.0
pywin32>=306
```

---

## 🚀 Installation & Setup

### 1. Clone the Repository
```bash
git clone https://github.com/Amaan12/OverlayLanguageTool.git
cd OverlayLanguageTool
```

### 2. Install Dependencies
Make sure you have Python installed, then install the required libraries:
```bash
pip install -r requirements.txt
```

---

## 💻 How to Run

### Option 1: Double-Click Launcher
Double-click [**`run.bat`**](run.bat) inside the project folder.

### Option 2: Terminal / Command Prompt
```bash
python main.py
```

Look for the green **"L"** icon in your Windows Taskbar System Tray.

---

## ⌨️ Controls & Shortcuts

| Action | How to Trigger |
|---|---|
| **Toggle Active / Disabled** | Press `Ctrl + Alt + L` or click the Taskbar Tray icon |
| **Select Word (Mouse)** | Drag or double-click any word in any app |
| **Select Word (Keyboard)** | Highlight with `Shift + Arrow Keys` or `Ctrl + Shift + Arrows` |
| **Auto-Dismiss / Hide** | Tap any arrow key, type a letter, press `Esc`/`Space`/`Enter`, scroll the mouse wheel, or click away |
| **Listen to Audio** | Click the `🔊` button on the overlay |
| **Star / Save Word** | Click the `☆` / `★` star icon |
| **Chain Word Exploration** | Click any Synonym, Antonym, or Related Word chip to look it up immediately |
| **Review Saved Words** | Right-click the Tray icon $\rightarrow$ **Vocabulary Bank** |
| **Exit Application** | Right-click the Tray icon $\rightarrow$ **Exit**, or close the terminal window |

---

## 🏗️ Architecture Overview

```
OverlayLanguageTool/
├── main.py                     # Application startup, tray registration & signal wiring
├── config.py                   # Dimensions (420x510), delays (30ms), hotkeys
├── requirements.txt            # Dependency manifest
├── run.bat                     # Windows one-click batch launcher
├── core/
│   ├── dictionary_engine.py    # Multi-provider (Free Dictionary API + Datamuse fallback)
│   ├── selection_detector.py   # Global mouse + keyboard listeners with deselect auto-hide
│   └── text_extractor.py       # Non-destructive clipboard snapshot & first-word regex
├── ui/
│   ├── overlay_window.py       # Top-right flush card with persistent chips & async loader
│   ├── tray_icon.py            # Windows taskbar system tray controller
│   └── vocab_viewer.py         # Study review dialog & Anki/CSV flashcard exporter
├── storage/
│   └── db.py                   # Local SQLite manager for 0ms caching & saved vocabulary
└── tests/
    ├── test_db.py              # SQLite cache & vault unit tests
    ├── test_dictionary_engine.py # API parser & Datamuse fallback tests
    └── test_text_extractor.py  # Regex word isolation tests
```

---

## 🧪 Running Tests

To run the automated test suite:
```bash
python -m unittest discover -s tests -p "test_*.py"
```
