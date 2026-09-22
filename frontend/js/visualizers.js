// 시각화 모듈 --------------------------------------------------------------
// 1) WaveformBar
//    - 입력 파일을 Web Audio API 로 디코딩한 뒤 peak 96개 짜리 정규화된
//      파형 막대를 <canvas> 에 직접 그린다.
//    - 외부에서 setCursor(0..1) 를 호출하면 그 비율만큼 색이 채워진다.
// 2) renderRadarChart
//    - 의존성 없는 순수 SVG. 1위 매칭 vs 업로드 비교용 6축 레이더.

(function () {
  // -------------------------------------------------------- 파형 --------
  class WaveformBar {
    constructor(canvas) {
      this.canvas = canvas;
      this.ctx = canvas.getContext("2d");
      this.peaks = null;
      this.duration = 0;
      this._version = 0;
      this._context = null;
      this._destroyed = false;
      this._progress = 0;
      this._resize = typeof ResizeObserver === "function" ? new ResizeObserver(() => this.draw(this._progress)) : null;
      if (this._resize) this._resize.observe(canvas);
    }

    async load(file) {
      if (this._destroyed) return;
      const version = ++this._version;
      this._closeContext(this._context);
      let ac;
      try {
        const arrayBuffer = await file.arrayBuffer();
        if (this._destroyed || version !== this._version) return;
        ac = new (window.AudioContext || window.webkitAudioContext)();
        this._context = ac;
        // decodeAudioData에 원본 버퍼를 넘긴다. 같은 파일 크기의 복사본은 필요 없다.
        const buf = await ac.decodeAudioData(arrayBuffer);
        if (this._destroyed || version !== this._version) return;
        this.duration = buf.duration;
        this.peaks = this._computePeaks(buf, 96);
        this.draw(0);
      } catch (e) {
        if (this._destroyed || version !== this._version) return;
        // 일부 코덱은 브라우저 디코딩이 안 되는 경우가 있다(예: m4a 일부 변종).
        // 그 때는 평탄한 막대로 fallback.
        this.peaks = new Float32Array(96);
        this.duration = 0;
        this.draw(0);
      } finally {
        this._closeContext(ac);
      }
    }

    _closeContext(context) {
      if (!context) return;
      if (this._context === context) this._context = null;
      if (context.state !== "closed") {
        try { Promise.resolve(context.close()).catch(() => {}); } catch (_) {}
      }
    }

    _computePeaks(buf, bins) {
      // 어느 채널에만 소리가 있어도 표시하고, 마지막 구간까지 빠짐없이 읽는다.
      const channels = Array.from({ length: buf.numberOfChannels }, (_, i) => buf.getChannelData(i));
      const length = channels[0].length;
      bins = Math.min(bins, length);
      const peaks = new Float32Array(bins);
      for (let i = 0; i < bins; i++) {
        let max = 0;
        const start = Math.floor(i * length / bins);
        const end = Math.floor((i + 1) * length / bins);
        for (const ch of channels) {
          for (let j = start; j < end; j++) {
            const v = Math.abs(ch[j]);
            if (v > max) max = v;
          }
        }
        peaks[i] = max;
      }
      // 가장 큰 막대를 1.0 으로 정규화. 다이내믹 레인지가 작은 곡도 잘 보이게.
      let m = 0;
      for (const p of peaks) if (p > m) m = p;
      if (m > 0) for (let i = 0; i < peaks.length; i++) peaks[i] /= m;
      return peaks;
    }

    setCursor(progress01) {
      this.draw(Math.max(0, Math.min(1, progress01 || 0)));
    }

    draw(progress) {
      if (this._destroyed) return;
      this._progress = Math.max(0, Math.min(1, progress || 0));
      const { canvas, ctx, peaks } = this;
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      const w = canvas.clientWidth;
      const h = canvas.clientHeight;
      if (!ctx || !w || !h) return;
      // 고해상도 디스플레이를 위해 캔버스 실제 픽셀 수를 맞춰준다.
      if (canvas.width !== Math.floor(w * dpr) || canvas.height !== Math.floor(h * dpr)) {
        canvas.width = Math.floor(w * dpr);
        canvas.height = Math.floor(h * dpr);
      }
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, w, h);

      if (!peaks || !peaks.length) return;

      // 테마에 따라 색이 바뀌도록 CSS 변수에서 색을 읽는다.
      const style = getComputedStyle(canvas);
      const baseColor = style.getPropertyValue("--wave-base").trim() || "rgba(255,255,255,0.18)";
      const playedColor = style.getPropertyValue("--wave-played").trim() || "#004cff";

      const bars = Math.min(peaks.length, Math.max(1, Math.floor(w / 3)));
      const gap = bars > 1 ? 2 : 0;
      const barWidth = (w - gap * (bars - 1)) / bars;
      for (let i = 0; i < bars; i++) {
        let peak = 0;
        for (let j = Math.floor(i * peaks.length / bars); j < Math.floor((i + 1) * peaks.length / bars); j++) {
          peak = Math.max(peak, peaks[j]);
        }
        // peak 가 0이어도 최소 두께를 줘서 막대 자리가 보이게 한다.
        const barHeight = Math.min(h, Math.max(2, peak * h * 0.86));
        const x = i * (barWidth + gap);
        const y = (h - barHeight) / 2;
        const playedThreshold = this._progress * bars;
        ctx.fillStyle = i < playedThreshold ? playedColor : baseColor;
        const r = Math.min(barWidth / 2, 3);
        roundRect(ctx, x, y, barWidth, barHeight, r);
      }
    }

    destroy() {
      this._destroyed = true;
      this._version++;
      if (this._resize) this._resize.disconnect();
      this._closeContext(this._context);
      this.peaks = null;
    }
  }

  function roundRect(ctx, x, y, w, h, r) {
    // 캔버스에 둥근 모서리 사각형을 그린다. 따로 라이브러리 안 쓰려고 직접 구현.
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.lineTo(x + w - r, y);
    ctx.quadraticCurveTo(x + w, y, x + w, y + r);
    ctx.lineTo(x + w, y + h - r);
    ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
    ctx.lineTo(x + r, y + h);
    ctx.quadraticCurveTo(x, y + h, x, y + h - r);
    ctx.lineTo(x, y + r);
    ctx.quadraticCurveTo(x, y, x + r, y);
    ctx.closePath();
    ctx.fill();
  }

  // -------------------------------------------------------- 레이더 -----
  // 입력 형식: { axes: [{ label, query01, match01 }, ...] }
  // query01 / match01 은 [0, 1] 정규화 값.
  function measureRadarLabels(target, axes) {
    const canvas = document.createElement("canvas");
    const ctx = canvas.getContext("2d");
    if (!ctx) return axes.map((axis) => Array.from(String(axis.label || "")).length * 6.2);

    const fontFamily = getComputedStyle(target).fontFamily || "sans-serif";
    ctx.font = `11px ${fontFamily}`;
    return axes.map((axis) => ctx.measureText(String(axis.label || "")).width);
  }

  function renderRadarChart(target, data) {
    if (!target) return;
    const axes = (data && data.axes) || [];
    if (!axes.length) {
      target.innerHTML = "";
      return;
    }
    const w = target.clientWidth || 320;
    const h = Math.min(w, 360);
    const cx = w / 2;
    const cy = h / 2;
    const radius = Math.min(w, h) * 0.4;

    const n = axes.length;
    const step = (Math.PI * 2) / n;

    function point(value, i, offset = 0) {
      // 각 축의 i번째 점 좌표. 12시 방향(-π/2) 부터 시계방향으로 배치.
      const angle = -Math.PI / 2 + i * step;
      const r = radius * value + offset;
      return [cx + r * Math.cos(angle), cy + r * Math.sin(angle)];
    }

    function polygon(values) {
      return values.map((v, i) => point(v, i).join(",")).join(" ");
    }

    // 동심원(폴리곤) 그리드. 4단계로 충분.
    const rings = [0.25, 0.5, 0.75, 1].map((ratio) => {
      const pts = axes.map((_, i) => point(ratio, i).join(",")).join(" ");
      return `<polygon points="${pts}" class="radar-ring"></polygon>`;
    });

    // 각 축 방향 보조선.
    const spokes = axes
      .map((_, i) => {
        const [x, y] = point(1, i);
        return `<line x1="${cx}" y1="${cy}" x2="${x}" y2="${y}" class="radar-spoke"></line>`;
      })
      .join("");

    const labelWidths = measureRadarLabels(target, axes);
    const labelItems = axes.map((ax, i) => {
      // 라벨은 축 끝점에서 16px 만큼 바깥쪽으로 둔다. 실제 글자 폭까지 계산해
      // viewBox 를 넓혀야 모바일에서도 좌우 라벨이 SVG 경계에 잘리지 않는다.
      const [x, y] = point(1, i, 16);
      const anchor = x < cx - 4 ? "end" : x > cx + 4 ? "start" : "middle";
      const width = labelWidths[i] || 0;
      const left = anchor === "end" ? x - width : anchor === "middle" ? x - width / 2 : x;
      const right = anchor === "start" ? x + width : anchor === "middle" ? x + width / 2 : x;
      return { ax, x, y, anchor, left, right };
    });
    const labelPadding = 4;
    const labelHalfHeight = 6;
    const minLabelX = Math.min(...labelItems.map((item) => item.left));
    const maxLabelX = Math.max(...labelItems.map((item) => item.right));
    const minLabelY = Math.min(...labelItems.map((item) => item.y - labelHalfHeight));
    const maxLabelY = Math.max(...labelItems.map((item) => item.y + labelHalfHeight));
    const horizontalGutter = Math.ceil(
      Math.max(0, -minLabelX, maxLabelX - w) + labelPadding,
    );
    const verticalGutter = Math.ceil(
      Math.max(0, -minLabelY, maxLabelY - h) + labelPadding,
    );
    const labels = labelItems
      .map(
        ({ ax, x, y, anchor }) =>
          `<text x="${x}" y="${y}" class="radar-label" text-anchor="${anchor}" dominant-baseline="middle">${escapeXml(ax.label)}</text>`,
      )
      .join("");

    const queryPts = polygon(axes.map((a) => clamp01(a.query01)));
    const matchPts = polygon(axes.map((a) => clamp01(a.match01)));

    const ariaLabel =
      (data && data.ariaLabel) ||
      "업로드한 곡과 1위 매칭의 오디오 지문을 비교하는 레이더 차트";
    target.innerHTML = `
      <svg viewBox="${-horizontalGutter} ${-verticalGutter} ${w + horizontalGutter * 2} ${h + verticalGutter * 2}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="${escapeXml(ariaLabel)}">
        <g>
          ${rings.join("")}
          ${spokes}
        </g>
        <polygon points="${matchPts}" class="radar-shape radar-match"></polygon>
        <polygon points="${queryPts}" class="radar-shape radar-query"></polygon>
        ${labels}
      </svg>
    `;
  }

  function clamp01(v) {
    if (v == null || !isFinite(v)) return 0;
    return Math.max(0, Math.min(1, v));
  }

  function escapeXml(s) {
    return String(s ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&apos;");
  }

  // 특성별 절대 단위가 제각각이라(템포는 BPM, 밝기는 Hz...) 그대로 그리면
  // 축이 한쪽으로 쏠린다. 음악 카탈로그에서 "일반적인 범위" 를 잡아 [0, 1] 로 매핑.
  function normalise(value, axis) {
    const v = Number(value);
    if (!isFinite(v)) return 0;
    const { min, max } = axis;
    if (max === min) return 0.5;
    return clamp01((v - min) / (max - min));
  }

  function radarFromSummaries(summary, matchSummary, options = {}) {
    // 축 정의 + 표시 범위. 정상 곡들이 보통 들어오는 구간을 경험적으로 설정.
    const axes = [
      { key: "tempo_bpm", label: "Tempo", min: 60, max: 200 },
      { key: "energy_rms", label: "Energy", min: 0, max: 0.5 },
      { key: "brightness", label: "Brightness", min: 800, max: 6000 },
      { key: "noisiness", label: "Roughness", min: 0.02, max: 0.25 },
      { key: "harmony_ratio", label: "Harmony", min: 0, max: 4 },
      { key: "chroma", label: "Chroma", min: 0.1, max: 0.6 },
    ];
    return {
      ariaLabel: options.ariaLabel,
      axes: axes.map((a) => ({
        label: (options.labels && options.labels[a.key]) || a.label,
        query01: normalise(summary && summary[a.key], a),
        match01: normalise(matchSummary && matchSummary[a.key], a),
      })),
    };
  }

  window.SoundMatchVisualizers = {
    WaveformBar,
    renderRadarChart,
    radarFromSummaries,
  };
})();
