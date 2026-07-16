# SoundMatch BI 가이드

## 콘셉트

SoundMatch는 두 곡이 완전히 같다고 판정하지 않는다. 여러 음악 특성을 비교해
얼마나 닮았는지 보여준다. BI는 등호 대신 근삿값 기호 `≈`를 출발점으로 삼았다.

위아래 두 획은 같은 파형을 복제하지 않았다. 길이와 곡률이 조금씩 다르지만 같은
방향으로 움직여서 “같지는 않지만 닮음”을 표현한다. 음표, 헤드폰, 재생 버튼처럼
음악 서비스에서 반복되는 상징은 사용하지 않는다.

헤더의 시각 워드마크는 소문자 `soundmatch`를 사용한다. 본문, 문서, 접근성 이름은
기존 제품명 `SoundMatch`를 유지한다.

## 색상 역할

| 토큰 | 색상 | 용도 |
| --- | --- | --- |
| Black | `#101010` | 기본 배경, 본문, 상단 획 |
| Paper | `#efefef` | 기본 글자, 밝은 배경 |
| Near Green | `#b9ee84` | 브랜드 하단 획, 핵심 행동, 1순위 결과 |
| Compare Sky | `#b9e0fd` | 업로드 곡과 비교 데이터 |
| Notice Yellow | `#faed27` | 경고와 제한적인 주의 표시 |

초록, 하늘색, 노랑을 한 화면의 장식으로 동시에 펼치지 않는다. 의미가 있는 상태와
데이터에만 사용하고, 나머지는 Black/Paper 대비로 구성한다.

## 사용 규칙

- 로고에 그라데이션, 광택, 그림자, 외곽선을 추가하지 않는다.
- 두 획의 간격과 서로 다른 곡률을 유지한다.
- 밝은 배경에서는 Black/Green, 어두운 배경에서는 Paper/Green 조합을 사용한다.
- 헤더에는 배경 없는 브랜드 마크를, 브라우저와 홈 화면에는 타일형 아이콘을 사용한다.
- 파비콘은 16px 미만으로 축소하지 않는다.
- 마스커블 아이콘의 핵심 도형은 중앙 안전 영역 안에 둔다.
- 배경과 상단 획의 대비가 사라지는 조합은 사용하지 않는다.

## 자산

| 파일 | 용도 |
| --- | --- |
| `docs/brand/brand-mark.svg` | 밝은 배경용 독립 브랜드 마크 원본 |
| `frontend/assets/favicon.svg` | 브라우저용 타일형 파비콘 |
| `frontend/assets/favicon-32.png` | PNG 파비콘 폴백 |
| `frontend/assets/favicon.ico` | 레거시 브라우저 폴백 |
| `frontend/assets/apple-touch-icon.png` | iOS 홈 화면 |
| `frontend/assets/app-icon-192.png` | PWA 192px 아이콘 |
| `frontend/assets/app-icon-512.png` | PWA 512px 아이콘 |
| `frontend/assets/maskable-icon-512.png` | Android 마스커블 아이콘 |
| `docs/brand/app-icon-source.svg` | 일반 앱 아이콘 원본 |
| `docs/brand/maskable-icon-source.svg` | 마스커블 아이콘 원본 |
