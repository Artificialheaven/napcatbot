@echo off
chcp 65001 >nul
echo ========================================
echo   NapCatBot 打包脚本
echo ========================================
echo.

echo [1/3] 清理旧的构建文件...
if exist "dist" rmdir /s /q dist
if exist "build" rmdir /s /q build
if exist "NapCatBot.spec" del NapCatBot.spec

echo [2/3] 开始打包...
pyinstaller --name=NapCatBot ^
            --onefile ^
            --windowed ^
            --add-data "config.json;." ^
            --add-data "plugins;plugins" ^
            --hidden-import=dearpygui ^
            --hidden-import=websockets ^
            --hidden-import=configs ^
            --hidden-import=globals ^
            --hidden-import=events ^
            --hidden-import=main_ui ^
            --hidden-import=plugin_loader ^
            --hidden-import=bot ^
            --hidden-import=config_window ^
            --hidden-import=plugin_window ^
            --hidden-import=monitor_window ^
            --hidden-import=report_window ^
            main.py

echo.
echo [3/3] 打包完成！
echo.

if exist "dist\NapCatBot.exe" (
    echo ✓ 可执行文件位置: dist\NapCatBot.exe
    echo.
    echo 请将以下文件和文件夹复制到 dist 目录：
    echo   - config.json (如果不存在会自动创建)
    echo   - plugins 文件夹
    echo.
    echo 然后运行 run.bat 或直接双击 NapCatBot.exe
    echo.
    echo 注意：已隐藏控制台窗口，如需调试请查看日志文件
) else (
    echo ✗ 打包失败，请检查错误信息
)

echo.
pause
