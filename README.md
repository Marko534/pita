# Pita 📸 – Raspberry Pi Touchscreen Digital Camera

**Pita** ("pie" in Macedonian) is a homemade Raspberry Pi-powered digital camera with a custom touchscreen UI built using GTK 4 and Python. It provides the basic functionality of a digital camera while remaining hackable and fully customizable.

## 💡 Features
- Live camera view
- Touchscreen capture button
- Built-in photo/video gallery
- Settings menu:
  - Brightness
  - Flip image
  - Resolution
  - Date and time
- Intuitive UI styled for touch displays

## 🧰 Tech Stack
- **Language:** Python 3
- **UI:** GTK 4 (created with Cambalache)
- **Platform:** Raspberry Pi
- **Optional:** Wi-Fi/Bluetooth media transfer

## 🖥️ UI Screens
| Screen | Description |
|--------|-------------|
| Live View | Full-screen preview with overlay button |
| Gallery | Scrollable grid of thumbnails |
| Settings | Toggles, sliders, and combo boxes for camera settings |

## 🛠️ How to Run
1. Clone this repository
2. Install dependencies:
```bash
sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-4.0
