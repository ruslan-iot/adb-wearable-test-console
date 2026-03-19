# Distributing ADB Wearable Test Console (Windows)

## Build the package (on your dev machine)

1. Install **Python 3.10+** (3.11+ recommended) and add it to `PATH`.
2. Open **Command Prompt** or **PowerShell** in the project folder.
3. Run:

   ```bat
   build_exe.bat
   ```

   Or manually:

   ```bat
   python -m pip install -r requirements.txt
   python -m PyInstaller --noconfirm adb_wearable_console.spec
   ```

4. When the build finishes, you will have:

   ```
   dist\ADBWearableConsole\
     ADBWearableConsole.exe    ← main program
     _internal\                ← required support files (do not remove)
     assets\                   ← optional schematic / readme
   ```

## What to give testers

1. **Zip the entire `ADBWearableConsole` folder** (not only the `.exe`).
2. Send the zip by share drive, Teams, etc.
3. Instructions for testers:
   - Extract the zip anywhere (e.g. Desktop).
   - Run **`ADBWearableConsole.exe`**.
   - Install **Android platform-tools** (`adb`) on the PC or use **Auto-detect** in the app if SDK is in the default location.

## Optional: device photo

Before building, place **`assets\device_schematic.png`** in the project. It is copied into `dist\...\assets\` automatically.

You can also drop `device_schematic.png` into the **`assets`** folder next to the `.exe` after build (same layout as in `dist`).

## Requirements on tester PCs

- **Windows 10/11** (64-bit).
- **adb.exe** available (Android SDK platform-tools or path configured in the app).
- **USB drivers** for the wearable if needed.

No **Python** installation required on tester machines.

## Troubleshooting

| Issue | What to try |
|--------|-------------|
| “Failed to execute script” | Ensure the full folder was copied; `_internal` must sit beside the `.exe`. |
| Antivirus quarantines EXE | Restore + exclusion, or code-sign the EXE for your org. |
| App won’t start / missing DLL | Rebuild on a clean `pip install -r requirements.txt`; avoid mixing old `dist` with new builds. |

## Rebuilding after code changes

Delete old outputs if you hit odd errors:

```bat
rmdir /s /q build dist
build_exe.bat
```
