# libshot

A simple, unified, Wayland/X11-agnostic screen capture library for Python on Linux.

`libshot` provides a straightforward API to take screenshots, automatically detecting your display server environment and using the appropriate backend without any configuration.

## Features

- **Unified API:** The same code works for both Wayland and X11.
- **Backend Auto-Detection:** Automatically uses the correct backend (xdg-desktop-portal for Wayland, mss for X11).
- **Simple to Use:** Capture the full screen or a specific region with a single function call.
- **Pillow Integration:** Returns screenshots as Pillow `Image` objects for easy manipulation and saving.

## Installation

Install the library directly from the source directory:

```bash
# Navigate to the libshot directory
cd /path/to/libshot

# Install using pip
pip install .
```

## Dependencies

`libshot` relies on the following packages:

- `mss`: For the X11 backend.
- `jeepney`: For D-Bus communication on Wayland.
- `Pillow`: For image manipulation.

These dependencies are automatically installed when you install `libshot`.

## Usage

Using `libshot` is simple. Just import the library and call the `capture()` function.

### Capture the Full Screen

```python
import libshot

try:
    # Capture the primary monitor
    image = libshot.capture()
    image.save("fullscreen.png")
    print("Screenshot saved to fullscreen.png")
except Exception as e:
    print(f"An error occurred: {e}")
```

### Capture a Specific Region

```python
import libshot

try:
    # Define a region (x, y, width, height)
    region = (100, 100, 500, 500)
    
    image = libshot.capture(region=region)
    image.save("region.png")
    print("Screenshot saved to region.png")
except Exception as e:
    print(f"An error occurred: {e}")
```

## A Note on Wayland

Due to the security architecture of Wayland, applications cannot programmatically select a specific monitor or capture the screen without user interaction. 

- When calling `libshot.capture()` on Wayland, the `xdg-desktop-portal` will handle the process. 
- For full-screen captures, it will capture the entire desktop.
- For region captures (`region=...`), it will typically open an interactive selector for you to choose the area.
- The `monitor` parameter in the `capture()` function is ignored when running on Wayland.