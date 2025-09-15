"""
libshot: A unified, Wayland/X11-agnostic screen capture library for Linux.

This library provides a simple, high-level API to take screenshots on Linux,
automatically detecting whether the environment is running on Wayland or X11
and using the appropriate backend.

Example:
    >>> import libshot
    >>> # Perform an interactive screenshot
    >>> image = libshot.capture_interactive()
    >>> if image:
    >>>     image.save("interactive_capture.png")
"""

__version__ = "0.2.0"  # Bump version for new features
__author__ = "Your Name"

import os
from .backends import WaylandBackend, X11Backend, GnomeWaylandBackend
from .exceptions import LibshotError, UnsupportedError, PermissionDeniedError, InvalidRegionError

# This global variable will hold the singleton instance of the detected backend.
_backend_instance = None

def _get_backend():
    """
    Detects and initializes the appropriate backend.

    It determines the session type and desktop environment from environment
    variables and caches the backend instance for all subsequent calls.

    The priority is:
    1. GnomeWaylandBackend (for GNOME on Wayland)
    2. WaylandBackend (for other Wayland desktops)
    3. X11Backend (for X11)

    Returns:
        The initialized backend instance.

    Raises:
        UnsupportedError: If the display server is not Wayland or X11.
    """
    global _backend_instance
    if _backend_instance is not None:
        return _backend_instance

    session_type = os.environ.get("XDG_SESSION_TYPE", "").lower()
    desktop_env = os.environ.get("XDG_CURRENT_DESKTOP", "").lower()

    if session_type == "wayland":
        # Check if we are on GNOME and try to use the specific backend
        if "gnome" in desktop_env:
            try:
                print("INFO: Detected GNOME on Wayland. Trying GNOME-specific backend.")
                _backend_instance = GnomeWaylandBackend()
                return _backend_instance
            except Exception as e:
                print(f"WARNING: GNOME backend failed to initialize ({e}). Falling back to standard portal.")
                # Fallback to the generic Wayland portal if the GNOME one fails
                _backend_instance = WaylandBackend()
                return _backend_instance
        else:
            # For other Wayland desktops (KDE, Sway, etc.)
            _backend_instance = WaylandBackend()
            return _backend_instance
    elif session_type == "x11" or os.environ.get("DISPLAY"):
        _backend_instance = X11Backend()
        return _backend_instance

    raise UnsupportedError(
        f"Unsupported or unknown session type '{session_type}'. "
        f"libshot currently supports Wayland and X11."
    )

def capture(*, region=None, monitor=1):
    """Captures a screenshot of a given region or the full screen.

    Args:
        region (tuple, optional): A tuple of (x, y, width, height) defining the
                                  box to capture. If None, captures the whole
                                  monitor. Defaults to None.
        monitor (int, optional): The monitor number to capture, starting from 1.
                                 Note: This is ignored on Wayland. Defaults to 1.

    Returns:
        A Pillow Image object of the captured screen area, or None if failed.
    """
    backend = _get_backend()
    return backend.capture(region=region, monitor=monitor)

def capture_interactive():
    """
    Performs an interactive screenshot session.

    This is the recommended function for interactive use.
    It will automatically use the best available interactive method:
    - On GNOME Wayland: Uses the seamless, built-in screenshot UI.
    - On other Wayland desktops: Uses the xdg-desktop-portal.
    - On X11: Uses a custom Pygame-based overlay for selection.

    Returns:
        A Pillow Image object of the captured screen area, or None if cancelled.
    """
    backend = _get_backend()
    return backend.capture_interactive()

def list_monitors():
    """Lists available display monitors.

    Returns:
        A list of dictionaries, with each dictionary describing a monitor's
        geometry, e.g., {'left': int, 'top': int, 'width': int, 'height': int}.
    """
    backend = _get_backend()
    return backend.list_monitors()