@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

cd /d "%~dp0"

set "PY_CMD="
for %%P in (py python python3) do (
	where %%P >nul 2>nul && (
		set "PY_CMD=%%P"
		goto :found_python
	)
)

echo 未找到 Python 解释器。请先安装 Python 并将其添加到 PATH。
pause
exit /b 1

:found_python
echo 使用 Python 解释器: %PY_CMD%
echo 在 http://127.0.0.1:8888 启动 Rio Toolbox 后端
start "Rio Toolbox Server" cmd /k "%PY_CMD% -m uvicorn backend.server:app --host 127.0.0.1 --port 8888"

timeout /t 2 >nul
start "" http://127.0.0.1:8888

endlocal
