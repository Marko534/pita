# Pita 📸 – Raspberry Pi Touchscreen Digital Camera

Pita ("pie" in Macedonian) is a homemade Raspberry Pi-powered digital camera with a custom touchscreen UI built using GTK 4 and Python. It provides the basic functionality of a digital camera while remaining hackable and fully customizable.
---

## ✨ Features

- 📸 **Capture photos** – full-resolution stills saved as `.jpg`
- 🎥 **Record videos** – H.264 `.mp4` with live timer
- 🎚 **Real-time adjustments** with sliders:
  - Brightness
  - Contrast
  - Saturation
  - Sharpness
- 🖼 **Built-in gallery** – view captured images and videos
- 🔄 **Fullscreen navigation** – browse, delete, and return to camera
- ⚡ **Responsive preview** – 30 FPS live feed with applied adjustments

---

## 🚀 Project Vision

Pita is designed as an **open, hackable camera platform**:

- A learning tool for students exploring photography, image processing, and Raspberry Pi development.
- A prototyping base for makers building specialized imaging devices.
- A path toward advanced features: editing tools, remote control from a smartphone, motion-triggered security capture, and more.

---

## 🖥️ Screenshots

<img width="452" height="412" alt="image" src="https://github.com/user-attachments/assets/dbdc97be-4e49-416d-be73-f9b56ca4522f" />

---

## 🛠 Hardware Requirements

- Raspberry Pi 3 (recommended) or newer
- Raspberry Pi Camera Module (v2, HQ, or compatible)
- Touchscreen display (HDMI or DSI)
- 16 GB microSD card
- Case, lens, and cooling (optional but recommended)

---

## ⚙️ Software Requirements

- Python 3.9+
- GTK 4 + libadwaita
- Picamera2
- OpenCV
- NumPy
- Pillow

---

## 📦 Installation

### 1. System preparation

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3-pip python3-venv \
    libgtk-4-dev libadwaita-1-dev \
    ffmpeg libavcodec-dev libavformat-dev \
    libatlas-base-dev libopenblas-dev libhdf5-dev \
    python3-gi gir1.2-gtk-4.0 gir1.2-adw-1 \
    python3-picamera2
```

### 2. Project setup
```git clone https://github.com/Marko534/pita.git
cd pita
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Run the app
```python3 pita/main.py

