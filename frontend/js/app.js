// SoundMatch 메인 컨트롤러 -------------------------------------------------
// 업로드 폼, 로딩/결과 상태, 파형/레이더 시각화, 히스토리, 테마/언어 토글,
// 공유/다운로드, 키보드 단축키까지 묶어서 처리한다. 빌드 스텝 없는 plain JS.

(function () {
  "use strict";

  const $ = (sel) => document.querySelector(sel);

  let maxUploadBytes = 25 * 1024 * 1024;
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
  const sampleBtn = $("#sample-btn");

  const loadingSection = $("#loading");
  const loadingStep = $("#loading-step");
  const loadingElapsed = $("#loading-elapsed");

  const errorSection = $("#error");
  const errorMessage = $("#error-message");
  const errorRetryBtn = $("#error-retry");

  const resultsSection = $("#results");
  const resultsTitle = $("#results-title");
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
  const seekSlider = $("#waveform-seek");
  const playBtn = $("#play-btn");
  const audioTime = $("#audio-time");

  const resetBtn = $("#reset-btn");
  const seedBackBtn = $("#seed-back-btn");
  const expandToggleBtn = $("#expand-toggle-btn");
  const resultsSortSelect = $("#results-sort");
  const copyLinkBtn = $("#copy-link-btn");
  const copyShareUrlBtn = $("#copy-share-url-btn");
  const exportJsonBtn = $("#export-json-btn");
  const exportCsvBtn = $("#export-csv-btn");
  const exportSvgBtn = $("#export-svg-btn");
  const exportPngBtn = $("#export-png-btn");
  const exportMenu = $("#export-menu");
  const yearSpan = $("#year");

  // 내보내기 <details> 드롭다운 — 항목을 클릭하면 메뉴를 닫고, 바깥을 클릭해도 닫는다.
  // <details> 자체는 JS 없이 토글되지만, "선택 후 자동 닫힘" 과 "바깥 클릭 닫힘" 은 보조해야
  // 일반적인 드롭다운 UX 에 맞는다.
  if (exportMenu) {
    exportMenu.querySelectorAll(".export-menu-item").forEach((item) => {
      item.addEventListener("click", () => exportMenu.removeAttribute("open"));
    });
    document.addEventListener("click", (e) => {
      if (exportMenu.hasAttribute("open") && !exportMenu.contains(e.target)) {
        exportMenu.removeAttribute("open");
      }
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && exportMenu.hasAttribute("open")) {
        exportMenu.removeAttribute("open");
        const summary = exportMenu.querySelector("summary");
        if (summary) summary.focus();
      }
    });
  }

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

  function formatUploadLimit(bytes) {
    const value = Number(bytes);
    if (!Number.isFinite(value) || value <= 0) return "25MB";
    const mb = value / (1024 * 1024);
    if (mb >= 1) {
      const rounded = mb >= 10 ? Math.round(mb) : Math.round(mb * 10) / 10;
      return `${String(rounded).replace(/\.0$/, "")}MB`;
    }
    const kb = Math.max(1, Math.round(value / 1024));
    return `${kb}KB`;
  }

  function syncUploadLimitText() {
    const uploadSub = $(".upload-sub");
    if (uploadSub) {
      uploadSub.textContent = t("upload.subtitleWithLimit", formatUploadLimit(maxUploadBytes));
    }
  }

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
    syncUploadLimitText();
    renderHistory();
    if (_lastResults) renderResults(_lastResults, /* preserveFile */ true, { focus: false, scroll: false });
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
  // theme-init.js 가 OS prefers-color-scheme 변경에 따라 테마를 갈아끼우면 같은 이벤트로 알린다.
  // 파형 캔버스 등 CSS 변수에 묶인 요소를 다시 그려야 하기 때문 (applyTheme 의 부수효과와 동일).
  window.addEventListener("theme:change", () => {
    if (_waveform) _waveform.draw(_audioProgress);
  });
  langToggleBtn.addEventListener("click", () => {
    if (window.i18n) window.i18n.toggle();
  });

  // ----------------------------------------------------------------------
  // 모바일 네비게이션 (햄버거 드롭다운)
  // ----------------------------------------------------------------------
  // <600px 에서 nav 텍스트 링크가 드롭다운으로 접히고, 햄버거 버튼으로 토글한다.
  // 데스크톱에서는 CSS 가 .nav-menu-toggle 을 숨기므로 이 핸들러는 사실상 비활성.
  const navMenuToggle = $("#nav-menu-toggle");
  const navLinksGroup = $("#nav-links-group");
  if (navMenuToggle && navLinksGroup) {
    const setNavOpen = (open) => {
      navLinksGroup.classList.toggle("is-open", open);
      navMenuToggle.setAttribute("aria-expanded", open ? "true" : "false");
      // aria-label 도 상태에 맞춰 — 스크린리더가 "열기/닫기" 를 정확히 안내.
      navMenuToggle.setAttribute(
        "aria-label",
        t(open ? "nav.menuClose" : "nav.menuToggle"),
      );
    };
    navMenuToggle.addEventListener("click", (e) => {
      e.stopPropagation();
      setNavOpen(!navLinksGroup.classList.contains("is-open"));
    });
    // 메뉴 안의 링크를 누르면 (페이지 이동 / 앵커 점프) 메뉴를 닫는다.
    navLinksGroup.querySelectorAll("a").forEach((a) => {
      a.addEventListener("click", () => setNavOpen(false));
    });
    // 바깥 클릭 시 닫기.
    document.addEventListener("click", (e) => {
      if (!navLinksGroup.classList.contains("is-open")) return;
      if (navLinksGroup.contains(e.target) || navMenuToggle.contains(e.target)) return;
      setNavOpen(false);
    });
    // Esc 로 닫고 포커스를 토글 버튼으로 되돌린다.
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && navLinksGroup.classList.contains("is-open")) {
        setNavOpen(false);
        navMenuToggle.focus();
      }
    });
  }

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

  // Hero 영역에 누적 분석 횟수를 작게 노출 — social proof. /api/version 응답의
  // analyses_total 활용. 횟수가 0 이면 (아직 한 번도 분석 안 됨) 그냥 숨겨둔다.
  // 같은 응답에서 footer 의 빌드 정보 (v + release_date) 도 함께 채운다.
  async function loadSocialProof() {
    const el = $("#hero-social-proof");
    const buildEl = $("#footer-build");
    try {
      const res = await fetch("/api/version");
      if (!res.ok) throw new Error("offline");
      const data = await res.json();
      const configuredMax = Number(data.max_upload_bytes);
      if (Number.isFinite(configuredMax) && configuredMax > 0) {
        maxUploadBytes = configuredMax;
        syncUploadLimitText();
      }

      // 누적 분석 횟수 (social proof).
      if (el) {
        const total = Number(data.analyses_total) || 0;
        if (total <= 0) {
          el.hidden = true;
        } else {
          const isEn = window.i18n && window.i18n.lang() === "en";
          const formatted = isEn ? total.toLocaleString("en-US") : total.toLocaleString("ko-KR");
          el.textContent = t("hero.totalAnalyses", formatted);
          el.hidden = false;
        }
      }

      // footer 빌드 정보 — 'v1.5.0 · 2026-05-21 · abc1234' 형태.
      // git_commit / release_date 가 없으면 차례로 생략. 응답이 죽어 있으면 라인 자체를 숨김.
      if (buildEl && data.version) {
        const parts = [`v${String(data.version)}`];
        if (data.release_date) parts.push(String(data.release_date));
        if (data.git_commit) parts.push(String(data.git_commit));
        buildEl.textContent = parts.join(" · ");
        buildEl.hidden = false;
      }

      // "새 기능" 배너 — version + release_date 가 마지막 확인 값과 다를 때만 노출.
      // 처음 방문자(localStorage 비어 있음) 에게는 보여주지 않는다 — onboarding 의 다른
      // 신호 (PWA install, 카탈로그 안내) 와 겹치면 노이즈가 되기 때문.
      maybeShowWhatsNew(data);
    } catch {
      if (el) el.hidden = true;
      // buildEl 은 hidden 그대로 유지.
    }
  }
  loadSocialProof();
  window.addEventListener("i18n:change", loadSocialProof);

  // ------------------------------------------------------------------
  // What's New 배너 + 모달.
  // ------------------------------------------------------------------
  const WHATSNEW_KEY = "soundmatch.lastSeenRelease";
  let lastWhatsNewReleaseId = "";

  function releaseSeenId(versionData) {
    if (!versionData || !versionData.version || !versionData.release_date) return "";
    return `${String(versionData.version)}|${String(versionData.release_date)}`;
  }

  function maybeShowWhatsNew(versionData) {
    const banner = document.getElementById("whatsnew-banner");
    const versionChip = document.getElementById("whatsnew-version");
    if (!banner || !versionData) return;
    const date = versionData.release_date;
    const version = versionData.version;
    if (!date || !version) return;
    const currentSeenId = releaseSeenId(versionData);
    if (!currentSeenId) return;
    lastWhatsNewReleaseId = currentSeenId;
    let lastSeen = "";
    try { lastSeen = localStorage.getItem(WHATSNEW_KEY) || ""; } catch (e) { /* private mode */ }

    if (!lastSeen) {
      // 처음 방문자 — 배너 띄우지 않고 현재 release 만 silent 하게 기록.
      try { localStorage.setItem(WHATSNEW_KEY, currentSeenId); } catch (e) { /* private mode */ }
      return;
    }
    if (lastSeen === currentSeenId) {
      // 이미 확인한 릴리즈 — 표시 안 함.
      banner.classList.add("hidden");
      return;
    }
    // 새 릴리즈가 있다 → 배너 노출 + 버전 chip 갱신.
    if (versionChip) versionChip.textContent = `v${version}`;
    banner.classList.remove("hidden");
  }

  function dismissWhatsNew() {
    const banner = document.getElementById("whatsnew-banner");
    if (banner) banner.classList.add("hidden");
    // 가장 마지막에 받은 /api/version 의 version + release_date 조합을 저장한다.
    if (lastWhatsNewReleaseId) {
      try { localStorage.setItem(WHATSNEW_KEY, lastWhatsNewReleaseId); } catch (e) {}
      return;
    }
    // 예외적으로 캐시된 값이 없으면 한 번 더 조회해서 같은 marker 를 만든다.
    fetch("/api/version").then(function (r) { return r.ok ? r.json() : null; }).then(function (d) {
      const seenId = releaseSeenId(d);
      if (seenId) {
        try { localStorage.setItem(WHATSNEW_KEY, seenId); } catch (e) {}
      }
    }).catch(function () { /* ignore */ });
  }

  async function openWhatsNewModal() {
    const modal = document.getElementById("whatsnew-modal");
    const body = document.getElementById("whatsnew-modal-body");
    if (!modal || !body) return;
    modal.classList.remove("hidden");
    document.body.style.overflow = "hidden";
    body.innerHTML = `<p class="whatsnew-loading">${escapeHtml(t("whatsNew.loading"))}</p>`;
    try {
      const res = await fetch("/api/version/changelog?limit=3");
      if (!res.ok) throw new Error("HTTP " + res.status);
      const data = await res.json();
      body.innerHTML = renderWhatsNewBody(data.releases || []);
    } catch (e) {
      body.innerHTML = `<p class="whatsnew-empty">${escapeHtml(t("whatsNew.loadFail"))}</p>`;
    }
  }
  function closeWhatsNewModal() {
    const modal = document.getElementById("whatsnew-modal");
    if (modal) modal.classList.add("hidden");
    document.body.style.overflow = "";
  }
  // escapeHtml 는 app.js 하단에 이미 동일 구현이 있어 hoisting 으로 호출 가능 — 중복 정의 안 함.
  function renderWhatsNewBody(releases) {
    if (!releases || !releases.length) {
      return `<p class="whatsnew-empty">${escapeHtml(t("whatsNew.empty"))}</p>`;
    }
    return releases.map(function (rel) {
      const sectionsHtml = Object.keys(rel.sections || {}).map(function (name) {
        const items = (rel.sections[name] || []).map(function (item) {
          return `<li>${escapeHtml(item)}</li>`;
        }).join("");
        return `
          <div class="whatsnew-section">
            <span class="whatsnew-section-name">${escapeHtml(name)}</span>
            <ul>${items}</ul>
          </div>
        `;
      }).join("");
      return `
        <div class="whatsnew-release">
          <div class="whatsnew-release-head">
            <span class="whatsnew-release-ver">v${escapeHtml(rel.version)}</span>
            <span class="whatsnew-release-date">${escapeHtml(rel.date)}</span>
          </div>
          ${sectionsHtml}
        </div>
      `;
    }).join("");
  }

  // 이벤트 핸들러 연결.
  const wnOpenBtn = document.getElementById("whatsnew-open");
  const wnDismissBtn = document.getElementById("whatsnew-dismiss");
  const wnCloseBtn = document.getElementById("whatsnew-modal-close");
  const wnModal = document.getElementById("whatsnew-modal");
  if (wnOpenBtn) wnOpenBtn.addEventListener("click", function () {
    openWhatsNewModal();
    // 배너는 누르면 자동으로 "확인" 처리 — 다음 릴리즈까지 다시 안 뜬다.
    dismissWhatsNew();
  });
  if (wnDismissBtn) wnDismissBtn.addEventListener("click", dismissWhatsNew);
  if (wnCloseBtn) wnCloseBtn.addEventListener("click", closeWhatsNewModal);
  if (wnModal) wnModal.addEventListener("click", function (e) {
    // backdrop 클릭 시 닫기 (모달 카드 내부 클릭은 버블링 안 막혔지만, target 이 backdrop 일 때만).
    if (e.target === wnModal) closeWhatsNewModal();
  });
  // Esc 로도 닫기 — 모달이 열려 있을 때만.
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && wnModal && !wnModal.classList.contains("hidden")) {
      closeWhatsNewModal();
    }
  });

  // hero stat 의 "평균 분석 시간" 을 실시간 latency P50 으로 갱신 + 카탈로그
  // 갱신 일자(catalog_updated_at) 도 같은 응답에서 가져와 stat 카드에 작게 표시.
  // health 엔드포인트는 ring buffer 의 P50 을 같이 내려준다 — 샘플이 없으면 0.
  async function loadLatencyStat() {
    const latencyEl = $("#stat-latency");
    const freshEl = $("#stat-catalog-fresh");
    if (!latencyEl && !freshEl) return;
    try {
      const res = await fetch("/api/health");
      if (!res.ok) throw new Error("offline");
      const data = await res.json();

      if (latencyEl) {
        const p50 = Number(data.analyze_latency_p50_seconds) || 0;
        if (p50 > 0) {
          // 1초 미만이면 "0.7s", 1초 이상이면 "~3s" 식으로.
          latencyEl.textContent = p50 < 1 ? `${p50.toFixed(1)}s` : `~${Math.round(p50)}s`;
        }
        // 샘플이 없으면 정적 기본값을 그대로 둔다.
      }

      if (freshEl) {
        const iso = data.catalog_updated_at;
        if (typeof iso === "string" && iso.length >= 10) {
          const date = iso.slice(0, 10);  // YYYY-MM-DD
          freshEl.textContent = t("hero.catalogFresh", date);
          freshEl.hidden = false;
        }
      }
    } catch {
      /* health 가 안 잡혀도 기본 문구 유지 */
    }
  }
  loadLatencyStat();
  // 언어 토글 시 "최근 갱신:" 라벨도 다시 그려야 한다.
  window.addEventListener("i18n:change", () => loadLatencyStat());
  rebuildLocalizedSelectOptions();
  syncUploadLimitText();
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
  const favSortSelect = document.getElementById("favorites-sort");

  // 즐겨찾기 정렬 선호. 사용자가 200곡까지 모을 수 있어서 정렬 옵션이 중요.
  const FAV_SORT_KEY = "soundmatch.fav-sort";

  function readFavSort() {
    try {
      const v = localStorage.getItem(FAV_SORT_KEY);
      return v === "title" || v === "artist" ? v : "recent";
    } catch {
      return "recent";
    }
  }

  function writeFavSort(mode) {
    try {
      localStorage.setItem(FAV_SORT_KEY, mode);
    } catch {
      // localStorage 비활성화여도 화면 동작은 일회성으로 그대로 유지.
    }
  }

  function sortFavorites(items, mode) {
    // 원본 배열 안 건드리고 정렬된 사본을 돌려준다.
    if (!Array.isArray(items)) return [];
    const list = items.slice();
    if (mode === "title") {
      list.sort((a, b) => (a.title || "").localeCompare(b.title || "", undefined, { sensitivity: "base" }));
    } else if (mode === "artist") {
      list.sort((a, b) => (a.artist || "").localeCompare(b.artist || "", undefined, { sensitivity: "base" }));
    }
    // "recent" 모드는 favorites.js 의 add() 가 unshift 라 이미 최신순.
    return list;
  }

  function renderFavorites() {
    if (!favSection || !favList || !window.SoundMatchFavorites) return;
    const items = window.SoundMatchFavorites.list();
    if (!items.length) {
      favSection.classList.add("hidden");
      favList.innerHTML = "";
      return;
    }
    favSection.classList.remove("hidden");
    // 정렬 select 가 있으면 사용자 선호 반영, 아니면 기본 "recent".
    if (favSortSelect) favSortSelect.value = readFavSort();
    const sorted = sortFavorites(items, readFavSort());
    favList.innerHTML = sorted
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

  if (favSortSelect) {
    favSortSelect.value = readFavSort();
    favSortSelect.addEventListener("change", () => {
      writeFavSort(favSortSelect.value);
      renderFavorites();
    });
  }

  // 즐겨찾기 내보내기 — 현재 저장된 항목을 JSON 파일로 다운로드.
  const favExportBtn = document.getElementById("favorites-export");
  if (favExportBtn) {
    favExportBtn.addEventListener("click", () => {
      if (!window.SoundMatchFavorites) return;
      try {
        const payload = window.SoundMatchFavorites.exportJson();
        const blob = new Blob([payload], { type: "application/json" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        const stamp = new Date().toISOString().slice(0, 10);
        a.href = url;
        a.download = `soundmatch-favorites-${stamp}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        // 다운로드가 시작된 뒤에는 URL 해제. 같은 마이크로태스크에서 풀어버리면
        // 사파리 같은 일부 브라우저에서 다운로드가 캔슬되는 사례가 있어 한 박자 늦춤.
        setTimeout(() => URL.revokeObjectURL(url), 1000);
        toast(t("favorites.exportDone"));
      } catch (e) {
        console.error("[favorites] export failed:", e);
        toast(t("favorites.importFailed"));
      }
    });
  }

  // 가져오기 — 숨겨둔 file input 을 트리거해서 JSON 파일을 받는다.
  const favImportBtn = document.getElementById("favorites-import-btn");
  const favImportFile = document.getElementById("favorites-import-file");
  if (favImportBtn && favImportFile) {
    favImportBtn.addEventListener("click", () => favImportFile.click());
    favImportFile.addEventListener("change", async () => {
      const file = favImportFile.files && favImportFile.files[0];
      // 같은 파일을 두 번 연속 선택하는 경우에도 change 이벤트가 다시 발생하도록 초기화.
      favImportFile.value = "";
      if (!file) return;
      try {
        const text = await file.text();
        const result = window.SoundMatchFavorites.importJson(text);
        toast(t("favorites.importSuccess", result.added, result.total));
      } catch (e) {
        console.warn("[favorites] import failed:", e);
        toast(t("favorites.importFailed"));
      }
    });
  }

  window.addEventListener("favorites:change", renderFavorites);
  // favorites.js 가 쿼터 초과로 저장 실패하면 신호. 사용자한테 알려야
  // 영문도 모르는 상태로 즐겨찾기가 안 쌓이는 일을 막을 수 있다.
  window.addEventListener("favorites:storage-full", () => {
    toast(t("favorites.storageFull") || t("history.storageFull"));
  });
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
    if (selectedFile.size > maxUploadBytes) {
      dropzoneError.textContent = t(
        "upload.validation.tooBig",
        formatUploadLimit(maxUploadBytes),
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
  // 분석 요청을 도중에 취소할 때 쓰는 AbortController. 사용자가 분석 중
  // 다른 파일을 새로 올리거나 "새 분석" 으로 돌아가면 이전 fetch 는 취소되어
  // 결과가 뒤섞이는 race 를 막는다.
  let _analysisAbortController = null;

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
    // 이전에 진행 중이던 분석이 있으면 abort. 같은 핸들러 안에서 새 fetch 가
    // 시작되기 전에 옛 요청을 끊어줘야 결과가 뒤섞이는 race 가 안 생긴다.
    if (_analysisAbortController) {
      try { _analysisAbortController.abort(); } catch (_) {}
    }
    const controller = new AbortController();
    _analysisAbortController = controller;

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
        signal: controller.signal,
      });
      stopLoadingMessages();

      if (!res.ok) {
        if (res.status === 429) throw new Error(t("error.rateLimit"));
        const text = await safeJsonOrText(res);
        throw new Error(text || `서버 오류 (${res.status})`);
      }

      const data = await res.json();
      // 응답 도착 직전에 새 분석이 시작돼서 controller 가 바뀌었다면
      // 이 응답은 stale. 화면 갱신을 건너뛴다.
      if (_analysisAbortController !== controller) return;
      _lastResults = data;
      addToHistory(data);
      await setAudioPreview(file);
      renderResults(data);
      // 분석이 끝났으니 URL hash 에 결과를 자동으로 직렬화 — 새로고침 /
      // 북마크 만으로도 결과가 살아남는다. 실패는 무시 (선택적 기능).
      updateLocationHash(data).catch(() => {});
    } catch (err) {
      // AbortError 는 사용자가 의도적으로 cancel 한 것이라 에러 화면을 띄우지 않음.
      if (err && err.name === "AbortError") return;
      stopLoadingMessages();
      showError(err.message || String(err));
    } finally {
      // 이 호출이 시작한 분석만 in-flight 플래그를 끈다 (새 분석이 이미
      // 시작된 경우엔 그 controller 가 살아 있어야 함).
      if (_analysisAbortController === controller) {
        _analysisInFlight = false;
        _analysisAbortController = null;
      }
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
      // 보조 시킹 슬라이더(키보드/SR)도 재생 위치에 맞춰 갱신한다. 값 set 은
      // input 이벤트를 발생시키지 않으므로 사용자의 직접 조작과 충돌하지 않는다.
      if (seekSlider) {
        seekSlider.value = String(Math.round(_audioProgress * 100));
        seekSlider.setAttribute(
          "aria-valuetext",
          `${fmtTime(audioPreview.currentTime)} / ${fmtTime(audioPreview.duration)}`,
        );
      }
    }
    updateAudioTime();
  });
  audioPreview.addEventListener("play", () => { playBtn.dataset.playing = "true"; });
  audioPreview.addEventListener("pause", () => { playBtn.dataset.playing = "false"; });
  audioPreview.addEventListener("ended", () => {
    playBtn.dataset.playing = "false";
    _audioProgress = 0;
    if (_waveform) _waveform.draw(0);
    if (seekSlider) seekSlider.value = "0";
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

  // 보조 시킹 슬라이더 — 키보드 화살표 / 스크린리더로 재생 위치를 옮긴다.
  // 파형 캔버스는 마우스 전용(aria-hidden)이라, 이 슬라이더가 같은 기능을
  // 키보드 사용자에게 제공한다.
  if (seekSlider) {
    seekSlider.addEventListener("input", () => {
      if (!audioPreview.duration) return;
      audioPreview.currentTime = (parseFloat(seekSlider.value) / 100) * audioPreview.duration;
    });
  }

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
  // 결과 카드 펼침 모드 — 사용자 선호를 localStorage 에 저장
  // ----------------------------------------------------------------------
  const EXPAND_MODE_KEY = "soundmatch.hit-expand-mode";

  function readExpandMode() {
    try {
      const v = localStorage.getItem(EXPAND_MODE_KEY);
      return v === "all" ? "all" : "compact";
    } catch (_) {
      return "compact";
    }
  }

  function writeExpandMode(mode) {
    try {
      localStorage.setItem(EXPAND_MODE_KEY, mode === "all" ? "all" : "compact");
    } catch (_) {
      // localStorage 비활성화면 무시 — 화면 토글은 일회성으로 동작.
    }
  }

  function syncExpandToggleButton() {
    if (!expandToggleBtn) return;
    const mode = readExpandMode();
    const label = expandToggleBtn.querySelector(".expand-toggle-label");
    if (label) {
      label.textContent = mode === "all" ? t("results.collapseAll") : t("results.expandAll");
    }
    expandToggleBtn.setAttribute("aria-pressed", mode === "all" ? "true" : "false");
  }

  function applyExpandModeToVisibleCards(mode) {
    // 이미 렌더된 결과 카드들의 펼침 상태를 일괄 변경. 1위는 "compact" 모드에서도
    // 펼쳐진 상태가 기본이라 그대로 둔다.
    document.querySelectorAll(".hit-list .hit").forEach((li, idx) => {
      const expanded = mode === "all" || idx === 0;
      li.dataset.expanded = expanded ? "true" : "false";
      const tb = li.querySelector(".hit-toggle");
      if (tb) tb.setAttribute("aria-expanded", expanded ? "true" : "false");
    });
  }

  if (expandToggleBtn) {
    expandToggleBtn.addEventListener("click", () => {
      const next = readExpandMode() === "all" ? "compact" : "all";
      writeExpandMode(next);
      syncExpandToggleButton();
      applyExpandModeToVisibleCards(next);
    });
    // 페이지 로드 시 한 번, 그리고 lang 토글 시 한 번 라벨 동기화.
    syncExpandToggleButton();
    window.addEventListener("i18n:change", syncExpandToggleButton);
  }

  // ----------------------------------------------------------------------
  // 결과 렌더링
  // ----------------------------------------------------------------------
  function focusResultTitle() {
    if (!resultsTitle) return;
    try {
      resultsTitle.focus({ preventScroll: true });
    } catch {
      resultsTitle.focus();
    }
  }

  function revealResults(options = {}) {
    if (options.focus !== false) {
      focusResultTitle();
    }
    if (options.scroll !== false) {
      const behavior = options.focus === false ? "smooth" : "auto";
      resultsSection.scrollIntoView({ behavior, block: "start" });
    }
  }

  function renderResults(data, preserveFile = false, options = {}) {
    hideAll();
    resultsSection.classList.remove("hidden");
    // 새 결과를 그리면 키보드 selected 인덱스를 초기화. 사용자가 j 를 처음
    // 누를 때 0 번 카드로 이동한다.
    _selectedHitIdx = -1;

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

    // 1위 매칭 유사도가 낮으면 신뢰도 안내 배너를 띄운다. 카탈로그에 잘 맞는 곡이
    // 없을 때 순위만 보고 사용자가 과신하지 않도록 솔직하게 알려주는 장치.
    renderConfidenceNote(data.results);

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
      revealResults(options);
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
    // 사용자가 선택한 정렬 기준 적용. 원본 배열은 건드리지 않는다.
    const sortKey = resultsSortSelect ? resultsSortSelect.value : "similarity";
    const sorted = sortResults(data.results, data.summary || {}, sortKey);
    sorted.forEach((hit, idx) => {
      const li = tmpl.content.firstElementChild.cloneNode(true);
      li.querySelector(".rank-num").textContent = hit.rank;
      // 순위 단위 라벨(ko "위"). en 처럼 단위가 없는 언어에선 빈 문자열이라
      // 라벨 노드를 숨겨 숫자 밑에 빈 칸이 남지 않게 한다.
      const rankLabelEl = li.querySelector(".rank-label");
      const rankUnit = t("results.hitRankUnit");
      rankLabelEl.textContent = rankUnit;
      rankLabelEl.hidden = !rankUnit;
      li.querySelector(".hit-title").textContent = hit.title;
      li.querySelector(".hit-artist").textContent = hit.artist;
      li.querySelector(".hit-percent-num").textContent = hit.similarity_percent.toFixed(1);
      li.querySelector(".hit-percent-label").textContent = t("results.hitSimilarityLabel");

      const bar = li.querySelector(".hit-bar");
      bar.setAttribute("aria-valuenow", String(Math.round(hit.similarity_percent)));
      // progressbar 에 라벨이 없으면 스크린리더가 "55%" 만 읽고 무슨 값인지 모른다.
      // "곡명 유사도 55%" 형태로 맥락을 붙여준다.
      bar.setAttribute(
        "aria-label",
        `${hit.title} ${t("results.hitSimilarityLabel")} ${hit.similarity_percent.toFixed(1)}%`,
      );
      const fillEl = li.querySelector(".hit-bar-fill");
      // 약간의 지연을 두고 채우면 transition 이 실제로 보인다.
      setTimeout(() => {
        fillEl.style.width = `${Math.max(2, hit.similarity_percent)}%`;
      }, 60 + idx * 80);

      li.querySelector(".hit-summary").innerHTML = renderInlineMarkdown(hit.reason.summary || "");

      // 매칭 곡과 업로드 곡의 핵심 메트릭을 가로 mini-bar 로 비교 노출.
      const miniEl = li.querySelector(".hit-mini-metrics");
      if (miniEl) {
        miniEl.innerHTML = renderMiniMetrics(data.summary || {}, hit.match_summary);
      }

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
      // 카탈로그 페이지의 song deep-link 로 이동 — 모달 자동 오픈.
      const catalogLink = li.querySelector('[data-link="catalog"]');
      if (catalogLink) {
        const songKey = `${hit.title} - ${hit.artist}`;
        catalogLink.href = `/catalog?song=${encodeURIComponent(songKey)}`;
      }

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

      // 펼침 토글. 모드:
      //   "compact" (기본) — 1위만 펼침, 나머지 접힘. 첫 인상이 깔끔하고 모바일 스크롤이 짧다.
      //   "all"             — 모두 펼침. 사용자가 헤더의 토글로 선택 가능 (선호 localStorage 저장).
      const toggleBtn = li.querySelector(".hit-toggle");
      const mode = readExpandMode();
      const expanded = mode === "all" || idx === 0;
      li.dataset.expanded = expanded ? "true" : "false";
      toggleBtn.setAttribute("aria-expanded", expanded ? "true" : "false");
      toggleBtn.addEventListener("click", () => {
        const now = li.dataset.expanded === "true";
        const next = !now;
        li.dataset.expanded = next ? "true" : "false";
        toggleBtn.setAttribute("aria-expanded", next ? "true" : "false");
      });

      // staggered 등장 — 1위부터 차례로 살짝 fade-up. 앞쪽 5장만 지연을 주고
      // (90ms 간격) 그 뒤로는 지연 없이 — 카드가 많아도 마지막까지 기다리지 않게.
      li.classList.add("hit-enter");
      if (idx < 5) {
        li.style.animationDelay = `${idx * 0.09}s`;
      }

      hitList.appendChild(li);
    });

    if (!preserveFile && _lastFile && audioPlayer.classList.contains("hidden")) {
      setAudioPreview(_lastFile);
    }

    renderResultMeta(data);

    revealResults(options);
  }

  // 1위 매칭 유사도를 보고 신뢰도 안내 배너를 그린다.
  //   - 65% 이상: 배너 없음 (좋은 매칭).
  //   - 50~65%: "느슨하게 닮은" 수준 — 톤 다운된 info 안내.
  //   - 50% 미만: "잘 맞는 곡 없음" — 좀 더 강한 warn 안내.
  // 임계값은 z-score 거리 기반 코사인 유사도의 경험적 분포에서 잡았다. 카탈로그가
  // ~1000곡 규모라 정말 새로운 장르를 올리면 1위도 50%대로 떨어지는 일이 흔하다.
  function renderConfidenceNote(results) {
    const el = document.getElementById("confidence-note");
    if (!el) return;
    const topPct = Array.isArray(results) && results[0]
      ? Number(results[0].similarity_percent) || 0
      : 0;
    // 결과가 아예 없으면 (빈 상태) 배너도 숨김 — 빈 상태 카드가 따로 안내함.
    if (!Array.isArray(results) || results.length === 0 || topPct >= 65) {
      el.classList.add("hidden");
      el.innerHTML = "";
      el.removeAttribute("data-level");
      return;
    }
    const level = topPct < 50 ? "low" : "mid";
    const msgKey = level === "low" ? "results.confidenceLow" : "results.confidenceMid";
    const icon = level === "low" ? "⚠" : "ℹ";
    el.dataset.level = level;
    el.innerHTML =
      `<span class="confidence-note-icon" aria-hidden="true">${icon}</span>`
      + `<span class="confidence-note-text">${escapeHtml(t(msgKey, topPct.toFixed(1)))}</span>`;
    el.classList.remove("hidden");
  }

  // 분석 시각 ISO (UTC) 를 사용자 로컬 타임존으로 포맷한다. 한국 사용자는
  // "2026-05-15 13:42" 처럼 KST 로 보임 (백엔드 ISO 는 UTC). 파싱 실패 시
  // 원본 ISO 의 분 단위만 잘라 fallback.
  function formatLocalTimestamp(iso) {
    if (!iso) return "";
    const d = new Date(String(iso));
    if (!Number.isFinite(d.getTime())) {
      // 알 수 없는 형식 — 안전 fallback.
      return String(iso).slice(0, 16).replace("T", " ");
    }
    const locale = (window.i18n && window.i18n.lang() === "en") ? "en-US" : "ko-KR";
    return d.toLocaleString(locale, {
      year: "numeric", month: "2-digit", day: "2-digit",
      hour: "2-digit", minute: "2-digit",
      hour12: false,
    });
  }

  // 결과 페이지 분석 메타 footer — 분석 시각 / 카탈로그 크기 / 엔진 버전 /
  // 캐시 여부를 한 줄에 노출. 사용자가 결과 신뢰성을 가늠하거나 디버깅할 때 단서.
  function renderResultMeta(data) {
    const el = document.getElementById("result-meta");
    if (!el) return;
    const parts = [];
    if (data.analyzed_at) {
      // 사용자 로컬 타임존으로 변환. monospace 폰트라 정렬은 그대로 깔끔.
      const stamp = formatLocalTimestamp(data.analyzed_at);
      parts.push(`<span>${t("results.metaAnalyzedAt")} ${escapeHtml(stamp)}</span>`);
    }
    if (typeof data.catalog_size === "number") {
      const n = data.catalog_size.toLocaleString(
        window.i18n && window.i18n.lang() === "en" ? "en-US" : "ko-KR",
      );
      parts.push(`<span>${t("results.metaCatalogSize", n)}</span>`);
    }
    if (data.engine_version) {
      parts.push(`<span>v${escapeHtml(data.engine_version)}</span>`);
    }
    if (data.cached) {
      parts.push(`<span class="meta-cached">${t("results.metaCached")}</span>`);
    }
    if (!parts.length) {
      el.classList.add("hidden");
      el.innerHTML = "";
      return;
    }
    el.innerHTML = parts.join('<span class="sep" aria-hidden="true">·</span>');
    el.classList.remove("hidden");
  }

  // 결과 카드 정렬. 항상 rank 1~N 라벨은 그대로 유지하되 화면 노출 순서만 바꾼다.
  function sortResults(results, summary, key) {
    const copy = results.slice();
    if (key === "tempo") {
      const queryBpm = Number(summary.tempo_bpm) || 0;
      copy.sort((a, b) => {
        const ad = Math.abs((a.match_summary?.tempo_bpm ?? queryBpm) - queryBpm);
        const bd = Math.abs((b.match_summary?.tempo_bpm ?? queryBpm) - queryBpm);
        if (ad !== bd) return ad - bd;
        return (b.similarity_percent || 0) - (a.similarity_percent || 0);
      });
    } else if (key === "energy") {
      const queryE = Number(summary.energy_rms) || 0;
      copy.sort((a, b) => {
        const ad = Math.abs((a.match_summary?.energy_rms ?? queryE) - queryE);
        const bd = Math.abs((b.match_summary?.energy_rms ?? queryE) - queryE);
        if (ad !== bd) return ad - bd;
        return (b.similarity_percent || 0) - (a.similarity_percent || 0);
      });
    } else {
      // 기본: 유사도 내림차순.
      copy.sort((a, b) => (b.similarity_percent || 0) - (a.similarity_percent || 0));
    }
    return copy;
  }

  if (resultsSortSelect) {
    resultsSortSelect.addEventListener("change", () => {
      if (_lastResults) renderResults(_lastResults, /* preserveFile */ true, { focus: false, scroll: false });
    });
  }

  // 매칭 곡의 핵심 메트릭을 업로드한 곡과 가로 mini-bar 로 비교.
  // 빈 값이거나 매칭 메타가 없으면 아무것도 안 그린다.
  function renderMiniMetrics(query, match) {
    if (!match) return "";
    // 표시할 메트릭 + 정규화 범위. radar 와 같은 룰을 따라간다.
    // 라벨은 i18n.t() 로 해서 ko/en 토글에 즉시 반응하도록.
    const axes = [
      { key: "tempo_bpm", labelKey: "summary.tempo", min: 60, max: 200, unit: " BPM", digits: 0 },
      { key: "energy_rms", labelKey: "summary.energy", min: 0, max: 0.5, unit: "", digits: 3 },
      { key: "brightness", labelKey: "summary.brightness", min: 800, max: 6000, unit: " Hz", digits: 0 },
    ];
    function norm(v, ax) {
      const x = Number(v);
      if (!isFinite(x)) return 0;
      if (ax.max === ax.min) return 0.5;
      return Math.max(0, Math.min(1, (x - ax.min) / (ax.max - ax.min)));
    }
    function fmt(v, d) {
      if (typeof v !== "number" || !isFinite(v)) return "—";
      return v.toFixed(d);
    }
    return axes
      .map((ax) => {
        const qv = Number(query[ax.key]);
        const mv = Number(match[ax.key]);
        const qp = (norm(qv, ax) * 100).toFixed(1);
        const mp = (norm(mv, ax) * 100).toFixed(1);
        const label = t(ax.labelKey);
        return `
          <li>
            <span class="mini-label">${escapeHtml(label)}</span>
            <span class="mini-bars">
              <span class="mini-bar mini-bar-q" style="width: ${qp}%"></span>
              <span class="mini-bar mini-bar-m" style="width: ${mp}%"></span>
            </span>
            <span class="mini-vals">${fmt(qv, ax.digits)}${ax.unit} → ${fmt(mv, ax.digits)}${ax.unit}</span>
          </li>`;
      })
      .join("");
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
      // 실패 시: 이전 결과가 있으면 그 화면을 그대로 되돌려주고 토스트로만 알린다.
      // (showError 가 전체 결과 영역을 hide 해버려서 사용자가 직전 분석을 잃어버리던 회귀를 막음.)
      if (_seedPrev) {
        _lastResults = _seedPrev;
        renderResults(_seedPrev, /* preserveFile */ true);
        toast(t("results.seedFailedToast") || (err.message || String(err)));
      } else {
        showError(err.message || String(err));
      }
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

  // "샘플로 분석해보기" — 업로드 없이 카탈로그에서 랜덤 한 곡을 골라 by-catalog 분석.
  // 첫 방문자가 음원 준비 단계 없이 결과 페이지/차트/매칭 설명을 바로 체험할 수 있어
  // conversion 에 큰 도움. 누를 때마다 다른 곡이 뽑힘 (discovery 성).
  if (sampleBtn) {
    sampleBtn.addEventListener("click", async () => {
      // 중복 클릭 방어 — 첫 클릭 후 fetch 끝날 때까지 비활성.
      sampleBtn.disabled = true;
      const originalText = sampleBtn.textContent;
      sampleBtn.textContent = t("upload.sampleLoading");
      try {
        const res = await fetch("/api/catalog/random?n=1");
        if (!res.ok) throw new Error("HTTP " + res.status);
        const data = await res.json();
        const item = (data.items || [])[0];
        if (!item || !item.title) throw new Error("샘플을 찾지 못했어요.");
        // seedFromHit 가 by-catalog 분석 + 결과 렌더까지 모두 수행 → 코드 재사용.
        await seedFromHit({ title: item.title, artist: item.artist });
      } catch (err) {
        showError(err.message || String(err));
      } finally {
        sampleBtn.disabled = false;
        sampleBtn.textContent = originalText;
      }
    });
  }

  // ----------------------------------------------------------------------
  // 초기화
  // ----------------------------------------------------------------------
  resetBtn.addEventListener("click", () => {
    // 진행 중인 분석이 있으면 같이 cancel — 그 응답이 나중에 도착해서 빈
    // 화면에 결과가 갑자기 떠오르는 일을 막는다.
    if (_analysisAbortController) {
      try { _analysisAbortController.abort(); } catch (_) {}
      _analysisAbortController = null;
      _analysisInFlight = false;
    }
    setFile(null);
    setAudioPreview(null);
    _lastResults = null;
    _lastFile = null;
    _seedPrev = null;
    if (seedBackBtn) seedBackBtn.classList.add("hidden");
    fileInput.value = "";
    hideAll();
    // 결과가 박혀있던 hash 를 비워준다.
    try {
      history.replaceState(null, "", `${location.pathname}${location.search}`);
    } catch {}
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

  // 분석이 끝나면 결과를 URL hash 에 살짝 박아준다 — 새로고침이나 북마크로도
  // 결과가 살아남게. URL 이 너무 길어지면(약 12KB+) 그냥 hash 갱신을 포기한다.
  async function updateLocationHash(data) {
    if (!data) return;
    const token = await encodeForShare(data);
    if (!token) return;
    const newHash = `#r=${token}`;
    // 6KB(~base64 8000자) 보다 길면 일부 모바일 브라우저가 거부하니 안전선.
    if (newHash.length > 8000) return;
    try {
      history.replaceState(null, "", `${location.pathname}${location.search}${newHash}`);
    } catch {
      // history API 가 막힌 환경은 그냥 pass.
    }
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

  // ----- CSV 다운로드 ---------------------------------------------------
  // 비개발자가 엑셀에서 바로 가공할 수 있도록 결과를 CSV 로 떨궈준다. 외부
  // 라이브러리 없이 RFC 4180 기준 escape (큰따옴표는 두 번, 본문은 quote 감싸기)
  // + UTF-8 BOM (한글이 엑셀에서 깨지지 않도록).
  function buildResultsCsv(data) {
    const rows = Array.isArray(data && data.results) ? data.results : [];
    const summary = (data && data.summary) || {};

    const header = [
      "rank",
      "title",
      "artist",
      "similarity",
      "similarity_percent",
      "youtube_search_url",
      "spotify_search_url",
      // 업로드 곡의 핵심 메트릭은 모든 행에 함께 박아둔다 — 엑셀에서 1위만 보고
      // 비교하는 흔한 사용 패턴 대비.
      "query_tempo_bpm",
      "query_energy_rms",
      "query_brightness",
    ];

    function esc(v) {
      if (v == null) return "";
      const s = String(v);
      // CRLF / 콤마 / 쌍따옴표가 들어가면 quote 로 감싼다. 항상 감싸도 무방하지만,
      // 짧은 셀은 quote 없이 더 깔끔.
      if (/[",\r\n]/.test(s)) return '"' + s.replace(/"/g, '""') + '"';
      return s;
    }

    const lines = [header.join(",")];
    for (const r of rows) {
      lines.push([
        r.rank,
        r.title,
        r.artist,
        typeof r.similarity === "number" ? r.similarity.toFixed(6) : "",
        typeof r.similarity_percent === "number" ? r.similarity_percent.toFixed(2) : "",
        r.youtube_search_url || "",
        r.spotify_search_url || "",
        typeof summary.tempo_bpm === "number" ? summary.tempo_bpm.toFixed(2) : "",
        typeof summary.energy_rms === "number" ? summary.energy_rms.toFixed(4) : "",
        typeof summary.brightness === "number" ? summary.brightness.toFixed(1) : "",
      ].map(esc).join(","));
    }
    return "﻿" + lines.join("\r\n") + "\r\n"; // BOM + CRLF.
  }

  if (exportCsvBtn) {
    exportCsvBtn.addEventListener("click", () => {
      if (!_lastResults) return;
      const csv = buildResultsCsv(_lastResults);
      const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      const baseName = (_lastResults.filename || "soundmatch").replace(/\.[^.]+$/, "");
      const stamp = new Date().toISOString().slice(0, 10);
      a.href = url;
      a.download = `${baseName}.soundmatch-${stamp}.csv`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      setTimeout(() => URL.revokeObjectURL(url), 500);
    });
  }

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

  // PNG 저장 — 위에서 만든 SVG 문자열을 Image 로 한 번 그린 뒤 canvas 로 토출.
  // 외부 라이브러리 없이 브라우저 기본 기능만 사용한다.
  if (exportPngBtn) {
    exportPngBtn.addEventListener("click", async () => {
      if (!_lastResults) return;
      const svg = buildResultSvg(_lastResults);
      if (!svg) return;

      // SVG 의 width/height 가 viewBox 만 있고 명시되어 있지 않을 수 있어
      // 파싱해서 비율을 추출한 뒤 2배 스케일(retina 친화)로 그린다.
      const dimMatch = svg.match(/viewBox="0 0 (\d+) (\d+)"/);
      const baseW = dimMatch ? parseInt(dimMatch[1], 10) : 1200;
      const baseH = dimMatch ? parseInt(dimMatch[2], 10) : 720;
      const scale = 2;

      const baseName = (_lastResults.filename || "soundmatch").replace(/\.[^.]+$/, "");

      try {
        const url = URL.createObjectURL(new Blob([svg], { type: "image/svg+xml" }));
        const img = await new Promise((resolve, reject) => {
          const im = new Image();
          im.onload = () => resolve(im);
          im.onerror = () => reject(new Error("svg-load-failed"));
          im.src = url;
        });
        const canvas = document.createElement("canvas");
        canvas.width = baseW * scale;
        canvas.height = baseH * scale;
        const ctx = canvas.getContext("2d");
        ctx.scale(scale, scale);
        ctx.drawImage(img, 0, 0, baseW, baseH);
        URL.revokeObjectURL(url);
        canvas.toBlob((pngBlob) => {
          if (!pngBlob) {
            toast(t("results.exportPngFailed"));
            return;
          }
          const pngUrl = URL.createObjectURL(pngBlob);
          const a = document.createElement("a");
          a.href = pngUrl;
          a.download = `${baseName}.soundmatch.png`;
          document.body.appendChild(a);
          a.click();
          document.body.removeChild(a);
          setTimeout(() => URL.revokeObjectURL(pngUrl), 500);
        }, "image/png");
      } catch {
        toast(t("results.exportPngFailed"));
      }
    });
  }

  // ----------------------------------------------------------------------
  // 키보드 단축키
  //   "/"   : 파일 업로드에 포커스
  //   Esc   : 분석 결과 닫고 첫 화면으로
  //   Space : 결과 화면에서 재생/일시정지 (input 안에 있을 때는 동작 X)
  // ----------------------------------------------------------------------
  // 결과 hit 카드 사이를 j/k (↓/↑) 로 이동 — power user UX. selected 카드는
  // data-selected="true" 속성으로 CSS 가 시각적으로 강조.
  let _selectedHitIdx = -1;

  function selectHitByIdx(idx) {
    const cards = document.querySelectorAll(".hit-list .hit");
    if (!cards.length) return;
    const clamped = Math.max(0, Math.min(cards.length - 1, idx));
    cards.forEach((el, i) => {
      if (i === clamped) {
        el.dataset.selected = "true";
        el.scrollIntoView({ behavior: "smooth", block: "nearest" });
      } else {
        delete el.dataset.selected;
      }
    });
    _selectedHitIdx = clamped;
  }

  // 단축키 도움말 모달 — '?' 키로 토글 + Esc 로 닫기. a11y: focus trap + 이전 포커스 복원.
  const shortcutsModal = document.getElementById("shortcuts-modal");
  const shortcutsCloseBtn = document.getElementById("shortcuts-modal-close");
  const SHORTCUTS_FOCUSABLE_SEL =
    'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])';
  let _shortcutsPrevFocus = null;

  function shortcutsFocusable() {
    if (!shortcutsModal) return [];
    const nodes = shortcutsModal.querySelectorAll(SHORTCUTS_FOCUSABLE_SEL);
    return Array.from(nodes).filter((el) => !el.disabled);
  }

  function openShortcutsModal() {
    if (!shortcutsModal) return;
    _shortcutsPrevFocus = document.activeElement;
    shortcutsModal.hidden = false;
    // 첫 조작 가능 요소로 이동 (보통 닫기 버튼).
    setTimeout(() => {
      const nodes = shortcutsFocusable();
      if (nodes.length) nodes[0].focus();
    }, 0);
  }
  function closeShortcutsModal() {
    if (!shortcutsModal) return;
    shortcutsModal.hidden = true;
    // 이전 포커스로 복원 — 키보드 사용자가 흐름을 잃지 않도록.
    if (_shortcutsPrevFocus && typeof _shortcutsPrevFocus.focus === "function") {
      try { _shortcutsPrevFocus.focus(); } catch (_) {}
    }
    _shortcutsPrevFocus = null;
  }
  if (shortcutsCloseBtn) shortcutsCloseBtn.addEventListener("click", closeShortcutsModal);
  if (shortcutsModal) {
    shortcutsModal.addEventListener("click", (e) => {
      if (e.target === shortcutsModal) closeShortcutsModal();
    });
    // Tab 키 트랩 — 모달 내부 요소들 사이만 순환.
    shortcutsModal.addEventListener("keydown", (e) => {
      if (e.key !== "Tab") return;
      const nodes = shortcutsFocusable();
      if (!nodes.length) return;
      const first = nodes[0];
      const last = nodes[nodes.length - 1];
      const active = document.activeElement;
      if (e.shiftKey) {
        if (active === first || !shortcutsModal.contains(active)) {
          e.preventDefault();
          last.focus();
        }
      } else if (active === last) {
        e.preventDefault();
        first.focus();
      }
    });
  }

  document.addEventListener("keydown", (e) => {
    const target = e.target;
    const isTyping =
      target &&
      (target.tagName === "INPUT" ||
        target.tagName === "TEXTAREA" ||
        target.tagName === "SELECT" ||
        target.isContentEditable);
    const resultsOpen = !resultsSection.classList.contains("hidden");
    const shortcutsOpen = shortcutsModal && !shortcutsModal.hidden;

    // 단축키 도움말이 열려 있으면 Esc 가 최우선 — 그 외 단축키는 잡지 않는다.
    if (shortcutsOpen) {
      if (e.key === "Escape") {
        e.preventDefault();
        closeShortcutsModal();
      }
      return;
    }

    // '?' 키 (보통 Shift + /) — 어디서든 도움말 열림. 단 입력창 안에서는 X.
    if (e.key === "?" && !isTyping) {
      e.preventDefault();
      openShortcutsModal();
      return;
    }

    if (e.key === "/" && !isTyping) {
      e.preventDefault();
      fileInput.focus();
      dropzone.classList.add("is-drag");
      setTimeout(() => dropzone.classList.remove("is-drag"), 280);
    } else if (e.key === "Escape" && resultsOpen) {
      resetBtn.click();
    } else if (e.key === " " && !isTyping && resultsOpen && audioPreview.src) {
      e.preventDefault();
      if (audioPreview.paused) audioPreview.play();
      else audioPreview.pause();
    } else if (!isTyping && resultsOpen && (e.key === "j" || e.key === "ArrowDown")) {
      // 다음 hit 카드.
      e.preventDefault();
      selectHitByIdx(_selectedHitIdx + 1);
    } else if (!isTyping && resultsOpen && (e.key === "k" || e.key === "ArrowUp")) {
      // 이전 hit 카드.
      e.preventDefault();
      selectHitByIdx(_selectedHitIdx <= 0 ? 0 : _selectedHitIdx - 1);
    } else if (!isTyping && resultsOpen && e.key === "Enter" && _selectedHitIdx >= 0) {
      // 선택된 카드 펼침/접힘 토글.
      const cards = document.querySelectorAll(".hit-list .hit");
      const li = cards[_selectedHitIdx];
      if (li) {
        e.preventDefault();
        const tb = li.querySelector(".hit-toggle");
        if (tb) tb.click();
      }
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
      return true;
    } catch (err) {
      // localStorage 쿼터(5MB) 초과 / private mode 등에서 실패. silently
      // no-op 이면 사용자는 "히스토리가 안 늘어남" 만 보고 영문을 모름.
      // 토스트로 알리되 분석 자체는 계속 동작하도록 그대로 둔다.
      console.warn("[soundmatch] writeHistory failed:", err);
      try {
        toast(t("history.storageFull"));
      } catch (e) {
        // 토스트 헬퍼가 없으면 무시.
      }
      return false;
    }
  }
  function addToHistory(data) {
    const items = readHistory();
    // 히스토리는 메타 정보 위주로 가볍게 저장한다. 멜 스펙트로그램 SVG 는
    // ~320KB 라 5건만으로 1.6MB 를 점유 → 즐겨찾기와 같은 5MB 쿼터를 빠르게
    // 잠식. radar / waveform 같은 그래프는 결과 화면을 다시 그릴 때 매번
    // 새로 계산하므로 저장하지 않아도 영향 없음.
    const trimmed = Object.assign({}, data, { spectrogram_svg: "" });
    const entry = {
      ts: Date.now(),
      filename: data.filename,
      topTitle: data.results && data.results[0] && data.results[0].title,
      topArtist: data.results && data.results[0] && data.results[0].artist,
      topPercent: data.results && data.results[0] && data.results[0].similarity_percent,
      data: trimmed,
    };
    items.unshift(entry);
    if (!writeHistory(items)) {
      // 쓰기 실패한 상황에서는 in-memory render 도 무의미 (다음 로드 때
      // 동기화가 안 되어 사용자가 혼란). 그냥 기존 히스토리만 다시 그린다.
      renderHistory();
      return;
    }
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
