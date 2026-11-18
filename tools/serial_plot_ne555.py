#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ESP32-P4 NE555 方波采集 · 电脑端串口绘图
==========================================

读 20_adc_ne555_capture 固件输出的 CSV（timestamp_us,raw_adc），
实时显示波形并测量：频率、周期、占空比、高低电平 ADC 值。

依赖安装（一次即可）：
    python -m pip install pyserial matplotlib

用法：
    python tools/serial_plot_ne555.py COM3              # Windows 指定端口
    python tools/serial_plot_ne555.py COM3 --baud 921600
    python tools/serial_plot_ne555.py COM3 --save data.csv
    python tools/serial_plot_ne555.py --list             # 列出所有串口

参数换算（12dB 衰减，Vref≈1.1V，k≈0.25）：
    理论满量程 ≈ 4.4V，但 GPIO 绝对上限 3.3V。
    分压节点 2.98V → raw ≈ 2.98/4.4 × 4095 ≈ 2773
    NE555 低电平 0V → raw ≈ 0
    判据：raw 在 0 与 ~2700 之间来回跳 = 起振成功。
"""
import argparse
import collections
import csv
import sys
import time

try:
    import serial
    import serial.tools.list_ports
except ImportError:
    sys.exit("缺少 pyserial，请先运行：python -m pip install pyserial matplotlib")

try:
    import matplotlib
    matplotlib.use("TkAgg")
    import matplotlib.pyplot as plt
except ImportError:
    sys.exit("缺少 matplotlib，请先运行：python -m pip install pyserial matplotlib")


# 12dB 衰减下的近似换算（仅显示用，测频率不依赖此值）
VREF_MV = 1100.0
K_12DB = 0.25
FULL_SCALE_V = (VREF_MV / 1000.0) / K_12DB   # ≈4.4V
BITWIDTH = 4095


def raw_to_v(raw):
    return raw / BITWIDTH * FULL_SCALE_V


def list_ports():
    print("可用串口：")
    for p in serial.tools.list_ports.comports():
        print(f"  {p.device:<20} {p.description}")
    if not list(serial.tools.list_ports.comports()):
        print("  （没找到串口，检查 USB 线是否支持数据、CH343P 驱动是否装好）")


def measure(t_us, raw, threshold_ratio=0.5):
    """从一批样本测频率/占空比/电平。返回 dict 或 None。"""
    if len(raw) < 20:
        return None
    hi = max(raw)
    lo = min(raw)
    span = hi - lo
    if span < 300:   # 幅度太小，认为没起振
        return {"state": "flat", "hi": hi, "lo": lo, "span": span}

    thr = lo + span * threshold_ratio
    # 找上升沿（跨阈值且中场足够高）
    edges = []
    for i in range(1, len(raw)):
        prev, cur = raw[i - 1], raw[i]
        if prev <= thr < cur:
            # 线性插值定位过零点，提高周期精度
            frac = (thr - prev) / (cur - prev) if cur != prev else 0.0
            edges.append(t_us[i - 1] + frac * (t_us[i] - t_us[i - 1]))

    if len(edges) < 3:
        return {"state": "edges", "hi": hi, "lo": lo, "span": span, "n": len(edges)}

    periods = [edges[i] - edges[i - 1] for i in range(1, len(edges))]
    # 中位数抗毛刺
    periods.sort()
    median_period = periods[len(periods) // 2]
    freq_hz = 1e6 / median_period if median_period > 0 else 0

    # 占空比：相邻上升沿之间高于阈值的样本比例
    duty_samples = 0
    total_samples = 0
    for i in range(len(edges) - 1):
        a, b = int(edges[i] / (t_us[1] - t_us[0])), int(edges[i + 1] / (t_us[1] - t_us[0]))
        # 用索引近似即可，因为采样等间隔
        a = max(0, min(a, len(raw) - 1))
        b = max(a + 1, min(b, len(raw) - 1))
        for j in range(a, b):
            total_samples += 1
            if raw[j] > thr:
                duty_samples += 1
    duty = duty_samples / total_samples * 100 if total_samples else 0

    return {
        "state": "ok",
        "hi": hi,
        "lo": lo,
        "span": span,
        "freq_hz": freq_hz,
        "period_us": median_period,
        "duty_pct": duty,
        "n_edges": len(edges),
    }


def main():
    ap = argparse.ArgumentParser(description="ESP32-P4 NE555 串口波形采集与频率测量")
    ap.add_argument("port", nargs="?", help="串口号，如 COM3 或 /dev/ttyUSB0")
    ap.add_argument("--baud", type=int, default=921600, help="波特率，默认 921600")
    ap.add_argument("--window", type=int, default=2000, help="显示最近 N 个样本，默认 2000")
    ap.add_argument("--save", help="同时把原始数据存成 CSV 文件")
    ap.add_argument("--list", action="store_true", help="列出可用串口后退出")
    args = ap.parse_args()

    if args.list:
        list_ports()
        return

    if not args.port:
        ap.error("请指定串口，或用 --list 查看可用串口")

    try:
        ser = serial.Serial(args.port, args.baud, timeout=1)
    except serial.SerialException as e:
        sys.exit(f"打不开串口 {args.port}: {e}")

    print(f"已打开 {args.port} @ {args.baud}，等待数据...")
    print("跳变判据：raw 在 ~0 与 ~2700 之间来回跳 = NE555 起振成功")

    plt.ion()
    fig, ax = plt.subplots(figsize=(11, 4.5))
    line, = ax.plot([], [], lw=1.2, color="#185FA5")
    ax.set_xlabel("time (ms)")
    ax.set_ylabel("ADC raw")
    ax.set_ylim(-100, 4200)
    ax.grid(alpha=0.3)
    fig.tight_layout()

    buf_t = collections.deque(maxlen=args.window)
    buf_v = collections.deque(maxlen=args.window)
    writer = None
    fout = None
    if args.save:
        fout = open(args.save, "w", newline="", encoding="utf-8")
        writer = csv.writer(fout)
        writer.writerow(["timestamp_us", "raw_adc"])

    t0 = None
    last_report = 0.0
    try:
        while True:
            line_bytes = ser.readline()
            if not line_bytes:
                continue
            try:
                text = line_bytes.decode("utf-8", errors="ignore").strip()
                if "," not in text:
                    continue
                a, b = text.split(",", 1)
                t_us = int(a)
                raw = int(b)
            except (ValueError, IndexError):
                continue

            if t0 is None:
                t0 = t_us
            buf_t.append((t_us - t0) / 1000.0)   # ms
            buf_v.append(raw)
            if writer:
                writer.writerow([t_us, raw])

            now = time.monotonic()
            if now - last_report < 0.5:
                continue
            last_report = now

            if len(buf_v) >= 20:
                m = measure(list(buf_t), list(buf_v))
                if m:
                    if m["state"] == "flat":
                        status = (f"未起振/无跳变  hi={m['hi']} lo={m['lo']} "
                                  f"span={m['span']}")
                    elif m["state"] == "edges":
                        status = (f"边沿不足  hi={m['hi']} lo={m['lo']} "
                                  f"edges={m['n']}")
                    else:
                        status = (f"{m['freq_hz']:.1f} Hz  周期 {m['period_us'] / 1000:.2f} ms  "
                                  f"占空比 {m['duty_pct']:.1f}%  "
                                  f"hi={m['hi']}({raw_to_v(m['hi']):.2f}V) "
                                  f"lo={m['lo']}({raw_to_v(m['lo']):.2f}V)")
                    print(status, flush=True)

            if buf_t:
                line.set_data(buf_t, buf_v)
                ax.set_xlim(max(0, buf_t[0]), max(buf_t[-1], buf_t[0] + 1))
                fig.canvas.draw_idle()
                plt.pause(0.001)
    except KeyboardInterrupt:
        print("\n已停止。")
    finally:
        ser.close()
        if fout:
            fout.close()
            print(f"数据已保存到 {args.save}")


if __name__ == "__main__":
    main()
