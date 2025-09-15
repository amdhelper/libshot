# This file makes the 'libshot' directory a package and exposes the public API
# from the inner 'libshot' module.

from .libshot import (
    capture,
    capture_interactive,
    list_monitors,
    LibshotError,
    UnsupportedError,
    PermissionDeniedError,
    InvalidRegionError
)
