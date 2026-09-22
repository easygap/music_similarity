# SoundMatch

[한국어](../../README.md) · **English** · [日本語](README.ja.md) · [简体中文](README.zh-CN.md)

**Find similar music from an audio file.**

Upload a track and SoundMatch finds similar songs in a collection of **781 tracks**. Compare their tempo and tone in the charts, or pick a result to find more tracks like it.
The app runs on your computer. No account or API key required.

[Run the app](#start) · [Find similar tracks](#find-tracks) · [Report a problem](https://github.com/easygap/music_similarity/issues/new/choose)

<picture>
  <source media="(prefers-reduced-motion: reduce)" srcset="../screenshots/hero-en.png">
  <img src="../media/listen-en.gif" alt="Switching between samples A and B, then overlaying their frequency graphs" width="960">
</picture>

## Try the audio samples

The home page includes **9-second samples** of the same melody with different sounds and rhythms.
**Switch between A and B to hear the same passage in each version.** You can also use the A and B keys while focused on the sample player. Turn on **Loop** to keep listening.

A bold line follows the track you're hearing; a dashed line marks the same moment in the other track. Use **Overlay sounds** to bring the graphs together.

The GIF is silent. Run the app to listen, or download the samples:
[Original](../../frontend/assets/demo/original.wav?raw=true) · [Bright keys](../../frontend/assets/demo/tone.wav?raw=true) · [Faster beat](../../frontend/assets/demo/rhythm.wav?raw=true)

<a name="find-tracks"></a>

## Find tracks like yours

1. Drop an audio file onto the upload area, or click to choose one.
2. Click **Find similar tracks** to see the closest matches first.
3. Like one of the recommendations? Choose **Keep exploring from here** to search for tracks like that one.

![Analysis results with recommended tracks, similarity scores, and charts showing how their audio characteristics compare](../screenshots/result-en.png)

Each recommendation includes YouTube and Spotify search links so you can find a place to listen.

| Supported formats | File size limit | Audio analyzed |
| --- | --- | --- |
| MP3 · WAV · FLAC · OGG · M4A | 25MB | Up to the first 30 seconds |

## Compare two tracks

Pick two tracks from your analysis history to compare their tempo, loudness, and tone side by side. If your history is empty, choose **Try the sample comparison**.

![Two tracks compared side by side using bar charts](../screenshots/compare-en.png)

Save tracks to **Favorites**, share a link to your results, or download them as an image (PNG or SVG), a spreadsheet-friendly CSV, or JSON data.

## Browse the music collection

Open **Catalog** to search by title or artist. Filter by tempo and loudness to narrow the list.

![The catalog, with title and artist search plus tempo and loudness filters](../screenshots/catalog-en.png)

<details>
<summary>Mobile layout and dark mode</summary>

<table>
<tr>
<td width="70%" valign="top"><img src="../screenshots/hero-dark.png" alt="SoundMatch in dark mode, with the interface set to Korean"></td>
<td width="30%" valign="top"><img src="../screenshots/hero-mobile.png" alt="The sample player on a mobile screen, with the interface set to Korean"></td>
</tr>
</table>

The app interface supports Korean and English. This guide is also available in Japanese and Simplified Chinese using the links at the top.

</details>

<a name="start"></a>

## Run it on your computer

Install [Git](https://git-scm.com/downloads) and [Docker](https://docs.docker.com/get-started/get-docker/), then run:

```bash
git clone https://github.com/easygap/music_similarity.git
cd music_similarity
docker compose up --build
```

Once the server is running, open **[localhost:8000](http://localhost:8000)** in your browser. The first build takes a little longer because it downloads the required software.

To try a full analysis without choosing a file, click **Analyze the sample you just heard** on the home page.

<details>
<summary>Run without Docker</summary>

Tested with Python 3.11, 3.12, and 3.14. Install [FFmpeg](https://ffmpeg.org/download.html) as well.
Run the `git clone` and `cd` commands above, then follow the instructions for your system.

**Windows PowerShell**

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m uvicorn backend.main:app
```

**macOS · Linux**

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m uvicorn backend.main:app
```

Open [localhost:8000](http://localhost:8000).

</details>

## Questions

**Which songs can it recommend?**

SoundMatch searches the 781 tracks included with the project. It doesn't search every song on the internet. You can browse the full list in **Catalog**.

**What happens to my uploaded file?**

The server keeps a temporary copy for analysis and deletes it afterward. When you run the app on your own computer, the file is processed there. Uploads aren't used for AI training. Your analysis history and favorites are saved in your browser.

**What does the similarity score mean?**

It compares audio characteristics such as tempo and tone. It isn't a measure of matching melodies or evidence of plagiarism. Only the first 30 seconds are analyzed, so later sections of the song won't affect the result.

**Where can I report a problem?**

[Open an issue](https://github.com/easygap/music_similarity/issues/new/choose) with your browser name and the steps that led to the problem. A screenshot helps.

---

SoundMatch grew out of the [capstone_music](https://github.com/easygap/capstone_music) graduation project.
[Contributing](../../CONTRIBUTING.md) · [Changelog](../../CHANGELOG.md) · [Test and performance results](../verification-2026.md) — these documents are in Korean.

The code and original audio samples are released under the [MIT license](../../LICENSE). Fonts are licensed under the SIL OFL:
[Pretendard](../../frontend/assets/fonts/OFL.txt) · [LINE Seed KR](../../frontend/assets/fonts/LINE-Seed-OFL.txt)
