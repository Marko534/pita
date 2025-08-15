import sys
import gi
import os
import time
from picamera2 import Picamera2
from PIL import Image
from concurrent.futures import ThreadPoolExecutor

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GdkPixbuf, GLib, Pango


class CameraApp(Adw.Application):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.connect("activate", self.on_activate)

        self.recording_start_time = 0
        self.timer_id = 0  # To keep track of the GLib timeout source

        self.picam2 = None
        self.capture_config = None
        self.record_config = None
        self.viewfinder_widget = None
        self.capture_button = None
        self.record_button = None
        self.recording = False

        self.running = False
        self.executor = ThreadPoolExecutor(
            max_workers=2
        )  # One for preview, one for captures

    def on_activate(self, app):
        builder = Gtk.Builder()
        builder.add_from_file("ui/camera.ui")

        self.window = builder.get_object("main_window")
        self.window.set_application(self)
        self.toast_overlay = builder.get_object("toast_overlay")
        self.viewfinder_widget = builder.get_object("viewfinder")

        self.capture_button = builder.get_object("capture_button")
        self.capture_button.connect("clicked", self.on_capture_clicked)
        self.record_button = builder.get_object("record_button")
        self.record_button.connect("toggled", self.on_record_button_toggled)
        self.window.connect("close-request", self.cleanup)
        self.window.connect("destroy", self.cleanup)

        self.setup_camera()

        self.window.present()
        self.window.fullscreen()

    def setup_camera(self):
        try:
            self.picam2 = Picamera2()

            preview_config = self.picam2.create_preview_configuration(
                main={"size": (640, 480), "format": "BGR888"}, queue=False
            )

            self.capture_config = self.picam2.create_still_configuration(
                main={"size": self.picam2.sensor_resolution},
                buffer_count=2,
                display=None,
            )

            self.record_config = self.picam2.create_video_configuration()

            self.picam2.configure(preview_config)
            self.picam2.start()

            self.running = True
            self.executor.submit(self.camera_preview_loop)

            print("Camera initialized successfully")

        except Exception as e:
            print(f"Failed to initialize camera: {e}")
            self.show_error_dialog(f"Camera Error: {e}")

    def camera_preview_loop(self):
        """Background thread for updating the preview"""
        while self.running:
            try:
                frame = self.picam2.capture_array("main")

                pixbuf = GdkPixbuf.Pixbuf.new_from_bytes(
                    GLib.Bytes.new(frame.tobytes()),
                    GdkPixbuf.Colorspace.RGB,
                    False,
                    8,
                    640,
                    480,
                    640 * 3,
                )

                if self.recording:
                    elapsed = int(time.time() - self.recording_start_time)
                    minutes = elapsed // 60
                    seconds = elapsed % 60
                    timer_text = f"{minutes:02d}:{seconds:02d}"

                    self.record_button.get_child().set_text(timer_text)
                    # print(self.record_button)

                # Push frame to UI
                GLib.idle_add(self.update_picture_widget, pixbuf)

                time.sleep(1 / 30.0)  # ~30 FPS
            except Exception as e:
                print(f"Camera loop error: {e}")
                time.sleep(0.1)

    def update_picture_widget(self, pixbuf):
        if self.viewfinder_widget:
            self.viewfinder_widget.set_pixbuf(pixbuf)
        return False

    def on_capture_clicked(self, button):
        print("Capture button clicked")
        GLib.idle_add(self.show_toast, "Image captured successfully!")

        self.executor.submit(self.capture_image)

    def on_record_button_toggled(self, button):
        style_context = button.get_style_context()
        label = button.get_child()  # Get the GtkLabel child

        if button.get_active():
            self.recording = True
            style_context.add_class("destructive-action")
            style_context.remove_class("text-button")

            # Set timer text with larger font
            label.set_text("00:00")
            attr_list = Pango.AttrList()
            size_attr = Pango.attr_size_new(11 * Pango.SCALE)
            attr_list.insert(size_attr)
            label.set_attributes(attr_list)

            self.recording_start_time = time.time()
            # Update timer every second
            self.timer_id = GLib.timeout_add(1000, self.update_recording_timer)

        else:

            if self.timer_id:
                GLib.source_remove(self.timer_id)
                self.timer_id = 0
            self.recording = False
            style_context.remove_class("destructive-action")
            style_context.add_class("text-button")

            # Set record symbol with smaller font
            label.set_text("")
            attr_list = Pango.AttrList()
            size_attr = Pango.attr_size_new(32 * Pango.SCALE)
            attr_list.insert(size_attr)
            label.set_attributes(attr_list)

    def capture_image(self):
        filename = self.get_capture_filename()
        image = self.picam2.switch_mode_and_capture_request(
            self.capture_config
        )

        image.save("main", self.get_capture_filename() + ".jpg")
        # image.save("main", self.get_capture_filename() + ".png")
        # image.save_dng(self.get_capture_filename() + ".dng")

    def start_video(self):
        filename = self.get_capture_filename()
        image = self.picam2.switch_mode_and_capture_request(
            self.capture_config
        )

        image.save("main", self.get_capture_filename() + ".jpg")
        # image.save("main", self.get_capture_filename() + ".png")
        # image.save_dng(self.get_capture_filename() + ".dng")

    def get_capture_filename(self):
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        os.makedirs("captures", exist_ok=True)
        return f"captures/capture_{timestamp}"

    def show_toast(self, message):
        toast = Adw.Toast.new(message)
        self.toast_overlay.add_toast(toast)

    def cleanup(self, window=None):

        if self.timer_id:
            GLib.source_remove(self.timer_id)
            self.timer_id = 0
        # self.stop_recording()

        self.running = False
        self.executor.shutdown(wait=True)
        if self.picam2:
            try:
                self.picam2.stop()
                self.picam2.close()
            except Exception as e:
                print(f"Error during camera cleanup: {e}")
        print("Camera cleaned up successfully")
        # Quit the application
        self.quit()
        # Ensure Python process exits
        sys.exit(0)


if __name__ == "__main__":
    app = CameraApp(application_id="com.example.CameraApp")
    app.run(sys.argv)
