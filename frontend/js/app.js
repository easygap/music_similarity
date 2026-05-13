// SoundMatch 메인 컨트롤러 -------------------------------------------------
// 업로드 폼, 로딩/결과 상태, 파형/레이더 시각화, 히스토리, 테마/언어 토글,
// 공유/다운로드, 키보드 단축키까지 묶어서 처리한다. 빌드 스텝 없는 plain JS.

(function () {
  "use strict";

  const $ = (sel) => document.querySelector(sel);

  const MAX_UPLOAD_BYTES = 25 * 1024 * 1024;
  const ALLOWED_EXT = new Set([".wav", ".mp3", ".flac", ".ogg", ".m4a"]);
  const HISTORY_KEY = "soundmatch.history.v1";
  const HISTORY_LIMIT = 5;
  const THEME_KEY = "soundmatch.theme";

  // ----------------------------------------------------------------------
  // DOM 참조
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
  // i18n 헬퍼
  // ----------------------------------------------------------------------
  const t = (k, ...args) => (window.i18n ? window.i18n.t(k, ...args) : k);

  function rebuildLocalizedSelectOptions() {
    // 언어가 바뀌면 select 옵션 텍스트도 다시 그려야 한다.
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
  // 테마 / 언어
  // ----------------------------------------------------------------------
  function applyTheme(next) {
    document.documentElement.setAttribute("data-theme", next);
    localStorage.setItem(THEME_KEY, next);
    // 파형 색이 CSS 변수에 묶여있으므로 테마 바뀌면 다시 그려준다.
    if (_waveform) _waveform.draw(_audioProgress);
  }
  themeToggleBtn.addEventListener("click", () => {
    const cur = document.documentElement.getAttribute("data-theme") || "dark";
    applyTheme(cur === "dark" ? "light" : "dark");
  });
  langToggleBtn.addEventListener("click", () => {
    if (window.i18n) window.i18n.toggle();
  });

  // ----------------------------------------------------------------------
  // 카탈로그 통계 + footer 연도
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
      // API 가 죽었어도 사이트 자체는 계속 보이게.
      const el = $("#stat-catalog");
      if (el) el.textContent = window.i18n && window.i18n.lang() === "en" ? "Many" : "다수";
    }
  }
  loadCatalogStat();
  rebuildLocalizedSelectOptions();
  if (langToggleBtn) langToggleBtn.textContent = t("controls.langToggle");

  // ----------------------------------------------------------------------
  // 토스트
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
  // 파일 선택 + 클라이언트 검증
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

    // 서버까지 가지 않고도 잡을 수 있는 명백한 실수들은 미리 막아준다.
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

  // 드래그 앤 드롭
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
  // 키보드 접근성: 드롭존에 포커스 후 Enter/Space 누르면 파일 다이얼로그 오픈.
  dropzone.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      fileInput.click();
    }
  });

  // ----------------------------------------------------------------------
  // 제출 → 분석 요청
  // ----------------------------------------------------------------------
  let _lastResults = null;
  let _lastFile = null;
  let _analysisInFlight = false;

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
    _analysisInFlight = true;

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
        throw new Error(text || `서버 오류 (${res.status})`);
      }

      const data = await res.json();
      _lastResults = data;
      addToHistory(data);
      await setAudioPreview(file);
      renderResults(data);
    } catch (err) {
      stopLoadingMessages();
      showError(err.message || String(err));
    } finally {
      _analysisInFlight = false;
    }
  }

  function hideAll() {
    loadingSection.classList.add("hidden");
    errorSection.classList.add("hidden");
    resultsSection.classList.add("hidden");
  }

  function showSkeletonResults() {
    // 실제 결과가 도착하기 전에 같은 자리에 스켈레톤 카드 3장을 깔아둔다.
    // 결과가 도착하면 그대로 교체되므로 레이아웃이 튀지 않는다.
    resultsSection.classList.remove("hidden");
    audioSummary.innerHTML = "";
    radarCard.classList.add("hidden");
    audioPlayer.classList.add("hidden");
    resultsSubtitle.textContent = "";
    hitList.innerHTML = "";
    const skelTmpl = $("#skeleton-template");
    for (let i = 0; i < 3; i++) hitList.appendChild(skelTmpl.content.firstElementChild.cloneNode(true));
    loadingSection.classList.remove("hidden");
  }

  async function safeJsonOrText(res) {
    // 에러 응답이 JSON 일 수도 있고 plain text 일 수도 있다.
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
  // 로딩 단계 + 경과 시간 표시
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
      // 15초 넘어가면 "조금만 더..." 같은 안심 멘트 같이 노출.
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
  // 업로드 음원 재생 (HTML5 audio + 파형)
  // ----------------------------------------------------------------------
  let _audioPreviewUrl = null;
  let _waveform = null;
  let _audioProgress = 0;

  async function setAudioPreview(file) {
    // 기존 blob URL 은 메모리 해제.
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

    if (window.SoundMatchVisualizers) {
      _waveform = new window.SoundMatchVisualizers.WaveformBar(waveformCanvas);
      try {
        await _waveform.load(file);
      } catch {
        // 디코딩 실패해도 페이지는 계속 동작해야 함. 파형만 비어있게 둔다.
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
  audioPreview.addEventListener("play", () => { playBtn.dataset.playing = "true"; });
  audioPreview.addEventListener("pause", () => { playBtn.dataset.playing = "false"; });
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
    // 파형의 클릭 위치(0~1)로 currentTime 이동.
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
  // 결과 렌더링
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

    // 결과가 0건일 때는 친절한 빈 상태 카드로 대체.
    if (!Array.isArray(data.results) || data.results.length === 0) {
      hitList.innerHTML = `
        <div class="empty-results card">
          <strong>${escapeHtml(t("results.emptyTitle"))}</strong>
          <p>${escapeHtml(t("results.emptyHint"))}</p>
        </div>`;
      radarCard.classList.add("hidden");
      return;
    }

    // 1위 매칭과의 6축 레이더 차트.
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
      // 약간의 지연을 두고 채우면 transition 이 실제로 보인다.
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
    // 각 메트릭마다 title 속성으로 간단한 설명 툴팁을 달아준다.
    const items = [
      { labelKey: "summary.tempo", helpKey: "summary.tempoHelp", key: "tempo_bpm", unit: "BPM" },
      { labelKey: "summary.energy", helpKey: "summary.energyHelp", key: "energy_rms", unit: "" },
      { labelKey: "summary.brightness", helpKey: "summary.brightnessHelp", key: "brightness", unit: "Hz" },
      { labelKey: "summary.noisiness", helpKey: "summary.noisinessHelp", key: "noisiness", unit: "" },
      { labelKey: "summary.harmony", helpKey: "summary.harmonyHelp", key: "harmony_ratio", unit: "" },
      { labelKey: "summary.chroma", helpKey: "summary.chromaHelp", key: "chroma", unit: "" },
    ];
    audioSummary.innerHTML = items
      .map((it) => {
        const v = summary[it.key];
        if (v === undefined || v === null) return "";
        const displayVal = typeof v === "number" ? formatNumber(v) : v;
        const help = t(it.helpKey);
        return `
          <div class="metric" title="${escapeHtml(help)}">
            <div class="metric-label">
              ${escapeHtml(t(it.labelKey))}
              <span class="metric-info" aria-hidden="true">?</span>
            </div>
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
    // **bold** 만 지원하는 초간단 마크다운. summary 문자열 안에서만 사용.
    return escapeHtml(text).replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  }

  // ----------------------------------------------------------------------
  // 초기화
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

  window.addEventListener("beforeunload", (e) => {
    // blob URL 정리.
    setAudioPreview(null);
    // 분석 진행 중이면 실수 이탈을 한 번 막아준다.
    if (_analysisInFlight) {
      e.preventDefault();
      e.returnValue = t("loading.leaveWarn");
      return e.returnValue;
    }
  });

  // ----------------------------------------------------------------------
  // 공유 / 내보내기
  // ----------------------------------------------------------------------
  copyLinkBtn.addEventListener("click", async () => {
    if (!_lastResults) return;
    // 결과를 텍스트로 정리해 클립보드에 넣어준다 (Web Share API 가 없어도 동작).
    const tracks = _lastResults.results
      .slice(0, 3)
      .map((r) => `${r.rank}. ${r.title} – ${r.artist} (${r.similarity_percent.toFixed(1)}%)`)
      .join("\n");
    const shareText = `SoundMatch · ${_lastResults.filename}\n\n${tracks}\n\n${location.origin}`;
    try {
      await navigator.clipboard.writeText(shareText);
      toast(t("results.copied"));
    } catch {
      // 클립보드 API 가 없으면 토스트로 노출해 사용자가 직접 복사하게 한다.
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
  // 키보드 단축키
  //   "/"   : 파일 업로드에 포커스
  //   Esc   : 분석 결과 닫고 첫 화면으로
  //   Space : 결과 화면에서 재생/일시정지 (input 안에 있을 때는 동작 X)
  // ----------------------------------------------------------------------
  document.addEventListener("keydown", (e) => {
    const target = e.target;
    const isTyping =
      target &&
      (target.tagName === "INPUT" ||
        target.tagName === "TEXTAREA" ||
        target.tagName === "SELECT" ||
        target.isContentEditable);
    if (e.key === "/" && !isTyping) {
      e.preventDefault();
      fileInput.focus();
      dropzone.classList.add("is-drag");
      setTimeout(() => dropzone.classList.remove("is-drag"), 280);
    } else if (e.key === "Escape" && !resultsSection.classList.contains("hidden")) {
      resetBtn.click();
    } else if (e.key === " " && !isTyping && !resultsSection.classList.contains("hidden") && audioPreview.src) {
      e.preventDefault();
      if (audioPreview.paused) audioPreview.play();
      else audioPreview.pause();
    }
  });

  // ----------------------------------------------------------------------
  // 최근 분석 히스토리 (localStorage)
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
    } catch {
      // 사용자가 storage 비활성화한 경우 등 — 조용히 무시.
    }
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
            <button type="button" class="history-load" data-idx="${idx}">${escapeHtml(t("history.view"))}</button>
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
