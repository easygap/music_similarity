// SoundMatch service worker -----------------------------------------------
// 목적은 둘:
//   1) 정적 자산(쉘 + 폰트 외)을 캐시해서 두 번째 방문부터 빠른 로딩.
//   2) 네트워크가 끊긴 상황에서 친절한 오프라인 폴백 페이지 노출.
// API 응답(POST/api/analyze 등)은 캐시하지 않는다.

const VERSION = "soundmatch-v1";
const SHELL = [
  "/",
  "/style.css",
  "/app.js",
  "/i18n.js",
  "/visualizers.js",
  "/favicon.svg",
  "/og-image.svg",
  "/offline.html",
  "/manifest.webmanifest",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(VERSION)
      .then((cache) => cache.addAll(SHELL))
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    (async () => {
      // 옛 버전 캐시는 정리.
      const names = await caches.keys();
      await Promise.all(names.filter((n) => n !== VERSION).map((n) => caches.delete(n)));
      await self.clients.claim();
    })(),
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return; // POST /api/analyze 등은 캐시 손대지 않음.

  const url = new URL(req.url);

  // API 요청은 항상 네트워크 우선.
  if (url.pathname.startsWith("/api/")) {
    event.respondWith(
      fetch(req).catch(() =>
        new Response(JSON.stringify({ status: "offline" }), {
          status: 503,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );
    return;
  }

  // 같은 출처의 정적 리소스는 stale-while-revalidate.
  if (url.origin === self.location.origin) {
    event.respondWith(staleWhileRevalidate(req));
    return;
  }

  // 외부 폰트 CDN 등은 그냥 네트워크 우선 → 실패하면 캐시 폴백.
  event.respondWith(
    fetch(req).catch(() => caches.match(req)),
  );
});

async function staleWhileRevalidate(req) {
  const cache = await caches.open(VERSION);
  const cached = await cache.match(req);
  const network = fetch(req)
    .then((res) => {
      // 정상 응답만 캐싱한다.
      if (res && res.status === 200 && res.type === "basic") {
        cache.put(req, res.clone()).catch(() => {});
      }
      return res;
    })
    .catch(async () => {
      // 네트워크 실패 + 캐시도 없으면 오프라인 페이지.
      if (req.mode === "navigate") {
        const fallback = await cache.match("/offline.html");
        if (fallback) return fallback;
      }
      throw new Error("offline");
    });

  return cached || network;
}
