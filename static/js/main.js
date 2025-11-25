const playlistForm = document.getElementById("playlist-form");
const urlInput = document.getElementById("playlist-url");
const loadBtn = document.getElementById("load-btn");
const statusEl = document.getElementById("status");

const optionsSection = document.getElementById("options-section");
const formatSelect = document.getElementById("format-select");
const qualitySelect = document.getElementById("quality-select");
const playlistTitleEl = document.getElementById("playlist-title");
const playlistMetaEl = document.getElementById("playlist-meta");
const videosContainer = document.getElementById("videos-container");
const selectAllBtn = document.getElementById("select-all-btn");
const clearAllBtn = document.getElementById("clear-all-btn");
const downloadBtn = document.getElementById("download-btn");

let currentUrl = null;
let currentVideos = [];
let currentJobId = null;
let progressTimer = null;

function setStatus(msg, type) {
    statusEl.textContent = msg || "";
    statusEl.className = "status" + (type ? " " + type : "");
}

function createVideoRow(video) {
    const row = document.createElement("div");
    row.className = "video-item";
    row.dataset.index = video.index;

    const main = document.createElement("div");
    main.className = "video-main";

    const label = document.createElement("label");
    label.className = "video-label";

    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.className = "video-checkbox";
    checkbox.dataset.index = video.index;

    const thumb = document.createElement("img");
    thumb.className = "video-thumb";
    thumb.src = video.thumbnail || "";
    thumb.alt = video.title || "thumbnail";

    const title = document.createElement("span");
    title.className = "video-title";
    title.textContent = "#" + video.index + " – " + video.title;

    label.appendChild(checkbox);
    label.appendChild(thumb);
    label.appendChild(title);

    const stateSpan = document.createElement("span");
    stateSpan.className = "video-state";
    stateSpan.textContent = "Idle";

    main.appendChild(label);
    main.appendChild(stateSpan);

    const progressWrap = document.createElement("div");
    progressWrap.className = "video-progress";

    const progress = document.createElement("progress");
    progress.className = "video-progress-bar";
    progress.max = 100;
    progress.value = 0;

    const percentSpan = document.createElement("span");
    percentSpan.className = "video-percent";
    percentSpan.textContent = "0%";

    progressWrap.appendChild(progress);
    progressWrap.appendChild(percentSpan);

    row.appendChild(main);
    row.appendChild(progressWrap);

    return row;
}

function updateVideoProgress(video) {
    const row = document.querySelector(`.video-item[data-index="${video.index}"]`);
    if (!row) return;

    const progressEl = row.querySelector(".video-progress-bar");
    const percentEl = row.querySelector(".video-percent");
    const stateEl = row.querySelector(".video-state");

    if (progressEl) {
        progressEl.value = video.progress || 0;
    }
    if (percentEl) {
        percentEl.textContent = (video.progress || 0) + "%";
    }
    if (stateEl) {
        stateEl.textContent = video.status || "";
    }
}

function getSelectedIndices() {
    const cbs = Array.from(document.querySelectorAll(".video-checkbox"));
    return cbs
        .filter(cb => cb.checked)
        .map(cb => parseInt(cb.dataset.index, 10));
}

async function pollProgress() {
    if (!currentJobId) return;

    try {
        const res = await fetch("/progress/" + currentJobId);
        const data = await res.json();
        if (!data.ok) {
            setStatus("Error: " + (data.error || "progress failed"), "error");
            clearInterval(progressTimer);
            progressTimer = null;
            return;
        }

        if (data.playlist_title) {
            playlistTitleEl.textContent = data.playlist_title;
        }

        (data.videos || []).forEach(v => updateVideoProgress(v));

        if (data.status === "finished") {
            setStatus("Download finished. Preparing archive…", "success");
            clearInterval(progressTimer);
            progressTimer = null;
            window.location.href = "/download-archive/" + currentJobId;
        } else if (data.status === "error") {
            setStatus("Error: " + (data.error || "download failed"), "error");
            clearInterval(progressTimer);
            progressTimer = null;
        }
    } catch (err) {
        setStatus("Error getting progress: " + err.message, "error");
        clearInterval(progressTimer);
        progressTimer = null;
    }
}

playlistForm.addEventListener("submit", async (e) => {
    e.preventDefault();

    const url = urlInput.value.trim();
    if (!url) {
        setStatus("Please enter a playlist URL.", "error");
        return;
    }

    setStatus("Loading playlist…", "info");
    loadBtn.disabled = true;
    optionsSection.classList.add("hidden");
    videosContainer.innerHTML = "";
    playlistTitleEl.textContent = "";
    playlistMetaEl.textContent = "";
    currentUrl = null;
    currentVideos = [];
    currentJobId = null;
    if (progressTimer) {
        clearInterval(progressTimer);
        progressTimer = null;
    }

    try {
        const res = await fetch("/api/playlist-info", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ url }),
        });

        const data = await res.json();
        if (!data.ok) {
            setStatus("Error: " + (data.error || "could not load playlist"), "error");
            return;
        }

        currentUrl = url;
        currentVideos = data.videos || [];
        playlistTitleEl.textContent = data.playlist_title || "";

        if (!currentVideos.length) {
            setStatus("No videos found in this playlist.", "error");
            return;
        }

        playlistMetaEl.textContent = `${currentVideos.length} item(s)`;

        videosContainer.innerHTML = "";
        currentVideos.forEach(v => {
            const row = createVideoRow(v);
            videosContainer.appendChild(row);
        });

        optionsSection.classList.remove("hidden");
        setStatus("Playlist loaded. Select videos and click Download selected.", "success");
    } catch (err) {
        setStatus("Error: " + err.message, "error");
    } finally {
        loadBtn.disabled = false;
    }
});

selectAllBtn.addEventListener("click", () => {
    document.querySelectorAll(".video-checkbox").forEach(cb => cb.checked = true);
});

clearAllBtn.addEventListener("click", () => {
    document.querySelectorAll(".video-checkbox").forEach(cb => cb.checked = false);
});

downloadBtn.addEventListener("click", async () => {
    if (!currentUrl) {
        setStatus("Load a playlist first.", "error");
        return;
    }

    const indices = getSelectedIndices();
    if (!indices.length) {
        setStatus("Select at least one video.", "error");
        return;
    }

    const format = formatSelect.value;
    const quality = qualitySelect.value;

    setStatus("Starting download…", "info");
    downloadBtn.disabled = true;
    currentJobId = null;
    if (progressTimer) {
        clearInterval(progressTimer);
        progressTimer = null;
    }

    // Reset progress UI
    document.querySelectorAll(".video-item").forEach(row => {
        const prog = row.querySelector(".video-progress-bar");
        const perc = row.querySelector(".video-percent");
        const state = row.querySelector(".video-state");
        if (prog) prog.value = 0;
        if (perc) perc.textContent = "0%";
        if (state) state.textContent = "Queued";
    });

    try {
        const res = await fetch("/download", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                url: currentUrl,
                format,
                quality,
                indices,
            }),
        });

        const data = await res.json();
        if (!data.ok) {
            setStatus("Error: " + (data.error || "could not start download"), "error");
            return;
        }

        currentJobId = data.job_id;
        setStatus("Downloading selected videos…", "info");
        progressTimer = setInterval(pollProgress, 1000);
    } catch (err) {
        setStatus("Error: " + err.message, "error");
    } finally {
        downloadBtn.disabled = false;
    }
});
