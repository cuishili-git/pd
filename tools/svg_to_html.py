# -*- coding: utf-8 -*-
"""把一张 SVG 电路图包成自包含的 HTML 预览页。

为什么需要这个：本机 Edge 的 headless 截图在部分时段会静默失败（不落盘也不报错），
而 SVG 在浏览器里直接打开完全正常。所以图的正本永远是 .svg，
再配一个 .html 预览页，方便在对话里直接看、在手机上放大看。

用法:
    python tools/svg_to_html.py docs/figures/xxx.svg
    python tools/svg_to_html.py docs/figures/xxx.svg --title "标题" --desc "说明"
"""
import argparse
import pathlib


def build(svg: str, title: str, desc: str) -> str:
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
body{{margin:0;padding:24px;background:#F7F9FB;
  font-family:"Microsoft YaHei",system-ui,-apple-system,sans-serif}}
.wrap{{background:#fff;border:1px solid #D6DEE5;border-radius:12px;
  padding:16px;max-width:1280px;margin:0 auto;overflow:auto}}
h1{{font-size:16px;font-weight:500;color:#2C2C2A;margin:0 0 4px}}
p{{font-size:13px;color:#5F5E5A;margin:0 0 12px;line-height:1.6}}
svg{{display:block;width:100%;height:auto}}
</style></head><body><div class="wrap">
<h1>{title}</h1>
<p>{desc}</p>
{svg}
</div></body></html>
"""


def main():
    ap = argparse.ArgumentParser(description="SVG → 自包含 HTML 预览页")
    ap.add_argument("src", help="输入 .svg 路径")
    ap.add_argument("--title", default="")
    ap.add_argument("--desc", default="")
    ap.add_argument("-o", "--out", default="")
    a = ap.parse_args()

    src = pathlib.Path(a.src).resolve()
    svg = src.read_text(encoding="utf-8")
    title = a.title or src.stem
    out = pathlib.Path(a.out).resolve() if a.out else src.with_name(src.stem + "_预览.html")
    out.write_text(build(svg, title, a.desc), encoding="utf-8")
    print(f"OK {out}  ({out.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
