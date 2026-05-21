// 페이지가 처음 페인트되기 전에 저장된 테마(다크/라이트) 를 즉시 적용한다.
// CSS 가 먼저 적용된 뒤 JS 가 토글하면 색이 한 번 깜빡(FOUC) 이는데, 이를
// 막기 위해 <head> 최상단 외부 스크립트로 로드. CSP unsafe-inline 제거의
// 일환으로 인라인이 아닌 별도 파일로 분리한다.
//
// 외부 스크립트도 동기 로드(<script src=...>) 라면 인라인과 동일하게 파서를
// 막아 paint 전에 실행된다. defer / async 는 일부러 안 붙임.

(function () {
  try {
    var stored = localStorage.getItem("soundmatch.theme");
    var theme = stored
      || (window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark");
    document.documentElement.setAttribute("data-theme", theme);

    // 사용자가 명시적으로 테마를 토글한 적 없으면 (= localStorage 비어있음) OS 테마 변경을
    // 실시간으로 따라간다. 한 번이라도 토글하면 명시 선택을 우선하므로 listener 효과 없음.
    // matchMedia 의 change 이벤트는 모던 브라우저 전부 지원, IE 만 미지원이라 무시.
    if (!stored && window.matchMedia) {
      var mq = window.matchMedia("(prefers-color-scheme: light)");
      var handler = function (e) {
        // 그 사이에 사용자가 토글했으면 OS 변경을 무시 — localStorage 에 값이 박혀있을 것.
        var saved = null;
        try { saved = localStorage.getItem("soundmatch.theme"); } catch (err) {}
        if (saved) return;
        document.documentElement.setAttribute("data-theme", e.matches ? "light" : "dark");
        // 다른 곳에서 테마 변경 이벤트를 듣고 있는 코드 (예: 파형 다시 그리기) 가 있을 수 있으니 알려준다.
        try { window.dispatchEvent(new CustomEvent("theme:change", { detail: { theme: e.matches ? "light" : "dark", source: "system" } })); } catch (err) {}
      };
      // 모던 브라우저 표준 — addEventListener. 구형 Safari 는 addListener 였는데 폴백 두지 않음.
      if (typeof mq.addEventListener === "function") {
        mq.addEventListener("change", handler);
      } else if (typeof mq.addListener === "function") {
        mq.addListener(handler);
      }
    }
  } catch (e) {
    // localStorage 가 막혀 있어도 무시. 기본 다크 테마 그대로.
  }
})();
