// Service Worker 등록 — CSP 'unsafe-inline' 제거 차원에서 외부 파일로 분리.
// 메인 페이지에서만 로드된다.
if ("serviceWorker" in navigator) {
  window.addEventListener("load", function () {
    var refreshing = false;
    var hadController = !!navigator.serviceWorker.controller;

    // 새 SW 가 skipWaiting() 으로 활성화되면, 한 번만 새로고침해서 오래된
    // HTML/JS 셸 캐시가 화면에 남는 시간을 줄인다. controller 가 없던 첫 설치는
    // 새로고침하지 않는다.
    navigator.serviceWorker.addEventListener("controllerchange", function () {
      if (!hadController) {
        hadController = true;
        return;
      }
      if (refreshing) return;
      refreshing = true;
      window.location.reload();
    });

    navigator.serviceWorker.register("/sw.js").then(function (registration) {
      // 브라우저가 자동 업데이트 체크를 미루는 경우가 있어 메인 진입 때 가볍게 확인.
      if (registration && typeof registration.update === "function") {
        registration.update().catch(function () {});
      }
    }).catch(function (err) {
      console.warn("SW 등록 실패:", err);
    });
  });
}
