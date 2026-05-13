"""OpenAPI 응답 모델.

타입을 명시해두면 ``/docs`` 의 Swagger UI 에서 응답 구조가 깔끔하게 잡힌다.
프론트엔드에서 이 스키마를 그대로 fetch type 생성에 쓸 수 있다는 것도 장점.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(..., examples=["ok"])
    catalog_size: int = Field(..., examples=[1006])
    env: str = Field("development", examples=["production"])
    version: str = Field(..., examples=["1.2.0"])


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
    results: list[HitResult]
    timing: TimingInfo
    catalog_size: int
    # 멜 스펙트로그램 SVG 문자열. 시각화 실패 시 빈 문자열.
    spectrogram_svg: str = ""
