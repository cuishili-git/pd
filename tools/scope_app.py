#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PD-SCOPE · 虚拟示波器上位机（NE555 / 局放信号采集）
====================================================
下位机：ESP32-P4 @ 2000Hz 输出 CSV（timestamp_us,raw_adc）
连接：  串口（921600）或 DEMO 模拟模式（无硬件演示）

功能
----
  · 实时波形 + 边沿触发（波形稳定不漂，真示波器体验）
  · 自动测量：频率 / 周期 / 占空比 / Vmax / Vmin / Vpp / 高低电平
  · 双游标（可拖动）：Δt、1/Δt、ΔV
  · 时基切换、运行/停止、CSV 保存
  · raw ↔ 电压换算（12dB 衰减，理论满量程 4.4V）

运行
----
  venv/Scripts/python scope_app.py              # 无参启动，手动连接
  venv/Scripts/python scope_app.py --demo       # 直接进入模拟模式
  venv/Scripts/python scope_app.py --port COM5  # 指定串口
"""

import argparse
import csv
import random
import sys
import time
from collections import deque

import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (QApplication, QCheckBox, QComboBox, QFileDialog,
                             QGridLayout, QGroupBox, QHBoxLayout, QLabel,
                             QMainWindow, QPushButton, QSlider, QStatusBar,
                             QVBoxLayout, QWidget)

# ---------------------------------------------------------------- 常量
V_FULL     = 4.4          # 12dB 衰减理论满量程（GPIO 绝对上限 3.3V）
RAW_MAX    = 4095
BUF_SEC    = 22.0         # 缓冲区时长（秒）——需容纳最大时基 2s/格×10格
DEMO_FREQ  = 100.0        # 模拟方波频率
DEMO_VHI   = 2773         # 模拟高电平 raw（≈2.98V）
DEMO_VLO   = 25           # 模拟低电平 raw（≈0.02V，含底噪）
DEMO_NOISE = 25           # 模拟噪声幅度（raw）

COLOR_WAVE   = '#00E676'  # 波形：示波器绿
COLOR_TRIG   = '#FFD54F'  # 触发电平：黄
COLOR_CUR_A  = '#4FC3F7'  # 游标 A：青
COLOR_CUR_B  = '#FFB74D'  # 游标 B：橙
COLOR_GRID   = '#1B2430'
BG_PLOT      = '#0B0F14'

TIMEBASES = [('10 ms', 0.010), ('20 ms', 0.020), ('50 ms', 0.050),
             ('100 ms', 0.100), ('200 ms', 0.200), ('500 ms', 0.500),
             ('1 s', 1.000), ('2 s', 2.000)]   # 值为每格宽度，全屏 10 格


def raw_to_v(raw):
    return raw / RAW_MAX * V_FULL


# ================================================================ 串口线程
class SerialWorker(QThread):
    sample = pyqtSignal(float, int)      # t_us, raw
    status = pyqtSignal(str)
    error = pyqtSignal(str)              # 打开串口失败 → 界面复位

    def __init__(self, port, baud):
        super().__init__()
        self.port, self.baud = port, baud
        self._stop = False

    def run(self):
        import serial  # pyserial
        try:
            ser = serial.Serial(self.port, self.baud, timeout=0.1)
        except Exception as e:
            self.error.emit(f'打开 {self.port} 失败: {e}')
            return
        self.status.emit(f'已连接 {self.port} @ {self.baud}')
        n_rx = n_ok = n_bytes = 0        # 原始行数 / 解析成功行数 / 原始字节数
        shown = 0                        # 控制台只打印前 3 行原始数据
        last_stat = time.time()
        while not self._stop:
            raw = ser.readline()
            if raw:
                n_bytes += len(raw)
                n_rx += 1
                if shown < 3:
                    print(f'[scope] 串口原始第 {shown + 1} 行: {raw[:64]!r}', flush=True)
                    shown += 1
            line = raw.decode('ascii', errors='ignore').strip()
            if ',' in line:
                parts = line.split(',')
                try:
                    t_us, raw_adc = float(parts[0]), int(parts[1])
                except ValueError:
                    continue
                n_ok += 1
                self.sample.emit(t_us / 1e6, max(0, min(RAW_MAX, raw_adc)))
            now = time.time()
            if now - last_stat >= 1.0:   # 每秒刷新一次接收统计
                self.status.emit(f'接收统计: {n_bytes} 字节 / {n_rx} 行原始, 解析成功 {n_ok}')
                last_stat = now
        ser.close()
        self.status.emit('串口已断开')

    def stop(self):
        self._stop = True
        self.wait(800)


# ================================================================ 测量算法
def edge_crossings(t, v, level, rising=True):
    """返回信号穿越 level 的精确时间点（线性插值）。"""
    t, v = np.asarray(t), np.asarray(v)
    s = v - level
    idx = np.where((s[:-1] < 0) & (s[1:] >= 0))[0] if rising else \
          np.where((s[:-1] >= 0) & (s[1:] < 0))[0]
    if len(idx) == 0:
        return np.array([])
    frac = -s[idx] / (s[idx + 1] - s[idx])
    return t[idx] + frac * (t[idx + 1] - t[idx])


def measure_wave(t, v):
    """对一段波形做自动测量，返回字典（无有效信号时各项为 None）。"""
    out = {'freq': None, 'period': None, 'duty': None,
           'vmax': None, 'vmin': None, 'vpp': None,
           'v_hi': None, 'v_lo': None, 'sps': None}
    if len(t) < 10:
        return out
    vmax, vmin = float(np.max(v)), float(np.min(v))
    out.update(vmax=vmax, vmin=vmin, vpp=vmax - vmin,
               v_hi=float(np.percentile(v, 90)),
               v_lo=float(np.percentile(v, 10)))
    mid = (vmax + vmin) / 2.0
    if vmax - vmin < 0.05:                   # 幅度过小视为直流
        return out
    rising = edge_crossings(t, v, mid, rising=True)
    if len(rising) >= 3:
        d = np.diff(rising)
        period = float(np.median(d))
        if period > 0:
            out['period'] = period
            out['freq'] = 1.0 / period
            # 占空比：上升沿到下一下降沿
            falling = edge_crossings(t, v, mid, rising=False)
            if len(falling) and len(rising):
                hi = [float(np.min(falling[falling > r] - r))
                      for r in rising[:-1]
                      if np.any(falling > r)]
                if hi:
                    out['duty'] = float(np.median(hi)) / period
    return out


# ================================================================ 主窗口
class ScopeWindow(QMainWindow):
    def __init__(self, args):
        super().__init__()
        self.args = args
        self.setWindowTitle('PD-SCOPE · 虚拟示波器  v1.0')
        self.resize(1280, 800)

        self.buf = deque()                   # (t_abs_s, raw)
        self.running = True
        self.worker = None
        self.demo_timer = None
        self.demo_t0 = None
        self.bytes_acc, self.bytes_t0 = 0, time.time()
        self.fps, self._fps_t, self._fps_n = 0, time.time(), 0
        self.measure = {}

        self._build_ui()
        self._build_plot()

        # 刷新定时器 ~40fps
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh)
        self.refresh_timer.start(25)

        if args.demo:
            self.start_demo()
        elif args.port:
            # 把指定串口选进下拉框，再走统一的连接路径
            for i in range(self.cmb_port.count()):
                if self.cmb_port.itemText(i).startswith(args.port):
                    self.cmb_port.setCurrentIndex(i)
                    break
            else:
                # 列表里没有（比如设备插在别的口），直接原样追加
                self.cmb_port.addItem(args.port)
                self.cmb_port.setCurrentIndex(self.cmb_port.count() - 1)
            self.on_connect()

    # ---------- UI ----------
    def _build_ui(self):
        central = QWidget()
        root = QHBoxLayout(central)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)
        self.setCentralWidget(central)

        # 左：波形区
        self.plot = pg.PlotWidget()
        self.plot.setSizePolicy(self.plot.sizePolicy())
        root.addWidget(self.plot, stretch=4)

        # 右：控制面板
        panel = QWidget()
        panel.setFixedWidth(300)
        right = QVBoxLayout(panel)
        right.setSpacing(8)
        root.addWidget(panel, stretch=0)

        # -- 连接组 --
        g1 = QGroupBox('信号源')
        f1 = QGridLayout(g1)
        self.cmb_port = QComboBox()
        self.cmb_port.addItem('DEMO 模拟')
        self.btn_refresh = QPushButton('刷新端口')
        self.btn_conn = QPushButton('连接')
        self.btn_run = QPushButton('■ 停止')
        self.btn_run.setCheckable(True)
        self.btn_save = QPushButton('保存 CSV')
        f1.addWidget(self.cmb_port, 0, 0, 1, 2)
        f1.addWidget(self.btn_refresh, 1, 0)
        f1.addWidget(self.btn_conn, 1, 1)
        f1.addWidget(self.btn_run, 2, 0)
        f1.addWidget(self.btn_save, 2, 1)
        right.addWidget(g1)

        # -- 时基 / 触发组 --
        g2 = QGroupBox('时基与触发')
        f2 = QGridLayout(g2)
        f2.addWidget(QLabel('时基'), 0, 0)
        self.cmb_tb = QComboBox()
        for name, _ in TIMEBASES:
            self.cmb_tb.addItem(name)
        self.cmb_tb.setCurrentIndex(2)       # 默认 50ms/格 → 全屏 500ms
        f2.addWidget(self.cmb_tb, 0, 1)
        self.chk_trig = QCheckBox('边沿触发')
        self.chk_trig.setChecked(True)
        f2.addWidget(self.chk_trig, 1, 0, 1, 2)
        f2.addWidget(QLabel('触发电平'), 2, 0)
        self.sld_trig = QSlider(Qt.Orientation.Horizontal)
        self.sld_trig.setRange(5, 95)
        self.sld_trig.setValue(50)
        f2.addWidget(self.sld_trig, 2, 1)
        self.lbl_trig_v = QLabel('1.50 V')
        f2.addWidget(self.lbl_trig_v, 3, 0, 1, 2)
        right.addWidget(g2)

        # -- 测量读数 --
        g3 = QGroupBox('自动测量')
        f3 = QGridLayout(g3)
        self.readouts = {}
        rows = [('freq', '频率'), ('period', '周期'), ('duty', '占空比'),
                ('vpp', 'Vpp'), ('vmax', 'Vmax'), ('vmin', 'Vmin'),
                ('v_hi', '高电平'), ('v_lo', '低电平'), ('sps', '采样率')]
        for i, (key, name) in enumerate(rows):
            lab = QLabel(name)
            lab.setStyleSheet('color:#8B949E; font-size:12px;')
            val = QLabel('---')
            val.setFont(QFont('Consolas', 13, QFont.Weight.Bold))
            val.setStyleSheet('color:#E6EDF3;')
            f3.addWidget(lab, i, 0)
            f3.addWidget(val, i, 1)
            self.readouts[key] = val
        right.addWidget(g3)

        # -- 游标读数 --
        g4 = QGroupBox('游标测量（拖动图中虚线）')
        f4 = QGridLayout(g4)
        self.cur_a = QLabel('A: ---')
        self.cur_b = QLabel('B: ---')
        self.cur_ab = QLabel('Δt: ---   1/Δt: ---   ΔV: ---')
        for w in (self.cur_a, self.cur_b, self.cur_ab):
            w.setFont(QFont('Consolas', 11))
            w.setStyleSheet('color:#C9D1D9;')
        f4.addWidget(self.cur_a, 0, 0)
        f4.addWidget(self.cur_b, 1, 0)
        f4.addWidget(self.cur_ab, 2, 0)
        right.addWidget(g4)
        right.addStretch(1)

        # -- 信号连接 --
        self.btn_refresh.clicked.connect(self.refresh_ports)
        self.btn_conn.clicked.connect(self.on_connect)
        self.btn_run.clicked.connect(self.on_run_toggle)
        self.btn_save.clicked.connect(self.on_save)
        self.cmb_tb.currentIndexChanged.connect(lambda _: None)  # 刷新时读取
        self.sld_trig.valueChanged.connect(self._trig_moved)

        # -- 状态栏 --
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.lbl_state = QLabel('● 未连接')
        self.lbl_state.setStyleSheet('color:#F85149; font-weight:bold;')
        self.status.addWidget(self.lbl_state)
        self.lbl_rate = QLabel('')
        self.status.addPermanentWidget(self.lbl_rate)

        self.setStyleSheet('''
            QMainWindow, QWidget { background:#0D1117; color:#C9D1D9;
                                   font-family:"Microsoft YaHei"; font-size:13px; }
            QGroupBox { border:1px solid #30363D; border-radius:6px;
                        margin-top:10px; padding-top:6px; }
            QGroupBox::title { subcontrol-origin:margin; left:10px;
                               color:#58A6FF; }
            QPushButton { background:#21262D; border:1px solid #30363D;
                          border-radius:4px; padding:5px 10px; }
            QPushButton:hover { background:#30363D; }
            QPushButton:checked { background:#1F6FEB; color:#FFF;
                                  border-color:#1F6FEB; }
            QComboBox { background:#21262D; border:1px solid #30363D;
                        border-radius:4px; padding:4px; }
            QSlider::groove:horizontal { height:4px; background:#30363D;
                                         border-radius:2px; }
            QSlider::handle:horizontal { width:12px; margin:-6px 0;
                                         background:#58A6FF; border-radius:6px; }
        ''')

    # ---------- 绘图区 ----------
    def _build_plot(self):
        p = self.plot
        p.setBackground(BG_PLOT)
        p.showGrid(x=True, y=True, alpha=0.35)
        p.setLabel('left', '电压', units='V')
        p.setLabel('bottom', '时间', units='s')   # 数据单位是秒；pyqtgraph 会按视窗自动切 ms/µs 前缀
        p.setYRange(-0.3, 4.8)   # 换算用 4.4V 理论满量程，顶部要留出显示空间
        p.setMouseEnabled(x=True, y=False)

        self.curve = p.plot([], [], pen=pg.mkPen(COLOR_WAVE, width=2))
        self.trig_line = pg.InfiniteLine(angle=90, movable=False,
                                         pen=pg.mkPen(COLOR_TRIG, width=1,
                                                      style=Qt.PenStyle.DashLine))
        p.addItem(self.trig_line)
        self.curs = []
        for color, name in ((COLOR_CUR_A, 'A'), (COLOR_CUR_B, 'B')):
            line = pg.InfiniteLine(angle=90, movable=True,
                                   pen=pg.mkPen(color, width=1))
            line.setPos(0.0)
            p.addItem(line)
            self.curs.append(line)

    # ---------- 数据入口 ----------
    def push(self, t_abs, raw):
        self.buf.append((t_abs, raw))
        while self.buf and t_abs - self.buf[0][0] > BUF_SEC:
            self.buf.popleft()
        self.bytes_acc += 14
        self._fps_n += 1

    def on_sample(self, t_s, raw):
        self.push(t_s, raw)

    # ---------- DEMO ----------
    def start_demo(self):
        if self.demo_timer:
            return
        self.demo_t0 = time.perf_counter()
        self._demo_i = 0
        self.demo_timer = QTimer(self)
        self.demo_timer.timeout.connect(self._demo_tick)
        self.demo_timer.start(10)            # 每 10ms 生成 20 点
        self.lbl_state.setText('● DEMO 模拟')
        self.lbl_state.setStyleSheet('color:#3FB950; font-weight:bold;')
        self.status.showMessage('DEMO：100 Hz 方波 + 噪声（无硬件）')

    def _demo_tick(self):
        now = time.perf_counter() - self.demo_t0
        # 补齐到当前时间的数据，2000Hz 节拍
        t_next = self._demo_i / 2000.0
        while t_next <= now:
            phase = (t_next % (1.0 / DEMO_FREQ)) * DEMO_FREQ
            base = DEMO_VHI if phase < 0.5 else DEMO_VLO
            raw = base + random.randint(-DEMO_NOISE, DEMO_NOISE)
            self.push(t_next, max(0, min(RAW_MAX, raw)))
            self._demo_i += 1
            t_next = self._demo_i / 2000.0

    # ---------- 串口 ----------
    def refresh_ports(self):
        self.cmb_port.blockSignals(True)
        self.cmb_port.clear()
        self.cmb_port.addItem('DEMO 模拟')
        try:
            from serial.tools.list_ports import comports
            for p in comports():
                self.cmb_port.addItem(f'{p.device} — {p.description}')
        except Exception:
            pass
        self.cmb_port.blockSignals(False)

    def on_connect(self):
        if self.worker:
            self.worker.stop()
            self.worker = None
            self.btn_conn.setText('连接')
            self.lbl_state.setText('● 未连接')
            self.lbl_state.setStyleSheet('color:#F85149; font-weight:bold;')
            return
        if self.demo_timer:                  # 关掉 demo
            self.demo_timer.stop()
            self.demo_timer = None
        text = self.cmb_port.currentText()
        if text.startswith('DEMO'):
            self.start_demo()
            return
        port = text.split(' — ')[0].strip()
        self.worker = SerialWorker(port, 921600)
        self.worker.sample.connect(self.on_sample)
        self.worker.status.connect(self.status.showMessage)
        self.worker.error.connect(self.on_conn_error)
        self.worker.start()
        self.btn_conn.setText('断开')
        self.lbl_state.setText(f'● 已连接 {port}')
        self.lbl_state.setStyleSheet('color:#3FB950; font-weight:bold;')

    def on_conn_error(self, msg):
        """串口打开失败：复位连接状态并把错误亮出来。"""
        self.worker = None
        self.btn_conn.setText('连接')
        self.lbl_state.setText('● 未连接')
        self.lbl_state.setStyleSheet('color:#F85149; font-weight:bold;')
        self.status.showMessage(msg, 10000)

    # ---------- 控制 ----------
    def on_run_toggle(self):
        self.running = not self.btn_run.isChecked()
        self.btn_run.setText('▶ 运行' if self.btn_run.isChecked() else '■ 停止')

    def _trig_moved(self, val):
        self.lbl_trig_v.setText(f'{val / 100 * V_FULL:.2f} V')

    def on_save(self):
        path, _ = QFileDialog.getSaveFileName(
            self, '保存 CSV', f'ne555_{time.strftime("%H%M%S")}.csv', 'CSV (*.csv)')
        if not path:
            return
        with open(path, 'w', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            w.writerow(['timestamp_us', 'raw_adc', 'volt'])
            for t, raw in self.buf:
                w.writerow([int(t * 1e6), raw, f'{raw_to_v(raw):.4f}'])
        self.status.showMessage(f'已保存 {len(self.buf)} 点 → {path}', 5000)

    # ---------- 主刷新 ----------
    def refresh(self):
        if not self.buf:
            return
        data = list(self.buf)
        t = np.array([d[0] for d in data])
        v = np.array([raw_to_v(d[1]) for d in data])
        # 示波器语义：档位值是每格宽度，全屏 10 格
        window = TIMEBASES[self.cmb_tb.currentIndex()][1] * 10.0
        trig_on = self.chk_trig.isChecked() and self.running
        level = (self.sld_trig.value() / 100.0) * V_FULL
        self.trig_line.setPos(0.0)           # 相对坐标下触发线在 x=0
        self.trig_line.setVisible(trig_on)

        x, ok, origin = self._extract_window(t, v, window, trig_on, level)
        self._last_origin = origin
        xs = np.array([p[0] for p in x])
        ys = np.array([p[1] for p in x])
        self.curve.setData(xs, ys)
        # 锁定 X 视窗到触发窗口宽度，避免自动拉伸出大片空白
        pre, post = window * 0.1, window * 0.9
        self.plot.setXRange(-pre, post, padding=0)

        self._update_measure(t, v, window)
        self._update_cursor(t, v)
        self._update_status(t)

        self._last_origin = t[-1]

    def _extract_window(self, t, v, window, trig_on, level):
        """返回 [(t_rel, v), ...]，t_rel 相对触发点（秒，触发点=0）。"""
        t_end = t[-1]
        pre, post = window * 0.1, window * 0.9
        if trig_on:
            vmax, vmin = float(v.max()), float(v.min())
            lv = vmin + (vmax - vmin) * (self.sld_trig.value() / 100.0)
            if vmax - vmin > 0.05:
                cross = edge_crossings(t, v, lv, rising=True)
                # 找最后一个能放下完整窗口的触发点
                good = cross[(cross - pre >= t[0]) & (cross + post <= t_end)]
                if len(good):
                    t0 = float(good[-1])
                    sel = (t >= t0 - pre) & (t <= t0 + post)
                    return list(zip(t[sel] - t0, v[sel])), True, t0
            # 触发丢失 → 退化为滚动窗口
        t0 = t_end - post
        sel = (t >= t0 - pre) & (t <= t0 + post)
        return list(zip(t[sel] - t0, v[sel])), False, t0

    def _update_measure(self, t, v, window):
        # 优先用最近 1s 数据；频率读不出（慢信号）时回退到全缓存 4s
        sel = t >= t[-1] - min(1.0, BUF_SEC)
        self.measure = measure_wave(t[sel], v[sel])
        if self.measure['freq'] is None and (t[-1] - t[0]) > 1.5:
            self.measure = measure_wave(t, v)
        self.measure['sps'] = (len(t[sel]) /
                               max(1e-6, min(1.0, t[-1] - t[sel][0])))
        m = self.measure
        def put(key, text):
            self.readouts[key].setText(text)
        put('freq',  f"{m['freq']:.2f} Hz" if m['freq'] else '---')
        put('period', f"{m['period'] * 1e3:.2f} ms" if m['period'] else '---')
        put('duty',  f"{m['duty'] * 100:.1f} %" if m['duty'] else '---')
        put('vpp',   f"{m['vpp']:.3f} V" if m['vpp'] is not None else '---')
        put('vmax',  f"{m['vmax']:.3f} V" if m['vmax'] is not None else '---')
        put('vmin',  f"{m['vmin']:.3f} V" if m['vmin'] is not None else '---')
        put('v_hi',  f"{m['v_hi']:.3f} V" if m['v_hi'] is not None else '---')
        put('v_lo',  f"{m['v_lo']:.3f} V" if m['v_lo'] is not None else '---')
        put('sps',   f"{m['sps']:.0f} /s")

    def _update_cursor(self, t, v):
        pos = [float(c.value()) for c in self.curs]
        self.cur_a.setText(f'A: t={pos[0] * 1e3:+7.2f} ms  V={self._v_at(t, v, pos[0]):.3f} V')
        self.cur_b.setText(f'B: t={pos[1] * 1e3:+7.2f} ms  V={self._v_at(t, v, pos[1]):.3f} V')
        dt = pos[1] - pos[0]
        dv = self._v_at(t, v, pos[1]) - self._v_at(t, v, pos[0])
        inv = f'{1.0 / dt:.1f} Hz' if abs(dt) > 1e-6 else '---'
        self.cur_ab.setText(f'Δt={dt * 1e3:+7.3f} ms  1/Δt={inv}  ΔV={dv:+.3f} V')

    def _v_at(self, t, v, t_rel):
        """游标坐标（相对原点）→ 最近采样点的电压。"""
        t_abs = self._last_origin + t_rel
        i = int(np.abs(t - t_abs).argmin())
        return float(v[i])

    def _update_status(self, t):
        now = time.time()
        if now - self._fps_t >= 1.0:
            self.fps = self._fps_n / (now - self._fps_t)
            rate = self.bytes_acc / max(1e-6, now - self.bytes_t0)
            self.lbl_rate.setText(f'{self.fps:.0f} fps · {rate / 1024:.1f} kB/s · '
                                  f'{len(self.buf)} 点缓存')
            self._fps_t, self._fps_n = now, 0
            self.bytes_acc, self.bytes_t0 = 0, now

    def closeEvent(self, event):
        if self.worker:
            self.worker.stop()
        event.accept()


# ================================================================ 入口
def main():
    ap = argparse.ArgumentParser(description='PD-SCOPE 虚拟示波器')
    ap.add_argument('--port', help='直接连接指定串口，如 COM5')
    ap.add_argument('--demo', action='store_true', help='启动即进入模拟模式')
    ap.add_argument('--list', action='store_true',
                    help='列出可用串口后退出（不启动界面）')
    ap.add_argument('--selftest', action='store_true',
                    help='离屏自测：跑 2.5 秒后自动退出')
    args = ap.parse_args()

    if args.list:
        try:
            from serial.tools import list_ports
            ports = list(list_ports.comports())
        except ImportError:
            print('未安装 pyserial: venv\\Scripts\\python -m pip install pyserial')
            sys.exit(1)
        if not ports:
            print('（没有发现任何串口设备——检查 USB 线是否插在 UART 口）')
        for p in ports:
            print(f'{p.device:8s}  {p.description}')
        return

    app = QApplication(sys.argv)
    win = ScopeWindow(args)
    win.refresh_ports()
    win.show()
    if args.selftest:
        QTimer.singleShot(2500, app.quit)
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
