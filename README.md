# pd · 局放信号模拟源（V0）

一个人、一块洞洞板、不用示波器，从零做出能发出 UHF 脉冲的局放信号源，并且能自己证明它真的在发。

这是「GIS 局放手持式检测仪」项目里的**模拟源子项目**。主设备（超外差接收机）还没做到能联调的程度，所以这一版把目标砍到最小：**源在发脉冲 + 检波能数到脉冲**。相位、锁相、PRPD、幅度精调一概不碰。

> ⚠️ 电路含 **200 V 直流高压**和升压模块内部 µF 级储能。不是玩具电路，动手前请先读 [安全规程](docs/00-新人教程.md#6-安全规程每次上电前默读)。

---

## 今天从哪开始

**只做 Step 1，完全不碰 200 V**：高压模块先别接 12 V，只在面包板上插 NE555，用万用表量三个数：

| 量哪里 | 正常值 |
|---|---|
| 12 V 适配器输出 | ≈12.0 V |
| NE555 的 4 脚（RST）对 GND | ≈12.0 V |
| **NE555 的 3 脚对 GND（直流档）** | **≈6 V**（12 V 方波占空比一半） |

3 脚读到 6 V 就是 ≈100 Hz 起振了，再进 Step 2 空载调 200 V。发烫、冒味、3 脚恒高恒低 → 立刻断电。

---

## 文档导航

| 文档 | 内容 |
|---|---|
| [**00 · 新人教程（从这里读）**](docs/00-新人教程.md) | 心智模型、整条电路、每个元件为什么在、参数怎么算、四步上电、验源判据、故障表、纠错记录 |
| [01 · 上电验收卡](docs/01-上电验收卡.md) | 分步 × 打勾 × 判据，动手时摊在桌上 |
| [02 · 模拟源子项目](docs/02-模拟源子项目.md) | V0–V3 完整方案、链路预算、器件清单与原理 |
| [03 · 参数推导与踩坑 FAQ](docs/03-参数推导与踩坑FAQ.md) | 「为什么」深入版：下拉电阻、钳位 0.8 V、淬灭、双端口关断、τ 与 5τ |
| [**04 · 元件参数计算手册**](docs/04-元件参数计算手册.md) | **7 个电容位 + 6 个电阻位逐个算**：公式 → 代入 → 结果 → 边界，附可重算脚本 |
| [**05 · 电路图图文讲解**](docs/05-电路图图文讲解.md) | 整机图拆成三块逐根线讲，含充电波形 / 微分尖峰曲线与跨区连线表 |
| [figures/](docs/figures/) | 接线图（SVG 可编辑 / PNG 可直接打印 / HTML 可缩放） |

**看图顺序**：[完整接线图 100Hz](docs/figures/雪崩源_完整接线图_100Hz.png)（照着焊）→ [**05 图文讲解**](docs/05-电路图图文讲解.md)（看不懂总图就从这里逐块拆）→ [ZTX415 雪崩级单张版](docs/figures/ZTX415_雪崩级接线图_单张版.png) → [引脚专图](docs/figures/ZTX415_引脚与接线专图.png)（脚位拿不准才翻）。

---

## HTML 博客版（浏览器直接看）

上面那些 `.md` 是**源文档**；仓库另有一套由它们编译出来的**静态 HTML 博客**，给人读而不是给 GitHub 渲染 Markdown：

| 入口 | 说明 |
|---|---|
| [`index.html`](index.html) | 博客首页，6 篇文章卡片 + 版本信息 |
| [`blog/00-新人教程.html`](blog/00-新人教程.html) | 从主教程开始读 |
| `blog/01…05-*.html` | 验收卡、方案、FAQ、计算手册、图文讲解 |

每篇都带**左侧目录、上一篇/下一篇、表格与接线图**，公式用仓库自带的轻量渲染器排版（分式 / 上下标 / 希腊字母），**不依赖任何 CDN，离线双击也能看**。图片仍引用 `docs/figures/`，不复制第二份。

重新生成（改完 `.md` 后跑一次即可）：

```bash
cd D:/workbuddy/docs/pd
node tools/make_blog.js
```

`tools/vendor/marked.cjs` 已随仓库带上，构建期零依赖、运行时零依赖。若要变成在线博客：GitHub 仓库 **Settings → Pages → Build from `main` / `(root)`**，保存后约 1 分钟即可访问 `https://cuishili-git.github.io/pd/`（Pages 认 `index.html`，与仓库页显示 README 互不冲突）。

---

## 当前硬件版本（2026-11-09 定稿）

| 项 | 值 |
|---|---|
| 雪崩管 | ZTX415（E-Line，**印字面朝自己：左 C · 中 B · 右 E**，与常见 TO-92 相反） |
| 高压 | 45–390 V 模块，**200 V 起步 / 250 V 封顶**（`V_CBO 260 V` 是绝对最大值，早期 270 V 方案已作废） |
| 供电 | 12 V 适配器直供；XL6009、UF4007 本轮不接 |
| 重复率 | NE555 ≈102 Hz，`Ct = 100 nF (104)`；50 Hz 档用两颗 104 并联 |
| 储能 | **10 nF / 1 kV (103)**，C0G/NP0 首选 —— 绝不能拿 104 顶 |
| 充电 / 淬灭 | 47 kΩ（1/4 W 件可 4×12 kΩ 串联代替） |
| 断电泄放 | 10 MΩ 常接（1/4 W 件可 2×5.1 MΩ 串联代替） |
| 触发 | 100 pF 微分 + 10 kΩ 下拉到 GND；点不着火先换 470 pF |
| 输出 | 50 Ω 下地 + 10 cm 导线天线 |
| 验源判据 | 47 kΩ 压降：静态 ≈1 V → 雪崩时 **≈10 V** |

**一句话口诀**：47 kΩ 慢慢灌、10 nF 瞬间放、10 kΩ 撤点火、10 MΩ 断电放净；τ = RC，5τ 算充满。

---

## 仓库结构

```
pd/
├── README.md                     ← 本页（GitHub 仓库页）
├── index.html                    ★ HTML 博客首页（Pages 入口）
├── blog/                         ★ 6 篇博客文章页（由 docs/*.md 编译）
├── .gitignore
├── docs/
│   ├── 00-新人教程.md             ★ 主教程
│   ├── 01-上电验收卡.md
│   ├── 02-模拟源子项目.md
│   ├── 03-参数推导与踩坑FAQ.md
│   ├── 04-元件参数计算手册.md     ★ 每个数值怎么算
│   ├── 05-电路图图文讲解.md       ★ 总图拆三块逐根线讲
│   └── figures/
│       ├── 雪崩源_完整接线图_100Hz.svg / .png / _预览.html
│       ├── 模块1_低压触发链 / 模块2_高压充电级 / 模块3_雪崩输出级 .svg / .png
│       ├── 参数曲线_充电与放电 / 参数曲线_微分尖峰 .svg / .png
│       ├── ZTX415_雪崩级接线图_单张版.svg / .png
│       ├── ZTX415_引脚与接线专图.svg / .png
│       └── 雪崩脉冲源接线图_V0终版.svg / .png（备份）
└── tools/
    ├── push.sh                   ← 一键推送（SSH-over-443 隧道，免 token）
    ├── ssh-https-proxy.py        ← HTTP CONNECT 隧道，供 OpenSSH ProxyCommand 使用
    ├── calc_params.py            ← 改数值重算全部参数（--compare / --json）
    ├── make_figures.py           ← 一键重生成分区图与参数曲线（--png）
    ├── svg2png.py                ← SVG → 独立 PNG（支持任意 viewBox）
    ├── make_preview.py           ← 生成可缩放网页版
    ├── make_blog.js              ← Markdown → 静态 HTML 博客（离线公式渲染）
    └── vendor/marked.cjs         ← 构建期 Markdown 解析器（随仓库自带）
```

### 参数与配图都能自己重算

```bash
cd D:/workbuddy/docs/pd
python tools/calc_params.py              # 打印完整计算书
python tools/calc_params.py --compare    # 换电容 / 换频率会怎样
python tools/make_figures.py --png       # 重生成 3 张分区图 + 2 张曲线
```

`calc_params.py` 顶部的 `Params(...)` 是唯一输入源，`make_figures.py` 从总图裁剪（不改任何连线）并按同一套公式画曲线，改完跑一遍，文档里的数字就不会和图各说各话。

---

## 怎么再次推送（脚本可直接执行）

本机直连 GitHub 的 22/443 会被 reset，但环境提供本地 HTTP 代理且端口是会话级的。仓库自带隧道脚本，会自动从 `HTTPS_PROXY` 读代理地址，无需 token、无需写死端口。

```bash
# 1. 改完文档后，进入仓库目录
cd D:/workbuddy/docs/pd

# 2. 一键提交 + 推送到 cuishili-git/pd 的 main
bash tools/push.sh

# 只提交不推送（本地验收）
SKIP_PUSH=1 bash tools/push.sh

# 换仓库 / 换分支 / 自定义提交信息
REPO=cuishili-git/pd BRANCH=main MSG="docs: 更新验源判据" bash tools/push.sh
```

脚本做的事（全部只写仓库 **local** git config，不动全局配置）：

1. 检查工作区与 `HTTPS_PROXY`；
2. 配置 `core.sshCommand` = `ssh -p 443 -o ProxyCommand="python tools/ssh-https-proxy.py ssh.github.com 443"`；
3. 配置/校正 `origin` 为 `ssh://git@ssh.github.com:443/<REPO>.git`；
4. 设置提交署名；`git add -A` + `git commit`（无改动则跳过）；
5. `git push origin <BRANCH>`。

前置条件：本机 `~/.ssh/id_ed25519` 已加到 GitHub 账户、Python 3 可用。验证认证：

```bash
ssh -T -p 443 -o ProxyCommand="python tools/ssh-https-proxy.py ssh.github.com 443" git@ssh.github.com
# 应返回：Hi cuishili-git! You've successfully authenticated...
```

---

## 升级路线（每级只加一件事）

| 级 | 加什么 | 验收 |
|---|---|---|
| **V0（当前）** | 检波 + 峰值保持 + PCNT 计数 | 计数率 ≈ 触发率，距离衰减单调 |
| V1 | SAW 带通 / 本振 + 混频 | 关源时干扰被压制 |
| V2 | 电极板 + 过零捕获 + 相位窗 | PRPD 出现竖线（允许漂移） |
| V3 | 电场过零锁相 | 竖线静止、可标定、扫角匀速转圈 |

---

## 免责

本项目记录的是个人 DIY 调试过程，参数来自公开 datasheet / 应用笔记与实算，**不是经过安规认证的产品设计**。200 V 高压、雪崩脉冲的宽带辐射、以及后续接入的射频前端，都可能涉及人身安全与无线电管理要求。请在绝缘台面、单手操作、断电验压的前提下实验，勿用于现场设备或商业用途。
