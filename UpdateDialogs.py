"""
Update dialogs and GUI components for CaseBriefs application.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QComboBox, QCheckBox, QProgressBar, QTextEdit, QMessageBox,
    QGroupBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject
from PyQt6.QtGui import QFont
from typing import Optional

from UpdateManager import UpdateManager, UpdateChannel, UpdateStatus
from logger import StructuredLogger


class UpdateCheckWorker(QObject):
    """Worker for checking updates in a separate thread."""
    
    finished = pyqtSignal(str, str, str)  # status, version, error
    
    def __init__(self, update_manager: UpdateManager):
        super().__init__()
        self.update_manager = update_manager
    
    def run(self):
        """Check for updates."""
        try:
            status, version, error = self.update_manager.check_for_updates()
            self.finished.emit(status.value, version or "", error or "")
        except Exception as e:
            self.finished.emit(UpdateStatus.ERROR.value, "", str(e))


class UpdateDialog(QDialog):
    """Dialog for checking and managing updates."""
    
    def __init__(self, update_manager: UpdateManager, parent=None):
        super().__init__(parent)
        self.update_manager = update_manager
        self.logger = update_manager.logger
        
        self.setWindowTitle("Check for Updates")
        self.setFixedSize(500, 400)
        self.setModal(True)
        
        self.setup_ui()
        
        # Worker thread for update checking
        self.worker_thread: Optional[QThread] = None
        self.worker: Optional[UpdateCheckWorker] = None
    
    def setup_ui(self):
        """Set up the user interface."""
        layout = QVBoxLayout(self)
        
        # Current version info
        version_group = QGroupBox("Current Version")
        version_layout = QVBoxLayout(version_group)
        
        current_version_label = QLabel(f"Version: {self.update_manager.current_version}")
        current_version_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        version_layout.addWidget(current_version_label)
        
        channel_layout = QHBoxLayout()
        channel_layout.addWidget(QLabel("Update Channel:"))
        
        self.channel_combo = QComboBox()
        for channel in UpdateChannel:
            self.channel_combo.addItem(channel.value.capitalize(), channel)
        
        # Set current channel
        current_index = 0
        for i in range(self.channel_combo.count()):
            if self.channel_combo.itemData(i) == self.update_manager.channel:
                current_index = i
                break
        self.channel_combo.setCurrentIndex(current_index)
        self.channel_combo.currentTextChanged.connect(self.on_channel_changed)
        
        channel_layout.addWidget(self.channel_combo)
        channel_layout.addStretch()
        version_layout.addLayout(channel_layout)
        
        layout.addWidget(version_group)
        
        # Update status
        status_group = QGroupBox("Update Status")
        status_layout = QVBoxLayout(status_group)
        
        self.status_label = QLabel("Click 'Check for Updates' to check for new versions")
        status_layout.addWidget(self.status_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        status_layout.addWidget(self.progress_bar)
        
        layout.addWidget(status_group)
        
        # Update details (initially hidden)
        self.details_group = QGroupBox("Update Details")
        details_layout = QVBoxLayout(self.details_group)
        
        self.details_text = QTextEdit()
        self.details_text.setMaximumHeight(100)
        self.details_text.setReadOnly(True)
        details_layout.addWidget(self.details_text)
        
        self.details_group.setVisible(False)
        layout.addWidget(self.details_group)
        
        # Auto-update settings
        auto_group = QGroupBox("Auto-Update Settings")
        auto_layout = QVBoxLayout(auto_group)
        
        self.auto_check_checkbox = QCheckBox("Automatically check for updates")
        self.auto_check_checkbox.setChecked(self.update_manager.global_vars.auto_check_updates)
        self.auto_check_checkbox.toggled.connect(self.on_auto_check_changed)
        auto_layout.addWidget(self.auto_check_checkbox)
        
        self.auto_install_checkbox = QCheckBox("Automatically install updates")
        self.auto_install_checkbox.setChecked(self.update_manager.global_vars.auto_install_updates)
        self.auto_install_checkbox.toggled.connect(self.on_auto_install_changed)
        auto_layout.addWidget(self.auto_install_checkbox)
        
        layout.addWidget(auto_group)
        
        layout.addStretch()
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.check_button = QPushButton("Check for Updates")
        self.check_button.clicked.connect(self.check_for_updates)
        button_layout.addWidget(self.check_button)
        
        self.download_button = QPushButton("Download Update")
        self.download_button.setVisible(False)
        self.download_button.clicked.connect(self.download_update)
        button_layout.addWidget(self.download_button)
        
        button_layout.addStretch()
        
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        button_layout.addWidget(close_button)
        
        layout.addLayout(button_layout)
    
    def on_channel_changed(self, text: str):
        """Handle channel selection change."""
        channel_value = text.lower()
        for channel in UpdateChannel:
            if channel.value == channel_value:
                self.update_manager.channel = channel
                self.update_manager.global_vars.update_channel = channel_value
                self.logger.info(f"Changed update channel to: {channel_value}")
                break
    
    def on_auto_check_changed(self, checked: bool):
        """Handle auto-check setting change."""
        self.update_manager.global_vars.auto_check_updates = checked
        self.logger.info(f"Auto-check updates: {checked}")
    
    def on_auto_install_changed(self, checked: bool):
        """Handle auto-install setting change."""
        self.update_manager.global_vars.auto_install_updates = checked
        self.logger.info(f"Auto-install updates: {checked}")
    
    def check_for_updates(self):
        """Start checking for updates."""
        self.check_button.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate progress
        self.status_label.setText("Checking for updates...")
        
        # Start worker thread
        self.worker_thread = QThread()
        self.worker = UpdateCheckWorker(self.update_manager)
        self.worker.moveToThread(self.worker_thread)
        
        self.worker_thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.on_update_check_finished)
        self.worker_thread.finished.connect(self.worker_thread.deleteLater)
        
        self.worker_thread.start()
    
    def on_update_check_finished(self, status: str, version: str, error: str):
        """Handle update check completion."""
        self.check_button.setEnabled(True)
        self.progress_bar.setVisible(False)
        
        if status == UpdateStatus.ERROR.value:
            self.status_label.setText(f"Error checking for updates: {error}")
            QMessageBox.warning(self, "Update Check Failed", f"Failed to check for updates:\n{error}")
        
        elif status == UpdateStatus.UP_TO_DATE.value:
            self.status_label.setText("Your application is up to date!")
            self.details_group.setVisible(False)
            self.download_button.setVisible(False)
        
        elif status == UpdateStatus.UPDATE_AVAILABLE.value:
            self.status_label.setText(f"Update available: Version {version}")
            self.details_text.setText(f"A new version ({version}) is available for download.\n\n"
                                    f"Current version: {self.update_manager.current_version}\n"
                                    f"Channel: {self.update_manager.channel.value}")
            self.details_group.setVisible(True)
            self.download_button.setVisible(True)
        
        # Clean up worker thread
        if self.worker_thread:
            self.worker_thread.quit()
            self.worker_thread.wait()
            self.worker_thread = None
            self.worker = None
    
    def download_update(self):
        """Handle update download."""
        # For MVP, show a message about manual download
        QMessageBox.information(
            self, 
            "Download Update",
            "Please visit the GitHub releases page to download the latest version:\n\n"
            f"https://github.com/{self.update_manager.repository_owner}/"
            f"{self.update_manager.repository_name}/releases\n\n"
            "Automatic updates will be available in a future version."
        )


class UpdateNotificationDialog(QDialog):
    """Simple notification dialog for available updates."""
    
    def __init__(self, version: str, channel: str, parent=None):
        super().__init__(parent)
        self.version = version
        self.channel = channel
        
        self.setWindowTitle("Update Available")
        self.setFixedSize(350, 150)
        self.setModal(True)
        
        self.setup_ui()
    
    def setup_ui(self):
        """Set up the user interface."""
        layout = QVBoxLayout(self)
        
        # Icon and message
        message = QLabel(f"A new version ({self.version}) is available!")
        message.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        layout.addWidget(message)
        
        channel_label = QLabel(f"Channel: {self.channel}")
        layout.addWidget(channel_label)
        
        layout.addStretch()
        
        # Buttons
        button_layout = QHBoxLayout()
        
        update_button = QPushButton("Check Updates")
        update_button.clicked.connect(self.accept)
        button_layout.addWidget(update_button)
        
        later_button = QPushButton("Later")
        later_button.clicked.connect(self.reject)
        button_layout.addWidget(later_button)
        
        layout.addLayout(button_layout)