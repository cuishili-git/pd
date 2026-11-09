# -*- coding: utf-8 -*-
"""一键生成本仓库的「图文讲解」配套图。

产出（全部写到 docs/figures/）：
  模块1_低压触发链.svg / .png     从整机总图裁出
  模块2_高压充电级.svg / .png     从整机总图裁出
  模块3_雪崩输出级.svg / .png     从整机总图裁出
  参数曲线_充电与放电.svg / .png   按 calc_params.py 的数值画 T 节点波形
  参数曲线_微分尖峰.svg / .png     100pF / 470pF 尖峰对比

用法：
    python tools/make_figures.py            # 只生成 SVG
    python tools/make_figures.py --png      # 生成 SVG 后再渲染 PNG（需 Edge/Chrome）

原理：裁剪只改 viewBox 与 width/height，原 SVG 元素一个字不动，
所以局部图的接线与主图 100% 一致，不会引入新的画错。
"""
import math
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FIG = os.path.join(ROOT, "docs", "figures")
MASTER = os.path.join(FIG, "雪崩源_完整接线图_100Hz.svg")
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

FONT = "Microsoft YaHei, PingFang SC, Arial, sans-serif"
INK = "#1F2933"
MUTED = "#5B6770"
RED = "#D64545"
ORANGE = "#E8871A"
PURPLE = "#7B5BD6"
GREEN = "#1E9E6A"
GRID = "#E3E9EF"


def save(name, body, w, h, viewbox=None):
    vb = viewbox or f"0 0 {w} {h}"
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vb}" '
           f'width="{w}" height="{h}">\n{body}\n</svg>\n')
    path = os.path.join(FIG, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(svg)
    print("SVG", name, f"{w}x{h}")
    return path


def txt(x, y, s, size=12, fill=INK, anchor="start", weight="normal"):
    return (f'<text x="{x}" y="{y}" text-anchor="{anchor}" font-family="{FONT}" '
            f'font-size="{size}" font-weight="{weight}" fill="{fill}">{s}</text>')


# ---------------------------------------------------------------- 分区裁剪
def crop_modules():
    src = open(MASTER, encoding="utf-8").read()
    # 去掉根标签，只留内部元素；白底 rect 保留（覆盖整个裁剪区）
    inner = src[src.index(">") + 1: src.rindex("</svg>")]
    # patches：用分区底色盖掉「跨区元素被裁一半」的残字 / 说明线，
    # 再把被边界切掉的元件标注补画一份完整的。只动标注，不动任何接线。
    p2 = f"""
<!-- 盖掉属于①区的跨区布线说明（y=590 文字 + y=600 横线在本区被截断） -->
<rect x="480" y="575" width="430" height="50" fill="#FFFFFF"/>
<rect x="490" y="575" width="400" height="50" fill="#FFF4F4"/>
<!-- 10MΩ 标注原居中于 x=880，右半越出裁剪边界，补画一份完整且略左移 -->
<rect x="826" y="442" width="84" height="40" fill="#FFF4F4"/>
<text x="868" y="458" text-anchor="middle" font-family="{FONT}" font-size="12"
      font-weight="700" fill="{INK}">10MΩ / 1W</text>
<text x="868" y="474" text-anchor="middle" font-family="{FONT}" font-size="11"
      fill="{MUTED}">泄放（常接）</text>
"""
    p3 = """
<!-- 盖掉②区「10MΩ / 1W」「泄放（常接）」被裁进左边缘的半截字 -->
<rect x="900" y="435" width="10" height="55" fill="#FFFFFF"/>
<rect x="910" y="435" width="28" height="55" fill="#F4F9FF"/>
<!-- 遮罩压住了③区分区框左边线，补回来，避免看起来像断线 -->
<line x1="910" y1="435" x2="910" y2="490" stroke="#C9DCF0" stroke-width="1.5"/>
"""
    crops = [
        ("模块1_低压触发链.svg", 30, 90, 450, 645, ""),
        ("模块2_高压充电级.svg", 480, 90, 430, 645, p2),
        ("模块3_雪崩输出级.svg", 900, 90, 350, 645, p3),
    ]
    out = []
    for name, x, y, w, h, patches in crops:
        body = (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="#FFFFFF"/>\n'
                + inner + patches
                + f'\n<rect x="{x + 1}" y="{y + 1}" width="{w - 2}" height="{h - 2}" '
                  f'fill="none" stroke="#C9D3DC" stroke-width="2"/>')
        out.append(save(name, body, w, h, f"{x} {y} {w} {h}"))
    return out


# ------------------------------------------------------------ 曲线：充电/放电
def wave_charge():
    W, H = 960, 500
    x0, x1 = 90, 900          # 0 ~ 10 ms
    y0, y1 = 80, 380          # 200 V ~ 0 V
    T_ms, Vmax = 10.0, 200.0
    V_T, tau_ms = 190.0, 0.470

    def X(t):
        return x0 + t / T_ms * (x1 - x0)

    def Y(v):
        return y1 - v / Vmax * (y1 - y0)

    b = [f'<rect x="0" y="0" width="{W}" height="{H}" fill="#FFFFFF"/>']
    b.append(txt(480, 38, "T 节点电压 · 一个周期（100 Hz，10 ms）", 20, INK, "middle", "bold"))
    b.append(txt(480, 62, "47 kΩ 慢慢充 → 保持 → 雪崩瞬间被 50 Ω 抽空 → 重新充电", 12, MUTED, "middle"))

    # 网格 + 刻度
    for v in (0, 50, 100, 126, 150, 200):
        yy = Y(v)
        b.append(f'<line x1="{x0}" y1="{yy:.1f}" x2="{x1}" y2="{yy:.1f}" '
                 f'stroke="{GRID}" stroke-width="1" stroke-dasharray="4 4"/>')
        b.append(txt(x0 - 12, yy + 4, f"{v}V", 11, MUTED, "end"))
    for t in (0, 1, 2, 2.35, 4, 6, 8, 10):
        xx = X(t)
        b.append(f'<line x1="{xx:.1f}" y1="{y0}" x2="{xx:.1f}" y2="{y1}" '
                 f'stroke="{GRID}" stroke-width="1" stroke-dasharray="4 4"/>')
        b.append(txt(xx, y1 + 20, f"{t:g}", 11, MUTED, "middle"))
    b.append(txt((x0 + x1) / 2, y1 + 42, "时间 / ms", 12, MUTED, "middle"))
    b.append(f'<line x1="{x0}" y1="{y0}" x2="{x0}" y2="{y1}" stroke="{INK}" stroke-width="1.5"/>')
    b.append(f'<line x1="{x0}" y1="{y1}" x2="{x1}" y2="{y1}" stroke="{INK}" stroke-width="1.5"/>')

    # 充电指数曲线（稳态目标 190V），到 9.75ms
    pts = []
    for i in range(201):
        t = 9.75 * i / 200
        v = V_T * (1 - math.exp(-t / tau_ms))
        pts.append(f"{X(t):.1f},{Y(v):.1f}")
    b.append(f'<polyline points="{" ".join(pts)}" fill="none" stroke="{RED}" stroke-width="3"/>')

    # 雪崩瞬间垂直跌落 + 下一周期起点
    b.append(f'<line x1="{X(9.75):.1f}" y1="{Y(V_T):.1f}" x2="{X(9.75):.1f}" '
             f'y2="{Y(0.21):.1f}" stroke="{RED}" stroke-width="3"/>')
    b.append(f'<line x1="{X(9.75):.1f}" y1="{Y(0.21):.1f}" x2="{X(10):.1f}" '
             f'y2="{Y(0.21):.1f}" stroke="{RED}" stroke-width="3" stroke-dasharray="6 4"/>')

    # 标注
    b.append(f'<line x1="{X(0.47):.1f}" y1="{y0}" x2="{X(0.47):.1f}" y2="{Y(120):.1f}" '
             f'stroke="{ORANGE}" stroke-width="1.5" stroke-dasharray="5 4"/>')
    # 标注分三档高度错开，避免全挤在 y≈95 一条线上
    b.append(txt(X(0.47) + 10, y0 + 40, "1τ = 470µs → 120V (63.2%)", 11, ORANGE))
    b.append(txt(X(2.35) + 10, y0 + 60, "5τ = 2.35ms，充到 99.3%", 11, ORANGE))
    b.append(txt(X(4.8), y0 + 34, "稳态 V_T = 190V（47kΩ 平均压掉 10V）", 12, RED, "middle", "bold"))
    b.append(txt(X(9.75) - 8, y0 + 34, "雪崩！190V → 0.21V", 12, RED, "end", "bold"))
    b.append(txt(X(9.75) - 8, y0 + 52, "峰值 3.8A / 500ns", 11, MUTED, "end"))
    b.append(txt(x0 + 20, y1 - 28, "V(t) = V_T·(1 − e^(−t/τ))，τ = R·C = 47kΩ × 10nF", 11, MUTED))

    # 底部结论条
    b.append(f'<rect x="{x0}" y="430" width="{x1 - x0}" height="46" rx="8" fill="#F7F9FB" stroke="#D6DEE5"/>')
    b.append(txt(x0 + 16, 450, "周期 10ms = 20.8τ ✅ 每次都充满；旧版 1kHz 只有 2.1τ，T 节点塌到 ≈135V", 12, INK))
    b.append(txt(x0 + 16, 468, "放电走「ZTX415 + 50Ω」，不是 47kΩ；47kΩ 上游接着电源，只负责慢慢灌。", 11, MUTED))
    return save("参数曲线_充电与放电.svg", "\n".join(b), W, H)


# ------------------------------------------------------------ 曲线：微分尖峰
def wave_trigger():
    W, H = 960, 500
    x0, x1 = 90, 900          # 0 ~ 16 µs
    y0, y1 = 80, 360          # 12 V ~ 0 V
    T_us, Vmax = 16.0, 12.0

    def X(t):
        return x0 + t / T_us * (x1 - x0)

    def Y(v):
        return y1 - v / Vmax * (y1 - y0)

    b = [f'<rect x="0" y="0" width="{W}" height="{H}" fill="#FFFFFF"/>']
    b.append(txt(480, 38, "基极触发尖峰 · 微分电容只改宽度、不改峰值", 20, INK, "middle", "bold"))
    b.append(txt(480, 62, "NE555 输出 12V 上升沿 → 100pF 串 / 10kΩ 并的一阶高通", 12, MUTED, "middle"))

    for v in (0, 2, 4, 6, 8, 10, 12):
        yy = Y(v)
        b.append(f'<line x1="{x0}" y1="{yy:.1f}" x2="{x1}" y2="{yy:.1f}" '
                 f'stroke="{GRID}" stroke-width="1" stroke-dasharray="4 4"/>')
        b.append(txt(x0 - 12, yy + 4, f"{v}V", 11, MUTED, "end"))
    for t in (0, 1, 2, 3, 4.7, 6, 8, 10, 12, 14, 16):
        xx = X(t)
        b.append(f'<line x1="{xx:.1f}" y1="{y0}" x2="{xx:.1f}" y2="{y1}" '
                 f'stroke="{GRID}" stroke-width="1" stroke-dasharray="4 4"/>')
        b.append(txt(xx, y1 + 20, f"{t:g}", 11, MUTED, "middle"))
    b.append(txt((x0 + x1) / 2, y1 + 42, "时间 / µs", 12, MUTED, "middle"))
    b.append(f'<line x1="{x0}" y1="{y0}" x2="{x0}" y2="{y1}" stroke="{INK}" stroke-width="1.5"/>')
    b.append(f'<line x1="{x0}" y1="{y1}" x2="{x1}" y2="{y1}" stroke="{INK}" stroke-width="1.5"/>')

    def curve(tau, color, width, dash=""):
        pts = []
        for i in range(241):
            t = 16.0 * i / 240
            v = 12.0 * math.exp(-t / tau)
            pts.append(f"{X(t):.1f},{Y(v):.1f}")
        d = f' stroke-dasharray="{dash}"' if dash else ""
        return f'<polyline points="{" ".join(pts)}" fill="none" stroke="{color}" stroke-width="{width}"{d}/>'

    b.append(curve(0.1, "#B9A8E8", 2))                 # 10pF
    b.append(curve(4.7, "#B08BE0", 2.5, "7 5"))        # 470pF 加强档
    b.append(curve(1.0, PURPLE, 3.5))                  # 100pF 定稿

    # 峰值公共点。说明文字下移到 y=105 且右移，避开副标题与 470pF 虚线
    b.append(f'<circle cx="{X(0):.1f}" cy="{Y(12):.1f}" r="5" fill="{PURPLE}"/>')
    b.append(txt(220, 105, "三条曲线峰值都是 12V（边沿瞬间 C ≈ 短路）", 12, PURPLE, weight="bold"))

    b.append(txt(X(3) + 6, y1 - 14, "100pF：3τ = 3µs 归零", 11, PURPLE))
    b.append(txt(X(8.5), y1 - 80, "470pF：τ=4.7µs，拖尾 14µs", 11, "#8E63CC"))
    b.append(txt(X(0.6), y1 - 50, "10pF：0.3µs 就没了", 11, "#9A8ABE"))

    # 图例 + 底部结论（下移，给 x 轴「时间 / µs」留位置）
    b.append(f'<rect x="{x0}" y="415" width="{x1 - x0}" height="70" rx="8" fill="#F7F9FB" stroke="#D6DEE5"/>')
    b.append(txt(x0 + 16, 437, "取值边界：太小 → 注入电荷不足点不着火；太大 → B-E 长时间导通、负尖峰能量涨 100 倍", 12, INK))
    b.append(txt(x0 + 16, 457, "100pF：τ=1µs、Q=1.2nC、½CV²=7.2nJ　｜　470pF：τ=4.7µs、Q=5.64nC、½CV²=33.8nJ（点火失败时换）", 11, MUTED))
    b.append(txt(x0 + 16, 477, "与重复频率无关：微分只看方波边沿。1kHz → 100Hz 只换定时电容 Ct，这颗不动。", 11, MUTED))
    return save("参数曲线_微分尖峰.svg", "\n".join(b), W, H)


# ---------------------------------------------------------------- 渲染 PNG
def render(svg_paths, scale=2):
    script = os.path.join(HERE, "svg2png.py")
    for p in svg_paths:
        png = os.path.splitext(p)[0] + ".png"
        subprocess.run([sys.executable, script, p, png, str(scale)], check=True)


def main():
    os.makedirs(FIG, exist_ok=True)
    paths = crop_modules()
    paths.append(wave_charge())
    paths.append(wave_trigger())
    if "--png" in sys.argv:
        print("\n--- 渲染 PNG ---")
        render(paths, 2)
    print("\n完成。图文讲解见 docs/05-电路图图文讲解.md")


if __name__ == "__main__":
    main()
