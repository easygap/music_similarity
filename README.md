<div align="center">

# 🎧 SoundMatch · AI 음악 유사도 분석

**음악을 업로드하면 sklearn 코사인 유사도로 가장 닮은 곡을 찾고, 닮은 이유까지 설명하는 웹 서비스.**

[![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![scikit-learn](https://img.shields.io/badge/scikit--learn-1.4-F7931E?logo=scikit-learn&logoColor=white)](https://scikit-learn.org/)
[![librosa](https://img.shields.io/badge/librosa-0.10-5C2D91)](https://librosa.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

</div>

---

졸업작품으로 만들었던 [easygap/capstone_music](https://github.com/easygap/capstone_music)을 기반으로,
**완성도 있는 단일 웹 서비스**로 재설계한 프로젝트입니다.

* 🎼 음악 파일 업로드 (드래그&드롭 / 클릭)
* 🤖 **58개 오디오 특성** 추출 (librosa)
* 📐 **sklearn StandardScaler + cosine similarity**로 카탈로그 매칭
* 🥇 **순위 + 유사도 퍼센트** 표시
* 💡 **닮은 이유**를 한국어 문장으로 자동 생성
* 🎨 다크모드 글래스모피즘 UI, 모바일 반응형
* 🔍 결과별 YouTube · Spotify 검색 링크 자동 생성

---

## ✨ 데모 · 화면 흐름

1. **메인 화면** — Hero + 업로드 카드
2. **분석 중** — 단계별 진행 메시지(librosa → MFCC → cosine)
3. **결과 화면** — 업로드 곡의 오디오 요약 + 상위 N곡 카드 (유사도 게이지·이유 분해)

업로드한 음원은 분석이 끝나는 즉시 서버에서 자동 삭제됩니다.
사용자 음악은 카탈로그에 학습되지도, 저장되지도 않습니다.

---

## 🏗️ 아키텍처

```
┌────────────────────┐        ┌────────────────────────────────────┐
│   Browser (HTML)   │  POST  │             FastAPI                │
│   /api/analyze     │ ─────▶ │  ├─ audio_features.py (librosa)    │
│   드래그/드롭 UI   │        │  ├─ similarity.py (sklearn cosine) │
│                    │ ◀───── │  └─ reason_engine.py (NL 설명)     │
└────────────────────┘  JSON  └────────────────────────────────────┘
                                          │
                                          ▼
                              data/dataset.csv (사전 추출된 카탈로그)
```

### 핵심 코드

| 파일 | 역할 |
| --- | --- |
| `backend/audio_features.py` | librosa로 RMS · BPM · 스펙트럴 · 크로마 · 20-MFCC 등 58개 특성 추출 |
| `backend/similarity.py` | `StandardScaler`로 정규화 후 `cosine_similarity`로 카탈로그와 비교 |
| `backend/reason_engine.py` | 특성 거리(z-score)를 음악적 개념으로 묶어 한국어 설명 생성 |
| `backend/main.py` | FastAPI 엔드포인트 + 정적 프론트엔드 서빙 |
| `frontend/index.html` | 단일 페이지 UI (Pretendard / Inter / JetBrains Mono) |
| `frontend/css/style.css` | 다크모드 글래스모피즘 디자인 시스템 |
| `frontend/js/app.js` | 업로드 · 진행상태 · 결과 렌더링 |
| `data/dataset.csv` | 곡 카탈로그 + 사전 추출된 특성값 |

---

## 🎼 분석되는 오디오 특성 (58개)

| 그룹 | 특성 |
| --- | --- |
| **기본** | `length` (참조용 라벨, 유사도 계산 시 제외) |
| **에너지** | `rms_mean`, `rms_var` |
| **템포** | `bpm` (librosa beat track) |
| **거친 정도** | `zero_crossing_rate_mean`, `zero_crossing_rate_var` |
| **HPSS** | `harmony_mean/var`, `percussive_mean/var` |
| **스펙트럴** | `spectral_centroid_mean/var`, `spectral_bandwidth_mean/var`, `spectral_rolloff_mean/var` |
| **크로마** | `chroma_frequencies_mean`, `chroma_frequencies_var` |
| **MFCC** | `mfcc1_mean/var` ~ `mfcc20_mean/var` (총 40개) |

원작 캡스톤 노트북과 동일한 컬럼 레이아웃을 유지해서, 기존
`Project Dataset.csv`를 그대로 재사용할 수 있습니다.

---

## 🚀 빠른 시작

### 옵션 1 · 로컬 (권장: 첫 실행)

```bash
# 1) 클론
git clone https://github.com/easygap/music_similarity.git
cd music_similarity

# 2) 가상환경 + 의존성
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 3) 개발 서버 실행 (자동 reload)
uvicorn backend.main:app --reload --port 8000
```

브라우저에서 <http://localhost:8000> 접속 → 음악 파일 업로드.

### 옵션 2 · Docker

```bash
docker compose up --build
# http://localhost:8000
```

### 옵션 3 · 쉘 스크립트

* Linux/macOS: `bash scripts/dev.sh`
* Windows PowerShell: `pwsh scripts/dev.ps1`

---

## 🧪 API 사용법

### `POST /api/analyze`

```bash
curl -X POST http://localhost:8000/api/analyze \
  -F "file=@./my_song.wav" \
  "&top_n=5"
```

**응답 예시**

```json
{
  "filename": "my_song.wav",
  "summary": {
    "tempo_bpm": 128.0,
    "energy_rms": 0.3142,
    "brightness": 3120.5,
    "noisiness": 0.115,
    "harmony_ratio": 0.92,
    "chroma": 0.412
  },
  "results": [
    {
      "rank": 1,
      "title": "Invincible",
      "artist": "DEAF KEV",
      "similarity": 0.9123,
      "similarity_percent": 91.2,
      "youtube_search_url": "https://www.youtube.com/results?search_query=Invincible+DEAF+KEV",
      "spotify_search_url": "https://open.spotify.com/search/Invincible%20DEAF%20KEV",
      "reason": {
        "summary": "두 곡은 **템포 & 리듬** 측면이 특히 닮았고, 전반적인 청각적 인상이 비슷합니다.",
        "groups": [
          {
            "label": "템포 & 리듬",
            "match_score": 0.94,
            "summary": "템포 & 리듬 측면에서 매우 닮은 특성을 보입니다.",
            "detail": [
              "템포: 업로드한 곡 128.00BPM · 매칭된 곡 130.50BPM (비슷한 값)"
            ]
          }
        ]
      }
    }
  ],
  "timing": { "feature_extraction_seconds": 1.42, "similarity_seconds": 0.012 },
  "catalog_size": 1006
}
```

### `GET /api/catalog`

```json
{
  "catalog_size": 1006,
  "feature_count": 57,
  "features": ["rms_mean", "rms_var", "bpm", ...]
}
```

### `GET /api/health`

라이브니스 프로브용 — 카탈로그 사이즈와 OK 상태만 돌려줍니다.

---

## 🧰 카탈로그 다시 만들기

사용자가 가지고 있는 .wav/.mp3 폴더로 카탈로그를 다시 빌드하고 싶다면:

```bash
python scripts/rebuild_dataset.py \
    --audio-dir ./my_songs \
    --out data/dataset.csv
```

파일명 규칙: `"Song Title - Artist Name.wav"` (UI에서 아티스트를 분리해 표시할 때 사용).

---

## 🛠️ 기술 스택

| 영역 | 라이브러리 |
| --- | --- |
| 백엔드 | **FastAPI** · uvicorn · python-multipart |
| 머신러닝 | **scikit-learn** (StandardScaler · cosine_similarity) |
| 오디오 | **librosa** (STFT · MFCC · HPSS · beat track) |
| 데이터 | numpy · pandas |
| 프론트엔드 | 순수 HTML/CSS/JS (빌드 스텝 없음), Pretendard · Inter · JetBrains Mono |
| 컨테이너 | Docker · docker-compose |

---

## 📂 디렉토리 구조

```
music_similarity/
├── backend/
│   ├── __init__.py
│   ├── audio_features.py       # librosa 특성 추출
│   ├── similarity.py           # sklearn 유사도 엔진
│   ├── reason_engine.py        # 한국어 설명 생성
│   └── main.py                 # FastAPI 엔트리포인트
├── frontend/
│   ├── index.html
│   ├── css/style.css
│   ├── js/app.js
│   └── assets/favicon.svg
├── data/
│   └── dataset.csv             # 사전 추출된 카탈로그
├── scripts/
│   ├── dev.sh                  # Linux/macOS 개발 실행 스크립트
│   ├── dev.ps1                 # Windows PowerShell 개발 스크립트
│   └── rebuild_dataset.py      # 카탈로그 재생성
├── uploads/                    # 업로드 임시 폴더 (자동 정리)
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

---

## 🔒 개인정보 & 보안

* 업로드된 음원은 **분석 종료 즉시 삭제**되며, 카탈로그에 추가/학습되지 않습니다.
* 파일 사이즈는 25MB로 제한되어 있고, 허용 확장자는 `.wav .mp3 .flac .ogg .m4a` 입니다.
* 외부에 노출할 때는 nginx 등 리버스 프록시 뒤에 두고 HTTPS를 사용하는 것을 권장합니다.

---

## 🗺️ 향후 개선 아이디어

* 결과 카드에 30초 미리듣기(스트리밍 + 오디오 비주얼라이저)
* Annoy/FAISS 기반 ANN 검색으로 대규모 카탈로그 지원
* 사용자 직접 카탈로그 업로드(관리자 페이지)
* 장르 다중 분류(예: trap / EDM / classical)와 유사도 함께 표기
* 다국어(EN/JP) 지원

---

## 📜 라이선스

MIT License. 자유롭게 포크 후 사용하세요.

원작 캡스톤 데이터셋과 코드는 [easygap/capstone_music](https://github.com/easygap/capstone_music)
에서 확인할 수 있습니다.

---

> Made with 🎵 by [@easygap](https://github.com/easygap)
