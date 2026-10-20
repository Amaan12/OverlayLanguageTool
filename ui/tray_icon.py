"""System Tray Icon Manager: Provides taskbar controls, enable/disable toggling, and quick menus."""

import logging
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont
from PyQt6.QtWidgets import QSystemTrayIcon, QMenu, QMessageBox
from ui.vocab_viewer import VocabViewerDialog

logger = logging.getLogger(__name__)

def create_tray_pixmap(enabled: bool) -> QPixmap:
    """Dynamically generates a crisp 32x32 tray icon without needing external image assets."""
    pixmap = QPixmap(32, 32)
    pixmap.fill(Qt.GlobalColor.transparent)
    
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    
    # Circle background
    bg_color = QColor("#10b981") if enabled else QColor("#64748b")
    painter.setBrush(bg_color)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(2, 2, 28, 28, 8, 8)
    
    # Letter "L" for Language
    painter.setPen(QColor("#ffffff"))
    font = QFont("Segoe UI", 15, QFont.Weight.Bold)
    painter.setFont(font)
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "L")
    painter.end()
    
    return pixmap

class SystemTrayManager(QSystemTrayIcon):
    """Manages the Windows taskbar system tray icon and context menu."""
    
    toggle_requested = pyqtSignal()
    exit_requested = pyqtSignal()
    
    def __init__(self, detector, parent=None):
        super().__init__(parent)
        self.detector = detector
        self.vocab_dialog = None
        
        self._init_menu()
        self._update_icon(self.detector.enabled)
        
        # Connect signals
        self.detector.status_changed.connect(self._update_icon)
        self.activated.connect(self._on_tray_activated)

    def _init_menu(self):
        self.menu = QMenu()
        self.menu.setStyleSheet("""
            QMenu {
                background-color: #1e2233;
                color: #e2e8f0;
                border: 1px solid #3b4261;
                border-radius: 6px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 20px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #3b4261;
                color: #ffffff;
            }
            QMenu::separator {
                height: 1px;
                background-color: #2f354a;
                margin: 4px 0px;
            }
        """)
        
        self.toggle_action = self.menu.addAction("Enabled (Ctrl+Alt+L)")
        self.toggle_action.setCheckable(True)
        self.toggle_action.setChecked(self.detector.enabled)
        self.toggle_action.triggered.connect(self.toggle_requested.emit)
        
        self.menu.addSeparator()
        
        self.vocab_action = self.menu.addAction("📚 Vocabulary Bank")
        self.vocab_action.triggered.connect(self._open_vocab_bank)
        
        self.menu.addSeparator()
        
        self.exit_action = self.menu.addAction("✕ Exit")
        self.exit_action.triggered.connect(self.exit_requested.emit)
        
        self.setContextMenu(self.menu)

    def _update_icon(self, enabled: bool):
        pixmap = create_tray_pixmap(enabled)
        self.setIcon(QIcon(pixmap))
        self.toggle_action.setChecked(enabled)
        status_text = "Active" if enabled else "Paused"
        self.setToolTip(f"Overlay Language Tool ({status_text})\nShortcut: Ctrl+Alt+L")

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            # Single click toggles enable/disable
            self.toggle_requested.emit()

    def _open_vocab_bank(self):
        if self.vocab_dialog is None or not self.vocab_dialog.isVisible():
            self.vocab_dialog = VocabViewerDialog()
            self.vocab_dialog.show()
        else:
            self.vocab_dialog.raise_()
            self.vocab_dialog.activateWindow()
