# 文件上传服务 - Linux部署指南

## 1. 项目概述

本项目是一个基于Flask的文件上传服务器，支持多种文件类型上传，开放端口给外部网络访问，适合在Linux服务器上部署使用。

### 功能特性

- ✅ 支持多种文件类型上传
- ✅ 支持外部网络访问
- ✅ 支持CORS跨域访问
- ✅ 支持通过环境变量配置
- ✅ 自动创建上传文件夹
- ✅ 提供健康检查接口
- ✅ 支持列出上传的文件
- ✅ 支持删除指定文件
- ✅ 支持开机自启动
- ✅ 支持自动重启

### 支持的文件类型

- 压缩包：zip, rar, 7z, tar.gz, tgz
- 文档：txt, pdf, docx, xlsx, pptx
- 图片：jpg, jpeg, png, gif

## 2. 系统要求

- **操作系统**：Linux（CentOS, Ubuntu, Debian等）
- **Python版本**：Python 3.6+
- **依赖**：Flask, Flask-CORS, Werkzeug
- **网络**：能够访问外部网络（用于安装依赖）
- **权限**：具有sudo权限（用于安装依赖和配置服务）

## 3. 安装步骤

### 3.1 准备工作

1. **创建项目目录**：
   ```bash
   mkdir -p /home/a214/VideoProject
   cd /home/a214/VideoProject
   ```

2. **上传文件**：
   将以下文件上传到项目目录：
   - `file_upload_server.py` - 主程序文件
   - `file_upload.service` - systemd服务配置文件
   - `setup_service.md` - 详细设置文档

3. **设置文件权限**：
   ```bash
   chmod +x file_upload_server.py
   ```

### 3.2 安装依赖

1. **安装Python和pip**：
   ```bash
   # Ubuntu/Debian
   sudo apt-get update
   sudo apt-get install -y python3 python3-pip python3-venv
   
   # CentOS/RHEL
   sudo yum update -y
   sudo yum install -y python3 python3-pip python3-venv
   ```

2. **安装项目依赖**：
   ```bash
   pip3 install flask flask-cors werkzeug
   ```

### 3.3 配置服务

1. **复制服务文件到系统目录**：
   ```bash
   sudo cp file_upload.service /etc/systemd/system/
   ```

2. **修改服务文件权限**：
   ```bash
   sudo chmod 644 /etc/systemd/system/file_upload.service
   ```

3. **根据实际情况修改服务配置**（可选）：
   ```bash
   sudo nano /etc/systemd/system/file_upload.service
   ```
   
   修改以下配置项（根据实际情况）：
   - `WorkingDirectory` - 项目目录
   - `User`/`Group` - 运行服务的用户和组
   - `Environment` - 环境变量配置

## 4. 启动和管理服务

### 4.1 启动服务

1. **重新加载systemd配置**：
   ```bash
   sudo systemctl daemon-reload
   ```

2. **启动服务**：
   ```bash
   sudo systemctl start file_upload.service
   ```

3. **设置开机自启动**：
   ```bash
   sudo systemctl enable file_upload.service
   ```

### 4.2 服务状态检查

1. **查看服务状态**：
   ```bash
   sudo systemctl status file_upload.service
   ```

2. **查看服务日志**：
   ```bash
   # 查看所有日志
   sudo journalctl -u file_upload.service
   
   # 实时查看日志
   sudo journalctl -u file_upload.service -f
   ```

### 4.3 服务管理命令

| 命令 | 功能描述 |
|------|----------|
| `sudo systemctl start file_upload.service` | 启动服务 |
| `sudo systemctl stop file_upload.service` | 停止服务 |
| `sudo systemctl restart file_upload.service` | 重启服务 |
| `sudo systemctl status file_upload.service` | 查看服务状态 |
| `sudo systemctl enable file_upload.service` | 设置开机自启动 |
| `sudo systemctl disable file_upload.service` | 禁用开机自启动 |
| `sudo journalctl -u file_upload.service -f` | 实时查看日志 |

## 5. 配置说明

### 5.1 环境变量配置

可以通过环境变量配置服务的运行参数：

| 环境变量 | 默认值 | 描述 |
|----------|--------|------|
| `UPLOAD_FOLDER` | `/home/a214/result` | 上传文件保存路径 |
| `PORT` | `8094` | 服务器监听端口 |
| `ALLOWED_EXTENSIONS` | `zip,rar,7z,tar.gz,tgz,txt,pdf,jpg,jpeg,png,gif,docx,xlsx,pptx` | 允许上传的文件类型 |
| `MAX_CONTENT_LENGTH` | `104857600` | 最大文件大小（100MB） |

### 5.2 修改环境变量

1. **临时修改（当前会话）**：
   ```bash
   export UPLOAD_FOLDER="/home/a214/result"
   export PORT="8094"
   python3 file_upload_server.py
   ```

2. **永久修改（服务配置）**：
   ```bash
   sudo nano /etc/systemd/system/file_upload.service
   ```
   
   修改`Environment`行：
   ```ini
   Environment=UPLOAD_FOLDER="/home/a214/result",PORT="8094",ALLOWED_EXTENSIONS="zip,rar,7z",MAX_CONTENT_LENGTH="52428800"
   ```
   
   然后重启服务：
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl restart file_upload.service
   ```

## 6. API接口

### 6.1 健康检查

| 方法 | URL | 功能描述 |
|------|-----|----------|
| GET | `/health` | 检查服务是否正常运行 |

**示例请求**：
```bash
curl http://localhost:8094/health
```

**响应**：
```json
{
    "allowed_extensions": ["zip", "rar", "7z", "tar.gz", "tgz", "txt", "pdf", "jpg", "jpeg", "png", "gif", "docx", "xlsx", "pptx"],
    "max_file_size": 104857600,
    "message": "文件上传服务器运行正常",
    "port": 8094,
    "server_time": "2025-12-31T13:59:59.123456",
    "success": true,
    "upload_folder": "/home/a214/result"
}
```

### 6.2 文件上传

| 方法 | URL | 功能描述 |
|------|-----|----------|
| POST | `/upload` | 上传文件 |

**示例请求**：
```bash
curl -X POST -F "file=@test.zip" http://localhost:8094/upload
```

**响应**：
```json
{
    "filename": "test.zip",
    "message": "文件上传成功",
    "size": 123456,
    "success": true,
    "upload_folder": "/home/a214/result"
}
```

### 6.3 列出文件

| 方法 | URL | 功能描述 |
|------|-----|----------|
| GET | `/files` | 列出上传的文件 |

**示例请求**：
```bash
curl http://localhost:8094/files
```

**响应**：
```json
{
    "file_count": 2,
    "files": [
        {
            "filename": "test1.zip",
            "mtime": 1735689600.0,
            "size": 123456
        },
        {
            "filename": "test2.pdf",
            "mtime": 1735689600.0,
            "size": 789012
        }
    ],
    "success": true,
    "upload_folder": "/home/a214/result"
}
```

### 6.4 删除文件

| 方法 | URL | 功能描述 |
|------|-----|----------|
| DELETE | `/delete/<filename>` | 删除指定文件 |

**示例请求**：
```bash
curl -X DELETE http://localhost:8094/delete/test.zip
```

**响应**：
```json
{
    "message": "文件删除成功: test.zip",
    "success": true
}
```

## 7. 安全考虑

### 7.1 权限设置

1. **使用非root用户运行服务**：
   ```bash
   # 创建专用用户
   sudo useradd -r -s /sbin/nologin uploaduser
   
   # 修改服务配置
   sudo nano /etc/systemd/system/file_upload.service
   ```
   
   将`User`和`Group`改为：
   ```ini
   User=uploaduser
   Group=uploaduser
   ```

2. **设置上传文件夹权限**：
   ```bash
   sudo chown -R uploaduser:uploaduser /home/a214/result
   sudo chmod 755 /home/a214/result
   ```

### 7.2 防火墙设置

1. **开放必要的端口**：
   ```bash
   # Ubuntu/Debian
   sudo ufw allow 8094/tcp
   sudo ufw enable
   
   # CentOS/RHEL
   sudo firewall-cmd --add-port=8094/tcp --permanent
   sudo firewall-cmd --reload
   ```

2. **限制访问来源**（可选）：
   ```bash
   # Ubuntu/Debian
   sudo ufw allow from 192.168.1.0/24 to any port 8094
   
   # CentOS/RHEL
   sudo firewall-cmd --add-rich-rule='rule family="ipv4" source address="192.168.1.0/24" port port="8094" protocol="tcp" accept' --permanent
   sudo firewall-cmd --reload
   ```

### 7.3 HTTPS配置

为了提高安全性，建议使用HTTPS协议访问服务。可以使用Nginx或Apache作为反向代理，并配置SSL证书。

**示例Nginx配置**：
```nginx
server {
    listen 443 ssl;
    server_name your-domain.com;
    
    ssl_certificate /path/to/ssl/cert.pem;
    ssl_certificate_key /path/to/ssl/key.pem;
    
    location / {
        proxy_pass http://localhost:8094;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## 8. 故障排除

### 8.1 服务无法启动

1. **检查Python路径**：
   ```bash
   which python3
   ```
   
   确保服务配置中的`ExecStart`使用正确的Python路径。

2. **检查依赖**：
   ```bash
   pip3 list | grep -E "Flask|Flask-CORS|Werkzeug"
   ```
   
   如果缺少依赖，重新安装：
   ```bash
   pip3 install flask flask-cors werkzeug
   ```

3. **查看服务日志**：
   ```bash
   sudo journalctl -u file_upload.service -n 50
   ```

### 8.2 无法访问服务

1. **检查端口是否被占用**：
   ```bash
   netstat -tlnp | grep 8094
   ```

2. **检查防火墙设置**：
   ```bash
   # Ubuntu/Debian
   sudo ufw status
   
   # CentOS/RHEL
   sudo firewall-cmd --list-ports
   ```

3. **检查服务是否在监听所有网络接口**：
   ```bash
   sudo ss -tuln | grep 8094
   ```
   
   确保输出中包含`0.0.0.0:8094`或`:::8094`。

### 8.3 上传文件失败

1. **检查文件大小**：
   确保上传的文件大小不超过配置的`MAX_CONTENT_LENGTH`。

2. **检查文件类型**：
   确保上传的文件类型在`ALLOWED_EXTENSIONS`中。

3. **检查上传文件夹权限**：
   ```bash
   ls -la /home/a214/result
   ```
   
   确保服务运行用户具有写入权限。

## 9. 最佳实践

1. **使用虚拟环境**：
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install flask flask-cors werkzeug
   ```
   
   然后修改服务配置中的`ExecStart`：
   ```ini
   ExecStart=/home/a214/VideoProject/venv/bin/python file_upload_server.py
   ```

2. **定期清理上传的文件**：
   创建一个定时任务，定期清理超过一定时间的文件：
   ```bash
   sudo crontab -e
   ```
   
   添加以下内容（每天凌晨2点清理30天前的文件）：
   ```
   0 2 * * * find /home/a214/result -type f -mtime +30 -delete
   ```

3. **监控服务状态**：
   使用监控工具（如Prometheus+Grafana）监控服务运行状态和资源使用情况。

4. **备份配置文件**：
   ```bash
   cp /etc/systemd/system/file_upload.service /home/a214/VideoProject/
   ```

5. **使用版本控制**：
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   ```

## 10. 更新和升级

### 10.1 更新服务代码

1. **上传新的代码文件**：
   将更新后的`file_upload_server.py`上传到项目目录。

2. **重启服务**：
   ```bash
   sudo systemctl restart file_upload.service
   ```

### 10.2 升级依赖

1. **升级pip**：
   ```bash
   pip3 install --upgrade pip
   ```

2. **升级项目依赖**：
   ```bash
   pip3 install --upgrade flask flask-cors werkzeug
   ```

3. **重启服务**：
   ```bash
   sudo systemctl restart file_upload.service
   ```

## 11. 卸载服务

1. **停止并禁用服务**：
   ```bash
   sudo systemctl stop file_upload.service
   sudo systemctl disable file_upload.service
   ```

2. **删除服务配置文件**：
   ```bash
   sudo rm /etc/systemd/system/file_upload.service
   sudo systemctl daemon-reload
   ```

3. **删除项目文件**：
   ```bash
   rm -rf /home/a214/VideoProject
   ```

4. **删除上传文件夹**（可选）：
   ```bash
   rm -rf /home/a214/result
   ```

5. **删除专用用户**（可选）：
   ```bash
   sudo userdel uploaduser
   ```

## 12. 联系方式

如果您在部署或使用过程中遇到问题，欢迎联系我们：

- 邮箱：your-email@example.com
- 电话：+86 123 4567 8910
- GitHub：https://github.com/your-username/file-upload-server

## 13. 许可证

本项目采用MIT许可证，详情请见LICENSE文件。

## 14. 变更日志

### v1.0.0 (2025-12-31)
- 初始版本
- 支持多种文件类型上传
- 支持外部网络访问
- 支持CORS跨域访问
- 支持通过环境变量配置
- 支持开机自启动
- 提供完整的API接口

---

**部署完成后，您可以通过以下URL访问服务：**
- 健康检查：http://your-server-ip:8094/health
- 文件上传：http://your-server-ip:8094/upload
- 列出文件：http://your-server-ip:8094/files

祝您使用愉快！