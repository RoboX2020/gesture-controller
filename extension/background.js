// ============================================================================
// background.js - the Chrome extension's messenger (runs invisibly in the
// background, not on any web page).
//
// WHAT IT DOES: the Python backend (backend/main.py) broadcasts the
// controller's live status (mode, FPS, current gesture) over a WebSocket on
// localhost:8765. This script keeps a connection to that WebSocket open and
// forwards every status update to whichever browser tab you are looking at,
// where content.js draws it as a small on-screen badge.
//
// IT ALSO: puts an "ON"/"OFF" pill on the extension's toolbar icon so you
// can tell at a glance whether the Python backend is running. If the backend
// quits, this retries the connection every 2 seconds.
// ============================================================================

let socket = null;
let isConnected = false;

// Opens (and re-opens) the WebSocket connection to the Python backend.
function connect() {
  socket = new WebSocket('ws://localhost:8765');

  // Connected: show a blue ON badge on the toolbar icon.
  socket.onopen = () => {
    console.log('Connected to Gesture Backend');
    isConnected = true;
    chrome.action.setBadgeText({ text: 'ON' });
    chrome.action.setBadgeBackgroundColor({ color: '#4688F1' });
  };

  // A status update arrived from Python: pass it to the active tab so
  // content.js can display it.
  socket.onmessage = (event) => {
    const data = JSON.parse(event.data);
    // Broadcast to active tab
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      if (tabs[0] && tabs[0].id) {
        chrome.tabs.sendMessage(tabs[0].id, { type: 'GESTURE_UPDATE', data: data }).catch(() => {});
      }
    });
  };

  // Connection lost (backend quit or never started): show a red OFF badge
  // and try again in 2 seconds.
  socket.onclose = () => {
    console.log('Disconnected from Gesture Backend');
    isConnected = false;
    chrome.action.setBadgeText({ text: 'OFF' });
    chrome.action.setBadgeBackgroundColor({ color: '#FF0000' });
    setTimeout(connect, 2000); // Reconnect retry
  };

  socket.onerror = (error) => {
    console.error('WebSocket Error:', error);
    socket.close();
  };
}

connect();
