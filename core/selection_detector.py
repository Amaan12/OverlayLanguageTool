"""Selection Detector: listens for mouse and keyboard selection events globally."""

import time
import math
import threading
import logging
from typing import Optional, Callable
from PyQt6.QtCore import QObject, pyqtSignal

from pynput import mouse, keyboard
from core.text_extractor import extract_selected_text_with_fallback, extract_first_word
from config import SELECTION_DEBOUNCE_MS, MOUSE_DEBOUNCE_MS, KEYBOARD_DEBOUNCE_MS

logger = logging.getLogger(__name__)

class SelectionDetector(QObject):
    """Monitors global Windows mouse and keyboard events to detect text selection and deselects."""
    
    # Signals emitted to UI thread
    word_selected = pyqtSignal(str, int, int)  # (first_word, cursor_x, cursor_y)
    selection_cleared = pyqtSignal()
    status_changed = pyqtSignal(bool)           # (is_enabled)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.enabled = True
        
        # Callback to check if a screen coordinate is inside the overlay window
        self.is_point_in_overlay: Optional[Callable[[int, int], bool]] = None
        
        # Mouse tracking state
        self._mouse_pressed = False
        self._press_pos = (0, 0)
        self._press_time = 0.0
        self._last_click_time = 0.0
        
        # Keyboard tracking state
        self._shift_pressed = False
        self._ctrl_pressed = False
        self._alt_pressed = False
        
        # Debounce timer
        self._debounce_timer: Optional[threading.Timer] = None
        self._lock = threading.Lock()
        
        # Background listeners
        self._mouse_listener: Optional[mouse.Listener] = None
        self._keyboard_listener: Optional[keyboard.Listener] = None

    def start(self):
        """Starts mouse and keyboard global hooks."""
        self._mouse_listener = mouse.Listener(
            on_click=self._on_mouse_click,
            on_move=self._on_mouse_move,
            on_scroll=self._on_mouse_scroll
        )
        self._mouse_listener.daemon = True
        self._mouse_listener.start()
        
        self._keyboard_listener = keyboard.Listener(
            on_press=self._on_key_press,
            on_release=self._on_key_release
        )
        self._keyboard_listener.daemon = True
        self._keyboard_listener.start()
        logger.info("Selection detector hooks started.")

    def stop(self):
        """Stops background hooks."""
        if self._mouse_listener:
            self._mouse_listener.stop()
        if self._keyboard_listener:
            self._keyboard_listener.stop()
        self._cancel_debounce()

    def set_enabled(self, enabled: bool):
        """Enables or disables selection detection."""
        self.enabled = enabled
        self.status_changed.emit(self.enabled)
        if not self.enabled:
            self._cancel_debounce()
            self.selection_cleared.emit()

    def toggle(self):
        """Toggles active state."""
        self.set_enabled(not self.enabled)

    # ------------------ Debouncing ------------------
    def _cancel_debounce(self):
        with self._lock:
            if self._debounce_timer is not None:
                self._debounce_timer.cancel()
                self._debounce_timer = None

    def _schedule_check(self, x: int, y: int, delay_ms: Optional[int] = None):
        if not self.enabled:
            return
        self._cancel_debounce()
        actual_delay = delay_ms if delay_ms is not None else SELECTION_DEBOUNCE_MS
        delay_sec = max(0.01, actual_delay / 1000.0)
        with self._lock:
            self._debounce_timer = threading.Timer(delay_sec, self._perform_selection_check, args=(x, y))
            self._debounce_timer.daemon = True
            self._debounce_timer.start()

    def _perform_selection_check(self, x: int, y: int):
        if not self.enabled:
            return
            
        raw_text = extract_selected_text_with_fallback()
        if raw_text:
            first_word = extract_first_word(raw_text)
            if first_word:
                self.word_selected.emit(first_word, x, y)
                return
                
        # If no text selected or selection was cleared
        self.selection_cleared.emit()

    # ------------------ Mouse Handling ------------------
    def _on_mouse_move(self, x, y):
        pass

    def _on_mouse_scroll(self, x, y, dx, dy):
        """Scrolling the page or document indicates moving away from selected text -> hide window."""
        if not self.enabled:
            return
        if self.is_point_in_overlay and self.is_point_in_overlay(x, y):
            # User is scrolling the definition inside the overlay card
            return
        self._cancel_debounce()
        self.selection_cleared.emit()

    def _on_mouse_click(self, x, y, button, pressed):
        # If clicking inside the overlay window, ignore so user can click buttons/chips
        if self.is_point_in_overlay and self.is_point_in_overlay(x, y):
            return

        # Right-click or middle-click outside overlay indicates context menu or deselect
        if button != mouse.Button.left:
            if pressed:
                self._cancel_debounce()
                self.selection_cleared.emit()
            return
            
        current_time = time.time()
        
        if pressed:
            self._mouse_pressed = True
            self._press_pos = (x, y)
            self._press_time = current_time
            self._cancel_debounce()
        else:
            self._mouse_pressed = False
            dx = x - self._press_pos[0]
            dy = y - self._press_pos[1]
            dist = math.hypot(dx, dy)
            time_diff = current_time - self._last_click_time
            self._last_click_time = current_time
            
            is_double_click = (time_diff < 0.45 and dist < 6)
            is_drag_selection = (dist > 8)
            
            if is_drag_selection or is_double_click:
                # Text selection occurred
                self._schedule_check(x, y, delay_ms=MOUSE_DEBOUNCE_MS)
            else:
                # Single simple click without movement = clearing selection
                self._cancel_debounce()
                self.selection_cleared.emit()

    # ------------------ Keyboard Handling ------------------
    def _on_key_press(self, key):
        # Track modifier keys
        if key in (keyboard.Key.shift, keyboard.Key.shift_r):
            self._shift_pressed = True
            return
        elif key in (keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
            self._ctrl_pressed = True
            return
        elif key in (keyboard.Key.alt_l, keyboard.Key.alt_r, keyboard.Key.alt_gr):
            self._alt_pressed = True
            return
            
        # Global Hotkey check: Ctrl + Alt + L
        if self._ctrl_pressed and self._alt_pressed:
            try:
                if hasattr(key, 'char') and key.char and key.char.lower() == 'l':
                    self.toggle()
                    return
            except Exception:
                pass

        # If user presses ANY key without Shift (typing, arrows, space, enter, backspace, esc, etc.)
        # that is not solitary Ctrl or Ctrl+C:
        is_ctrl_c = self._ctrl_pressed and not self._alt_pressed and hasattr(key, 'char') and key.char in ('c', 'C')
        if not self._shift_pressed and not is_ctrl_c:
            self._cancel_debounce()
            self.selection_cleared.emit()

    def _on_key_release(self, key):
        if key in (keyboard.Key.shift, keyboard.Key.shift_r):
            self._shift_pressed = False
        elif key in (keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
            self._ctrl_pressed = False
        elif key in (keyboard.Key.alt_l, keyboard.Key.alt_r, keyboard.Key.alt_gr):
            self._alt_pressed = False
            
        nav_keys = (keyboard.Key.left, keyboard.Key.right, keyboard.Key.up, keyboard.Key.down,
                    keyboard.Key.home, keyboard.Key.end, keyboard.Key.page_up, keyboard.Key.page_down)
                    
        # If navigation keys were released while Shift is active (keyboard text selection!)
        if key in nav_keys and self._shift_pressed:
            mouse_ctrl = mouse.Controller()
            mx, my = mouse_ctrl.position
            self._schedule_check(int(mx), int(my), delay_ms=KEYBOARD_DEBOUNCE_MS)
