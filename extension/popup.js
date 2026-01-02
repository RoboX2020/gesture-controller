const statusDiv = document.getElementById('status');
const bg = chrome.runtime.getBackgroundPage();
// Or better, just check badge or message
// V3 doesn't allow getBackgroundPage easily in some contexts, but let's simple check
statusDiv.innerText = "Check Overlay on Page";
