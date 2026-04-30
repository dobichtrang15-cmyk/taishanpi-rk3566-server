# 新开发板安装后手工配置清单

适用场景：

- 新开发板刚执行完 `sudo ./deploy/install.sh`
- 系统已经重启
- Nginx / filemgr / eth0-direct 已安装
- 需要补充每台设备自己的私有配置

## 1. 连接 WiFi

先确认 `nmcli` 可用：

```bash
which nmcli
```

连接 WiFi：

```bash
sudo nmcli dev wifi connect "你的WiFi名称" password "你的WiFi密码" ifname wlan0
```

检查是否联网：

```bash
nmcli dev status
ip a show wlan0
ip route
ping -c 4 223.5.5.5
ping -c 4 baidu.com
```

预期：

```text
wlan0 connected
有 inet 192.168.x.x
default via ... dev wlan0
ping 能通
```

## 2. 确认有线直连地址

安装脚本会自动配置：

```text
eth0 = 192.168.50.1/24
```

检查：

```bash
ip a show eth0
ip route | grep 192.168.50
```

如果电脑也配置了：

```text
Windows 以太网 = 192.168.50.2/24
```

则可测试：

```bash
ping -c 4 192.168.50.2
```

## 3. 检查基础服务

```bash
sudo systemctl status nginx --no-pager
sudo systemctl status filemgr --no-pager
sudo systemctl status eth0-direct --no-pager
sudo systemctl status ssh --no-pager
```

本机测试：

```bash
curl -I http://127.0.0.1
```

## 4. 初始化真实用户配置

仓库里只带示例文件，不带真实用户。

首次部署后如果还没有真实配置，可从示例复制：

```bash
cd /userdata/server/apps/filemgr
sudo cp -n users.example.json users.json
sudo cp -n devices.example.json devices.json
sudo chown lckfb:lckfb users.json devices.json
sudo chmod 600 users.json devices.json
```

然后按你的实际账号需求修改：

```bash
sudo nano /userdata/server/apps/filemgr/users.json
sudo nano /userdata/server/apps/filemgr/devices.json
```

修改后重启：

```bash
sudo systemctl restart filemgr
```

## 5. 配置服务器网页管理员账号

建议直接通过网页完成，而不是长期手改 JSON。

访问：

```text
http://开发板IP
```

首次登录后：

- 修改管理员密码
- 新建普通用户
- 配置用户权限

注意：

- 不要把真实密码提交到 GitHub
- `users.json` 只留在板子本地

## 6. 配置 Windows 工作站控制

在网页“设备控制”中填写：

```text
设备名称：例如 JJ的破电脑
笔记本 IP / 主机名：192.168.50.2
MAC 地址：你的 Windows 有线网卡 MAC
广播地址：192.168.50.255
SSH 用户名：woladmin
SSH 密码：你的真实密码
SSH 端口：22
远程关机命令：shutdown /s /f /t 0
```

保存后测试：

- 检测在线
- 网络唤醒
- 远程关机

## 7. Windows 侧准备项

### 7.1 配置有线直连 IP

管理员 PowerShell：

```powershell
New-NetIPAddress -InterfaceAlias "以太网" -IPAddress 192.168.50.2 -PrefixLength 24
```

### 7.2 启用 OpenSSH Server

```powershell
Start-Service sshd
Set-Service -Name sshd -StartupType Automatic
New-NetFirewallRule -Name "OpenSSH-22-Ethernet" -DisplayName "OpenSSH 22 Ethernet" -Direction Inbound -Protocol TCP -LocalPort 22 -Action Allow
```

### 7.3 启用 WOL

确认：

- BIOS 已开启 Wake on LAN
- Windows 已关闭快速启动
- 网卡启用：
  - Wake on Magic Packet
  - S5 Wake on LAN
  - 关闭 Green Ethernet

## 8. 配置 Cloudflare Tunnel

如果你要用原公网域名，需要补这一步。

安装和服务检查：

```bash
cloudflared --version
sudo systemctl status cloudflared --no-pager
```

如果是新板，通常要重新注入 tunnel token：

```bash
sudo cloudflared service install <你的TUNNEL_TOKEN>
sudo systemctl enable cloudflared
sudo systemctl start cloudflared
```

检查日志：

```bash
sudo journalctl -u cloudflared -n 50 --no-pager
```

注意：

- 域名通常不用换
- 只要 tunnel token 对、开发板能联网，原域名可继续使用

## 9. 配置 Syncthing

安装脚本不会自动完成设备配对，首次部署后要手工做。

启动服务：

```bash
sudo systemctl enable syncthing@lckfb
sudo systemctl start syncthing@lckfb
sudo systemctl status syncthing@lckfb --no-pager
```

浏览器打开：

```text
http://192.168.50.1:8384
```

然后完成：

- 设置 GUI 用户名和密码
- 和 Windows 设备互加设备 ID
- 共享 `obsidian-vault`

## 10. VS Code SSH 连接

Windows 的 `C:\Users\20634\.ssh\config` 建议至少有：

```sshconfig
Host taishanpi
    HostName 192.168.50.1
    User lckfb
    Port 22
    IdentityFile C:\Users\20634\.ssh\id_ed25519
```

测试：

```powershell
ssh taishanpi
```

## 11. 安装完成后的总验证

开发板执行：

```bash
ip a show wlan0
ip a show eth0
hostname -I
sudo systemctl status nginx --no-pager
sudo systemctl status filemgr --no-pager
sudo systemctl status cloudflared --no-pager
sudo systemctl status syncthing@lckfb --no-pager
curl -I http://127.0.0.1
```

网页验证：

- 首页能打开
- 文件管理正常
- 设备控制正常
- 同步管理正常

## 12. 不要提交回仓库的文件

这些文件只保留在板子本地：

```text
/userdata/server/apps/filemgr/users.json
/userdata/server/apps/filemgr/devices.json
/etc/sudoers.d/filemgr-syncthing
Cloudflare tunnel token
真实 SSH 密码
```

## 13. 最终原则

可以提交到 GitHub 的内容：

- 源代码
- 部署脚本
- 示例配置
- 文档

不要提交到 GitHub 的内容：

- 明文密码
- token
- 私钥
- 真实用户数据
