# -*- coding: utf-8 -*-
"""把接线图 SVG 内嵌成白底、可缩放的预览 HTML（不依赖界面主题变量）。

用法（在仓库任意目录执行均可）:
    python tools/make_preview.py                                   # 默认生成主图预览
    python tools/make_preview.py <输入.svg> <输出.html>
"""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FIG = os.path.join(ROOT, "docs", "figures")

src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(FIG, "雪崩源_完整接线图_100Hz.svg")
dst = sys.argv[2] if len(sys.argv) > 2 else os.path.join(FIG, "雪崩源_完整接线图_预览.html")

title = ("雪崩源完整接线图（100 Hz 版）" if "完整" in os.path.basename(src)
         else "ZTX415 雪崩级接线图（单张版）")

HEAD = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>{TITLE}</title>
<style>
body{margin:0;background:#FFFFFF;color:#1F2933;font-family:"Microsoft YaHei","PingFang SC",Arial,sans-serif}
.bar{padding:12px 20px;background:#F7F9FB;border-bottom:1px solid #D6DEE5;font-size:13px;line-height:1.7}
.bar b{font-size:16px}
.wrap{padding:18px}
svg{width:100%;height:auto;display:block;border:1px solid #D6DEE5;border-radius:8px}
.tip{padding:0 20px 22px;font-size:12px;color:#5B6770;line-height:1.9}
code{background:#F1F4F7;padding:1px 5px;border-radius:4px}
</style></head><body>
<div class="bar"><b>{TITLE}</b> &nbsp;·&nbsp; 200V 起步 / 250V 封顶 ｜ 12V 适配器直供 ｜ NE555 ≈100Hz（Ct=104）<br>
红 = 高压　橙 = 12V　紫 = 触发　绿 = 输出　灰 = GND　｜　● 实心圆点 = 相连；全图零交叉</div>
<div class="wrap">
"""

TAIL = """</div>
<div class="tip">
看图顺序：① 本图（整机接线）→ ② <code>ZTX415_雪崩级接线图_单张版.png</code>（雪崩级特写）→ ③ <code>ZTX415_引脚与接线专图.png</code>（脚位详解与万用表验脚）。<br>
本轮 V0 不用 XL6009 / UF4007；高压区用洞洞板焊接，不插面包板；断电确认 HV &lt; 5V 才装 / 拆管；所有 GND 星形汇到 12V 适配器负极。<br>
同目录有同名 <code>.svg</code>（可编辑）与 <code>.png</code>（可直接打印）；完整教程见仓库 <code>docs/00-新人教程.md</code>。
</div>
</body></html>
"""

svg = io.open(src, encoding="utf-8").read()
html = (HEAD + svg + TAIL).replace("{TITLE}", title)
io.open(dst, "w", encoding="utf-8").write(html)
print("OK", dst, "|", title)
