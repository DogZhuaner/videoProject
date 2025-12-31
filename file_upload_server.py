#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文件上传服务器
功能：接收客户端文件上传，保存到指定文件夹
端口：8094
默认上传路径：/home/a214/result
"""

import os
import shutil
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.utils import secure_filename

# 配置参数（支持环境变量）
UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', '/home/a214/result')
PORT = int(os.environ.get('PORT', 8094))
ALLOWED_EXTENSIONS = set(os.environ.get('ALLOWED_EXTENSIONS', 'zip,rar,7z,tar.gz,tgz,txt,pdf,jpg,jpeg,png,gif,docx,xlsx,pptx').split(','))
MAX_CONTENT_LENGTH = int(os.environ.get('MAX_CONTENT_LENGTH', 1000 * 1024 * 1024))  # 1GB

# 创建Flask应用
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

# 启用CORS，允许所有域名访问
CORS(app)

# 确保上传文件夹存在
if not os.path.exists(UPLOAD_FOLDER):
    try:
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        print(f"✅ 创建上传文件夹成功: {UPLOAD_FOLDER}")
    except Exception as e:
        print(f"❌ 创建上传文件夹失败: {e}")
        exit(1)


def allowed_file(filename):
    """检查文件是否允许上传"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/upload', methods=['POST'])
def upload_file():
    """处理文件上传请求"""
    try:
        # 检查是否有文件部分
        if 'file' not in request.files:
            print('⚠️ 请求中没有文件部分')
            return jsonify({
                'success': False,
                'message': '请求中没有文件部分'
            }), 400

        file = request.files['file']

        # 检查文件名是否为空
        if file.filename == '':
            print('⚠️ 没有选择文件')
            return jsonify({
                'success': False,
                'message': '没有选择文件'
            }), 400

        # 检查文件类型是否允许
        if not allowed_file(file.filename):
            print(f'⚠️ 不允许的文件类型: {file.filename}，仅允许: {ALLOWED_EXTENSIONS}')
            return jsonify({
                'success': False,
                'message': f'不允许的文件类型，仅允许: {ALLOWED_EXTENSIONS}'
            }), 400

        # 确保文件名安全
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)

        # 保存文件
        file.save(file_path)
        print(f'✅ 文件上传成功: {filename}，保存路径: {file_path}，大小: {os.path.getsize(file_path)} bytes')

        return jsonify({
            'success': True,
            'message': '文件上传成功',
            'filename': filename,
            'file_path': file_path,
            'size': os.path.getsize(file_path),
            'upload_folder': UPLOAD_FOLDER
        }), 200

    except Exception as e:
        print(f'❌ 文件上传失败: {str(e)}')
        return jsonify({
            'success': False,
            'message': f'文件上传失败: {str(e)}'
        }), 500


@app.route('/health', methods=['GET'])
def health_check():
    """健康检查接口"""
    print('ℹ️  健康检查请求')
    return jsonify({
        'success': True,
        'message': '文件上传服务器运行正常',
        'upload_folder': UPLOAD_FOLDER,
        'port': PORT,
        'allowed_extensions': list(ALLOWED_EXTENSIONS),
        'max_file_size': MAX_CONTENT_LENGTH,
        'server_time': datetime.now().isoformat()
    }), 200


@app.route('/files', methods=['GET'])
def list_files():
    """列出上传文件夹中的文件"""
    try:
        files = []
        for filename in os.listdir(UPLOAD_FOLDER):
            file_path = os.path.join(UPLOAD_FOLDER, filename)
            if os.path.isfile(file_path):
                files.append({
                    'filename': filename,
                    'size': os.path.getsize(file_path),
                    'mtime': os.path.getmtime(file_path)
                })
        
        print(f'ℹ️  列出文件成功，共 {len(files)} 个文件')
        return jsonify({
            'success': True,
            'upload_folder': UPLOAD_FOLDER,
            'file_count': len(files),
            'files': files
        }), 200
    except Exception as e:
        print(f'❌ 列出文件失败: {str(e)}')
        return jsonify({
            'success': False,
            'message': f'列出文件失败: {str(e)}'
        }), 500


@app.route('/delete/<filename>', methods=['DELETE'])
def delete_file(filename):
    """删除指定文件"""
    try:
        file_path = os.path.join(UPLOAD_FOLDER, secure_filename(filename))
        if os.path.exists(file_path):
            os.remove(file_path)
            print(f'✅ 文件删除成功: {filename}')
            return jsonify({
                'success': True,
                'message': f'文件删除成功: {filename}'
            }), 200
        else:
            print(f'⚠️ 文件不存在: {filename}')
            return jsonify({
                'success': False,
                'message': f'文件不存在: {filename}'
            }), 404
    except Exception as e:
        print(f'❌ 文件删除失败: {str(e)}')
        return jsonify({
            'success': False,
            'message': f'文件删除失败: {str(e)}'
        }), 500


if __name__ == '__main__':
    # 打印服务器启动信息
    print("=" * 60)
    print("📤 文件上传服务器")
    print("=" * 60)
    print(f"✅ 上传文件夹: {UPLOAD_FOLDER}")
    print(f"✅ 监听端口: {PORT}")
    print(f"✅ 允许的文件类型: {ALLOWED_EXTENSIONS}")
    print(f"✅ 最大文件大小: {MAX_CONTENT_LENGTH / 1024 / 1024:.2f}MB")
    print("=" * 60)
    print(f"🚀 服务器启动成功！")
    print(f"📌 API端点:")
    print(f"   POST   http://0.0.0.0:{PORT}/upload       # 文件上传")
    print(f"   GET    http://0.0.0.0:{PORT}/health      # 健康检查")
    print(f"   GET    http://0.0.0.0:{PORT}/files       # 列出文件")
    print(f"   DELETE http://0.0.0.0:{PORT}/delete/{'{filename}'}  # 删除文件")
    print("=" * 60)
    print("按 Ctrl+C 停止服务器")
    print("=" * 60)
    
    # 启动服务器，监听所有网络接口
    print(f"ℹ️  服务器开始监听 http://0.0.0.0:{PORT}")
    app.run(host='0.0.0.0', port=PORT, debug=False)
