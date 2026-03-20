# ADB Wearable Test Console

Windows desktop console for **hardware testers / QA** validating Android-based wearables over **ADB** (USB + Wi‑Fi).  
The app automates USB→TCP handover, guides Wi‑Fi setup, collects 1 Hz telemetry, estimates battery runtime, and exports CSV for lab analysis.

Built with **Python 3 / PySide6 / pyqtgraph** and packaged as a **stand‑alone `.exe`** via PyInstaller (no Python required on tester PCs).

---

## 1. System requirements

- **Tester PCs**
  - Windows 10 / 11 (64‑bit)
  - USB driver for the wearable (if required by the vendor)
  - Android **platform‑tools** (`adb.exe`) installed, either:
    - on the system `PATH`, or
    - configured via the **ADB path** field in the app

- **Development machine**
  - Python **3.10+** (3.11+ recommended)
  - Internet access to install dependencies from PyPI

---

## 2. Quick start (development)

```bat
cd "z:\Development\adb-application W10"
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

Run tests:

```bat
pytest
```

---

## 3. Tester workflow (supported by the UI)

1. **Connect via USB**
   - Enable **USB debugging**; accept the RSA prompt.

2. **Start the console**
   - Launch `ADBWearableConsole.exe` (or `python main.py` in dev).
   - Set **ADB path** (or use **Auto-detect**).

3. **Select device**
   - Click **Refresh Devices**.
   - Choose the USB device (serial, not `IP:port`).

4. **Enable ADB over Wi‑Fi**
   - Optionally enter **SSID** and **Password** for the lab AP.
   - Click **Enable ADB over Wi-Fi**:
     - `adb -s <serial> tcpip <port>`
     - `svc wifi enable`
     - best‑effort `cmd wifi connect-network …` (see below)
     - IP discovery + `adb connect <ip>:<port>`

5. **If direct Wi‑Fi join is unsupported**
   - The app displays:
     > Direct Wi‑Fi joining is not supported on this Android build through standard ADB commands. Please connect the device to Wi‑Fi manually, then click Read IP.
   - Join Wi‑Fi manually on the device.
   - Use **Read device IP** + **Connect to device via IP**.

6. **Switch to Wi‑Fi device**
   - Click **Refresh Devices**.
   - Select the `IP:port` entry (now in TCP/IP mode).
   - You may unplug USB and continue testing over Wi‑Fi.

7. **Telemetry and charts**
   - Click **Start telemetry**.
   - Observe the **metric grid** (Zone3, current, rolling avg, %, V, timestamps, runtime, Wh) and the **three charts** (current / rolling avg / Zone3).

8. **Export CSV**
   - Click **Export CSV** when the run is complete.

9. **Tear‑down**
   - Click **Disable ADB over Wi-Fi** to:
     - `adb disconnect ip:port`
     - `adb usb` (when a USB serial is known)

---

## 4. Project layout

| Path | Role |
|------|------|
| `main.py` | Application entry |
| `ui/main_window.py` | Main window, layout, wiring |
| `ui/widgets/` | Schematic view, telemetry cards, charts |
| `services/adb_service.py` | Subprocess ADB with timeouts |
| `services/wifi_service.py` | Wi-Fi probe / join / IP read |
| `services/telemetry_service.py` | QThread telemetry worker |
| `services/console_controller.py` | Orchestration (no widgets) |
| `models/telemetry_sample.py` | Dataclass + CSV row |
| `utils/parsers.py` | adb/thermal/battery/IP parsing |
| `utils/settings_manager.py` | `QSettings` persistence |
| `utils/logger.py` | Logging helpers |
| `tests/` | Pytest (parser tests) |
| `assets/device_schematic.png` | Optional board schematic (see `assets/README.txt`) |
| `utils/runtime_estimator.py` | Battery runtime / Wh estimate helpers |
| `DISTRIBUTING.md` | How to package and hand builds to testers |

---

## 5. Packaging (standalone `.exe`)

1. Install dependencies (includes PyInstaller):

   ```bat
   pip install -r requirements.txt
   ```

2. Run the batch file:

   ```bat
   build_exe.bat
   ```

3. Output folder: **`dist\ADBWearableConsole\`**
   - **`ADBWearableConsole.exe`** — launcher (double-click this)
   - **`_internal\`** — Python runtime, Qt, libraries (required; do not delete)

   **Distribute the whole folder** (zip `ADBWearableConsole` and share the archive). Testers extract and run the `.exe` inside — **no Python install** on their PC.

   See **`DISTRIBUTING.md`** for a short checklist.

### PyInstaller notes

- Spec file: `adb_wearable_console.spec` — copies **`assets\`** into the bundle (for `device_schematic.png`).
- Add **`assets\device_schematic.png`** before building if you want the schematic panel populated (optional).
- First build can take several minutes. Bundle size is large (~hundreds of MB) because of Qt + NumPy + pyqtgraph dependencies.
- If antivirus flags the build, sign **`ADBWearableConsole.exe`** in your release pipeline (common with PyInstaller).

### Manual PyInstaller command

```bat
cd "path\to\adb-application W10"
python -m pip install -r requirements.txt
python -m PyInstaller --noconfirm adb_wearable_console.spec
```

---

## 6. Telemetry details

| Signal | Source |
|--------|--------|
| Zone3 °C | `/sys/class/thermal/thermal_zone3/temp` (millidegrees → °C) |
| Current (mA, display) | `current_now`: usually **µA→mA**; if \|raw\|≥100 and µA scaling gives &lt;1 mA, raw is treated as **mA** (some OEMs) |
| Rolling average | Mean of last **up to 100** current samples (same units as current) |
| Battery % | `capacity` sysfs, else `dumpsys battery` |
| Voltage (V) | `batt_vol` sysfs (assumed mV), else `dumpsys battery` |

Raw signed integer from sysfs is stored in CSV as `current_raw_ua` (naming legacy; may be µA or OEM mA depending on device).

---

## 7. Runtime estimate (telemetry cards)

- **Nominal** pack: configurable from the UI (**default 3300 mAh**) × **0.85** usable factor → effective **capacity × 0.85**.
- **Runtime** uses **mAh ÷ mA** (not Wh): **rolling-average current first**, then instantaneous if rolling is unavailable or ≤1 mA.
- **Wh** on the card is auxiliary only: `(mAh/1000) × terminal voltage`.
- Sub-**1 mA** load shows **"--"** for runtime; last valid estimate is held **~5 s** if SOC is still present (glitch smoothing).

---

## 8. License / internal use

Use and modify within your organization as needed.
