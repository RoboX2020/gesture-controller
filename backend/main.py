# ============================================================================
# Gesture Controller - drive your Mac with hand waves in front of the webcam.
#
# WHAT IT DOES: this program watches your webcam, finds your hand, and turns
# gestures into computer controls:
#   - Hold up ONLY your middle finger for 1 second  -> wake up / go to sleep
#   - Index finger up                               -> move the mouse cursor
#   - Pinch thumb + index                           -> left click
#   - Pinch thumb + middle                          -> double click
#   - Index + middle + ring up                      -> right click
#   - Index + middle up, hand high or low           -> scroll up / down
#   - Only pinky up, hand high or low               -> volume up / down
#   - Four fingers up, swipe left/right             -> switch desktop space
#
# THE TWO HALVES OF THE PROJECT:
#   1. This Python backend (the backend/ folder) does all the real work.
#   2. A small Chrome extension (the extension/ folder) just DISPLAYS the
#      current mode/gesture as a little badge on your web pages. The backend
#      broadcasts its status over a WebSocket (a live message channel on
#      your own computer, port 8765) and the extension listens.
#      The controller works fine without the extension - it is display only.
#
# THE OTHER FILE HERE: hand_detector.py wraps Google's MediaPipe AI model
# that finds the 21 hand landmarks (knuckle/fingertip positions) in a photo.
# This file decides what to DO with those positions.
#
# BEFORE YOU RUN: pip install opencv-python mediapipe pyautogui websockets
# You also need backend/hand_landmarker.task (the AI model file).
# macOS only for volume/space switching (uses AppleScript and Ctrl+arrows).
#
# WHEN DEBUGGING:
#   - "Could not open camera": another app is using the webcam, or terminal
#     lacks camera permission (System Settings > Privacy > Camera).
#   - Cursor jitters: raise `smoothening` below; overshoots: lower it.
#   - Gestures fire by accident: good light and a plain background help the
#     hand detector most.
#   (These notes are reasoned from the code, not re-tested on hardware.)
# ============================================================================

# OpenCV: reads webcam frames and draws the preview window
import cv2
# built-in: timers (hold-to-toggle, debounce pauses, FPS)
import time
# arrays/math: maps hand positions to screen/volume ranges
import numpy as np
# our wrapper around the MediaPipe hand-tracking AI
import hand_detector as hd
# moves/clicks the mouse and presses keys for us
import pyautogui
# built-in: which OS we are on (imported, currently unused)
import platform
# built-in: runs the macOS volume command
import os
# built-in: hypot() for cursor-movement distances
import math
# built-in: runs the WebSocket server
import asyncio
# the live status channel to the Chrome extension
import websockets
# built-in: runs the WebSocket server in the background
import threading
# built-in: packs the status dict into text for sending
import json

################################
# Settings
################################
wCam, hCam = 640, 480
frameR = 100 # Frame Reduction
smoothening = 5
ws_port = 8765
# Optimize PyAutoGUI for speed
pyautogui.PAUSE = 0 
pyautogui.FAILSAFE = False # Optional: prevents error if cursor hits corner, handled nicely in loop
################################

# Global State for WebSocket
# The one shared "what is happening right now" dictionary. The main loop
# keeps it fresh; the WebSocket server sends it to the extension 10x/second.
current_state = {
    "mode": "Initializing",
    "fps": 0,
    "hand_detected": False,
    "gesture": "None"
}

# Sets the Mac's speaker volume. vol_level is 0-100.
# Works by shelling out to AppleScript ("set volume output volume N").
def set_mac_volume(vol_level):
    """
    Sets mac volume (0-100)
    """
    try:
        # Map 0-100 to 0-7 (approx) or use output volume
        cmd = "osascript -e 'set volume output volume {}'".format(vol_level)
        os.system(cmd)
    except Exception as e:
        print(f"Error setting volume: {e}")

# Runs once per extension that connects: keeps sending it the latest
# current_state as JSON text, 10 times per second, until it disconnects.
async def ws_handler(websocket):
    while True:
        try:
            await websocket.send(json.dumps(current_state))
            await asyncio.sleep(0.1) # 10Hz updates
        except websockets.ConnectionClosed:
            break

# Starts the WebSocket server on localhost:8765 and runs it forever.
# "localhost" means only programs on THIS computer can connect.
async def start_server():
    async with websockets.serve(ws_handler, "localhost", ws_port):
        await asyncio.Future()  # run forever

# The camera loop cannot wait on the server, so the server gets its own
# background thread and this is its entry point.
def run_ws_server():
    asyncio.run(start_server())

# Re-maps a number from one range to another, e.g. camera pixels 0-640 to
# screen pixels 0-1920. (Currently unused - np.interp does the same below.)
def map_range(x, in_min, in_max, out_min, out_max):
  return (x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min

# The main program: camera loop + gesture decisions. Runs until you press q
# in the preview window or Ctrl+C in the terminal.
def main():
    # Start WebSocket Server in background thread
    t = threading.Thread(target=run_ws_server, daemon=True)
    t.start()
    print(f"WebSocket Server started on port {ws_port}")

    # Open webcam 0 (the built-in camera).
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: Could not open camera.")
        return

    cap.set(3, wCam)
    cap.set(4, hCam)
    
    pTime = 0
    # Only track one hand - two hands would make gestures ambiguous.
    detector = hd.HandDetector(max_hands=1)
    wScr, hScr = pyautogui.size()
    
    # Previous and current smoothed cursor locations (for steady movement).
    plocX, plocY = 0, 0
    clocX, clocY = 0, 0

    mode = "Cursor" 
    
    # State Vars
    system_active = False # Start Sleeping
    toggle_start_time = 0
    swipe_start_x = -1
    
    # Scroll State
    scroll_start_y = 0

    
    print("Gesture Controller Started.")

    while True:
        success, img = cap.read()
        if not success:
            break
            
        # Ask the AI where the hand is in this frame.
        img = detector.find_hands(img)
        lmList, bbox = detector.find_position(img)
        
        current_state["hand_detected"] = len(lmList) > 0
        
        if len(lmList) != 0:
            # Landmark numbers come from MediaPipe's hand map:
            # 4 = thumb tip, 8 = index tip, 12 = middle tip, 20 = pinky tip,
            # 9 = middle finger base (knuckle).
            x1, y1 = lmList[8][1:]   # Index Tip
            x2, y2 = lmList[12][1:]  # Middle Tip
            
            # Which fingers are up: [thumb, index, middle, ring, pinky],
            # each 1 (up) or 0 (down).
            fingers = detector.fingers_up()
            
            cv2.rectangle(img, (frameR, frameR), (wCam - frameR, hCam - frameR), (255, 0, 255), 2)
            

            # ------------------------------------------------------------------
            # WAKE / SLEEP GESTURE (Middle Finger Up)
            # ------------------------------------------------------------------
            # Check for "Middle Finger Only" (Thumb, Index, Ring, Pinky down. Middle Up)
            # fingers array: [Thumb, Index, Middle, Ring, Pinky]
            # Standard "Middle Only": 0 0 1 0 0
            if fingers[1] == 0 and fingers[2] == 1 and fingers[3] == 0 and fingers[4] == 0:
                 # Check if holding
                 if toggle_start_time == 0:
                     toggle_start_time = time.time()
                 
                 elapsed = time.time() - toggle_start_time
                 cv2.putText(img, f"Hold for Toggle: {int((1.0 - elapsed)*10)}", (wCam//2 - 100, hCam//2), cv2.FONT_HERSHEY_PLAIN, 3, (0, 0, 255), 3)
                 
                 if elapsed > 1.0:
                     system_active = not system_active
                     toggle_start_time = 0 # Reset
                     # Visual Feedback
                     color = (0, 255, 0) if system_active else (0, 0, 255)
                     cv2.circle(img, (wCam//2, hCam//2), 100, color, cv2.FILLED)
                     mode = "Active" if system_active else "Sleep"
                     current_state["mode"] = mode
                     # Cooldown to prevent rapid toggle
                     time.sleep(1.0) 
            else:
                 toggle_start_time = 0

            # ------------------------------------------------------------------
            # IF SLEEP, SKIP REST
            # ------------------------------------------------------------------
            if not system_active:
                cv2.rectangle(img, (0,0), (wCam, hCam), (0, 0, 255), 10)
                current_state["mode"] = "Sleep"
                current_state["gesture"] = "None"
                # Display only FPS and Sleep status, skip control logic
            else:
                # ------------------------------------------------------------------
                # 4-FINGER SWIPE (Tab Switch)
                # ------------------------------------------------------------------
                # Fingers [0, 1, 1, 1, 1] (Thumb might be whatever)
                if fingers[1] == 1 and fingers[2] == 1 and fingers[3] == 1 and fingers[4] == 1:
                     mode = "Swipe"
                     # Track X movement of wrist or middle finger base
                     current_x = lmList[9][1] # Middle finger MCP
                     
                     if swipe_start_x == -1:
                        swipe_start_x = current_x
                     
                     dx = current_x - swipe_start_x
                     
                     # Threshold for swipe
                     if abs(dx) > 100:
                         if dx > 0: # Right Swipe
                             # Switch Space Right (Ctrl+Right)
                             pyautogui.hotkey('ctrl', 'right')
                             current_state["gesture"] = "Space Next"
                             cv2.putText(img, "NEXT SPACE", (wCam//2 - 100, hCam//2), cv2.FONT_HERSHEY_PLAIN, 4, (0, 255, 0), 4)
                         else: # Left Swipe
                             # Switch Space Left (Ctrl+Left)
                             pyautogui.hotkey('ctrl', 'left')
                             current_state["gesture"] = "Space Prev"
                             cv2.putText(img, "PREV SPACE", (wCam//2 - 100, hCam//2), cv2.FONT_HERSHEY_PLAIN, 4, (0, 255, 0), 4)
                         
                         time.sleep(0.5) # Debounce
                         swipe_start_x = -1 # Reset
                     
                     
                         # NOTE: these next two lines are an accidental
                         # duplicate of the two above (harmless leftover -
                         # they just do the same debounce twice). Left as-is.
                         time.sleep(0.5) # Debounce
                         swipe_start_x = -1 # Reset


                # MODE: SCROLL
                # Index and Middle Up
                elif fingers[1] == 1 and fingers[2] == 1 and fingers[3] == 0:
                    mode = "Scroll"
                    current_state["gesture"] = "Scroll"
                    
                    # Logic: Relative movement or Position based?
                    # Let's use Position based. If hand is in top part -> Scroll Up. Bottom -> Scroll Down.
                    # Center -> Stop.
                    
                    mid_y = hCam // 2
                    deadzone = 50
                    
                    if y1 < mid_y - deadzone:
                        pyautogui.scroll(5) # Scroll Up
                        cv2.putText(img, "SCROLL UP", (20, 100), cv2.FONT_HERSHEY_PLAIN, 2, (0, 255, 0), 2)
                    elif y1 > mid_y + deadzone:
                        pyautogui.scroll(-5) # Scroll Down
                        cv2.putText(img, "SCROLL DOWN", (20, 100), cv2.FONT_HERSHEY_PLAIN, 2, (0, 255, 0), 2)
                
                # MODE: VOLUME
                # Pinky Up only
                elif fingers[4] == 1 and fingers[1] == 0 and fingers[2] == 0:
                    mode = "Volume"
                    current_state["gesture"] = "Volume"
                    
                    # Map y position of pinky tip to volume 0-100
                    # Top (0) -> 100%
                    # Bottom (hCam) -> 0%
                    
                    vol = np.interp(lmList[20][2], [frameR, hCam-frameR], [100, 0])
                    set_mac_volume(int(vol))
                    
                    cv2.rectangle(img, (50, 150), (85, 400), (0, 255, 0), 3)
                    cv2.rectangle(img, (50, int(np.interp(vol, [0, 100], [400, 150]))), (85, 400), (0, 255, 0), cv2.FILLED)
                    cv2.putText(img, f"{int(vol)}%", (40, 450), cv2.FONT_HERSHEY_PLAIN, 2, (0, 255, 0), 2)

                # MODE: CURSOR & CLICK
                # Index Up, Middle Down
                elif fingers[1] == 1 and fingers[2] == 0:
                    mode = "Cursor"
                    
                    # Cursor Move Logic
                    # Map the finger position inside the purple rectangle onto
                    # the real screen. X is mirrored (wScr -> 0) so moving
                    # your hand left moves the cursor left, like a mirror.
                    x3 = np.interp(x1, (frameR, wCam - frameR), (wScr, 0))
                    y3 = np.interp(y1, (frameR, hCam - frameR), (0, hScr))
                    
                    # Adaptive Smoothing
                    # The cursor only moves PART of the way to the target each
                    # frame (division below), which smooths hand wobble. Fast
                    # hand = less smoothing (responsive); slow hand = more
                    # smoothing (steady aim).
                    dist = math.hypot(x3 - plocX, y3 - plocY)
                    
                    if dist > 100:
                        adaptive_smooth = 2
                    elif dist < 10:
                        adaptive_smooth = 10
                    else:
                        adaptive_smooth = 5
                    
                    clocX = plocX + (x3 - plocX) / adaptive_smooth
                    clocY = plocY + (y3 - plocY) / adaptive_smooth
                    
                    pyautogui.moveTo(clocX, clocY)
                    plocX, plocY = clocX, clocY

                    # Click Logic
                    # 1. Left Click: Pinch Index (8) + Thumb (4)
                    dist_click, img, _ = detector.find_distance(4, 8, img)
                    
                    # 2. Double Click: Pinch Middle (12) + Thumb (4)
                    dist_dbl, img, lineInfoDbl = detector.find_distance(4, 12, img)
                    
                    if dist_dbl < 40:
                        cv2.circle(img, (lineInfoDbl[4], lineInfoDbl[5]), 15, (255, 0, 0), cv2.FILLED) # Blue for Double
                        pyautogui.doubleClick()
                        current_state["gesture"] = "Double Click"
                        time.sleep(0.3)
                    elif dist_click < 40:
                        # Draw click feedback
                        cx, cy = (lmList[4][1] + lmList[8][1]) // 2, (lmList[4][2] + lmList[8][2]) // 2
                        cv2.circle(img, (cx, cy), 15, (0, 255, 0), cv2.FILLED)
                        pyautogui.click()
                        current_state["gesture"] = "Click"
                        # No sleep here allows dragging? But we need to handle "Hold" for drag.
                        # pyautogui.click() is press+release.
                        # For drag, we might need mouseDown / mouseUp logic. 
                        # For now, sticking to simple click as requested.
                        # time.sleep(0.1) 
                    else:
                        current_state["gesture"] = "Move"

                # MODE: RIGHT CLICK
                # Index + Thumb + Middle all close together?
                elif fingers[1] == 1 and fingers[2] == 1 and fingers[3] == 1:
                    mode = "Right Click"
                    pyautogui.rightClick()
                    current_state["gesture"] = "Right Click"
                    time.sleep(0.3)
                
                else:
                    mode = "Idle"
                    current_state["gesture"] = "Idle"

        current_state["mode"] = mode
        if mode != "Swipe":
             swipe_start_x = -1

        cv2.putText(img, f"Mode: {mode}", (10, 50), cv2.FONT_HERSHEY_PLAIN, 2, (0,0,255), 3)

        cTime = time.time()
        fps = 1 / (cTime - pTime) if (cTime - pTime) > 0 else 0
        pTime = cTime
        current_state["fps"] = int(fps)
        cv2.putText(img, f"FPS: {int(fps)}", (400, 50), cv2.FONT_HERSHEY_PLAIN, 2, (255, 0, 0), 3)
        
        cv2.imshow("Gesture Controller", img)
        
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
