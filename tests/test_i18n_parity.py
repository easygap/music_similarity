"""i18n 사전의 ko/en 키 누락을 막아주는 회귀 테스트.

`frontend/js/i18n.js` 안의 `dict = { ko: {...}, en: {...} }` 블록을 파싱해서
두 트리의 키 셋이 동일한지 확인한다. 동적 JS 평가가 필요해서 brittle 할 수
있으니 정규식과 brace counting 으로 최소 범위만 잘라낸다.
"""
from __future__ import annotations

import re
from pathlib import Path


def _extract_block(text: str, key: str) -> str:
    """``key: {`` 로 시작하는 객체 블록을 균형 잡힌 중괄호 단위로 잘라 반환."""
    pattern = re.compile(rf"\b{re.escape(key)}\s*:\s*{{", re.MULTILINE)
    m = pattern.search(text)
    assert m, f"i18n.js 에서 '{key}:' 블록을 찾지 못했습니다."
    start = m.end() - 1  # 여는 중괄호 위치
    depth = 0
    for i in range(start, len(text)):
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    raise AssertionError(f"'{key}' 블록의 닫는 중괄호를 찾지 못했습니다.")


def _walk_keys(block: str, prefix: str = "") -> set[str]:
    """블록 안에서 dot-path 키 집합을 뽑는다. 값이 객체면 재귀로 들어간다.

    문자열 리터럴(따옴표 사이) 의 콜론은 무시한다. 줄 단위 정규식만으로는
    중첩 객체를 정확히 잡기 어려워서 토크나이저처럼 간단히 짠다.
    """
    keys: set[str] = set()
    i = 0
    n = len(block)
    # 가장 바깥 중괄호를 한 번 벗긴다.
    if block.startswith("{"):
        i = 1
        n -= 1
    while i < n:
        ch = block[i]
        # 공백/콤마/세미콜론 건너뛰기.
        if ch in " \t\r\n,;":
            i += 1
            continue
        # 줄 주석 / 블록 주석 건너뛰기.
        if ch == "/" and i + 1 < n and block[i + 1] in "/*":
            if block[i + 1] == "/":
                end = block.find("\n", i)
                i = end + 1 if end != -1 else n
            else:
                end = block.find("*/", i + 2)
                i = end + 2 if end != -1 else n
            continue
        # 키 시작. 이름 토큰 추출.
        key_match = re.match(r'(\w+|"[^"]+"|\'[^\']+\')\s*:', block[i:])
        if not key_match:
            i += 1
            continue
        raw_key = key_match.group(1).strip('"\'')
        i += key_match.end()
        # 다음 값 시작 위치.
        while i < n and block[i] in " \t\r\n":
            i += 1
        if i >= n:
            break
        full_key = f"{prefix}{raw_key}" if not prefix else f"{prefix}.{raw_key}"
        if block[i] == "{":
            # 중첩 객체 — 재귀로 진입.
            depth = 0
            start = i
            while i < n:
                if block[i] == "{":
                    depth += 1
                elif block[i] == "}":
                    depth -= 1
                    if depth == 0:
                        nested = block[start : i + 1]
                        keys.update(_walk_keys(nested, full_key))
                        i += 1
                        break
                i += 1
        else:
            # 단일 값(문자열 / 함수 / 배열 등). 첫 콤마 또는 줄바꿈까지 건너뛴다.
            depth = 0
            in_str: str | None = None
            while i < n:
                c = block[i]
                if in_str:
                    if c == "\\" and i + 1 < n:
                        i += 2
                        continue
                    if c == in_str:
                        in_str = None
                elif c in "\"'`":
                    in_str = c
                elif c in "([{":
                    depth += 1
                elif c in ")]}":
                    if depth == 0:
                        break
                    depth -= 1
                elif c == "," and depth == 0:
                    break
                i += 1
            keys.add(full_key)
    return keys


def test_i18n_ko_en_key_parity():
    """ko 와 en 의 키 집합이 정확히 일치해야 한다."""
    js = Path(__file__).resolve().parent.parent / "frontend" / "js" / "i18n.js"
    text = js.read_text(encoding="utf-8")

    ko_block = _extract_block(text, "ko")
    en_block = _extract_block(text, "en")

    ko_keys = _walk_keys(ko_block)
    en_keys = _walk_keys(en_block)

    missing_in_en = sorted(ko_keys - en_keys)
    missing_in_ko = sorted(en_keys - ko_keys)

    assert not missing_in_en, f"en 에 빠진 키: {missing_in_en}"
    assert not missing_in_ko, f"ko 에 빠진 키: {missing_in_ko}"


def test_i18n_has_critical_keys():
    """핵심 키 몇 개가 빠지지 않았는지 빠르게 sanity check."""
    js = Path(__file__).resolve().parent.parent / "frontend" / "js" / "i18n.js"
    text = js.read_text(encoding="utf-8")
    ko = _walk_keys(_extract_block(text, "ko"))
    must_have = {
        "hero.title",
        "upload.submit",
        "results.title",
        "results.copyShareUrl",
        "footer.privacy",
        "footer.terms",
        "info.catalogPreviewTitle",
    }
    missing = sorted(must_have - ko)
    assert not missing, f"ko 사전에 필수 키 누락: {missing}"
