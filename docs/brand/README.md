# SoundMatch 색상·로고 가이드

2026년 9월 22일 기준. [화면 설계와 참고 자료](../design-2026.md)에서 선택 근거를 확인할 수 있다.

![SoundMatch 첫 화면](../screenshots/hero.png)

## 로고

두 파형은 같은 방향으로 흐르지만 굴곡이 조금 다르다. 서로 다른 음악에서 닮은 특성을 찾는 제품을 나타낸다.
제품명은 화면과 문서 모두 **SoundMatch**로 쓴다.

로고는 단색으로 표시한다. 밝은 바탕에서는 파랑, 어두운 바탕에서는 라임을 사용한다.
앱 아이콘과 파비콘은 파란 면 위 흰 파형으로 통일한다.

## 색상

![블루·라임·흰색·검정 색상표](palette.svg)

| 역할 | 라이트 모드 | 다크 모드 |
| --- | --- | --- |
| 본문 바탕 | `#FFFFFF` | `#111216` |
| 기본 글자 | `#111216` | `#FFFFFF` |
| 보조 글자 | `#484D5C` | `#CCD0DA` |
| 강조 | `#004CFF` | `#CCFF00` |
| 분석 차트 A | `#004CFF` | `#A5BAFF` |
| 분석 차트 B | `#111216` | `#CCFF00` |

첫 화면은 두 모드 모두 파란 바탕 `#004CFF`, 흰 글자 `#FFFFFF`, A 파형과 주요 버튼은 라임 `#CCFF00`이다.
라임 버튼 안 글자는 검정이다. A/B 표기를 색과 함께 제공한다.

## 글꼴

첫 화면 제목·큰 숫자는 **LINE Seed KR Bold**, 본문·폼·표는 **Pretendard Variable**을 바탕으로 한 로컬 서브셋을 사용한다.
파생 글꼴 이름은 SoundMatch Display / SoundMatch UI이며 원 저작권과 OFL 라이선스를 함께 배포한다.
본문의 숫자는 `tabular-nums`로 폭을 맞춘다. 전체 글꼴을 외부 CDN에서 매번 내려받지 않는다.

## 자산

| 파일 | 용도 |
| --- | --- |
| `brand-mark.svg` | 단색 파형 로고 |
| `app-icon-source.svg`, `maskable-icon-source.svg` | 앱 아이콘 원본 |
| `../../frontend/assets/favicon.svg` | SVG 파비콘 |
| `../../frontend/assets/favicon-32.png`, `favicon.ico` | 파비콘 폴백 |
| `../../frontend/assets/apple-touch-icon.png` | iOS 홈 화면 |
| `../../frontend/assets/app-icon-192.png`, `app-icon-512.png` | PWA 아이콘 |
| `../../frontend/assets/maskable-icon-512.png` | Android 마스커블 아이콘 |
| `../../frontend/assets/og-image.svg` | 실제 샘플 파형을 사용한 공유 이미지 |
| `../../frontend/assets/fonts/` | UI 글꼴과 라이선스 |

SVG·PNG 결과 저장도 흰색·검정·파랑을 사용한다. 이미지 자산에 이전 베이지·코랄 색상을 섞지 않는다.
