# Matter Windows电脑电源桥接

该服务将现有 Flask 工作站控制 API 暴露为 Matter `On/Off Plug-in Unit`：

- 打开：`POST /api/device/workstation/wake`
- 关闭：`POST /api/device/workstation/shutdown`
- 状态：`GET /api/device/workstation/status`

配网信息会输出到 systemd 日志：

```bash
sudo journalctl -u matter-workstation -n 100 --no-pager
```

首次启动后，在日志中找到 `QR payload` 或 `manual pairing code`，在 iPhone「家庭」中添加 Matter 配件。

默认参数位于 `deploy/matter-workstation.env`，配对成功后不要随意修改设备ID、端口或删除 `/var/lib/matter-workstation`。

运行要求：

- Node.js 22.13+
- `@matter/main` 0.17.3
- 本机 Flask API 可访问
- 局域网允许 mDNS、IPv6 链路本地通信和 UDP 5540

本地检查：

```bash
npm install
npm run check
npm start -- --storage-path=./data
```

`data/` 和生产环境 `/var/lib/matter-workstation` 都属于私有运行态，不应提交。

注意：Matter Bridge 不是 Apple 家庭中枢。没有 HomePod/Apple TV 时，iPhone 离开局域网后的 Apple“家庭”远程控制不受保证。
