import sys
import gi
from picamera2 import Picamera2

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gio


class CameraApp(Adw.Application):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.connect("activate", self.on_activate)

    def on_activate(self, app):
        # Load the UI file
        builder = Gtk.Builder()
        # builder.add_from_file("ui/camera.ui")
        builder.add_from_file("ui/adw-multi-layout-demo-dialog.ui")

        # Get the window from UI file
        self.window = builder.get_object("main_window")
        self.window.set_application(self)

        self.window.present()
        self.window.fullscreen()

    def on_capture_clicked(self, button):
        print("Capture button clicked")
        # Add camera capture logic here

    def on_record_clicked(self, button):
        print("Record button clicked")
        # Add video recording logic here


app = CameraApp(application_id="com.example.CameraApp")
app.run(sys.argv)
