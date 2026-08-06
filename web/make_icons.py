#!/usr/bin/env python3
"""PWA用アイコンを標準ライブラリのみで生成する（追加インストール不要）。

出力: web/icons/icon-192.png, icon-512.png, icon-180.png, icon.svg
デザイン: ダーク背景 + 白い3本リール + ゴールドのアクセント。
マスカブル対応のため、絵柄は中央60%のセーフゾーン内に収める。
"""
import os
import struct
import zlib

ICON_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons")

BG = (28, 28, 30)        # #1c1c1e ダーク背景
REEL = (245, 245, 247)   # ほぼ白
GOLD = (212, 160, 23)    # ゴールドのアクセント


def _write_png(path: str, width: int, height: int, rgb: bytearray) -> None:
    """RGB画素列(bytearray, 長さ=width*height*3)を8bit PNGとして書き出す。"""
    raw = bytearray()
    stride = width * 3
    for y in range(height):
        raw.append(0)  # filter type 0 (None)
        raw.extend(rgb[y * stride:(y + 1) * stride])

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xffffffff))

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)  # 8bit truecolor
    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", ihdr)
           + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
           + chunk(b"IEND", b""))
    with open(path, "wb") as f:
        f.write(png)


def _rounded(px: float, py: float, x0: float, y0: float, x1: float, y1: float, r: float) -> bool:
    """角丸長方形の内側なら True。"""
    if not (x0 <= px <= x1 and y0 <= py <= y1):
        return False
    # 縦帯・横帯（角以外）は無条件で内側
    if x0 + r <= px <= x1 - r or y0 + r <= py <= y1 - r:
        return True
    # 四隅は円の内側だけ
    cx = x0 + r if px < x0 + r else x1 - r
    cy = y0 + r if py < y0 + r else y1 - r
    return (px - cx) ** 2 + (py - cy) ** 2 <= r * r


def _render(size: int) -> bytearray:
    rgb = bytearray(size * size * 3)
    # 3本リールの配置（中央60%セーフゾーン内）
    margin = size * 0.20
    inner = size - 2 * margin
    gap = inner * 0.08
    bar_w = (inner - 2 * gap) / 3.0
    top = margin + inner * 0.14
    bot = size - margin - inner * 0.14
    radius = bar_w * 0.28
    bars = []
    for i in range(3):
        bx0 = margin + i * (bar_w + gap)
        bars.append((bx0, top, bx0 + bar_w, bot))
    # ゴールドの横帯（リール中央のライン）
    line_y0 = size * 0.47
    line_y1 = size * 0.53

    for y in range(size):
        for x in range(size):
            r, g, b = BG
            for (bx0, by0, bx1, by1) in bars:
                if _rounded(x + 0.5, y + 0.5, bx0, by0, bx1, by1, radius):
                    r, g, b = REEL
                    if line_y0 <= y <= line_y1:
                        r, g, b = GOLD
                    break
            idx = (y * size + x) * 3
            rgb[idx] = r
            rgb[idx + 1] = g
            rgb[idx + 2] = b
    return rgb


SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 512 512">
  <rect width="512" height="512" fill="#1c1c1e"/>
  <g>
    <rect x="112" y="150" width="80" height="212" rx="22" fill="#f5f5f7"/>
    <rect x="216" y="150" width="80" height="212" rx="22" fill="#f5f5f7"/>
    <rect x="320" y="150" width="80" height="212" rx="22" fill="#f5f5f7"/>
    <rect x="100" y="240" width="312" height="32" fill="#d4a017"/>
  </g>
</svg>
"""


def main() -> None:
    os.makedirs(ICON_DIR, exist_ok=True)
    for size, name in ((192, "icon-192.png"), (512, "icon-512.png"), (180, "icon-180.png")):
        _write_png(os.path.join(ICON_DIR, name), size, size, _render(size))
        print(f"生成: icons/{name}")
    with open(os.path.join(ICON_DIR, "icon.svg"), "w", encoding="utf-8") as f:
        f.write(SVG)
    print("生成: icons/icon.svg")


if __name__ == "__main__":
    main()
