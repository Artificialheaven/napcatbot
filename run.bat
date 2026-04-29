@echo off
chcp 65001 >nul
echo ========================================
echo   NapCatBot - QQ机器人框架
echo ========================================
echo.

if exist "NapCatBot.exe" (
    echo 正在启动 NapCatBot...
    start NapCatBot.exe
) else (
    echo 错误: 找不到 NapCatBot.exe
    echo 请先运行打包命令或从发布包中获取
    pause
)
