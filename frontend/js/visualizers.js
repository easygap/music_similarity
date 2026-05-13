// Visualizers --------------------------------------------------------------
// 1) WaveformBar — decodes a File with Web Audio, renders a static waveform
//    into a <canvas>, and lets the consumer drive a playback cursor.
// 2) renderRadarChart — pure-SVG radar comparing the uploaded track summary
//    against the top match.

(function () {
  // ------------------------------------------------------------ Waveform --
  class WaveformBar {
    constructor(canvas) {
      this.canvas = canvas;
      this.ctx = canvas.getContext("2d");
      this.peaks = null;
      this.duration = 0;
      this._raf = null;
    }

    async load(file) {
      // Decode just enough to render the bars; we don't need samples back.
      const ac = new (window.AudioContext || window.webkitAudioContext)();
      const arrayBuffer = await file.arrayBuffer();
      try {
        const buf = await ac.decodeAudioData(arrayBuffer.slice(0));
        this.duration = buf.duration;
        this.peaks = this._computePeaks(buf, 96);
        this.draw(0);
      } catch (e) {
        // Decoding can fail for exotic codecs in the browser; show flat bars.
        this.peaks = new Float32Array(96);
        this.duration = 0;
        this.draw(0);
      } finally {
        ac.close && ac.close();
      }
    }

    _computePeaks(buf, bins) {
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
      // Normalise so the loudest bar = 1.
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
      if (canvas.width !== Math.floor(w * dpr) || canvas.height !== Math.floor(h * dpr)) {
        canvas.width = Math.floor(w * dpr);
        canvas.height = Math.floor(h * dpr);
      }
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, w, h);

      if (!peaks || !peaks.length) return;

      const style = getComputedStyle(canvas);
      const baseColor = style.getPropertyValue("--wave-base").trim() || "rgba(255,255,255,0.18)";
      const playedColor = style.getPropertyValue("--wave-played").trim() || "#7c5cff";

      const bars = peaks.length;
      const gap = 2;
      const barWidth = Math.max(1, (w - gap * (bars - 1)) / bars);
      for (let i = 0; i < bars; i++) {
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

  // ------------------------------------------------------------ Radar -----
  // Inputs: { axes: [{ label, query01, match01 }, ...] }
  // Each `query01` / `match01` is normalised to [0, 1] by the caller.
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
      const angle = -Math.PI / 2 + i * step;
      const r = radius * value + offset;
      return [cx + r * Math.cos(angle), cy + r * Math.sin(angle)];
    }

    function polygon(values) {
      return values.map((v, i) => point(v, i).join(",")).join(" ");
    }

    const rings = [0.25, 0.5, 0.75, 1].map((ratio) => {
      const pts = axes.map((_, i) => point(ratio, i).join(",")).join(" ");
      return `<polygon points="${pts}" class="radar-ring"></polygon>`;
    });

    const spokes = axes
      .map((_, i) => {
        const [x, y] = point(1, i);
        return `<line x1="${cx}" y1="${cy}" x2="${x}" y2="${y}" class="radar-spoke"></line>`;
      })
      .join("");

    const labels = axes
      .map((ax, i) => {
        const [x, y] = point(1, i, 16);
        const anchor = x < cx - 4 ? "end" : x > cx + 4 ? "start" : "middle";
        return `<text x="${x}" y="${y}" class="radar-label" text-anchor="${anchor}" dominant-baseline="middle">${escapeXml(ax.label)}</text>`;
      })
      .join("");

    const queryPts = polygon(axes.map((a) => clamp01(a.query01)));
    const matchPts = polygon(axes.map((a) => clamp01(a.match01)));

    target.innerHTML = `
      <svg viewBox="0 0 ${w} ${h}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Radar chart comparing your upload with the top match">
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

  // Normalise a query/match feature against a "typical" range so the radar
  // has consistent axes regardless of absolute units.
  function normalise(value, axis) {
    const v = Number(value);
    if (!isFinite(v)) return 0;
    const { min, max } = axis;
    if (max === min) return 0.5;
    return clamp01((v - min) / (max - min));
  }

  function radarFromSummaries(summary, matchSummary) {
    // Reasonable display ranges for a music corpus.
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
