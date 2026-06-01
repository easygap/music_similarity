"""OpenAPI 응답 모델.

타입을 명시해두면 ``/docs`` 의 Swagger UI 에서 응답 구조가 깔끔하게 잡힌다.
프론트엔드에서 이 스키마를 그대로 fetch type 생성에 쓸 수 있다는 것도 장점.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(..., examples=["ok"])
    catalog_size: int = Field(..., examples=[781])
    env: str = Field("development", examples=["production"])
    version: str = Field(..., examples=["1.8.4"])
    # 빌드 식별용 메타 — /api/version 과 같은 값. 운영자가 health 만 봐도 빌드 확인 가능.
    release_date: str | None = Field(
        None,
        description="CHANGELOG 에서 파싱한 최신 release 일자 (YYYY-MM-DD). 없으면 null.",
        examples=["2026-05-21"],
    )
    git_commit: str | None = Field(
        None,
        description="짧은 7자 git SHA. 환경변수 MUSIC_GIT_COMMIT → .git/HEAD fallback.",
        examples=["7cf785a"],
    )
    uptime_seconds: float = Field(0.0, description="프로세스 부팅 후 경과 시간(초)")
    analyze_latency_p50_seconds: float = Field(0.0, description="최근 분석 latency P50(초). 샘플 없으면 0.")
    catalog_updated_at: str | None = Field(
        None,
        description="카탈로그 CSV 의 마지막 수정 시각(ISO 8601, UTC). 파일이 없거나 stat 실패면 null.",
        examples=["2026-05-15T00:42:51+00:00"],
    )
    # degraded 응답 전용 필드 — 정상(ok) 응답에서는 항상 null/없음.
    # 식별자 enum: engine_load_failed | ml_imports_unavailable | upload_dir_not_writable
    reason: str | None = Field(
        None,
        description="degraded 응답 시 어느 점검이 실패했는지 식별자. ok 응답에서는 항상 null.",
        examples=["engine_load_failed"],
    )
    reason_detail: str | None = Field(
        None,
        description="실패 exception 의 클래스명. 상세 traceback 은 노출하지 않고 운영 로그로 확인.",
        examples=["ValueError"],
    )


class CatalogResponse(BaseModel):
    catalog_size: int
    feature_count: int
    features: list[str]


class SummaryMetrics(BaseModel):
    tempo_bpm: float
    energy_rms: float
    brightness: float
    noisiness: float
    harmony_ratio: float
    chroma: float


class ReasonGroupSchema(BaseModel):
    label: str
    match_score: float
    summary: str
    detail: list[str]


class ReasonReportSchema(BaseModel):
    summary: str
    groups: list[ReasonGroupSchema]


class HitResult(BaseModel):
    rank: int
    title: str
    artist: str
    similarity: float
    similarity_percent: float
    youtube_search_url: str
    spotify_search_url: str
    match_summary: SummaryMetrics | None = None
    reason: ReasonReportSchema


class TimingInfo(BaseModel):
    feature_extraction_seconds: float
    similarity_seconds: float


class AnalyzeResponse(BaseModel):
    request_id: str
    filename: str
    summary: SummaryMetrics
    # 휴리스틱 태그(예: ["빠른 템포", "에너지 폭발", "밝은 톤"]). 빈 배열 가능.
    tags: list[str] = Field(default_factory=list)
    results: list[HitResult]
    timing: TimingInfo
    catalog_size: int
    # 멜 스펙트로그램 SVG 문자열. 시각화 실패 시 빈 문자열.
    spectrogram_svg: str = ""
    # 분석 메타데이터 — 결과 JSON 을 나중에 다시 봐도 재현 가능한 정보들.
    analyzed_at: str = Field(..., description="ISO-8601 UTC 분석 완료 시각")
    engine_version: str = Field(..., examples=["1.8.4"])
    cached: bool = Field(False, description="결과 캐시에서 즉시 응답된 경우 True")
