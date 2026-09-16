# 本地安装与使用教程

这份教程面向第一次接触本项目的人。整个过程只需要装一个 Docker，然后在项目目录里运行一条命令，
不需要安装 Python、Node.js，也不需要懂编程。

---

## 一、先装好 Docker

| 系统 | 要装的东西 |
| --- | --- |
| Windows 10/11 | [Docker Desktop](https://www.docker.com/products/docker-desktop/)，安装时保持勾选 WSL2 |
| macOS | [Docker Desktop](https://www.docker.com/products/docker-desktop/)（选 Apple Silicon 或 Intel 版本） |
| Linux | `docker` 与 `docker compose` 插件（发行版仓库或 Docker 官方源） |

装完后**启动 Docker Desktop**，等托盘/菜单栏图标变成运行状态。打开命令行确认：

```sh
docker --version
docker compose version
```

两条都能打印版本号，就说明准备好了。

### 国内网络提示

第一次运行需要从 Docker Hub 拉取基础镜像（合计约 2 GB）。如果下载很慢或一直失败，可以任选一种办法：

1. **走代理**：Docker Desktop → Settings → Resources → Proxies，填上本机代理地址（例如 `http://127.0.0.1:7892`），应用后重启 Docker。
2. **配置镜像加速**：Docker Desktop → Settings → Docker Engine，在 JSON 里加
   `"registry-mirrors": ["https://<可用的镜像地址>"]`，保存后重启 Docker。
3. **使用离线镜像包**：向提供项目的人索取 `ai-knowledge-agent-images.tar`，然后执行
   `docker load -i ai-knowledge-agent-images.tar`，之后启动时就不需要再联网拉镜像。

> 使用在线模型（例如 DeepSeek）时需要能访问对应服务商的接口；不配置模型也能用，见第五节。

---

## 二、拿到项目

**方式 A（推荐）**：把 `ai-knowledge-structuring-agent-source.zip` 解压到任意目录，例如 `D:\projects\`。

**方式 B**：使用 Git 克隆。

```sh
git clone https://github.com/Index0203/ai-knowledge-structuring-agent.git
```

---

## 三、一键启动

在项目目录里执行：

| 系统 | 命令 |
| --- | --- |
| Windows | 双击 `scripts\deploy.cmd`；或在项目目录执行 `powershell -ExecutionPolicy Bypass -File scripts\deploy.ps1` |
| macOS / Linux | `sh scripts/deploy.sh` |

脚本会自动完成：生成配置文件 `.env` → 构建镜像 → 启动全部服务 → 执行数据库迁移 → 等待服务就绪 →
打印访问地址。

首次构建大约需要 3–10 分钟（取决于网速和机器性能），之后再启动通常只要几十秒。
看到「部署完成」后，用浏览器打开：

```
http://localhost:3000
```

---

## 四、怎么用

1. **上传资料**：点击「选择文件」，选择 PDF 或 DOCX（单个文件最大 25 MB）。扫描版 PDF 也可以，系统会自动 OCR。
2. **生成结构**：两个入口——
   - 「生成思维导图」：只看章节结构，不做问答；
   - 「生成知识地图」：结构 + 节点搜索 + 基于原文的问答。
3. **等待处理**：普通文档一到两分钟；扫描件较慢（OCR 约 3 秒/页），页面会显示当前进度。
4. **查看与编辑**：地图支持滚轮平移、Ctrl+滚轮缩放；点击节点查看详情；
   - 回车：给选中节点新增子节点
   - 双击：编辑节点标题与内容
   - Delete：删除选中节点
   - 拖拽节点：移到别的分支下（松手保持位置）
   - Ctrl+Z / Ctrl+Y：撤销 / 重做
5. **保存与导出**：点右上角「下载 XMind」，把当前（含你编辑过的）结构导出成本地 `.xmind` 文件，可直接用 XMind 打开。
6. **节点问答**：选中节点后，右侧「节点 AI 助手」提供解释、举例、深入学习、生成测试问题，以及自由提问。
   回答只使用该节点的原文证据并附引用；证据不足时会明确拒答，不会编造。

---

## 五、（可选）接入自己的模型

不配置模型也能完整使用：系统会进入**降级模式**——知识结构取自文档自身的章节层级，回答是原文摘录，
界面会明确标注，不会假装成模型生成的内容。

如果要启用模型，编辑项目根目录的 `.env`：

```ini
OPENAI_API_KEY=你的密钥
OPENAI_MODEL=模型名
OPENAI_BASE_URL=接口地址
```

保存后重新创建容器让它生效（`restart` 不会重新读取 `.env`）：

```sh
docker compose -f docker-compose.prod.yml up -d
```

---

## 六、常见问题

| 现象 | 处理 |
| --- | --- |
| 提示找不到 `docker` 命令 | Docker 没安装或没启动，见第一节 |
| 启动时报端口被占用（3000 / 8000） | 编辑 `.env` 里的 `FRONTEND_PORT` / `BACKEND_PORT` 换成其它端口，再重跑启动脚本 |
| 一直卡在 Pulling / 拉取超时 | 网络问题，按第一节配置代理或镜像加速，或改用离线镜像包 |
| PowerShell 提示「禁止运行脚本」 | 改用 `scripts\deploy.cmd`（它已带 `-ExecutionPolicy Bypass`） |
| 后端一直不健康，日志报数据库连接失败 | 如果改过 `POSTGRES_PASSWORD`，记得同时修改 `DATABASE_URL` 里的密码 |
| 页面能打开但操作报错 | 确认 `.env` 里的 `NEXT_PUBLIC_API_BASE_URL` 是浏览器能访问到的地址；改过之后要重新构建前端镜像（`up -d --build`） |
| 想彻底重来 | `docker compose -f docker-compose.prod.yml down -v`（**会删除全部数据**，谨慎使用） |
| 只想停止服务 | `docker compose -f docker-compose.prod.yml down`（数据保留） |
| 更新到新版本 | 拉取最新代码后重新运行启动脚本，它会重建镜像并重启服务 |

---

## 七、数据放在哪里

所有数据都在 Docker 命名卷里，删除容器不会丢失：

`postgres_data`（数据库）、`redis_data`（队列）、`chroma_data`（向量索引）、
`minio_data`（对象存储）、`backend_upload_data`（上传的原始文件与解析中间文件）。

备份数据库：

```sh
docker compose -f docker-compose.prod.yml exec -T postgres pg_dump -U app knowledge_agent > backup.sql
```

---

## 八、把链接发给同一局域网的人

页面会自动使用"当前访问地址"去连接后端：对方用 `http://<这台机器的IP>:3000` 打开，请求就发到
`http://<这台机器的IP>:8000`，不需要改任何配置，也不需要重新构建。

步骤：

1. 在运行项目的这台机器上执行 `powershell -ExecutionPolicy Bypass -File scripts\link.ps1`
   （macOS/Linux 用 `sh scripts/link.sh`），它会直接打印"自己访问"和"分享给同一 WiFi"两条链接，并检查服务是否在运行。
2. 把"分享"那条发出去，例如 `http://192.168.1.10:3000`。
3. 对方在浏览器打开即可使用（建议用 Chrome / Edge）。

也可以手动查询地址：执行 `ipconfig`，找到"无线局域网适配器 WLAN"下的 IPv4 地址，再拼成 `http://<该地址>:3000`。

如果对方打不开，按顺序排查：

| 现象 | 原因与处理 |
| --- | --- |
| 一直转圈、打不开 | 两台设备不在同一 WiFi；或该 WiFi 开启了"客户端隔离"（校园网、酒店网络常见），改用手机热点重试 |
| 页面能开但上传/提问失败 | 让对方先访问 `http://<你的IP>:8000/health`，能看到 `{"status":"ok"}` 说明网络通；若不通就是网络隔离问题 |
| 换了 WiFi 后对方打不开 | IP 变了，重新运行 `scripts\link.ps1` 拿到新链接发出去即可（不需要改配置） |

> ⚠️ 注意：接口目前**没有鉴权**，同一个网络里的人打开链接就能看到数据库里的全部文档，也能上传和删除。
> 只适合局域网内给同学/同事演示，不要把它直接暴露到公网。
