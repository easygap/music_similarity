// 간단한 i18n 레이어 ------------------------------------------------------
// translations 사전을 들고 있다가 window.i18n.t(key) 로 호출하면 현재 언어의
// 문자열을 돌려준다. 사용자가 고른 언어는 localStorage 에 저장해서 새로고침
// 이후에도 유지.

(function () {
  const STORAGE_KEY = "soundmatch.lang";
  const FALLBACK = "ko";

  const dict = {
    ko: {
      nav: { how: "사용법", features: "기능", compare: "비교", catalog: "카탈로그", github: "GitHub" },
      hero: {
        eyebrow: "Sklearn · librosa · FastAPI · WebAudio",
        title: "업로드한 음악과 <span class=\"grad\">가장 닮은 곡</span>을<br/>AI가 찾아드립니다.",
        lede: "파일 하나만 올리면 60초 안에 끝납니다. 음색·템포·리듬·MFCC 등 <strong>58가지 오디오 특성</strong>을 추출해 코사인 유사도로 가장 닮은 곡 순위와 <strong>닮은 이유</strong>를 알려드려요.",
        statCatalogLabel: "분석 가능한 곡",
        statFeaturesLabel: "추출 특성 수",
        statTimeLabel: "평균 분석 시간",
        catalogFresh: (date) => `최근 갱신 · ${date}`,
        totalAnalyses: (n) => `지금까지 ${n}회 분석된 사이트`,
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
        leaveWarn: "분석이 진행 중입니다. 페이지를 떠나면 다시 처음부터 분석해야 합니다.",
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
        globalToast: "문제가 발생했어요. 새로고침 후 다시 시도해주세요.",
        unhandledToast: "요청 처리 중 문제가 발생했어요. 잠시 후 다시 시도해주세요.",
      },
      results: {
        title: "분석 결과",
        subtitlePrefix: "카탈로그",
        subtitleSongs: "곡 비교 · 총",
        subtitleSeconds: "초 소요",
        newAnalysis: "새 음악 분석",
        share: "결과 공유",
        sortLabel: "정렬 기준",
        sortBySimilarity: "유사도 높은 순",
        sortByTempo: "Tempo 차이 적은 순",
        sortByEnergy: "에너지 차이 적은 순",
        copyLink: "결과 복사",
        copyShareUrl: "공유 링크 복사",
        seedButton: "이 곡으로 다시 찾기",
        seedBack: "← 이전 분석으로",
        expandAll: "모두 펼치기",
        collapseAll: "모두 접기",
        seedHeader: (title, artist) => `시드: ${title} – ${artist}`,
        seedFailedToast: "시드 재탐색에 실패해서 이전 결과로 돌아갔어요.",
        metaAnalyzedAt: "분석 시각",
        metaCatalogSize: (n) => `카탈로그 ${n}곡`,
        metaCached: "캐시된 결과",
        favoriteAdd: "즐겨찾기",
        favoriteRemove: "즐겨찾기 해제",
        copied: "복사됨!",
        restored: "공유된 분석 결과를 불러왔어요.",
        shareUrlFailed: "공유 링크 생성에 실패했습니다. 다시 시도해주세요.",
        exportJson: "JSON 다운로드",
        exportCsv: "CSV 저장",
        exportSvg: "SVG 저장",
        exportPng: "PNG 저장",
        exportPngFailed: "PNG 변환에 실패했어요. SVG 저장으로 대체해주세요.",
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
        view: "보기",
        storageFull: "로컬 저장 공간이 부족해 히스토리를 추가하지 못했어요. '기록 지우기' 로 정리해주세요.",
      },
      favorites: {
        title: "내 즐겨찾기",
        sub: "★ 표시한 곡들이 여기 모입니다. 카드를 누르면 그 곡 기준으로 카탈로그를 즉시 다시 검색합니다.",
        clear: "모두 지우기",
        confirm: "즐겨찾기를 모두 지울까요?",
        filterOnly: "즐겨찾기만 보기",
        export: "내보내기",
        import: "가져오기",
        exportDone: "즐겨찾기 JSON 파일을 받았어요.",
        importSuccess: (added, total) =>
          added > 0
            ? `새 곡 ${added}개를 추가했어요. 현재 ${total}곡 저장 중.`
            : "이미 모두 등록된 곡이에요. 변경된 항목이 없습니다.",
        importFailed: "JSON 파일을 읽지 못했어요. 같은 형식의 파일인지 확인해주세요.",
        storageFull: "로컬 저장 공간이 부족해 즐겨찾기를 저장하지 못했어요. '모두 지우기' 로 정리해주세요.",
      },
      summary: {
        tempo: "Tempo",
        tempoHelp: "분당 비트 수. 빠른 곡일수록 큰 값.",
        energy: "에너지 (RMS)",
        energyHelp: "평균 음량. 1에 가까울수록 큰 소리.",
        brightness: "밝기",
        brightnessHelp: "스펙트럴 센트로이드(Hz). 높을수록 고음역 중심의 밝은 톤.",
        noisiness: "거친 정도",
        noisinessHelp: "Zero-Crossing Rate. 노이즈/마찰음이 많은 록·메탈에서 높게 나옴.",
        harmony: "화성/타악기 비율",
        harmonyHelp: "1보다 크면 멜로디 성분이, 작으면 타악기 성분이 우세.",
        chroma: "크로마",
        chromaHelp: "12음 분포 평균. 화성적인 색채감.",
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
        catalogPreviewTitle: "카탈로그에 어떤 곡들이 있나요?",
        catalogPreviewSub:
          "분석 시 비교 대상이 되는 카탈로그의 일부를 보여드려요. 같은 장르 / 음색의 곡을 올리면 더 정확한 매칭이 가능합니다.",
        catalogPreviewLoading: "카탈로그를 불러오는 중…",
        catalogPreviewFail: "카탈로그 미리보기를 불러올 수 없어요. 잠시 후 다시 시도해주세요.",
        catalogReload: "다른 곡 보기",
      },
      footer: {
        notice:
          "서버에 음원을 영구 저장하지 않습니다. 분석 결과는 학술/취미 용도로만 사용해주세요.",
        repoLink: "GitHub",
        privacy: "개인정보 처리방침",
        terms: "이용약관",
        tagline: "졸업작품에서 출발해, 시중 서비스급으로 끝까지 다듬은 프로젝트",
      },
      controls: {
        themeToggle: "테마 전환",
        langToggle: "Language: English",
        shortcuts: "단축키: / 업로드 · Esc 결과 닫기 · Space 재생 · j/k 결과 이동 · ? 도움말",
      },
      shortcuts: {
        title: "키보드 단축키",
        close: "닫기",
        focusUpload: "업로드 영역으로 포커스 이동",
        playPause: "업로드 음원 재생 / 일시정지",
        next: "다음 결과 카드",
        prev: "이전 결과 카드",
        toggle: "선택된 카드 펼침 / 접힘",
        closeResult: "결과 닫기 / 모달 닫기",
        openHelp: "이 도움말 토글",
        hint: "입력창 안에서는 단축키가 동작하지 않습니다.",
      },
      install: {
        title: "앱으로 설치",
        body: "— 홈 화면에 추가하면 오프라인에서도 결과 페이지를 다시 열어볼 수 있어요.",
        accept: "설치하기",
      },
      catalog: {
        back: "← 메인으로",
        title: "카탈로그 둘러보기",
        sub: "업로드한 음원이 비교되는 카탈로그입니다. 같은 장르 / 음색의 곡이 보이면 매칭이 더 잘 됩니다.",
        searchPlaceholder: "제목이나 아티스트로 검색",
        searchClear: "검색어 지우기",
        loading: "불러오는 중…",
        empty: "결과 없음",
        emptyFavorites: "즐겨찾기 없음",
        emptyHint: "해당하는 곡이 없어요. 다른 키워드로 검색해보세요.",
        emptyFavoritesHint: "즐겨찾기에 저장된 곡이 없어요. 카탈로그 카드의 ★ 버튼으로 추가해보세요.",
        loadFail: "불러오기에 실패했어요",
        retryHint: "잠시 후 다시 시도해주세요.",
        favoritesOnly: "즐겨찾기만 보기",
        sortLabel: "정렬",
        sortDefault: "기본",
        sortTitle: "곡명",
        sortArtist: "아티스트",
        sortBpm: "BPM 낮은 순",
        sortEnergy: "에너지 낮은 순",
        sortShuffle: "🎲 무작위",
        prev: "← 이전",
        next: "다음 →",
        first: "처음 페이지",
        last: "마지막 페이지",
        bpmDist: "BPM 분포",
        bpmDistAvg: (avg, total) => `평균 ${avg} · 곡 수 ${total}`,
        histClickHint: "클릭하면 이 구간으로 필터",
        metaRange: (total, from, to) => `${total.toLocaleString("ko-KR")}곡 중 ${from}–${to}`,
        cardHint: "이 곡과 유사한 다른 곡 보기",
        favAdd: "즐겨찾기 추가",
        favRemove: "즐겨찾기 해제",
        modalLoading: "불러오는 중…",
        modalAnalysing: "분석 중…",
        modalFail: "불러오기에 실패했어요. 잠시 후 다시 시도해주세요.",
        modalNone: "유사한 곡을 찾지 못했어요.",
        modalSub: (artist, size) => `${artist} · ${size.toLocaleString("ko-KR")}곡과 비교`,
        modalSeed: "이 곡 기준으로 다시 보기",
        modalClose: "닫기",
        resetFilters: "필터 초기화",
      },
      compare: {
        back: "← 메인으로",
        title: "두 곡 나란히 비교하기",
        sub: "최근 분석한 곡 중 두 개를 골라서 메트릭과 1위 매칭을 한 눈에 비교해보세요.",
        left: "왼쪽 곡",
        right: "오른쪽 곡",
        emptyTitle: "히스토리에 분석 결과가 2건 이상 있어야 비교할 수 있어요.",
        emptyBody: "메인 화면에서 음원을 두 곡 이상 분석해 주세요.",
        invalid: "유효하지 않은 선택이에요.",
        topMatch: "Top 1 매칭",
        topSuffix: "유사도",
        metric: {
          tempo: "Tempo (BPM)",
          energy: "에너지 (RMS)",
          brightness: "밝기 (Hz)",
          noisiness: "거친 정도",
          harmony: "화성/타악기",
          chroma: "크로마",
        },
      },
      notFound: {
        title: "요청하신 페이지를 찾을 수 없어요",
        sub: "주소가 잘못되었거나 페이지가 이동된 것 같습니다. 메인 화면에서 음악을 업로드하면 유사한 곡을 다시 찾아드릴게요.",
        home: "메인으로 돌아가기",
      },
    },
    en: {
      nav: { how: "How it works", features: "Features", compare: "Compare", catalog: "Catalog", github: "GitHub" },
      hero: {
        eyebrow: "Sklearn · librosa · FastAPI · WebAudio",
        title: "Find the songs <span class=\"grad\">most similar</span> to yours,<br/>powered by AI.",
        lede: "Drop an audio file and we extract <strong>58 acoustic features</strong> with librosa, rank the closest matches with cosine similarity, and explain <strong>why</strong> each match sounds like yours.",
        statCatalogLabel: "Catalog songs",
        statFeaturesLabel: "Audio features",
        statTimeLabel: "Avg. analysis time",
        catalogFresh: (date) => `Updated · ${date}`,
        totalAnalyses: (n) => `${n} tracks analysed so far`,
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
        leaveWarn: "Analysis is still running. Leaving will discard the result.",
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
        globalToast: "Something went wrong. Please refresh and try again.",
        unhandledToast: "Something went wrong handling the request. Please try again shortly.",
      },
      results: {
        title: "Results",
        subtitlePrefix: "Compared against",
        subtitleSongs: "tracks ·",
        subtitleSeconds: "s total",
        newAnalysis: "Analyze another",
        share: "Share",
        sortLabel: "Sort by",
        sortBySimilarity: "Similarity (high to low)",
        sortByTempo: "Closest tempo",
        sortByEnergy: "Closest energy",
        copyLink: "Copy result",
        copyShareUrl: "Copy shareable link",
        seedButton: "Search by this track",
        seedBack: "← Back to previous result",
        expandAll: "Expand all",
        collapseAll: "Collapse all",
        seedHeader: (title, artist) => `Seed: ${title} – ${artist}`,
        seedFailedToast: "Seed search failed. Reverted to the previous result.",
        metaAnalyzedAt: "Analyzed at",
        metaCatalogSize: (n) => `${n} catalog tracks`,
        metaCached: "cached result",
        favoriteAdd: "Favorite",
        favoriteRemove: "Unfavorite",
        copied: "Copied!",
        restored: "Loaded a shared analysis result.",
        shareUrlFailed: "Failed to build a share link. Try again.",
        exportJson: "Download JSON",
        exportCsv: "Save CSV",
        exportSvg: "Save SVG",
        exportPng: "Save PNG",
        exportPngFailed: "PNG conversion failed. Try SVG instead.",
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
        view: "View",
        storageFull: "Browser storage is full. We couldn't save this analysis to history — please clear old entries.",
      },
      favorites: {
        title: "My favorites",
        sub: "Tracks you starred land here. Click a card to re-search the catalog using that track as the seed.",
        clear: "Clear all",
        confirm: "Clear all favorites?",
        filterOnly: "Favorites only",
        export: "Export",
        import: "Import",
        exportDone: "Saved favorites to a JSON file.",
        importSuccess: (added, total) =>
          added > 0
            ? `Added ${added} new tracks. Now keeping ${total} favorites.`
            : "All tracks were already saved. Nothing changed.",
        importFailed: "Could not read the JSON file. Please check the format.",
        storageFull: "Browser storage is full. Favorites weren't saved — please clear them first.",
      },
      summary: {
        tempo: "Tempo",
        tempoHelp: "Beats per minute. Higher means faster.",
        energy: "Energy (RMS)",
        energyHelp: "Average loudness. Closer to 1 = louder.",
        brightness: "Brightness",
        brightnessHelp: "Spectral centroid (Hz). Higher = brighter, treble-heavy tone.",
        noisiness: "Roughness",
        noisinessHelp: "Zero-Crossing Rate. Higher in rock/metal — more friction.",
        harmony: "Harmony/Percussive ratio",
        harmonyHelp: ">1 means melodic dominance; <1 means percussion dominance.",
        chroma: "Chroma",
        chromaHelp: "Average 12-pitch distribution — harmonic flavor.",
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
        catalogPreviewTitle: "What's in the catalog?",
        catalogPreviewSub:
          "A peek at the songs your upload is compared against. Tracks with a similar genre/timbre will match more accurately.",
        catalogPreviewLoading: "Loading catalog…",
        catalogPreviewFail: "Couldn't load the catalog preview. Try again later.",
        catalogReload: "Shuffle",
      },
      footer: {
        notice:
          "No audio is permanently stored. Results are for academic / personal use.",
        repoLink: "GitHub",
        privacy: "Privacy",
        terms: "Terms",
        tagline: "Started as a capstone project, polished into a production-ready service.",
      },
      controls: {
        themeToggle: "Toggle theme",
        langToggle: "언어: 한국어",
        shortcuts: "Shortcuts: / upload · Esc close result · Space play · j/k navigate · ? help",
      },
      shortcuts: {
        title: "Keyboard shortcuts",
        close: "Close",
        focusUpload: "Focus the upload area",
        playPause: "Play / pause uploaded track",
        next: "Next result card",
        prev: "Previous result card",
        toggle: "Toggle selected card expansion",
        closeResult: "Close result / modal",
        openHelp: "Toggle this help dialog",
        hint: "Shortcuts are disabled while typing in inputs.",
      },
      install: {
        title: "Install as app",
        body: "— Add to home screen to keep results available offline.",
        accept: "Install",
      },
      catalog: {
        back: "← Back home",
        title: "Browse the catalog",
        sub: "These are the songs your upload is compared against. Closer genre/timbre = better matches.",
        searchPlaceholder: "Search title or artist",
        searchClear: "Clear search",
        loading: "Loading…",
        empty: "No results",
        emptyFavorites: "No favorites",
        emptyHint: "No tracks match. Try a different keyword.",
        emptyFavoritesHint: "No favorites yet. Use the ★ button on catalog cards.",
        loadFail: "Could not load",
        retryHint: "Please try again later.",
        favoritesOnly: "Favorites only",
        sortLabel: "Sort",
        sortDefault: "Default",
        sortTitle: "Title",
        sortArtist: "Artist",
        sortBpm: "BPM (low to high)",
        sortEnergy: "Energy (low to high)",
        sortShuffle: "🎲 Shuffle",
        prev: "← Prev",
        next: "Next →",
        first: "First page",
        last: "Last page",
        bpmDist: "BPM distribution",
        bpmDistAvg: (avg, total) => `avg ${avg} · ${total} tracks`,
        histClickHint: "Click to filter by this range",
        metaRange: (total, from, to) => `${from}–${to} of ${total.toLocaleString("en-US")}`,
        cardHint: "Show tracks similar to this one",
        favAdd: "Add to favorites",
        favRemove: "Remove from favorites",
        modalLoading: "Loading…",
        modalAnalysing: "Analysing…",
        modalFail: "Could not load. Try again shortly.",
        modalNone: "No similar tracks found.",
        modalSub: (artist, size) => `${artist} · compared with ${size.toLocaleString("en-US")} tracks`,
        modalSeed: "Use this track as the seed",
        modalClose: "Close",
        resetFilters: "Reset filters",
      },
      compare: {
        back: "← Back home",
        title: "Compare two tracks side by side",
        sub: "Pick two recent analyses and inspect metrics & top matches in parallel.",
        left: "Left track",
        right: "Right track",
        emptyTitle: "You need at least two analyses in history to compare.",
        emptyBody: "Analyse two or more tracks on the main page first.",
        invalid: "Invalid selection.",
        topMatch: "Top 1 match",
        topSuffix: "similarity",
        metric: {
          tempo: "Tempo (BPM)",
          energy: "Energy (RMS)",
          brightness: "Brightness (Hz)",
          noisiness: "Roughness",
          harmony: "Harmony/Percussion",
          chroma: "Chroma",
        },
      },
      notFound: {
        title: "Page not found",
        sub: "The URL looks broken, or the page has moved. Head back home and try analysing a track from there.",
        home: "Back home",
      },
    },
  };

  function detectInitial() {
    // 저장된 값이 있으면 우선 사용, 없으면 브라우저 언어로 추론.
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored && dict[stored]) return stored;
    const nav = (navigator.language || FALLBACK).toLowerCase();
    if (nav.startsWith("ko")) return "ko";
    if (nav.startsWith("en")) return "en";
    return FALLBACK;
  }

  let current = detectInitial();

  function get(path) {
    // dot path 로 사전을 깊이 탐색. 현재 언어에서 못 찾으면 폴백 언어로 한 번 더 시도.
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
    // 외부에서 언어 변경에 반응할 수 있도록 커스텀 이벤트 한 번 쏘아준다.
    window.dispatchEvent(new CustomEvent("i18n:change", { detail: { lang: next } }));
  }

  function toggle() {
    setLang(current === "ko" ? "en" : "ko");
  }

  function apply(root = document) {
    // data-i18n="키"  →  텍스트 콘텐츠로 주입.
    // data-i18n-html 속성이 함께 있으면 HTML 로 주입(서식 포함).
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
    // data-i18n-attr="aria-label:키,placeholder:키2" 형태로 속성 단위 번역 지원.
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

  // DOM 이 이미 준비됐으면 즉시 적용, 아니면 DOMContentLoaded 까지 대기.
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
