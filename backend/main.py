"""FastAPI application entry point.

Serves the frontend (static files) and exposes the music similarity API.

Endpoints
---------
GET  /              -> frontend index.html
GET  /api/catalog   -> catalog size and feature column list
POST /api/analyze   -> multipart file upload; returns similarity ranking
GET  /api/health    -> liveness probe
"""
from __future__ import annotations

import os
import shutil
import time
import uuid
from pathlib import Path
from typing import List

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .audio_features import extract_features, summary_metrics
from .reason_engine import explain_match, report_to_dict
from .similarity import MusicSimilarityEngine


# ----------------------------------------------------------------------
# Path setup
# ----------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
DATASET_PATH = ROOT / "data" / "dataset.csv"
FRONTEND_DIR = ROOT / "frontend"
UPLOAD_DIR = ROOT / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {".wav", ".mp3", ".flac", ".ogg", ".m4a"}
MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MB cap

# ----------------------------------------------------------------------
# Engine
# ----------------------------------------------------------------------
engine = MusicSimilarityEngine(DATASET_PATH)

# ----------------------------------------------------------------------
# App
# ----------------------------------------------------------------------
app = FastAPI(
    title="Music Similarity API",
    description="Upload a song and find the most acoustically similar tracks from the catalog.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"status": "ok", "catalog_size": engine.catalog_size}


@app.get("/api/catalog")
def catalog_info():
    return {
        "catalog_size": engine.catalog_size,
        "feature_count": len(engine.feature_columns),
        "features": engine.feature_columns,
    }


@app.post("/api/analyze")
async def analyze(file: UploadFile = File(...), top_n: int = 5):
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"지원하지 않는 파일 형식입니다. ({', '.join(sorted(ALLOWED_EXTENSIONS))})",
        )

    if top_n < 1 or top_n > 20:
        raise HTTPException(status_code=400, detail="top_n must be in [1, 20].")

    # Save upload to disk. We use a per-request uuid so concurrent uploads
    # never collide on the same filename.
    request_id = uuid.uuid4().hex
    dest = UPLOAD_DIR / f"{request_id}{ext}"

    written = 0
    try:
        with dest.open("wb") as out:
            while chunk := await file.read(1024 * 1024):
                written += len(chunk)
                if written > MAX_UPLOAD_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail=f"파일이 너무 큽니다. 최대 {MAX_UPLOAD_BYTES // (1024*1024)}MB.",
                    )
                out.write(chunk)
        if written == 0:
            raise HTTPException(status_code=400, detail="빈 파일입니다.")

        t0 = time.perf_counter()
        try:
            features = extract_features(dest)
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"오디오 분석 중 오류가 발생했습니다: {e}",
            )
        feature_seconds = time.perf_counter() - t0

        t1 = time.perf_counter()
        hits, _q_scaled = engine.find_similar(features, top_n=top_n)
        similarity_seconds = time.perf_counter() - t1

        results: List[dict] = []
        for hit in hits:
            catalog_full_name = f"{hit.name} - {hit.artist}"
            catalog_raw = engine.catalog_row_raw(catalog_full_name) or {}
            report = explain_match(
                query_raw=features.values,
                catalog_raw=catalog_raw,
                distances_scaled=hit.feature_distances,
            )

            results.append(
                {
                    "rank": hit.rank,
                    "title": hit.name,
                    "artist": hit.artist,
                    "similarity": hit.similarity,
                    "similarity_percent": hit.similarity_percent,
                    "youtube_search_url": _youtube_search_url(hit.name, hit.artist),
                    "spotify_search_url": _spotify_search_url(hit.name, hit.artist),
                    "reason": report_to_dict(report),
                }
            )

        return JSONResponse(
            {
                "filename": file.filename,
                "summary": summary_metrics(features),
                "results": results,
                "timing": {
                    "feature_extraction_seconds": round(feature_seconds, 3),
                    "similarity_seconds": round(similarity_seconds, 3),
                },
                "catalog_size": engine.catalog_size,
            }
        )
    finally:
        # Always clean up the temp upload — we don't store user audio.
        try:
            os.remove(dest)
        except OSError:
            pass


def _youtube_search_url(title: str, artist: str) -> str:
    import urllib.parse
    q = urllib.parse.quote_plus(f"{title} {artist}")
    return f"https://www.youtube.com/results?search_query={q}"


def _spotify_search_url(title: str, artist: str) -> str:
    import urllib.parse
    q = urllib.parse.quote_plus(f"{title} {artist}")
    return f"https://open.spotify.com/search/{q}"


# ----------------------------------------------------------------------
# Frontend (static)
# ----------------------------------------------------------------------
if FRONTEND_DIR.exists():
    app.mount(
        "/static",
        StaticFiles(directory=str(FRONTEND_DIR)),
        name="static",
    )

    @app.get("/")
    def index():
        index_html = FRONTEND_DIR / "index.html"
        if not index_html.exists():
            raise HTTPException(status_code=404, detail="Frontend not built.")
        return FileResponse(str(index_html))

    # Asset shortcuts so the HTML can write <link href="/style.css"> etc.
    @app.get("/style.css")
    def style_css():
        return FileResponse(str(FRONTEND_DIR / "css" / "style.css"))

    @app.get("/app.js")
    def app_js():
        return FileResponse(str(FRONTEND_DIR / "js" / "app.js"))

    @app.get("/favicon.svg")
    def favicon():
        return FileResponse(str(FRONTEND_DIR / "assets" / "favicon.svg"))
