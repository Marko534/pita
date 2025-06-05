import sys
import gi

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
        builder.add_from_file("camera.ui")

        # Get the window from UI file
        self.window = builder.get_object("main_window")
        self.window.set_application(self)

        # Connect signals
        self.capture_button = builder.get_object("capture_button")
        self.capture_button.connect("clicked", self.on_capture_clicked)

        self.record_button = builder.get_object("record_button")
        self.record_button.connect("clicked", self.on_record_clicked)

        self.window.present()

    def on_capture_clicked(self, button):
        print("Capture button clicked")
        # Add camera capture logic here

    def on_record_clicked(self, button):
        print("Record button clicked")
        # Add video recording logic here


app = CameraApp(application_id="com.example.CameraApp")
app.run(sys.argv)
