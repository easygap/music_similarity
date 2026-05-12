// SoundMatch frontend logic ------------------------------------------------
// Plain ES2019 — no build step required.

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));

const dropzone = $("#dropzone");
const fileInput = $("#file-input");
const filenameDisplay = $("#filename-display");
const analyzeBtn = $("#analyze-btn");
const form = $("#upload-form");

const loadingSection = $("#loading");
const loadingStep = $("#loading-step");
const errorSection = $("#error");
const errorMessage = $("#error-message");
const resultsSection = $("#results");
const audioSummary = $("#audio-summary");
const hitList = $("#hit-list");
const resultsSubtitle = $("#results-subtitle");

const audioPlayer = $("#audio-player");
const audioPreview = $("#audio-preview");
const audioPlayerTitle = $("#audio-player-title");
const resetBtn = $("#reset-btn");
const yearSpan = $("#year");

let _audioPreviewUrl = null;
function setAudioPreview(file) {
  if (_audioPreviewUrl) {
    URL.revokeObjectURL(_audioPreviewUrl);
    _audioPreviewUrl = null;
  }
  if (!file) {
    audioPreview.removeAttribute("src");
    audioPlayer.classList.add("hidden");
    return;
  }
  _audioPreviewUrl = URL.createObjectURL(file);
  audioPreview.src = _audioPreviewUrl;
  audioPlayerTitle.textContent = file.name;
  audioPlayer.classList.remove("hidden");
}

if (yearSpan) yearSpan.textContent = new Date().getFullYear();

// ----------------------------------------------------------------------
// Catalog stat
// ----------------------------------------------------------------------
async function loadCatalogStat() {
  try {
    const res = await fetch("/api/catalog");
    if (!res.ok) throw new Error("offline");
    const data = await res.json();
    const el = $("#stat-catalog");
    if (el) {
      el.textContent = `${data.catalog_size.toLocaleString("ko-KR")}곡`;
    }
  } catch {
    const el = $("#stat-catalog");
    if (el) el.textContent = "다수";
  }
}
loadCatalogStat();

// ----------------------------------------------------------------------
// File selection
// ----------------------------------------------------------------------
let selectedFile = null;

function setFile(file) {
  selectedFile = file || null;
  if (selectedFile) {
    filenameDisplay.textContent = `${selectedFile.name} · ${formatBytes(selectedFile.size)}`;
    analyzeBtn.removeAttribute("disabled");
  } else {
    filenameDisplay.textContent = "최대 30초가 분석에 사용됩니다.";
    analyzeBtn.setAttribute("disabled", "");
  }
}

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

fileInput.addEventListener("change", (e) => {
  setFile(e.target.files && e.target.files[0]);
});

// Drag-and-drop
["dragenter", "dragover"].forEach((ev) =>
  dropzone.addEventListener(ev, (e) => {
    e.preventDefault();
    e.stopPropagation();
    dropzone.classList.add("is-drag");
  })
);
["dragleave", "drop"].forEach((ev) =>
  dropzone.addEventListener(ev, (e) => {
    e.preventDefault();
    e.stopPropagation();
    dropzone.classList.remove("is-drag");
  })
);
dropzone.addEventListener("drop", (e) => {
  const files = e.dataTransfer && e.dataTransfer.files;
  if (files && files.length) {
    fileInput.files = files;
    setFile(files[0]);
  }
});

// ----------------------------------------------------------------------
// Submit -> analyze
// ----------------------------------------------------------------------
form.addEventListener("submit", async (e) => {
  e.preventDefault();
  if (!selectedFile) return;

  hideAll();
  loadingSection.classList.remove("hidden");
  startLoadingMessages();

  const formData = new FormData();
  formData.append("file", selectedFile);
  const topN = parseInt($("#top-n").value, 10) || 5;

  try {
    const res = await fetch(`/api/analyze?top_n=${topN}`, {
      method: "POST",
      body: formData,
    });
    stopLoadingMessages();

    if (!res.ok) {
      const text = await safeJsonOrText(res);
      throw new Error(text || `서버 오류 (${res.status})`);
    }

    const data = await res.json();
    setAudioPreview(selectedFile);
    renderResults(data);
  } catch (err) {
    stopLoadingMessages();
    showError(err.message || String(err));
  }
});

function hideAll() {
  loadingSection.classList.add("hidden");
  errorSection.classList.add("hidden");
  resultsSection.classList.add("hidden");
}

async function safeJsonOrText(res) {
  try {
    const j = await res.json();
    return j.detail || j.message || JSON.stringify(j);
  } catch {
    try {
      return await res.text();
    } catch {
      return null;
    }
  }
}

function showError(msg) {
  hideAll();
  errorMessage.textContent = msg;
  errorSection.classList.remove("hidden");
  errorSection.scrollIntoView({ behavior: "smooth", block: "start" });
}

// ----------------------------------------------------------------------
// Loading message cycler
// ----------------------------------------------------------------------
const LOADING_STEPS = [
  "librosa · 오디오 디코딩",
  "RMS · BPM · 제로 크로싱 추출",
  "스펙트럴 센트로이드 · 롤오프 · 대역폭 계산",
  "20차원 MFCC 계산",
  "StandardScaler · 정규화",
  "cosine_similarity · 카탈로그 비교",
  "닮은 이유 분석 중",
];
let _loadingTimer = null;
function startLoadingMessages() {
  let i = 0;
  loadingStep.textContent = LOADING_STEPS[0];
  _loadingTimer = setInterval(() => {
    i = (i + 1) % LOADING_STEPS.length;
    loadingStep.textContent = LOADING_STEPS[i];
  }, 900);
}
function stopLoadingMessages() {
  if (_loadingTimer) {
    clearInterval(_loadingTimer);
    _loadingTimer = null;
  }
}

// ----------------------------------------------------------------------
// Render results
// ----------------------------------------------------------------------
function renderResults(data) {
  hideAll();

  // Subtitle with metadata
  const timing = data.timing || {};
  const total = (timing.feature_extraction_seconds || 0) + (timing.similarity_seconds || 0);
  resultsSubtitle.innerHTML = `
    <strong>${escapeHtml(data.filename || "업로드된 파일")}</strong> ·
    카탈로그 ${data.catalog_size.toLocaleString("ko-KR")}곡 비교 ·
    총 ${total.toFixed(2)}초 소요
  `;

  // Summary metrics
  renderSummary(data.summary || {});

  // Hits
  hitList.innerHTML = "";
  const tmpl = $("#hit-template");
  (data.results || []).forEach((hit, idx) => {
    const li = tmpl.content.firstElementChild.cloneNode(true);
    li.querySelector(".rank-num").textContent = hit.rank;
    li.querySelector(".hit-title").textContent = hit.title;
    li.querySelector(".hit-artist").textContent = hit.artist;
    li.querySelector(".hit-percent-num").textContent = hit.similarity_percent.toFixed(1);

    const fillEl = li.querySelector(".hit-bar-fill");
    setTimeout(() => {
      fillEl.style.width = `${Math.max(2, hit.similarity_percent)}%`;
    }, 60 + idx * 80);

    li.querySelector(".hit-summary").innerHTML = renderInlineMarkdown(hit.reason.summary || "");

    const groupsEl = li.querySelector(".hit-groups");
    groupsEl.innerHTML = "";
    (hit.reason.groups || []).forEach((g) => {
      const gli = document.createElement("li");
      gli.innerHTML = `
        <div class="group-head">
          <span class="group-label">${escapeHtml(g.label)}</span>
          <span class="group-score">match ${Math.round((g.match_score || 0) * 100)}%</span>
        </div>
        <p class="group-summary">${escapeHtml(g.summary || "")}</p>
        <ul class="group-detail">${(g.detail || []).map((d) => `<li>${escapeHtml(d)}</li>`).join("")}</ul>
      `;
      groupsEl.appendChild(gli);
    });

    li.querySelector('[data-link="yt"]').href = hit.youtube_search_url;
    li.querySelector('[data-link="sp"]').href = hit.spotify_search_url;

    hitList.appendChild(li);
  });

  resultsSection.classList.remove("hidden");
  resultsSection.scrollIntoView({ behavior: "smooth", block: "start" });
}

function renderSummary(summary) {
  const items = [
    { label: "Tempo", key: "tempo_bpm", unit: "BPM" },
    { label: "에너지 (RMS)", key: "energy_rms", unit: "" },
    { label: "밝기", key: "brightness", unit: "Hz" },
    { label: "거친 정도", key: "noisiness", unit: "" },
    { label: "화성/타악기 비율", key: "harmony_ratio", unit: "" },
    { label: "크로마", key: "chroma", unit: "" },
  ];
  audioSummary.innerHTML = items
    .map((it) => {
      const v = summary[it.key];
      if (v === undefined || v === null) return "";
      const displayVal = typeof v === "number" ? formatNumber(v) : v;
      return `
        <div class="metric">
          <div class="metric-label">${escapeHtml(it.label)}</div>
          <div class="metric-value">${displayVal}<span class="metric-unit">${escapeHtml(it.unit)}</span></div>
        </div>`;
    })
    .join("");
}

function formatNumber(n) {
  if (!isFinite(n)) return "—";
  if (Math.abs(n) >= 100) return n.toFixed(0);
  if (Math.abs(n) >= 1) return n.toFixed(1);
  return n.toFixed(3);
}

function escapeHtml(str) {
  return String(str ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

// Minimal **bold** -> <strong> rendering for reason summaries.
function renderInlineMarkdown(text) {
  return escapeHtml(text).replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
}

// ----------------------------------------------------------------------
// Reset
// ----------------------------------------------------------------------
resetBtn.addEventListener("click", () => {
  setFile(null);
  setAudioPreview(null);
  fileInput.value = "";
  hideAll();
  form.scrollIntoView({ behavior: "smooth", block: "start" });
});

// Clean up the blob URL on unload.
window.addEventListener("beforeunload", () => setAudioPreview(null));
