// 실제 카탈로그 비교 결과와 스크롤 위치 표시. 유휴 상태에서는 그리지 않는다.

(function () {
  "use strict";

  var data = window.SoundMatchLanding;
  var app = window.SoundMatchApp || {};

  function t(key) {
    try {
      if (window.i18n && typeof window.i18n.t === "function") {
        var args = Array.prototype.slice.call(arguments, 1);
        return window.i18n.t.apply(null, [key].concat(args));
      }
    } catch (e) { /* i18n 미로드 */ }
    return key;
  }
  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#039;");
  }
  function clamp(v, a, b) { return Math.max(a, Math.min(b, v)); }
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
  // 카탈로그에서 계산한 비교 예시
  var showcase = data && data.showcase || [];
  var showcaseList = document.getElementById("showcase-list");
  var selector = document.getElementById("showcase-selector");
  var selectedExample = 0;

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
    if (selector) selector.innerHTML = showcase.map(function (ex, i) {
      return '<button type="button" data-example="' + i + '" aria-pressed="' + (i === selectedExample) + '"><span class="example-index" aria-hidden="true">0' + (i + 1) + '</span><span><strong>' + esc(ex.title) + '</strong><small>' + esc(ex.artist) + '</small></span><span class="example-mark" aria-hidden="true">↗</span></button>';
    }).join("");
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
      return '<li class="pair" data-showcase="' + i + '"' + (i === selectedExample ? '' : ' hidden') + '>' +
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
  }

  if (selector) selector.addEventListener("click", function (event) {
    var button = event.target.closest("[data-example]");
    if (!button) return;
    selectedExample = Number(button.dataset.example);
    selector.querySelectorAll("[data-example]").forEach(function (item) { item.setAttribute("aria-pressed", String(item === button)); });
    showcaseList.querySelectorAll("[data-showcase]").forEach(function (item, index) { item.hidden = index !== selectedExample; });
  });
  renderShowcase();

  window.addEventListener("i18n:change", function () {
      renderShowcase();
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
    });
  }
  window.addEventListener("scroll", onScroll, { passive: true });
  window.addEventListener("resize", onScroll);
  paintMeter();
})();
