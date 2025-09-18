import cv2
import sys
import gi
import os
import time
import numpy as np
import glob
from pathlib import Path
from picamera2 import Picamera2
from PIL import Image
from concurrent.futures import ThreadPoolExecutor
from picamera2.encoders import H264Encoder, MJPEGEncoder, Quality
from picamera2.outputs import FfmpegOutput

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Gst", "1.0")  # Add GStreamer for video playback
from gi.repository import Gtk, Adw, GdkPixbuf, GLib, Pango, Gio, Gst

# Initialize GStreamer
Gst.init(None)


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

        # Slider widgets
        self.saturation_slider = None
        self.contrast_slider = None
        self.sharpness_slider = None
        self.brightness_slider = None

        # Gallery widgets
        self.main_stack = None
        self.gallery_grid = None
        self.fullscreen_image = None
        self.fullscreen_video = None  # Add video widget
        self.gallery_button = None
        self.back_to_camera_button = None
        self.back_to_gallery_button = None
        self.delete_button = None
        self.prev_button = None
        self.next_button = None

        # Gallery state
        self.media_files = []
        self.current_media_index = 0

        # Video playback
        self.video_pipeline = None
        self.is_playing_video = False

        self.running = False
        self.executor = ThreadPoolExecutor(
            max_workers=2
        )  # One for preview, one for captures

        # Image processing parameters
        self.saturation_value = 1.0
        self.contrast_value = 1.0
        self.sharpness_value = 1.0
        self.brightness_value = 0.0

    def on_activate(self, app):
        builder = Gtk.Builder()
        builder.add_from_file("ui/camera.ui")

        self.window = builder.get_object("main_window")
        self.window.set_application(self)
        self.toast_overlay = builder.get_object("toast_overlay")
        
        # Get main stack
        self.main_stack = builder.get_object("main_stack")
        
        # Camera view widgets
        self.viewfinder_widget = builder.get_object("viewfinder")
        self.capture_button = builder.get_object("capture_button")
        self.capture_button.connect("clicked", self.on_capture_clicked)
        self.record_button = builder.get_object("record_button")
        self.record_button.connect("toggled", self.on_record_button_toggled)
        
        # Gallery button
        self.gallery_button = builder.get_object("gallery_button")
        self.gallery_button.connect("clicked", self.on_gallery_clicked)
        
        # Gallery view widgets
        self.gallery_grid = builder.get_object("gallery_grid")
        self.back_to_camera_button = builder.get_object("back_to_camera_button")
        self.back_to_camera_button.connect("clicked", self.on_back_to_camera_clicked)
        
        # Fullscreen view widgets
        self.fullscreen_image = builder.get_object("fullscreen_image")
        self.back_to_gallery_button = builder.get_object("back_to_gallery_button")
        self.back_to_gallery_button.connect("clicked", self.on_back_to_gallery_clicked)
        self.delete_button = builder.get_object("delete_button")
        self.delete_button.connect("clicked", self.on_delete_clicked)
        self.prev_button = builder.get_object("prev_button")
        self.prev_button.connect("clicked", self.on_prev_clicked)
        self.next_button = builder.get_object("next_button")
        self.next_button.connect("clicked", self.on_next_clicked)
        
        # Create video widget for fullscreen playback
        self.create_video_widget()
        
        # Get slider widgets and connect them
        self.saturation_slider = builder.get_object("saturation")
        self.contrast_slider = builder.get_object("contrast")
        self.sharpness_slider = builder.get_object("sharpness")
        self.brightness_slider = builder.get_object("brightness")
        
        # Connect slider value changes
        self.saturation_slider.connect("value-changed", self.on_saturation_changed)
        self.contrast_slider.connect("value-changed", self.on_contrast_changed)
        self.sharpness_slider.connect("value-changed", self.on_sharpness_changed)
        self.brightness_slider.connect("value-changed", self.on_brightness_changed)
        
        self.window.connect("close-request", self.cleanup)
        self.window.connect("destroy", self.cleanup)

        # Set up key event handling for navigation
        key_controller = Gtk.EventControllerKey()
        key_controller.connect("key-pressed", self.on_key_pressed)
        self.window.add_controller(key_controller)

        self.setup_camera()

        self.window.present()
        self.window.fullscreen()

    def create_video_widget(self):
        """Create GStreamer video widget for fullscreen playback"""
        # We'll create this dynamically when needed since we need to embed it in the fullscreen view
        pass

    def on_key_pressed(self, controller, keyval, keycode, state):
        """Handle keyboard navigation"""
        current_view = self.main_stack.get_visible_child_name()
        
        if current_view == "fullscreen":
            if keyval == 65361:  # Left arrow
                self.on_prev_clicked(None)
                return True
            elif keyval == 65363:  # Right arrow
                self.on_next_clicked(None)
                return True
            elif keyval == 65307:  # Escape
                self.on_back_to_gallery_clicked(None)
                return True
            elif keyval == 32:  # Space bar - play/pause video
                if self.is_playing_video:
                    self.toggle_video_playback()
                return True
        elif current_view == "gallery":
            if keyval == 65307:  # Escape
                self.on_back_to_camera_clicked(None)
                return True
        
        return False

    # Gallery Functions
    def on_gallery_clicked(self, button):
        """Switch to gallery view"""
        self.load_gallery()
        self.main_stack.set_visible_child_name("gallery")

    def on_back_to_camera_clicked(self, button):
        """Switch back to camera view"""
        self.stop_video_playback()  # Stop any video playback
        self.main_stack.set_visible_child_name("camera")

    def on_back_to_gallery_clicked(self, button):
        """Switch back to gallery from fullscreen"""
        self.stop_video_playback()  # Stop any video playback
        self.main_stack.set_visible_child_name("gallery")

    def load_gallery(self):
        """Load all media files and populate the gallery grid"""
        # Clear existing grid
        child = self.gallery_grid.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            self.gallery_grid.remove(child)
            child = next_child

        # Get all media files
        self.media_files = []
        captures_dir = Path("captures")
        if captures_dir.exists():
            # Get all jpg and mp4 files, sorted by modification time (newest first)
            jpg_files = list(captures_dir.glob("*.jpg"))
            mp4_files = list(captures_dir.glob("*.mp4"))
            all_files = jpg_files + mp4_files
            all_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            self.media_files = [str(f) for f in all_files]

        # Create thumbnail widgets
        for i, file_path in enumerate(self.media_files):
            thumbnail = self.create_thumbnail(file_path, i)
            if thumbnail:
                self.gallery_grid.append(thumbnail)

    def create_thumbnail(self, file_path, index):
        """Create a thumbnail widget for a media file"""
        try:
            button = Gtk.Button()
            button.set_size_request(200, 150)
            
            # Create overlay for video indicator
            overlay = Gtk.Overlay()
            
            if file_path.endswith('.jpg'):
                # Load image thumbnail
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                    file_path, 200, 150, True
                )
                image = Gtk.Picture.new_for_pixbuf(pixbuf)
            else:
                # For videos, try to extract first frame as thumbnail
                thumbnail_pixbuf = self.extract_video_thumbnail(file_path)
                if thumbnail_pixbuf:
                    image = Gtk.Picture.new_for_pixbuf(thumbnail_pixbuf)
                else:
                    # Fallback to video icon
                    image = Gtk.Image.new_from_icon_name("video-x-generic")
                    image.set_pixel_size(64)
                
                # Add video indicator
                video_label = Gtk.Label.new("")
                video_label.set_halign(Gtk.Align.END)
                video_label.set_valign(Gtk.Align.START)
                video_label.set_margin_top(5)
                video_label.set_margin_end(5)
                video_label.add_css_class("osd")
                overlay.add_overlay(video_label)
            
            overlay.set_child(image)
            button.set_child(overlay)
            button.connect("clicked", lambda btn, idx=index: self.on_thumbnail_clicked(idx))
            
            # Add some styling
            button.add_css_class("flat")
            
            return button
            
        except Exception as e:
            print(f"Error creating thumbnail for {file_path}: {e}")
            return None

    def extract_video_thumbnail(self, video_path):
        """Extract first frame from video as thumbnail"""
        try:
            cap = cv2.VideoCapture(video_path)
            ret, frame = cap.read()
            cap.release()
            
            if ret:
                # Convert BGR to RGB
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                
                # Resize to thumbnail size
                height, width = frame_rgb.shape[:2]
                aspect = width / height
                if aspect > 200/150:  # wider than thumbnail
                    new_width = 200
                    new_height = int(200 / aspect)
                else:  # taller than thumbnail
                    new_height = 150
                    new_width = int(150 * aspect)
                
                frame_resized = cv2.resize(frame_rgb, (new_width, new_height))
                
                # Create pixbuf
                pixbuf = GdkPixbuf.Pixbuf.new_from_data(
                    frame_resized.tobytes(),
                    GdkPixbuf.Colorspace.RGB,
                    False,
                    8,
                    new_width,
                    new_height,
                    new_width * 3,
                )
                return pixbuf
        except Exception as e:
            print(f"Error extracting video thumbnail: {e}")
        return None

    def on_thumbnail_clicked(self, index):
        """Handle thumbnail click - switch to fullscreen view"""
        self.current_media_index = index
        self.show_fullscreen_media()

    def show_fullscreen_media(self):
        """Show current media file in fullscreen"""
        if not self.media_files or self.current_media_index >= len(self.media_files):
            return
            
        file_path = self.media_files[self.current_media_index]
        
        # Stop any existing video playback first
        self.stop_video_playback()
        
        try:
            if file_path.endswith('.jpg'):
                # Load and display image
                pixbuf = GdkPixbuf.Pixbuf.new_from_file(file_path)
                self.fullscreen_image.set_pixbuf(pixbuf)
                self.fullscreen_image.set_visible(True)
                
                # Make sure video widget is hidden
                if hasattr(self, 'fullscreen_video') and self.fullscreen_video:
                    self.fullscreen_video.set_visible(False)
                    
                self.is_playing_video = False
            else:
                # For videos, set up video playback
                self.setup_video_playback(file_path)
                
        except Exception as e:
            print(f"Error loading media {file_path}: {e}")
            
        # Update navigation buttons
        self.update_navigation_buttons()
        
        # Switch to fullscreen view
        self.main_stack.set_visible_child_name("fullscreen")

    def setup_video_playback(self, video_path):
        """Set up video playback by replacing the image widget temporarily"""
        try:
            # Get the parent container of the fullscreen_image
            parent = self.fullscreen_image.get_parent()
            
            if not parent:
                print("Could not find parent container for video playback")
                return
                
            # Hide image widget
            self.fullscreen_image.set_visible(False)
            
            # Create video widget if it doesn't exist
            if not hasattr(self, 'fullscreen_video') or not self.fullscreen_video:
                self.fullscreen_video = Gtk.Video()
                self.fullscreen_video.set_hexpand(True)
                self.fullscreen_video.set_vexpand(True)
                self.fullscreen_video.set_halign(Gtk.Align.CENTER)
                self.fullscreen_video.set_valign(Gtk.Align.CENTER)
                
                # Add the video widget to the same parent as the image
                parent.append(self.fullscreen_video)
            
            # Set video file and show widget
            video_file = Gio.File.new_for_path(os.path.abspath(video_path))
            self.fullscreen_video.set_file(video_file)
            self.fullscreen_video.set_visible(True)
            
            # Set autoplay
            self.fullscreen_video.set_autoplay(True)
            self.fullscreen_video.set_loop(False)
            
            self.is_playing_video = True
            
            print(f"Playing video: {video_path}")
            
        except Exception as e:
            print(f"Error setting up video playback: {e}")
            # Fallback to showing video thumbnail
            try:
                thumbnail_pixbuf = self.extract_video_thumbnail(video_path)
                if thumbnail_pixbuf:
                    # Scale thumbnail to fit fullscreen
                    window_size = self.window.get_default_size()
                    if window_size[0] > 0 and window_size[1] > 0:
                        scaled_pixbuf = thumbnail_pixbuf.scale_simple(
                            min(800, window_size[0] - 100),
                            min(600, window_size[1] - 100),
                            GdkPixbuf.InterpType.BILINEAR
                        )
                        self.fullscreen_image.set_pixbuf(scaled_pixbuf)
                    else:
                        self.fullscreen_image.set_pixbuf(thumbnail_pixbuf)
                else:
                    # Final fallback to video icon
                    icon_pixbuf = GdkPixbuf.Pixbuf.new_from_icon_name("video-x-generic", 128)
                    self.fullscreen_image.set_pixbuf(icon_pixbuf)
                    
                self.fullscreen_image.set_visible(True)
                self.is_playing_video = False
            except Exception as fallback_error:
                print(f"Fallback error: {fallback_error}")
                self.fullscreen_image.set_visible(True)
                self.is_playing_video = False

    def stop_video_playback(self):
        """Stop video playback and clean up"""
        if hasattr(self, 'fullscreen_video') and self.fullscreen_video and self.is_playing_video:
            try:
                self.fullscreen_video.set_file(None)
                self.fullscreen_video.set_visible(False)
                self.is_playing_video = False
                
                # Show the image widget again
                self.fullscreen_image.set_visible(True)
            except Exception as e:
                print(f"Error stopping video: {e}")

    def toggle_video_playback(self):
        """Toggle video play/pause (if implemented in future)"""
        # Gtk.Video doesn't have direct play/pause control in GTK4
        # This is a placeholder for future implementation
        pass

    def update_navigation_buttons(self):
        """Update the state of navigation buttons"""
        self.prev_button.set_sensitive(self.current_media_index > 0)
        self.next_button.set_sensitive(self.current_media_index < len(self.media_files) - 1)

    def on_prev_clicked(self, button):
        """Show previous media file"""
        if self.current_media_index > 0:
            self.current_media_index -= 1
            self.show_fullscreen_media()

    def on_next_clicked(self, button):
        """Show next media file"""
        if self.current_media_index < len(self.media_files) - 1:
            self.current_media_index += 1
            self.show_fullscreen_media()

    def on_delete_clicked(self, button):
        """Delete current media file with confirmation"""
        if not self.media_files or self.current_media_index >= len(self.media_files):
            return
            
        file_path = self.media_files[self.current_media_index]
        filename = os.path.basename(file_path)
        
        # Create confirmation dialog
        dialog = Adw.MessageDialog.new(
            self.window,
            f"Delete {filename}?",
            "This action cannot be undone."
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("delete", "Delete")
        dialog.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")
        
        dialog.connect("response", self.on_delete_response, file_path)
        dialog.present()

    def on_delete_response(self, dialog, response, file_path):
        """Handle delete confirmation response"""
        if response == "delete":
            try:
                # Stop video playback if it's a video file
                self.stop_video_playback()
                
                # Delete the file
                os.remove(file_path)
                self.show_toast(f"Deleted {os.path.basename(file_path)}")
                
                # Remove from media files list
                self.media_files.remove(file_path)
                
                # Always refresh gallery to ensure consistency
                # We need to do this before navigation to ensure the gallery is updated
                GLib.idle_add(self.load_gallery)
                
                # Handle navigation after deletion
                if not self.media_files:
                    # No more files, go back to gallery (which will be empty)
                    self.on_back_to_gallery_clicked(None)
                else:
                    # Adjust current index if necessary
                    if self.current_media_index >= len(self.media_files):
                        self.current_media_index = len(self.media_files) - 1
                    self.show_fullscreen_media()
                    
            except Exception as e:
                self.show_toast(f"Error deleting file: {e}")

    # Camera Functions (existing code with additions)
    def on_saturation_changed(self, slider):
        # Convert from 0-200 range to 0-2.0 range
        self.saturation_value = slider.get_value() / 100.0
        self.update_camera_controls()

    def on_contrast_changed(self, slider):
        # Convert from 0-200 range to 0-2.0 range
        self.contrast_value = slider.get_value() / 100.0
        self.update_camera_controls()

    def on_sharpness_changed(self, slider):
        # Convert from 0-200 range to 0-2.0 range
        self.sharpness_value = slider.get_value() / 100.0
        self.update_camera_controls()

    def on_brightness_changed(self, slider):
        # Convert from 0-200 range to -1.0 to 1.0 range
        self.brightness_value = (slider.get_value() - 100.0) / 100.0
        self.update_camera_controls()

    def update_camera_controls(self):
        """Update camera controls with current slider values"""
        if self.picam2:
            try:
                controls = {
                    "Saturation": self.saturation_value,
                    "Contrast": self.contrast_value,
                    "Sharpness": self.sharpness_value,
                    "Brightness": self.brightness_value,
                }
                self.picam2.set_controls(controls)
            except Exception as e:
                print(f"Error setting camera controls: {e}")

    def apply_image_processing(self, image):
        """Apply additional image processing effects"""
        try:
            # Convert to float for processing
            img_float = image.astype(np.float32) / 255.0
            
            # Apply brightness (additive)
            img_float = img_float + (self.brightness_value * 0.3)  # Scale down brightness effect
            
            # Apply contrast (multiplicative around 0.5)
            img_float = ((img_float - 0.5) * self.contrast_value) + 0.5
            
            # Apply saturation
            if self.saturation_value != 1.0:
                # Convert to HSV for saturation adjustment
                hsv = cv2.cvtColor(img_float, cv2.COLOR_RGB2HSV)
                hsv[:,:,1] = hsv[:,:,1] * self.saturation_value
                img_float = cv2.cvtColor(hsv, cv2.COLOR_HSV2RGB)
            
            # Apply sharpness using unsharp mask
            if self.sharpness_value != 1.0:
                gaussian = cv2.GaussianBlur(img_float, (0, 0), 2.0)
                img_float = cv2.addWeighted(img_float, self.sharpness_value, 
                                          gaussian, -(self.sharpness_value - 1.0), 0)
            
            # Clip values and convert back to uint8
            img_float = np.clip(img_float, 0, 1)
            return (img_float * 255).astype(np.uint8)
            
        except Exception as e:
            print(f"Error in image processing: {e}")
            return image

    def setup_camera(self):
        try:
            self.picam2 = Picamera2()

            self.record_config = self.picam2.create_video_configuration(
                main={
                    "size": (2028, 1080),  # Matches Mode 2 resolution
                },
                lores={"size": (640, 480)},
                display="lores",
                encode="main",
                sensor={
                    "output_size": (2028, 1080),  # Ensures correct sensor mode
                    "bit_depth": 12,  # SRGGB12 (12-bit RAW)
                },
            )

            self.capture_config = self.picam2.create_still_configuration(
                main={"size": self.picam2.sensor_resolution},
                lores={"size": (640, 480)},
                buffer_count=2,
                display=None,
            )

            self.picam2.configure(self.record_config)
            self.picam2.start()

            # Set initial camera controls
            self.update_camera_controls()

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
                # Only update camera preview when on camera view
                current_view = self.main_stack.get_visible_child_name() if self.main_stack else "camera"
                if current_view != "camera":
                    time.sleep(0.1)
                    continue
                    
                yuv_array = self.picam2.capture_array("lores")

                # Convert YUV420 to RGB using OpenCV
                rgb_array = cv2.cvtColor(yuv_array, cv2.COLOR_YUV2RGB_I420)
                
                # Apply additional image processing effects
                rgb_array = self.apply_image_processing(rgb_array)

                # Create GdkPixbuf directly from RGB array
                height, width, channels = rgb_array.shape
                pixbuf = GdkPixbuf.Pixbuf.new_from_data(
                    rgb_array.tobytes(),
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

            output = FfmpegOutput(
                self.get_capture_filename() + ".mp4", audio=False
            )

            # Update camera controls before recording
            self.update_camera_controls()

            # For HD and lower
            self.picam2.start_encoder(
                H264Encoder(), output, quality=Quality.VERY_HIGH
            )
            print(self.get_capture_filename() + ".mp4")

        else:

            if self.timer_id:
                GLib.source_remove(self.timer_id)
                self.timer_id = 0
            self.recording = False
            style_context.remove_class("destructive-action")
            style_context.add_class("text-button")

            # Set record symbol with smaller font
            label.set_text("")
            attr_list = Pango.AttrList()
            size_attr = Pango.attr_size_new(32 * Pango.SCALE)
            attr_list.insert(size_attr)
            label.set_attributes(attr_list)
            self.picam2.stop_encoder()

    def capture_image(self):
        filename = self.get_capture_filename()
        
        # Update camera controls before capture
        self.update_camera_controls()
        
        image = self.picam2.switch_mode_and_capture_request(
            self.capture_config
        )

        image.save("main", self.get_capture_filename() + ".jpg")

    def get_capture_filename(self):
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        os.makedirs("captures", exist_ok=True)
        return f"captures/capture_{timestamp}"

    def show_toast(self, message):
        toast = Adw.Toast.new(message)
        self.toast_overlay.add_toast(toast)
    
    def show_error_dialog(self, message):
        """Show error dialog - placeholder implementation"""
        print(f"Error: {message}")

    def cleanup(self, window=None):

        if self.timer_id:
            GLib.source_remove(self.timer_id)
            self.timer_id = 0

        # Stop video playback
        self.stop_video_playback()
            
        if self.picam2 and self.recording:
            try:
                self.picam2.stop_encoder()
            except:
                pass

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
