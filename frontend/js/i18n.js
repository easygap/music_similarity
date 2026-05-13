// Tiny i18n layer ----------------------------------------------------------
// Loads translations and exposes window.i18n.t(key) for static and dynamic
// content. Persists the chosen language in localStorage.

(function () {
  const STORAGE_KEY = "soundmatch.lang";
  const FALLBACK = "ko";

  const dict = {
    ko: {
      nav: { how: "사용법", features: "기능", github: "GitHub" },
      hero: {
        eyebrow: "Sklearn · librosa · FastAPI · WebAudio",
        title: "업로드한 음악과 <span class=\"grad\">가장 닮은 곡</span>을<br/>AI가 찾아드립니다.",
        lede: "파일 하나만 올리면 60초 안에 끝납니다. 음색·템포·리듬·MFCC 등 <strong>58가지 오디오 특성</strong>을 추출해 코사인 유사도로 가장 닮은 곡 순위와 <strong>닮은 이유</strong>를 알려드려요.",
        statCatalogLabel: "분석 가능한 곡",
        statFeaturesLabel: "추출 특성 수",
        statTimeLabel: "평균 분석 시간",
      },
      upload: {
        title: "지금 분석해보기",
        subtitle: ".mp3 · .wav · .flac · .ogg · .m4a (25MB 이하)",
        dropTitle: "음악 파일을 여기에 드래그하거나 클릭",
        dropHint: "최대 30초가 분석에 사용됩니다.",
        topNLabel: "찾을 곡 수",
        topNOption: (n) => `상위 ${n}곡`,
        submit: "유사한 곡 찾기",
        privacy:
          "업로드된 음원은 분석이 끝나는 즉시 서버에서 자동 삭제됩니다. 학습이나 카탈로그에 사용되지 않습니다.",
        validation: {
          tooBig: (mb) => `파일이 너무 큽니다. 최대 ${mb}MB까지 업로드 가능합니다.`,
          badType: "지원하지 않는 오디오 형식입니다. (.mp3 .wav .flac .ogg .m4a)",
        },
      },
      loading: {
        title: "오디오 특성을 추출하는 중…",
        elapsed: (s) => `${s}초 경과`,
        late: "조금만 더 기다려주세요. 큰 파일은 시간이 더 걸릴 수 있어요.",
        steps: [
          "librosa · 오디오 디코딩",
          "RMS · BPM · 제로 크로싱 추출",
          "스펙트럴 센트로이드 · 롤오프 · 대역폭 계산",
          "20차원 MFCC 계산",
          "StandardScaler · 정규화",
          "cosine_similarity · 카탈로그 비교",
          "닮은 이유 분석 중",
        ],
      },
      error: {
        title: "분석에 실패했습니다.",
        retry: "다시 시도",
        rateLimit: "요청이 너무 잦습니다. 잠시 후 다시 시도해주세요.",
      },
      results: {
        title: "분석 결과",
        subtitlePrefix: "카탈로그",
        subtitleSongs: "곡 비교 · 총",
        subtitleSeconds: "초 소요",
        newAnalysis: "새 음악 분석",
        share: "결과 공유",
        copyLink: "링크 복사",
        copied: "복사됨!",
        exportJson: "JSON 다운로드",
        emptyTitle: "유사한 곡을 찾지 못했습니다.",
        emptyHint: "다른 곡으로 다시 시도해보세요.",
        uploadedTrackTitle: "업로드한 음원",
        uploadedTrackSub: "분석에 사용된 첫 30초가 동일하게 재생됩니다.",
        radarTitle: "오디오 지문 비교 (1위 매칭과)",
        radarLegendQuery: "업로드한 곡",
        radarLegendMatch: "Top 1 매칭",
        hitRankUnit: "위",
        hitSimilarityLabel: "유사도",
        groupMatchPrefix: "match",
      },
      history: {
        title: "최근 분석",
        empty: "아직 분석한 기록이 없어요.",
        clear: "기록 지우기",
        confirm: "히스토리를 모두 지울까요?",
      },
      summary: {
        tempo: "Tempo",
        energy: "에너지 (RMS)",
        brightness: "밝기",
        noisiness: "거친 정도",
        harmony: "화성/타악기 비율",
        chroma: "크로마",
      },
      info: {
        howTitle: "어떻게 동작하나요?",
        step1Title: "오디오 특성 추출",
        step1Body:
          "librosa가 업로드된 곡에서 RMS 에너지, BPM, 스펙트럴 센트로이드, 제로 크로싱, 크로마, 20차원 MFCC 등 <strong>58개 특성</strong>을 뽑아냅니다.",
        step2Title: "표준화 + 코사인 유사도",
        step2Body:
          "sklearn의 <code>StandardScaler</code>로 정규화한 뒤 <code>cosine_similarity</code>로 카탈로그 전곡과의 유사도를 계산합니다.",
        step3Title: "닮은 이유 설명",
        step3Body:
          "특성별 거리(z-score)를 그룹화해 <strong>음색·템포·리듬·화성</strong> 중 어디가 닮았는지 한국어 문장으로 풀어드립니다.",
        featuresTitle: "SoundMatch가 분석하는 항목",
      },
      footer: {
        notice:
          "서버에 음원을 영구 저장하지 않습니다. 분석 결과는 학술/취미 용도로만 사용해주세요.",
        repoLink: "GitHub",
        tagline: "졸업작품에서 출발해, 시중 서비스급으로 끝까지 다듬은 프로젝트",
      },
      controls: {
        themeToggle: "테마 전환",
        langToggle: "Language: English",
      },
    },
    en: {
      nav: { how: "How it works", features: "Features", github: "GitHub" },
      hero: {
        eyebrow: "Sklearn · librosa · FastAPI · WebAudio",
        title: "Find the songs <span class=\"grad\">most similar</span> to yours,<br/>powered by AI.",
        lede: "Drop an audio file and we extract <strong>58 acoustic features</strong> with librosa, rank the closest matches with cosine similarity, and explain <strong>why</strong> each match sounds like yours.",
        statCatalogLabel: "Catalog songs",
        statFeaturesLabel: "Audio features",
        statTimeLabel: "Avg. analysis time",
      },
      upload: {
        title: "Try it now",
        subtitle: ".mp3 · .wav · .flac · .ogg · .m4a (up to 25MB)",
        dropTitle: "Drop a music file here, or click to choose",
        dropHint: "The first 30 seconds are used for analysis.",
        topNLabel: "Match count",
        topNOption: (n) => `Top ${n}`,
        submit: "Find similar tracks",
        privacy:
          "Uploads are deleted from the server immediately after analysis. We never train models or extend the catalog with your audio.",
        validation: {
          tooBig: (mb) => `File is too large. The maximum size is ${mb}MB.`,
          badType: "Unsupported audio format. (.mp3 .wav .flac .ogg .m4a)",
        },
      },
      loading: {
        title: "Extracting audio features…",
        elapsed: (s) => `${s}s elapsed`,
        late: "Hang tight — large files take a little longer.",
        steps: [
          "librosa · decoding audio",
          "RMS · BPM · zero crossings",
          "Spectral centroid · rolloff · bandwidth",
          "20-dim MFCC",
          "StandardScaler · normalization",
          "cosine_similarity · comparing the catalog",
          "Analysing similarity reasons",
        ],
      },
      error: {
        title: "Analysis failed.",
        retry: "Try again",
        rateLimit: "Too many requests. Please try again shortly.",
      },
      results: {
        title: "Results",
        subtitlePrefix: "Compared against",
        subtitleSongs: "tracks ·",
        subtitleSeconds: "s total",
        newAnalysis: "Analyze another",
        share: "Share",
        copyLink: "Copy link",
        copied: "Copied!",
        exportJson: "Download JSON",
        emptyTitle: "No similar songs found.",
        emptyHint: "Try a different file.",
        uploadedTrackTitle: "Your upload",
        uploadedTrackSub: "Same first 30 seconds used by the analyzer.",
        radarTitle: "Acoustic fingerprint vs. top match",
        radarLegendQuery: "Your upload",
        radarLegendMatch: "Top match",
        hitRankUnit: "",
        hitSimilarityLabel: "similarity",
        groupMatchPrefix: "match",
      },
      history: {
        title: "Recent analyses",
        empty: "No analyses yet.",
        clear: "Clear history",
        confirm: "Clear all history?",
      },
      summary: {
        tempo: "Tempo",
        energy: "Energy (RMS)",
        brightness: "Brightness",
        noisiness: "Roughness",
        harmony: "Harmony/Percussive ratio",
        chroma: "Chroma",
      },
      info: {
        howTitle: "How does it work?",
        step1Title: "Feature extraction",
        step1Body:
          "librosa extracts <strong>58 features</strong> from your upload: RMS energy, BPM, spectral centroid/rolloff/bandwidth, zero crossings, chroma and 20-dim MFCC.",
        step2Title: "Standardize + cosine",
        step2Body:
          "Features are normalized with sklearn's <code>StandardScaler</code>, then ranked against every catalog track via <code>cosine_similarity</code>.",
        step3Title: "Reason explanations",
        step3Body:
          "Per-feature distances (z-scores) are grouped into musical concepts — <strong>timbre, tempo, rhythm, harmony</strong> — and turned into plain sentences.",
        featuresTitle: "Audio features extracted",
      },
      footer: {
        notice:
          "No audio is permanently stored. Results are for academic / personal use.",
        repoLink: "GitHub",
        tagline: "Started as a capstone project, polished into a production-ready service.",
      },
      controls: {
        themeToggle: "Toggle theme",
        langToggle: "Language: 한국어",
      },
    },
  };

  function detectInitial() {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored && dict[stored]) return stored;
    const nav = (navigator.language || FALLBACK).toLowerCase();
    if (nav.startsWith("ko")) return "ko";
    if (nav.startsWith("en")) return "en";
    return FALLBACK;
  }

  let current = detectInitial();

  function get(path) {
    const parts = path.split(".");
    let cur = dict[current];
    for (const p of parts) {
      if (cur == null) return null;
      cur = cur[p];
    }
    if (cur == null && current !== FALLBACK) {
      let cur2 = dict[FALLBACK];
      for (const p of parts) {
        if (cur2 == null) return null;
        cur2 = cur2[p];
      }
      return cur2;
    }
    return cur;
  }

  function t(key, ...args) {
    const v = get(key);
    if (typeof v === "function") return v(...args);
    return v == null ? key : v;
  }

  function lang() {
    return current;
  }

  function setLang(next) {
    if (!dict[next]) return;
    current = next;
    localStorage.setItem(STORAGE_KEY, next);
    document.documentElement.setAttribute("lang", next);
    apply();
    window.dispatchEvent(new CustomEvent("i18n:change", { detail: { lang: next } }));
  }

  function toggle() {
    setLang(current === "ko" ? "en" : "ko");
  }

  function apply(root = document) {
    // data-i18n="key" -> textContent
    root.querySelectorAll("[data-i18n]").forEach((el) => {
      const v = get(el.dataset.i18n);
      if (typeof v === "string") {
        if (el.dataset.i18nHtml !== undefined) {
          el.innerHTML = v;
        } else {
          el.textContent = v;
        }
      }
    });
    // data-i18n-attr="aria-label:key,placeholder:key2"
    root.querySelectorAll("[data-i18n-attr]").forEach((el) => {
      const spec = el.dataset.i18nAttr;
      spec.split(",").forEach((pair) => {
        const [attr, key] = pair.split(":").map((s) => s.trim());
        const v = get(key);
        if (typeof v === "string") el.setAttribute(attr, v);
      });
    });
  }

  window.i18n = { t, lang, setLang, toggle, apply };

  // Apply on first paint if DOM is already ready, else on DOMContentLoaded.
  if (document.readyState !== "loading") {
    apply();
    document.documentElement.setAttribute("lang", current);
  } else {
    document.addEventListener("DOMContentLoaded", () => {
      apply();
      document.documentElement.setAttribute("lang", current);
    });
  }
})();
