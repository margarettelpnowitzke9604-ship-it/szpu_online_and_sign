@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
if not exist "%~dp0签到.exe" (
    echo 未找到同目录的 签到.exe，请确认文件已完整解压。
    set "RESULT=1"
    goto done
)
"%~dp0签到.exe" %*
set "RESULT=%ERRORLEVEL%"
:done
echo.
pause
exit /b %RESULT%
