let socket = null;
let isConnected = false;

function connect() {
  socket = new WebSocket('ws://localhost:8765');

  socket.onopen = () => {
    console.log('Connected to Gesture Backend');
    isConnected = true;
    chrome.action.setBadgeText({ text: 'ON' });
    chrome.action.setBadgeBackgroundColor({ color: '#4688F1' });
  };

  socket.onmessage = (event) => {
    const data = JSON.parse(event.data);
    // Broadcast to active tab
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      if (tabs[0] && tabs[0].id) {
        chrome.tabs.sendMessage(tabs[0].id, { type: 'GESTURE_UPDATE', data: data }).catch(() => {});
      }
    });
  };

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
