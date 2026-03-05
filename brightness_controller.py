"""
Brightness Controller - A modern GUI application for controlling screen brightness
with customizable keyboard shortcuts.
"""

import sys
import json
import os
import winreg
import urllib.request
import urllib.error
import tempfile
import subprocess
import webbrowser
from pathlib import Path


def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller bundle"""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative_path)


DEF_AUTOSTART_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
DEF_AUTOSTART_NAME = "BrightnessController"


def get_autostart_command():
    """Return the command string to register for autostart"""
    if getattr(sys, 'frozen', False):
        return f'"{sys.executable}"'
    return f'"{sys.executable}" "{os.path.abspath(sys.argv[0])}"'


CURRENT_VERSION = "v0.0.1"
GITHUB_REPO = "bibekchandsah/brightness"
GITHUB_RELEASES_PAGE = f"https://github.com/{GITHUB_REPO}/releases/latest"


def parse_version(tag):
    """Parse a version tag like 'v1.2.3' into a comparable tuple of ints."""
    try:
        return tuple(int(x) for x in tag.lstrip('v').strip().split('.'))
    except ValueError:
        return (0,)
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                              QHBoxLayout, QPushButton, QLabel, QSlider,
                              QTableWidget, QTableWidgetItem, QSystemTrayIcon,
                              QMenu, QMessageBox, QLineEdit, QDialog, QDialogButtonBox,
                              QGroupBox, QProgressDialog)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QIcon, QKeySequence, QAction, QColor, QPainter, QPixmap, QImage
from PIL import Image, ImageFilter
import screen_brightness_control as sbc
from pynput import keyboard
import ctypes


# Windows API for checking modifier key state in real-time
def is_key_pressed(vk_code):
    """Check if a key is currently pressed using Windows API"""
    return ctypes.windll.user32.GetAsyncKeyState(vk_code) & 0x8000 != 0

VK_LCONTROL = 0xA2
VK_RCONTROL = 0xA3
VK_LSHIFT = 0xA0
VK_RSHIFT = 0xA1
VK_LALT = 0xA4
VK_RALT = 0xA5


class BlurOverlay(QWidget):
    """Fullscreen Gaussian blur overlay window"""
    
    def __init__(self):
        super().__init__()
        self.blur_level = 50  # 0-100, maps to blur radius
        self.blurred_pixmap = None
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.active = False
    
    def set_blur_level(self, level):
        """Set the blur level (0-100)"""
        self.blur_level = max(0, min(100, level))
    
    def paintEvent(self, event):
        """Paint the blurred screenshot"""
        if self.blurred_pixmap:
            painter = QPainter(self)
            painter.drawPixmap(0, 0, self.blurred_pixmap)
            painter.end()
    
    def capture_and_blur(self):
        """Capture the screen and apply Gaussian blur"""
        screens = QApplication.screens()
        if not screens:
            return
        
        # Get combined geometry of all screens
        combined = screens[0].geometry()
        for screen in screens[1:]:
            combined = combined.united(screen.geometry())
        self.setGeometry(combined)
        
        # Capture the entire virtual desktop
        primary = QApplication.primaryScreen()
        screenshot = primary.grabWindow(
            0, combined.x(), combined.y(),
            combined.width(), combined.height()
        )
        
        # Convert QPixmap -> QImage -> PIL Image
        qimage = screenshot.toImage().convertToFormat(QImage.Format.Format_RGBA8888)
        width = qimage.width()
        height = qimage.height()
        ptr = qimage.bits()
        ptr.setsize(height * width * 4)
        pil_image = Image.frombuffer('RGBA', (width, height), bytes(ptr), 'raw', 'RGBA', 0, 1)
        
        # Apply Gaussian blur - radius scales with blur_level (0-100 -> 0-30 px)
        blur_radius = self.blur_level * 0.3
        blurred = pil_image.filter(ImageFilter.GaussianBlur(radius=blur_radius))
        
        # Convert back: PIL Image -> QImage -> QPixmap
        data = blurred.tobytes('raw', 'RGBA')
        qimg = QImage(data, width, height, width * 4, QImage.Format.Format_RGBA8888)
        # Must keep a reference to data so it isn't garbage collected
        self._image_data = data
        self.blurred_pixmap = QPixmap.fromImage(qimg)
    
    def toggle(self):
        """Toggle the blur overlay on/off"""
        if self.active:
            self.hide()
            self.active = False
            self.blurred_pixmap = None
            self._image_data = None
        else:
            self.capture_and_blur()
            self.show()
            self.active = True


class HotkeyListener(QThread):
    """Thread for listening to global hotkeys"""
    brightness_change = pyqtSignal(int)
    blur_toggle = pyqtSignal()
    keys_detected = pyqtSignal(str)  # Signal to show detected keys
    
    def __init__(self, shortcuts):
        super().__init__()
        self.shortcuts = shortcuts
        self.listener = None
        self.running = False
        
    def run(self):
        """Start listening for hotkeys"""
        self.running = True
        with keyboard.Listener(
            on_press=self.on_press,
            on_release=self.on_release) as listener:
            self.listener = listener
            listener.join()
    
    def on_press(self, key):
        """Handle key press events"""
        try:
            self.check_shortcuts(key)
        except Exception as e:
            print(f"Error on key press: {e}")
    
    def on_release(self, key):
        """Handle key release events"""
        pass
    
    def check_shortcuts(self, pressed_key):
        """Check if current key combination matches any shortcut"""
        # Query modifier state directly from OS - never gets stale
        has_ctrl = is_key_pressed(VK_LCONTROL) or is_key_pressed(VK_RCONTROL)
        has_shift = is_key_pressed(VK_LSHIFT) or is_key_pressed(VK_RSHIFT)
        has_alt = is_key_pressed(VK_LALT) or is_key_pressed(VK_RALT)
        
        # Determine the main key from the pressed key
        main_key = self._get_main_key(pressed_key)
        
        if not main_key:
            return
        
        # Build the combo
        parts = []
        if has_ctrl:
            parts.append('ctrl')
        if has_shift:
            parts.append('shift')
        if has_alt:
            parts.append('alt')
        parts.append(main_key)
        
        key_combo = '+'.join(parts)
        
        # Emit signal to show detected keys
        self.keys_detected.emit(key_combo)
        print(f"Detected key combo: {key_combo}")
            
        # Check blur toggle shortcut first
        blur_shortcut = self.shortcuts.get('blur_toggle', 'ctrl+shift+b')
        if self.normalize_shortcut(key_combo) == self.normalize_shortcut(blur_shortcut):
            print("Match found! Toggling blur overlay")
            self.blur_toggle.emit()
            return
        
        for brightness_value, shortcut in self.shortcuts.items():
            if brightness_value in ('blur_toggle', 'blur_level'):
                continue
            normalized_combo = self.normalize_shortcut(key_combo)
            normalized_shortcut = self.normalize_shortcut(shortcut)
            if normalized_combo == normalized_shortcut:
                print(f"Match found! Setting brightness to {brightness_value}%")
                self.brightness_change.emit(int(brightness_value))
                break
    
    def normalize_shortcut(self, shortcut):
        """Normalize a shortcut string for comparison"""
        parts = [p.strip().lower() for p in shortcut.split('+')]
        parts.sort()
        return '+'.join(parts)
    
    def _get_main_key(self, key):
        """Extract the main (non-modifier) key from a pynput key event"""
        if isinstance(key, keyboard.Key):
            # Skip pure modifier keys
            if key in (keyboard.Key.ctrl_l, keyboard.Key.ctrl_r,
                       keyboard.Key.shift_l, keyboard.Key.shift_r,
                       keyboard.Key.alt_l, keyboard.Key.alt_r):
                return None
            # Numpad keys with Shift held may appear as navigation keys
            numpad_map = {
                keyboard.Key.insert: '0',
                keyboard.Key.end: '1',
                keyboard.Key.down: '2',
                keyboard.Key.page_down: '3',
                keyboard.Key.left: '4',
                keyboard.Key.right: '6',
                keyboard.Key.home: '7',
                keyboard.Key.up: '8',
                keyboard.Key.page_up: '9',
            }
            return numpad_map.get(key, None)
        else:
            # Use virtual key code for reliable detection
            vk = getattr(key, 'vk', None)
            if vk is not None:
                if 0x30 <= vk <= 0x39:
                    return str(vk - 0x30)
                elif 0x41 <= vk <= 0x5A:
                    return chr(vk).lower()
                elif 0x60 <= vk <= 0x69:
                    return str(vk - 0x60)
            elif hasattr(key, 'char') and key.char:
                return key.char.lower()
        return None
    
    def update_shortcuts(self, shortcuts):
        """Update shortcuts dictionary"""
        self.shortcuts = shortcuts
    
    def stop(self):
        """Stop the listener"""
        self.running = False
        if self.listener:
            self.listener.stop()


class UpdateChecker(QThread):
    """Background thread that checks GitHub for a newer release."""
    update_available = pyqtSignal(str, str, str)  # tag, download_url, release_url
    no_update = pyqtSignal()
    check_error = pyqtSignal(str)

    def run(self):
        try:
            # Follow the redirect on the releases/latest page to get the tag.
            # This avoids the GitHub REST API entirely and its 60 req/hr rate limit.
            req = urllib.request.Request(
                GITHUB_RELEASES_PAGE,
                headers={"User-Agent": "BrightnessController-Updater"}
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                final_url = resp.url  # e.g. .../releases/tag/v1.2.3

            # Extract tag from the final URL after the redirect
            import re
            m = re.search(r'/releases/tag/([^/?#]+)', final_url)
            if not m:
                self.no_update.emit()
                return

            tag = m.group(1).strip()
            release_url = f"https://github.com/{GITHUB_REPO}/releases/tag/{tag}"

            if parse_version(tag) > parse_version(CURRENT_VERSION):
                # Construct asset download URL directly (no API needed)
                download_url = (
                    f"https://github.com/{GITHUB_REPO}/releases/download"
                    f"/{tag}/BrightnessController.exe"
                )
                self.update_available.emit(tag, download_url, release_url)
            else:
                self.no_update.emit()
        except Exception as exc:
            self.check_error.emit(str(exc))


class UpdateDownloader(QThread):
    """Background thread that downloads a release asset."""
    progress = pyqtSignal(int)   # 0-100
    finished = pyqtSignal(str)   # path to downloaded temp file
    error = pyqtSignal(str)

    def __init__(self, url):
        super().__init__()
        self.url = url

    def run(self):
        try:
            req = urllib.request.Request(
                self.url,
                headers={"User-Agent": "BrightnessController-Updater"}
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                total = int(resp.headers.get("Content-Length", 0))
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".exe")
                downloaded = 0
                while True:
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    tmp.write(chunk)
                    downloaded += len(chunk)
                    if total > 0:
                        self.progress.emit(int(downloaded * 100 / total))
                tmp.close()
            self.finished.emit(tmp.name)
        except Exception as exc:
            self.error.emit(str(exc))


class ShortcutEditDialog(QDialog):
    """Dialog for editing keyboard shortcuts"""
    
    def __init__(self, parent=None, brightness_value="", current_shortcut=""):
        super().__init__(parent)
        self.setWindowTitle(f"Edit Shortcut for {brightness_value}% Brightness")
        self.setModal(True)
        self.captured_keys = set()
        
        layout = QVBoxLayout()
        
        # Instructions
        label = QLabel("Press the key combination you want to use:")
        layout.addWidget(label)
        
        # Shortcut display
        self.shortcut_edit = QLineEdit()
        self.shortcut_edit.setReadOnly(True)
        self.shortcut_edit.setText(current_shortcut)
        self.shortcut_edit.setPlaceholderText("Press keys...")
        layout.addWidget(self.shortcut_edit)
        
        # Clear button
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self.clear_shortcut)
        layout.addWidget(clear_btn)
        
        # Dialog buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | 
            QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
        self.setLayout(layout)
        
    def keyPressEvent(self, event):
        """Capture key press events"""
        key = event.key()
        modifiers = event.modifiers()
        
        keys = []
        if modifiers & Qt.KeyboardModifier.ControlModifier:
            keys.append("ctrl")
        if modifiers & Qt.KeyboardModifier.ShiftModifier:
            keys.append("shift")
        if modifiers & Qt.KeyboardModifier.AltModifier:
            keys.append("alt")
        
        # Add the actual key - handle special cases
        key_text = event.text().lower() if event.text() else ""
        
        # If text is empty, try to get from key code
        if not key_text:
            key_name = QKeySequence(key).toString().lower()
            # Remove any existing modifiers from the key name
            key_name = key_name.replace("ctrl+", "").replace("shift+", "").replace("alt+", "")
            if key_name and key_name not in ['ctrl', 'shift', 'alt']:
                key_text = key_name
        
        # Add the main key if we have one
        if key_text and key_text not in ['ctrl', 'shift', 'alt']:
            keys.append(key_text)
        
        if len(keys) > 1:  # At least one modifier + one key
            self.shortcut_edit.setText("+".join(keys))
    
    def clear_shortcut(self):
        """Clear the shortcut"""
        self.shortcut_edit.clear()
    
    def get_shortcut(self):
        """Get the captured shortcut"""
        return self.shortcut_edit.text()


class BrightnessController(QMainWindow):
    """Main application window"""
    
    def __init__(self):
        super().__init__()
        self.config_file = Path("brightness_config.json")
        self.shortcuts = self.load_config()
        self.hotkey_listener = None
        
        # Create blur overlay
        self.blur_overlay = BlurOverlay()
        blur_level = int(self.shortcuts.get('blur_level', 50))
        self.blur_overlay.set_blur_level(blur_level)
        
        self.init_ui()
        self.start_hotkey_listener()
        # Check for updates silently 5 seconds after startup
        QTimer.singleShot(5000, lambda: self.check_for_updates(silent=True))

    def init_ui(self):
        """Initialize the user interface"""
        self.setWindowTitle("Brightness Controller")
        self.setGeometry(100, 100, 600, 700)
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # Title
        title = QLabel("Screen Brightness Controller")
        title.setStyleSheet("font-size: 20px; font-weight: bold; padding: 10px;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title)
        
        # Current brightness display
        brightness_layout = QHBoxLayout()
        brightness_label = QLabel("Current Brightness:")
        brightness_label.setStyleSheet("font-size: 14px;")
        brightness_layout.addWidget(brightness_label)
        
        try:
            current = sbc.get_brightness()[0]
        except:
            current = 50
        
        self.brightness_value_label = QLabel(f"{current}%")
        self.brightness_value_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        brightness_layout.addWidget(self.brightness_value_label)
        brightness_layout.addStretch()
        main_layout.addLayout(brightness_layout)
        
        # Brightness slider
        slider_layout = QHBoxLayout()
        slider_label = QLabel("Manual Control:")
        slider_layout.addWidget(slider_label)
        
        self.brightness_slider = QSlider(Qt.Orientation.Horizontal)
        self.brightness_slider.setMinimum(0)
        self.brightness_slider.setMaximum(100)
        self.brightness_slider.setValue(current)
        self.brightness_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.brightness_slider.setTickInterval(10)
        self.brightness_slider.valueChanged.connect(self.slider_changed)
        slider_layout.addWidget(self.brightness_slider)
        main_layout.addLayout(slider_layout)
        
        # Shortcuts table
        shortcuts_label = QLabel("Keyboard Shortcuts:")
        shortcuts_label.setStyleSheet("font-size: 14px; font-weight: bold; padding-top: 20px;")
        main_layout.addWidget(shortcuts_label)
        
        self.shortcuts_table = QTableWidget()
        self.shortcuts_table.setColumnCount(3)
        self.shortcuts_table.setHorizontalHeaderLabels(["Brightness", "Shortcut", "Action"])
        self.shortcuts_table.horizontalHeader().setStretchLastSection(False)
        self.shortcuts_table.setColumnWidth(0, 100)
        self.shortcuts_table.setColumnWidth(1, 250)
        self.shortcuts_table.setColumnWidth(2, 200)
        
        self.populate_shortcuts_table()
        main_layout.addWidget(self.shortcuts_table)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        reset_btn = QPushButton("Reset to Defaults")
        reset_btn.clicked.connect(self.reset_defaults)
        button_layout.addWidget(reset_btn)
        
        save_btn = QPushButton("Save Configuration")
        save_btn.clicked.connect(self.save_config)
        button_layout.addWidget(save_btn)
        
        button_layout.addStretch()
        
        minimize_btn = QPushButton("Minimize to Tray")
        minimize_btn.clicked.connect(self.hide)
        button_layout.addWidget(minimize_btn)
        
        main_layout.addLayout(button_layout)
        
        # Blur settings section
        blur_group = QGroupBox("Blur Overlay Settings")
        blur_layout = QVBoxLayout()
        
        # Blur shortcut row
        blur_shortcut_layout = QHBoxLayout()
        blur_shortcut_label = QLabel("Toggle Shortcut:")
        blur_shortcut_layout.addWidget(blur_shortcut_label)
        
        self.blur_shortcut_display = QLineEdit()
        self.blur_shortcut_display.setReadOnly(True)
        self.blur_shortcut_display.setText(self.shortcuts.get('blur_toggle', 'ctrl+shift+b'))
        blur_shortcut_layout.addWidget(self.blur_shortcut_display)
        
        blur_edit_btn = QPushButton("Edit")
        blur_edit_btn.clicked.connect(self.edit_blur_shortcut)
        blur_shortcut_layout.addWidget(blur_edit_btn)
        blur_layout.addLayout(blur_shortcut_layout)
        
        # Blur level row
        blur_level_layout = QHBoxLayout()
        blur_level_label = QLabel("Blur Level:")
        blur_level_layout.addWidget(blur_level_label)
        
        self.blur_slider = QSlider(Qt.Orientation.Horizontal)
        self.blur_slider.setMinimum(0)
        self.blur_slider.setMaximum(100)
        self.blur_slider.setValue(int(self.shortcuts.get('blur_level', 50)))
        self.blur_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.blur_slider.setTickInterval(10)
        self.blur_slider.valueChanged.connect(self.blur_level_changed)
        blur_level_layout.addWidget(self.blur_slider)
        
        self.blur_level_label = QLabel(f"{self.blur_slider.value()}%")
        self.blur_level_label.setStyleSheet("font-weight: bold; min-width: 40px;")
        blur_level_layout.addWidget(self.blur_level_label)
        blur_layout.addLayout(blur_level_layout)
        
        # Toggle button
        self.blur_toggle_btn = QPushButton("Toggle Blur Overlay")
        self.blur_toggle_btn.clicked.connect(self.toggle_blur)
        blur_layout.addWidget(self.blur_toggle_btn)
        
        blur_group.setLayout(blur_layout)
        main_layout.addWidget(blur_group)
        
        # Debug info label
        debug_label = QLabel("Hotkey Debugger:")
        debug_label.setStyleSheet("font-size: 12px; font-weight: bold; padding-top: 10px;")
        main_layout.addWidget(debug_label)
        
        self.debug_keys_label = QLabel("Press any hotkey to see it here...")
        self.debug_keys_label.setStyleSheet("background-color: #f0f0f0; padding: 10px; border-radius: 5px; font-family: monospace;")
        main_layout.addWidget(self.debug_keys_label)
        
        # System tray
        self.setup_system_tray()
        
        # Status label
        self.status_label = QLabel("Hotkeys are active")
        self.status_label.setStyleSheet("color: green; padding: 5px;")
        main_layout.addWidget(self.status_label)
        
    def setup_system_tray(self):
        """Setup system tray icon"""
        self.tray_icon = QSystemTrayIcon(self)
        
        # Create tray menu
        tray_menu = QMenu()
        
        show_action = QAction("Show", self)
        show_action.triggered.connect(self.show)
        tray_menu.addAction(show_action)
        
        tray_menu.addSeparator()
        
        self.autostart_action = QAction("Start on Startup", self)
        self.autostart_action.setCheckable(True)
        self.autostart_action.setChecked(self.is_autostart_enabled())
        self.autostart_action.triggered.connect(self.toggle_autostart)
        tray_menu.addAction(self.autostart_action)

        tray_menu.addSeparator()

        check_update_action = QAction("Check for Updates", self)
        check_update_action.triggered.connect(lambda: self.check_for_updates(silent=False))
        tray_menu.addAction(check_update_action)

        self.update_tray_action = QAction("", self)
        self.update_tray_action.setVisible(False)
        self.update_tray_action.triggered.connect(self.download_update)
        tray_menu.addAction(self.update_tray_action)

        tray_menu.addSeparator()

        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.quit_application)
        tray_menu.addAction(quit_action)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.tray_icon_activated)
        
        # Set icon
        icon_path = resource_path("sun.png")
        icon = QIcon(str(icon_path))
        self.tray_icon.setIcon(icon)
        self.setWindowIcon(icon)
        self.tray_icon.setToolTip("Brightness Controller")
        self.tray_icon.show()
    
    def is_autostart_enabled(self):
        """Check if autostart is registered in the Windows registry"""
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, DEF_AUTOSTART_KEY, 0, winreg.KEY_READ)
            try:
                winreg.QueryValueEx(key, DEF_AUTOSTART_NAME)
                return True
            except FileNotFoundError:
                return False
            finally:
                winreg.CloseKey(key)
        except Exception:
            return False

    def toggle_autostart(self, checked):
        """Enable or disable autostart based on the tray menu checkbox"""
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, DEF_AUTOSTART_KEY, 0, winreg.KEY_SET_VALUE)
            try:
                if checked:
                    winreg.SetValueEx(key, DEF_AUTOSTART_NAME, 0, winreg.REG_SZ, get_autostart_command())
                else:
                    try:
                        winreg.DeleteValue(key, DEF_AUTOSTART_NAME)
                    except FileNotFoundError:
                        pass
            finally:
                winreg.CloseKey(key)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to update autostart setting: {str(e)}")
            # Revert checkbox state on failure
            self.autostart_action.setChecked(not checked)

    def tray_icon_activated(self, reason):
        """Handle tray icon activation"""
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            if self.isVisible():
                self.hide()
            else:
                self.show()
                self.activateWindow()
    
    def load_config(self):
        """Load configuration from file"""
        default_shortcuts = {
            "0": "ctrl+shift+0",
            "10": "ctrl+shift+1",
            "20": "ctrl+shift+2",
            "30": "ctrl+shift+3",
            "40": "ctrl+shift+4",
            "50": "ctrl+shift+5",
            "60": "ctrl+shift+6",
            "70": "ctrl+shift+7",
            "80": "ctrl+shift+8",
            "90": "ctrl+shift+9",
            "100": "ctrl+shift+f",
            "blur_toggle": "ctrl+shift+b",
            "blur_level": "50"
        }
        
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    return json.load(f)
            except:
                return default_shortcuts
        return default_shortcuts
    
    def save_config(self):
        """Save configuration to file"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.shortcuts, f, indent=4)
            QMessageBox.information(self, "Success", "Configuration saved successfully!")
            
            # Restart hotkey listener with new shortcuts
            self.restart_hotkey_listener()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save configuration: {str(e)}")
    
    def _save_config_silent(self):
        """Save configuration to file without showing a message"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.shortcuts, f, indent=4)
        except Exception:
            pass
    
    def reset_defaults(self):
        """Reset shortcuts to default values"""
        reply = QMessageBox.question(
            self, "Confirm Reset",
            "Are you sure you want to reset all shortcuts to defaults?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.shortcuts = {
                "0": "ctrl+shift+0",
                "10": "ctrl+shift+1",
                "20": "ctrl+shift+2",
                "30": "ctrl+shift+3",
                "40": "ctrl+shift+4",
                "50": "ctrl+shift+5",
                "60": "ctrl+shift+6",
                "70": "ctrl+shift+7",
                "80": "ctrl+shift+8",
                "90": "ctrl+shift+9",
                "100": "ctrl+shift+f",
                "blur_toggle": "ctrl+shift+b",
                "blur_level": "50"
            }
            self.populate_shortcuts_table()
            self.blur_shortcut_display.setText("ctrl+shift+b")
            self.blur_slider.setValue(50)
            self.blur_overlay.set_blur_level(50)
            self.save_config()
    
    def populate_shortcuts_table(self):
        """Populate the shortcuts table"""
        brightness_items = {k: v for k, v in self.shortcuts.items()
                           if k not in ('blur_toggle', 'blur_level')}
        self.shortcuts_table.setRowCount(len(brightness_items))
        
        sorted_items = sorted(brightness_items.items(), key=lambda x: int(x[0]))
        
        for row, (brightness, shortcut) in enumerate(sorted_items):
            # Brightness column
            brightness_item = QTableWidgetItem(f"{brightness}%")
            brightness_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.shortcuts_table.setItem(row, 0, brightness_item)
            
            # Shortcut column
            shortcut_item = QTableWidgetItem(shortcut)
            shortcut_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.shortcuts_table.setItem(row, 1, shortcut_item)
            
            # Action column
            edit_btn = QPushButton("Edit")
            edit_btn.clicked.connect(lambda checked, b=brightness: self.edit_shortcut(b))
            self.shortcuts_table.setCellWidget(row, 2, edit_btn)
    
    def edit_shortcut(self, brightness_value):
        """Open dialog to edit a shortcut"""
        current_shortcut = self.shortcuts.get(brightness_value, "")
        dialog = ShortcutEditDialog(self, brightness_value, current_shortcut)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_shortcut = dialog.get_shortcut()
            if new_shortcut:
                self.shortcuts[brightness_value] = new_shortcut
                self.populate_shortcuts_table()
    
    def slider_changed(self, value):
        """Handle brightness slider change"""
        self.set_brightness(value)
    
    def set_brightness(self, value):
        """Set screen brightness"""
        try:
            sbc.set_brightness(value)
            self.brightness_value_label.setText(f"{value}%")
            self.brightness_slider.setValue(value)
            self.status_label.setText(f"Brightness set to {value}%")
            self.status_label.setStyleSheet("color: green; padding: 5px;")
        except Exception as e:
            self.status_label.setText(f"Error: {str(e)}")
            self.status_label.setStyleSheet("color: red; padding: 5px;")
    
    def toggle_blur(self):
        """Toggle the blur overlay"""
        self.blur_overlay.toggle()
        state = "ON" if self.blur_overlay.active else "OFF"
        self.status_label.setText(f"Blur overlay {state}")
        self.status_label.setStyleSheet("color: green; padding: 5px;")
    
    def blur_level_changed(self, value):
        """Handle blur level slider change"""
        self.blur_level_label.setText(f"{value}%")
        self.blur_overlay.set_blur_level(value)
        self.shortcuts['blur_level'] = str(value)
        self._save_config_silent()
    
    def edit_blur_shortcut(self):
        """Edit the blur toggle shortcut"""
        current = self.shortcuts.get('blur_toggle', 'ctrl+shift+b')
        dialog = ShortcutEditDialog(self, "Blur Toggle", current)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_shortcut = dialog.get_shortcut()
            if new_shortcut:
                self.shortcuts['blur_toggle'] = new_shortcut
                self.blur_shortcut_display.setText(new_shortcut)
    
    def start_hotkey_listener(self):
        """Start the hotkey listener thread"""
        self.hotkey_listener = HotkeyListener(self.shortcuts)
        self.hotkey_listener.brightness_change.connect(self.set_brightness)
        self.hotkey_listener.blur_toggle.connect(self.toggle_blur)
        self.hotkey_listener.keys_detected.connect(self.update_debug_keys)
        self.hotkey_listener.start()
    
    def update_debug_keys(self, keys):
        """Update the debug label with detected keys"""
        self.debug_keys_label.setText(f"Detected: {keys}")
        self.debug_keys_label.setStyleSheet("background-color: #ffffcc; padding: 10px; border-radius: 5px; font-family: monospace;")
    
    def restart_hotkey_listener(self):
        """Restart the hotkey listener with updated shortcuts"""
        if self.hotkey_listener:
            self.hotkey_listener.stop()
            self.hotkey_listener.wait()
        self.start_hotkey_listener()
    
    def closeEvent(self, event):
        """Handle window close event"""
        event.ignore()
        self.hide()
        self.tray_icon.showMessage(
            "Brightness Controller",
            "Application minimized to tray. Hotkeys are still active.",
            QSystemTrayIcon.MessageIcon.Information,
            2000
        )
    
    def quit_application(self):
        """Quit the application"""
        if self.hotkey_listener:
            self.hotkey_listener.stop()
            self.hotkey_listener.wait()
        
        if self.blur_overlay.active:
            self.blur_overlay.hide()
        
        QApplication.quit()

    def check_for_updates(self, silent=True):
        """Start a background check for a newer GitHub release."""
        self._update_checker = UpdateChecker()
        self._update_checker.update_available.connect(self.on_update_available)
        if not silent:
            self._update_checker.no_update.connect(self._on_no_update)
            self._update_checker.check_error.connect(self._on_update_check_error)
        self._update_checker.start()

    def on_update_available(self, tag, download_url, release_url):
        """Called when a newer version exists on GitHub."""
        self._pending_update_tag = tag
        self._pending_update_download_url = download_url
        self._pending_update_release_url = release_url

        self.update_tray_action.setText(f"Update Available: {tag}")
        self.update_tray_action.setVisible(True)

        self.tray_icon.showMessage(
            "Brightness Controller \u2014 Update Available",
            f"Version {tag} is available. Right-click the tray icon to update.",
            QSystemTrayIcon.MessageIcon.Information,
            6000
        )

    def _on_no_update(self):
        QMessageBox.information(
            self, "No Updates",
            f"You are already running the latest version ({CURRENT_VERSION})."
        )

    def _on_update_check_error(self, error):
        QMessageBox.warning(
            self, "Update Check Failed",
            f"Could not check for updates:\n{error}"
        )

    def download_update(self):
        """Begin downloading the update, or open the release page as fallback."""
        tag = getattr(self, '_pending_update_tag', '')
        download_url = getattr(self, '_pending_update_download_url', '')
        release_url = getattr(self, '_pending_update_release_url', GITHUB_RELEASES_PAGE)

        # Non-frozen (dev) mode or no .exe asset: open browser
        if not download_url or not getattr(sys, 'frozen', False):
            webbrowser.open(release_url)
            return

        self._progress_dialog = QProgressDialog(
            f"Downloading {tag}...", "Cancel", 0, 100, self
        )
        self._progress_dialog.setWindowTitle("Downloading Update")
        self._progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self._progress_dialog.setMinimumDuration(0)
        self._progress_dialog.setValue(0)

        self._downloader = UpdateDownloader(download_url)
        self._downloader.progress.connect(self._progress_dialog.setValue)
        self._downloader.finished.connect(self._on_download_finished)
        self._downloader.error.connect(self._on_download_error)
        self._progress_dialog.canceled.connect(self._downloader.terminate)
        self._downloader.start()

    def _on_download_finished(self, tmp_path):
        """Replace the running exe with the downloaded one and relaunch."""
        self._progress_dialog.close()
        current_exe = sys.executable
        bat_lines = [
            "@echo off",
            "timeout /t 2 /nobreak >nul",
            f'move /y "{tmp_path}" "{current_exe}"',
            f'start "" "{current_exe}"',
        ]
        bat_fd, bat_path = tempfile.mkstemp(suffix=".bat")
        with os.fdopen(bat_fd, 'w') as bat:
            bat.write("\n".join(bat_lines))
        subprocess.Popen(
            ["cmd.exe", "/c", bat_path],
            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
        )
        self.quit_application()

    def _on_download_error(self, error):
        self._progress_dialog.close()
        QMessageBox.critical(
            self, "Download Failed",
            f"Could not download the update:\n{error}"
        )


def main():
    """Main entry point"""
    app = QApplication(sys.argv)
    app.setApplicationName("Brightness Controller")
    
    # Set application to continue running in background
    app.setQuitOnLastWindowClosed(False)
    
    window = BrightnessController()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
