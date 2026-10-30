#!/bin/bash
# ============================================================================
# build_app.sh - packages the Gesture Controller into one double-clickable
# Mac app (no Python install needed to run the result).
#
# HOW: PyInstaller bundles backend/main.py, the Python runtime, the
# MediaPipe library, and the hand_landmarker.task AI model into a single
# executable at dist/GestureController.
#
# RUN IT WITH:  bash build_app.sh   (needs: pip install pyinstaller)
# ============================================================================

# Clean previous builds
rm -rf build dist

# Run PyInstaller
# --onefile: Create a single executable
# --noconsole: Don't open a terminal window (optional, but good for release)
# --add-data: Include the model file
pyinstaller --name "GestureController" \
            --onefile \
            --collect-all mediapipe \
            --add-data "backend/hand_landmarker.task:." \
            backend/main.py

echo "Build Complete! Executable is in dist/GestureController"
