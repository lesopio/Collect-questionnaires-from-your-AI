# Collect-questionnaires-from or for-your-AI

仅用于已授权问卷的自动化测试与调研，不用于未授权目标。

## 合规声明

- 仅对明确授权的问卷链接使用本工具。
- 不提供验证码绕过、风控绕过能力。
- 需自行遵守平台条款与法律法规。

## 功能概览

- 读取 `网址.txt`、`人格配置.json`、`.env`。
- 使用 Playwright 模拟浏览器自动填写问卷。
- 使用 OpenAI 兼容接口生成答案。
- 从代理 API 拉取代理并轮换使用。
- 检测验证码时暂停，支持人工接管继续。
- 命令：`doctor` / `scan` / `run` / `schedule`。

## 项目结构

```text
。
├─ src/
├─ tests/
├─ mappings/
├─ data/
│  ├─ logs/
│  ├─ screenshots/
│  └─ state/
├─ 网址.txt
├─ 人格配置.json
└─ requirements.txt
```

## 环境准备

```bash
python -m venv .venv
# Windows PowerShell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m playwright install chromium
```

建议 Python `3.10+`。

## 配置说明

### `.env`

必填项：

- `LLM_BASE_URL`
- `LLM_API_KEY`
- `LLM_MODEL`
- `PROXY_API_URL`
- `PROXY_API_AUTH_HEADER`（格式：`Header-Name: value`）
- `PROXY_API_RESULT_PATH`
- `PROXY_API_ITEM_SCHEMA`（JSON 字符串，需含 `host/port/protocol/username/password`）

可选项（默认值）：

- `LLM_TIMEOUT_SEC=30`
- `BROWSER_HEADLESS=false`
- `ACTION_DELAY_MIN_MS=800`
- `ACTION_DELAY_MAX_MS=3500`
- `SUBMIT_RETRY_PER_TASK=2`
- `PROXY_HEALTHCHECK_URL=https://httpbin.org/ip`
- `PROXY_DEFAULT_USERNAME=`
- `PROXY_DEFAULT_PASSWORD=`

`PROXY_DEFAULT_USERNAME/PROXY_DEFAULT_PASSWORD` 用于代理 API 只返回 `ip:port`，但实际代理需要账号密码认证的场景。

### `网址.txt`

- 每行一个 URL。
- 空行和 `#` 注释行会被忽略。

示例：

```text
# 授权问卷地址
https://v.wjx.cn/vm/xxxx.aspx
```

### `人格配置.json`

核心字段：

- `personas[]`
- `tasks[]`
- `tasks[].submit_count`（必填，正整数）

最小示例：

```json
{
  "personas": [
    {
      "id": "young_professional",
      "description": "25-30岁职场人群",
      "weight": 1.0,
      "style": "理性务实"
    }
  ],
  "tasks": [
    {
      "url": "https://v.wjx.cn/vm/xxxx.aspx",
      "submit_count": 10,
      "mapping_file": "mappings/v_wjx_cn__vm_xxxx.aspx.json",
      "persona_mix": {
        "young_professional": 1.0
      },
      "delay_profile": "slow_random"
    }
  ]
}
```

### mapping 文件

`mapping_file` 通常与 URL slug 对应。示例：

- URL：`https://v.wjx.cn/vm/Ow7tRPN.aspx`
- 映射：`mappings/v_wjx_cn__vm_Ow7tRPN.aspx.json`

结构示例：

```json
{
  "meta": {
    "url": "https://...",
    "platform": "wjx_like",
    "generated_at": "2026-02-18T00:00:00+00:00",
    "version": 1
  },
  "questions": [
    {
      "qid": "div1",
      "text": "题目文本",
      "type": "single_choice",
      "options": [],
      "constraints": {
        "required": true,
        "max_select": 1
      },
      "locator": {
        "anchor_text": "题目锚点",
        "fallback_selector": ""
      }
    }
  ]
}
```

## 使用流程

1. 预检：

```bash
python -m src.main doctor
```

2. 生成 mapping 模板（后续人工校对）：

```bash
python -m src.main scan
```

3. 执行填写：

```bash
python -m src.main run
```

4. 定时运行（可选）：

```bash
python -m src.main schedule --cron "*/30 * * * *"
```

## CLI 接口

- `python -m src.main doctor --env-file --url-file --persona-file`
- `python -m src.main scan --env-file --url-file`
- `python -m src.main run --env-file --url-file --persona-file`
- `python -m src.main schedule --cron --env-file --url-file --persona-file`

默认值：

- `--env-file .env`
- `--url-file 网址.txt`
- `--persona-file 人格配置.json`

## 输出结果

- `data/logs/runs-YYYYMMDD.jsonl`：`run_id`、`status`、`detail` 等记录。
- `data/screenshots/<run_id>/`：关键过程截图。
- `data/state/schedule_state.json`：调度运行状态。

## 常见问题

- `No healthy proxy found from API`  
  检查代理连通性、健康检查地址、代理是否失效。

- `407 Proxy Authentication Required`  
  配置 `PROXY_DEFAULT_USERNAME` / `PROXY_DEFAULT_PASSWORD`，或让代理 API 返回账号密码字段。

- `Missing mapping file`  
  先执行 `scan` 生成模板，再修订 mapping 并与 `tasks[].mapping_file` 对齐。

- `Tasks contain URLs not present in 网址.txt`  
  保证 `人格配置.json` 里的 `tasks[].url` 与 `网址.txt` 一致。


