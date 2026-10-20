"""Main application entry point for Windows Overlay Language Tool."""

import sys
import logging
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon

from storage.db import init_db
from core.selection_detector import SelectionDetector
from ui.overlay_window import OverlayWindow
from ui.tray_icon import SystemTrayManager, create_tray_pixmap

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("OverlayLanguageTool")

def main():
    # 1. Initialize SQLite Database
    init_db()
    
    # 2. Setup Qt Application
    app = QApplication(sys.argv)
    app.setApplicationName("Overlay Language Tool")
    app.setQuitOnLastWindowClosed(False)  # Keep running in system tray
    
    # 3. Create Core Components
    detector = SelectionDetector()
    overlay = OverlayWindow()
    tray = SystemTrayManager(detector)
    
    # Set default app icon
    app_icon = QIcon(create_tray_pixmap(True))
    app.setWindowIcon(app_icon)
    
    # 4. Wire Signals & Slots
    detector.is_point_in_overlay = lambda x, y: overlay.isVisible() and overlay.geometry().contains(x, y)
    detector.word_selected.connect(overlay.display_word)
    detector.selection_cleared.connect(overlay.hide)
    
    tray.toggle_requested.connect(detector.toggle)
    tray.exit_requested.connect(lambda: _clean_exit(detector, app))
    
    # 5. Start Background Selection Hooks
    detector.start()
    tray.show()
    
    # 6. Welcome balloon notification
    tray.showMessage(
        "Overlay Language Tool Active",
        "Select any word with mouse or Shift+Arrows to see definitions.\nPress Ctrl+Alt+L to toggle.",
        QIcon(create_tray_pixmap(True)),
        4000
    )
    
    logger.info("Overlay Language Tool initialized and running.")
    sys.exit(app.exec())

def _clean_exit(detector: SelectionDetector, app: QApplication):
    logger.info("Stopping selection hooks and exiting.")
    detector.stop()
    app.quit()

if __name__ == "__main__":
    main()
