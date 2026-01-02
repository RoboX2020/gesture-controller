#!/bin/bash
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
