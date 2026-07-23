# 变更记录

本项目采用日期版本记录重要变化。

## 2026-07-23

### 新增

- 完整项目背景、架构、迁移、安全和维护文档。
- GitHub Actions 基础验证。
- 本地项目验证脚本。
- `filemgr`、Matter 和直连网口环境配置模板。
- 稳定运行路径 `/opt/taishanpi-server` 和 `/srv/taishanpi-files`。

### 改进

- 安装路径和文件路径可通过环境变量配置。
- 安装脚本支持无桌面、无 Matter 和跳过 APT 模式。
- Node.js 可从 `/usr/bin` 或 `/usr/local/bin` 发现。
- Python 依赖增加兼容 Python 3.8 的版本范围。
- 新部署使用随机管理员密码，不再使用固定默认密码。
- README 链接改为 GitHub 可用的相对路径。

### 保留

- 已存在的用户、设备和 Matter Fabric 不会在正常安装或更新中被覆盖。

## 2026-06-29

### 新增

- matter.js 工作站电源桥。
- Apple“家庭”Matter 开机、关机和状态同步。
- Bearer Token 登录支持和微信小程序接口。
- 项目发布打包脚本及维护文档。

## 早期版本

- Flask/Nginx 文件服务器。
- Syncthing 管理。
- HDMI kiosk 与 Qt 原型。
- WOL 开机和 Windows OpenSSH 关机。
- Cloudflare Tunnel 与反向 SSH 联动记录。
