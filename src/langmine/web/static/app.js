/* LangMine SPA — vanilla JavaScript, no framework. */

let currentVideoId = null;
let currentStatusFilter = "all";
let allSentences = [];

// ============================================================
// Init
// ============================================================

document.addEventListener("DOMContentLoaded", () => {
    loadVideos();
    setupTabs();
    setupUrlInput();
});

// ============================================================
// Video Library
// ============================================================

async function loadVideos() {
    try {
        const resp = await fetch("/api/videos");
        const data = await resp.json();
        renderVideoList(data.videos);
    } catch (err) {
        console.error("Failed to load videos:", err);
    }
}

function renderVideoList(videos) {
    const list = document.getElementById("video-list");
    if (videos.length === 0) {
        list.innerHTML = '<div style="padding: 20px; color: var(--text-secondary); font-size: 0.85rem;">No videos yet. Paste a YouTube URL above.</div>';
        return;
    }

    list.innerHTML = videos.map(v => {
        const i1Badge = v.i1_count > 0 ? ` 🔥${v.i1_count}` : "";
        const keptBadge = v.kept_count > 0 ? ` ✅${v.kept_count}` : "";
        return `
            <div class="video-item ${v.id === currentVideoId ? 'active' : ''}"
                 onclick="selectVideo(${v.id})">
                <div class="video-title">${escapeHtml(v.title || v.youtube_id)}</div>
                <div class="video-meta">${v.total_sentences} sentences${i1Badge}${keptBadge}</div>
            </div>
        `;
    }).join("");
}

async function selectVideo(videoId) {
    currentVideoId = videoId;
    currentStatusFilter = "all";
    highlightActiveVideo();
    resetTabs();
    await loadSentences();
}

function highlightActiveVideo() {
    document.querySelectorAll(".video-item").forEach(el => {
        el.classList.remove("active");
    });
    document.querySelectorAll(".video-item").forEach(el => {
        const onclick = el.getAttribute("onclick") || "";
        if (onclick.includes(String(currentVideoId))) {
            el.classList.add("active");
        }
    });
}

// ============================================================
// Sentence Cards
// ============================================================

async function loadSentences() {
    if (!currentVideoId) return;

    const status = currentStatusFilter === "all" ? "" : currentStatusFilter;
    const url = `/api/videos/${currentVideoId}/sentences${status ? `?status=${status}` : ""}`;

    try {
        const resp = await fetch(url);
        const data = await resp.json();
        allSentences = data.sentences;
        renderCards(allSentences);
    } catch (err) {
        console.error("Failed to load sentences:", err);
    }
}

function renderCards(sentences) {
    const container = document.getElementById("cards-container");

    if (sentences.length === 0) {
        container.innerHTML = '<div id="empty-state">No sentences to show.</div>';
        return;
    }

    container.innerHTML = sentences.map(s => `
        <div class="sentence-card" id="sentence-${s.id}">
            <div class="chinese-text">
                ${highlightUnknown(s.text, s.unknown_word)}
                <span class="status-badge ${s.status}">${statusLabel(s.status)}</span>
            </div>
            ${s.text_segmented ? `<div class="segmented-text">${escapeHtml(s.text_segmented)}</div>` : ""}
            ${s.has_audio ? `
                <div class="audio-player">
                    <audio controls src="/api/sentences/${s.id}/audio"></audio>
                </div>
            ` : ""}
            ${s.unknown_word ? `
                <div style="font-size: 0.8rem; color: var(--text-secondary); margin-bottom: 8px;">
                    🆕 <strong>${escapeHtml(s.unknown_word)}</strong>
                    ${s.unknown_word_rank ? `(rank #${s.unknown_word_rank})` : ""}
                </div>
            ` : ""}
            <div class="card-actions">
                <button class="btn-keep" onclick="keepSentence(${s.id})">🟢 Keep</button>
                <button class="btn-delete" onclick="deleteSentence(${s.id})">🔴 Delete</button>
                ${s.unknown_word ? `<button onclick="markWordKnown(${s.id})">📖 I Know This</button>` : ""}
            </div>
        </div>
    `).join("");
}

function highlightUnknown(text, unknownWord) {
    if (!unknownWord) return escapeHtml(text);
    // Highlight the unknown word with special styling
    const escaped = escapeHtml(unknownWord);
    const textEscaped = escapeHtml(text);
    return textEscaped.replace(
        new RegExp(`(${escaped.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'g'),
        '<span class="unknown-word-highlight">$1</span>'
    );
}

function statusLabel(status) {
    const labels = {
        i1: "i+1",
        i0: "known",
        kept: "kept",
        deleted: "deleted",
        stashed: "stashed",
    };
    return labels[status] || status;
}

// ============================================================
// Actions
// ============================================================

async function keepSentence(id) {
    await updateSentence(id, "kept");
}

async function deleteSentence(id) {
    await updateSentence(id, "deleted");
}

async function updateSentence(id, status) {
    try {
        const resp = await fetch(`/api/sentences/${id}`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ status }),
        });
        if (!resp.ok) {
            console.error(`Failed to update sentence ${id}: ${resp.status}`);
            return;
        }
        // Update the card inline
        const card = document.getElementById(`sentence-${id}`);
        if (card) {
            const badge = card.querySelector(".status-badge");
            if (badge) {
                badge.className = `status-badge ${status}`;
                badge.textContent = statusLabel(status);
            }
        }
        // Reload video list to update counts
        loadVideos();
    } catch (err) {
        console.error(`Error updating sentence:`, err);
    }
}

async function markWordKnown(id) {
    try {
        const resp = await fetch(`/api/sentences/${id}/iknowthis`, {
            method: "PATCH",
        });
        if (!resp.ok) {
            const data = await resp.json();
            alert(data.error || "Failed to mark word as known");
            return;
        }
        const data = await resp.json();
        // Reload sentences to reflect reclassification
        await loadSentences();
        loadVideos();
    } catch (err) {
        console.error(`Error marking word known:`, err);
    }
}

// ============================================================
// Mining
// ============================================================

function setupUrlInput() {
    const input = document.getElementById("url-input");
    input.addEventListener("keydown", (e) => {
        if (e.key === "Enter") mineVideo();
    });
}

async function mineVideo() {
    const input = document.getElementById("url-input");
    const btn = document.getElementById("mine-btn");
    const status = document.getElementById("mine-status");
    const url = input.value.trim();

    if (!url) {
        status.textContent = "Please enter a YouTube URL.";
        return;
    }

    btn.disabled = true;
    status.textContent = "⏳ Mining...";

    try {
        const resp = await fetch("/api/videos/mine", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ url }),
        });

        const data = await resp.json();

        if (!resp.ok) {
            status.textContent = `❌ ${data.error || "Failed to mine video"}`;
            btn.disabled = false;
            return;
        }

        status.textContent = `✅ Done! ${data.total_sentences} sentences, ${data.i1_count} i+1.`;
        input.value = "";

        // Reload video list and select the new video
        await loadVideos();
        if (data.video_id) {
            currentVideoId = data.video_id;
        }
        highlightActiveVideo();
        await loadSentences();
    } catch (err) {
        status.textContent = `❌ Network error: ${err.message}`;
    } finally {
        btn.disabled = false;
    }
}

// ============================================================
// Tabs
// ============================================================

function setupTabs() {
    document.querySelectorAll(".tab").forEach(tab => {
        tab.addEventListener("click", () => {
            currentStatusFilter = tab.dataset.status;
            document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
            tab.classList.add("active");
            loadSentences();
        });
    });
}

function resetTabs() {
    document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
    const allTab = document.querySelector('.tab[data-status="all"]');
    if (allTab) allTab.classList.add("active");
    currentStatusFilter = "all";
}

// ============================================================
// Helpers
// ============================================================

function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
}
