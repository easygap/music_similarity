// 실제 mel 스펙트로그램을 2D 캔버스에 입체 투영한다. 정지 화면/재생 위치를 분리한다.
(function () {
  "use strict";
  window.SoundMatchSurface = function (tracks) {
    const viewport = document.getElementById("surface-viewport");
    const base = document.getElementById("sound-surface"), cursor = document.getElementById("surface-cursor");
    if (!viewport || !base || !cursor) return null;
    const ctx = base.getContext("2d"), live = cursor.getContext("2d");
    if (!ctx || !live) return null;
    const reduced = matchMedia("(prefers-reduced-motion: reduce)");
    let width = 0, height = 0, dpr = 1, visible = true, raf = 0;
    let second = "tone", progress = 0, playing = false, channel = "a";
    let spread = 1, targetSpread = 1, angle = -.20, targetAngle = -.20;
    let lastTime = 0, rows = [], colors, scrollTilt = 0;
    let compact = false, cosine = 1, sine = 0;
    const clamp = (value, min, max) => Math.max(min, Math.min(max, value));
    const readColors = () => {
      const style = getComputedStyle(base);
      colors = { a: style.getPropertyValue("--series-query").trim(), b: style.getPropertyValue("--series-match").trim(), ink: style.getPropertyValue("--ink-mute").trim(), rule: style.getPropertyValue("--rule").trim() };
    };
    function project(x, z, amplitude) {
      const xx = x * cosine - z * sine;
      const zz = x * sine + z * cosine;
      return [xx, zz * (.36 + scrollTilt) - amplitude * .96];
    }
    function pointsFor(track, time, side) {
      const values = track.surface[time];
      const xOffset = side * .60 * spread;
      const z = (time / (track.surface.length - 1) - .5) * 2.7 + side * .20 * spread;
      const points = values.map((value, index) => project((index / (values.length - 1) - .5) * 2.9 + xOffset, z, Math.pow(value / 255, 1.6)));
      return { points, z, from: project(-1.45 + xOffset, z, 0), to: project(1.45 + xOffset, z, 0), time, side };
    }
    function fitProjection(axis) {
      // 실제 투영 범위로 맞춘다. 시점·샘플·화면 폭이 바뀌어도 끝선과 축이 잘리지 않는다.
      let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
      const include = (point) => {
        minX = Math.min(minX, point[0]); maxX = Math.max(maxX, point[0]);
        minY = Math.min(minY, point[1]); maxY = Math.max(maxY, point[1]);
      };
      rows.forEach((row) => { row.points.forEach(include); include(row.from); include(row.to); });
      axis.forEach(include);
      const left = compact ? 14 : width * .41, right = width - 16;
      const top = compact ? 16 : 34, bottom = height - (compact ? 28 : 96);
      const scale = Math.min((right - left) / (maxX - minX), (bottom - top) / (maxY - minY), compact ? 150 : 172);
      const centerX = clamp(width * (compact ? .50 : .70), left - minX * scale, right - maxX * scale);
      const centerY = clamp(height * (compact ? .57 : .50), top - minY * scale, bottom - maxY * scale);
      const toCanvas = (point) => [centerX + point[0] * scale, centerY + point[1] * scale];
      rows.forEach((row) => { row.points = row.points.map(toCanvas); });
      return axis.map(toCanvas);
    }
    function trace(context, points) {
      context.beginPath();
      context.moveTo(points[0][0], points[0][1]);
      for (let index = 1; index < points.length - 1; index++) {
        const point = points[index], next = points[index + 1];
        context.quadraticCurveTo(point[0], point[1], (point[0] + next[0]) / 2, (point[1] + next[1]) / 2);
      }
      const last = points[points.length - 1];
      context.lineTo(last[0], last[1]);
    }
    function draw() {
      if (!width || !height || !visible) return;
      if (!colors) readColors();
      ctx.clearRect(0, 0, width, height);
      cosine = Math.cos(angle); sine = Math.sin(angle);
      rows = [];
      [tracks[0], tracks.find((track) => track.id === second)].forEach((track, index) => {
        if (!track || !track.surface) return;
        track.surface.forEach((_, time) => rows.push(pointsFor(track, time, index ? 1 : -1)));
      });
      rows.sort((a, b) => a.z - b.z);
      const axis = fitProjection([project(-1.8, -1.7, 0), project(-1.8, 1.8, 0), project(1.75, 1.8, 0)]);
      ctx.lineJoin = "round"; ctx.lineCap = "round";
      // 두 데이터의 경계도 연결한다. 불투명 면으로 다른 곡의 선을 덮지 않는다.
      [-1, 1].forEach((side) => {
        const ridges = rows.filter((row) => row.side === side).sort((a, b) => a.time - b.time);
        if (!ridges.length) return;
        ctx.strokeStyle = side < 0 ? colors.a : colors.b;
        ctx.globalAlpha = .32; ctx.lineWidth = .7;
        [0, ridges[0].points.length - 1].forEach((edge) => {
          trace(ctx, ridges.map((row) => row.points[edge])); ctx.stroke();
        });
      });
      // 좁은 화면에서 선이 뭉치지 않도록 표시 간격만 넓힌다. 재생 커서는 전체 데이터를 쓴다.
      const stride = width < 500 ? 3 : 2;
      rows.forEach((row) => {
        if (row.time % stride && row.time !== tracks[0].surface.length - 1) return;
        trace(ctx, row.points);
        ctx.globalAlpha = (row.side < 0 ? .92 : .82) * (.4 + .6 * row.time / (tracks[0].surface.length - 1));
        ctx.strokeStyle = row.side < 0 ? colors.a : colors.b;
        ctx.lineWidth = width < 780 ? .75 : 1.05;
        ctx.stroke();
      });
      ctx.globalAlpha = 1;
      // Axes follow the same projection; these are data coordinates, not decoration.
      ctx.strokeStyle = colors.rule;
      ctx.lineWidth = .75;
      ctx.beginPath();
      axis.forEach((point, index) => index ? ctx.lineTo(...point) : ctx.moveTo(...point));
      ctx.stroke();
      ctx.fillStyle = colors.ink;
      ctx.font = "10px sans-serif";
      ctx.textAlign = "left";
      const from = axis[1], to = axis[2];
      ctx.fillText("40 Hz", from[0], from[1] + 15);
      ctx.textAlign = "right";
      ctx.fillText("10 kHz", to[0], to[1] + 15);
      paintCursor();
    }
    function paintCursor() {
      if (!visible || !width) return;
      live.clearRect(0, 0, width, height);
      if (!playing && progress === 0) return;
      const time = Math.round(clamp(progress, 0, 1) * (tracks[0].surface.length - 1));
      const row = rows.find((candidate) => candidate.time === time && candidate.side === (channel === "a" ? -1 : 1));
      if (!row) return;
      trace(live, row.points);
      live.strokeStyle = channel === "a" ? colors.a : colors.b;
      live.lineWidth = 2.6;
      live.stroke();
      const first = row.points[0];
      live.beginPath(); live.arc(first[0], first[1], 4, 0, Math.PI * 2);
      live.fillStyle = live.strokeStyle; live.fill();
    }
    function animate(now) {
      raf = 0;
      if (!visible || document.hidden) return;
      const delta = lastTime ? Math.min(50, now - lastTime) : 16;
      lastTime = now;
      const ease = reduced.matches ? 1 : 1 - Math.exp(-delta / 90);
      spread += (targetSpread - spread) * ease;
      angle += (targetAngle - angle) * ease;
      if (Math.abs(targetSpread - spread) < .002) spread = targetSpread;
      if (Math.abs(targetAngle - angle) < .001) angle = targetAngle;
      draw();
      if (spread !== targetSpread || angle !== targetAngle) schedule();
    }
    function schedule() { if (!raf && visible && !document.hidden) raf = requestAnimationFrame(animate); }
    function resize() {
      const rect = viewport.getBoundingClientRect();
      compact = matchMedia("(max-width: 1100px)").matches;
      width = Math.round(rect.width); height = Math.round(rect.height);
      dpr = Math.min(devicePixelRatio || 1, 1.75);
      [base, cursor].forEach((canvas) => { canvas.width = Math.round(width * dpr); canvas.height = Math.round(height * dpr); });
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0); live.setTransform(dpr, 0, 0, dpr, 0, 0);
      schedule();
    }
    document.getElementById("surface-overlay").addEventListener("click", (event) => {
      targetSpread = targetSpread ? 0 : 1;
      event.currentTarget.setAttribute("aria-pressed", String(!targetSpread));
      lastTime = 0; schedule();
    });
    document.getElementById("surface-view").addEventListener("click", (event) => {
      targetAngle = targetAngle < 0 ? .32 : -.20;
      event.currentTarget.setAttribute("aria-pressed", String(targetAngle > 0));
      lastTime = 0; schedule();
    });
    const onScroll = () => {
      if (!visible || reduced.matches) return;
      const next = clamp(window.scrollY / 800, 0, 1) * .07;
      if (Math.abs(next - scrollTilt) < .002) return;
      scrollTilt = next; schedule();
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    const resizeObserver = typeof ResizeObserver === "function" ? new ResizeObserver(resize) : null;
    if (resizeObserver) resizeObserver.observe(viewport); else window.addEventListener("resize", resize);
    const observer = typeof IntersectionObserver === "function" ? new IntersectionObserver((entries) => {
      visible = entries[0].isIntersecting;
      if (!visible) { cancelAnimationFrame(raf); raf = 0; } else schedule();
    }) : null;
    if (observer) observer.observe(viewport);
    new MutationObserver(() => { colors = null; schedule(); }).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    document.addEventListener("visibilitychange", () => {
      if (document.hidden) { cancelAnimationFrame(raf); raf = 0; } else { lastTime = 0; schedule(); }
    });
    reduced.addEventListener("change", () => { scrollTilt = 0; lastTime = 0; schedule(); });
    resize();
    return {
      setPair(id) { second = id; schedule(); },
      setProgress(value, isPlaying, source) { progress = value; playing = isPlaying; channel = source; paintCursor(); },
    };
  };
})();
