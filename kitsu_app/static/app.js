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

const validationModal = document.getElementById("validationModal");
const closeBtn = document.querySelector(".close-btn");
const modalOkBtn = document.getElementById("modalOkBtn");

function showModal() {
    validationModal.style.display = "block";
}

function closeModal() {
    validationModal.style.display = "none";
}

closeBtn.addEventListener("click", closeModal);
modalOkBtn.addEventListener("click", closeModal);

window.addEventListener("click", (e) => {
    if (e.target === validationModal) closeModal();
});


startBtn.addEventListener("click", () => {
    /*if (interval !== null) return;

    const payload = {
        process: document.getElementById("process-input").value,
        machine: document.getElementById("machine-input").value,
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
    saveBtn.disabled = true; */
    startBtn.addEventListener("click", () => {
        if (interval !== null) return;

        // ----- REQUIRED FIELD VALIDATION -----
        const process = document.getElementById("process").value;
        const machine = document.getElementById("machine").value;
        const operator = document.getElementById("operator").value;

        if (!process || !machine || !operator) {
            showModal();
            return;
        }


        // ----- PAYLOAD -----
        const payload = {
            process: process,
            machine: machine,
            operator: operator,
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

});

stopBtn.addEventListener("click", () => {
    // Check if timer is running
    if (interval === null) {
        alert("Timer is not running.");
        return;
    }

    clearInterval(interval);
    interval = null;

    fetch("/stop", { method: "POST" })
        .then(res => res.json())
        .then(data => {
            console.log("Duration saved:", data.duration);
        });

    startBtn.disabled = false;
    stopBtn.disabled = true;
    resetBtn.disabled = false;
    saveBtn.disabled = false;
    statusText.textContent = "Status: Stopped";
});

const resetBtn = document.getElementById("reset-button");

resetBtn.addEventListener("click", () => {
    // Stop timer if running
    if (interval !== null) {
        clearInterval(interval);
        interval = null;
    }

    // Reset display
    timerDisplay.textContent = "00:00.000";

    // Reset button states
    startBtn.disabled = false;
    stopBtn.disabled = true;
    saveBtn.disabled = true;

    // Reset status text
    statusText.textContent = "Status: Reset";

    // Clear form fields
    document.getElementById("process-input").value = "";
    document.getElementById("machine-input").value = "";
    document.getElementById("operator-input").value = "";
    document.getElementById("notes-input").value = "";
});


