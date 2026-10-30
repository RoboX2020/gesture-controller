# ============================================================================
# hand_detector.py - the "eyes" of the Gesture Controller.
#
# WHAT THIS FILE DOES: wraps Google's MediaPipe hand-tracking AI in one
# friendly class, HandDetector. You hand it webcam photos, it tells you
# where the hand is:
#   - find_hands()     runs the AI on one photo (one webcam frame)
#   - find_position()  turns the AI's answer into a list of 21 landmarks
#                      (knuckle and fingertip pixel positions)
#   - fingers_up()     works out which of the 5 fingers are raised
#   - find_distance()  measures the pixel gap between two landmarks
#                      (used for "pinch to click")
#
# HOW THE AI WORKS, ROUGHLY: the model file hand_landmarker.task (must sit
# next to this file) was trained by Google on huge numbers of hand photos.
# Given a new photo it outputs 21 (x, y) positions following a fixed map:
# 0 = wrist, 4 = thumb tip, 8 = index tip, 12 = middle tip, 16 = ring tip,
# 20 = pinky tip, and the knuckles in between.
#
# USED BY: backend/main.py (the main loop). Nothing else imports this.
# ============================================================================

# Google's hand-tracking AI library
import mediapipe as mp
# OpenCV: image format conversions and drawing
import cv2
# arrays: used for the (currently unused) drawing helper
import numpy as np
# built-in: timestamps the AI needs for video mode
import time
# built-in: builds the path to the model file
import os

from mediapipe.tasks import python
from mediapipe.tasks.python import vision

class HandDetector:
    # Sets up the AI. max_hands=1 because the controller tracks one hand;
    # detection_con/track_con are confidence thresholds (0.5 = "only report
    # a hand when the AI is at least 50% sure").
    def __init__(self, mode=False, max_hands=1, detection_con=0.5, track_con=0.5):
        self.max_hands = max_hands
        # Note: Mode/Con ranges are different in Tasks API or handled via options
        
        # Path to model
        model_path = os.path.join(os.path.dirname(__file__), 'hand_landmarker.task')
        
        base_options = python.BaseOptions(model_asset_path=model_path)
        options = vision.HandLandmarkerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.VIDEO,
            num_hands=self.max_hands,
            min_hand_detection_confidence=detection_con,
            min_hand_presence_confidence=detection_con,
            min_tracking_confidence=track_con
        )
        self.landmarker = vision.HandLandmarker.create_from_options(options)
        
        self.results = None
        self.lm_list = []
        self.tip_ids = [4, 8, 12, 16, 20]
        
        # Helper for drawing (mp.solutions.drawing_utils might still exist?)
        # If solutions.drawing_utils is missing, we must implement custom drawing
        # Let's hope mp.solutions works for drawing tools, usually it does, or query explicitly
        try:
             self.mp_draw = mp.solutions.drawing_utils
             self.mp_hands_style = mp.solutions.hands
        except AttributeError:
             self.mp_draw = None

    # Runs the AI on one webcam frame and (optionally) draws the hand on it.
    # Returns the frame (with any drawing). The actual landmark data is kept
    # in self.results for find_position() to read next.
    def find_hands(self, img, draw=True):
        # Convert CV2 BGR to RGB
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        
        # Create MP Image
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=img_rgb)
        
        # Detect
        # Timestamp needed for VIDEO mode
        timestamp_ms = int(time.time() * 1000) 
        
        self.results = self.landmarker.detect_for_video(mp_image, timestamp_ms)

        if self.results.hand_landmarks:
             if draw:
                 # Custom drawer if mp_draw fails or using it if available
                 if self.mp_draw:
                     # Need to convert NormalizedLandmarks to list for drawing_utils?
                     # drawing_utils expects protobuf-like. Tasks API returns objects.
                     # Might be incompatible. Safer to draw manually.
                     pass
                 
                     # NOTE for anyone debugging: the block below is
                     # unfinished. It references `hand_landmarks`, `w` and
                     # `h`, none of which exist in this scope, so it would
                     # crash if it ever ran. It is left exactly as found;
                     # in practice the visible hand drawing comes from
                     # find_position()'s bounding box instead.
                     # Optimize Drawing: Use polylines instead of multiple line calls
                     points = []
                     for lm in hand_landmarks:
                         px, py = int(lm.x * w), int(lm.y * h)
                         points.append([px, py])
                         cv2.circle(img, (px, py), 5, (255, 0, 255), cv2.FILLED)
                     
                     points = np.array(points, np.int32)
                     
                     # Connections definitions for polylines
                     # Thumb, Index, Middle, Ring, Pinky
                     fingers = [
                         [0,1,2,3,4],
                         [0,5,6,7,8],
                         [5,9,10,11,12],
                         [9,13,14,15,16],
                         [13,17,18,19,20],
                         [0,17] # Wrist closure
                     ]
                     
                     for finger in fingers:
                        cv2.polylines(img, [points[finger]], False, (255, 255, 255), 2)


        return img

    # Turns the AI's answer into a simple list and a bounding box.
    # Returns:
    #   lm_list: 21 entries of [landmark_id, x_pixels, y_pixels]
    #   bbox:    (left, top, right, bottom) of the hand, or [] if no hand
    def find_position(self, img, hand_no=0, draw=True):
        x_list = []
        y_list = []
        bbox = []
        self.lm_list = []

        if self.results and self.results.hand_landmarks:
            if hand_no < len(self.results.hand_landmarks):
                my_hand = self.results.hand_landmarks[hand_no]
                h, w, c = img.shape
                # The AI gives positions as fractions of the image (0.0-1.0);
                # multiply by width/height to get real pixels.
                for id, lm in enumerate(my_hand):
                    cx, cy = int(lm.x * w), int(lm.y * h)
                    x_list.append(cx)
                    y_list.append(cy)
                    self.lm_list.append([id, cx, cy])
                    # if draw is handled in find_hands, skip here or re-draw special
                
                if x_list:
                    xmin, xmax = min(x_list), max(x_list)
                    ymin, ymax = min(y_list), max(y_list)
                    bbox = xmin, ymin, xmax, ymax

                    if draw:
                        cv2.rectangle(img, (xmin - 20, ymin - 20), (xmax + 20, ymax + 20), (0, 255, 0), 2)
        
        return self.lm_list, bbox

    # Works out which fingers are raised.
    # Returns a list of five 1/0 values: [thumb, index, middle, ring, pinky]
    # (or an empty list when no hand was found).
    def fingers_up(self):
        fingers = []
        if len(self.lm_list) == 0:
            return []

        # Thumb (Right Hand Assumption - Check x)
        # Tip (4) < IP (3)? 
        # Actually in Tasks API landmarks are distinct objects.
        # Logic remains same if we use coordinates.
        if self.lm_list[self.tip_ids[0]][1] < self.lm_list[self.tip_ids[0] - 1][1]:
            fingers.append(1)
        else:
            fingers.append(0)

        # 4 Fingers
        # A finger counts as "up" when its tip is HIGHER on the screen
        # (smaller y) than the joint two landmarks below it.
        for id in range(1, 5):
            if self.lm_list[self.tip_ids[id]][2] < self.lm_list[self.tip_ids[id] - 2][2]:
                fingers.append(1)
            else:
                fingers.append(0)
        return fingers

    # Measures the pixel distance between two landmarks (e.g. thumb tip 4
    # and index tip 8 for a pinch) and draws the line between them.
    # Returns (distance, the drawn-on image, [x1, y1, x2, y2, center_x, center_y]).
    def find_distance(self, p1, p2, img, draw=True, r=15, t=3):
        x1, y1 = self.lm_list[p1][1:]
        x2, y2 = self.lm_list[p2][1:]
        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2

        if draw:
            cv2.line(img, (x1, y1), (x2, y2), (255, 0, 255), t)
            cv2.circle(img, (x1, y1), r, (255, 0, 255), cv2.FILLED)
            cv2.circle(img, (x2, y2), r, (255, 0, 255), cv2.FILLED)
            cv2.circle(img, (cx, cy), r, (0, 0, 255), cv2.FILLED)
            
        # Pythagoras: the straight-line distance between the two points.
        length = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
        return length, img, [x1, y1, x2, y2, cx, cy]
