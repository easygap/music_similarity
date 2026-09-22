# SoundMatch

[한국어](../../README.md) · [English](README.en.md) · [日本語](README.ja.md) · **简体中文**

**上传音乐文件，找声音相近的歌。**

SoundMatch 会分析你上传的音乐，从内置的 **781 首歌**中找出相似的歌曲。
你可以看图表了解它们的节奏、音色有多接近，也可以从推荐结果继续找歌。
在自己的电脑上就能运行，不需要注册账号，也不用申请 API 密钥。

[运行方法](#start) · [怎么找歌](#find-tracks) · [反馈问题](https://github.com/easygap/music_similarity/issues/new/choose)

<picture>
  <source media="(prefers-reduced-motion: reduce)" srcset="../screenshots/hero-en.png">
  <img src="../media/listen-en.gif" alt="切换播放 A、B 两段示例音频，再将频率图叠在一起比较" width="960">
</picture>

应用界面目前支持韩语和英语。下文的按钮名称和截图均以英文界面为例；如果打开后显示韩语，点击右上角的 **English** 即可切换。

## 先听听示例

首页准备了几段**约 9 秒的示例音频**：旋律相同，音色和节奏有所变化。
**交替点击 A、B 的播放按钮，就能从同一位置接着听，比较两段音频的差别。**
焦点在示例播放器内时，也可以按键盘上的 A、B 键切换。打开 **Loop** 可以循环播放。

图表中的粗实线跟随当前播放的音频，虚线标出另一段音频的同一位置。
点击 **Overlay sounds**，可以把两张图叠在一起看。

GIF 没有声音。想听音频，可以运行应用，也可以直接下载示例：
[原版](../../frontend/assets/demo/original.wav?raw=true) · [更明亮的音色](../../frontend/assets/demo/tone.wav?raw=true) · [更快的节奏](../../frontend/assets/demo/rhythm.wav?raw=true)

<a name="find-tracks"></a>

## 用自己的音乐找相似歌曲

1. 把音频文件拖到上传区域，或点击选择文件。
2. 点击 **Find similar tracks**，结果会按相似程度从高到低排列。
3. 遇到感兴趣的歌，点击 **Keep exploring from here**，就能继续找与这首歌相似的歌曲。

![分析结果页，展示推荐歌曲、相似度，以及节奏和音色的对比图表](../screenshots/result-en.png)

每首推荐歌曲都附有 YouTube 和 Spotify 搜索链接，可以通过链接找到歌曲收听。

| 支持格式 | 文件大小上限 | 分析范围 |
| --- | --- | --- |
| MP3 · WAV · FLAC · OGG · M4A | 25MB | 每首歌开头最多 30 秒 |

## 对比两首歌

从分析记录中选两首歌，就能并排比较速度、音量和音色。
还没有分析记录的话，可以先点 **Try the sample comparison** 查看示例。

![用条形图并排比较两首歌的速度、音量和音色](../screenshots/compare-en.png)

喜欢的歌可以加入收藏。分析结果既能通过链接分享，也能下载为图片（PNG、SVG）、表格（CSV）或 JSON 数据。

## 浏览曲库

打开 **Catalog**，可以按歌名或歌手搜索，也可以按速度和音量筛选。

![曲库页面，可搜索歌名和歌手，并按速度、音量筛选](../screenshots/catalog-en.png)

<details>
<summary>手机界面和深色模式</summary>

<table>
<tr>
<td width="70%" valign="top"><img src="../screenshots/hero-dark.png" alt="深色模式，截图中的界面语言为韩语"></td>
<td width="30%" valign="top"><img src="../screenshots/hero-mobile.png" alt="手机上的示例播放器，截图中的界面语言为韩语"></td>
</tr>
</table>

</details>

<a name="start"></a>

## 在自己的电脑上运行

先安装 [Git](https://git-scm.com/downloads) 和 [Docker](https://docs.docker.com/get-started/get-docker/)，然后运行：

```bash
git clone https://github.com/easygap/music_similarity.git
cd music_similarity
docker compose up --build
```

服务启动后，用浏览器打开 **[localhost:8000](http://localhost:8000)**。
首次运行需要下载相关软件，会花一些时间。

不想自己选文件的话，点击首页的 **Analyze the sample you just heard**，就能用示例音频查看完整的推荐结果。

<details>
<summary>不使用 Docker 的运行方法</summary>

已在 Python 3.11、3.12、3.14 上测试。还需要安装 [FFmpeg](https://ffmpeg.org/download.html)。
先执行上面的 `git clone` 和 `cd`，再按你的操作系统运行以下命令。

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

浏览器访问地址同样是 [localhost:8000](http://localhost:8000)。

</details>

## 常见问题

**能搜索全网的歌曲吗？**

目前只在项目自带的 781 首歌中查找。完整曲目可以在 **Catalog** 中查看。

**上传的文件会保存下来吗？**

文件只会在分析时临时保存，分析结束后删除。按上面的方法在自己的电脑上运行时，文件也在本机处理，不会用于 AI 训练。分析记录和收藏保存在浏览器里。

**相似度分数怎么看？**

分数表示速度、音色等声音特征有多接近，不代表旋律相同的比例，也不能用来判断是否抄袭。只分析开头最多 30 秒，后面的副歌等部分不会影响结果。

**遇到问题怎么反馈？**

请[提交 Issue](https://github.com/easygap/music_similarity/issues/new/choose)，写明使用的浏览器，以及出问题前做了哪些操作。有截图的话，也请一起附上。

---

本项目从毕业设计 [capstone_music](https://github.com/easygap/capstone_music)发展而来。
[参与开发](../../CONTRIBUTING.md) · [更新记录](../../CHANGELOG.md) · [测试和性能记录](../verification-2026.md)（链接中的文档为韩语）

代码和自行制作的示例音频采用 [MIT 许可证](../../LICENSE)，字体采用 SIL OFL 许可证：
[Pretendard](../../frontend/assets/fonts/OFL.txt) · [LINE Seed KR](../../frontend/assets/fonts/LINE-Seed-OFL.txt)
