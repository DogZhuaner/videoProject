#!/bin/bash

# 文件上传服务器启动脚本

# 设置环境变量（可选）
# export UPLOAD_FOLDER="/home/a214/result"
# export PORT="8094"
# export ALLOWED_EXTENSIONS="zip,rar,7z,tar.gz,tgz,txt,pdf,jpg,jpeg,png,gif,docx,xlsx,pptx"
# export MAX_CONTENT_LENGTH="104857600"

# 检查Python是否安装
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 未安装，请先安装Python 3"
    exit 1
fi

# 检查pip是否安装
if ! command -v pip3 &> /dev/null; then
    echo "❌ pip3 未安装，请先安装pip3"
    exit 1
fi

# 安装依赖
pip3 install flask flask-cors werkzeug

# 启动服务器
echo "🚀 启动文件上传服务器..."
python3 file_upload_server.py