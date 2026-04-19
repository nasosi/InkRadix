@echo off

echo ==================================================
echo                 InkRadix Installer
echo ==================================================
echo.

set "CUR_DIR=%CD%"
set "TARGET_DIR=%APPDATA%\inkscape\extensions\nasos.inkradix"
set "WARNED=0"

echo   Target directory:
echo     %TARGET_DIR%
echo.

if not exist "%TARGET_DIR%" (
    mkdir "%TARGET_DIR%"
)

cd ..

set FILES=InkRadixEdit.inx InkRadixToggleBL.inx InkRadix.py info.json LICENSE README.md

for %%F in (%FILES%) do (
    if exist "%TARGET_DIR%\%%F" set "WARNED=1"
)

if "%WARNED%"=="1" (
    echo   [!] Existing files detected.
    echo.
    choice /M "  Overwrite existing files"
    
    if errorlevel 2 (
        echo.
        echo   Operation cancelled.
        echo.
        cd "%CUR_DIR%"
        pause
        exit /b
    )
    echo.
)

echo   Installing files...
echo.

for %%F in (%FILES%) do (
    copy /Y "%%F" "%TARGET_DIR%" >nul
)

cd "%CUR_DIR%"

echo   Installation complete.
echo.
echo ==================================================
echo   Files installed to:
echo     %TARGET_DIR%
echo.
echo   Please restart Inkscape to load the extension.
echo ==================================================
echo.

pause