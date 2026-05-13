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
      this._raf = null;
    }

    async load(file) {
      // 디코딩이 끝나면 raw samples 는 필요 없어서 즉시 컨텍스트를 닫는다.
      const ac = new (window.AudioContext || window.webkitAudioContext)();
      const arrayBuffer = await file.arrayBuffer();
      try {
        const buf = await ac.decodeAudioData(arrayBuffer.slice(0));
        this.duration = buf.duration;
        this.peaks = this._computePeaks(buf, 96);
        this.draw(0);
      } catch (e) {
        // 일부 코덱은 브라우저 디코딩이 안 되는 경우가 있다(예: m4a 일부 변종).
        // 그 때는 평탄한 막대로 fallback.
        this.peaks = new Float32Array(96);
        this.duration = 0;
        this.draw(0);
      } finally {
        ac.close && ac.close();
      }
    }

    _computePeaks(buf, bins) {
      // 모노 첫 채널만 가지고 bins 구간으로 잘라 각 구간의 최대 절댓값을 뽑는다.
      // (스테레오 평균을 내봐야 시각적으로 큰 차이는 없음)
      const ch = buf.getChannelData(0);
      const block = Math.floor(ch.length / bins);
      const peaks = new Float32Array(bins);
      for (let i = 0; i < bins; i++) {
        let max = 0;
        const start = i * block;
        const end = start + block;
        for (let j = start; j < end; j++) {
          const v = Math.abs(ch[j] || 0);
          if (v > max) max = v;
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
      const { canvas, ctx, peaks } = this;
      const dpr = window.devicePixelRatio || 1;
      const w = canvas.clientWidth;
      const h = canvas.clientHeight;
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
      const playedColor = style.getPropertyValue("--wave-played").trim() || "#7c5cff";

      const bars = peaks.length;
      const gap = 2;
      const barWidth = Math.max(1, (w - gap * (bars - 1)) / bars);
      for (let i = 0; i < bars; i++) {
        // peak 가 0이어도 최소 두께를 줘서 막대 자리가 보이게 한다.
        const peak = peaks[i] || 0.02;
        const barHeight = Math.max(2, peak * h * 0.86);
        const x = i * (barWidth + gap);
        const y = (h - barHeight) / 2;
        const playedThreshold = progress * bars;
        ctx.fillStyle = i < playedThreshold ? playedColor : baseColor;
        const r = Math.min(barWidth / 2, 3);
        roundRect(ctx, x, y, barWidth, barHeight, r);
      }
    }

    destroy() {
      if (this._raf) cancelAnimationFrame(this._raf);
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
  function renderRadarChart(target, data) {
    if (!target) return;
    const axes = (data && data.axes) || [];
    if (!axes.length) {
      target.innerHTML = "";
      return;
    }
    const w = target.clientWidth || 320;
    const h = Math.min(w, 320);
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

    const labels = axes
      .map((ax, i) => {
        // 라벨은 축 끝점에서 16px 만큼 바깥쪽으로.
        const [x, y] = point(1, i, 16);
        const anchor = x < cx - 4 ? "end" : x > cx + 4 ? "start" : "middle";
        return `<text x="${x}" y="${y}" class="radar-label" text-anchor="${anchor}" dominant-baseline="middle">${escapeXml(ax.label)}</text>`;
      })
      .join("");

    const queryPts = polygon(axes.map((a) => clamp01(a.query01)));
    const matchPts = polygon(axes.map((a) => clamp01(a.match01)));

    target.innerHTML = `
      <svg viewBox="0 0 ${w} ${h}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="업로드한 곡과 1위 매칭의 오디오 지문을 비교하는 레이더 차트">
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

  function radarFromSummaries(summary, matchSummary) {
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
      axes: axes.map((a) => ({
        label: a.label,
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
