@echo off

set "CUR_DIR=%CD%"
set "ZIP_FILE=%USERPROFILE%\Documents\InkRadix.zip"
if exist "%ZIP_FILE%" del "%ZIP_FILE%"

cd ..

for %%F in (*.*) do (
    zip.exe "%ZIP_FILE%" "%%F"
)

cd "%CUR_DIR%"

echo InkRadix Zip created at: %ZIP_FILE%

pause