// 서브페이지(카탈로그 / 비교 / 약관 등) 공용 네비게이션 배선.
//
// 메인(index.html)은 app.js 가 같은 일을 하지만 app.js 는 분석 페이지 전용
// 무거운 번들이라 서브페이지에 싣지 않는다. 대신 네비의 테마/언어 토글과
// 모바일 햄버거에 필요한 최소 로직만 여기 모아 서브페이지에서 로드한다.
// (app.js 의 해당 블록과 동작은 동일하되, 파형 재그리기 같은 분석 페이지
//  전용 부수효과는 없다. 마크업은 각 페이지에 인라인으로 두어 첫 페인트에
//  네비가 깜빡이지 않게 한다.)
(function () {
  "use strict";

  var THEME_KEY = "soundmatch.theme";
  var $ = function (sel) { return document.querySelector(sel); };
  var t = function (k) {
    return (window.i18n && typeof window.i18n.t === "function") ? window.i18n.t(k) : k;
  };

  // 테마 토글 -----------------------------------------------------------
  // theme-init.js 가 이미 초기 테마를 적용해 둔다. 여기서는 클릭 시 다크/라이트를
  // 뒤집고 localStorage 에 저장한 뒤, 테마 변경에 반응하는 코드가 있으면 알린다.
  var themeToggleBtn = $("#theme-toggle");
  if (themeToggleBtn) {
    themeToggleBtn.addEventListener("click", function () {
      var cur = document.documentElement.getAttribute("data-theme") || "dark";
      var next = cur === "dark" ? "light" : "dark";
      document.documentElement.setAttribute("data-theme", next);
      try { localStorage.setItem(THEME_KEY, next); } catch (e) {}
      try {
        window.dispatchEvent(new CustomEvent("theme:change", {
          detail: { theme: next, source: "toggle" },
        }));
      } catch (e) {}
    });
  }

  // 언어 토글 -----------------------------------------------------------
  var langToggleBtn = $("#lang-toggle");
  if (langToggleBtn) {
    langToggleBtn.addEventListener("click", function () {
      if (window.i18n) window.i18n.toggle();
    });
  }
  // 언어가 바뀌면 토글 버튼 라벨을 갱신 (i18n.apply 가 data-i18n 텍스트는 갱신하지만
  // 토글 라벨은 "현재 언어의 반대" 를 가리켜야 해서 따로 맞춰준다).
  window.addEventListener("i18n:change", function () {
    if (langToggleBtn) langToggleBtn.textContent = t("controls.langToggle");
  });

  // 푸터 연도 -----------------------------------------------------------
  var yearSpan = $("#year");
  if (yearSpan) yearSpan.textContent = String(new Date().getFullYear());

  // 모바일 햄버거 메뉴 ---------------------------------------------------
  // <600px 에서 nav 링크가 드롭다운으로 접히고 햄버거로 토글한다.
  // 데스크톱에서는 CSS 가 .nav-menu-toggle 을 숨겨 이 핸들러가 사실상 비활성.
  var navMenuToggle = $("#nav-menu-toggle");
  var navLinksGroup = $("#nav-links-group");
  if (navMenuToggle && navLinksGroup) {
    var setNavOpen = function (open) {
      navLinksGroup.classList.toggle("is-open", open);
      navMenuToggle.setAttribute("aria-expanded", open ? "true" : "false");
      navMenuToggle.setAttribute("aria-label", t(open ? "nav.menuClose" : "nav.menuToggle"));
    };
    navMenuToggle.addEventListener("click", function (e) {
      e.stopPropagation();
      setNavOpen(!navLinksGroup.classList.contains("is-open"));
    });
    navLinksGroup.querySelectorAll("a").forEach(function (a) {
      a.addEventListener("click", function () { setNavOpen(false); });
    });
    document.addEventListener("click", function (e) {
      if (!navLinksGroup.classList.contains("is-open")) return;
      if (navLinksGroup.contains(e.target) || navMenuToggle.contains(e.target)) return;
      setNavOpen(false);
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && navLinksGroup.classList.contains("is-open")) {
        setNavOpen(false);
        navMenuToggle.focus();
      }
    });
  }
})();
