// 메인 화면 전용 — 소리 지도, 실제 결과 예시, 원리 섹션의 미니 차트, 스크롤 진행선.
//
// 데이터는 scripts/build_landing_data.py 가 만든 landing-data.js 의
// window.SoundMatchLanding 하나. 카탈로그 781곡의 PCA 좌표와, 서버 엔진이 실제로
// 계산한 예시 3쌍이 들어 있다. 여기서는 그리기만 한다. 외부 라이브러리 없음.
//
// 성능 원칙:
//   - 캔버스는 화면에 보일 때만, 그리고 바뀐 게 있을 때만 다시 그린다.
//   - 유휴 회전은 30fps 로 제한하고 prefers-reduced-motion 이면 아예 돌리지 않는다.
//   - 점 781개 hit-test 는 단순 순회. 이 규모에선 공간 인덱스가 오히려 손해다.

(function () {
  "use strict";

  var data = window.SoundMatchLanding;
  var app = window.SoundMatchApp || {};
  var reduceMotion = false;
  try {
    reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  } catch (e) { /* matchMedia 없음 */ }

  function t(key) {
    try {
      if (window.i18n && typeof window.i18n.t === "function") {
        var args = Array.prototype.slice.call(arguments, 1);
        return window.i18n.t.apply(null, [key].concat(args));
      }
    } catch (e) { /* i18n 미로드 */ }
    return key;
  }
  function isEn() {
    return Boolean(window.i18n && window.i18n.lang && window.i18n.lang() === "en");
  }
  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#039;");
  }
  function clamp(v, a, b) { return Math.max(a, Math.min(b, v)); }
  function splitName(full) {
    var i = full.indexOf(" - ");
    if (i === -1) return { title: full, artist: "" };
    return { title: full.slice(0, i).trim(), artist: full.slice(i + 3).trim() };
  }
  function localizeTag(tag) {
    return app.localizeResultTag ? app.localizeResultTag(tag) : tag;
  }
  function localizeGroup(label) {
    return app.localizeReasonGroupLabel ? app.localizeReasonGroupLabel(label) : label;
  }
  function seedFrom(title, artist, trigger) {
    if (!app.seedFromHit) return;
    if (trigger) {
      trigger.disabled = true;
      trigger.setAttribute("aria-busy", "true");
    }
    var done = function () {
      if (trigger && trigger.isConnected) {
        trigger.disabled = false;
        trigger.setAttribute("aria-busy", "false");
      }
    };
    try {
      var p = app.seedFromHit({ title: title, artist: artist });
      if (p && typeof p.finally === "function") p.finally(done);
      else done();
    } catch (e) {
      done();
    }
  }

  // 요약 지표 6축 — visualizers.js 의 레이더와 같은 범위를 쓴다.
  var AXES = [
    { key: "tempo_bpm", labelKey: "results.radarAxisTempo", min: 60, max: 200, unit: " BPM", digits: 0 },
    { key: "energy_rms", labelKey: "results.radarAxisEnergy", min: 0, max: 0.5, unit: "", digits: 3 },
    { key: "brightness", labelKey: "results.radarAxisBrightness", min: 800, max: 6000, unit: " Hz", digits: 0 },
    { key: "noisiness", labelKey: "results.radarAxisRoughness", min: 0.02, max: 0.25, unit: "", digits: 3 },
    { key: "harmony_ratio", labelKey: "results.radarAxisHarmony", min: 0, max: 4, unit: "", digits: 2 },
    { key: "chroma", labelKey: "results.radarAxisChroma", min: 0.1, max: 0.6, unit: "", digits: 3 },
  ];
  function norm(v, ax) {
    var x = Number(v);
    if (!isFinite(x) || ax.max === ax.min) return 0;
    return clamp((x - ax.min) / (ax.max - ax.min), 0, 1);
  }
  function fmt(v, digits) {
    var x = Number(v);
    if (!isFinite(x)) return "—";
    return x.toFixed(digits);
  }

  // ----------------------------------------------------------------------
  // 스크롤 진행선
  // ----------------------------------------------------------------------
  var meter = document.getElementById("meter");
  var scrollTicking = false;
  function paintMeter() {
    if (!meter) return;
    var max = document.documentElement.scrollHeight - window.innerHeight;
    var p = max > 0 ? clamp(window.pageYOffset / max, 0, 1) : 0;
    meter.style.transform = "scaleX(" + p.toFixed(4) + ")";
  }

  // ----------------------------------------------------------------------
  // 소리 지도
  // ----------------------------------------------------------------------
  var frame = document.getElementById("map-frame");
  var canvas = document.getElementById("sound-map");
  var labelEl = document.getElementById("map-label");
  var focusEl = document.getElementById("map-focus");
  var subtitleEl = document.getElementById("map-subtitle");
  var varianceEl = document.getElementById("map-variance");
  var map = null;

  function createMap() {
    if (!data || !canvas || !frame || !Array.isArray(data.points) || !data.points.length) return null;
    var ctx = canvas.getContext("2d", { alpha: true });
    if (!ctx) return null;

    var pts = data.points;
    var names = data.names || [];
    var n = pts.length;
    var xs = new Float32Array(n), ys = new Float32Array(n), zs = new Float32Array(n);
    // PCA 좌표는 가운데에 몰려 있는 종 모양 분포다. 그대로 그리면 점 대부분이
    // 중심에 뭉쳐 보이니, 순서는 유지한 채 꼬리를 눌러 화면을 고르게 쓴다.
    var spread = function (v) {
      var a = Math.abs(v);
      return (v < 0 ? -1 : 1) * Math.pow(a, 0.62);
    };
    for (var i = 0; i < n; i++) {
      xs[i] = spread(pts[i][0] / 1000);
      ys[i] = spread(pts[i][1] / 1000);
      zs[i] = spread(pts[i][2] / 1000);
    }
    // 화면 좌표 캐시 — hover hit-test 와 라벨 위치에 쓴다.
    var sx = new Float32Array(n), sy = new Float32Array(n), ss = new Float32Array(n);

    var state = {
      width: 0, height: 0, dpr: 1,
      drift: 0,           // 유휴 회전 누적각
      scrollAngle: 0,     // 스크롤 위치에 따른 회전
      hover: -1,
      seed: -1,
      hits: [],
      hitSet: {},
      sticky: false,      // 결과 화면이 켠 하이라이트인지 (원리 섹션이 덮어쓰지 않게)
      reveal: reduceMotion ? 1 : 0,
      visible: true,
      dirty: true,
      lastTs: 0,
      lastDraw: 0,
      colors: null,
      raf: 0,
    };

    function readColors() {
      var cs = getComputedStyle(frame);
      var pick = function (name, fallback) {
        var v = cs.getPropertyValue(name).trim();
        return v || fallback;
      };
      state.colors = {
        other: pick("--series-other", "rgba(18,17,16,0.26)"),
        query: pick("--series-query", "#121110"),
        match: pick("--series-match", "#e8452b"),
        paper: pick("--paper", "#f3f1ec"),
        rule: pick("--rule", "rgba(18,17,16,0.14)"),
        ink: pick("--ink", "#121110"),
      };
    }

    function resize() {
      var rect = frame.getBoundingClientRect();
      var w = Math.max(1, Math.round(rect.width));
      var h = Math.max(1, Math.round(rect.height));
      var dpr = Math.min(2, window.devicePixelRatio || 1);
      if (w === state.width && h === state.height && dpr === state.dpr) return;
      state.width = w; state.height = h; state.dpr = dpr;
      canvas.width = Math.round(w * dpr);
      canvas.height = Math.round(h * dpr);
      state.dirty = true;
      schedule();
    }

    function project() {
      var angle = state.drift + state.scrollAngle;
      var cosA = Math.cos(angle), sinA = Math.sin(angle);
      var cx = state.width / 2, cy = state.height / 2;
      var R = Math.min(state.width, state.height) * 0.45;
      for (var i = 0; i < n; i++) {
        var xr = xs[i] * cosA - zs[i] * sinA;
        var zr = xs[i] * sinA + zs[i] * cosA;
        var s = 1 / (1 + zr * 0.32);
        sx[i] = cx + xr * R * s;
        sy[i] = cy - ys[i] * R * s;
        ss[i] = s;
      }
    }

    function dot(x, y, r, fill, ring) {
      if (ring) {
        ctx.beginPath();
        ctx.arc(x, y, r + 2, 0, Math.PI * 2);
        ctx.fillStyle = ring;
        ctx.fill();
      }
      ctx.beginPath();
      ctx.arc(x, y, r, 0, Math.PI * 2);
      ctx.fillStyle = fill;
      ctx.fill();
    }

    function draw() {
      if (!state.colors) readColors();
      var c = state.colors;
      var w = state.width, h = state.height, dpr = state.dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, w, h);
      project();

      // 아주 옅은 십자 괘선 — 지도라는 걸 살짝만 알려준다.
      ctx.strokeStyle = c.rule;
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(w / 2, 0); ctx.lineTo(w / 2, h);
      ctx.moveTo(0, h / 2); ctx.lineTo(w, h / 2);
      ctx.stroke();

      var reveal = state.reveal;
      var baseR = Math.max(2, Math.min(w, h) / 190);
      var hasFocus = state.seed >= 0 || state.hits.length > 0;

      // 1) 나머지 카탈로그. 하이라이트가 있으면 한 단계 더 물러난다.
      ctx.fillStyle = c.other;
      var cx = w / 2, cy = h / 2, maxD = Math.hypot(cx, cy);
      for (var i = 0; i < n; i++) {
        if (i === state.seed || state.hitSet[i]) continue;
        var s = ss[i];
        var alpha = 0.55 + 0.45 * clamp((s - 0.72) / 0.6, 0, 1);
        if (reveal < 1) {
          var d = Math.hypot(sx[i] - cx, sy[i] - cy) / maxD;
          alpha *= clamp((reveal * 1.35 - d) / 0.35, 0, 1);
        }
        if (hasFocus) alpha *= 0.55;
        if (alpha <= 0.02) continue;
        ctx.globalAlpha = alpha;
        ctx.beginPath();
        ctx.arc(sx[i], sy[i], baseR * s, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.globalAlpha = 1;

      // 2) 기준 곡 → 닮은 곡 연결선.
      if (state.seed >= 0 && state.hits.length) {
        ctx.strokeStyle = c.match;
        ctx.lineWidth = 1;
        ctx.globalAlpha = 0.75;
        ctx.beginPath();
        for (var k = 0; k < state.hits.length; k++) {
          var hi = state.hits[k];
          ctx.moveTo(sx[state.seed], sy[state.seed]);
          ctx.lineTo(sx[hi], sy[hi]);
        }
        ctx.stroke();
        ctx.globalAlpha = 1;
      }

      // 3) 닮은 곡, 기준 곡, 그리고 hover.
      for (var j = 0; j < state.hits.length; j++) {
        var idx = state.hits[j];
        dot(sx[idx], sy[idx], baseR * ss[idx] + 1.6, c.match, c.paper);
      }
      if (state.seed >= 0) {
        dot(sx[state.seed], sy[state.seed], baseR * ss[state.seed] + 2.4, c.query, c.paper);
      }
      if (state.hover >= 0) {
        var hv = state.hover;
        ctx.beginPath();
        ctx.arc(sx[hv], sy[hv], baseR * ss[hv] + 5, 0, Math.PI * 2);
        ctx.strokeStyle = c.ink;
        ctx.lineWidth = 1;
        ctx.stroke();
      }
      state.dirty = false;
    }

    function tick(ts) {
      state.raf = 0;
      if (!state.visible) return;
      var dt = state.lastTs ? Math.min(64, ts - state.lastTs) : 16;
      state.lastTs = ts;
      var animating = false;
      if (state.reveal < 1) {
        state.reveal = Math.min(1, state.reveal + dt / 1100);
        state.dirty = true;
        animating = true;
      }
      var drifting = !reduceMotion && state.hover < 0 && document.visibilityState === "visible";
      if (drifting) {
        state.drift += dt * 0.00006;
        animating = true;
        // 유휴 회전은 30fps 면 충분하다. 매 프레임 그리면 배터리만 먹는다.
        if (ts - state.lastDraw >= 32) state.dirty = true;
      }
      if (state.dirty) {
        draw();
        state.lastDraw = ts;
      }
      if (animating) schedule();
    }

    function schedule() {
      if (state.raf || !state.visible) return;
      state.raf = window.requestAnimationFrame(tick);
    }

    // hover / click ----------------------------------------------------
    function nearest(px, py, radius) {
      var best = -1, bestD = radius * radius;
      for (var i = 0; i < n; i++) {
        var dx = sx[i] - px, dy = sy[i] - py;
        var d2 = dx * dx + dy * dy;
        if (d2 < bestD) { bestD = d2; best = i; }
      }
      return best;
    }
    function showLabel(i) {
      if (!labelEl) return;
      if (i < 0) {
        labelEl.classList.remove("is-show");
        return;
      }
      var parts = splitName(names[i] || "");
      labelEl.innerHTML = esc(parts.title) + (parts.artist ? "<small>" + esc(parts.artist) + "</small>" : "");
      var x = clamp(sx[i], 70, state.width - 70);
      var y = clamp(sy[i], 44, state.height);
      labelEl.style.left = x + "px";
      labelEl.style.top = y + "px";
      labelEl.classList.add("is-show");
    }
    function setHover(i) {
      if (i === state.hover) return;
      state.hover = i;
      frame.setAttribute("data-hit", i >= 0 ? "true" : "false");
      showLabel(i);
      state.dirty = true;
      schedule();
    }
    canvas.addEventListener("pointermove", function (e) {
      var rect = canvas.getBoundingClientRect();
      setHover(nearest(e.clientX - rect.left, e.clientY - rect.top, 14));
    });
    canvas.addEventListener("pointerleave", function () { setHover(-1); });
    canvas.addEventListener("click", function (e) {
      var rect = canvas.getBoundingClientRect();
      var i = nearest(e.clientX - rect.left, e.clientY - rect.top, 18);
      if (i < 0) return;
      var parts = splitName(names[i] || "");
      if (!parts.title) return;
      seedFrom(parts.title, parts.artist);
    });

    // 스크롤 → 회전. 스크롤 한 화면에 약 20도. 지도가 화면 밖이면 그리지 않는다.
    var lastScrollY = -1;
    function onScroll() {
      var y = window.pageYOffset;
      if (y === lastScrollY) return;
      lastScrollY = y;
      state.scrollAngle = y * 0.00045;
      state.dirty = true;
      schedule();
    }

    var io = null;
    if ("IntersectionObserver" in window) {
      io = new IntersectionObserver(function (entries) {
        state.visible = entries[0].isIntersecting;
        if (state.visible) { state.lastTs = 0; schedule(); }
      }, { threshold: 0.02 });
      io.observe(frame);
    }
    document.addEventListener("visibilitychange", function () {
      if (document.visibilityState === "visible") { state.lastTs = 0; schedule(); }
    });
    window.addEventListener("theme:change", function () { state.colors = null; state.dirty = true; schedule(); });
    // app.js 의 테마 토글은 data-theme 속성만 바꾼다. 속성 변화를 직접 본다.
    if ("MutationObserver" in window) {
      new MutationObserver(function () { state.colors = null; state.dirty = true; schedule(); })
        .observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    }
    if ("ResizeObserver" in window) {
      new ResizeObserver(resize).observe(frame);
    } else {
      window.addEventListener("resize", resize);
    }

    var nameIndex = null;
    function indexOfName(full) {
      if (!nameIndex) {
        nameIndex = {};
        for (var i = 0; i < names.length; i++) nameIndex[names[i]] = i;
      }
      var v = nameIndex[full];
      return typeof v === "number" ? v : -1;
    }

    function highlight(seedIdx, hitIdxs, opts) {
      opts = opts || {};
      state.seed = typeof seedIdx === "number" ? seedIdx : -1;
      state.hits = (hitIdxs || []).filter(function (i) { return typeof i === "number" && i >= 0 && i !== state.seed; });
      state.hitSet = {};
      state.hits.forEach(function (i) { state.hitSet[i] = true; });
      state.sticky = Boolean(opts.sticky);
      if (focusEl) {
        if (state.seed >= 0) {
          var parts = splitName(names[state.seed] || "");
          focusEl.innerHTML = esc(t("map.focusLabel")) + "<strong>" + esc(parts.title) +
            (parts.artist ? " · " + esc(parts.artist) : "") + "</strong>";
        } else if (state.hits.length) {
          focusEl.innerHTML = esc(t("map.focusHits", state.hits.length));
        } else {
          focusEl.textContent = "";
        }
      }
      state.dirty = true;
      schedule();
    }

    resize();
    onScroll();
    schedule();

    return {
      highlight: highlight,
      highlightNames: function (seedName, hitNames, opts) {
        highlight(seedName ? indexOfName(seedName) : -1, (hitNames || []).map(indexOfName), opts);
      },
      clear: function () { highlight(-1, [], { sticky: false }); },
      isSticky: function () { return state.sticky; },
      onScroll: onScroll,
      refreshText: function () { highlight(state.seed, state.hits, { sticky: state.sticky }); },
    };
  }

  function paintMapText() {
    if (!data) return;
    if (subtitleEl) {
      subtitleEl.textContent = t("map.subtitle", data.catalogSize, data.featureCount);
    }
    if (varianceEl && Array.isArray(data.explainedVariance)) {
      var total = data.explainedVariance.reduce(function (a, b) { return a + b; }, 0);
      varianceEl.textContent = t("map.variance", Math.round(total * 100));
    }
  }

  map = createMap();
  if (!map && frame) {
    // 데이터가 없으면 빈 프레임을 보여주는 것보다 숨기는 편이 낫다.
    var visual = frame.closest(".stage-visual");
    if (visual) visual.hidden = true;
  }
  paintMapText();
  window.SoundMatchMap = map;

  // ----------------------------------------------------------------------
  // 결과 화면 ↔ 지도 연결
  // ----------------------------------------------------------------------
  window.addEventListener("soundmatch:results", function (e) {
    if (!map) return;
    var d = (e && e.detail) || {};
    map.highlightNames(d.seed || "", d.hits || [], { sticky: true });
  });
  window.addEventListener("soundmatch:results-cleared", function () {
    if (map) map.clear();
  });

  // ----------------------------------------------------------------------
  // 원리 섹션 — 단계가 화면에 들어오면 지도 상태를 바꾼다.
  // ----------------------------------------------------------------------
  var showcase = (data && Array.isArray(data.showcase)) ? data.showcase : [];
  var storySteps = Array.prototype.slice.call(document.querySelectorAll("[data-story-step]"));
  if (map && showcase.length && storySteps.length && "IntersectionObserver" in window) {
    var stepObserver = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting || map.isSticky()) return;
        var step = entry.target.getAttribute("data-story-step");
        var ex = showcase[0];
        if (step === "1") {
          map.highlight(ex.index, []);
        } else {
          map.highlight(ex.index, ex.hits.map(function (h) { return h.index; }));
        }
      });
    }, { threshold: 0.6 });
    storySteps.forEach(function (el) { stepObserver.observe(el); });
  }

  function renderStoryVisuals() {
    var strip = document.getElementById("story-strip");
    var reasons = document.getElementById("story-reasons");
    if (!showcase.length) {
      if (strip) strip.hidden = true;
      if (reasons) reasons.hidden = true;
      return;
    }
    var ex = showcase[0];
    if (strip) {
      strip.innerHTML = AXES.map(function (ax) {
        var v = ex.summary ? ex.summary[ax.key] : null;
        return "<li>" +
          '<span class="strip-value">' + esc(fmt(v, ax.digits)) + esc(ax.unit) + "</span>" +
          '<span class="strip-track"><span class="strip-fill" style="--v:' + norm(v, ax).toFixed(3) + '"></span></span>' +
          '<span class="strip-name">' + esc(t(ax.labelKey)) + "</span>" +
          "</li>";
      }).join("");
    }
    if (reasons) {
      var top = ex.hits[0];
      var groups = (top && top.reason && top.reason.groups) || [];
      reasons.innerHTML = groups.map(function (g) {
        var v = clamp(Number(g.match_score) || 0, 0, 1);
        return "<li>" +
          '<span class="rb-label">' + esc(localizeGroup(g.label)) + "</span>" +
          '<span class="rb-track"><span class="rb-fill" style="--v:' + v.toFixed(3) + '"></span></span>' +
          '<span class="rb-val">' + Math.round(v * 100) + "%</span>" +
          "</li>";
      }).join("");
    }
  }

  // ----------------------------------------------------------------------
  // 실제 결과 예시
  // ----------------------------------------------------------------------
  var showcaseList = document.getElementById("showcase-list");

  function searchUrl(kind, title, artist) {
    var q = encodeURIComponent((title + " " + artist).trim());
    return kind === "yt"
      ? "https://www.youtube.com/results?search_query=" + q
      : "https://open.spotify.com/search/" + q;
  }

  function renderShowcase() {
    if (!showcaseList) return;
    var section = showcaseList.closest("section");
    if (!showcase.length) {
      if (section) section.hidden = true;
      return;
    }
    showcaseList.innerHTML = showcase.map(function (ex, i) {
      var top = ex.hits[0];
      var rest = ex.hits.slice(1);
      var tags = (ex.tags || []).map(function (tag) {
        return "<span>" + esc(localizeTag(tag)) + "</span>";
      }).join("");
      var topReason = "";
      if (top && top.reason && top.reason.groups && top.reason.groups.length) {
        var g0 = top.reason.groups[0];
        topReason = t("showcase.reason", localizeGroup(g0.label), Math.round((g0.match_score || 0) * 100));
      }
      var fingerprint = AXES.map(function (ax) {
        var q = ex.summary ? ex.summary[ax.key] : null;
        var m = top && top.match_summary ? top.match_summary[ax.key] : null;
        return "<li>" +
          '<span class="fp-label">' + esc(t(ax.labelKey)) + "</span>" +
          '<span class="fp-bars">' +
            '<span class="fp-bar fp-q" style="--v:' + norm(q, ax).toFixed(3) + '"></span>' +
            '<span class="fp-bar fp-m" style="--v:' + norm(m, ax).toFixed(3) + '"></span>' +
          "</span>" +
          '<span class="fp-vals">' + esc(fmt(q, ax.digits)) + esc(ax.unit) + " → " + esc(fmt(m, ax.digits)) + esc(ax.unit) + "</span>" +
          "</li>";
      }).join("");
      var restHtml = rest.map(function (h) {
        return "<li>" +
          '<span class="pr-rank">' + String(h.rank).padStart(2, "0") + "</span>" +
          '<span class="pr-name">' + esc(h.title) + " <span>· " + esc(h.artist) + "</span></span>" +
          '<span class="pr-pct">' + esc(fmt(h.similarity_percent, 1)) + "%</span>" +
          "</li>";
      }).join("");
      return '<li class="pair reveal" data-showcase="' + i + '">' +
        '<div class="pair-seed">' +
          '<p class="pair-kicker">' + esc(t("showcase.seedKicker", i + 1)) + "</p>" +
          '<h3 class="pair-title">' + esc(ex.title) + "</h3>" +
          '<p class="pair-artist">' + esc(ex.artist) + "</p>" +
          (tags ? '<div class="pair-tags">' + tags + "</div>" : "") +
          '<div class="pair-actions">' +
            '<button type="button" class="pill" data-showcase-seed data-title="' + esc(ex.title) + '" data-artist="' + esc(ex.artist) + '">' +
              esc(t("showcase.seedButton")) +
            "</button>" +
            '<a class="text-link" href="' + esc(searchUrl("yt", ex.title, ex.artist)) + '" target="_blank" rel="noopener">YouTube</a>' +
            '<a class="text-link" href="' + esc(searchUrl("sp", ex.title, ex.artist)) + '" target="_blank" rel="noopener">Spotify</a>' +
          "</div>" +
        "</div>" +
        '<div class="pair-matches">' +
          (top ? (
            '<div class="pair-top">' +
              '<p class="pair-top-pct">' + esc(fmt(top.similarity_percent, 1)) + "<small>%</small></p>" +
              '<p class="pair-top-name">' + esc(t("showcase.topLabel")) + " " + esc(top.title) + " <span>· " + esc(top.artist) + "</span></p>" +
              '<p class="pair-top-reason">' + topReason + "</p>" +
            "</div>" +
            '<ul class="fingerprint" aria-label="' + esc(t("showcase.fingerprintAria")) + '">' + fingerprint + "</ul>" +
            '<ul class="fingerprint-legend">' +
              '<li><span class="legend-dot is-query"></span>' + esc(ex.title) + "</li>" +
              '<li><span class="legend-dot is-match"></span>' + esc(top.title) + "</li>" +
            "</ul>"
          ) : "") +
          (restHtml ? '<ol class="pair-rest">' + restHtml + "</ol>" : "") +
        "</div>" +
      "</li>";
    }).join("");
  }

  if (showcaseList) {
    showcaseList.addEventListener("click", function (e) {
      var btn = e.target.closest("[data-showcase-seed]");
      if (!btn || !showcaseList.contains(btn)) return;
      seedFrom(btn.getAttribute("data-title") || "", btn.getAttribute("data-artist") || "", btn);
    });
    // 예시 위에 마우스를 올리면 지도에서 그 쌍을 비춘다 (결과 하이라이트 중에는 건드리지 않음).
    showcaseList.addEventListener("pointerover", function (e) {
      var li = e.target.closest("[data-showcase]");
      if (!li || !map || map.isSticky()) return;
      var ex = showcase[Number(li.getAttribute("data-showcase"))];
      if (ex) map.highlight(ex.index, ex.hits.map(function (h) { return h.index; }));
    });
  }

  renderStoryVisuals();
  renderShowcase();

  window.addEventListener("i18n:change", function () {
    renderStoryVisuals();
    renderShowcase();
    paintMapText();
    if (map) map.refreshText();
  });

  // ----------------------------------------------------------------------
  // 스크롤 배선 — 리스너는 하나만 두고 rAF 로 합친다.
  // ----------------------------------------------------------------------
  function onScroll() {
    if (scrollTicking) return;
    scrollTicking = true;
    window.requestAnimationFrame(function () {
      scrollTicking = false;
      paintMeter();
      if (map) map.onScroll();
    });
  }
  window.addEventListener("scroll", onScroll, { passive: true });
  window.addEventListener("resize", onScroll);
  paintMeter();
})();
