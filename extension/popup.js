// popup.js - runs when you click the extension's toolbar icon.
// Deliberately minimal: all it does is point you at the on-page badge,
// which is where the real status lives (see content.js).
const statusDiv = document.getElementById('status');
const bg = chrome.runtime.getBackgroundPage();
// Or better, just check badge or message
// V3 doesn't allow getBackgroundPage easily in some contexts, but let's simple check
statusDiv.innerText = "Check Overlay on Page";
