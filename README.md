# TaishanPi RK3566 Server

立创 RK3566 开发板改装服务器工程。

这个仓库现在包含：

- Web 主控制台：`www/site/index.html`
- HDMI 本地控制面板：`www/kiosk.html`
- Flask 后端：`apps/filemgr/app.py`
- Nginx / systemd / 安装脚本：`deploy/`
- 项目笔记与架构文档：`00-09*.md`

## 功能

- 文件管理、上传下载、目录浏览、文件预览
- 用户登录、权限控制、修改密码
- Windows 工作站在线检测、WOL 唤醒、SSH 关机
- Syncthing 状态显示、启停控制、设备管理
- HDMI 本地 kiosk 控制面板
- `eth0` 直连固定地址：`192.168.50.1/24`

## 新开发板一键部署

新板只要能联网，执行：

```bash
sudo apt update
sudo apt install -y git
git clone https://github.com/YOUR_GITHUB_NAME/taishanpi-rk3566-server.git
cd taishanpi-rk3566-server
sudo ./deploy/install.sh
sudo reboot
```

安装脚本会自动：

- 安装 Nginx、Python、OpenSSH
- 部署 Web 页面到 `/userdata/server/www/site`
- 部署 Flask 后端到 `/userdata/server/apps/filemgr`
- 部署 `filemgr.service` 和 `eth0-direct.service`
- 固定 `eth0 = 192.168.50.1/24`
- 安装 HDMI kiosk 脚本并配置自启动

安装完成后，继续按清单补设备私有配置：

```text
deploy/post-install.md
```

## 仓库上传到 GitHub

首次上传：

```powershell
cd "C:\Users\20634\Desktop\my notion\my notion\其他项目\立创开发板3566改装服务器"
git init
git add .
git commit -m "Initial import of TaishanPi RK3566 server project"
git branch -M main
git remote add origin https://github.com/YOUR_GITHUB_NAME/taishanpi-rk3566-server.git
git push -u origin main
```

后续更新：

```powershell
cd "C:\Users\20634\Desktop\my notion\my notion\其他项目\立创开发板3566改装服务器"
git add .
git commit -m "Update dashboard and backend"
git push
```

## 新板拉取更新

如果新开发板已经部署过一次，后续更新只要：

```bash
cd ~/taishanpi-rk3566-server
git pull
sudo ./deploy/install.sh
sudo systemctl restart nginx
sudo systemctl restart filemgr
```

## 不要提交到 GitHub 的内容

仓库里只保留示例文件，不提交真实运行配置。

不要提交：

- `apps/filemgr/users.json`
- `apps/filemgr/devices.json`
- Cloudflare token / tunnel 凭据
- 私钥、证书、明文密码

只提交：

- `apps/filemgr/users.example.json`
- `apps/filemgr/devices.example.json`

## 推荐目录结构

```text
apps/filemgr/app.py
apps/filemgr/requirements.txt
apps/filemgr/users.example.json
apps/filemgr/devices.example.json
deploy/install.sh
deploy/nginx-default.conf
deploy/systemd/filemgr.service
deploy/systemd/eth0-direct.service
www/site/index.html
www/kiosk.html
```

## 首次部署后需要手工补的项目

以下内容通常与具体设备强绑定，不建议写死进仓库：

- 新板 WiFi 名称和密码
- Cloudflare Tunnel token
- Syncthing 实际设备配对
- Windows 工作站真实 SSH 密码

## 验证命令

```bash
sudo systemctl status nginx --no-pager
sudo systemctl status filemgr --no-pager
sudo systemctl status eth0-direct --no-pager
ip -4 addr show eth0
curl -I http://127.0.0.1
```

如果要验证有线直连：

```bash
ping -c 4 192.168.50.2
```

## 说明

当前仓库已经补入最新：

- 主 Web 控制台
- Flask 后端
- 部署脚本

因此后续新开发板可以按“克隆仓库 -> 执行安装脚本”方式直接落地，再补少量设备私有配置即可。
