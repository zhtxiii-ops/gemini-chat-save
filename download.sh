#!/bin/bash
# gemini2pdf.sh - 一键运行脚本，自动处理虚拟环境

# 进入脚本所在目录
cd "$(dirname "$0")" || exit

# 检查虚拟环境是否存在
if [ ! -d ".venv" ]; then
    echo "未检测到虚拟环境，正在自动创建并安装依赖..."
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    
    # 使用 Playwright 镜像加速下载（针对国内网络）
    export PLAYWRIGHT_DOWNLOAD_HOST=https://npmmirror.com/mirrors/playwright/
    python -m playwright install chromium
    echo "虚拟环境及依赖配置完成！"
    echo "----------------------------------------"
else
    source .venv/bin/activate
fi

# 检查是否传入了参数
if [ $# -eq 0 ]; then
    echo "用法: ./gemini2pdf.sh \"https://gemini.google.com/app/...\" [选项]"
    echo ""
    python gemini2pdf.py --help
else
    # 传递所有参数给 Python 脚本
    python gemini2pdf.py "$@"
fi
