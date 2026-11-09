# -*- coding: utf-8 -*-
"""局放信号模拟源 V0 —— 全部元件参数一键重算。

用法（仓库任意目录下）:
    python tools/calc_params.py                 # 按定稿参数打印完整计算书
    python tools/calc_params.py --compare      # 额外打印变参对比（换电容 / 换频率）
    python tools/calc_params.py --json         # 输出 JSON，便于别的脚本引用

想试别的取值，直接改下面 P = Params(...) 里的数字再跑一次。
所有公式与推导见 docs/04-元件参数计算手册.md。
"""
import argparse
import json
import math
from dataclasses import asdict, dataclass


@dataclass
class Params:
    # —— 高压侧 ——
    V_hv: float = 200.0        # 升压模块空载设定值 V（200 起步 / 250 封顶）
    C_store: float = 10e-9     # 储能电容 F，10nF(103)/1kV
    R_chg: float = 47e3        # 充电限流 / 淬灭电阻 Ω
    R_bleed: float = 10e6      # 断电泄放电阻 Ω
    R_load: float = 50.0       # 发射极负载 Ω

    # —— NE555 定时侧 ——
    V_cc: float = 12.0
    R1: float = 4.7e3
    R2: float = 68e3
    Ct: float = 100e-9         # 定时电容 F，100nF(104)

    # —— 触发侧 ——
    C_trig: float = 100e-12    # 微分电容 F，100pF(101)
    R_pd: float = 10e3         # 基极下拉 Ω

    # —— 555 内部 3 个 5k 分压电阻（用于 5 脚抗扰电容计算）——
    R_555: float = 5e3

    # —— 接收侧临时检波探头 ——
    C_det: float = 100e-12
    R_det: float = 1e6


def si(v, unit=""):
    """把数值格式化成工程记数（自动选 µ/n/m/k/M 前缀）。"""
    a = abs(v)
    for p, s in ((1e9, "G"), (1e6, "M"), (1e3, "k"), (1, ""),
                 (1e-3, "m"), (1e-6, "µ"), (1e-9, "n"), (1e-12, "p")):
        if a >= p or p == 1e-12:
            return f"{v / p:.4g} {s}{unit}"
    return f"{v:.4g} {unit}"


def section(title):
    print("\n" + "=" * 68)
    print(title)
    print("=" * 68)


def calc(p: Params):
    r = {}

    # ---------- 1. NE555 无稳态 ----------
    # 充电 0.693*(R1+R2)*Ct（1/3 -> 2/3 VCC），放电 0.693*R2*Ct（2/3 -> 1/3 VCC）
    t_chg_555 = math.log(2) * (p.R1 + p.R2) * p.Ct
    t_dis_555 = math.log(2) * p.R2 * p.Ct
    T_555 = t_chg_555 + t_dis_555
    f = 1.0 / T_555
    duty = (p.R1 + p.R2) / (p.R1 + 2 * p.R2)
    # 常用近似式，用来和精确式对照
    f_approx = 1.44 / ((p.R1 + 2 * p.R2) * p.Ct)
    out_dc = p.V_cc * duty

    section("1 · NE555 震荡（决定重复率，与雪崩级无关）")
    print(f"  Ct              = {si(p.Ct, 'F')}   ({(p.Ct * 1e9):.0f} nF)")
    print(f"  充电段 ln2(R1+R2)Ct = {si(t_chg_555, 's')}")
    print(f"  放电段 ln2·R2·Ct    = {si(t_dis_555, 's')}")
    print(f"  周期 T = 1.44/((R1+2R2)Ct) = {si(T_555, 's')}")
    print(f"  频率 f = {f:.2f} Hz   （近似式 {f_approx:.2f} Hz）")
    print(f"  占空比 = (R1+R2)/(R1+2R2) = {duty * 100:.1f}%")
    print(f"  3 脚直流档读数 = Vcc × 占空比 = {out_dc:.2f} V   ← Step 1 判据")
    r.update(f=f, T_555=T_555, duty=duty, out_dc=out_dc,
             t_chg_555=t_chg_555, t_dis_555=t_dis_555)

    # ---------- 2. 高压充电级：稳态自洽解 ----------
    # 每个脉冲放掉 Q = C_store * V_T，平均雪崩电流 I = C*V_T*f
    # 静态还有 V_T/R_bleed 的泄放电流
    # V_T = V_hv - (C*V_T*f + V_T/R_bleed) * R_chg
    #   => V_T = V_hv / (1 + R_chg*(C*f + 1/R_bleed))
    denom = 1.0 + p.R_chg * (p.C_store * f + 1.0 / p.R_bleed)
    V_T = p.V_hv / denom
    I_aval = p.C_store * V_T * f          # 雪崩平均电流
    I_bleed = V_T / p.R_bleed             # 静态泄放电流
    I_total = I_aval + I_bleed
    V_drop = I_total * p.R_chg            # 47k 两端压降（验源判据）
    V_drop_static = (p.V_hv / (1 + p.R_chg / p.R_bleed)) / p.R_bleed * p.R_chg

    tau_chg = p.R_chg * p.C_store
    five_tau = 5 * tau_chg
    ratio = T_555 / tau_chg
    V_at_5tau = p.V_hv * (1 - math.exp(-5))

    section("2 · 高压充电级（47kΩ + 10nF + 10MΩ）")
    print(f"  充电时间常数 τ = R_chg × C_store = {si(tau_chg, 's')}")
    print(f"  工程「充满」5τ = {si(five_tau, 's')}  (达到 99.3%，{V_at_5tau:.1f} V)")
    print(f"  周期 / τ = {ratio:.1f} τ   {'✅ 充足（≥20τ）' if ratio >= 20 else '❌ 充不满'}")
    print(f"  稳态自洽解 V_T = V_hv / (1 + R(C·f + 1/R_bleed)) = {V_T:.1f} V")
    print(f"    雪崩平均电流 I = C·V_T·f       = {si(I_aval, 'A')}")
    print(f"    静态泄放电流   = V_T / R_bleed = {si(I_bleed, 'A')}")
    print(f"  47kΩ 压降（雪崩时） = {V_drop:.2f} V   ← 验源判据")
    print(f"  47kΩ 压降（静态）   ≈ {V_drop_static:.2f} V   （源关掉时）")
    print(f"  跳变倍数 ≈ {V_drop / V_drop_static:.1f}×")
    r.update(V_T=V_T, tau_chg=tau_chg, five_tau=five_tau, ratio=ratio,
             I_aval=I_aval, I_bleed=I_bleed, V_drop=V_drop,
             V_drop_static=V_drop_static)

    # ---------- 3. 单脉冲能量 / 峰值 ----------
    Q_pulse = p.C_store * V_T
    E_pulse = 0.5 * p.C_store * V_T ** 2
    I_peak = V_T / p.R_load
    tau_dis = p.R_load * p.C_store
    P_avg = E_pulse * f
    # 雪崩导通瞬间的分压：电源还在，但 47k 只给得出这么点电流
    V_T_on = p.V_hv * p.R_load / (p.R_chg + p.R_load)
    I_supply_on = p.V_hv / (p.R_chg + p.R_load)

    section("3 · 单脉冲：能量、峰值电流、放电时间")
    print(f"  每脉冲放掉电荷 Q = C·V_T       = {si(Q_pulse, 'C')}")
    print(f"  单脉冲能量 ½CV_T²              = {si(E_pulse, 'J')}")
    print(f"  峰值放电电流 V_T / R_load      = {si(I_peak, 'A')}")
    print(f"  放电时间常数 R_load·C          = {si(tau_dis, 's')}")
    print(f"  50Ω 瞬时峰值功率 V_T²/R        = {si(V_T ** 2 / p.R_load, 'W')} (仅 ns~µs)")
    print(f"  平均功率 E·f                   = {si(P_avg, 'W')}   ← 选型看这个")
    print(f"  雪崩导通瞬间：V_T 塌到 {V_T_on:.3f} V，")
    print(f"                 电源经 47k 只补得进 {si(I_supply_on, 'A')}")
    print(f"                 ≈ {I_peak / I_supply_on:.0f} 倍差距 ⇒ 低于维持电流 I_H ⇒ 自动关断（限流淬灭）")
    r.update(Q_pulse=Q_pulse, E_pulse=E_pulse, I_peak=I_peak,
             tau_dis=tau_dis, P_avg=P_avg, V_T_on=V_T_on)

    # ---------- 4. 触发微分器 ----------
    tau_trig = p.R_pd * p.C_trig
    Q_trig = p.C_trig * p.V_cc
    E_neg = 0.5 * p.C_trig * p.V_cc ** 2
    three_tau = 3 * tau_trig

    section("4 · 触发微分器（100pF 串 + 10kΩ 下拉）")
    print(f"  尖峰时间常数 τ = R_pd × C_trig = {si(tau_trig, 's')}")
    print(f"  峰值 = Vcc = {p.V_cc:.1f} V（与 C 无关：边沿瞬间电容≈短路）")
    print(f"  3τ 归零 = {si(three_tau, 's')}；占周期 {three_tau / T_555 * 100:.4f}%")
    print(f"  注入电荷 Q = C_trig × Vcc     = {si(Q_trig, 'C')}")
    print(f"  下降沿负尖峰能量 ½CVcc²       = {si(E_neg, 'J')}（太小，暂不用钳位二极管）")
    print(f"  基极静态电流上限 Vcc/R_pd     = {si(p.V_cc / p.R_pd, 'A')}")
    r.update(tau_trig=tau_trig, Q_trig=Q_trig, E_neg=E_neg, three_tau=three_tau)

    # ---------- 5. 断电泄放 ----------
    tau_bleed = p.R_bleed * p.C_store
    section("5 · 断电泄放（10MΩ 安全阀）")
    print(f"  τ = R_bleed × C_store = {si(tau_bleed, 's')}")
    print(f"  5τ = {si(5 * tau_bleed, 's')} → 残压 < 5V（安全规程「断电等 0.5s」的来历）")
    print(f"  正常带电时泄放功耗 V_T²/R = {si(V_T ** 2 / p.R_bleed, 'W')}")
    r.update(tau_bleed=tau_bleed)

    # ---------- 6. 其余电容 ----------
    # 555 的 5 脚：内部 3 个 5k 串联，CTRL 在 2/3VCC 处，等效 R = 5k || (5k+5k)
    R_eq_ctrl = p.R_555 * (2 * p.R_555) / (p.R_555 + 2 * p.R_555)
    fc_ctrl = 1 / (2 * math.pi * R_eq_ctrl * 10e-9)
    E_ct = 0.5 * p.Ct * (2 / 3 * p.V_cc) ** 2
    E_ct_swing = 0.5 * p.Ct * ((2 / 3 * p.V_cc) ** 2 - (1 / 3 * p.V_cc) ** 2)
    tau_det = p.R_det * p.C_det

    section("6 · 其余电容位")
    print(f"  Ct 在 1/3↔2/3 Vcc 之间摆动（{p.V_cc / 3:.0f}V ↔ {2 * p.V_cc / 3:.0f}V）")
    print(f"    充到 8V 时储能 ½Ct·(2/3Vcc)² = {si(E_ct, 'J')}")
    print(f"    每周期实际吞吐              = {si(E_ct_swing, 'J')}（全耗在 555 内部放电管）")
    print(f"  5 脚抗扰 10nF：内部等效 R_eq = 5k∥10k = {si(R_eq_ctrl, 'Ω')}")
    print(f"    低通截止频率 fc = 1/(2π·R_eq·C) = {si(fc_ctrl, 'Hz')}  ≫ 100Hz，只滤高频干扰")
    print(f"  检波探头 100pF ∥ 1MΩ：τ = {si(tau_det, 's')}")
    print(f"    ≫ ns 级脉冲（能展宽成可测直流），≪ {si(T_555, 's')} 周期（不会跨周期累积）")
    r.update(R_eq_ctrl=R_eq_ctrl, fc_ctrl=fc_ctrl, E_ct=E_ct,
             E_ct_swing=E_ct_swing, tau_det=tau_det)

    # ---------- 7. 电阻应力校核 ----------
    section("7 · 电阻应力校核（判断 1/4W 能不能用）")
    rows = [
        ("47k 充电/淬灭", I_total ** 2 * p.R_chg, p.V_hv ** 2 / p.R_chg, V_T, "耐压顶格 → 串联或换 2W"),
        ("10M 泄放", V_T ** 2 / p.R_bleed, p.V_hv ** 2 / p.R_bleed, V_T, "功耗够、长期耐压卡边 → 串联"),
        ("10k 基极下拉", (p.V_cc ** 2 / p.R_pd) * (three_tau / T_555), p.V_cc ** 2 / p.R_pd, p.V_cc, "12V 侧，直接用"),
        ("R1 4.7k", (p.V_cc / 3) ** 2 / p.R1, p.V_cc ** 2 / p.R1, p.V_cc, "12V 侧，直接用"),
        ("R2 68k", (p.V_cc / 3) ** 2 / p.R2, p.V_cc ** 2 / p.R2, p.V_cc, "12V 侧，直接用"),
        ("50Ω 负载", P_avg, V_T ** 2 / p.R_load, V_T, "平均功率极小，但需脉冲耐受"),
    ]
    print(f"  {'位置':<16}{'正常/平均':>14}{'最坏/峰值':>14}{'跨压':>10}   判定")
    for name, normal, worst, voltage, note in rows:
        print(f"  {name:<16}{si(normal, 'W'):>14}{si(worst, 'W'):>14}{si(voltage, 'V'):>10}   {note}")
    print("  ※ 1/4W 色环电阻额定工作电压通常 200~250V；T 节点长期 190V，")
    print("    问题在「耐压」不在「瓦数」。零采购方案：47k→4×12k 串联、10M→2×5.1M 串联。")

    # ---------- 8. 电容耐压与储能对照 ----------
    section("8 · 电容位速查（丝印别拿混）")
    print(f"  {'位置':<20} {'容值':>9}  {'编码':>5}  {'实际跨压':>8}   最低耐压")
    caps = [
        ("储能（T 节点）", p.C_store, "103", V_T, "≥630V，推荐 1kV"),
        ("NE555 定时 Ct", p.Ct, "104", 2 / 3 * p.V_cc, "≥16V"),
        ("触发微分", p.C_trig, "101", p.V_cc, "≥50V"),
        ("5 脚抗扰（可选）", 10e-9, "103", 2 / 3 * p.V_cc, "≥16V"),
        ("12V 去耦", 100e-9, "104", p.V_cc, "≥16V"),
        ("检波探头", p.C_det, "101", 0.1, "≥50V"),
    ]
    for name, c, code, v, rating in caps:
        print(f"  {name:<20} {si(c, 'F'):>9}  {code:>5}  {si(v, 'V'):>8}   {rating}")
    print("  ⚠ 储能位 103/1kV 与定时位 104/50V 耐压差 100 倍，焊反会击穿炸裂。")

    return r


def compare(p: Params):
    """变参对比：换 Ct / 换储能电容 / 换频率，看哪些量会塌。"""
    section("9 · 变参对比（为什么定稿是 100Hz + 103 储能 + 104 定时）")

    print("\n[9.1] 只改定时电容 Ct（决定频率）")
    print(f"  {'Ct':>12}{'f (Hz)':>10}{'周期/τ':>10}{'V_T (V)':>10}{'47k压降':>10}  结论")
    for ct, label in ((10e-9, "103 旧版"), (100e-9, "104 定稿"), (200e-9, "2×104 并联")):
        q = Params(**{**asdict(p), "Ct": ct})
        f2 = 1.44 / ((q.R1 + 2 * q.R2) * q.Ct)
        T2 = 1 / f2
        vt = q.V_hv / (1 + q.R_chg * (q.C_store * f2 + 1 / q.R_bleed))
        drop = (q.C_store * vt * f2 + vt / q.R_bleed) * q.R_chg
        ok = "✅" if T2 / (q.R_chg * q.C_store) >= 20 else "❌ 充不满"
        print(f"  {label:>12}{f2:>10.1f}{T2 / (q.R_chg * q.C_store):>10.1f}{vt:>10.1f}{drop:>10.1f}  {ok}")

    print("\n[9.2] 只改储能电容 C_store（100Hz 固定）—— 越大不等于越强")
    print(f"  {'C_store':>12}{'τ':>10}{'周期/τ':>10}{'V_T (V)':>10}{'单脉冲能量':>14}{'47k压降':>10}")
    for cs, label in ((1e-9, "1nF"), (10e-9, "10nF 定稿"), (100e-9, "100nF 错件")):
        q = Params(**{**asdict(p), "C_store": cs})
        f2 = 1.44 / ((q.R1 + 2 * q.R2) * q.Ct)
        tau = q.R_chg * cs
        vt = q.V_hv / (1 + q.R_chg * (cs * f2 + 1 / q.R_bleed))
        ep = 0.5 * cs * vt ** 2
        drop = (cs * vt * f2 + vt / q.R_bleed) * q.R_chg
        print(f"  {label:>12}{si(tau, 's'):>10}{1 / f2 / tau:>10.1f}{vt:>10.1f}{si(ep, 'J'):>14}{drop:>10.1f}")

    print("\n[9.3] 只改微分电容 C_trig（峰值恒为 12V，只有宽度变）")
    print(f"  {'C_trig':>12}{'τ':>10}{'3τ归零':>10}{'注入电荷':>12}{'负尖峰能量':>14}")
    for ctr, label in ((10e-12, "10pF"), (100e-12, "100pF 定稿"), (470e-12, "470pF 加强"), (10e-9, "10nF 过大")):
        tau = p.R_pd * ctr
        print(f"  {label:>12}{si(tau, 's'):>10}{si(3 * tau, 's'):>10}"
              f"{si(ctr * p.V_cc, 'C'):>12}{si(0.5 * ctr * p.V_cc ** 2, 'J'):>14}")


def main():
    ap = argparse.ArgumentParser(description="局放信号源 V0 参数计算")
    ap.add_argument("--compare", action="store_true", help="额外打印变参对比")
    ap.add_argument("--json", action="store_true", help="只输出 JSON")
    a = ap.parse_args()

    p = Params()
    if a.json:
        # 静默计算后输出 JSON
        import contextlib
        import io
        with contextlib.redirect_stdout(io.StringIO()):
            r = calc(p)
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return

    print("局放信号模拟源 V0 · 参数计算书")
    print("定稿：ZTX415 ｜ 200V 起步 ｜ 100Hz(Ct=104) ｜ 储能 10nF/1kV(103)")
    print("改数值请编辑本文件顶部的 Params(...)，公式推导见 docs/04-元件参数计算手册.md")
    r = calc(p)
    if a.compare:
        compare(p)
    print("\n" + "=" * 68)
    print("一句话：47k 慢慢灌、10nF 瞬间放、10k 撤点火、10M 断电放净；τ=RC，5τ 算充满。")
    print("=" * 68)
    return r


if __name__ == "__main__":
    main()
