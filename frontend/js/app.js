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
  const resultTagsEl = $("#result-tags");
  const audioSummary = $("#audio-summary");
  const radarCard = $("#radar-card");
  const radarHost = $("#radar-host");
  const hitList = $("#hit-list");

  const spectrogramCard = $("#spectrogram-card");
  const spectrogramHost = $("#spectrogram-host");
  const shareBtn = $("#share-btn");
  const audioPlayer = $("#audio-player");
  const audioPlayerTitle = $("#audio-player-title");
  const audioPreview = $("#audio-preview");
  const waveformCanvas = $("#waveform");
  const playBtn = $("#play-btn");
  const audioTime = $("#audio-time");

  const resetBtn = $("#reset-btn");
  const seedBackBtn = $("#seed-back-btn");
  const copyLinkBtn = $("#copy-link-btn");
  const copyShareUrlBtn = $("#copy-share-url-btn");
  const exportJsonBtn = $("#export-json-btn");
  const exportSvgBtn = $("#export-svg-btn");
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

  // hero stat 의 "평균 분석 시간" 을 실시간 latency P50 으로 갱신.
  // health 엔드포인트는 ring buffer 의 P50 을 같이 내려준다 — 샘플이 없으면 0.
  async function loadLatencyStat() {
    const el = $("#stat-latency");
    if (!el) return;
    try {
      const res = await fetch("/api/health");
      if (!res.ok) throw new Error("offline");
      const data = await res.json();
      const p50 = Number(data.analyze_latency_p50_seconds) || 0;
      if (p50 > 0) {
        // 1초 미만이면 "0.7s", 1초 이상이면 "~3s" 식으로.
        el.textContent = p50 < 1 ? `${p50.toFixed(1)}s` : `~${Math.round(p50)}s`;
      }
      // 샘플이 없으면 정적 기본값을 그대로 둔다.
    } catch {
      /* health 가 안 잡혀도 기본 문구 유지 */
    }
  }
  loadLatencyStat();
  rebuildLocalizedSelectOptions();
  if (langToggleBtn) langToggleBtn.textContent = t("controls.langToggle");

  // 카탈로그 일부 미리보기 — 메인 페이지 하단 정보용.
  // 첫 로드만 /sample 로 정렬된 12곡, 그 후 "다른 곡 보기" 누르면 /random 으로 무작위.
  async function loadCatalogPreview({ randomize = false } = {}) {
    const host = document.getElementById("catalog-list");
    if (!host) return;
    try {
      const url = randomize ? "/api/catalog/random?n=12" : "/api/catalog/sample?limit=12";
      const res = await fetch(url);
      if (!res.ok) throw new Error("fail");
      const data = await res.json();
      if (!Array.isArray(data.items) || !data.items.length) {
        host.innerHTML = `<p class="catalog-loading">${escapeHtml(t("info.catalogPreviewFail"))}</p>`;
        return;
      }
      host.innerHTML = data.items
        .map(
          (it) => `
            <div class="catalog-chip" title="${escapeHtml(it.title)} – ${escapeHtml(it.artist)}">
              <span class="catalog-title">${escapeHtml(it.title)}</span>
              <span class="catalog-artist">${escapeHtml(it.artist)}</span>
            </div>`,
        )
        .join("");
    } catch {
      host.innerHTML = `<p class="catalog-loading">${escapeHtml(t("info.catalogPreviewFail"))}</p>`;
    }
  }
  loadCatalogPreview();
  window.addEventListener("i18n:change", () => loadCatalogPreview());
  const catalogReloadBtn = document.getElementById("catalog-reload");
  if (catalogReloadBtn) {
    catalogReloadBtn.addEventListener("click", () => loadCatalogPreview({ randomize: true }));
  }

  // 즐겨찾기 섹션 — 저장된 곡이 있을 때만 노출.
  const favSection = document.getElementById("favorites-section");
  const favList = document.getElementById("favorites-list");
  const favClearBtn = document.getElementById("favorites-clear");

  function renderFavorites() {
    if (!favSection || !favList || !window.SoundMatchFavorites) return;
    const items = window.SoundMatchFavorites.list();
    if (!items.length) {
      favSection.classList.add("hidden");
      favList.innerHTML = "";
      return;
    }
    favSection.classList.remove("hidden");
    favList.innerHTML = items
      .map((it) => {
        const safeName = escapeHtml(it.name);
        return `
          <button type="button" class="catalog-chip catalog-chip-fav" data-name="${safeName}"
                  title="${safeName} — 클릭 시 이 곡으로 카탈로그 다시 검색">
            <span class="catalog-title">${escapeHtml(it.title)}</span>
            <span class="catalog-artist">${escapeHtml(it.artist)}</span>
          </button>`;
      })
      .join("");
    favList.querySelectorAll("button[data-name]").forEach((el) => {
      el.addEventListener("click", () => {
        const name = el.getAttribute("data-name");
        if (!name) return;
        const [title, artist] = name.split(" - ");
        seedFromHit({
          title: title || name,
          artist: artist || "",
          youtube_search_url: "#",
          spotify_search_url: "#",
        });
      });
    });
  }

  if (favClearBtn) {
    favClearBtn.addEventListener("click", () => {
      if (!confirm(t("favorites.confirm"))) return;
      window.SoundMatchFavorites.clearAll();
    });
  }

  window.addEventListener("favorites:change", renderFavorites);
  window.addEventListener("i18n:change", renderFavorites);
  renderFavorites();

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
    // 새 분석 시작 시 시드 백 스택은 초기화.
    _seedPrev = null;
    if (seedBackBtn) seedBackBtn.classList.add("hidden");

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

    // 휴리스틱 태그 칩 ("빠른 템포", "에너지 폭발" 등). 빈 배열이면 숨김.
    const tags = Array.isArray(data.tags) ? data.tags : [];
    if (tags.length && resultTagsEl) {
      resultTagsEl.innerHTML = tags
        .map((tag) => `<span class="result-tag">${escapeHtml(tag)}</span>`)
        .join("");
      resultTagsEl.classList.remove("hidden");
    } else if (resultTagsEl) {
      resultTagsEl.innerHTML = "";
      resultTagsEl.classList.add("hidden");
    }

    // 멜 스펙트로그램 SVG (백엔드가 직접 만들어줌). 빈 문자열이면 카드 숨김.
    if (typeof data.spectrogram_svg === "string" && data.spectrogram_svg.length > 0) {
      spectrogramHost.innerHTML = data.spectrogram_svg;
      spectrogramCard.classList.remove("hidden");
    } else {
      spectrogramHost.innerHTML = "";
      spectrogramCard.classList.add("hidden");
    }

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

      // "이 곡으로 다시 찾기" — by-catalog 로 연쇄 탐색.
      const seedBtn = li.querySelector('[data-action="seed"]');
      if (seedBtn) {
        seedBtn.addEventListener("click", () => seedFromHit(hit));
      }

      // ★ 즐겨찾기 토글.
      const favBtn = li.querySelector('[data-action="favorite"]');
      if (favBtn && window.SoundMatchFavorites) {
        const fullName = `${hit.title} - ${hit.artist}`;
        const applyFavState = () => {
          const isFav = window.SoundMatchFavorites.has(fullName);
          favBtn.setAttribute("aria-pressed", isFav ? "true" : "false");
          favBtn.dataset.active = isFav ? "true" : "false";
          const label = favBtn.querySelector(".fav-label");
          if (label) {
            label.textContent = t(isFav ? "results.favoriteRemove" : "results.favoriteAdd");
          }
        };
        applyFavState();
        favBtn.addEventListener("click", () => {
          window.SoundMatchFavorites.toggle(fullName, hit.title, hit.artist);
          applyFavState();
        });
      }

      // 펼침 토글 — 1위 카드는 펼친 채로, 2위부터는 접어둔다.
      // 그래야 결과가 10개여도 첫 인상이 깔끔하고 모바일 스크롤이 짧다.
      const toggleBtn = li.querySelector(".hit-toggle");
      const expanded = idx === 0;
      li.dataset.expanded = expanded ? "true" : "false";
      toggleBtn.setAttribute("aria-expanded", expanded ? "true" : "false");
      toggleBtn.addEventListener("click", () => {
        const now = li.dataset.expanded === "true";
        const next = !now;
        li.dataset.expanded = next ? "true" : "false";
        toggleBtn.setAttribute("aria-expanded", next ? "true" : "false");
      });

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
  // 시드 탐색 — 결과 카드의 곡으로 카탈로그 재분석 (librosa 우회)
  // ----------------------------------------------------------------------
  // 1단계 스택만 유지: 시드로 들어가기 직전 결과 한 건을 보관해두고,
  // "이전 분석으로" 버튼으로 한 번 돌아갈 수 있게 한다.
  let _seedPrev = null;

  async function seedFromHit(hit) {
    const name = `${hit.title} - ${hit.artist}`;
    const topN = parseInt(topNSelect.value, 10) || 5;
    // 현재 결과를 백 스택에 저장 (직전 한 건만).
    _seedPrev = _lastResults;
    hideAll();
    showSkeletonResults();
    startLoadingMessages();
    try {
      const res = await fetch(
        `/api/analyze/by-catalog?top_n=${topN}&name=${encodeURIComponent(name)}`,
      );
      stopLoadingMessages();
      if (!res.ok) {
        const text = await safeJsonOrText(res);
        throw new Error(text || `서버 오류 (${res.status})`);
      }
      const data = await res.json();
      // by-catalog 응답에는 filename / spectrogram / timing 등이 없다.
      // renderResults 가 기대하는 형태로 살짝 보강해서 그대로 재사용.
      const seedAdapted = Object.assign({}, data, {
        filename: t("results.seedHeader", data.title, data.artist),
        timing: { feature_extraction_seconds: 0, similarity_seconds: 0 },
        spectrogram_svg: "",
      });
      _lastResults = seedAdapted;
      _lastFile = null;
      audioPlayer.classList.add("hidden");
      renderResults(seedAdapted, /* preserveFile */ true);
      seedBackBtn.classList.remove("hidden");
    } catch (err) {
      stopLoadingMessages();
      showError(err.message || String(err));
      // 실패 시 이전 결과를 잃지 않게 복원.
      if (_seedPrev) _lastResults = _seedPrev;
    }
  }

  seedBackBtn.addEventListener("click", () => {
    if (!_seedPrev) return;
    const prev = _seedPrev;
    _seedPrev = null;
    _lastResults = prev;
    renderResults(prev, /* preserveFile */ true);
    seedBackBtn.classList.add("hidden");
  });

  // ----------------------------------------------------------------------
  // 초기화
  // ----------------------------------------------------------------------
  resetBtn.addEventListener("click", () => {
    setFile(null);
    setAudioPreview(null);
    _lastResults = null;
    _lastFile = null;
    _seedPrev = null;
    if (seedBackBtn) seedBackBtn.classList.add("hidden");
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
  // 공유 가능한 URL — 결과를 압축 후 URL hash 에 직렬화
  // ----------------------------------------------------------------------
  // 결과 페이로드가 보통 5~10KB 라 hash 에 그대로 넣으면 URL 이 길어진다.
  // CompressionStream("gzip") 으로 압축 후 base64url 인코딩해서 짧게 만든다.
  // base64url 은 일반 base64 와 달리 `+/=` 를 `-_` 로 바꿔서 URL 에 안전.
  async function encodeForShare(data) {
    try {
      const json = JSON.stringify(data);
      if (typeof CompressionStream === "undefined") {
        // 구형 브라우저: 압축 없이 base64. 약간 길어지지만 동작은 됨.
        return base64UrlEncode(new TextEncoder().encode(json));
      }
      const stream = new Blob([json]).stream().pipeThrough(new CompressionStream("gzip"));
      const buf = await new Response(stream).arrayBuffer();
      return base64UrlEncode(new Uint8Array(buf));
    } catch {
      return null;
    }
  }

  async function decodeFromShare(token) {
    try {
      const bytes = base64UrlDecode(token);
      if (typeof DecompressionStream === "undefined") {
        // 구형 브라우저는 압축 안 한 경로로 직접 디코드.
        return JSON.parse(new TextDecoder().decode(bytes));
      }
      const stream = new Blob([bytes]).stream().pipeThrough(new DecompressionStream("gzip"));
      const text = await new Response(stream).text();
      return JSON.parse(text);
    } catch {
      return null;
    }
  }

  function base64UrlEncode(uint8) {
    let s = "";
    for (let i = 0; i < uint8.length; i++) s += String.fromCharCode(uint8[i]);
    return btoa(s).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  }

  function base64UrlDecode(str) {
    const pad = str.length % 4 === 0 ? "" : "=".repeat(4 - (str.length % 4));
    const b64 = str.replace(/-/g, "+").replace(/_/g, "/") + pad;
    const bin = atob(b64);
    const out = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
    return out;
  }

  // 페이지 로드 시 hash 에 결과가 들어있으면 자동 복원.
  // 형식: #r=<base64url-gzip-json>
  async function tryRestoreFromHash() {
    const m = (location.hash || "").match(/^#r=(.+)$/);
    if (!m) return;
    const restored = await decodeFromShare(m[1]);
    if (restored && Array.isArray(restored.results)) {
      _lastResults = restored;
      _lastFile = null;
      audioPlayer.classList.add("hidden");
      renderResults(restored, /* preserveFile */ true);
      // 복원 사실을 토스트로 알려준다.
      toast(t("results.restored"));
    }
  }

  // 페이지 첫 로드 시 한 번 시도. DOM 이 그려진 후에 결과 카드를 채워야 안전.
  if (document.readyState !== "loading") {
    tryRestoreFromHash();
  } else {
    document.addEventListener("DOMContentLoaded", tryRestoreFromHash);
  }

  // ----------------------------------------------------------------------
  // 공유 / 내보내기
  // ----------------------------------------------------------------------
  // Web Share API 가 지원되면 share 버튼을 노출한다.
  function buildShareText(data) {
    const tracks = data.results
      .slice(0, 3)
      .map((r) => `${r.rank}. ${r.title} – ${r.artist} (${r.similarity_percent.toFixed(1)}%)`)
      .join("\n");
    return `SoundMatch · ${data.filename}\n\n${tracks}\n\n${location.origin}`;
  }
  if (navigator.share && shareBtn) {
    shareBtn.classList.remove("hidden");
    shareBtn.addEventListener("click", async () => {
      if (!_lastResults) return;
      try {
        await navigator.share({
          title: "SoundMatch · AI 음악 유사도 결과",
          text: buildShareText(_lastResults),
          url: location.origin,
        });
      } catch (e) {
        // 사용자가 공유 시트를 취소했을 때는 굳이 알림 띄우지 않는다.
        if (e && e.name !== "AbortError") toast(t("results.copied"));
      }
    });
  }

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

  // "공유 가능한 링크 복사" — 결과를 hash 에 담은 URL 을 클립보드에 넣어준다.
  if (copyShareUrlBtn) {
    copyShareUrlBtn.addEventListener("click", async () => {
      if (!_lastResults) return;
      const token = await encodeForShare(_lastResults);
      if (!token) {
        toast(t("results.shareUrlFailed"));
        return;
      }
      const url = `${location.origin}/#r=${token}`;
      // URL 이 너무 길면(약 10KB+) 브라우저/주소창이 까다로워질 수 있어 경고만 한 번.
      if (url.length > 12000) {
        console.warn("Share URL is unusually long:", url.length);
      }
      try {
        await navigator.clipboard.writeText(url);
        toast(t("results.copied"));
      } catch {
        toast(url);
      }
    });
  }

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

  // 결과 한 페이지를 SVG 카드로 떨궈주기 — SNS 공유 / 보관 용.
  // 외부 라이브러리 없이 직접 SVG 문자열을 짜서 Blob 다운로드한다.
  function buildResultSvg(data) {
    if (!data || !data.results || !data.results.length) return null;
    const w = 1200;
    const top = data.results.slice(0, 5);
    const padding = 56;
    const rowH = 88;
    const headerH = 200;
    const tagsH = data.tags && data.tags.length ? 48 : 0;
    const h = headerH + tagsH + top.length * rowH + padding;

    function esc(s) {
      return String(s == null ? "" : s)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
    }

    const filename = esc(data.filename || "분석 결과");
    const subtitle = data.results.length
      ? `${data.catalog_size?.toLocaleString?.("ko-KR") || ""}곡과 비교 · ` +
        `${esc(data.analyzed_at || "")}`
      : "";

    const tagsXml = (data.tags || [])
      .slice(0, 5)
      .map((tag, i) => {
        const x = padding + i * 150;
        return (
          `<g transform="translate(${x}, ${headerH - 16})">` +
          `<rect rx="999" ry="999" width="140" height="32" fill="#3a2470"/>` +
          `<text x="70" y="20" text-anchor="middle" fill="#d3c8ff" ` +
          `font-size="14" font-weight="500">${esc(tag)}</text>` +
          `</g>`
        );
      })
      .join("");

    const rowsXml = top
      .map((r, i) => {
        const y = headerH + tagsH + i * rowH;
        const rankColor = "#7c5cff";
        const pct = (r.similarity_percent || 0).toFixed(1);
        const barW = Math.max(2, Math.min(100, r.similarity_percent || 0)) * (w - padding * 2 - 220) / 100;
        return (
          `<g transform="translate(${padding}, ${y})">` +
          `<text x="0" y="34" font-size="40" font-weight="800" fill="${rankColor}">${r.rank}</text>` +
          `<text x="60" y="22" font-size="22" font-weight="700" fill="#f4f4ff">${esc(r.title)}</text>` +
          `<text x="60" y="46" font-size="14" fill="rgba(244,244,255,0.7)">${esc(r.artist)}</text>` +
          `<text x="${w - padding * 2}" y="34" text-anchor="end" font-size="28" ` +
          `font-weight="800" fill="#22d3ee">${pct}%</text>` +
          `<rect x="60" y="58" width="${w - padding * 2 - 220}" height="6" rx="3" fill="rgba(255,255,255,0.08)"/>` +
          `<rect x="60" y="58" width="${barW}" height="6" rx="3" fill="url(#gradBar)"/>` +
          `</g>`
        );
      })
      .join("");

    return (
      `<?xml version="1.0" encoding="UTF-8"?>` +
      `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${w} ${h}" font-family="Pretendard, Inter, sans-serif">` +
      `<defs>` +
      `<linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">` +
      `<stop offset="0" stop-color="#0b0b18"/><stop offset="1" stop-color="#1a1430"/>` +
      `</linearGradient>` +
      `<linearGradient id="gradBar" x1="0" y1="0" x2="1" y2="0">` +
      `<stop offset="0" stop-color="#7c5cff"/><stop offset="1" stop-color="#22d3ee"/>` +
      `</linearGradient>` +
      `<linearGradient id="gradTitle" x1="0" y1="0" x2="1" y2="0">` +
      `<stop offset="0" stop-color="#7c5cff"/><stop offset="1" stop-color="#22d3ee"/>` +
      `</linearGradient>` +
      `</defs>` +
      `<rect width="${w}" height="${h}" fill="url(#bg)"/>` +
      `<text x="${padding}" y="80" font-size="40" font-weight="800" fill="#f4f4ff">SoundMatch · 분석 결과</text>` +
      `<text x="${padding}" y="118" font-size="22" font-weight="600" fill="url(#gradTitle)">${filename}</text>` +
      `<text x="${padding}" y="148" font-size="14" fill="rgba(244,244,255,0.6)">${subtitle}</text>` +
      tagsXml +
      rowsXml +
      `<text x="${w - padding}" y="${h - 16}" text-anchor="end" font-size="12" fill="rgba(244,244,255,0.4)">soundmatch · easygap/music_similarity</text>` +
      `</svg>`
    );
  }

  if (exportSvgBtn) {
    exportSvgBtn.addEventListener("click", () => {
      if (!_lastResults) return;
      const svg = buildResultSvg(_lastResults);
      if (!svg) return;
      const blob = new Blob([svg], { type: "image/svg+xml" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      const baseName = (_lastResults.filename || "soundmatch").replace(/\.[^.]+$/, "");
      a.download = `${baseName}.soundmatch.svg`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      setTimeout(() => URL.revokeObjectURL(url), 500);
    });
  }

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
  // PWA 설치 배너 — beforeinstallprompt 이벤트를 가로채서 사용자가 원할 때 띄움
  // ----------------------------------------------------------------------
  const INSTALL_DISMISS_KEY = "soundmatch.installDismissedAt";
  const INSTALL_DISMISS_TTL_MS = 7 * 24 * 60 * 60 * 1000; // 7일

  let _installPrompt = null;
  const installBanner = document.getElementById("install-banner");
  const installAcceptBtn = document.getElementById("install-accept");
  const installDismissBtn = document.getElementById("install-dismiss");

  function shouldHideInstallBanner() {
    try {
      const dismissedAt = parseInt(localStorage.getItem(INSTALL_DISMISS_KEY) || "0", 10);
      if (!dismissedAt) return false;
      return Date.now() - dismissedAt < INSTALL_DISMISS_TTL_MS;
    } catch {
      return false;
    }
  }

  window.addEventListener("beforeinstallprompt", (e) => {
    // Chrome / Edge 가 자체 설치 prompt 를 띄우려 하면 가로채서 우리 배너에 연결.
    e.preventDefault();
    _installPrompt = e;
    if (!shouldHideInstallBanner() && installBanner) {
      installBanner.classList.remove("hidden");
    }
  });

  window.addEventListener("appinstalled", () => {
    // 설치 완료되면 배너는 즉시 숨김.
    if (installBanner) installBanner.classList.add("hidden");
    _installPrompt = null;
  });

  if (installAcceptBtn) {
    installAcceptBtn.addEventListener("click", async () => {
      if (!_installPrompt) {
        installBanner.classList.add("hidden");
        return;
      }
      _installPrompt.prompt();
      try {
        await _installPrompt.userChoice;
      } catch {}
      _installPrompt = null;
      installBanner.classList.add("hidden");
    });
  }
  if (installDismissBtn) {
    installDismissBtn.addEventListener("click", () => {
      try { localStorage.setItem(INSTALL_DISMISS_KEY, String(Date.now())); } catch {}
      installBanner.classList.add("hidden");
    });
  }

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
