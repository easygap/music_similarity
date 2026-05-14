// 카탈로그 곡 즐겨찾기 (localStorage 기반) -------------------------------
// 키는 "곡명 - 아티스트" 풀 네임을 그대로 사용한다 — 백엔드 카탈로그 인덱스와
// 동일한 표기. 이렇게 두면 즐겨찾기에 저장된 곡으로 by-catalog 분석을 그대로
// 돌릴 수 있다.
//
// 사이즈는 200곡으로 cap. 그보다 많이 쌓이는 일은 거의 없지만, localStorage
// 쿼터 (5MB) 안전 마진을 위해 둔다.

(function () {
  const KEY = "soundmatch.favorites.v1";
  const MAX = 200;

  function read() {
    try {
      const raw = localStorage.getItem(KEY);
      if (!raw) return [];
      const parsed = JSON.parse(raw);
      return Array.isArray(parsed) ? parsed : [];
    } catch {
      return [];
    }
  }

  function write(items) {
    try {
      localStorage.setItem(KEY, JSON.stringify(items.slice(0, MAX)));
      return true;
    } catch (err) {
      // 쿼터 초과 (히스토리와 같은 5MB 쿼터 공유) / 사파리 시크릿 모드 등.
      // 조용히 무시하지 않고 외부에서 알 수 있도록 이벤트 한 번 쏴준다.
      // 외부 (app.js) 가 토스트로 안내한다.
      console.warn("[soundmatch] favorites write failed:", err);
      try {
        window.dispatchEvent(new CustomEvent("favorites:storage-full"));
      } catch (_) {}
      return false;
    }
  }

  function has(name) {
    if (!name) return false;
    return read().some((it) => it && it.name === name);
  }

  function add(name, title, artist) {
    if (!name) return false;
    if (has(name)) return false;
    const items = read();
    items.unshift({
      name,
      title: title || name,
      artist: artist || "",
      addedAt: Date.now(),
    });
    write(items);
    dispatchChange();
    return true;
  }

  function remove(name) {
    if (!name) return false;
    const before = read();
    const after = before.filter((it) => it.name !== name);
    if (after.length === before.length) return false;
    write(after);
    dispatchChange();
    return true;
  }

  function toggle(name, title, artist) {
    return has(name) ? !remove(name) : add(name, title, artist);
  }

  function list() {
    return read();
  }

  function size() {
    return read().length;
  }

  function clearAll() {
    write([]);
    dispatchChange();
  }

  // 즐겨찾기 백업용 JSON 페이로드. 버전 필드를 두면 나중에 스키마가 바뀌어도
  // 안전하게 마이그레이션 분기를 칠 수 있다.
  function exportJson() {
    const items = read();
    return JSON.stringify(
      {
        format: "soundmatch.favorites",
        version: 1,
        exportedAt: new Date().toISOString(),
        count: items.length,
        items,
      },
      null,
      2,
    );
  }

  function sanitizeIncoming(raw) {
    // 들어온 항목에서 신뢰할 수 있는 필드만 골라낸다. 외부에서 손댄 JSON 이
    // 들어와도 동일한 정규형으로 변환되도록.
    if (!raw || typeof raw !== "object") return null;
    const name = typeof raw.name === "string" ? raw.name.trim() : "";
    if (!name) return null;
    return {
      name: name.slice(0, 400),
      title: typeof raw.title === "string" && raw.title ? raw.title.slice(0, 200) : name,
      artist: typeof raw.artist === "string" ? raw.artist.slice(0, 200) : "",
      addedAt:
        typeof raw.addedAt === "number" && Number.isFinite(raw.addedAt)
          ? raw.addedAt
          : Date.now(),
    };
  }

  // 들어온 배열을 즐겨찾기 저장소에 그대로 덮어쓴다 (import 시 사용).
  // 같은 name 이 여러 개면 처음 것만 살린다.
  function replaceAll(items) {
    if (!Array.isArray(items)) return 0;
    const seen = new Set();
    const cleaned = [];
    for (const raw of items) {
      const it = sanitizeIncoming(raw);
      if (!it) continue;
      if (seen.has(it.name)) continue;
      seen.add(it.name);
      cleaned.push(it);
      if (cleaned.length >= MAX) break;
    }
    write(cleaned);
    dispatchChange();
    return cleaned.length;
  }

  // 백업 JSON 을 읽어 들이고 기존 즐겨찾기와 병합 (덮어쓰지 않음).
  // 반환값: { added, total } — 새로 추가된 곡 수와 최종 즐겨찾기 개수.
  function importJson(text, options) {
    const opts = options || {};
    let parsed;
    try {
      parsed = JSON.parse(text);
    } catch {
      throw new Error("INVALID_JSON");
    }
    // 두 가지 형태 허용: 우리 익스포트 포맷({items:[...]}) / 그냥 배열.
    let arr;
    if (Array.isArray(parsed)) {
      arr = parsed;
    } else if (parsed && Array.isArray(parsed.items)) {
      arr = parsed.items;
    } else {
      throw new Error("UNSUPPORTED_FORMAT");
    }
    if (opts.replace) {
      const total = replaceAll(arr);
      return { added: total, total };
    }
    // 병합 모드 — 기존 항목 위에 신규 항목을 추가한다.
    const existing = read();
    const existingNames = new Set(existing.map((it) => it.name));
    const incoming = [];
    for (const raw of arr) {
      const it = sanitizeIncoming(raw);
      if (!it) continue;
      if (existingNames.has(it.name)) continue;
      existingNames.add(it.name);
      incoming.push(it);
      if (existing.length + incoming.length >= MAX) break;
    }
    const merged = incoming.concat(existing).slice(0, MAX);
    write(merged);
    dispatchChange();
    return { added: incoming.length, total: merged.length };
  }

  function dispatchChange() {
    try {
      window.dispatchEvent(new CustomEvent("favorites:change"));
    } catch {}
  }

  window.SoundMatchFavorites = {
    has,
    add,
    remove,
    toggle,
    list,
    size,
    clearAll,
    exportJson,
    importJson,
    replaceAll,
  };
})();
