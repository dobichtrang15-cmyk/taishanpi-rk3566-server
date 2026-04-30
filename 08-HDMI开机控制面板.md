# HDMI 开机控制面板

## 目标

让开发板通过 HDMI 接显示器后，不停留在 Ubuntu 登录界面，而是在开机后自动显示服务器控制面板。

当前项目已经有 Web 控制面板：

```text
Nginx 入口：127.0.0.1:80
前端页面：/userdata/server/www/site/index.html
Flask API：127.0.0.1:5000
```

所以 HDMI 本地屏幕推荐直接全屏打开：

```text
http://127.0.0.1
```

## 推荐方案

采用 kiosk 模式：

```text
系统启动
  -> 自动登录 dashboard 专用用户
  -> 启动图形桌面会话
  -> 自动打开全屏浏览器
  -> 显示 http://127.0.0.1 控制面板
```

这个方案不重写现有后端，不影响 Nginx、Flask、cloudflared、eth0-direct 等服务。

## 一键部署

把 `scripts/setup-kiosk-dashboard.sh` 复制到开发板，然后执行：

```bash
chmod +x setup-kiosk-dashboard.sh
sudo DASHBOARD_URL=http://127.0.0.1 ./setup-kiosk-dashboard.sh
sudo reboot
```

如果以后控制面板地址变成其他端口，例如：

```text
http://127.0.0.1:8080
```

则执行：

```bash
sudo DASHBOARD_URL=http://127.0.0.1:8080 ./setup-kiosk-dashboard.sh
sudo reboot
```

## 小屏幕缩放

如果 HDMI 屏幕较小，页面显示不全，可以降低浏览器缩放比例。

编辑：

```bash
sudo nano /etc/dashboard-kiosk.conf
```

内容示例：

```bash
DASHBOARD_URL="http://127.0.0.1"
DASHBOARD_SCALE="0.70"
```

建议从这些值里试：

```text
0.85
0.75
0.70
0.60
```

保存后重启图形登录或直接重启：

```bash
sudo reboot
```

## 部署后预期

重启后：

- 系统自动登录 `dashboard` 用户。
- 屏幕自动打开全屏控制面板。
- 鼠标指针空闲后自动隐藏。
- 屏幕不自动息屏。
- 现有 Web 服务仍然由 `nginx`、`filemgr`、`cloudflared` 管理。

## 退出和排查

如果需要退出全屏界面，可以接键盘：

```text
Alt + F4
```

如果界面卡住，可以切换到命令行 TTY：

```text
Ctrl + Alt + F3
```

查看服务状态：

```bash
sudo systemctl status nginx --no-pager
sudo systemctl status filemgr --no-pager
sudo systemctl status cloudflared --no-pager
```

查看自动登录配置：

```bash
cat /etc/dashboard-kiosk.conf
ls -l /home/dashboard/.config/autostart/dashboard-kiosk.desktop
```

手动测试 kiosk 启动：

```bash
sudo -u dashboard DISPLAY=:0 /usr/local/bin/dashboard-kiosk.sh
```

## 回滚

如果不想再开机显示控制面板：

```bash
sudo rm -f /home/dashboard/.config/autostart/dashboard-kiosk.desktop
```

如果要关闭自动登录，需要按实际登录管理器修改：

### GDM

编辑：

```bash
sudo nano /etc/gdm3/custom.conf
```

把下面两项改掉或注释掉：

```ini
AutomaticLoginEnable=false
# AutomaticLogin=dashboard
```

### LightDM

删除：

```bash
sudo rm -f /etc/lightdm/lightdm.conf.d/50-dashboard-autologin.conf
```

### SDDM

删除：

```bash
sudo rm -f /etc/sddm.conf.d/50-dashboard-autologin.conf
```

然后重启：

```bash
sudo reboot
```

## 后续可选优化

如果觉得浏览器太重，可以第二阶段改成 PyQt 本地界面，但建议继续调用现有 Flask API，不要重复实现文件管理和设备控制逻辑。

## 小屏专用界面

如果普通后台页面在 HDMI 小屏上显示不全，使用项目里的小屏界面：

```text
www/kiosk.html
```

这个页面只保留本地屏幕常用能力：

- 登录。
- 查看登录、笔记本、同步状态。
- 大按钮唤醒电脑。
- 大按钮关闭电脑。
- 简化查看文件根目录。
- 简化查看 Syncthing 状态。

部署方式：

```bash
sudo ./install-kiosk-ui.sh ./kiosk.html
sudo reboot
```

部署后 kiosk 浏览器打开：

```text
http://127.0.0.1/kiosk.html
```

完整文件管理后台仍然保留在：

```text
http://127.0.0.1/
```
