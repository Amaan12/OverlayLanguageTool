"""Text Extractor: retrieves selected text from active Windows application and isolates the first word."""

import re
import time
import logging
import ctypes
from ctypes import wintypes
from typing import Optional

logger = logging.getLogger(__name__)

# Win32 Constants
CF_UNICODETEXT = 13
VK_CONTROL = 0x11
VK_C = 0x43
KEYEVENTF_KEYUP = 0x0002

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

user32.OpenClipboard.argtypes = [wintypes.HWND]
user32.OpenClipboard.restype = wintypes.BOOL
user32.CloseClipboard.argtypes = []
user32.CloseClipboard.restype = wintypes.BOOL
user32.EmptyClipboard.argtypes = []
user32.EmptyClipboard.restype = wintypes.BOOL
user32.GetClipboardData.argtypes = [wintypes.UINT]
user32.GetClipboardData.restype = wintypes.HANDLE
user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
user32.SetClipboardData.restype = wintypes.HANDLE
user32.IsClipboardFormatAvailable.argtypes = [wintypes.UINT]
user32.IsClipboardFormatAvailable.restype = wintypes.BOOL

kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalLock.restype = ctypes.c_void_p
kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalUnlock.restype = wintypes.BOOL
GMEM_MOVEABLE = 0x0002

def get_clipboard_text() -> Optional[str]:
    """Safely retrieves current text from Windows clipboard."""
    if not user32.OpenClipboard(None):
        return None
    try:
        if not user32.IsClipboardFormatAvailable(CF_UNICODETEXT):
            return None
        h_data = user32.GetClipboardData(CF_UNICODETEXT)
        if not h_data:
            return None
        ptr = kernel32.GlobalLock(h_data)
        if not ptr:
            return None
        try:
            text = ctypes.c_wchar_p(ptr).value
            return text
        finally:
            kernel32.GlobalUnlock(h_data)
    finally:
        user32.CloseClipboard()

def set_clipboard_text(text: Optional[str]) -> bool:
    """Safely sets text to Windows clipboard."""
    if text is None:
        return False
    if not user32.OpenClipboard(None):
        return False
    try:
        user32.EmptyClipboard()
        data_bytes = (text + '\0').encode('utf-16le')
        h_global = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data_bytes))
        if not h_global:
            return False
        ptr = kernel32.GlobalLock(h_global)
        if not ptr:
            return False
        ctypes.memmove(ptr, data_bytes, len(data_bytes))
        kernel32.GlobalUnlock(h_global)
        user32.SetClipboardData(CF_UNICODETEXT, h_global)
        return True
    finally:
        user32.CloseClipboard()

def extract_selected_text_with_fallback() -> Optional[str]:
    """Captures selected text safely by preserving the user's previous clipboard contents."""
    # 1. Backup user's clipboard
    previous_clip = get_clipboard_text()

    # 2. Put a unique sentinel into clipboard to detect if Ctrl+C copied new text
    sentinel = f"__SENTINEL_{time.time()}__"
    set_clipboard_text(sentinel)

    # 3. Simulate Ctrl+C instantly
    user32.keybd_event(VK_CONTROL, 0, 0, 0)
    user32.keybd_event(VK_C, 0, 0, 0)
    time.sleep(0.008)
    user32.keybd_event(VK_C, 0, KEYEVENTF_KEYUP, 0)
    user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)

    # 4. Fast poll (every 4ms up to 55ms) for clipboard change
    selected_text = None
    start = time.time()
    while time.time() - start < 0.055:
        time.sleep(0.004)
        current = get_clipboard_text()
        if current and current != sentinel:
            selected_text = current
            break

    # 5. Restore previous clipboard so user is not disrupted
    set_clipboard_text(previous_clip)

    if selected_text and selected_text != sentinel:
        return selected_text
    return None

def extract_first_word(raw_text: Optional[str]) -> Optional[str]:
    """Isolates the very first valid word from a selection string.
    
    Examples:
    - 'ubiquitous presence' -> 'ubiquitous'
    - '“eloquent”' -> 'eloquent'
    - 'state-of-the-art' -> 'state-of-the-art'
    - '   ' -> None
    - '12345' -> None
    """
    if not raw_text:
        return None
        
    cleaned = raw_text.strip()
    if not cleaned:
        return None

    # Matches words with hyphens and apostrophes (e.g., well-spoken, haven't)
    match = re.search(r"\b[A-Za-z]+(?:['\-][A-Za-z]+)*\b", cleaned)
    if match:
        word = match.group(0).lower()
        # Filter out 1-letter words except 'a' or 'i' if needed, or single letters
        if len(word) >= 2 or word in ('a', 'i'):
            return word
    return None
