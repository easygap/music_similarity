// Service Worker 등록 — CSP 'unsafe-inline' 제거 차원에서 외부 파일로 분리.
// 메인 페이지에서만 로드된다.
if ("serviceWorker" in navigator) {
  window.addEventListener("load", function () {
    navigator.serviceWorker.register("/sw.js").catch(function (err) {
      console.warn("SW 등록 실패:", err);
    });
  });
}
