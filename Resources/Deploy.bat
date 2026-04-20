@echo off
setlocal enabledelayedexpansion

set "CUR_DIR=%CD%"
cd ..

set "VERSION="
for /f "tokens=4" %%A in ('findstr /b "# InkRadix v" "InkRadix.py"') do (
    set "VERSION=%%A"
    goto :FoundVersion
)
:FoundVersion

echo VERSION: %VERSION%

if not defined VERSION (
    echo Could not detect version from InkRadix.py
    pause
    cd "%CUR_DIR%"
    exit /b
)

echo Detected InkRadix version: %VERSION%
echo.

set "ZIP_FILE=%USERPROFILE%\Documents\InkRadix-%VERSION%.zip"

if exist "%ZIP_FILE%" del "%ZIP_FILE%"

echo Creating zip: %ZIP_FILE%
zip.exe -q "%ZIP_FILE%" InkRadixEdit.inx InkRadixToggleBL.inx InkRadix.py info.json LICENSE README.md

cd "%CUR_DIR%"
echo Zip created at: %ZIP_FILE%
echo.

set "SIG_FILE=%USERPROFILE%\Documents\InkRadix-%VERSION%.sig"

echo Signing zip file with GPG...
gpg --output "%SIG_FILE%" --detach-sign --sign "%ZIP_FILE%"

echo Signature created at: %SIG_FILE%
echo.
echo Done.

pause