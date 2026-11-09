# -*- coding: utf-8 -*-
"""把含 WorkBuddy 主题 CSS 变量的 SVG 渲染成独立 PNG（白底、2 倍分辨率）。

用法:
    python svg2png.py <输入.svg> <输出.png> [倍率]

原理: 原 SVG 用了 var(--color-...) 主题变量，独立用浏览器打开时变量缺失会回退成
黑填充/无描边。这里先把 SVG 包进一个定义了同名变量的 HTML，再用 Edge headless
截图，得到任何看图软件都能正常显示的 PNG。原 SVG 文件不做任何修改。
"""
import pathlib
import re
import subprocess
import sys
import tempfile

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

CSS = """
:root{
  --font-sans: "Microsoft YaHei", "Segoe UI", sans-serif;
  --color-text-primary:#2C2C2A;
  --color-text-secondary:#5F5E5A;
  --color-background-primary:#FFFFFF;
  --color-background-secondary:#F7F7F5;
  --color-border-secondary:#B4B2A9;
  --color-border-tertiary:#D3D1C7;
}
html,body{margin:0;padding:0;background:#FFFFFF;}
"""


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    src = pathlib.Path(sys.argv[1]).resolve()
    dst = pathlib.Path(sys.argv[2]).resolve()
    scale = float(sys.argv[3]) if len(sys.argv) > 3 else 2.0

    svg = src.read_text(encoding="utf-8")
    m = re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', svg)
    w, h = (float(m.group(1)), float(m.group(2))) if m else (680.0, 650.0)
    W, H = int(w * scale), int(h * scale)

    html = ('<!doctype html><html><head><meta charset="utf-8"><style>'
            + CSS + f'svg{{display:block;width:{W}px;height:{H}px;}}</style>'
            + '</head><body>' + svg + '</body></html>')
    tmp = src.parent / ("_" + src.stem + "_render.html")
    tmp.write_text(html, encoding="utf-8")
    try:
        subprocess.run([
            EDGE,
            "--headless=new",
            "--disable-gpu",
            "--hide-scrollbars",
            "--no-first-run",
            "--disable-extensions",
            f"--user-data-dir={tempfile.gettempdir()}/wb_svg_render",
            f"--screenshot={dst}",
            f"--window-size={W},{H}",
            "--virtual-time-budget=1500",
            tmp.as_uri(),
        ], check=True, timeout=90)
    finally:
        tmp.unlink(missing_ok=True)

    if not dst.exists():
        print("FAILED: 未生成 PNG")
        sys.exit(2)
    print(f"OK {dst}  {W}x{H}  {dst.stat().st_size} bytes")


if __name__ == "__main__":
    main()
