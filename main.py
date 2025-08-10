import sys
import gi
from picamera2 import Picamera2
from picamera2.previews import QtGlPreview
import threading
import time
from PIL import Image
import io
import os

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gio, GdkPixbuf, GLib


class CameraApp(Adw.Application):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.connect("activate", self.on_activate)
        self.picam2 = None
        self.viewfinder_widget = None
        self.update_thread = None
        self.running = False
        self.capture_config = (
            None  # Will hold the high-res capture configuration
        )

    def on_activate(self, app):
        # Load the UI file
        builder = Gtk.Builder()
        builder.add_from_file("ui/camera.ui")

        # Get the window from UI file
        self.window = builder.get_object("main_window")
        self.window.set_application(self)

        # Get the viewfinder widget
        self.viewfinder_widget = builder.get_object("viewfinder")

        # Get the capture button and connect signal
        self.capture_button = builder.get_object("capture_button")
        self.capture_button.connect("clicked", self.on_capture_clicked)

        # Initialize camera
        self.setup_camera()

        # Connect window destroy signal to cleanup
        self.window.connect("destroy", self.on_window_destroy)

        self.window.present()
        self.window.fullscreen()

    def setup_camera(self):
        """Initialize and configure the camera"""
        try:
            self.picam2 = Picamera2()

            # Preview config with lower resolution
            preview_config = self.picam2.create_preview_configuration(
                main={"size": (640, 480), "format": "RGB888"},
                display="main",
                queue=False,  # Don't buffer frames
            )

            # High-res capture config
            self.capture_config = self.picam2.create_still_configuration(
                main={"size": self.picam2.sensor_resolution},
                buffer_count=2,  # Minimal buffer
            )

            self.picam2.configure(preview_config)
            self.picam2.start()

            # Start the viewfinder update thread
            self.running = True
            self.update_thread = threading.Thread(
                target=self.update_viewfinder
            )
            self.update_thread.daemon = True
            self.update_thread.start()

            print("Camera initialized successfully")

        except Exception as e:
            print(f"Failed to initialize camera: {e}")
            self.show_error_dialog(f"Camera Error: {e}")

    def update_viewfinder(self):
        """Continuously update the viewfinder with camera frames"""
        while self.running:
            try:
                if self.picam2 and self.viewfinder_widget:
                    pil_image = self.picam2.capture_image("main")
                    if pil_image.mode != "RGB":
                        pil_image = pil_image.convert("RGB")
                    pil_image = pil_image.resize((640, 480), Image.LANCZOS)

                    # Directly convert to RGB bytes
                    data = pil_image.tobytes()
                    pixbuf = GdkPixbuf.Pixbuf.new_from_bytes(
                        GLib.Bytes.new(data),
                        GdkPixbuf.Colorspace.RGB,
                        False,  # no alpha
                        8,  # bits per channel
                        640,
                        480,  # dimensions
                        640 * 3,  # rowstride (width * 3 for RGB)
                    )
                    GLib.idle_add(self.update_picture_widget, pixbuf)

                time.sleep(1.0 / 30.0)  # Limit to ~30 FPS

            except Exception as e:
                print(f"Viewfinder error: {e}")
                time.sleep(0.1)

    def update_picture_widget(self, pixbuf):
        """Update the GtkPicture widget with new frame"""
        if self.viewfinder_widget and pixbuf:
            self.viewfinder_widget.set_pixbuf(pixbuf)
        return False  # Don't repeat this idle callback

    def on_capture_clicked(self, button):
        """Handle capture button click - take full resolution photo"""
        print("Capture button clicked")
        if self.picam2:
            try:
                # Switch to high-res capture configuration
                self.picam2.switch_mode_and_capture_file(
                    self.capture_config, self.get_capture_filename()
                )

                # Show success message
                self.show_toast("Image captured successfully!")

            except Exception as e:
                print(f"Capture failed: {e}")
                self.show_error_dialog(f"Capture failed: {e}")

    def get_capture_filename(self):
        """Generate a timestamped filename for captures"""
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        # Create captures directory if it doesn't exist
        os.makedirs("captures", exist_ok=True)
        return f"captures/capture_{timestamp}.jpg"

    def show_toast(self, message):
        """Show a toast notification"""
        toast = Adw.Toast.new(message)
        toast.set_timeout(3)  # 3 seconds
        self.window.add_toast(toast)

    def show_error_dialog(self, message):
        """Show error dialog"""
        dialog = Adw.MessageDialog.new(
            transient_for=self.window, heading="Error", body=message
        )
        dialog.add_response("ok", "OK")
        dialog.present()

    def on_window_destroy(self, window):
        """Clean up when window is destroyed"""
        self.cleanup()

    def cleanup(self):
        """Clean up camera resources"""
        self.running = False

        if self.update_thread and self.update_thread.is_alive():
            self.update_thread.join(timeout=1.0)

        if self.picam2:
            try:
                self.picam2.stop()
                self.picam2.close()
                print("Camera cleaned up successfully")
            except Exception as e:
                print(f"Error during camera cleanup: {e}")


if __name__ == "__main__":
    app = CameraApp(application_id="com.example.CameraApp")
    app.run(sys.argv)
