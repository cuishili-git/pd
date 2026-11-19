# PD-SCOPE · 虚拟示波器上位机

配合 ESP32-P4 固件（`../main/test_ne555.c`，2000Hz ADC 采集 GPIO23）使用的示波器程序。
PyQt6 + pyqtgraph，暗色示波器风格。

## 运行

```bash
# 首次（虚拟环境已建好，依赖已装）
cd D:\esp32\p4\my\test_ne555\python
venv\Scripts\python scope_app.py --demo          # 演示模式（无硬件）
venv\Scripts\python scope_app.py --port COM5     # 直接连串口
venv\Scripts\python scope_app.py                 # 手动连接

# 若换了机器，重建环境
python -m venv venv
venv\Scripts\python -m pip install PyQt6 pyqtgraph pyserial
```

## 功能

| 功能 | 说明 |
|---|---|
| 边沿触发 | 波形按上升沿对齐，稳定不漂移；触发电平滑块可调 |
| 自动测量 | 频率 / 周期 / 占空比 / Vpp / Vmax / Vmin / 高低电平 / 实际采样率 |
| 双游标 | 图中青/橙两条虚线可拖动，读 Δt、1/Δt（=频率）、ΔV |
| 时基 | 每格宽度档位 10ms/格 ~ 2s/格（全屏 10 格）；100Hz 方波用 20~50ms/格，当前模块 1.8Hz 慢信号用 1~2s/格 |
| 运行/停止 | 停止冻结波形，便于游标测量 |
| 保存 CSV | 导出 时间戳/原始值/电压 三列原始数据 |
| DEMO 模式 | 无硬件模拟 100Hz 方波 + 噪声，验证软件链路 |

## 串口约定（与固件一致）

- 波特率 **921600**（固件 sdkconfig 已改，上位机默认一致）
- 数据格式 `timestamp_us,raw_adc`，2000 Hz
- 电压换算：12dB 衰减理论满量程 4.4V，`V = raw / 4095 × 4.4`

## 验收参考（DEMO 模式自检已通过）

```
频率: 100.003 Hz | 周期: 10.000 ms | 占空比: 50.0%
Vpp: 3.006 V | 高电平: 2.997 V | 低电平: 0.012 V
```

接真硬件后，预期读数：频率 ≈ 你 NE555 模块设定值（100Hz 或 50Hz）；
高电平 ≈2.98V（12V 直出模块）或 ≈1.24V（内置 7805 的模块）。
