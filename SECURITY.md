# 安全说明

## 支持范围

该项目是个人家庭服务器，不提供公开托管服务的安全保证。部署者负责操作系统更新、网络边界、备份和账号管理。

## 不应提交的内容

- `users.json`、`devices.json`、`tokens.json`
- `secret.key`、SSH 私钥、TLS 私钥
- Cloudflare Tunnel Token 和凭据
- Syncthing API Key、设备配置和加密密码
- Matter Fabric 运行态
- 真实账号密码和备份包

提交前运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\validate-project.ps1
```

## 首次账号

新环境不再使用固定默认密码。若未设置 `FILEMGR_BOOTSTRAP_PASSWORD`，服务会生成随机管理员密码并写入：

```text
/opt/taishanpi-server/apps/filemgr/bootstrap-admin.txt
```

首次登录并修改密码后应删除该文件。

## 网络暴露

- Flask 5000 端口不应直接暴露到互联网。
- Matter UDP 5540 和 mDNS UDP 5353 不应做公网端口映射。
- 公网访问应经过 HTTPS 反向代理或 Cloudflare Tunnel。
- 推荐在公网入口增加 Cloudflare Access、速率限制或额外的短期令牌。
- Syncthing GUI 不应在没有认证的情况下暴露到公网。

## Windows SSH

推荐使用专门的低权限 Windows 用户和 SSH 密钥。若使用密码：

- 使用独立强密码。
- 限制 Windows 防火墙仅允许直连网段访问 TCP 22。
- 不要把密码写入示例文件、文档或 Git。

关机账号只应获得完成关机所需的权限。

## 本地 Kiosk 信任

后端允许来自真实回环地址的 kiosk 请求使用本地身份。Nginx 必须正确覆盖 `X-Real-IP` 和 `X-Forwarded-For`，不能信任公网客户端自行传入的回环头。

## 凭据泄漏处理

如果怀疑仓库或备份泄漏：

1. 修改所有 Web 用户密码。
2. 删除 `tokens.json` 并重启 `filemgr`，撤销现有 Bearer Token。
3. 轮换 Cloudflare Tunnel Token、SSH 密钥和 Syncthing API Key。
4. 若 Matter Fabric 泄漏，删除控制器中的设备、清理设备 Fabric 后重新配对。
5. 检查 Git 历史，而不只是当前工作树。

## 漏洞报告

请通过 GitHub 仓库的私有漏洞报告功能联系仓库所有者。不要在公开 Issue 中粘贴密码、Token、私钥、家庭 IP、完整日志或备份。
