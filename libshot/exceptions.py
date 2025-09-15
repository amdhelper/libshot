"""
Custom exceptions for the libshot library.
"""

class LibshotError(Exception):
    """Base exception for all libshot errors."""
    pass

class UnsupportedError(LibshotError):
    """Raised when the environment is not supported (e.g., not Wayland or X11)."""
    pass

class PermissionDeniedError(LibshotError):
    """Raised when the user denies permission for a screenshot (e.g., in Wayland)."""
    pass

class InvalidRegionError(LibshotError):
    """Raised when the specified capture region is invalid or out of bounds."""
    pass
