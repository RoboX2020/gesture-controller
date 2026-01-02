// Create Overlay
const overlay = document.createElement('div');
overlay.id = 'gesture-controller-overlay';
overlay.style.position = 'fixed';
overlay.style.bottom = '20px';
overlay.style.right = '20px';
overlay.style.padding = '12px 20px';
overlay.style.background = 'rgba(20, 20, 20, 0.6)';
overlay.style.backdropFilter = 'blur(10px)';
overlay.style.borderRadius = '16px';
overlay.style.color = '#fff';
overlay.style.fontFamily = '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif';
overlay.style.fontSize = '14px';
overlay.style.zIndex = '999999';
overlay.style.display = 'flex';
overlay.style.alignItems = 'center';
overlay.style.gap = '10px';
overlay.style.boxShadow = '0 4px 30px rgba(0, 0, 0, 0.1)';
overlay.style.border = '1px solid rgba(255, 255, 255, 0.1)';
overlay.style.transition = 'all 0.3s ease';
overlay.style.opacity = '0'; // Hidden by default, show on connection
overlay.style.pointerEvents = 'none'; // Pass through clicks

// Status Dot
const dot = document.createElement('div');
dot.style.width = '10px';
dot.style.height = '10px';
dot.style.borderRadius = '50%';
dot.style.background = '#ff4444'; // Red = Disconnected
dot.style.transition = 'background 0.3s ease';

// Text
const text = document.createElement('span');
text.innerText = 'Gesture: Disconnected';
text.style.fontWeight = '500';

overlay.appendChild(dot);
overlay.appendChild(text);
document.body.appendChild(overlay);

let hideTimeout;

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.type === 'GESTURE_UPDATE') {
        const data = request.data;

        // Show overlay
        overlay.style.opacity = '1';

        // Update Status with Sleep Logic
        if (data.mode === "Sleep") {
            dot.style.background = '#ff4444'; // Red
            dot.style.boxShadow = 'none';
            overlay.style.border = '1px solid #ff4444';
            text.innerText = "SLEEPING (Middle Finger to Wake)";
            overlay.style.opacity = '0.7';
        } else {
            if (data.hand_detected) {
                dot.style.background = '#00C851'; // Green
                dot.style.boxShadow = '0 0 10px #00C851';
                overlay.style.border = '1px solid rgba(255, 255, 255, 0.1)';
            } else {
                dot.style.background = '#ffbb33'; // Orange (No Hand)
                dot.style.boxShadow = 'none';
            }
            text.innerText = `Mode: ${data.mode} | FPS: ${data.fps}`;
        }

        // Optional: Visual Flair based on Gesture
        if (data.gesture === 'Click') {
            overlay.style.transform = 'scale(1.1)';
            setTimeout(() => overlay.style.transform = 'scale(1)', 100);
        }
    }
});
