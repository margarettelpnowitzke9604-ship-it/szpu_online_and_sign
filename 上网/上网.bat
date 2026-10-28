@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

rem Optional: set the full path to your own python.exe here.
set "PYTHON_EXE="

if defined PYTHON_EXE goto custom_python
py -3 -c "import sys; print('Python:', sys.executable); print(sys.version); sys.exit(0 if sys.version_info.major == 3 else 1)" 2>nul
if not errorlevel 1 goto use_py
python -c "import sys; print('Python:', sys.executable); print(sys.version); sys.exit(0 if sys.version_info.major == 3 else 1)" 2>nul
if not errorlevel 1 goto use_python
echo 未找到可用的 Python 3。请先确认安装路径，再修改本文件的 PYTHON_EXE。
set "RESULT=1"
goto done

:custom_python
if not exist "%PYTHON_EXE%" (
    echo PYTHON_EXE 指定的路径不存在，请按 README 修改。
    set "RESULT=1"
    goto done
)
"%PYTHON_EXE%" -c "import sys; print('Python:', sys.executable); print(sys.version); sys.exit(0 if sys.version_info.major == 3 else 1)"
if errorlevel 1 (
    echo 指定的解释器无法运行 Python 3，请确认环境。
    set "RESULT=1"
    goto done
)
"%PYTHON_EXE%" "%~dp0上网.py" %*
set "RESULT=%ERRORLEVEL%"
goto done

:use_py
py -3 "%~dp0上网.py" %*
set "RESULT=%ERRORLEVEL%"
goto done

:use_python
python "%~dp0上网.py" %*
set "RESULT=%ERRORLEVEL%"

:done
echo.
pause
exit /b %RESULT%
