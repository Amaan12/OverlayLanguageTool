"""Overlay Window: Modern docked top-right floating card displaying word definitions,
with persistent synonyms/antonyms outside the scrollbar, and instant asynchronous loading.
"""

import logging
from typing import Optional, Dict, Any, List

from PyQt6.QtCore import Qt, QUrl, pyqtSignal, QPoint, QThread
from PyQt6.QtGui import QFont, QColor, QCursor, QGuiApplication
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QScrollArea, QFrame, QApplication, QSizePolicy
)
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput

import win32gui
import win32con

from config import OVERLAY_WIDTH, OVERLAY_HEIGHT
from storage.db import is_word_in_vault, save_to_vault, remove_from_vault, get_cached_word
from core.dictionary_engine import lookup_word

logger = logging.getLogger(__name__)

class LookupWorker(QThread):
    """Background thread to fetch dictionary data without blocking the UI."""
    data_received = pyqtSignal(dict)
    
    def __init__(self, word: str, parent=None):
        super().__init__(parent)
        self.word = word
        
    def run(self):
        data = lookup_word(self.word)
        if not data:
            data = {"word": self.word, "found": False, "message": "Lookup failed."}
        self.data_received.emit(data)


class OverlayWindow(QWidget):
    """Docked top-right borderless overlay displaying word definitions without stealing focus."""
    
    word_clicked = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_word_data: Optional[Dict[str, Any]] = None
        self.current_query_word: str = ""
        self.worker: Optional[LookupWorker] = None
        
        # Audio Player
        self.player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.player.setAudioOutput(self.audio_output)
        # Foreground application tracking
        self.origin_hwnd = 0
        from PyQt6.QtCore import QTimer
        self.focus_timer = QTimer(self)
        self.focus_timer.timeout.connect(self._check_focus)
        
        self._init_window_flags()
        self._init_ui()
        self._apply_styles()

    def _init_window_flags(self):
        # Frameless, Always on Top, Tool window (hidden from taskbar/Alt-Tab)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setFixedWidth(OVERLAY_WIDTH)
        self.setFixedHeight(OVERLAY_HEIGHT)

    def showEvent(self, event):
        super().showEvent(event)
        self._apply_no_activate_flag()

    def _apply_no_activate_flag(self):
        """Enforces WS_EX_NOACTIVATE using Win32 API so the window does not steal keyboard focus."""
        try:
            hwnd = int(self.winId())
            style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
            win32gui.SetWindowLong(
                hwnd, 
                win32con.GWL_EXSTYLE, 
                style | win32con.WS_EX_NOACTIVATE | win32con.WS_EX_TOPMOST
            )
        except Exception as e:
            logger.warning(f"Could not apply WS_EX_NOACTIVATE: {e}")

    def _check_focus(self):
        """Hides overlay if user switches to a different application."""
        if not self.isVisible():
            self.focus_timer.stop()
            return
        try:
            fg = win32gui.GetForegroundWindow()
            if fg != 0 and self.origin_hwnd != 0 and fg != self.origin_hwnd and fg != int(self.winId()):
                self.hide()
                self.focus_timer.stop()
        except Exception:
            pass

    def hideEvent(self, event):
        super().hideEvent(event)
        self.focus_timer.stop()

    def _init_ui(self):
        # 0 margins on root layout so card meets corner to corner exactly
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        
        # Main Card Container
        self.card = QFrame()
        self.card.setObjectName("cardFrame")
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(18, 16, 18, 14)
        card_layout.setSpacing(8)
        
        # --- Top Header Bar ---
        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)
        
        self.word_label = QLabel("Word")
        self.word_label.setObjectName("wordLabel")
        font = QFont("Segoe UI", 17, QFont.Weight.Bold)
        self.word_label.setFont(font)
        
        self.audio_btn = QPushButton("🔊")
        self.audio_btn.setObjectName("iconBtn")
        self.audio_btn.setToolTip("Listen to pronunciation")
        self.audio_btn.setFixedSize(28, 28)
        self.audio_btn.clicked.connect(self._play_audio)
        self.audio_btn.hide()
        
        self.star_btn = QPushButton("☆")
        self.star_btn.setObjectName("starBtn")
        self.star_btn.setToolTip("Save to Vocabulary Vault")
        self.star_btn.setFixedSize(28, 28)
        self.star_btn.clicked.connect(self._toggle_vault)
        
        self.close_btn = QPushButton("✕")
        self.close_btn.setObjectName("closeBtn")
        self.close_btn.setToolTip("Close")
        self.close_btn.setFixedSize(26, 26)
        self.close_btn.clicked.connect(self.hide)
        
        header_layout.addWidget(self.word_label)
        header_layout.addWidget(self.audio_btn)
        header_layout.addStretch()
        header_layout.addWidget(self.star_btn)
        header_layout.addWidget(self.close_btn)
        card_layout.addLayout(header_layout)
        
        # Phonetic Label
        self.phonetic_label = QLabel("")
        self.phonetic_label.setObjectName("phoneticLabel")
        card_layout.addWidget(self.phonetic_label)
        
        # --- Fixed Synonyms Section (OUTSIDE scrollbar) ---
        self.synonyms_widget = QWidget()
        self.synonyms_widget.setObjectName("synContainer")
        syn_vbox = QVBoxLayout(self.synonyms_widget)
        syn_vbox.setContentsMargins(0, 4, 0, 4)
        syn_vbox.setSpacing(4)
        
        syn_title = QLabel("SYNONYMS")
        syn_title.setObjectName("synTitle")
        syn_vbox.addWidget(syn_title)
        
        self.syn_chips_widget = QWidget()
        self.syn_chips_layout = QHBoxLayout(self.syn_chips_widget)
        self.syn_chips_layout.setContentsMargins(0, 0, 0, 0)
        self.syn_chips_layout.setSpacing(6)
        syn_vbox.addWidget(self.syn_chips_widget)
        
        card_layout.addWidget(self.synonyms_widget)
        self.synonyms_widget.hide()

        # --- Fixed Antonyms Section (OUTSIDE scrollbar) ---
        self.antonyms_widget = QWidget()
        self.antonyms_widget.setObjectName("antContainer")
        ant_vbox = QVBoxLayout(self.antonyms_widget)
        ant_vbox.setContentsMargins(0, 2, 0, 4)
        ant_vbox.setSpacing(4)
        
        ant_title = QLabel("ANTONYMS")
        ant_title.setObjectName("antTitle")
        ant_vbox.addWidget(ant_title)
        
        self.ant_chips_widget = QWidget()
        self.ant_chips_layout = QHBoxLayout(self.ant_chips_widget)
        self.ant_chips_layout.setContentsMargins(0, 0, 0, 0)
        self.ant_chips_layout.setSpacing(6)
        ant_vbox.addWidget(self.ant_chips_widget)
        
        card_layout.addWidget(self.antonyms_widget)
        self.antonyms_widget.hide()

        # --- Fixed Related Words Section (OUTSIDE scrollbar) ---
        self.related_widget = QWidget()
        self.related_widget.setObjectName("relContainer")
        rel_vbox = QVBoxLayout(self.related_widget)
        rel_vbox.setContentsMargins(0, 2, 0, 4)
        rel_vbox.setSpacing(4)
        
        rel_title = QLabel("RELATED WORDS")
        rel_title.setObjectName("relTitle")
        rel_vbox.addWidget(rel_title)
        
        self.rel_chips_widget = QWidget()
        self.rel_chips_layout = QHBoxLayout(self.rel_chips_widget)
        self.rel_chips_layout.setContentsMargins(0, 0, 0, 0)
        self.rel_chips_layout.setSpacing(6)
        rel_vbox.addWidget(self.rel_chips_widget)
        
        card_layout.addWidget(self.related_widget)
        self.related_widget.hide()
        
        # Separator Line before scrollable definitions
        self.line = QFrame()
        self.line.setFrameShape(QFrame.Shape.HLine)
        self.line.setObjectName("separator")
        card_layout.addWidget(self.line)
        
        # --- Scrollable Area ONLY for Definitions & Examples ---
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setObjectName("scrollArea")
        
        self.content_widget = QWidget()
        self.content_widget.setObjectName("content_widget")
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 4, 6, 4)
        self.content_layout.setSpacing(12)
        
        self.scroll_area.setWidget(self.content_widget)
        card_layout.addWidget(self.scroll_area, 1)
        
        # --- Bottom Status / Actions ---
        bottom_layout = QHBoxLayout()
        bottom_layout.setContentsMargins(0, 4, 0, 0)
        
        self.copy_btn = QPushButton("📋 Copy")
        self.copy_btn.setObjectName("actionBtn")
        self.copy_btn.clicked.connect(self._copy_definition)
        
        self.hint_label = QLabel("Toggle: Ctrl+Alt+L")
        self.hint_label.setObjectName("hintLabel")
        
        bottom_layout.addWidget(self.copy_btn)
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.hint_label)
        card_layout.addLayout(bottom_layout)
        
        root_layout.addWidget(self.card)

    def _apply_styles(self):
        self.setStyleSheet("""
            #cardFrame {
                background-color: #13141f;
                border: 1px solid #2f354a;
                border-top: none;
                border-right: none;
                border-top-left-radius: 0px;
                border-top-right-radius: 0px;
                border-bottom-right-radius: 0px;
                border-bottom-left-radius: 14px;
            }
            #wordLabel {
                color: #f8fafc;
            }
            #phoneticLabel {
                color: #94a3b8;
                font-family: 'Segoe UI', sans-serif;
                font-size: 13px;
                margin-top: -4px;
            }
            #separator {
                border: none;
                background-color: #24283b;
                height: 1px;
                margin: 4px 0px;
            }
            #synTitle {
                color: #34d399;
                font-size: 11px;
                font-weight: bold;
                letter-spacing: 0.5px;
            }
            #antTitle {
                color: #f87171;
                font-size: 11px;
                font-weight: bold;
                letter-spacing: 0.5px;
            }
            #relTitle {
                color: #a78bfa;
                font-size: 11px;
                font-weight: bold;
                letter-spacing: 0.5px;
            }
            #scrollArea {
                background: transparent;
            }
            QWidget#content_widget {
                background: transparent;
            }
            #iconBtn, #starBtn, #closeBtn {
                background-color: #1e2233;
                color: #cbd5e1;
                border: 1px solid #333b54;
                border-radius: 6px;
                font-size: 13px;
            }
            #iconBtn:hover, #starBtn:hover, #closeBtn:hover {
                background-color: #2e364f;
                color: #ffffff;
            }
            #starBtn {
                font-size: 15px;
                color: #fbbf24;
            }
            #closeBtn:hover {
                background-color: #ef4444;
                border-color: #ef4444;
            }
            #actionBtn {
                background-color: #1e2233;
                color: #93c5fd;
                border: 1px solid #333b54;
                border-radius: 6px;
                padding: 4px 12px;
                font-size: 11px;
            }
            #actionBtn:hover {
                background-color: #2e364f;
                color: #ffffff;
            }
            #hintLabel {
                color: #64748b;
                font-size: 10px;
            }
            .posBadge {
                background-color: #312e81;
                color: #a5b4fc;
                border-radius: 4px;
                padding: 2px 7px;
                font-weight: bold;
                font-size: 11px;
            }
            .defText {
                color: #e2e8f0;
                font-size: 13px;
                line-height: 1.45;
            }
            .exampleText {
                color: #94a3b8;
                font-style: italic;
                font-size: 12px;
                margin-left: 8px;
            }
            .pillSyn {
                background-color: #064e3b;
                color: #a7f3d0;
                border: 1px solid #047857;
                border-radius: 5px;
                padding: 3px 8px;
                font-size: 11px;
                font-weight: 500;
            }
            .pillSyn:hover {
                background-color: #059669;
                color: #ffffff;
            }
            .pillAnt {
                background-color: #450a0a;
                color: #fecaca;
                border: 1px solid #b91c1c;
                border-radius: 5px;
                padding: 3px 8px;
                font-size: 11px;
                font-weight: 500;
            }
            .pillAnt:hover {
                background-color: #dc2626;
                color: #ffffff;
            }
            .pillRel {
                background-color: #2e1065;
                color: #ddd6fe;
                border: 1px solid #6d28d9;
                border-radius: 5px;
                padding: 3px 8px;
                font-size: 11px;
                font-weight: 500;
            }
            .pillRel:hover {
                background-color: #5b21b6;
                color: #ffffff;
            }
            QScrollBar:vertical {
                border: none;
                background: #13141f;
                width: 6px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #2e364f;
                min-height: 24px;
                border-radius: 3px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

    def _position_top_right(self):
        """Positions window flush against the top-right corner of the active screen."""
        screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        if not screen:
            return
            
        geo = screen.availableGeometry()
        
        # Exact corner-to-corner meeting
        target_x = geo.right() - self.width() + 1
        target_y = geo.top()
        
        # Adjust height if screen is smaller
        max_h = min(OVERLAY_HEIGHT, geo.height() - 10)
        self.setFixedHeight(max_h)
        
        self.move(target_x, target_y)

    def display_word(self, word: str, cursor_x: int = 0, cursor_y: int = 0):
        """Instantly shows the overlay at the top-right corner and loads data asynchronously."""
        clean_word = word.strip().lower()
        if not clean_word:
            return
            
        self.current_query_word = clean_word
        
        # 1. Stop any pending worker
        if self.worker and self.worker.isRunning():
            try:
                self.worker.data_received.disconnect()
            except Exception:
                pass
            self.worker.terminate()
            self.worker = None

        # 2. Update initial UI instantly
        self.word_label.setText(clean_word.capitalize())
        self.audio_btn.hide()
        self._clear_content()
        self._clear_chips(self.syn_chips_layout)
        self._clear_chips(self.ant_chips_layout)
        self._clear_chips(self.rel_chips_layout)
        self.synonyms_widget.hide()
        self.antonyms_widget.hide()
        self.related_widget.hide()
        
        # 3. Position flush to top-right corner and show IMMEDIATELY (<5ms)
        try:
            self.origin_hwnd = win32gui.GetForegroundWindow()
        except Exception:
            self.origin_hwnd = 0
        self.focus_timer.start(250)

        self._position_top_right()
        self.show()
        self.raise_()

        # 4. Check local cache first for instant 0ms render
        cached_data = get_cached_word(clean_word)
        if cached_data:
            self._render_word_data(cached_data)
            return

        # 5. Otherwise, show instant loading indicator and query asynchronously
        self.phonetic_label.setText("Fetching definition...")
        self.star_btn.hide()
        
        self.worker = LookupWorker(clean_word, self)
        self.worker.data_received.connect(self._on_lookup_finished)
        self.worker.start()

    def _on_lookup_finished(self, data: Dict[str, Any]):
        # Ensure result matches the currently queried word
        if data.get("word", "").lower() != self.current_query_word:
            return
        self._render_word_data(data)

    def _render_word_data(self, data: Dict[str, Any]):
        """Populates the overlay with full dictionary data."""
        self.current_word_data = data
        self._clear_content()
        
        if not data or not data.get("found", False):
            self.phonetic_label.setText("")
            msg = data.get("message", f"No definition found for '{data.get('word', '')}'.")
            err_label = QLabel(msg)
            err_label.setProperty("class", "defText")
            err_label.setWordWrap(True)
            self.content_layout.addWidget(err_label)
            self.star_btn.hide()
            self.synonyms_widget.hide()
            self.antonyms_widget.hide()
            self.related_widget.hide()
            return

        self.star_btn.show()
        self._update_star_button(data["word"])
        
        # Phonetic & Audio
        phonetic = data.get("phonetic", "")
        self.phonetic_label.setText(phonetic)
        
        if data.get("audio_url"):
            self.audio_btn.show()
        else:
            self.audio_btn.hide()
            
        # --- Render Synonyms OUTSIDE Scrollbar ---
        synonyms = data.get("all_synonyms", [])
        self._clear_chips(self.syn_chips_layout)
        if synonyms:
            for s in synonyms[:6]:
                btn = QPushButton(s)
                btn.setProperty("class", "pillSyn")
                btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
                btn.clicked.connect(lambda checked, w=s: self.display_word(w))
                self.syn_chips_layout.addWidget(btn)
            self.syn_chips_layout.addStretch()
            self.synonyms_widget.show()
        else:
            self.synonyms_widget.hide()
            
        # --- Render Antonyms OUTSIDE Scrollbar ---
        antonyms = data.get("all_antonyms", [])
        self._clear_chips(self.ant_chips_layout)
        if antonyms:
            for a in antonyms[:6]:
                btn = QPushButton(a)
                btn.setProperty("class", "pillAnt")
                btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
                btn.clicked.connect(lambda checked, w=a: self.display_word(w))
                self.ant_chips_layout.addWidget(btn)
            self.ant_chips_layout.addStretch()
            self.antonyms_widget.show()
        else:
            self.antonyms_widget.hide()

        # --- Render Related Words OUTSIDE Scrollbar ---
        related = data.get("all_related", [])
        self._clear_chips(self.rel_chips_layout)
        if related:
            for r in related[:6]:
                btn = QPushButton(r)
                btn.setProperty("class", "pillRel")
                btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
                btn.clicked.connect(lambda checked, w=r: self.display_word(w))
                self.rel_chips_layout.addWidget(btn)
            self.rel_chips_layout.addStretch()
            self.related_widget.show()
        else:
            self.related_widget.hide()

        # --- Render Meanings INSIDE Scroll Area ---
        for meaning in data.get("meanings", []):
            pos = meaning.get("part_of_speech", "")
            if pos:
                pos_label = QLabel(pos.upper())
                pos_label.setProperty("class", "posBadge")
                self.content_layout.addWidget(pos_label)
                
            for idx, d_text in enumerate(meaning.get("definitions", []), 1):
                d_label = QLabel(f"{idx}. {d_text}")
                d_label.setProperty("class", "defText")
                d_label.setWordWrap(True)
                self.content_layout.addWidget(d_label)
                
            for ex in meaning.get("examples", []):
                ex_label = QLabel(f'"{ex}"')
                ex_label.setProperty("class", "exampleText")
                ex_label.setWordWrap(True)
                self.content_layout.addWidget(ex_label)

        # Always show audio button when word data is loaded
        self.audio_btn.show()

    def _clear_content(self):
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def _clear_chips(self, layout: QHBoxLayout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def _play_audio(self):
        if not self.current_word_data:
            return
        audio_url = self.current_word_data.get("audio_url")
        if audio_url:
            self.player.setSource(QUrl(audio_url))
            self.player.play()
        else:
            # Windows built-in TTS fallback
            import threading
            import pythoncom
            import win32com.client
            word = self.current_word_data.get("word", "")
            def _speak():
                try:
                    pythoncom.CoInitialize()
                    sp = win32com.client.Dispatch("SAPI.SpVoice")
                    sp.Speak(word)
                finally:
                    pythoncom.CoUninitialize()
            threading.Thread(target=_speak, daemon=True).start()

    def _update_star_button(self, word: str):
        if is_word_in_vault(word):
            self.star_btn.setText("★")
            self.star_btn.setToolTip("Saved in Vocabulary Vault")
        else:
            self.star_btn.setText("☆")
            self.star_btn.setToolTip("Save to Vocabulary Vault")

    def _toggle_vault(self):
        if not self.current_word_data:
            return
        word = self.current_word_data["word"]
        if is_word_in_vault(word):
            remove_from_vault(word)
            self._update_star_button(word)
        else:
            meanings = self.current_word_data.get("meanings", [])
            pos = meanings[0].get("part_of_speech", "") if meanings else ""
            defs = meanings[0].get("definitions", [""]) if meanings else [""]
            ex = meanings[0].get("examples", [""])[0] if meanings and meanings[0].get("examples") else ""
            
            save_to_vault(
                word=word,
                phonetic=self.current_word_data.get("phonetic", ""),
                part_of_speech=pos,
                definition=defs[0] if defs else "",
                example=ex,
                synonyms=", ".join(self.current_word_data.get("all_synonyms", [])[:5]),
                antonyms=", ".join(self.current_word_data.get("all_antonyms", [])[:5])
            )
            self._update_star_button(word)

    def _copy_definition(self):
        if not self.current_word_data:
            return
        word = self.current_word_data.get("word", "")
        phonetic = self.current_word_data.get("phonetic", "")
        lines = [f"{word.capitalize()} {phonetic}"]
        for m in self.current_word_data.get("meanings", []):
            lines.append(f"\n[{m.get('part_of_speech')}]")
            for idx, d in enumerate(m.get("definitions", []), 1):
                lines.append(f"  {idx}. {d}")
        
        QApplication.clipboard().setText("\n".join(lines))
        self.copy_btn.setText("✓ Copied!")
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(1500, lambda: self.copy_btn.setText("📋 Copy"))
