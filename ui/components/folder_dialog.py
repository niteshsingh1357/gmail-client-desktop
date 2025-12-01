"""
Folder management dialogs
"""
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QLineEdit, QPushButton)
from PyQt5.QtCore import Qt


class CreateFolderDialog(QDialog):
    """Dialog for creating a new folder"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create Folder")
        self.setMinimumWidth(400)
        self.folder_name = None
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)
        
        label = QLabel("Enter folder name:")
        label.setStyleSheet("""
            QLabel {
                color: #cccccc;
                font-size: 14px;
                font-weight: 500;
            }
        """)
        layout.addWidget(label)
        
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Folder name")
        self.name_input.setFixedHeight(44)
        self.name_input.setStyleSheet("""
            QLineEdit {
                padding: 8px 12px;
                border: 1px solid #dadce0;
                border-radius: 4px;
                font-size: 14px;
                background-color: white;
                color: #202124;
            }
            QLineEdit:focus {
                border: 2px solid #1a73e8;
            }
        """)
        self.name_input.returnPressed.connect(self.accept)
        layout.addWidget(self.name_input)
        
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedHeight(48)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #f1f3f4;
                color: #202124;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 14px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #e8eaed;
            }
            QPushButton:pressed {
                background-color: #dadce0;
            }
        """)
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        create_btn = QPushButton("Create")
        create_btn.setFixedHeight(48)
        create_btn.setDefault(True)
        create_btn.setStyleSheet("""
            QPushButton {
                background-color: #1a73e8;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 14px;
                font-weight: 500;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #1765cc;
            }
            QPushButton:pressed {
                background-color: #1557b0;
            }
        """)
        create_btn.clicked.connect(self.on_create)
        button_layout.addWidget(create_btn)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
        
        # Focus on input
        self.name_input.setFocus()
    
    def on_create(self):
        """Handle create button click"""
        folder_name = self.name_input.text().strip()
        if not folder_name:
            return
        self.folder_name = folder_name
        self.accept()
    
    def get_folder_name(self) -> str:
        """Get the entered folder name"""
        return self.folder_name or ""


class RenameFolderDialog(QDialog):
    """Dialog for renaming a folder"""
    
    def __init__(self, current_name: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Rename Folder")
        self.setMinimumWidth(400)
        self.new_name = None
        self.current_name = current_name
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)
        
        label = QLabel("Enter new folder name:")
        label.setStyleSheet("""
            QLabel {
                color: #cccccc;
                font-size: 14px;
                font-weight: 500;
            }
        """)
        layout.addWidget(label)
        
        self.name_input = QLineEdit()
        self.name_input.setText(self.current_name)
        self.name_input.setPlaceholderText("Folder name")
        self.name_input.setFixedHeight(44)
        self.name_input.setStyleSheet("""
            QLineEdit {
                padding: 8px 12px;
                border: 1px solid #dadce0;
                border-radius: 4px;
                font-size: 14px;
                background-color: white;
                color: #202124;
            }
            QLineEdit:focus {
                border: 2px solid #1a73e8;
            }
        """)
        self.name_input.returnPressed.connect(self.accept)
        self.name_input.selectAll()
        layout.addWidget(self.name_input)
        
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedHeight(48)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #f1f3f4;
                color: #202124;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 14px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #e8eaed;
            }
            QPushButton:pressed {
                background-color: #dadce0;
            }
        """)
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        rename_btn = QPushButton("Rename")
        rename_btn.setFixedHeight(48)
        rename_btn.setDefault(True)
        rename_btn.setStyleSheet("""
            QPushButton {
                background-color: #1a73e8;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 14px;
                font-weight: 500;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #1765cc;
            }
            QPushButton:pressed {
                background-color: #1557b0;
            }
        """)
        rename_btn.clicked.connect(self.on_rename)
        button_layout.addWidget(rename_btn)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
        
        # Focus on input and select all
        self.name_input.setFocus()
        self.name_input.selectAll()
    
    def on_rename(self):
        """Handle rename button click"""
        new_name = self.name_input.text().strip()
        if not new_name:
            return
        if new_name == self.current_name:
            self.reject()
            return
        self.new_name = new_name
        self.accept()
    
    def get_new_name(self) -> str:
        """Get the entered new folder name"""
        return self.new_name or ""


class MoveEmailDialog(QDialog):
    """Dialog for moving an email to a different folder"""
    
    def __init__(self, folders: list, current_folder_id: int = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Move Email")
        self.setMinimumWidth(400)
        self.selected_folder_id = None
        self.folders = folders
        self.current_folder_id = current_folder_id
        self.setup_ui()
    
    def setup_ui(self):
        from PyQt5.QtWidgets import QComboBox
        
        layout = QVBoxLayout()
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)
        
        label = QLabel("Select destination folder:")
        label.setStyleSheet("""
            QLabel {
                color: #cccccc;
                font-size: 14px;
                font-weight: 500;
            }
        """)
        layout.addWidget(label)
        
        self.folder_combo = QComboBox()
        self.folder_combo.setFixedHeight(44)
        self.folder_combo.setStyleSheet("""
            QComboBox {
                padding: 8px 12px;
                border: 1px solid #dadce0;
                border-radius: 4px;
                font-size: 14px;
                background-color: white;
                color: #202124;
            }
            QComboBox:focus {
                border: 2px solid #1a73e8;
            }
            QComboBox::drop-down {
                border: none;
                width: 30px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 6px solid #5f6368;
                margin-right: 8px;
            }
            QComboBox QAbstractItemView {
                background-color: white;
                border: 1px solid #dadce0;
                border-radius: 4px;
                selection-background-color: #e8f0fe;
                selection-color: #202124;
            }
        """)
        
        # Add folders to combo box (exclude current folder)
        for folder in self.folders:
            if folder.id and folder.id != self.current_folder_id:
                self.folder_combo.addItem(folder.name, folder.id)
        
        layout.addWidget(self.folder_combo)
        
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedHeight(48)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #f1f3f4;
                color: #202124;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 14px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #e8eaed;
            }
            QPushButton:pressed {
                background-color: #dadce0;
            }
        """)
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        move_btn = QPushButton("Move")
        move_btn.setFixedHeight(48)
        move_btn.setDefault(True)
        move_btn.setStyleSheet("""
            QPushButton {
                background-color: #1a73e8;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 14px;
                font-weight: 500;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #1765cc;
            }
            QPushButton:pressed {
                background-color: #1557b0;
            }
        """)
        move_btn.clicked.connect(self.on_move)
        button_layout.addWidget(move_btn)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
    
    def on_move(self):
        """Handle move button click"""
        folder_id = self.folder_combo.currentData()
        if folder_id:
            self.selected_folder_id = folder_id
            self.accept()
    
    def get_selected_folder_id(self) -> int:
        """Get the selected folder ID"""
        return self.selected_folder_id

