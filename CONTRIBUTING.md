# 参与维护

## 开发流程

1. 从 `main` 创建功能分支。
2. 一次提交只处理一个明确主题。
3. 修改 API、部署方式或配置项时同步更新文档。
4. 不提交真实运行态和凭据。
5. 推送前运行本地验证脚本。

## 本地验证

Windows：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\validate-project.ps1
```

Linux：

```bash
python3 -m py_compile apps/filemgr/app.py
node --check apps/matter-workstation/src/index.mjs
bash -n deploy/install.sh deploy/update.sh deploy/backup.sh
```

Matter 依赖安装后：

```bash
npm --prefix apps/matter-workstation run check
```

## 修改约束

- 不把设备 IP、MAC、域名和账号写死在新增业务代码中。
- 新运行配置优先放入 `/etc/default/*` 环境文件。
- 保持 `deploy/install.sh` 可重复执行，不覆盖已有私有配置。
- 不在普通更新中删除 Matter 存储目录。
- Shell、Python、JavaScript 和 systemd 文件使用 LF。
- 新增依赖时更新锁文件或版本范围，并说明最低运行版本。

## 提交信息

推荐格式：

```text
类型: 简短说明
```

常用类型：`feat`、`fix`、`docs`、`deploy`、`security`、`refactor`、`test`。

## 发布检查

- Git 工作树只包含预期改动。
- `scripts/validate-project.ps1` 通过。
- 发布包不包含私有配置。
- 在目标板上检查 Nginx、Flask、Matter 和直连网口服务。
- 更新 `CHANGELOG.md`。
