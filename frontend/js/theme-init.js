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
  } catch (e) {
    // localStorage 가 막혀 있어도 무시. 기본 다크 테마 그대로.
  }
})();
