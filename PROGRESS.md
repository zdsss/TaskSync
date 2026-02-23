# TaskSync 进度记录

## 当前状态

**本地可运行，API 调试中，尚未部署到 Render。**

---

## 已完成

- [x] 项目文件全部创建完毕（`app.py`, `task_decomposer.py`, `calendar_generator.py`, `templates/index.html`, `requirements.txt`, `Procfile`, `render.yaml`）
- [x] 依赖安装完成（`pip install -r requirements.txt`）
- [x] 修复 `httpx` 版本冲突：`openai==1.30.5` 与 `httpx==0.28` 不兼容，已锁定 `httpx==0.27.2`
- [x] 前端新增 **Model Name** 输入框，模型名可自定义（不再硬编码 `claude-sonnet-4-5`）
- [x] Git 初始化并完成首次 commit（`9d70fab`）

---

## 待完成

- [ ] **本地 API 联调通过**（见下方调试记录）
- [ ] 推送到 GitHub
- [ ] 部署到 Render

---

## 调试记录（API 连接问题）

遇到过以下错误，逐一排查：

| 错误 | 原因 | 解决方法 |
|------|------|----------|
| `unexpected keyword argument 'proxies'` | `httpx==0.28` 移除了 `proxies` 参数 | 锁定 `httpx==0.27.2` |
| `405 Not Allowed` | base URL 填错，指向了不接受 POST 的路径 | base URL 必须以 `/v1` 结尾 |
| `503 model_not_found` | 中转服务商该分组下无可用 Claude 渠道 | 换模型名或联系服务商 |
| `404 Invalid URL (POST /v1/messages/chat/completions)` | base URL 末尾多填了 `/messages`，拼出了错误路径 | base URL 只填到 `/v1`，不带 `/messages` |

**当前卡点：** base URL 格式问题已定位，正确格式为 `https://域名/v1`（不含 `/messages`）。

---

## 本地运行方式

```bash
cd "D:/Program/tools/TaskSync"
python app.py
# 访问 http://localhost:5000
```

表单填写说明：
- **API Key**：中转服务商的 key
- **API Base URL**：`https://你的域名/v1`（结尾是 `/v1`，不带 `/messages`）
- **Model Name**：服务商控制台里列出的可用模型名

---

## 部署步骤（待执行）

1. 在 GitHub 创建仓库（`github.com/new`）
2. 推送代码：
   ```bash
   git remote add origin https://github.com/你的用户名/tasksync.git
   git push -u origin master
   ```
3. 登录 [render.com](https://render.com) → New Web Service → 连接 GitHub 仓库
4. Render 自动读取 `render.yaml`，点击 Deploy
5. 部署完成后访问 `https://tasksync-xxxx.onrender.com`

> 注意：Render 免费套餐 15 分钟无请求后会休眠，首次唤醒约 30 秒。
