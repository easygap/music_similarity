// SoundMatch frontend controller ------------------------------------------
// Wires the upload form, loading/results state, audio playback with the
// waveform visualizer, radar chart, history, theme + i18n toggles, and
// share/export controls. Plain ES2019, no build step.

(function () {
  "use strict";

  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => Array.from(document.querySelectorAll(sel));

  const MAX_UPLOAD_BYTES = 25 * 1024 * 1024;
  const ALLOWED_EXT = new Set([".wav", ".mp3", ".flac", ".ogg", ".m4a"]);
  const HISTORY_KEY = "soundmatch.history.v1";
  const HISTORY_LIMIT = 5;
  const THEME_KEY = "soundmatch.theme";

  // ----------------------------------------------------------------------
  // DOM
  // ----------------------------------------------------------------------
  const dropzone = $("#dropzone");
  const fileInput = $("#file-input");
  const filenameDisplay = $("#filename-display");
  const dropzoneError = $("#dropzone-error");
  const analyzeBtn = $("#analyze-btn");
  const form = $("#upload-form");
  const topNSelect = $("#top-n");

  const loadingSection = $("#loading");
  const loadingStep = $("#loading-step");
  const loadingElapsed = $("#loading-elapsed");

  const errorSection = $("#error");
  const errorMessage = $("#error-message");
  const errorRetryBtn = $("#error-retry");

  const resultsSection = $("#results");
  const resultsSubtitle = $("#results-subtitle");
  const audioSummary = $("#audio-summary");
  const radarCard = $("#radar-card");
  const radarHost = $("#radar-host");
  const hitList = $("#hit-list");

  const audioPlayer = $("#audio-player");
  const audioPlayerTitle = $("#audio-player-title");
  const audioPreview = $("#audio-preview");
  const waveformCanvas = $("#waveform");
  const playBtn = $("#play-btn");
  const audioTime = $("#audio-time");

  const resetBtn = $("#reset-btn");
  const copyLinkBtn = $("#copy-link-btn");
  const exportJsonBtn = $("#export-json-btn");
  const yearSpan = $("#year");

  const themeToggleBtn = $("#theme-toggle");
  const langToggleBtn = $("#lang-toggle");

  const historySection = $("#history");
  const historyList = $("#history-list");
  const historyClearBtn = $("#history-clear");

  const toastEl = $("#toast");

  // ----------------------------------------------------------------------
  // i18n helpers
  // ----------------------------------------------------------------------
  const t = (k, ...args) => (window.i18n ? window.i18n.t(k, ...args) : k);

  function rebuildLocalizedSelectOptions() {
    [...topNSelect.options].forEach((opt) => {
      opt.textContent = t("upload.topNOption", parseInt(opt.value, 10));
    });
  }

  window.addEventListener("i18n:change", () => {
    rebuildLocalizedSelectOptions();
    if (yearSpan) yearSpan.textContent = String(new Date().getFullYear());
    if (langToggleBtn) langToggleBtn.textContent = t("controls.langToggle");
    renderHistory();
    if (_lastResults) renderResults(_lastResults, /* preserveFile */ true);
    loadCatalogStat();
  });

  // ----------------------------------------------------------------------
  // Theme
  // ----------------------------------------------------------------------
  function applyTheme(next) {
    document.documentElement.setAttribute("data-theme", next);
    localStorage.setItem(THEME_KEY, next);
    // Repaint waveform with new colors.
    if (_waveform) _waveform.draw(_audioProgress);
  }
  themeToggleBtn.addEventListener("click", () => {
    const cur = document.documentElement.getAttribute("data-theme") || "dark";
    applyTheme(cur === "dark" ? "light" : "dark");
  });

  // ----------------------------------------------------------------------
  // Lang toggle
  // ----------------------------------------------------------------------
  langToggleBtn.addEventListener("click", () => {
    if (window.i18n) window.i18n.toggle();
  });

  // ----------------------------------------------------------------------
  // Year + catalog stat
  // ----------------------------------------------------------------------
  if (yearSpan) yearSpan.textContent = String(new Date().getFullYear());

  async function loadCatalogStat() {
    try {
      const res = await fetch("/api/catalog");
      if (!res.ok) throw new Error("offline");
      const data = await res.json();
      const el = $("#stat-catalog");
      if (el) {
        el.textContent =
          window.i18n && window.i18n.lang() === "en"
            ? data.catalog_size.toLocaleString("en-US")
            : `${data.catalog_size.toLocaleString("ko-KR")}곡`;
      }
    } catch {
      const el = $("#stat-catalog");
      if (el) el.textContent = window.i18n && window.i18n.lang() === "en" ? "Many" : "다수";
    }
  }
  loadCatalogStat();
  rebuildLocalizedSelectOptions();
  if (langToggleBtn) langToggleBtn.textContent = t("controls.langToggle");

  // ----------------------------------------------------------------------
  // Toast
  // ----------------------------------------------------------------------
  let _toastTimer = null;
  function toast(message) {
    if (!toastEl) return;
    clearTimeout(_toastTimer);
    toastEl.textContent = message;
    toastEl.classList.remove("hidden");
    requestAnimationFrame(() => toastEl.classList.add("is-show"));
    _toastTimer = setTimeout(() => {
      toastEl.classList.remove("is-show");
      setTimeout(() => toastEl.classList.add("hidden"), 220);
    }, 1800);
  }

  // ----------------------------------------------------------------------
  // File selection + validation
  // ----------------------------------------------------------------------
  let selectedFile = null;

  function fileExt(name) {
    const dot = (name || "").lastIndexOf(".");
    return dot === -1 ? "" : (name || "").slice(dot).toLowerCase();
  }

  function setFile(file) {
    selectedFile = file || null;
    dropzoneError.classList.add("hidden");
    dropzoneError.textContent = "";

    if (!selectedFile) {
      filenameDisplay.textContent = t("upload.dropHint");
      analyzeBtn.setAttribute("disabled", "");
      return;
    }

    // Client-side validation
    const ext = fileExt(selectedFile.name);
    if (!ALLOWED_EXT.has(ext)) {
      dropzoneError.textContent = t("upload.validation.badType");
      dropzoneError.classList.remove("hidden");
      selectedFile = null;
      filenameDisplay.textContent = t("upload.dropHint");
      analyzeBtn.setAttribute("disabled", "");
      return;
    }
    if (selectedFile.size > MAX_UPLOAD_BYTES) {
      dropzoneError.textContent = t(
        "upload.validation.tooBig",
        Math.floor(MAX_UPLOAD_BYTES / (1024 * 1024)),
      );
      dropzoneError.classList.remove("hidden");
      selectedFile = null;
      filenameDisplay.textContent = t("upload.dropHint");
      analyzeBtn.setAttribute("disabled", "");
      return;
    }

    filenameDisplay.textContent = `${selectedFile.name} · ${formatBytes(selectedFile.size)}`;
    analyzeBtn.removeAttribute("disabled");
  }

  function formatBytes(bytes) {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  fileInput.addEventListener("change", (e) => setFile(e.target.files && e.target.files[0]));

  ["dragenter", "dragover"].forEach((ev) =>
    dropzone.addEventListener(ev, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.add("is-drag");
    }),
  );
  ["dragleave", "drop"].forEach((ev) =>
    dropzone.addEventListener(ev, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.remove("is-drag");
    }),
  );
  dropzone.addEventListener("drop", (e) => {
    const files = e.dataTransfer && e.dataTransfer.files;
    if (files && files.length) {
      fileInput.files = files;
      setFile(files[0]);
    }
  });
  // Keyboard support: pressing Enter/Space on the focused dropzone opens picker.
  dropzone.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      fileInput.click();
    }
  });

  // ----------------------------------------------------------------------
  // Submit -> analyze
  // ----------------------------------------------------------------------
  let _lastResults = null;
  let _lastFile = null;

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!selectedFile) return;
    await runAnalysis(selectedFile);
  });

  errorRetryBtn.addEventListener("click", () => {
    if (_lastFile) runAnalysis(_lastFile);
    else form.scrollIntoView({ behavior: "smooth", block: "start" });
  });

  async function runAnalysis(file) {
    hideAll();
    showSkeletonResults();
    startLoadingMessages();
    _lastFile = file;

    const formData = new FormData();
    formData.append("file", file);
    const topN = parseInt(topNSelect.value, 10) || 5;

    try {
      const res = await fetch(`/api/analyze?top_n=${topN}`, {
        method: "POST",
        body: formData,
      });
      stopLoadingMessages();

      if (!res.ok) {
        if (res.status === 429) throw new Error(t("error.rateLimit"));
        const text = await safeJsonOrText(res);
        throw new Error(text || `Server error (${res.status})`);
      }

      const data = await res.json();
      _lastResults = data;
      addToHistory(data);
      await setAudioPreview(file);
      renderResults(data);
    } catch (err) {
      stopLoadingMessages();
      showError(err.message || String(err));
    }
  }

  function hideAll() {
    loadingSection.classList.add("hidden");
    errorSection.classList.add("hidden");
    resultsSection.classList.add("hidden");
  }

  function showSkeletonResults() {
    // Render 3 skeleton cards inside the results section so the layout
    // doesn't jump when real data arrives.
    resultsSection.classList.remove("hidden");
    audioSummary.innerHTML = "";
    radarCard.classList.add("hidden");
    audioPlayer.classList.add("hidden");
    resultsSubtitle.textContent = "";
    hitList.innerHTML = "";
    const skelTmpl = $("#skeleton-template");
    for (let i = 0; i < 3; i++) hitList.appendChild(skelTmpl.content.firstElementChild.cloneNode(true));
    // Also show the loading-card under the form for the textual status.
    loadingSection.classList.remove("hidden");
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
  // Loading status (steps + elapsed)
  // ----------------------------------------------------------------------
  let _loadingTimer = null;
  let _loadingStartedAt = 0;
  function startLoadingMessages() {
    const steps = t("loading.steps") || ["…"];
    let i = 0;
    _loadingStartedAt = performance.now();
    loadingStep.textContent = steps[0];
    loadingElapsed.textContent = t("loading.elapsed", 0);
    _loadingTimer = setInterval(() => {
      i = (i + 1) % steps.length;
      loadingStep.textContent = steps[i];
      const elapsed = (performance.now() - _loadingStartedAt) / 1000;
      const fmt = elapsed >= 1 ? elapsed.toFixed(1) : elapsed.toFixed(2);
      loadingElapsed.textContent = t("loading.elapsed", fmt);
      if (elapsed > 15) {
        loadingElapsed.textContent = `${t("loading.elapsed", fmt)} · ${t("loading.late")}`;
      }
    }, 700);
  }
  function stopLoadingMessages() {
    if (_loadingTimer) {
      clearInterval(_loadingTimer);
      _loadingTimer = null;
    }
  }

  // ----------------------------------------------------------------------
  // Audio preview (HTML5 <audio> + waveform)
  // ----------------------------------------------------------------------
  let _audioPreviewUrl = null;
  let _waveform = null;
  let _audioProgress = 0;
  let _audioRaf = null;

  async function setAudioPreview(file) {
    if (_audioPreviewUrl) {
      URL.revokeObjectURL(_audioPreviewUrl);
      _audioPreviewUrl = null;
    }
    if (_audioRaf) {
      cancelAnimationFrame(_audioRaf);
      _audioRaf = null;
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

    if (window.SoundMatchVisualizers) {
      _waveform = new window.SoundMatchVisualizers.WaveformBar(waveformCanvas);
      try {
        await _waveform.load(file);
      } catch {
        // ignore decoding failures, waveform stays empty.
      }
    }
    updateAudioTime();
  }

  audioPreview.addEventListener("loadedmetadata", updateAudioTime);
  audioPreview.addEventListener("timeupdate", () => {
    if (audioPreview.duration > 0) {
      _audioProgress = audioPreview.currentTime / audioPreview.duration;
      if (_waveform) _waveform.draw(_audioProgress);
    }
    updateAudioTime();
  });
  audioPreview.addEventListener("play", () => {
    playBtn.dataset.playing = "true";
  });
  audioPreview.addEventListener("pause", () => {
    playBtn.dataset.playing = "false";
  });
  audioPreview.addEventListener("ended", () => {
    playBtn.dataset.playing = "false";
    _audioProgress = 0;
    if (_waveform) _waveform.draw(0);
  });

  playBtn.addEventListener("click", () => {
    if (!audioPreview.src) return;
    if (audioPreview.paused) audioPreview.play();
    else audioPreview.pause();
  });

  waveformCanvas.addEventListener("click", (e) => {
    if (!audioPreview.duration) return;
    const rect = waveformCanvas.getBoundingClientRect();
    const ratio = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
    audioPreview.currentTime = ratio * audioPreview.duration;
  });

  function fmtTime(secs) {
    if (!isFinite(secs)) return "0:00";
    const m = Math.floor(secs / 60);
    const s = Math.floor(secs % 60).toString().padStart(2, "0");
    return `${m}:${s}`;
  }
  function updateAudioTime() {
    audioTime.textContent = `${fmtTime(audioPreview.currentTime)} / ${fmtTime(audioPreview.duration || 0)}`;
  }

  // ----------------------------------------------------------------------
  // Render results
  // ----------------------------------------------------------------------
  function renderResults(data, preserveFile = false) {
    hideAll();
    resultsSection.classList.remove("hidden");

    const timing = data.timing || {};
    const total = (timing.feature_extraction_seconds || 0) + (timing.similarity_seconds || 0);
    const filename = escapeHtml(data.filename || "");
    resultsSubtitle.innerHTML = `
      <strong>${filename}</strong> · ${t("results.subtitlePrefix")}
      ${data.catalog_size.toLocaleString()}${t("results.subtitleSongs")}
      ${total.toFixed(2)}${t("results.subtitleSeconds")}
    `;

    renderSummary(data.summary || {});

    // Empty-state branch
    if (!Array.isArray(data.results) || data.results.length === 0) {
      hitList.innerHTML = `
        <div class="empty-results card">
          <strong>${escapeHtml(t("results.emptyTitle"))}</strong>
          <p>${escapeHtml(t("results.emptyHint"))}</p>
        </div>`;
      radarCard.classList.add("hidden");
      return;
    }

    // Radar chart vs top match.
    const top = data.results[0];
    if (top && top.match_summary && window.SoundMatchVisualizers) {
      const radarData = window.SoundMatchVisualizers.radarFromSummaries(
        data.summary,
        top.match_summary,
      );
      window.SoundMatchVisualizers.renderRadarChart(radarHost, radarData);
      radarCard.classList.remove("hidden");
    } else {
      radarCard.classList.add("hidden");
    }

    hitList.innerHTML = "";
    const tmpl = $("#hit-template");
    data.results.forEach((hit, idx) => {
      const li = tmpl.content.firstElementChild.cloneNode(true);
      li.querySelector(".rank-num").textContent = hit.rank;
      li.querySelector(".rank-label").textContent = t("results.hitRankUnit");
      li.querySelector(".hit-title").textContent = hit.title;
      li.querySelector(".hit-artist").textContent = hit.artist;
      li.querySelector(".hit-percent-num").textContent = hit.similarity_percent.toFixed(1);
      li.querySelector(".hit-percent-label").textContent = t("results.hitSimilarityLabel");

      const bar = li.querySelector(".hit-bar");
      bar.setAttribute("aria-valuenow", String(Math.round(hit.similarity_percent)));
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
            <span class="group-score">${t("results.groupMatchPrefix")} ${Math.round((g.match_score || 0) * 100)}%</span>
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

    if (!preserveFile && _lastFile && audioPlayer.classList.contains("hidden")) {
      setAudioPreview(_lastFile);
    }

    resultsSection.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function renderSummary(summary) {
    const items = [
      { labelKey: "summary.tempo", key: "tempo_bpm", unit: "BPM" },
      { labelKey: "summary.energy", key: "energy_rms", unit: "" },
      { labelKey: "summary.brightness", key: "brightness", unit: "Hz" },
      { labelKey: "summary.noisiness", key: "noisiness", unit: "" },
      { labelKey: "summary.harmony", key: "harmony_ratio", unit: "" },
      { labelKey: "summary.chroma", key: "chroma", unit: "" },
    ];
    audioSummary.innerHTML = items
      .map((it) => {
        const v = summary[it.key];
        if (v === undefined || v === null) return "";
        const displayVal = typeof v === "number" ? formatNumber(v) : v;
        return `
          <div class="metric">
            <div class="metric-label">${escapeHtml(t(it.labelKey))}</div>
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
    return String(str == null ? "" : str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function renderInlineMarkdown(text) {
    return escapeHtml(text).replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  }

  // ----------------------------------------------------------------------
  // Reset
  // ----------------------------------------------------------------------
  resetBtn.addEventListener("click", () => {
    setFile(null);
    setAudioPreview(null);
    _lastResults = null;
    _lastFile = null;
    fileInput.value = "";
    hideAll();
    form.scrollIntoView({ behavior: "smooth", block: "start" });
  });

  window.addEventListener("beforeunload", () => setAudioPreview(null));

  // ----------------------------------------------------------------------
  // Share / Export
  // ----------------------------------------------------------------------
  copyLinkBtn.addEventListener("click", async () => {
    if (!_lastResults) return;
    const tracks = _lastResults.results
      .slice(0, 3)
      .map((r) => `${r.rank}. ${r.title} – ${r.artist} (${r.similarity_percent.toFixed(1)}%)`)
      .join("\n");
    const shareText = `SoundMatch · ${_lastResults.filename}\n\n${tracks}\n\n${location.origin}`;
    try {
      await navigator.clipboard.writeText(shareText);
      toast(t("results.copied"));
    } catch {
      toast(shareText);
    }
  });

  exportJsonBtn.addEventListener("click", () => {
    if (!_lastResults) return;
    const payload = JSON.stringify(_lastResults, null, 2);
    const blob = new Blob([payload], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    const baseName = (_lastResults.filename || "soundmatch").replace(/\.[^.]+$/, "");
    a.download = `${baseName}.soundmatch.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(() => URL.revokeObjectURL(url), 500);
  });

  // ----------------------------------------------------------------------
  // History (localStorage)
  // ----------------------------------------------------------------------
  function readHistory() {
    try {
      const raw = localStorage.getItem(HISTORY_KEY);
      if (!raw) return [];
      const parsed = JSON.parse(raw);
      return Array.isArray(parsed) ? parsed : [];
    } catch {
      return [];
    }
  }
  function writeHistory(items) {
    try {
      localStorage.setItem(HISTORY_KEY, JSON.stringify(items.slice(0, HISTORY_LIMIT)));
    } catch {}
  }
  function addToHistory(data) {
    const items = readHistory();
    const entry = {
      ts: Date.now(),
      filename: data.filename,
      topTitle: data.results && data.results[0] && data.results[0].title,
      topArtist: data.results && data.results[0] && data.results[0].artist,
      topPercent: data.results && data.results[0] && data.results[0].similarity_percent,
      data,
    };
    items.unshift(entry);
    writeHistory(items);
    renderHistory();
  }
  function renderHistory() {
    const items = readHistory();
    if (!items.length) {
      historySection.classList.add("hidden");
      return;
    }
    historySection.classList.remove("hidden");
    historyList.innerHTML = items
      .map((it, idx) => {
        const when = new Date(it.ts);
        const label = when.toLocaleString(window.i18n && window.i18n.lang() === "en" ? "en-US" : "ko-KR", {
          month: "short",
          day: "numeric",
          hour: "2-digit",
          minute: "2-digit",
        });
        const top = it.topTitle
          ? `${escapeHtml(it.topTitle)} · ${it.topPercent ? it.topPercent.toFixed(1) : "?"}%`
          : "";
        return `
          <li>
            <div>
              <div class="history-name">${escapeHtml(it.filename || "—")}</div>
              <div class="history-meta">${escapeHtml(label)} ${top ? " · " + top : ""}</div>
            </div>
            <button type="button" class="history-load" data-idx="${idx}">${escapeHtml(
              t("history.title") === "Recent analyses" ? "View" : "보기",
            )}</button>
          </li>`;
      })
      .join("");
    historyList.querySelectorAll(".history-load").forEach((btn) => {
      btn.addEventListener("click", () => {
        const idx = parseInt(btn.dataset.idx, 10);
        const entry = readHistory()[idx];
        if (entry && entry.data) {
          _lastResults = entry.data;
          _lastFile = null;
          audioPlayer.classList.add("hidden");
          renderResults(entry.data, true);
        }
      });
    });
  }
  historyClearBtn.addEventListener("click", () => {
    if (!confirm(t("history.confirm"))) return;
    writeHistory([]);
    renderHistory();
  });
  renderHistory();
})();
