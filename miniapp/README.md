# 微信小程序骨架

这个目录是给现有 Flask `filemgr` 后端配套的小程序前端骨架。

API 域名集中配置在 `miniapp/config.js`：

```js
module.exports = {
  BASE_URL: "https://your-domain.example",
};
```

微信后台必须将相同 HTTPS 域名加入 request、uploadFile 和 downloadFile 合法域名。

当前实现特点：

- 直接复用现有 `/api/*` 接口
- 认证方式先兼容现有 Flask session
- 小程序侧手动保存 `Set-Cookie`，后续请求自动带 `Cookie`
- 先覆盖登录、概览、文件管理、设备控制、同步管理

## 目录

```text
miniapp/
  app.js
  app.json
  app.wxss
  project.config.json
  sitemap.json
  utils/
    api.js
    auth.js
    request.js
  pages/
    login/
    overview/
    files/
    device/
    sync/
```

## 使用方式

1. 用微信开发者工具打开 `miniapp/`
2. 修改 [project.config.json](project.config.json) 里的 `appid`
3. 确认 `utils/request.js` 里的 `BASE_URL`
4. 在微信公众平台配置：
   - request 合法域名
   - uploadFile 合法域名
   - downloadFile 合法域名

## 当前依赖

小程序默认使用：

- `https://files.jjpersonal.xyz`

如果你后面把 API 切到云服务器独立域名，只需要改：

- [request.js](utils/request.js)

## 后续建议

- 第二阶段把 Flask session 改成 Bearer Token
- 补文件预览页
- 补管理员用户管理页
- 补更细的异常提示和危险动作确认
