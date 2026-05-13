"""디자인 전용 로컬 프리뷰 서버.

librosa/sklearn 같은 무거운 의존성을 깔지 않고도 ``frontend/`` 정적 파일을
띄워볼 수 있게 한다. ``/api/catalog`` 와 ``/api/analyze`` 는 더미 응답을 돌려
줘서 결과 화면까지 전부 그려볼 수 있다. 프로덕션 용도가 아니다.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler
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
        if parsed.path == "/":
            self.path = "/index.html"
        elif parsed.path in self.PATH_ALIASES:
            self.path = self.PATH_ALIASES[parsed.path]
        elif parsed.path == "/api/catalog":
            return self._send_json({"catalog_size": 1006, "feature_count": 57, "features": []})
        elif parsed.path == "/api/health":
            return self._send_json({"status": "ok", "catalog_size": 1006})
        return super().do_GET()

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
