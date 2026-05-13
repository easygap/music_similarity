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
    } catch {
      // 쿼터 초과나 사파리 시크릿 모드 등은 조용히 무시.
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

  function dispatchChange() {
    try {
      window.dispatchEvent(new CustomEvent("favorites:change"));
    } catch {}
  }

  window.SoundMatchFavorites = { has, add, remove, toggle, list, size, clearAll };
})();
