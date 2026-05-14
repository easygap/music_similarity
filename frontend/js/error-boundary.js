// 글로벌 에러 boundary. app.js 가 깨져도 동작해야 해서 별도 파일로 분리.
// (예전엔 index.html 에 인라인으로 깔려 있었지만, CSP 'unsafe-inline' 을
// 제거하면서 외부 파일로 옮긴다.)

(function () {
  function show(msg) {
    try {
      var toast = document.getElementById("toast");
      if (!toast) return;
      toast.textContent = msg;
      toast.classList.remove("hidden");
      toast.classList.add("is-show");
      setTimeout(function () { toast.classList.remove("is-show"); }, 2400);
    } catch (e) {}
  }

  // 같은 에러를 반복적으로 비콘에 쏘지 않도록 1초 디바운스.
  var lastBeaconAt = 0;
  function beacon(body) {
    try {
      var now = Date.now();
      if (now - lastBeaconAt < 1000) return;
      lastBeaconAt = now;
      // navigator.sendBeacon 이 가능하면 페이지 이탈 중에도 안전하게 전송.
      var data = JSON.stringify(body).slice(0, 4000);
      if (navigator.sendBeacon) {
        var blob = new Blob([data], { type: "application/json" });
        navigator.sendBeacon("/api/client-error", blob);
      } else {
        fetch("/api/client-error", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: data,
          keepalive: true,
        }).catch(function () {});
      }
    } catch (e) {}
  }

  window.addEventListener("error", function (e) {
    if (e && e.target && e.target.tagName) return;
    show("문제가 발생했어요. 새로고침 후 다시 시도해주세요.");
    console.error("[soundmatch] error:", (e && e.message) || e);
    beacon({
      kind: "error",
      message: (e && e.message) || "",
      source: (e && e.filename) || "",
      lineno: (e && e.lineno) || null,
      colno: (e && e.colno) || null,
      url: location.pathname,
    });
  });

  window.addEventListener("unhandledrejection", function (e) {
    show("요청 처리 중 문제가 발생했어요. 잠시 후 다시 시도해주세요.");
    console.error("[soundmatch] unhandled:", (e && e.reason) || e);
    beacon({
      kind: "unhandledrejection",
      message: String((e && e.reason && (e.reason.message || e.reason)) || "").slice(0, 500),
      url: location.pathname,
    });
  });
})();
