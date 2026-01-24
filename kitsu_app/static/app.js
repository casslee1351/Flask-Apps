let startTime = null;
let interval = null;

const startBtn = document.getElementById("start-button");
const stopBtn = document.getElementById("stop-button");
const saveBtn = document.getElementById("save-button");
const timerDisplay = document.getElementById("timer-display");
const statusText = document.getElementById("status-text");

function formatTime(ms) {
    const totalSeconds = Math.floor(ms / 1000);
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;
    const millis = Math.floor(ms % 1000);

    return `${String(minutes).padStart(2, "0")}:` +
        `${String(seconds).padStart(2, "0")}.` +
        `${String(millis).padStart(3, "0")}`;
}

startBtn.addEventListener("click", () => {
    if (interval !== null) return;

    const payload = {
        process: document.getElementById("process-input").value,
        operation: document.getElementById("operation-input").value,
        operator: document.getElementById("operator-input").value,
        notes: document.getElementById("notes-input").value
    };

    fetch("/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
    });

    startTime = performance.now();
    interval = setInterval(() => {
        const elapsed = performance.now() - startTime;
        timerDisplay.textContent = formatTime(elapsed);
    }, 30);

    startBtn.disabled = true;
    stopBtn.disabled = false;
    saveBtn.disabled = true;
    statusText.textContent = "Status: Running";
});

stopBtn.addEventListener("click", () => {
    if (interval === null) return;

    clearInterval(interval);
    interval = null;

    fetch("/stop", { method: "POST" })
        .then(res => res.json())
        .then(data => {
            console.log("Duration saved:", data.duration);
        });

    startBtn.disabled = false;
    stopBtn.disabled = true;
    saveBtn.disabled = false;
    statusText.textContent = "Status: Stopped";
});

saveBtn.addEventListener("click", () => {
    statusText.textContent = "Status: Saved";
    saveBtn.disabled = true;
});
