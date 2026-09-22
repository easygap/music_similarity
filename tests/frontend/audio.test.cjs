const { test } = require("node:test");
const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const { join } = require("node:path");
const vm = require("node:vm");

const source = readFileSync(join(__dirname, "../../frontend/js/visualizers.js"), "utf8");
const flush = () => new Promise(setImmediate);
const deferred = () => {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
};
const decoded = (channels) => ({
  duration: 9, numberOfChannels: channels.length,
  getChannelData: (index) => Float32Array.from(channels[index]),
});

function fixture(width = 180) {
  const contexts = [], observers = [], points = [];
  const ctx = {
    clears: 0,
    setTransform() {}, clearRect() { this.clears++; }, beginPath() {}, closePath() {}, fill() {},
    moveTo(x, y) { points.push([x, y]); }, lineTo(x, y) { points.push([x, y]); },
    quadraticCurveTo(x, y, x2, y2) { points.push([x, y], [x2, y2]); },
  };
  const canvas = { clientWidth: width, clientHeight: 64, width: 0, height: 0, getContext: () => ctx };
  class AudioContext {
    constructor() { this.state = "running"; this.pending = deferred(); contexts.push(this); }
    decodeAudioData(buffer) { this.buffer = buffer; return this.pending.promise; }
    close() { this.state = "closed"; return Promise.resolve(); }
  }
  class ResizeObserver {
    constructor(callback) { this.callback = callback; observers.push(this); }
    observe() {} disconnect() { this.disconnected = true; }
  }
  const window = { AudioContext, devicePixelRatio: 3 };
  vm.runInNewContext(source, { window, ResizeObserver, getComputedStyle: () => ({ getPropertyValue: () => "" }) });
  const waveform = new window.SoundMatchVisualizers.WaveformBar(canvas);
  return { waveform, canvas, ctx, contexts, observers, points };
}

test("narrow waveforms fit the canvas and retain audio from the right channel", async () => {
  const f = fixture(127);
  const left = Array(101).fill(0), right = Array(101).fill(0);
  right[100] = .9;
  const bytes = new ArrayBuffer(32);
  const pending = f.waveform.load({ arrayBuffer: async () => bytes });
  await flush();
  assert.equal(f.contexts[0].buffer, bytes, "decoding must not duplicate the file buffer");
  f.contexts[0].pending.resolve(decoded([left, right]));
  await pending;
  assert.equal(f.waveform.peaks.at(-1), 1, "the last sample must not be dropped");
  assert.ok(f.points.every(([x, y]) => x >= 0 && x <= 127.000001 && y >= 0 && y <= 64));
  assert.equal(f.canvas.width, 254, "pixel density is capped at 2");
  assert.equal(f.contexts[0].state, "closed");
});

test("audio shorter than 96 samples still produces a visible waveform", () => {
  const { waveform } = fixture();
  assert.deepEqual(Array.from(waveform._computePeaks(decoded([[0, .5, 1]]), 96)), [0, .5, 1]);
});

test("reset during decoding releases resources and cannot repaint an old waveform", async () => {
  const f = fixture();
  const pending = f.waveform.load({ arrayBuffer: async () => new ArrayBuffer(8) });
  await flush();
  f.waveform.destroy();
  assert.equal(f.contexts[0].state, "closed");
  assert.equal(f.observers[0].disconnected, true);
  f.contexts[0].pending.resolve(decoded([[1, 0, 1]]));
  await pending;
  assert.equal(f.waveform.peaks, null);
  assert.equal(f.ctx.clears, 0);
});

test("reset while the file is being read never opens an audio context", async () => {
  const f = fixture(), reading = deferred();
  const pending = f.waveform.load({ arrayBuffer: () => reading.promise });
  f.waveform.destroy();
  reading.resolve(new ArrayBuffer(8));
  await pending;
  assert.equal(f.contexts.length, 0);
});

test("an older decode cannot replace the waveform from a newer file", async () => {
  const f = fixture();
  const old = f.waveform.load({ arrayBuffer: async () => new ArrayBuffer(8) });
  await flush();
  const recent = f.waveform.load({ arrayBuffer: async () => new ArrayBuffer(16) });
  await flush();
  f.contexts[1].pending.resolve(decoded([[0, 1]]));
  await recent;
  f.contexts[0].pending.resolve(decoded([[1, 0]]));
  await old;
  assert.deepEqual(Array.from(f.waveform.peaks), [0, 1]);
  assert.ok(f.contexts.every((context) => context.state === "closed"));
});

test("decode and file read failures leave no open audio context", async () => {
  const f = fixture();
  const pending = f.waveform.load({ arrayBuffer: async () => new ArrayBuffer(8) });
  await flush();
  f.contexts[0].pending.reject(new Error("unsupported codec"));
  await pending;
  assert.equal(f.contexts[0].state, "closed");
  await f.waveform.load({ arrayBuffer: async () => { throw new Error("file unavailable"); } });
  assert.equal(f.contexts.length, 1);
  assert.equal(f.waveform.duration, 0);
});

test("paused waveforms resize without a playback loop and stop observing after reset", () => {
  const f = fixture(300);
  f.waveform.peaks = new Float32Array(96).fill(.5);
  f.waveform.draw(.4);
  f.canvas.clientWidth = 80;
  f.points.length = 0;
  f.observers[0].callback();
  assert.equal(f.waveform._progress, .4);
  assert.ok(f.points.every(([x]) => x >= 0 && x <= 80.000001));
  f.waveform.destroy();
  const clears = f.ctx.clears;
  f.observers[0].callback();
  assert.equal(f.ctx.clears, clears);
});
