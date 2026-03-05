# Brightness Controller

A modern Python GUI application for controlling screen brightness with customizable global keyboard shortcuts.

## Features

- 🎨 **Modern GUI** - Built with PyQt6 for a clean, native look
- ⌨️ **Global Hotkeys** - Control brightness from anywhere, even when the app is minimized
- 🔧 **Customizable Shortcuts** - Easily change any keyboard shortcut to your preference
- 💾 **Persistent Settings** - Your custom shortcuts are saved automatically
- 🔔 **System Tray Integration** - Runs in the background without cluttering your taskbar
- 🎚️ **Manual Control** - Use the slider for fine-grained brightness adjustment

## Default Keyboard Shortcuts

| Shortcut | Brightness |
|----------|------------|
| `Ctrl + Shift + 0` | 0% |
| `Ctrl + Shift + 1` | 10% |
| `Ctrl + Shift + 2` | 20% |
| `Ctrl + Shift + 3` | 30% |
| `Ctrl + Shift + 4` | 40% |
| `Ctrl + Shift + 5` | 50% |
| `Ctrl + Shift + 6` | 60% |
| `Ctrl + Shift + 7` | 70% |
| `Ctrl + Shift + 8` | 80% |
| `Ctrl + Shift + 9` | 90% |
| `Ctrl + Shift + F` | 100% |

## Installation

### Prerequisites

- Python 3.8 or higher
- Windows OS (for brightness control)

### Setup Steps

1. **Clone or download this repository**

2. **Install required packages:**
   ```bash
   pip install -r requirements.txt
   ```

   Or install individually:
   ```bash
   pip install PyQt6 screen-brightness-control pynput
   ```

## Usage

### Running the Application

```bash
python brightness_controller.py
```

### Using the Application

1. **Launch** - Run the script to open the Brightness Controller window
2. **Control Brightness**:
   - Use keyboard shortcuts from anywhere
   - Adjust the slider manually in the GUI
3. **Customize Shortcuts**:
   - Click "Edit" next to any brightness level
   - Press your desired key combination
   - Click "OK" to save
   - Click "Save Configuration" to persist changes
4. **Minimize to Tray** - Click "Minimize to Tray" or close the window to keep it running in the background
5. **System Tray** - Right-click the tray icon to show the window or quit

### Customizing Shortcuts

1. Click the **Edit** button next to any brightness level
2. Press the key combination you want to use (e.g., `Ctrl + Alt + B`)
3. Click **OK** to confirm
4. Click **Save Configuration** to save your changes
5. Your custom shortcuts will be loaded automatically next time

### Configuration File

Shortcuts are stored in `brightness_config.json` in the same directory as the application. You can also edit this file directly if needed:

```json
{
    "0": "ctrl+shift+0",
    "10": "ctrl+shift+1",
    "20": "ctrl+shift+2",
    ...
}
```

## Requirements

- **PyQt6** - Modern GUI framework
- **screen-brightness-control** - Cross-platform brightness control
- **pynput** - Global keyboard event monitoring

## Troubleshooting

### Brightness Control Not Working

- **Windows**: Ensure you're running on a laptop or monitor that supports software brightness control
- **External Monitors**: Some external monitors may not support software brightness control
- **Permissions**: Run as administrator if brightness control doesn't work

### Hotkeys Not Working

- **Admin Rights**: Some applications may require the program to run as administrator to capture global hotkeys
- **Conflicting Shortcuts**: Make sure your shortcuts don't conflict with other applications

### Application Not Starting

- Ensure all dependencies are installed: `pip install -r requirements.txt`
- Check Python version: `python --version` (should be 3.8+)

## Running on Startup (Optional)

### Windows

1. Press `Win + R` and type `shell:startup`
2. Create a shortcut to `brightness_controller.py`
3. Or create a batch file:
   ```batch
   @echo off
   pythonw "d:\programming exercise\python\brightness\brightness_controller.py"
   ```

## Features in Detail

### System Tray Integration
- Minimizes to system tray instead of closing
- Right-click tray icon for quick access
- Hotkeys work even when minimized

### Persistent Configuration
- Settings are automatically saved to `brightness_config.json`
- Custom shortcuts persist between sessions
- Easy to backup or transfer settings

### Real-time Updates
- Brightness changes are instant
- Visual feedback in the GUI
- Status messages for all operations

## License

This project is open source and available under the MIT License.

## Contributing

Feel free to submit issues, fork the repository, and create pull requests for any improvements.

## Credits

Built with:
- [PyQt6](https://www.riverbankcomputing.com/software/pyqt/) - GUI framework
- [screen-brightness-control](https://github.com/Crozzers/screen_brightness_control) - Brightness control
- [pynput](https://github.com/moses-palmer/pynput) - Keyboard monitoring

---

**Note**: This application requires a display that supports software brightness control. Most laptop displays and some external monitors support this feature.
