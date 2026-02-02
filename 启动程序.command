#!/bin/bash
# Bilibili 视频总结工具 - Mac 启动脚本
# 双击此文件即可启动程序

# 切换到脚本所在目录
cd "$(dirname "$0")"

# 显示启动信息
echo "=================================================="
echo "     📺 Bilibili 视频总结工具"
echo "=================================================="
echo ""

# 检查 Python3
if ! command -v python3 &> /dev/null; then
    echo "❌ 错误: 未找到 Python3"
    echo ""
    echo "请先安装 Python3:"
    echo "  1. 访问 https://www.python.org/downloads/"
    echo "  2. 或运行: brew install python3"
    echo ""
    read -p "按回车键退出..."
    exit 1
fi

echo "✓ Python3 已找到: $(python3 --version)"
echo ""

# 运行主程序
echo "正在启动程序..."
echo ""
python3 main.py --ui

# 如果程序异常退出，保持窗口打开
if [ $? -ne 0 ]; then
    echo ""
    echo "=================================================="
    echo "程序已退出，如有错误请查看上方信息"
    echo "=================================================="
    read -p "按回车键关闭窗口..."
fi
