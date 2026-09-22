// 자체 제작 샘플의 실제 파형과 분석값. 음원은 사용자가 재생할 때만 요청한다.
(function () {
  "use strict";
  const desk = document.getElementById("listen");
  if (!desk) return;
  const $ = (selector) => desk.querySelector(selector);
  const t = (key) => window.i18n ? window.i18n.t("demo." + key) : key;
  const esc = (value) => String(value).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const clamp = (x, low, high) => Math.min(high, Math.max(low, x));
  const audioA = $("#demo-audio-a"), audioB = $("#demo-audio-b");
  const seek = $("#demo-seek"), clock = $("#demo-time"), status = $("#demo-status");
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  let data, surface, variant = "tone", chart = "spectrum", active = null;
  let position = 0, frame = 0, visible = true, requestId = 0;
  const metrics = [
    { key: "tempo_bpm", label: "tempo", digits: 1, unit: " BPM" },
    { key: "energy_rms", label: "energy", digits: 3, unit: "" },
    { key: "brightness", label: "brightness", digits: 0, unit: " Hz" },
    { key: "noisiness", label: "roughness", digits: 3, unit: "" },
    { key: "harmony_ratio", label: "harmony", digits: 2, unit: "" },
    { key: "chroma", label: "chroma", digits: 3, unit: "" },
  ];
  const trackA = () => data.tracks[0];
  const trackB = () => data.tracks.find((track) => track.id === variant);
  const timeText = (seconds) => "0:" + String(Math.floor(seconds)).padStart(2, "0");
  function message(text, error) {
    status.textContent = text;
    status.classList.toggle("sr-only", !error);
    if (error) desk.querySelector(".data-inspector").open = true;
  }

  function paintPosition() {
    if (!data) return;
    if (active && Number.isFinite(active.currentTime)) position = active.currentTime;
    seek.value = position;
    const duration = trackA().duration;
    seek.setAttribute("aria-valuetext", timeText(position) + " / " + timeText(Math.ceil(duration)));
    clock.textContent = timeText(position) + " / " + timeText(Math.ceil(duration));
    desk.querySelectorAll(".demo-playhead").forEach((head) => {
      head.style.transform = "scaleX(" + clamp(position / duration, 0, 1) + ")";
    });
    if (surface) surface.setProgress(position / duration, !!active && !active.paused, active === audioB ? "b" : "a");
  }
  function tick() {
    frame = 0;
    paintPosition();
    if (active && !active.paused && visible && !document.hidden && !reducedMotion.matches) {
      frame = requestAnimationFrame(tick);
    }
  }
  function cancelFrame() { if (frame) cancelAnimationFrame(frame); frame = 0; }
  function syncButtons() {
    [audioA, audioB].forEach((audio, index) => {
      const button = $('[data-demo-play="' + (index ? "b" : "a") + '"]');
      const playing = audio === active && !audio.paused;
      button.classList.toggle("is-playing", playing);
      const key = playing ? (index ? "pauseB" : "pauseA") : (index ? "playB" : "playA");
      button.dataset.i18nAttr = "aria-label:demo." + key;
      button.setAttribute("aria-label", t(key));
    });
  }
  function pause() {
    requestId++;
    if (active) position = active.currentTime || 0;
    audioA.pause(); audioB.pause();
    cancelFrame(); syncButtons(); paintPosition();
  }
  async function play(which) {
    if (!data) return;
    const audio = which === "a" ? audioA : audioB;
    if (active === audio && !audio.paused) { pause(); return; }
    const currentRequest = ++requestId;
    if (active) position = active.currentTime || 0;
    audioA.pause(); audioB.pause();
    const track = which === "a" ? trackA() : trackB();
    if (audio.getAttribute("src") !== track.src) audio.src = track.src;
    if (position >= track.duration - .05) position = 0;
    active = audio;
    audio.volume = .75;
    audio.currentTime = position;
    try {
      await audio.play();
      if (currentRequest !== requestId) return;
      message(t(which === "a" ? "playingA" : "playingB"));
      syncButtons();
      cancelFrame(); tick();
    } catch (error) {
      if (currentRequest !== requestId || error.name === "AbortError") return;
      message(t("playError"), true);
      syncButtons();
    }
  }

  function waveform(track) {
    // Same amplitude scale for both tracks. No random or decorative waveform bars.
    const lines = track.waveform.map((peak, index) => {
      const x = index * 3.5 + 1;
      const height = Math.max(.7, peak * 39);
      return "M" + x.toFixed(1) + " " + (22 - height).toFixed(1) + "v" + (height * 2).toFixed(1);
    }).join("");
    return '<svg viewBox="0 0 505 44" preserveAspectRatio="none"><path d="' + lines + '" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" opacity=".72"/></svg><i class="demo-playhead"></i>';
  }

  function renderChart() {
    if (!data) return;
    const a = trackA(), b = trackB();
    $("#demo-chart").innerHTML = chart === "features" ? featureBars(a, b) : spectrum(a, b);
  }
  function spectrum(a, b) {
    const x0 = 31, width = 466, y0 = 10, height = 104;
    const path = (track) => track.spectrum.map((db, index) => {
      const x = x0 + (index + .5) / track.spectrum.length * width;
      const y = y0 + clamp(-db / 100, 0, 1) * height;
      return (index ? "L" : "M") + x.toFixed(1) + "," + y.toFixed(1);
    }).join(" ");
    let grid = "";
    [0, -40, -80].forEach((db) => {
      const y = y0 + -db / 100 * height;
      grid += '<path class="chart-grid" d="M31 ' + y + 'H497"/><text x="24" y="' + (y + 3) + '" text-anchor="end">' + db + '</text>';
    });
    [40, 100, 500, 2000, 10000].forEach((hz) => {
      const x = x0 + Math.log(hz / 40) / Math.log(10000 / 40) * width;
      grid += '<text x="' + x.toFixed(1) + '" y="136" text-anchor="' + (hz === 40 ? "start" : hz === 10000 ? "end" : "middle") + '">' + (hz >= 1000 ? hz / 1000 + "k" : hz) + ' Hz</text>';
    });
    return '<svg viewBox="0 0 505 142" role="img" aria-label="' + esc(t("spectrumAria")) + '"><title>' + esc(t("spectrumAria")) + '</title>' + grid + '<path class="spectrum-a" d="' + path(a) + '"/><path class="spectrum-b" d="' + path(b) + '"/></svg>';
  }
  function featureBars(a, b) {
    return '<ul class="demo-feature-bars" aria-label="' + esc(t("featuresAria")) + '">' + metrics.slice(0, 4).map((m) => {
      const va = a.summary[m.key], vb = b.summary[m.key], max = Math.max(va, vb, .001);
      return '<li><span>' + esc(t(m.label)) + '</span><span class="measure-pair" aria-hidden="true"><i style="--value:' + (va / max).toFixed(3) + '"></i><i style="--value:' + (vb / max).toFixed(3) + '"></i></span><span class="measure-value">' + va.toFixed(m.digits) + ' / ' + vb.toFixed(m.digits) + '</span></li>';
    }).join("") + '</ul>';
  }
  function render() {
    if (!data) return;
    $("#demo-wave-a").innerHTML = waveform(trackA());
    $("#demo-wave-b").innerHTML = waveform(trackB());
    const nameKey = variant === "tone" ? "toneName" : "rhythmName";
    const subKey = variant === "tone" ? "toneSub" : "rhythmSub";
    const noteKey = variant === "tone" ? "toneNote" : "rhythmNote";
    [["#demo-track-title", nameKey], ["#demo-track-sub", subKey], ["#demo-note", noteKey]].forEach(([selector, key]) => {
      $(selector).dataset.i18n = "demo." + key;
      $(selector).textContent = t(key);
    });
    $("#demo-score").textContent = data.comparisons.find((comparison) => comparison.track === variant).similarityPercent.toFixed(1);
    $("#demo-download-b").href = trackB().src;
    $("#demo-values").innerHTML = '<table><caption class="sr-only">' + esc(t("values")) + '</caption><thead><tr><th scope="col">' + esc(t("measure")) + '</th><th scope="col">A</th><th scope="col">B</th></tr></thead><tbody>' + metrics.map((m) => '<tr><th scope="row">' + esc(t(m.label)) + '</th><td>' + trackA().summary[m.key].toFixed(m.digits) + m.unit + '</td><td>' + trackB().summary[m.key].toFixed(m.digits) + m.unit + '</td></tr>').join("") + '</tbody></table><p>' + esc(t("scaleNote")) + '</p>';
    renderChart(); paintPosition(); syncButtons();
    if (surface) surface.setPair(variant);
  }

  desk.addEventListener("click", (event) => {
    const playButton = event.target.closest("[data-demo-play]");
    if (playButton) { play(playButton.dataset.demoPlay); return; }
    const variantButton = event.target.closest("[data-demo-variant]");
    if (variantButton && variantButton.dataset.demoVariant !== variant) {
      pause(); active = null; position = 0;
      variant = variantButton.dataset.demoVariant;
      desk.querySelectorAll("[data-demo-variant]").forEach((button) => button.setAttribute("aria-pressed", String(button === variantButton)));
      render();
    }
    const chartButton = event.target.closest("[data-demo-chart]");
    if (chartButton) {
      chart = chartButton.dataset.demoChart;
      desk.querySelectorAll("[data-demo-chart]").forEach((button) => button.setAttribute("aria-pressed", String(button === chartButton)));
      renderChart();
    }
  });
  seek.addEventListener("input", () => {
    position = Number(seek.value);
    if (active) active.currentTime = position;
    paintPosition();
  });
  [audioA, audioB].forEach((audio) => {
    audio.addEventListener("timeupdate", () => { if (audio === active && !frame) paintPosition(); });
    audio.addEventListener("ended", () => { cancelFrame(); syncButtons(); paintPosition(); });
    audio.addEventListener("pause", syncButtons);
    audio.addEventListener("error", () => {
      if (audio !== active) return;
      pause(); message(t("playError"), true);
    });
  });
  // Uploaded audio and the two demo tracks must never play over one another.
  document.addEventListener("play", (event) => {
    const source = event.target;
    if (source === audioA || source === audioB) {
      const uploaded = document.getElementById("audio-preview");
      if (uploaded) uploaded.pause();
    } else if (source instanceof HTMLMediaElement) pause();
  }, true);
  document.addEventListener("visibilitychange", () => { if (document.hidden) pause(); });
  window.addEventListener("pagehide", pause);
  if ("IntersectionObserver" in window) new IntersectionObserver((entries) => {
    visible = entries[0].isIntersecting;
    cancelFrame();
    if (visible && active && !active.paused) tick();
  }).observe(desk);
  reducedMotion.addEventListener("change", () => { cancelFrame(); if (active && !active.paused) tick(); });
  window.addEventListener("i18n:change", render);
  const demoAnalyze = document.getElementById("demo-analyze");
  if (demoAnalyze) demoAnalyze.addEventListener("click", async () => {
    if (!data || !window.SoundMatchApp || !window.SoundMatchApp.analyzeFile) return;
    demoAnalyze.disabled = true;
    demoAnalyze.setAttribute("aria-busy", "true");
    try {
      pause();
      const response = await fetch(trackA().src);
      if (!response.ok) throw new Error("sample unavailable");
      const file = new File([await response.blob()], "SoundMatch-Night-Walk.wav", { type: "audio/wav" });
      window.SoundMatchApp.analyzeFile(file);
    } catch (_) {
      message(t("loadError"), true);
    } finally {
      demoAnalyze.disabled = false;
      demoAnalyze.setAttribute("aria-busy", "false");
    }
  });
  fetch("/static/assets/demo/analysis.json").then((response) => {
    if (!response.ok) throw new Error("demo analysis unavailable");
    return response.json();
  }).then((value) => {
    data = value;
    if (window.SoundMatchSurface) surface = window.SoundMatchSurface(data.tracks);
    seek.max = trackA().duration;
    seek.disabled = false;
    desk.querySelectorAll("[data-demo-play]").forEach((button) => { button.disabled = false; });
    render();
  }).catch(() => {
    message(t("loadError"), true);
  });
})();
