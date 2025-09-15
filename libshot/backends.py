"""
Backend implementations for screen capturing.

This module provides the actual implementations for capturing screenshots on
different Linux display servers (Wayland and X11).
"""

import os
import tempfile
import time
import uuid
from abc import ABC, abstractmethod
from urllib.parse import urlparse
from urllib.request import url2pathname
import subprocess
import io

import mss
from jeepney.io.blocking import open_dbus_connection
from jeepney.wrappers import MessageGenerator, new_method_call
from PIL import Image

from .exceptions import InvalidRegionError, UnsupportedError


class BaseBackend(ABC):
    """Abstract base class for a screenshot backend."""

    @abstractmethod
    def capture(self, *, region=None, monitor=1):
        """Capture a screenshot."""
        pass

    @abstractmethod
    def list_monitors(self):
        """List available display monitors."""
        pass

    @abstractmethod
    def capture_interactive(self):
        """Perform an interactive screenshot session."""
        pass


class ScreenshotPortal(MessageGenerator):
    """D-Bus message generator for the org.freedesktop.portal.Screenshot interface."""
    interface = "org.freedesktop.portal.Screenshot"

    def __init__(self, object_path="/org/freedesktop/portal/desktop",
                 bus_name="org.freedesktop.portal.Desktop"):
        super().__init__(object_path=object_path, bus_name=bus_name)


class GnomeShellScreenshot(MessageGenerator):
    """D-Bus message generator for the org.gnome.Shell.Screenshot interface."""
    interface = "org.gnome.Shell.Screenshot"

    def __init__(self, object_path="/org/gnome/Shell/Screenshot",
                 bus_name="org.gnome.Shell"):
        super().__init__(object_path=object_path, bus_name=bus_name)


class GnomeWaylandBackend(BaseBackend):
    """
    Screenshot backend for GNOME on Wayland.
    This uses the private, non-portal D-Bus interface, which allows for a
    more seamless 'select and release' workflow.
    """

    def __init__(self):
        self.conn = open_dbus_connection()
        self.screenshot_iface = GnomeShellScreenshot()

    def __del__(self):
        if hasattr(self, 'conn') and self.conn:
            self.conn.close()

    def capture(self, *, region=None, monitor=1):
        # This backend is primarily for interactive capture.
        if region:
            # Re-route to the main capture method which can handle regions
            with mss.mss() as sct:
                capture_area = {
                    "top": region[1], "left": region[0],
                    "width": region[2], "height": region[3],
                    "mon": monitor
                }
                sct_img = sct.grab(capture_area)
                return Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
        else:
            raise UnsupportedError("Non-interactive, full-screen capture is not implemented for the GNOME backend yet.")

    def list_monitors(self):
        # Same as generic Wayland backend
        return [{'left': 0, 'top': 0, 'width': 1920, 'height': 1080}]

    def capture_interactive(self):
        """
        Uses org.gnome.Shell.Screenshot for a seamless interactive capture.
        """
        try:
            # Step 1: Call SelectArea to let the user select a region. This is a blocking call.
            select_area_msg = new_method_call(self.screenshot_iface, "SelectArea")
            reply = self.conn.send_and_get_reply(select_area_msg)
            success, area = reply.body

            if not success:
                return None  # User cancelled

            x, y, w, h = area
            if w == 0 or h == 0:
                return None  # No area selected

            # Step 2: Create a temporary file for the screenshot
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                filepath = tmp.name

            # Step 3: Call ScreenshotArea with the selected region
            screenshot_area_msg = new_method_call(
                self.screenshot_iface, "ScreenshotArea", "iiiib s",
                (x, y, w, h, False, filepath)  # x, y, w, h, flash, filename
            )
            reply = self.conn.send_and_get_reply(screenshot_area_msg)
            screenshot_success, = reply.body

            if not screenshot_success:
                raise RuntimeError("GNOME Shell failed to take the screenshot after area selection.")

            # Step 4: Open the saved file with Pillow
            with Image.open(filepath) as img:
                img.load()
                os.remove(filepath)  # Clean up the temp file
                return img.convert("RGB")

        except Exception as e:
            print(f"INFO: GNOME-specific backend failed ({e}). Falling back to gnome-screenshot.")
            
            # Create a temporary file path for gnome-screenshot to save to
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                filepath = tmp.name
            
            try:
                # Use GNOME's native CLI tool as a fallback. -a is for area selection.
                command = f'gnome-screenshot -a -f "{filepath}"'
                # This command blocks until selection is done or cancelled.
                # It returns 0 on success, 1 on cancellation (e.g., pressing Esc).
                result = subprocess.run(command, shell=True, check=False)

                # Check if the command was successful and the file was created.
                if result.returncode == 0 and os.path.exists(filepath) and os.path.getsize(filepath) > 0:
                    with Image.open(filepath) as img:
                        img.load()
                        os.remove(filepath)
                        return img.convert("RGB")
                else:
                    print("INFO: User cancelled screenshot via gnome-screenshot or it failed.")
                    if os.path.exists(filepath):
                        os.remove(filepath)
                    return None

            except FileNotFoundError:
                print("ERROR: Fallback command 'gnome-screenshot' not found.")
                if os.path.exists(filepath):
                    os.remove(filepath)
                return None
            except Exception as gn_e:
                print(f"ERROR: An unexpected error occurred with gnome-screenshot: {gn_e}")
                if os.path.exists(filepath):
                    os.remove(filepath)
                return None


class WaylandBackend(BaseBackend):
    """
    Screenshot backend for Wayland using the xdg-desktop-portal.
    This is the standard, secure way to take screenshots on modern Wayland desktops.
    """

    def __init__(self):
        self.conn = open_dbus_connection()
        self.screenshot_portal = ScreenshotPortal()

    def __del__(self):
        if hasattr(self, 'conn') and self.conn:
            self.conn.close()

    def _get_response(self, request):
        reply = self.conn.send_and_get_reply(request)
        if not reply.body or not reply.body[0]:
            raise RuntimeError("Failed to get a valid handle from the portal.")
        
        handle_token = reply.body[0].split("/")[-1]

        while True:
            response_signal = self.conn.receive()
            if response_signal.header.fields[1].endswith(handle_token):
                break

        return response_signal.body[1]

    def capture(self, *, region=None, monitor=1):
        handle_token = f"libshot_{uuid.uuid4().hex}"
        options = {
            "handle_token": ('s', handle_token),
            "modal": ('b', True),
            "interactive": ('b', region is not None)
        }

        request = new_method_call(self.screenshot_portal, "Screenshot", "sa{sv}", ("", options))
        
        response = self._get_response(request)
        uri_variant = response.get("uri")

        if uri_variant is None:
            return None # User cancelled

        sig, body = uri_variant
        if sig != 's':
            raise TypeError(f"Expected URI with signature 's', got '{sig}'")

        image_path = url2pathname(urlparse(body).path)

        for _ in range(5):
            try:
                with Image.open(image_path) as img:
                    img.load()
                    return img.convert("RGB")
            except FileNotFoundError:
                time.sleep(0.1)
        
        raise FileNotFoundError(f"libshot: Portal returned a URI to a file that could not be found: {image_path}")

    def list_monitors(self):
        return [{'left': 0, 'top': 0, 'width': 1920, 'height': 1080}]

    def capture_interactive(self):
        """Uses the portal's interactive mode. Passing any region triggers it."""
        return self.capture(region=(1, 1, 1, 1))


class X11Backend(BaseBackend):
    """Screenshot backend for X11 using the 'mss' library."""

    def capture(self, *, region=None, monitor=1):
        try:
            with mss.mss() as sct:
                if monitor <= 0 or monitor >= len(sct.monitors):
                    raise InvalidRegionError(f"Monitor {monitor} is not available.")

                if region:
                    capture_area = {
                        "top": region[1], "left": region[0],
                        "width": region[2], "height": region[3],
                        "mon": monitor
                    }
                else:
                    capture_area = sct.monitors[monitor]

                sct_img = sct.grab(capture_area)
                return Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
        except mss.exception.ScreenShotError as e:
            raise InvalidRegionError(f"Failed to capture screen with mss: {e}") from e

    def list_monitors(self):
        with mss.mss() as sct:
            return sct.monitors[1:]

    def capture_interactive(self):
        """Provides an interactive region selection overlay using pygame for X11."""
        try:
            import pygame
        except ImportError:
            raise ImportError("Pygame is required for interactive screenshots on X11. Please install it.")

        pygame.init()
        try:
            pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_CROSSHAIR)

            with mss.mss() as sct:
                monitor_info = sct.monitors[0]
                full_width, full_height = monitor_info["width"], monitor_info["height"]
                bg_sct = sct.grab(monitor_info)
                bg_img = Image.frombytes("RGB", bg_sct.size, bg_sct.bgra, "raw", "BGRX")

            win = pygame.display.set_mode((full_width, full_height), pygame.NOFRAME)
            bg_surface = pygame.image.fromstring(bg_img.tobytes(), bg_img.size, bg_img.mode)
            win.blit(bg_surface, (0, 0))
            pygame.display.set_caption("Select area to capture, press ESC to cancel")
            
            selection_rect = None
            start_pos = None
            running = True

            while running:
                for event in pygame.event.get():
                    if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                        running = False
                        selection_rect = None
                    elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                        start_pos = event.pos
                    elif event.type == pygame.MOUSEBUTTONUP and event.button == 1 and start_pos:
                        end_pos = event.pos
                        left = min(start_pos[0], end_pos[0])
                        top = min(start_pos[1], end_pos[1])
                        width = abs(start_pos[0] - end_pos[0])
                        height = abs(start_pos[1] - end_pos[1])
                        if width > 0 and height > 0:
                            selection_rect = (left, top, width, height)
                        running = False

                if start_pos:
                    current_pos = pygame.mouse.get_pos()
                    win.blit(bg_surface, (0, 0))
                    
                    overlay = pygame.Surface((full_width, full_height), pygame.SRCALPHA)
                    overlay.fill((0, 0, 0, 128))
                    
                    rect_left = min(start_pos[0], current_pos[0])
                    rect_top = min(start_pos[1], current_pos[1])
                    rect_width = abs(start_pos[0] - current_pos[0])
                    rect_height = abs(start_pos[1] - current_pos[1])

                    if rect_width > 0 and rect_height > 0:
                        pygame.draw.rect(overlay, (0, 0, 0, 0), (rect_left, rect_top, rect_width, rect_height))
                        win.blit(overlay, (0,0))
                        pygame.draw.rect(win, (255, 255, 255), (rect_left, rect_top, rect_width, rect_height), 1)

                pygame.display.flip()
        finally:
            pygame.quit()

        if selection_rect:
            return self.capture(region=selection_rect)
        
        return None