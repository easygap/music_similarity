"""디자인 전용 로컬 프리뷰 서버.

librosa/sklearn 같은 무거운 의존성을 깔지 않고도 ``frontend/`` 정적 파일을
띄워볼 수 있게 한다. 메인 / 카탈로그 / 비교 페이지가 쓰는 API 를 모두 더미
응답으로 흉내내서 결과 화면까지 전부 그려볼 수 있다. 프로덕션 용도가 아니다.
"""
from __future__ import annotations

import json
import random
import sys
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent
FRONTEND = ROOT / "frontend"


SAMPLE_RESULTS = {
    "filename": "preview_sample.wav",
    "summary": {
        "tempo_bpm": 128.0,
        "energy_rms": 0.31,
        "brightness": 3120.5,
        "noisiness": 0.115,
        "harmony_ratio": 0.92,
        "chroma": 0.412,
    },
    "results": [
        {
            "rank": 1,
            "title": "Invincible",
            "artist": "DEAF KEV",
            "similarity": 0.94,
            "similarity_percent": 94.1,
            "youtube_search_url": "https://www.youtube.com/results?search_query=Invincible+DEAF+KEV",
            "spotify_search_url": "https://open.spotify.com/search/Invincible%20DEAF%20KEV",
            "match_summary": {
                "tempo_bpm": 130.5, "energy_rms": 0.30, "brightness": 3150.1,
                "noisiness": 0.118, "harmony_ratio": 0.88, "chroma": 0.40,
            },
            "reason": {
                "summary": "두 곡은 **템포 & 리듬** 측면이 특히 닮았고, 전반적인 청각적 인상이 비슷합니다.",
                "groups": [
                    {
                        "label": "템포 & 리듬",
                        "match_score": 0.96,
                        "summary": "템포 & 리듬 측면에서 거의 같은 특성을 보입니다.",
                        "detail": [
                            "템포: 업로드한 곡 128.00BPM · 매칭된 곡 130.50BPM (비슷한 값)",
                            "평균 음량(에너지)가 거의 동일합니다 (0.31).",
                        ],
                    },
                    {
                        "label": "음색 (밝기)",
                        "match_score": 0.88,
                        "summary": "음색 (밝기) 측면에서 매우 닮은 특성을 보입니다.",
                        "detail": [
                            "음색의 밝기: 업로드한 곡 3120.50Hz · 매칭된 곡 3150.10Hz (비슷한 값)",
                        ],
                    },
                    {
                        "label": "음정 분포 (크로마)",
                        "match_score": 0.81,
                        "summary": "음정 분포 (크로마) 측면에서 매우 닮은 특성을 보입니다.",
                        "detail": [
                            "음정 색채(크로마): 업로드한 곡 0.41 · 매칭된 곡 0.40 (비슷한 값)",
                        ],
                    },
                ],
            },
        },
        {
            "rank": 2,
            "title": "Heroes Tonight",
            "artist": "Janji",
            "similarity": 0.88,
            "similarity_percent": 88.4,
            "youtube_search_url": "https://www.youtube.com/results?search_query=Heroes+Tonight+Janji",
            "spotify_search_url": "https://open.spotify.com/search/Heroes%20Tonight%20Janji",
            "match_summary": {
                "tempo_bpm": 132.0, "energy_rms": 0.34, "brightness": 3080.2,
                "noisiness": 0.122, "harmony_ratio": 0.95, "chroma": 0.42,
            },
            "reason": {
                "summary": "두 곡은 **음색 (밝기)** 측면이 특히 닮았고, 전반적인 청각적 인상이 비슷합니다.",
                "groups": [
                    {
                        "label": "음색 (밝기)",
                        "match_score": 0.92,
                        "summary": "음색 (밝기) 측면에서 거의 같은 특성을 보입니다.",
                        "detail": [
                            "음색의 밝기: 업로드한 곡 3120.50Hz · 매칭된 곡 3080.20Hz (비슷한 값)",
                        ],
                    },
                    {
                        "label": "템포 & 리듬",
                        "match_score": 0.84,
                        "summary": "템포 & 리듬 측면에서 매우 닮은 특성을 보입니다.",
                        "detail": [
                            "템포: 업로드한 곡 128.00BPM · 매칭된 곡 132.00BPM (비슷한 값)",
                        ],
                    },
                ],
            },
        },
        {
            "rank": 3,
            "title": "Make Me Move",
            "artist": "Culture Code",
            "similarity": 0.81,
            "similarity_percent": 81.2,
            "youtube_search_url": "https://www.youtube.com/results?search_query=Make+Me+Move+Culture+Code",
            "spotify_search_url": "https://open.spotify.com/search/Make%20Me%20Move%20Culture%20Code",
            "match_summary": {
                "tempo_bpm": 95.7, "energy_rms": 0.24, "brightness": 2780.0,
                "noisiness": 0.118, "harmony_ratio": 0.58, "chroma": 0.34,
            },
            "reason": {
                "summary": "두 곡은 **거친 질감 & 노이즈** 측면이 특히 닮았고, 전반적인 청각적 인상이 비슷합니다.",
                "groups": [
                    {
                        "label": "거친 질감 & 노이즈",
                        "match_score": 0.86,
                        "summary": "거친 질감 & 노이즈 측면에서 매우 닮은 특성을 보입니다.",
                        "detail": [
                            "거친 정도(노이즈성)이 거의 동일합니다 (0.12).",
                        ],
                    },
                    {
                        "label": "화성 vs 타악기 균형",
                        "match_score": 0.75,
                        "summary": "화성 vs 타악기 균형 측면에서 닮은 특성을 보입니다.",
                        "detail": [
                            "화성 성분이 거의 동일합니다 (0.00).",
                        ],
                    },
                ],
            },
        },
    ],
    "timing": {"feature_extraction_seconds": 1.42, "similarity_seconds": 0.012},
    "catalog_size": 1006,
}


# 카탈로그 페이지 / 샘플 버튼이 쓰는 더미 곡 목록. 실제 dataset.csv 가 없어도
# 검색 / 필터 / 페이지네이션 UI 를 전부 그려볼 수 있도록 30곡 정도 합성.
_PREVIEW_ARTISTS = ["DEAF KEV", "Janji", "Culture Code", "Valcos", "Convex",
                    "Diamond Eyes", "Cadmium", "Paul Flint", "Tobu", "Elektronomia"]
PREVIEW_CATALOG = []
for _i in range(30):
    _artist = _PREVIEW_ARTISTS[_i % len(_PREVIEW_ARTISTS)]
    PREVIEW_CATALOG.append({
        "title": f"Preview Track {_i + 1:02d}",
        "artist": _artist,
        "metrics": {
            "bpm": round(90 + (_i * 7) % 80 + 0.5, 1),
            "energy_rms": round(0.18 + (_i % 10) * 0.03, 3),
            "brightness": round(2200 + (_i * 53) % 1800, 0),
        },
    })

# /api/version/changelog 더미 — "새 기능" 모달이 그려질 수 있게.
SAMPLE_CHANGELOG = {
    "releases": [
        {
            "version": "1.7.0",
            "date": "2026-05-22",
            "sections": {
                "Added": ["분석 결과 신뢰도 안내 배너", "noscript 폴백"],
                "Changed": ["결과 내보내기 메뉴 드롭다운화", "hit 카드 펼침 트랜지션"],
                "Fixed": ["모바일 네비게이션 햄버거 메뉴"],
            },
        },
        {
            "version": "1.6.0",
            "date": "2026-05-21",
            "sections": {
                "Added": ["/api/version 에 git_commit / dependencies"],
                "Changed": ["OS 테마 실시간 동기"],
            },
        },
    ],
}


class PreviewHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(FRONTEND), **kwargs)

    # Same convenience aliases the FastAPI app exposes.
    PATH_ALIASES = {
        "/style.css": "/css/style.css",
        "/app.js": "/js/app.js",
        "/i18n.js": "/js/i18n.js",
        "/visualizers.js": "/js/visualizers.js",
        "/favicon.svg": "/assets/favicon.svg",
    }

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/":
            self.path = "/index.html"
        elif path in self.PATH_ALIASES:
            self.path = self.PATH_ALIASES[path]
        elif path == "/api/catalog":
            return self._send_json({"catalog_size": 1006, "feature_count": 57, "features": []})
        elif path == "/api/health":
            return self._send_json({
                "status": "ok", "catalog_size": 1006, "env": "preview",
                "version": "1.7.0", "release_date": "2026-05-22", "git_commit": "preview",
                "uptime_seconds": 12.3, "analyze_latency_p50_seconds": 1.4,
                "catalog_updated_at": "2026-05-22T00:00:00+00:00",
            })
        elif path == "/api/version":
            return self._send_json({
                "name": "soundmatch", "version": "1.7.0", "release_date": "2026-05-22",
                "git_commit": "preview", "env": "preview", "catalog_size": 1006,
                "analyses_total": 1234,
                "features": {"spectrogram": True, "by_catalog": True, "metrics": True},
                "max_upload_bytes": 26214400, "rate_limit_per_min": 12,
                "dependencies": {"python": "3.11.x", "numpy": "preview", "scikit-learn": "preview"},
            })
        elif path == "/api/version/changelog":
            return self._send_json(SAMPLE_CHANGELOG)
        elif path == "/api/catalog/search":
            return self._catalog_search(parse_qs(parsed.query))
        elif path == "/api/catalog/random":
            qs = parse_qs(parsed.query)
            n = min(int((qs.get("n", ["6"])[0]) or 6), len(PREVIEW_CATALOG))
            picks = random.sample(PREVIEW_CATALOG, k=n)
            return self._send_json({
                "total": len(PREVIEW_CATALOG),
                "items": [{"title": p["title"], "artist": p["artist"]} for p in picks],
            })
        elif path == "/api/catalog/stats":
            bpms = [p["metrics"]["bpm"] for p in PREVIEW_CATALOG]
            return self._send_json({
                "catalog_size": len(PREVIEW_CATALOG),
                "bpm": {"min": min(bpms), "max": max(bpms), "avg": round(sum(bpms) / len(bpms), 1)},
                "histogram": [{"from": 80 + i * 20, "to": 100 + i * 20, "count": 5 - abs(2 - i)}
                              for i in range(5)],
            })
        elif path == "/api/catalog/export.csv":
            return self._catalog_export_csv()
        elif path == "/api/analyze/by-catalog":
            # 메인 페이지 '샘플로 분석해보기' / 카탈로그 모달이 호출.
            qs = parse_qs(parsed.query)
            name = (qs.get("name", ["Preview Track 01 - DEAF KEV"])[0])
            title, _, artist = name.partition(" - ")
            payload = dict(SAMPLE_RESULTS)
            payload["title"] = title or "Preview Track"
            payload["artist"] = artist or "Preview Artist"
            payload["tags"] = ["빠른 템포", "에너지 폭발"]
            return self._send_json(payload)
        return super().do_GET()

    def _catalog_search(self, qs):
        """카탈로그 검색/페이지네이션 더미 — q 부분일치 + page/size 만 흉내낸다."""
        needle = (qs.get("q", [""])[0] or "").strip().lower()
        page = max(int((qs.get("page", ["1"])[0]) or 1), 1)
        size = min(max(int((qs.get("size", ["24"])[0]) or 24), 1), 100)
        items = PREVIEW_CATALOG
        if needle:
            items = [p for p in items
                     if needle in p["title"].lower() or needle in p["artist"].lower()]
        total = len(items)
        start = (page - 1) * size
        page_items = items[start:start + size]
        return self._send_json({
            "total": total, "page": page, "size": size,
            "has_more": start + size < total, "items": page_items,
        })

    def _catalog_export_csv(self):
        """카탈로그 CSV 내보내기 더미."""
        lines = ["title,artist,bpm,energy_rms,brightness,full_name"]
        for p in PREVIEW_CATALOG:
            m = p["metrics"]
            lines.append(
                f'{p["title"]},{p["artist"]},{m["bpm"]},{m["energy_rms"]},'
                f'{m["brightness"]},{p["title"]} - {p["artist"]}'
            )
        body = ("﻿" + "\n".join(lines)).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/csv; charset=utf-8")
        self.send_header("Content-Disposition", 'attachment; filename="catalog.csv"')
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/analyze":
            # Drain the upload (we don't actually decode it in preview mode).
            length = int(self.headers.get("Content-Length", 0))
            if length:
                self.rfile.read(length)
            return self._send_json(SAMPLE_RESULTS)
        self.send_error(404)

    def _send_json(self, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    print(f"Preview server listening on http://127.0.0.1:{port}", flush=True)
    HTTPServer(("127.0.0.1", port), PreviewHandler).serve_forever()


if __name__ == "__main__":
    main()
