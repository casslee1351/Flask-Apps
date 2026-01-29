let startTime = null;
let interval = null;
let laps = [];
let lastLapTime = null;

const startBtn = document.getElementById("start-button");
const stopBtn = document.getElementById("stop-button");
const saveBtn = document.getElementById("save-button");
const resetBtn = document.getElementById("reset-button");
const timerDisplay = document.getElementById("timer-display");
const statusText = document.getElementById("status-text");
const lapBtn = document.getElementById("lap-button");
const statusDot = document.getElementById("status-dot");

function getSelectedTimeType() {
    return document.querySelector('input[name="timeType"]:checked')?.value;
}


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


// startBtn.addEventListener("click", () => {
//     /*if (interval !== null) return;

//     const payload = {
//         process: document.getElementById("process-input").value,
//         machine: document.getElementById("machine-input").value,
//         operator: document.getElementById("operator-input").value,
//         notes: document.getElementById("notes-input").value
//     };

//     fetch("/start", {
//         method: "POST",
//         headers: { "Content-Type": "application/json" },
//         body: JSON.stringify(payload)
//     });

//     startTime = performance.now();
//     interval = setInterval(() => {
//         const elapsed = performance.now() - startTime;
//         timerDisplay.textContent = formatTime(elapsed);
//     }, 30);

//     startBtn.disabled = true;
//     stopBtn.disabled = false;
//     saveBtn.disabled = true;
//     statusText.textContent = "Status: Running";
// });

// stopBtn.addEventListener("click", () => {
//     if (interval === null) return;

//     clearInterval(interval);
//     interval = null;

//     fetch("/stop", { method: "POST" })
//         .then(res => res.json())
//         .then(data => {
//             console.log("Duration saved:", data.duration);
//         });

//     startBtn.disabled = false;
//     stopBtn.disabled = true;
//     saveBtn.disabled = false;
//     statusText.textContent = "Status: Stopped";
// });

// saveBtn.addEventListener("click", () => {
//     statusText.textContent = "Status: Saved";
//     saveBtn.disabled = true; */

//     if (interval !== null) return;

//     // ----- REQUIRED FIELD VALIDATION -----
//     const process = document.getElementById("process-type").value;
//     const machine = document.getElementById("machine-type").value;
//     const operator = document.getElementById("operator-type").value;

//     if (!process || !machine || !operator) {
//         showModal();
//         return;
//     }


//     // ----- PAYLOAD -----
//     const payload = {
//         process: process,
//         machine: machine,
//         operator: operator,
//         notes: document.getElementById("notes-input").value
//     };

//     fetch("/start", {
//         method: "POST",
//         headers: { "Content-Type": "application/json" },
//         body: JSON.stringify(payload)
//     });

//     startTime = performance.now();
//     interval = setInterval(() => {
//         const elapsed = performance.now() - startTime;
//         timerDisplay.textContent = formatTime(elapsed);
//     }, 30);

//     startBtn.disabled = true;
//     stopBtn.disabled = false;
//     saveBtn.disabled = true;

//     // statusText.textContent = "Status: Running";
//     setStatus("Ready to start", "idle");
// });

startBtn.addEventListener("click", () => {
    if (interval !== null) return;

    const process = document.getElementById("process-type").value;
    const machine = document.getElementById("machine-type").value;
    const operator = document.getElementById("operator-type").value;
    const timeType = getSelectedTimeType();
    const lapBtn = document.getElementById("lap-button");

    if (!process || !machine || !operator || !timeType) {
        showModal();
        return;
    }


    const payload = {
        process: process,
        machine: machine,
        operator: operator,
        notes: document.getElementById("notes-input").value,
        time_type: timeType
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

    laps = [];
    lastLapTime = startTime;
    document.getElementById("lap-list").innerHTML = "";

    startBtn.disabled = true;
    stopBtn.disabled = false;
    saveBtn.disabled = true;
    lapBtn.disabled = false;

    setStatus("Ready to start", "idle");
});



stopBtn.addEventListener("click", () => {
    if (interval === null) return;

    clearInterval(interval);
    interval = null;

    // Calculate duration using the same timer as display
    const elapsedMs = performance.now() - startTime;
    const durationSeconds = elapsedMs / 1000;

    fetch("/stop", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ duration: durationSeconds })
    })
        .then(res => res.json())
        .then(data => {
            console.log("Stopped duration:", data.duration);
        });

    startBtn.disabled = false;
    stopBtn.disabled = true;
    saveBtn.disabled = false;
    resetBtn.disabled = false;
    lapBtn.disabled = true;


    // statusText.textContent = "Status: Stopped";
    setStatus("Stopped", "paused");
});


saveBtn.addEventListener("click", () => {
    // stop must have happened already
    if (interval !== null) {
        alert("Please stop the timer before saving.");
        return;
    }

    fetch("/save", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            notes: document.getElementById("notes-input").value,
            laps: laps
        })
    })
        .then(res => res.json())
        .then(data => {
            if (data.status === "saved") {
                setStatus("Saved", "idle");
                saveBtn.disabled = true;
                alert("Run saved successfully!");
            } else {
                alert(data.message || "Error saving run.");
            }
        });
});


resetBtn.addEventListener("click", () => {
    // Stop timer if running
    if (interval !== null) {
        clearInterval(interval);
        interval = null;
    }

    // Reset display
    timerDisplay.textContent = "00:00.000";

    laps = [];
    lastLapTime = null;
    document.getElementById("lap-list").innerHTML = "";

    // Reset button states
    startBtn.disabled = false;
    stopBtn.disabled = true;
    saveBtn.disabled = true;
    lapBtn.disabled = true;


    // Reset status text
    statusText.textContent = "Status: Reset";

    // Clear form fields
    document.getElementById("process-type").value = "";
    document.getElementById("machine-type").value = "";
    document.getElementById("operator-type").value = "";
    document.getElementById("notes-input").value = "";

    // Optional: clear current run data
    currentRun = null;

    setStatus("Ready to start", "idle");
});

lapBtn.addEventListener("click", () => {
    if (!startTime) return;
    console.log("Laps:", laps);

    const now = performance.now();
    const lapDuration = (now - lastLapTime) / 1000;
    const totalElapsed = (now - startTime) / 1000;

    const lap = {
        lap_number: laps.length + 1,
        lap_duration: lapDuration,
        total_time: totalElapsed
    };

    laps.push(lap);
    lastLapTime = now;

    // UI
    const li = document.createElement("li");
    li.textContent = `Lap ${lap.lap_number}: ${lapDuration.toFixed(2)}s (Total: ${totalElapsed.toFixed(2)}s)`;
    document.getElementById("lap-list").appendChild(li);
});


// Function to change the color of the status dot
function setStatus(text, state) {
    statusText.textContent = text;

    statusDot.classList.remove("idle", "running", "paused");
    statusDot.classList.add(state);
}



function loadRuns() {
    fetch("/runs")
        .then(res => res.json())
        .then(data => {
            console.log(data);
            // display runs in the UI here
        });
}

// load on page load
loadRuns();


