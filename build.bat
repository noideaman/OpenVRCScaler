@echo off
echo Installing required build tools...
pip install pyinstaller python-osc

echo.
echo Building OpenVRCScaler executable...
echo This may take a minute or two...

REM --noconfirm: Overwrite existing build folders without asking
REM --onefile: Bundle everything into a single .exe
REM --windowed: Hides the command prompt window so only the Tkinter UI shows
REM --icon: Sets the application icon
pyinstaller --noconfirm --onefile --windowed --icon "open_vrc_scaler_icon.ico" "open_vrc_scaler.py"

echo.
echo Build complete!
echo Your standalone executable is located in the new "dist" folder.
pause