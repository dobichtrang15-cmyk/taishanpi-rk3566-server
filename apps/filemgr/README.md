# File Manager Backend

Flask 后端负责认证、文件操作、Windows 工作站控制和 Syncthing 管理。

运行配置通过 `/etc/default/filemgr` 注入，模板见 `deploy/filemgr.env`。

新环境不存在 `users.json` 时会生成随机管理员密码，凭据临时保存在 `bootstrap-admin.txt`。首次登录修改密码后删除该文件。

不得提交：

- `users.json`
- `devices.json`
- `tokens.json`
- `secret.key`
- `bootstrap-admin.txt`

仓库只保留：

- `users.example.json`
- `devices.example.json`
- `requirements.txt`

语法检查：

```bash
python3 -m py_compile app.py
```
