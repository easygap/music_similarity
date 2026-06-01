(function () {
    var HISTORY_KEY = "soundmatch.history.v1";

    function t(key) {
      try {
        if (window.i18n && typeof window.i18n.t === "function") {
          var args = Array.prototype.slice.call(arguments, 1);
          return window.i18n.t.apply(null, [key].concat(args));
        }
      } catch (e) {}
      return key;
    }

    function read() {
      try {
        var raw = localStorage.getItem(HISTORY_KEY);
        if (!raw) return [];
        var parsed = JSON.parse(raw);
        return Array.isArray(parsed) ? parsed : [];
      } catch (e) { return []; }
    }

    function fmt(v, digits) {
      if (typeof v !== "number" || !isFinite(v)) return "—";
      if (Math.abs(v) >= 100) return v.toFixed(0);
      if (Math.abs(v) >= 1) return v.toFixed(digits || 1);
      return v.toFixed(digits || 3);
    }

    function deltaClass(a, b, lowerBetter) {
      // a 기준으로 b 가 어느 방향인지. lowerBetter 면 b 가 더 작으면 좋은 거.
      if (typeof a !== "number" || typeof b !== "number") return "delta-flat";
      if (Math.abs(a - b) < 1e-6) return "delta-flat";
      var bIsBigger = b > a;
      if (lowerBetter) return bIsBigger ? "delta-up" : "delta-down";
      return bIsBigger ? "delta-down" : "delta-up";
    }

    // 메트릭 라벨은 i18n 키를 통해서만 잡고, render 시점에 resolve 한다.
    var METRICS = [
      { key: "tempo_bpm", i18nKey: "compare.metric.tempo", digits: 1 },
      { key: "energy_rms", i18nKey: "compare.metric.energy", digits: 3 },
      { key: "brightness", i18nKey: "compare.metric.brightness", digits: 0 },
      { key: "noisiness", i18nKey: "compare.metric.noisiness", digits: 3 },
      { key: "harmony_ratio", i18nKey: "compare.metric.harmony", digits: 2 },
      { key: "chroma", i18nKey: "compare.metric.chroma", digits: 3 },
    ];

    function escapeHtml(s) {
      return String(s == null ? "" : s)
        .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;").replace(/'/g, "&#039;");
    }

    function renderCard(entry, other) {
      var data = entry.data || {};
      var summary = data.summary || {};
      var otherSummary = (other && other.data && other.data.summary) || {};
      var tags = Array.isArray(data.tags) ? data.tags : [];
      var top = data.results && data.results[0];

      var metricsHtml = METRICS.map(function (m) {
        var a = summary[m.key];
        var b = otherSummary[m.key];
        var cls = deltaClass(b, a, false);
        return [
          '<div class="compare-metric">',
          '<span class="compare-metric-key">' + escapeHtml(t(m.i18nKey)) + '</span>',
          '<span class="compare-metric-val ' + cls + '">' + fmt(a, m.digits) + '</span>',
          '</div>',
        ].join("");
      }).join("");

      var tagsHtml = tags.map(function (tg) {
        return '<span class="compare-tag">' + escapeHtml(tg) + '</span>';
      }).join("");

      var topHtml = "";
      if (top) {
        topHtml = [
          '<div class="compare-top">',
          '<div class="compare-top-label">' + escapeHtml(t("compare.topMatch")) + '</div>',
          '<p class="compare-top-title">' + escapeHtml(top.title || "—") + ' · <span style="color:var(--text-mute)">' + escapeHtml(top.artist || "") + '</span></p>',
          '<span class="compare-top-percent">' + fmt(top.similarity_percent, 1) + '% ' + escapeHtml(t("compare.topSuffix")) + '</span>',
          '</div>',
        ].join("");
      }

      return [
        '<div class="compare-card">',
        '<h2 class="compare-filename">' + escapeHtml(data.filename || "—") + '</h2>',
        tagsHtml ? '<div class="compare-tags">' + tagsHtml + '</div>' : "",
        metricsHtml,
        topHtml,
        '</div>',
      ].join("");
    }

    function init() {
      var items = read();
      var grid = document.getElementById("compare-grid");
      var pickerRow = document.querySelector(".picker-row");
      var selA = document.getElementById("select-a");
      var selB = document.getElementById("select-b");
      var swapBtn = document.getElementById("compare-swap");
      var sameWarn = document.getElementById("compare-same-warn");

      if (items.length < 2) {
        pickerRow.style.display = "none";
        return;
      }

      function buildOptions(target, defaultIdx) {
        var locale = (window.i18n && window.i18n.lang && window.i18n.lang() === "en") ? "en-US" : "ko-KR";
        target.innerHTML = items.map(function (it, idx) {
          var when = new Date(it.ts);
          var label = when.toLocaleString(locale, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
          var name = it.filename || ("Analysis " + (idx + 1));
          return '<option value="' + idx + '"' + (idx === defaultIdx ? ' selected' : '') + '>'
            + escapeHtml(name) + ' · ' + escapeHtml(label) + '</option>';
        }).join("");
      }

      buildOptions(selA, 0);
      buildOptions(selB, 1);

      function rerender() {
        var a = items[parseInt(selA.value, 10)];
        var b = items[parseInt(selB.value, 10)];
        // 같은 곡을 양쪽에 고르면 안내만 띄우고 렌더 자체는 막지 않는다.
        // 서로 다르면 hidden=true(숨김), 같으면 hidden=false(노출).
        if (sameWarn) sameWarn.hidden = selA.value !== selB.value;
        if (!a || !b) {
          grid.innerHTML = '<p class="compare-empty">' + escapeHtml(t("compare.invalid")) + '</p>';
          return;
        }
        grid.innerHTML = renderCard(a, b) + renderCard(b, a);
      }

      selA.addEventListener("change", rerender);
      selB.addEventListener("change", rerender);

      // A ↔ B 스왑 — 두 셀렉트 값을 맞바꿔 다시 그린다. 클릭마다 아이콘을 180°씩
      // 더 돌려 "맞바꿨다"는 시각 피드백을 준다.
      if (swapBtn) {
        var swapRot = 0;
        swapBtn.addEventListener("click", function () {
          var av = selA.value;
          selA.value = selB.value;
          selB.value = av;
          swapRot += 180;
          var icon = swapBtn.querySelector("svg");
          if (icon) icon.style.transform = "rotate(" + swapRot + "deg)";
          rerender();
        });
      }

      // 언어가 바뀌면 옵션 라벨(날짜) 과 카드 메트릭 라벨이 같이 바뀌어야 한다.
      window.addEventListener("i18n:change", function () {
        var prevA = selA.value;
        var prevB = selB.value;
        buildOptions(selA, parseInt(prevA, 10) || 0);
        buildOptions(selB, parseInt(prevB, 10) || 1);
        rerender();
      });
      rerender();
    }

    if (document.readyState !== "loading") init();
    else document.addEventListener("DOMContentLoaded", init);
  })();
