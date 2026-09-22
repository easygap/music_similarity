"""UI에 쓰는 글자의 가변 글꼴을 생성한다. 배포/실행 때는 이 과정이 필요 없다.

개발 도구: pip install fonttools brotli
원본 Pretendard 1.3.9는 SIL OFL. 서브셋은 예약된 이름을 쓰지 않는다.
"""
from pathlib import Path
from urllib.request import urlopen
from zipfile import ZipFile

from fontTools import subset
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "frontend/assets/fonts"
SOURCE = "https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/packages/pretendard/dist/web/variable/woff2/PretendardVariable.woff2"
LICENSE = "https://raw.githubusercontent.com/orioncactus/pretendard/v1.3.9/LICENSE"
DISPLAY_SOURCE = "https://seed.line.me/src/images/fonts/LINE_Seed_Sans_KR.zip"
DISPLAY_LICENSE = "https://raw.githubusercontent.com/line/seed/main/OFL.txt"


def build_display():
    """LINE·산돌의 LINE Seed KR Bold에서 첫 화면 제목과 숫자만 묶는다."""
    archive = ROOT / "output/LINE_Seed_Sans_KR.zip"
    if not archive.exists():
        with urlopen(DISPLAY_SOURCE, timeout=60) as response:
            archive.write_bytes(response.read())
    source = ROOT / "output/LINESeedKR-Bd.ttf"
    with ZipFile(archive) as package:
        member = next(name for name in package.namelist() if name.endswith("/TTF/LINESeedKR-Bd.ttf") and not name.startswith("__MACOSX/"))
        source.write_bytes(package.read(member))
    with urlopen(DISPLAY_LICENSE, timeout=30) as response:
        (DEST / "LINE-Seed-OFL.txt").write_bytes(response.read())
    font = TTFont(source)
    options = subset.Options()
    options.name_IDs = ["*"]
    options.name_legacy = True
    options.name_languages = ["*"]
    builder = subset.Subsetter(options=options)
    # 영문 제목은 ASCII로 포함. 한국어 제목을 수정하면 함께 재생성한다.
    builder.populate(unicodes=set(range(32, 127)) | set(map(ord, "두 곡, 어디가 닮았을까?")))
    builder.subset(font)
    for record in font["name"].names:
        if record.nameID in (1, 3, 4, 6, 16, 21, 25):
            name = "SoundMatchDisplay-Bold" if record.nameID in (3, 6, 25) else "SoundMatch Display"
            record.string = name.encode(record.getEncoding())
    font.flavor = "woff2"
    target = DEST / "soundmatch-display-v1.woff2"
    font.save(target)
    print(f"{target.name}: {target.stat().st_size:,} bytes / {len(font.getBestCmap()):,} characters")


def build():
    DEST.mkdir(parents=True, exist_ok=True)
    original = ROOT / "output/PretendardVariable.woff2"
    original.parent.mkdir(parents=True, exist_ok=True)
    if not original.exists():
        with urlopen(SOURCE, timeout=60) as response:
            original.write_bytes(response.read())
    with urlopen(LICENSE, timeout=30) as response:
        (DEST / "OFL.txt").write_bytes(response.read())
    characters = set(range(32, 127))
    for path in (ROOT / "frontend").rglob("*"):
        if path.suffix in (".html", ".js", ".css"):
            characters.update(map(ord, path.read_text(encoding="utf-8")))
    font = TTFont(original)
    options = subset.Options()
    options.flavor = "woff2"
    options.hinting = False
    options.name_IDs = ["*"]
    options.name_legacy = True
    options.name_languages = ["*"]
    builder = subset.Subsetter(options=options)
    builder.populate(unicodes=characters)
    builder.subset(font)
    for record in font["name"].names:
        if record.nameID in (1, 3, 4, 6, 16, 21, 25):
            family = "SoundMatchUI" if record.nameID in (6, 25) else "SoundMatch UI"
            record.string = record.toUnicode().replace("Pretendard", family).encode(record.getEncoding())
    font.flavor = "woff2"
    target = DEST / "soundmatch-ui-v1.woff2"
    font.save(target)
    print(f"{target.name}: {target.stat().st_size:,} bytes / {len(font.getBestCmap()):,} characters")


if __name__ == "__main__":
    build()
    build_display()
