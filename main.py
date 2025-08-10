import sys
import gi
from picamera2 import Picamera2
from picamera2.previews import QtGlPreview
import threading
import time
from PIL import Image
import io

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

    def on_activate(self, app):
        # Load the UI file
        builder = Gtk.Builder()
        # Make sure to use the correct UI file name
        builder.add_from_file("ui/camera.ui")  # Changed back to camera.ui

        # Get the window from UI file
        self.window = builder.get_object("main_window")
        self.window.set_application(self)

        # Get the viewfinder widget
        self.viewfinder_widget = builder.get_object("viewfinder")

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

            # Configure camera for preview with specific format
            preview_config = self.picam2.create_preview_configuration(
                main={"size": (640, 480), "format": "RGB888"}, display="main"
            )
            self.picam2.configure(preview_config)

            # Start the camera
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
            # Show error dialog
            self.show_error_dialog(f"Camera Error: {e}")

    def update_viewfinder(self):
        """Continuously update the viewfinder with camera frames (no JPEG/PNG)"""
        while self.running:
            try:
                if self.picam2 and self.viewfinder_widget:
                    pil_image = self.picam2.capture_image("main")
                    if pil_image.mode != "RGB":
                        pil_image = pil_image.convert("RGB")
                    pil_image = pil_image.resize((640, 480), Image.LANCZOS)

                    # Directly convert to RGB bytes (no compression)
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

    def show_error_dialog(self, message):
        """Show error dialog"""
        dialog = Adw.MessageDialog.new(self.window, "Error", message)
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

    def on_capture_clicked(self, button):
        """Handle capture button click"""
        print("Capture button clicked")
        if self.picam2:
            try:
                # Capture high resolution image
                # You might want to reconfigure for higher resolution capture
                timestamp = int(time.time())
                filename = f"capture_{timestamp}.jpg"
                self.picam2.capture_file(filename)
                print(f"Image saved as {filename}")

                # Show success message
                toast = Adw.Toast()
                toast.set_title(f"Image saved as {filename}")
                # You'd need to add a toast overlay to your UI to show this

            except Exception as e:
                print(f"Capture failed: {e}")
                self.show_error_dialog(f"Capture failed: {e}")

    def on_record_clicked(self, button):
        """Handle record button click"""
        print("Record button clicked")
        # Add video recording logic here
        # This would require additional configuration and state management


if __name__ == "__main__":
    app = CameraApp(application_id="com.example.CameraApp")
    app.run(sys.argv)
