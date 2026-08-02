# 皓月 3D 需求解析网站

一个面向普通用户的单页工具：上传一张完整需求图，可选补充文字与“丰富趣味”，后台自动执行完整 Skill、加入固定图2、调用多模态模型并校验输出。提示词通过审查后先停留在页面供人工检查，用户确认无误后再生成结果图。

桌面端采用 16:9 单屏生产线：固定左侧历史轨道，上传、处理中和结果在同一工作面内切换；正向提示词、负面提示词、解析详情和结果图使用页签切换。解析或生图开始后可选择“另起一个任务”，原任务留在后台继续，历史轨道持续显示每项任务的需求图、短编号和独立状态。结果完成后可点击“修改需求”，继续编辑补充要求，并选择沿用原图或重新上传一张新版图1；提交后建立独立的新任务，旧任务和旧结果继续保留。历史轨道不提供收起或关闭开关；小屏幕上始终显示并排在主工作台上方，必要时仅进行纵向滚动。

当前版本交付：

- 纯净生图提示词
- 纯净负面提示词
- 需求解析、任务类型、审查和建模要点
- 可下载的完整 Markdown 结果
- 可选的 PixPark v3 结果图

## Docker 启动

1. 创建环境配置：

   ```bash
   cp .env.example .env
   ```

2. 把正式的固定图2放到：

   ```text
   config/style-reference.png
   ```

3. 启动：

   ```bash
   docker compose up -d --build
   ```

4. 打开：

   ```text
   http://localhost:9985
   ```

   局域网其他设备使用部署机器的内网地址，例如：

   ```text
   http://192.168.1.20:9985
   ```

5. 点击页面右上角“服务配置”，填写模型 API 地址、模型名称、模型 API Key 和 PixPark Token。模型 API Key 对不需要鉴权的本地兼容服务可以留空；所选模型必须支持图片输入。

也可以继续在 `.env` 中预先填写 `MODEL_BASE_URL`、`MODEL_API_KEY`、`MODEL_NAME`、`PIX_PARK_TOKEN` 和 `IMAGE_GENERATION_ENABLED`。页面保存的值优先于 `.env`，并立即生效。

检查服务：

```bash
curl http://localhost:9985/health
curl http://localhost:9985/ready
curl http://localhost:9985/api/status
```

`/health` 是进程存活状态；`/ready` 只有在模型服务和固定图2都配置完成后才返回 200。`/api/config` 只返回非敏感字段与“已配置/未配置”状态，不会返回 API Key 或 Token。Docker 健康检查使用 `/ready`，因此未配置完成时容器会显示 `unhealthy`，但配置页面仍可访问。

停止服务：

```bash
docker compose down
```

## 模型接口

网站使用 OpenAI 兼容的 `POST /chat/completions` 多模态接口。`MODEL_BASE_URL` 可以填写：

```text
https://api.example.com/v1
```

也可以填写完整地址：

```text
https://api.example.com/v1/chat/completions
```

后台采用三段式提示词流程：

1. 用图1判断任务类型、专项规则和是否需要一次补充确认。
2. 自动读取当前 Skill 及适用 reference，把图1与固定图2一并提交，生成正式结果。
3. 先执行确定性机械校验，再用一次独立视觉模型调用重新查看双图和完整草稿，检查创意事件、动作可达、布局权限、聚拢、红线删除和局部参考范围；不接受草稿自报的 `PASS`。

任一检查失败时，结构化错误会送回模型修正，最多自动修正 `REPAIR_ATTEMPTS` 次，修正后必须重新执行两类审查。`SEMANTIC_AUDIT_ENABLED=false` 可紧急回退到旧的机械校验链，但默认开启。

“丰富趣味”默认关闭。关闭时仍执行上述完整流程和任务类型本身允许的正常创意；开启时只在文字识别、需求终态、主体锁和布局权限完成后，追加一个主创意、2–3 个关联功能模块和受控因果细节，不能覆盖图1硬要求，也不能靠散落小道具制造虚假丰富。

## PixPark v3 结果图

在页面“服务配置”中填写 PixPark Token 并打开“允许确认提示词后生成结果图”。提示词通过审查后不会自动进入 PixPark；用户需要在正向提示词页签中检查内容，再点击“确认提示词，一次生成 4 张”。也可使用 `.env`：

```text
IMAGE_GENERATION_ENABLED=true
PIX_PARK_TOKEN=replace-with-your-token
```

后台会分别上传图1需求图和固定图2风格参考图，并按固定顺序把两个独立公网 URL 传入 `imageUrls`：图1在前、图2在后。不得把两张参考图缩小、拼接成双栏画板，也不得增加数字角标；这样可以保留图1批注精度，并避免 PixPark 把图2内容误认为图1画面的组成部分。只发送审查通过的正向提示词，不发送负面提示词。

返工分为三种明确动作：“修改需求”会把当前补充要求重新开放编辑，并允许沿用原图或上传新版图1，提交为新的历史任务而不覆盖旧版；“重新生成创意和提示词”会在当前任务内保留原始图1、补充要求和“丰富趣味”选项，重新执行需求识别、提示词生成与审查；“重新生成 4 张结果图”会保留已经确认的提示词，只创建一组新的 PixPark 四图任务。重新生成动作会先确认，并在任务处理中禁用重复提交。

当前 PixPark 接口参数固定为 version 3、1:1、4K、4 张图、关闭 Google Search。一次点击只创建一个 PixPark 任务并请求 4 张结果，不会由浏览器重复提交四次。接口比例不会被写成提示词中的“生成1:1”标志；若用户明确要求其他画幅，网站保留提示词结果并禁用生图确认，避免静默改画幅。

PixPark `taskCode` 会在第一次查询前原子写入 `generated/pixpark-state/`。等待超时后，结果区可继续查询同一任务，不会重复提交。浏览器会在当前会话中仅记住非敏感的本地任务编号；即使网站进程重启，也能从状态文件恢复“继续查询原任务”入口。恢复模式不持久化用户原图、提示词或预签名地址。只有 `imageAuditStatus === true` 且结果地址非空时才会保存并展示图片。最多按返回顺序保存 4 张；若服务只返回部分审核通过的结果，会保留可用图片并明确显示实际数量。

图片保存后，默认再用独立视觉调用对照图1和已审查正向提示词，逐张给出需求符合度结论。审查只使用不超过 1536 像素的 JPEG 临时副本，原始 4K 图片保持不变，避免多图视觉请求超过网关大小限制。页面将“PixPark 平台审核”和“需求符合度复查”分开显示；后者失败时图片仍保留并标记“需修改”，不会自动重新生图或再次扣费。审查服务暂时不可用时，可点击“重新复查已有图片”，只重试视觉审查而不创建新的 Pix 任务。可用 `POST_IMAGE_AUDIT_ENABLED=false` 关闭该复查。

## 数据与进程约束

- 页面保存的模型连接和 PixPark 配置写入私有运行目录 `.runtime/runtime-settings.json`，文件权限为 `0600`；Docker 使用不对外提供静态访问的独立 `runtime-data` 命名卷。
- 页面读取配置时只返回非敏感字段和布尔状态；已有 API Key 与 Token 不会被回显到输入框、状态接口或任务结果。
- 修改服务配置时若仍有排队、处理、待补充或生图任务，后台会拒绝切换，避免任务绑定到不同配置。
- 上传图片和任务元数据按任务原子写入私有运行目录的 `jobs/<任务编号>/`；浏览器刷新或服务重启后可在 TTL 内恢复。
- 模型阶段在服务重启后使用相同任务编号重新进入解析队列；PixPark 阶段只在远端任务编号已经落盘时继续查询，绝不因重启自动重复提交。
- 完整提示词、需求图与同页历史记录默认保留 30 天，取消或到期时一并清理；这不是永久项目档案。
- 后续生成图片写入 Docker 命名卷 `generated-data`，避免 Linux 宿主目录权限覆盖容器内的 UID 10001。
- 因为首版使用内存任务队列，Docker 固定运行一个 Uvicorn worker。
- `MAX_CONCURRENT_JOBS` 控制同时调用模型的任务数，默认值为 2；前端允许继续提交，超过并发数的任务留在队列中。
- `MAX_CONCURRENT_IMAGE_JOBS` 独立控制 PixPark 图片任务数；图片轮询不会占用模型解析并发。
- `MAX_PENDING_JOBS` 限制排队、处理中和待补充任务总数，防止内存无限增长。
- `MAX_JOBS_PER_MINUTE` 按来源 IP 限制一分钟内的提交次数，适合可信局域网使用。
- `MAX_IMAGE_PIXELS` 与 `MAX_IMAGE_DIMENSION` 拒绝异常大分辨率图片。
- `MAX_CLARIFICATION_ROUNDS` 限制同一任务反复追问的次数。
- API Key 与 PixPark Token 只存在服务器端；浏览器提交新值后不会再读取到原文。
- PixPark Token、MCP Session ID 和预签名上传地址不会写入任务状态文件。
- 当前版本面向可信局域网，不包含账号系统；不要直接暴露到公网。

## 本地开发

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn webapp.app:app --reload
```

## 结果图状态

任务结果的 `result.image` 会返回当前状态：

```json
{
  "status": "completed",
  "url": "/generated/<任务编号>-1.png",
  "urls": [
    "/generated/<任务编号>-1.png",
    "/generated/<任务编号>-2.png",
    "/generated/<任务编号>-3.png",
    "/generated/<任务编号>-4.png"
  ],
  "count": 4,
  "expected_count": 4,
  "alt": "本任务后续生成的 3D 建模参考结果组图",
  "message": "4 张结果图已生成并通过 PixPark 审核。",
  "resumable": false,
  "platform_audit": {"status": "passed", "pass": true},
  "requirement_audit": {
    "status": "passed",
    "pass": true,
    "per_image": [{"index": 1, "pass": true, "errors": []}],
    "best_indices": [1]
  }
}
```

常见状态包括 `ready`、`uploading`、`creating`、`polling`、`downloading`、`completed`、`partial`、`needs_revision`、`timeout`、`rejected`、`failed`、`disabled`、`unavailable` 和 `incompatible_aspect_ratio`。`ready` 表示提示词已审查完成、等待用户确认生图；`needs_revision` 表示图片已通过平台审核并被保留，但需求符合度复查没有通过；生成成功时 `urls` 返回同源结果图列表，`url` 保留为首张图的兼容字段。
