#!/usr/bin/env python3
"""
A simple script to test the libshot library.
"""

import libshot

if __name__ == "__main__":
    print("Testing libshot screen capture library...")

    # --- Test 1: List monitors ---
    try:
        monitors = libshot.list_monitors()
        print(f"[SUCCESS] Found {len(monitors)} monitors:")
        for i, mon in enumerate(monitors, 1):
            print(f"  Monitor {i}: {mon['width']}x{mon['height']} at ({mon['left']}, {mon['top']})")
    except Exception as e:
        print(f"[FAILURE] Could not list monitors: {e}")


    # --- Test 2: Capture full screen ---
    try:
        print("\nAttempting to capture the primary monitor...")
        fullscreen_image = libshot.capture()
        if fullscreen_image:
            output_file = "test_fullscreen.png"
            fullscreen_image.save(output_file)
            print(f"[SUCCESS] Full screen captured and saved to '{output_file}'")
        else:
            print("[FAILURE] Capture command returned None.")
    except Exception as e:
        print(f"[FAILURE] Could not capture full screen: {e}")


    # --- Test 3: Capture a region ---
    try:
        region = (100, 100, 500, 500)
        print(f"\nAttempting to capture region {region}...")
        region_image = libshot.capture(region=region)
        if region_image:
            output_file = "test_region.png"
            region_image.save(output_file)
            print(f"[SUCCESS] Region captured and saved to '{output_file}'")
        else:
            print("[FAILURE] Region capture command returned None.")
    except Exception as e:
        print(f"[FAILURE] Could not capture region: {e}")

    print("\nTest complete.")
