@echo off

set "CUR_DIR=%CD%"
set "TARGET_DIR=%APPDATA%\inkscape\extensions\nasos.inkradix"

if not exist "%TARGET_DIR%" (
    mkdir "%TARGET_DIR%"
)
cd ..

copy /Y "InkRadix.inx" "%TARGET_DIR%"
copy /Y "InkRadix.py" "%TARGET_DIR%"
copy /Y "info.json" "%TARGET_DIR%"
copy /Y "LICENSE" "%TARGET_DIR%"
copy /Y "README.md" "%TARGET_DIR%"

cd "%CUR_DIR%"

echo.
echo InkRadix files installed to:
echo %TARGET_DIR%
echo.
echo Please restart Inkscape to load the extension.

