(function () {
    var input = document.getElementById("cat-search-input");
    var grid = document.getElementById("cat-grid");
    var meta = document.getElementById("cat-meta");
    var prev = document.getElementById("cat-prev");
    var next = document.getElementById("cat-next");
    var first = document.getElementById("cat-first");
    var last = document.getElementById("cat-last");
    var pageLabel = document.getElementById("cat-page-label");
    var favOnly = document.getElementById("cat-favorites-only");
    var minBpmEl = document.getElementById("cat-min-bpm");
    var maxBpmEl = document.getElementById("cat-max-bpm");
    var minEEl = document.getElementById("cat-min-energy");
    var maxEEl = document.getElementById("cat-max-energy");
    var sortEl = document.getElementById("cat-sort");
    var sizeEl = document.getElementById("cat-size");

    var state = {
      q: "", page: 1, size: 24, total: 0, hasMore: false, favOnly: false,
      minBpm: "", maxBpm: "", minEnergy: "", maxEnergy: "", sort: "default",
      // 현재 열려 있는 모달 곡 이름. 모달이 닫히면 빈 문자열.
      song: "",
    };
    var debounceTimer = null;
    var urlWriteTimer = null;
    var Fav = window.SoundMatchFavorites;
    // 페이지 이동 (next / prev / first / last) 직후 다음 render() 가 끝나면 첫 카드에
    // 포커스를 두기 위한 1회용 플래그. 검색어 입력 같은 인터랙티브 흐름에서는 해당 X.
    var _pendingFocusFirstCard = false;

    // 카드 간 화살표 이동 — DOM 순서 기준으로 ±N 칸 이동. row-aware 까지는 안 가지만
    // 1000곡 규모에서 직관적으로 동작한다 (←/→ = 가로 한 칸, ↑/↓ = 다음 행은 보통
    // 다음 카드라 자연스러움).
    function moveFocusByOffset(currentEl, offset) {
      var cards = Array.prototype.slice.call(document.querySelectorAll(".cat-card"));
      var idx = cards.indexOf(currentEl);
      if (idx < 0) return;
      var nextIdx = idx + offset;
      if (nextIdx < 0 || nextIdx >= cards.length) return;
      cards[nextIdx].focus();
    }
    // i18n 이 아직 안 붙은 경우의 안전 폴백. 키를 그대로 돌려줘서 UI 가 깨지지 않음.
    function t(key) {
      try {
        if (window.i18n && typeof window.i18n.t === "function") {
          var args = Array.prototype.slice.call(arguments, 1);
          return window.i18n.t.apply(null, [key].concat(args));
        }
      } catch (e) {}
      return key;
    }

    // ------------------------------------------------------------------
    // URL <-> state 동기화. 새로고침이나 링크 공유 시 동일한 필터로 복원되도록
    // q/페이지/필터/정렬/즐겨찾기 모드를 모두 URLSearchParams 에 싣는다.
    // ------------------------------------------------------------------
    function clampNumber(raw, lo, hi) {
      var n = parseFloat(raw);
      if (!Number.isFinite(n)) return "";
      if (n < lo) n = lo;
      if (n > hi) n = hi;
      // 정수 BPM 은 그대로, 에너지 0~1 은 소수점 두 자리까지.
      return Math.abs(n - Math.round(n)) < 1e-9 ? String(Math.round(n)) : String(n);
    }

    function readStateFromUrl() {
      try {
        var p = new URLSearchParams(window.location.search);
        if (p.has("q")) state.q = (p.get("q") || "").slice(0, 200);
        var pageRaw = parseInt(p.get("page") || "1", 10);
        if (Number.isFinite(pageRaw) && pageRaw >= 1 && pageRaw <= 1000) state.page = pageRaw;
        var sizeRaw = parseInt(p.get("size") || "", 10);
        if (Number.isFinite(sizeRaw) && sizeRaw >= 6 && sizeRaw <= 100) state.size = sizeRaw;
        var sortRaw = p.get("sort") || "";
        var allowedSort = ["default", "title", "artist", "bpm", "energy", "shuffle"];
        if (allowedSort.indexOf(sortRaw) !== -1) state.sort = sortRaw;
        if (p.has("min_bpm")) state.minBpm = clampNumber(p.get("min_bpm"), 0, 400);
        if (p.has("max_bpm")) state.maxBpm = clampNumber(p.get("max_bpm"), 0, 400);
        if (p.has("min_energy")) state.minEnergy = clampNumber(p.get("min_energy"), 0, 1);
        if (p.has("max_energy")) state.maxEnergy = clampNumber(p.get("max_energy"), 0, 1);
        if (p.get("fav_only") === "1") state.favOnly = true;
        // song 은 길이 제한만 두고 그대로 받는다 — "Title - Artist" 형태.
        if (p.has("song")) state.song = (p.get("song") || "").slice(0, 400);
      } catch (e) {
        // URL 파싱 실패해도 기본 상태로 그냥 계속.
      }
    }

    function writeStateToUrl() {
      // input 마다 호출되므로 디바운스. 한 번 history.replaceState 만 하면 충분.
      clearTimeout(urlWriteTimer);
      urlWriteTimer = setTimeout(function () {
        try {
          var p = new URLSearchParams();
          if (state.q) p.set("q", state.q);
          if (state.page > 1) p.set("page", String(state.page));
          if (state.sort && state.sort !== "default") p.set("sort", state.sort);
          if (state.minBpm !== "") p.set("min_bpm", state.minBpm);
          if (state.maxBpm !== "") p.set("max_bpm", state.maxBpm);
          if (state.minEnergy !== "") p.set("min_energy", state.minEnergy);
          if (state.maxEnergy !== "") p.set("max_energy", state.maxEnergy);
          if (state.favOnly) p.set("fav_only", "1");
          if (state.song) p.set("song", state.song);
          // 기본 24 와 다를 때만 size 를 URL 에 노출 — 짧고 깨끗하게.
          if (state.size && state.size !== 24) p.set("size", String(state.size));
          var qs = p.toString();
          var next = window.location.pathname + (qs ? "?" + qs : "") + window.location.hash;
          // history 스택을 망치지 않게 replaceState.
          window.history.replaceState(null, "", next);
        } catch (e) {}
      }, 180);
    }

    function applyStateToInputs() {
      // URL 에서 복원된 값을 input/select 에도 반영해야 사용자가 화면을 봤을 때 일치한다.
      if (input) input.value = state.q || "";
      if (favOnly) favOnly.checked = !!state.favOnly;
      if (minBpmEl) minBpmEl.value = state.minBpm;
      if (maxBpmEl) maxBpmEl.value = state.maxBpm;
      if (minEEl) minEEl.value = state.minEnergy;
      if (maxEEl) maxEEl.value = state.maxEnergy;
      if (sortEl) sortEl.value = state.sort || "default";
      if (sizeEl) {
        // select 에 명시적으로 노출된 값(24/48/96) 안에 있을 때만 그 옵션을 선택.
        // 그 외(예: URL 에 size=10 같은 비정상 값)는 기본 24 표시.
        var allowedSizes = ["24", "48", "96"];
        sizeEl.value = allowedSizes.indexOf(String(state.size)) !== -1
          ? String(state.size)
          : "24";
      }
    }

    // 빈 결과 상태에서 호출 — 모든 필터를 기본값으로 되돌리고 다시 로드.
    function resetFilters() {
      state.q = "";
      state.minBpm = "";
      state.maxBpm = "";
      state.minEnergy = "";
      state.maxEnergy = "";
      state.sort = "default";
      state.favOnly = false;
      state.page = 1;
      state.size = 24;  // 페이지당 곡 수도 기본값으로 되돌린다.
      state.song = ""; // 혹시 모달이 열려 있으면 같이 닫는다.
      modal.classList.remove("is-open");
      document.body.style.overflow = "";
      applyStateToInputs();
      writeStateToUrl();
      _syncHistActiveState();
      load();
    }

    function escapeHtml(s) {
      return String(s == null ? "" : s)
        .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;").replace(/'/g, "&#039;");
    }

    // 최근 검색어 (localStorage 기반). datalist 로 노출돼서 같은 단어 또
    // 칠 때 자동완성으로 골라잡기 편하다. 같은 검색어가 들어오면 맨 위로
    // 끌어올리고, 최대 5건만 유지.
    var RECENT_SEARCH_KEY = "soundmatch.catalog.recent-searches";
    var RECENT_SEARCH_MAX = 5;

    function readRecentSearches() {
      try {
        var raw = localStorage.getItem(RECENT_SEARCH_KEY);
        if (!raw) return [];
        var parsed = JSON.parse(raw);
        return Array.isArray(parsed) ? parsed.filter(function (s) { return typeof s === "string"; }) : [];
      } catch (e) {
        return [];
      }
    }

    function writeRecentSearches(items) {
      try {
        localStorage.setItem(RECENT_SEARCH_KEY, JSON.stringify(items.slice(0, RECENT_SEARCH_MAX)));
      } catch (e) {
        // 쿼터 초과 / 시크릿 모드 등은 무시.
      }
    }

    function pushRecentSearch(q) {
      var s = (q || "").trim();
      if (!s || s.length < 2) return; // 한 글자는 의미 적음.
      var items = readRecentSearches().filter(function (x) { return x !== s; });
      items.unshift(s);
      writeRecentSearches(items);
      renderRecentSearches();
    }

    function renderRecentSearches() {
      var dl = document.getElementById("cat-recent-searches");
      if (!dl) return;
      var items = readRecentSearches();
      dl.innerHTML = items
        .map(function (s) { return '<option value="' + escapeHtml(s) + '"></option>'; })
        .join("");
    }
    renderRecentSearches();

    // ------------------------------------------------------------------
    // 최근 본 곡 — 모달을 열어본 곡을 localStorage 에 쌓아 칩으로 노출한다.
    // 즐겨찾기처럼 영구 저장은 아니고 "방금 둘러본 흔적" 정도의 가벼운 네비 보조.
    // ------------------------------------------------------------------
    var RECENT_VIEWED_KEY = "soundmatch.catalog.recently-viewed";
    var RECENT_VIEWED_MAX = 8;

    function readRecentViewed() {
      try {
        var raw = localStorage.getItem(RECENT_VIEWED_KEY);
        if (!raw) return [];
        var parsed = JSON.parse(raw);
        return Array.isArray(parsed) ? parsed.filter(function (s) { return typeof s === "string"; }) : [];
      } catch (e) {
        return [];
      }
    }

    function pushRecentViewed(name) {
      var s = (name || "").trim();
      if (!s) return;
      // 같은 곡이 이미 있으면 제거 후 맨 앞으로 — 최신순 유지.
      var items = readRecentViewed().filter(function (x) { return x !== s; });
      items.unshift(s);
      items = items.slice(0, RECENT_VIEWED_MAX);
      try {
        localStorage.setItem(RECENT_VIEWED_KEY, JSON.stringify(items));
      } catch (e) { /* 쿼터 초과 / 시크릿 모드 무시 */ }
      renderRecentViewed();
    }

    function renderRecentViewed() {
      var wrap = document.getElementById("cat-recent");
      var chips = document.getElementById("cat-recent-chips");
      if (!wrap || !chips) return;
      var items = readRecentViewed();
      if (!items.length) {
        wrap.hidden = true;
        chips.innerHTML = "";
        return;
      }
      chips.innerHTML = items.map(function (name) {
        var parts = name.split(" - ");
        var title = parts[0] || name;
        var artist = parts.slice(1).join(" - ");
        return '<button type="button" class="cat-recent-chip" data-key="' + escapeHtml(name)
          + '" title="' + escapeHtml(name) + '">'
          + escapeHtml(title)
          + (artist ? ' <span class="chip-artist">· ' + escapeHtml(artist) + '</span>' : '')
          + '</button>';
      }).join("");
      chips.querySelectorAll(".cat-recent-chip").forEach(function (btn) {
        btn.addEventListener("click", function () {
          openSimilarModal(btn.getAttribute("data-key"));
        });
      });
      wrap.hidden = false;
    }

    var recentClearBtn = document.getElementById("cat-recent-clear");
    if (recentClearBtn) {
      recentClearBtn.addEventListener("click", function () {
        try { localStorage.removeItem(RECENT_VIEWED_KEY); } catch (e) {}
        renderRecentViewed();
      });
    }
    renderRecentViewed();

    // 검색어와 매칭된 부분만 <mark> 로 감싸 강조. escape 는 직접 처리하므로
    // 호출 측에서 추가 escape 가 필요 없다. 케이스 무시.
    function highlightMatch(text, needle) {
      var raw = String(text == null ? "" : text);
      if (!needle) return escapeHtml(raw);
      var lower = raw.toLowerCase();
      var needleLower = needle.toLowerCase();
      var nlen = needleLower.length;
      if (nlen === 0) return escapeHtml(raw);
      var out = "";
      var i = 0;
      while (i < raw.length) {
        var idx = lower.indexOf(needleLower, i);
        if (idx === -1) {
          out += escapeHtml(raw.slice(i));
          break;
        }
        out += escapeHtml(raw.slice(i, idx));
        out += '<mark class="cat-highlight">' + escapeHtml(raw.slice(idx, idx + nlen)) + '</mark>';
        i = idx + nlen;
      }
      return out;
    }

    // 페이저 4개 버튼 (first / prev / next / last) 의 disabled / pageLabel 갱신을
    // 한 군데에서 관리. load() 가 어떤 분기에서 끝나도 동일하게 호출한다.
    function syncPagerControls() {
      pageLabel.textContent = "p. " + state.page;
      prev.disabled = state.page <= 1;
      next.disabled = !state.hasMore;
      if (first) first.disabled = state.page <= 1;
      if (last) {
        if (!state.total || !state.size) {
          last.disabled = true;
        } else {
          var lastPage = Math.max(1, Math.ceil(state.total / state.size));
          last.disabled = state.page >= lastPage;
        }
      }
    }

    // 로딩 중 그리드를 스켈레톤 카드로 채운다. 이전 결과가 그대로 남아 있으면
    // 사용자가 "이게 새 결과인지 옛 결과인지" 헷갈리고, 빈 그리드면 레이아웃이
    // 출렁인다. 직전 페이지의 카드 수만큼 (최대 12개) 깔아 자리를 유지한다.
    function renderSkeletons() {
      var n = Math.min(Math.max(grid.querySelectorAll(".cat-card").length || state.size || 12, 6), 12);
      var cell =
        '<div class="cat-card-skel" aria-hidden="true">'
        + '<span class="skel-line t"></span>'
        + '<span class="skel-line a"></span>'
        + '<span class="skel-line m"></span>'
        + '</div>';
      grid.innerHTML = new Array(n + 1).join(cell);
    }

    async function load() {
      meta.textContent = t("catalog.loading");
      renderSkeletons();

      // 즐겨찾기 전용 모드는 백엔드 호출 없이 localStorage 만 사용한다.
      if (state.favOnly && Fav) {
        var favs = Fav.list().filter(function (f) {
          if (!state.q) return true;
          return (f.name || "").toLowerCase().indexOf(state.q.toLowerCase()) !== -1;
        });
        var start = (state.page - 1) * state.size;
        var end = start + state.size;
        var slice = favs.slice(start, end).map(function (f) {
          return { title: f.title, artist: f.artist };
        });
        state.total = favs.length;
        state.hasMore = end < favs.length;
        render(slice);
        if (favs.length === 0) {
          meta.textContent = t("catalog.emptyFavorites");
        } else {
          var rs = start + 1;
          var re = Math.min(rs + slice.length - 1, favs.length);
          meta.textContent = t("catalog.metaRange", favs.length, rs, re);
        }
        syncPagerControls();
        return;
      }

      try {
        var qs = [
          "q=" + encodeURIComponent(state.q),
          "page=" + state.page,
          "size=" + state.size,
          "sort=" + encodeURIComponent(state.sort || "default"),
        ];
        if (state.minBpm !== "") qs.push("min_bpm=" + encodeURIComponent(state.minBpm));
        if (state.maxBpm !== "") qs.push("max_bpm=" + encodeURIComponent(state.maxBpm));
        if (state.minEnergy !== "") qs.push("min_energy=" + encodeURIComponent(state.minEnergy));
        if (state.maxEnergy !== "") qs.push("max_energy=" + encodeURIComponent(state.maxEnergy));
        var url = "/api/catalog/search?" + qs.join("&");
        var res = await fetch(url);
        if (!res.ok) throw new Error("HTTP " + res.status);
        var data = await res.json();
        state.total = data.total;
        state.hasMore = data.has_more;
        render(data.items);
        var rangeStart = (state.page - 1) * state.size + 1;
        var rangeEnd = Math.min(rangeStart + data.items.length - 1, data.total);
        if (data.total === 0) {
          meta.textContent = t("catalog.empty");
        } else {
          meta.textContent = t("catalog.metaRange", data.total, rangeStart, rangeEnd);
        }
        syncPagerControls();
        // 검색어가 의미 있는 결과를 냈을 때만 history 에 기록 (0건 검색은 노이즈).
        if (state.q && data.total > 0) {
          pushRecentSearch(state.q);
        }
      } catch (e) {
        meta.textContent = t("catalog.loadFail");
        grid.innerHTML = '<p class="cat-empty">' + escapeHtml(t("catalog.retryHint")) + '</p>';
      }
    }

    // 카탈로그 카드 아래에 BPM / 에너지 / 밝기 mini-row 를 만든다.
    // 메트릭 객체가 없거나 모든 값이 null 이면 빈 문자열 (line 자체 안 그림).
    function buildMetricsLine(m) {
      if (!m || typeof m !== "object") return "";
      var parts = [];
      if (typeof m.bpm === "number" && m.bpm > 0) {
        parts.push('<span>BPM ' + Math.round(m.bpm) + '</span>');
      }
      if (typeof m.energy_rms === "number" && m.energy_rms > 0) {
        parts.push('<span>E ' + m.energy_rms.toFixed(2) + '</span>');
      }
      if (typeof m.brightness === "number" && m.brightness > 0) {
        parts.push('<span>' + Math.round(m.brightness) + 'Hz</span>');
      }
      if (!parts.length) return "";
      return '<span class="cat-metrics">'
        + parts.join('<span class="sep" aria-hidden="true">·</span>')
        + '</span>';
    }

    // 시드 곡 모달 헤더 — 메트릭 + 즐겨찾기 토글.
    // by-catalog 응답의 summary 는 {tempo_bpm, energy_rms, brightness, ...} 형태인데
    // buildMetricsLine 은 {bpm, energy_rms, brightness} 키를 기대하므로 한 번 변환.
    function renderSeedMetrics(summary) {
      var host = document.getElementById("modal-seed-metrics");
      if (!host) return;
      if (!summary) { host.innerHTML = ""; return; }
      // tempo_bpm 키 → bpm 으로 매핑.
      var adapted = {
        bpm: summary.tempo_bpm,
        energy_rms: summary.energy_rms,
        brightness: summary.brightness,
      };
      // buildMetricsLine 결과는 <span class="cat-metrics">…</span> 한 줄. inner 만 떼서 host 에 넣음.
      var raw = buildMetricsLine(adapted);
      host.innerHTML = raw
        ? raw.replace('<span class="cat-metrics">', '').replace(/<\/span>$/, '')
        : '';
    }

    function setupSeedFavButton(fullName, title, artist) {
      var btn = document.getElementById("modal-fav-seed");
      if (!btn || !Fav || !fullName) return;
      var apply = function () {
        var on = Fav.has(fullName);
        btn.setAttribute("aria-pressed", on ? "true" : "false");
      };
      apply();
      // 모달이 새로 열릴 때마다 핸들러를 갈아끼우므로 이전 리스너 흔적은 onclick 으로 덮어 정리.
      btn.onclick = function (e) {
        e.stopPropagation();
        Fav.toggle(fullName, title, artist);
        apply();
        // 즐겨찾기 전용 모드에서 시드를 풀면 카드 그리드 갱신.
        if (state.favOnly) load();
      };
    }

    function render(items) {
      if (!items || !items.length) {
        var msg = state.favOnly
          ? t("catalog.emptyFavoritesHint")
          : t("catalog.emptyHint");
        // 필터가 한 개라도 걸려 있으면 "초기화" 버튼도 같이 노출.
        var hasFilters = !!(state.q || state.minBpm || state.maxBpm
          || state.minEnergy || state.maxEnergy
          || (state.sort && state.sort !== "default") || state.favOnly);
        var resetBtn = hasFilters
          ? '<button type="button" class="cat-empty-reset" id="cat-empty-reset">'
            + escapeHtml(t("catalog.resetFilters")) + '</button>'
          : "";
        grid.innerHTML = '<p class="cat-empty">' + escapeHtml(msg) + '</p>' + resetBtn;
        var btn = document.getElementById("cat-empty-reset");
        if (btn) btn.addEventListener("click", resetFilters);
        return;
      }
      var cardHint = t("catalog.cardHint");
      var favAdd = t("catalog.favAdd");
      var favRemove = t("catalog.favRemove");
      // 즐겨찾기 전용 모드에선 자체 필터만 쓰니까 강조는 그대로 검색 q.
      var needle = state.q || "";
      grid.innerHTML = items.map(function (it) {
        var key = it.title + ' - ' + it.artist;
        var isFav = Fav ? Fav.has(key) : false;
        return '<div class="cat-card" data-key="' + escapeHtml(key) + '"'
          + ' title="' + escapeHtml(cardHint) + '" tabindex="0" role="button">'
          + '<div class="cat-card-head">'
          +   '<div class="cat-card-body">'
          +     '<span class="cat-title">' + highlightMatch(it.title, needle) + '</span>'
          +     '<span class="cat-artist">' + highlightMatch(it.artist, needle) + '</span>'
          +     buildMetricsLine(it.metrics)
          +   '</div>'
          +   '<button type="button" class="cat-fav-btn" data-fav="' + escapeHtml(key)
          +     '" data-title="' + escapeHtml(it.title) + '" data-artist="' + escapeHtml(it.artist)
          +     '" data-active="' + (isFav ? 'true' : 'false')
          +     '" aria-pressed="' + (isFav ? 'true' : 'false')
          +     '" title="' + escapeHtml(isFav ? favRemove : favAdd) + '">★</button>'
          + '</div>'
          + '</div>';
      }).join("");

      grid.querySelectorAll(".cat-card").forEach(function (el) {
        el.addEventListener("click", function (e) {
          // ★ 버튼 클릭은 상위 카드 클릭과 분리.
          if (e.target.closest(".cat-fav-btn")) return;
          openSimilarModal(el.getAttribute("data-key"), el);
        });
        el.addEventListener("keydown", function (e) {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            openSimilarModal(el.getAttribute("data-key"), el);
            return;
          }
          // 화살표 키 네비게이션 — 키보드 사용자가 1000곡 카탈로그를 빠르게 훑을 수 있게.
          // ←/↑ = 이전 카드, →/↓ = 다음 카드. 첫/마지막에서는 그 자리에 머무름 (wrap 안 함).
          if (e.key === "ArrowRight" || e.key === "ArrowDown") {
            e.preventDefault();
            moveFocusByOffset(el, 1);
          } else if (e.key === "ArrowLeft" || e.key === "ArrowUp") {
            e.preventDefault();
            moveFocusByOffset(el, -1);
          } else if (e.key === "Home") {
            e.preventDefault();
            var first = grid.querySelector(".cat-card");
            if (first) first.focus();
          } else if (e.key === "End") {
            e.preventDefault();
            var cards = grid.querySelectorAll(".cat-card");
            if (cards.length) cards[cards.length - 1].focus();
          }
        });
      });

      // 페이지가 새로 로드된 직후 — 사용자가 키보드로 페이저를 누른 직후처럼 — 첫 카드로
      // 포커스 이동을 자연스럽게 유도하기 위해, 직전 액션이 페이저 next/prev 였으면
      // 첫 카드에 포커스를 둔다. 일반 fetch (검색어 입력 등) 에서는 포커스를 그대로 두어
      // 입력 흐름을 방해하지 않는다.
      if (_pendingFocusFirstCard) {
        _pendingFocusFirstCard = false;
        var firstCard = grid.querySelector(".cat-card");
        if (firstCard) firstCard.focus();
      }

      grid.querySelectorAll(".cat-fav-btn").forEach(function (btn) {
        btn.addEventListener("click", function (e) {
          e.stopPropagation();
          if (!Fav) return;
          var key = btn.getAttribute("data-fav");
          Fav.toggle(key, btn.getAttribute("data-title"), btn.getAttribute("data-artist"));
          var nowActive = Fav.has(key);
          btn.setAttribute("data-active", nowActive ? "true" : "false");
          btn.setAttribute("aria-pressed", nowActive ? "true" : "false");
          btn.title = nowActive ? t("catalog.favRemove") : t("catalog.favAdd");
          // favOnly 모드에서 마지막 항목을 풀면 화면이 비어버려야 한다.
          if (state.favOnly) load();
        });
      });
    }

    // -------------------- 결과 모달 --------------------
    var modal = document.getElementById("modal-backdrop");
    var modalTitle = document.getElementById("modal-title");
    var modalSub = document.getElementById("modal-sub");
    var modalBody = document.getElementById("modal-body");
    var modalTags = document.getElementById("modal-tags");
    var modalClose = document.getElementById("modal-close");
    var _lastFocusedEl = null;

    function closeModal() {
      modal.classList.remove("is-open");
      document.body.style.overflow = "";
      if (_lastFocusedEl) _lastFocusedEl.focus();
      // URL 에서 song= 도 같이 제거. 다른 필터는 그대로 유지.
      if (state.song) {
        state.song = "";
        writeStateToUrl();
      }
    }
    modalClose.addEventListener("click", closeModal);
    modal.addEventListener("click", function (e) {
      if (e.target === modal) closeModal();
    });

    // 짧은 토스트 — 같은 토스트가 빠르게 연달아 호출되면 timer 만 리셋.
    var _toastTimer = null;

    function showToast(msg) {
      var el = document.getElementById("cat-toast");
      if (!el) return;
      el.textContent = msg;
      el.hidden = false;
      // 다음 프레임에 visible 클래스 — display:none → block 전환의 transition 안 먹히는 문제 회피.
      requestAnimationFrame(function () { el.classList.add("is-visible"); });
      clearTimeout(_toastTimer);
      _toastTimer = setTimeout(function () {
        el.classList.remove("is-visible");
        // 페이드아웃 끝난 뒤 hidden 처리 (screen reader 가 다시 읽지 않게).
        setTimeout(function () { el.hidden = true; }, 220);
      }, 1800);
    }

    // 공유 링크 복사 — 현재 URL (state.song 이 ?song= 로 박혀 있는 상태) 을 clipboard 로.
    // 모달이 열려 있을 때만 의미 있으므로, 모달이 닫혀 있으면 그냥 무시.
    var copyLinkBtn = document.getElementById("modal-copy-link");
    if (copyLinkBtn) {
      copyLinkBtn.addEventListener("click", function () {
        if (!modal.classList.contains("is-open")) return;
        var url = window.location.href;
        // navigator.clipboard 가 안 되는 환경 (file://, 권한 거부) 을 위한 fallback.
        var done = function () {
          showToast(t("catalog.linkCopied"));
          copyLinkBtn.classList.add("is-copied");
          setTimeout(function () { copyLinkBtn.classList.remove("is-copied"); }, 1500);
        };
        var fail = function () { showToast(t("catalog.linkCopyFail")); };
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(url).then(done).catch(function () {
            // 일부 브라우저 (구형 Safari) 는 promise 안 뱉고 throw — 그대로 fallback 으로.
            try { _legacyCopy(url); done(); } catch (e) { fail(); }
          });
        } else {
          try { _legacyCopy(url); done(); } catch (e) { fail(); }
        }
      });
    }

    // execCommand("copy") legacy 경로. 보안 정책상 user gesture 안에서만 호출되어야 한다.
    function _legacyCopy(text) {
      var ta = document.createElement("textarea");
      ta.value = text;
      ta.setAttribute("readonly", "");
      ta.style.position = "fixed";
      ta.style.top = "-1000px";
      document.body.appendChild(ta);
      ta.select();
      var ok = false;
      try { ok = document.execCommand("copy"); } catch (e) { ok = false; }
      document.body.removeChild(ta);
      if (!ok) throw new Error("legacy copy failed");
    }

    // 모달이 열린 상태에서 키 처리. Esc 로 닫고, Tab 이면 포커스를 모달 안에서만 순환.
    var FOCUSABLE_SEL =
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])';
    function focusableInModal() {
      var nodes = modal.querySelectorAll(FOCUSABLE_SEL);
      var visible = [];
      for (var i = 0; i < nodes.length; i++) {
        var el = nodes[i];
        // hidden / disabled 요소는 제외.
        if (el.disabled) continue;
        if (el.getAttribute("aria-hidden") === "true") continue;
        if (el.offsetWidth === 0 && el.offsetHeight === 0 && el.getClientRects().length === 0) continue;
        visible.push(el);
      }
      return visible;
    }
    document.addEventListener("keydown", function (e) {
      if (!modal.classList.contains("is-open")) return;
      if (e.key === "Escape") {
        closeModal();
        return;
      }
      if (e.key !== "Tab") return;
      // 포커스 트랩 — Tab/Shift+Tab 시 모달 내부 첫/끝 요소를 wrap.
      var nodes = focusableInModal();
      if (!nodes.length) return;
      var first = nodes[0];
      var last = nodes[nodes.length - 1];
      var active = document.activeElement;
      if (e.shiftKey) {
        if (active === first || !modal.contains(active)) {
          e.preventDefault();
          last.focus();
        }
      } else if (active === last) {
        e.preventDefault();
        first.focus();
      }
    });

    async function openSimilarModal(name, triggerCard) {
      // 상태 + URL 에 곡 이름을 박아두고 열기 — 새로고침이나 공유 시 같은 모달이 열린다.
      state.song = name || "";
      writeStateToUrl();
      // 모달을 연 곡을 "최근 본 곡" 에 기록 — 칩으로 빠른 재접근.
      if (name) pushRecentViewed(name);
      _lastFocusedEl = document.activeElement;
      // 클릭한 카드에 로딩 상태 표시 — 모달이 뜨기 전 잠깐의 fetch 동안 "반응 없음" 으로
      // 보이지 않도록. aria-busy 로 보조기기에도 알리고, .is-loading 으로 펄스 시각화.
      if (triggerCard) {
        triggerCard.classList.add("is-loading");
        triggerCard.setAttribute("aria-busy", "true");
      }
      modal.classList.add("is-open");
      document.body.style.overflow = "hidden";
      modalTitle.textContent = "—";
      modalSub.textContent = t("catalog.modalAnalysing");
      modalTags.innerHTML = "";
      // 이전 모달의 시드 메트릭 / 즐겨찾기 잔재 비우기.
      var smHost = document.getElementById("modal-seed-metrics");
      if (smHost) smHost.innerHTML = "";
      var favSeedBtn = document.getElementById("modal-fav-seed");
      if (favSeedBtn) { favSeedBtn.setAttribute("aria-pressed", "false"); favSeedBtn.onclick = null; }
      modalBody.innerHTML = '<p class="modal-loading">' + escapeHtml(t("catalog.modalLoading")) + '</p>';
      // 닫기 버튼 같은 첫 조작 가능 요소로 포커스 이동 — 키보드 사용자 / 스크린리더 사용자한테 필수.
      // microtask 한 박자 늦춰서 display:none → flex 전환 직후의 layout flush 를 기다린다.
      setTimeout(function () {
        var nodes = focusableInModal();
        if (nodes.length) nodes[0].focus();
      }, 0);
      try {
        var url = "/api/analyze/by-catalog?top_n=5&name=" + encodeURIComponent(name);
        var res = await fetch(url);
        if (!res.ok) throw new Error("HTTP " + res.status);
        var data = await res.json();
        modalTitle.textContent = data.title;
        modalSub.textContent = t("catalog.modalSub", data.artist, data.catalog_size);
        // 시드 곡의 BPM / E / Hz mini-row — by-catalog 응답의 summary 활용.
        renderSeedMetrics(data.summary);
        // 시드 곡의 즐겨찾기 상태 동기화.
        setupSeedFavButton(name, data.title || "", data.artist || "");
        modalTags.innerHTML = (data.tags || []).map(function (tg) {
          return '<span class="modal-tag">' + escapeHtml(tg) + '</span>';
        }).join("");
        if (!data.results || !data.results.length) {
          modalBody.innerHTML = '<p class="modal-loading">' + escapeHtml(t("catalog.modalNone")) + '</p>';
          return;
        }
        var seedTitle = t("catalog.modalSeed");
        modalBody.innerHTML = '<ol class="modal-hits">' + data.results.map(function (r) {
          var fullName = r.title + " - " + r.artist;
          var isFav = Fav ? Fav.has(fullName) : false;
          // 매칭 곡의 핵심 메트릭을 작은 라인으로 함께 — 카탈로그 카드와
          // 동일한 패턴. match_summary 가 없으면 라인 자체 안 그림.
          var matchMetrics = buildMetricsLine(r.match_summary ? {
            bpm: r.match_summary.tempo_bpm,
            energy_rms: r.match_summary.energy_rms,
            brightness: r.match_summary.brightness,
          } : null);
          return '<li>'
            + '<span class="modal-rank">' + r.rank + '</span>'
            + '<span><span class="modal-name">' + escapeHtml(r.title) + '</span>'
            + ' · <span class="modal-artist">' + escapeHtml(r.artist) + '</span>'
            + matchMetrics
            + '</span>'
            + '<span class="modal-actions">'
            + '<button type="button" class="modal-fav" data-fav-name="' + escapeHtml(fullName)
            + '" data-fav-title="' + escapeHtml(r.title) + '" data-fav-artist="' + escapeHtml(r.artist)
            + '" data-active="' + (isFav ? 'true' : 'false')
            + '" aria-pressed="' + (isFav ? 'true' : 'false') + '" title="★">★</button>'
            + '<button type="button" class="modal-seed" data-seed="' + escapeHtml(fullName)
            + '" title="' + escapeHtml(seedTitle) + '">→</button>'
            + '</span>'
            + '<span class="modal-percent">' + r.similarity_percent.toFixed(1) + '%</span>'
            + '</li>';
        }).join("") + '</ol>';

        // ★ 토글
        modalBody.querySelectorAll(".modal-fav").forEach(function (btn) {
          btn.addEventListener("click", function (e) {
            e.stopPropagation();
            if (!Fav) return;
            var n = btn.getAttribute("data-fav-name");
            Fav.toggle(n, btn.getAttribute("data-fav-title"), btn.getAttribute("data-fav-artist"));
            var now = Fav.has(n);
            btn.setAttribute("data-active", now ? "true" : "false");
            btn.setAttribute("aria-pressed", now ? "true" : "false");
          });
        });
        // 시드 재탐색 — 그 곡으로 모달 다시 열기 (재귀 호출).
        modalBody.querySelectorAll(".modal-seed").forEach(function (btn) {
          btn.addEventListener("click", function (e) {
            e.stopPropagation();
            openSimilarModal(btn.getAttribute("data-seed"));
          });
        });
      } catch (e) {
        modalBody.innerHTML = '<p class="modal-loading">' + escapeHtml(t("catalog.modalFail")) + '</p>';
      } finally {
        // 성공/실패 무관하게 카드 로딩 상태 해제.
        if (triggerCard) {
          triggerCard.classList.remove("is-loading");
          triggerCard.removeAttribute("aria-busy");
        }
      }
    }

    // 검색 input 의 clear (×) 버튼 — 검색어가 있을 때만 보임.
    var searchClearBtn = document.getElementById("cat-search-clear");

    function syncSearchClearVisibility() {
      if (!searchClearBtn) return;
      searchClearBtn.hidden = !input.value;
    }

    function clearSearch() {
      input.value = "";
      state.q = "";
      state.page = 1;
      syncSearchClearVisibility();
      writeStateToUrl();
      load();
      input.focus();
    }

    if (searchClearBtn) {
      searchClearBtn.addEventListener("click", clearSearch);
    }

    input.addEventListener("input", function () {
      syncSearchClearVisibility();
      // 입력 직후 바로 fetch 하면 한글 IME 입력마다 호출되므로 280ms 디바운스.
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(function () {
        state.q = input.value.trim();
        state.page = 1;
        writeStateToUrl();
        load();
      }, 280);
    });
    // Esc 키 — 검색 input 에 포커스가 있을 때만 검색어 지움.
    input.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && input.value) {
        e.preventDefault();
        clearSearch();
      }
    });
    prev.addEventListener("click", function () {
      if (state.page > 1) {
        state.page--;
        _pendingFocusFirstCard = true;
        writeStateToUrl();
        load();
      }
    });
    next.addEventListener("click", function () {
      if (state.hasMore) {
        state.page++;
        _pendingFocusFirstCard = true;
        writeStateToUrl();
        load();
      }
    });
    if (first) {
      first.addEventListener("click", function () {
        if (state.page > 1) {
          state.page = 1;
          _pendingFocusFirstCard = true;
          writeStateToUrl();
          load();
        }
      });
    }
    if (last) {
      last.addEventListener("click", function () {
        // 마지막 페이지 번호 = ceil(total / size). state.total 은 load() 가 항상 채워준다.
        if (!state.total || !state.size) return;
        var lastPage = Math.max(1, Math.ceil(state.total / state.size));
        if (state.page !== lastPage) {
          state.page = lastPage;
          _pendingFocusFirstCard = true;
          writeStateToUrl();
          load();
        }
      });
    }
    if (favOnly) {
      favOnly.addEventListener("change", function () {
        state.favOnly = favOnly.checked;
        state.page = 1;
        writeStateToUrl();
        load();
      });
    }

    // 즐겨찾기 카운트 노출 — 라벨 옆에 작은 chip 으로 N. 비어 있으면 토글 자체를
    // disabled 처리 (시각적으로 흐리게 + 클릭 불가) 해서 "지금 누를 의미 없다" 시그널.
    function syncFavoritesCount() {
      var countEl = document.getElementById("cat-fav-count");
      var labelEl = document.getElementById("cat-favorites-only-label");
      if (!countEl || !labelEl) return;
      var n = (Fav && typeof Fav.size === "function") ? Fav.size() : 0;
      if (n > 0) {
        countEl.textContent = String(n);
        countEl.hidden = false;
        labelEl.classList.remove("is-empty");
        if (favOnly) favOnly.disabled = false;
      } else {
        countEl.hidden = true;
        labelEl.classList.add("is-empty");
        // 즐겨찾기가 비어 있으면 토글이 의미 없으니 비활성. favOnly state 도 강제 해제.
        if (favOnly) {
          favOnly.disabled = true;
          if (favOnly.checked) {
            favOnly.checked = false;
            state.favOnly = false;
            writeStateToUrl();
            load();
          }
        }
      }
    }
    syncFavoritesCount();
    window.addEventListener("favorites:change", syncFavoritesCount);

    function bindFilterInput(el, stateKey) {
      if (!el) return;
      var t;
      el.addEventListener("input", function () {
        clearTimeout(t);
        t = setTimeout(function () {
          state[stateKey] = el.value;
          state.page = 1;
          writeStateToUrl();
          // BPM 범위가 input 으로 바뀌면 히스토그램 active 상태도 다시 계산.
          if (stateKey === "minBpm" || stateKey === "maxBpm") _syncHistActiveState();
          load();
        }, 280);
      });
    }
    bindFilterInput(minBpmEl, "minBpm");
    bindFilterInput(maxBpmEl, "maxBpm");
    bindFilterInput(minEEl, "minEnergy");
    bindFilterInput(maxEEl, "maxEnergy");
    if (sortEl) {
      sortEl.addEventListener("change", function () {
        state.sort = sortEl.value;
        state.page = 1;
        writeStateToUrl();
        load();
      });
    }
    if (sizeEl) {
      sizeEl.addEventListener("change", function () {
        var n = parseInt(sizeEl.value, 10);
        if (!Number.isFinite(n) || n < 6 || n > 100) return;
        state.size = n;
        // 페이지당 곡 수가 바뀌면 현재 page 가 의미를 잃으므로 1로 리셋.
        state.page = 1;
        writeStateToUrl();
        load();
      });
    }

    // CSV 내보내기 — 현재 적용된 q / 필터 / 정렬을 그대로 백엔드에 넘겨 전체를 한 장의 CSV 로.
    // 즐겨찾기 전용 모드는 localStorage 기반이라 백엔드가 모르므로, 그 모드에서는 클라이언트가
    // 즐겨찾기 목록을 직접 직렬화해 Blob 다운로드한다.
    var exportBtn = document.getElementById("cat-export-csv");
    if (exportBtn) {
      exportBtn.addEventListener("click", function () {
        if (state.favOnly && Fav) {
          // 즐겨찾기 전용 — 클라이언트가 직접 CSV 만들어 내려준다.
          var favs = Fav.list();
          var rows = [["title", "artist", "full_name"]];
          favs.forEach(function (f) {
            // CSV injection 방어: 셀 첫 글자가 = + - @ 면 ' prefix.
            function s(v) {
              var x = v == null ? "" : String(v);
              return x && "=+-@".indexOf(x[0]) !== -1 ? "'" + x : x;
            }
            // CSV 표준 quoting: 콤마/큰따옴표/줄바꿈이 있으면 큰따옴표로 감싸고 내부 " 를 "" 로.
            function q(v) {
              var x = s(v);
              return /[",\n]/.test(x) ? '"' + x.replace(/"/g, '""') + '"' : x;
            }
            rows.push([
              q(f.title),
              q(f.artist),
              q(f.name || ((f.title || "") + " - " + (f.artist || ""))),
            ]);
          });
          var body = "﻿" + rows.map(function (r) { return r.join(","); }).join("\n");
          var blob = new Blob([body], { type: "text/csv;charset=utf-8" });
          var a = document.createElement("a");
          a.href = URL.createObjectURL(blob);
          a.download = "favorites.csv";
          document.body.appendChild(a);
          a.click();
          setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 0);
          return;
        }
        // 일반 모드 — 백엔드 export 엔드포인트로 navigate 하면 브라우저가 다운로드를 트리거.
        var qs = ["q=" + encodeURIComponent(state.q || "")];
        if (state.sort && state.sort !== "default") qs.push("sort=" + encodeURIComponent(state.sort));
        if (state.minBpm !== "") qs.push("min_bpm=" + encodeURIComponent(state.minBpm));
        if (state.maxBpm !== "") qs.push("max_bpm=" + encodeURIComponent(state.maxBpm));
        if (state.minEnergy !== "") qs.push("min_energy=" + encodeURIComponent(state.minEnergy));
        if (state.maxEnergy !== "") qs.push("max_energy=" + encodeURIComponent(state.maxEnergy));
        var url = "/api/catalog/export.csv?" + qs.join("&");
        // window.location 으로 갈아엎으면 페이지가 빈 채로 깜빡이고 뒤로가기도 어색하다.
        // download 속성을 가진 임시 <a> 로 트리거하면 페이지 상태가 보존된다.
        var a = document.createElement("a");
        a.href = url;
        a.download = "catalog.csv";
        document.body.appendChild(a);
        a.click();
        a.remove();
      });
    }

    // 뒤로가기/앞으로가기 시 URL 이 바뀌면 state 를 다시 읽어와 화면을 갱신.
    window.addEventListener("popstate", function () {
      var prevSong = state.song;
      readStateFromUrl();
      applyStateToInputs();
      _syncHistActiveState();
      load();
      // 모달 상태도 URL 에 맞춰 동기화.
      if (state.song && state.song !== prevSong) {
        openSimilarModal(state.song);
      } else if (!state.song && prevSong) {
        modal.classList.remove("is-open");
        document.body.style.overflow = "";
      }
    });
    // 다른 페이지에서 추가/해제 시 카탈로그 페이지도 즉시 갱신.
    window.addEventListener("favorites:change", function () { load(); });

    // BPM 분포 미니 차트는 페이지 진입 시 한 번만 그린다.
    var _histBins = []; // 히스토그램 bin 메타 (from/to) 캐시. 클릭 핸들러에서 사용.

    function _syncHistActiveState() {
      // 현재 state.minBpm/maxBpm 이 어떤 bin 범위와 정확히 일치하면 그 막대를
      // active 로 표시. 일치하지 않으면 모두 inactive.
      var nodes = document.querySelectorAll("#cat-hist-bars .cat-hist-bar");
      nodes.forEach(function (el) {
        var idx = parseInt(el.getAttribute("data-bin"), 10);
        var bin = _histBins[idx];
        if (!bin) return;
        var minMatch = String(Math.round(bin.from)) === String(state.minBpm);
        var maxMatch = String(Math.round(bin.to)) === String(state.maxBpm);
        el.setAttribute("data-active", (minMatch && maxMatch) ? "true" : "false");
      });
    }

    (async function loadHist() {
      var host = document.getElementById("cat-hist");
      var bars = document.getElementById("cat-hist-bars");
      var sub = document.getElementById("cat-hist-sub");
      try {
        var res = await fetch("/api/catalog/stats?bpm_bins=12");
        if (!res.ok) throw new Error("fail");
        var data = await res.json();
        var hist = Array.isArray(data.bpm_histogram) ? data.bpm_histogram : [];
        if (!hist.length) { host.style.display = "none"; return; }
        _histBins = hist;
        var maxCount = Math.max.apply(null, hist.map(function (b) { return b.count; }));
        bars.innerHTML = hist.map(function (b, idx) {
          var h = maxCount > 0 ? Math.max(4, Math.round((b.count / maxCount) * 100)) : 4;
          var tip = b.from.toFixed(0) + "–" + b.to.toFixed(0) + " BPM · " + b.count + "곡 · "
            + t("catalog.histClickHint");
          // <button> 으로 만들어야 키보드 포커스 / Enter 도 같이 동작.
          return '<button type="button" class="cat-hist-bar" data-bin="' + idx
            + '" title="' + escapeHtml(tip) + '"'
            + ' aria-label="' + escapeHtml(tip) + '"'
            + ' style="height: ' + h + '%"></button>';
        }).join("");
        var avg = data.bpm && data.bpm.avg ? data.bpm.avg.toFixed(1) : "?";
        sub.textContent = t("catalog.bpmDistAvg", avg, data.total || 0);

        bars.querySelectorAll(".cat-hist-bar").forEach(function (el) {
          el.addEventListener("click", function () {
            var idx = parseInt(el.getAttribute("data-bin"), 10);
            var bin = _histBins[idx];
            if (!bin) return;
            var minVal = String(Math.round(bin.from));
            var maxVal = String(Math.round(bin.to));
            // 같은 막대를 다시 누르면 토글로 필터 해제.
            if (state.minBpm === minVal && state.maxBpm === maxVal) {
              state.minBpm = "";
              state.maxBpm = "";
            } else {
              state.minBpm = minVal;
              state.maxBpm = maxVal;
            }
            state.page = 1;
            applyStateToInputs();
            writeStateToUrl();
            _syncHistActiveState();
            load();
          });
        });
        _syncHistActiveState();
      } catch (e) {
        host.style.display = "none";
      }
    })();

    // 언어가 바뀌면 동적 텍스트도 다시 그려야 한다 (cat-meta 같은 건 data-i18n 만으로 못 잡음).
    window.addEventListener("i18n:change", function () { load(); });

    // 초기 URL 파라미터로 state 를 채운 뒤 input/select 에도 반영하고 첫 로드.
    readStateFromUrl();
    applyStateToInputs();
    syncSearchClearVisibility();
    load();
    // URL 에 ?song=... 이 있으면 그 곡 기준 모달을 자동으로 띄운다.
    if (state.song) {
      // load() 와 충돌 안 나게 한 타이밍 늦춤. fetch 가 두 번 가는 건 어쩔 수 없는데
      // 둘 다 LRU 캐시에 의해 두 번째부터는 즉시 응답한다.
      setTimeout(function () { openSimilarModal(state.song); }, 0);
    }
  })();
