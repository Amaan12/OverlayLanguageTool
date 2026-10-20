"""Vocabulary Viewer: Window for reviewing and managing saved words and exporting to Anki/CSV."""

import csv
import logging
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QTableWidget, QTableWidgetItem, QPushButton, QHeaderView, 
    QFileDialog, QMessageBox, QAbstractItemView
)
from storage.db import get_all_vault_words, remove_from_vault

logger = logging.getLogger(__name__)

class VocabViewerDialog(QDialog):
    """Vocabulary Bank dialog for reviewing saved words to improve retention."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Vocabulary Bank & Review")
        self.resize(780, 500)
        self._init_ui()
        self._load_words()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)
        
        # Header + Search Row
        top_row = QHBoxLayout()
        title_label = QLabel("📚 Saved Vocabulary")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #f1f5f9;")
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Filter words...")
        self.search_input.textChanged.connect(self._filter_words)
        self.search_input.setStyleSheet("""
            QLineEdit {
                background-color: #1e2233;
                color: #f1f5f9;
                border: 1px solid #3b4261;
                border-radius: 6px;
                padding: 6px 10px;
            }
        """)
        
        top_row.addWidget(title_label)
        top_row.addStretch()
        top_row.addWidget(self.search_input)
        layout.addLayout(top_row)
        
        # Table of saved words
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Word", "Type", "Definition", "Example", "Saved Date"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: #16161e;
                color: #e2e8f0;
                gridline-color: #24283b;
                border: 1px solid #2f354a;
                border-radius: 8px;
            }
            QHeaderView::section {
                background-color: #1f2335;
                color: #94a3b8;
                padding: 6px;
                border: 1px solid #24283b;
                font-weight: bold;
            }
            QTableWidget::item:selected {
                background-color: #2f354a;
                color: #ffffff;
            }
        """)
        layout.addWidget(self.table)
        
        # Bottom Actions
        bottom_row = QHBoxLayout()
        self.delete_btn = QPushButton("🗑️ Remove Word")
        self.delete_btn.clicked.connect(self._delete_selected)
        self.export_btn = QPushButton("💾 Export to CSV / Anki")
        self.export_btn.clicked.connect(self._export_csv)
        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.accept)
        
        for btn in (self.delete_btn, self.export_btn, self.close_btn):
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #24283b;
                    color: #cbd5e1;
                    border: 1px solid #3b4261;
                    border-radius: 6px;
                    padding: 6px 14px;
                    font-size: 12px;
                }
                QPushButton:hover {
                    background-color: #3b4261;
                    color: #ffffff;
                }
            """)
            
        bottom_row.addWidget(self.delete_btn)
        bottom_row.addWidget(self.export_btn)
        bottom_row.addStretch()
        bottom_row.addWidget(self.close_btn)
        layout.addLayout(bottom_row)

    def _load_words(self):
        self.all_words = get_all_vault_words()
        self._populate_table(self.all_words)

    def _populate_table(self, words):
        self.table.setRowCount(len(words))
        for row_idx, item in enumerate(words):
            word_item = QTableWidgetItem(item.get("word", "").capitalize())
            pos_item = QTableWidgetItem(item.get("part_of_speech", ""))
            def_item = QTableWidgetItem(item.get("definition", ""))
            ex_item = QTableWidgetItem(item.get("example", ""))
            date_item = QTableWidgetItem(str(item.get("saved_at", ""))[:10])
            
            self.table.setItem(row_idx, 0, word_item)
            self.table.setItem(row_idx, 1, pos_item)
            self.table.setItem(row_idx, 2, def_item)
            self.table.setItem(row_idx, 3, ex_item)
            self.table.setItem(row_idx, 4, date_item)

    def _filter_words(self, query: str):
        q = query.strip().lower()
        if not q:
            self._populate_table(self.all_words)
            return
        filtered = [w for w in self.all_words if q in w.get("word", "").lower() or q in w.get("definition", "").lower()]
        self._populate_table(filtered)

    def _delete_selected(self):
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            return
        row = selected_rows[0].row()
        word = self.table.item(row, 0).text().lower()
        if remove_from_vault(word):
            self._load_words()

    def _export_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export Vocabulary Bank", "vocabulary_deck.csv", "CSV Files (*.csv)")
        if not path:
            return
        try:
            with open(path, mode="w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Word", "Type", "Phonetic", "Definition", "Example", "Synonyms", "Antonyms"])
                for w in self.all_words:
                    writer.writerow([
                        w.get("word", ""),
                        w.get("part_of_speech", ""),
                        w.get("phonetic", ""),
                        w.get("definition", ""),
                        w.get("example", ""),
                        w.get("synonyms", ""),
                        w.get("antonyms", "")
                    ])
            QMessageBox.information(self, "Export Successful", f"Saved {len(self.all_words)} words to {path}!")
        except Exception as e:
            QMessageBox.critical(self, "Export Failed", f"Could not write file: {e}")
