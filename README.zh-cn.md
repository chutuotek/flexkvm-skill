# FlexKVM Universal Controller（中文）

基于 FlexKVM agent 控制接口的 OpenClaw 技能：通过 HTTPS API 对 KVM 所连接的
目标机进行屏幕截图与键鼠自动化操作。适用于远程服务器管理、自动化测试与无人值守运维。

## 功能特性

- 📸 **屏幕截图**: 获取被控机实时屏幕图像（JPEG 原始字节 + `X-Resolution` 分辨率头）
- 🖱️ **鼠标控制**: 归一化绝对坐标 `[0.0, 1.0]`，单击 / 双击 / 滚动
- ⌨️ **键盘控制**: 原子快捷键（修饰键 + 键名）与单键（Enter/Esc 等）
- 📝 **文本输入**: **同步完成语义** —— 设备输完才返回，单事件支持最长 1024 字符
- ⏱️ **延时控制**: 应用启动 / 页面加载等待的节奏控制

## 快速开始

### 1. 设备准备工作

1. 在 FlexKVM 网页界面**设置 → Agent** 中开启 Agent 服务
2. 生成 **API Key**（`sk-` 前缀 + 32 hex 字符）
3. 记下设备 IP（HTTPS 走默认 443 端口）

### 2. 环境配置

以下环境变量均为必填：

#### Bash

```bash
export FlexKVM_IP="192.168.x.x"
export FlexKVM_TOKEN="sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
```

#### PowerShell

```powershell
[System.Environment]::SetEnvironmentVariable("FlexKVM_IP", "192.168.x.x", "User")
[System.Environment]::SetEnvironmentVariable("FlexKVM_TOKEN", "sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx", "User")
```

> 修改环境变量后需重启 OpenClaw 或重开终端再执行。
> 设备使用默认 HTTPS 端口（443）自签 TLS 证书，客户端需跳过证书校验（curl 加 `-k`，
> Python 设 `verify=False`）。

### 3. 执行规则

读取环境变量后组合出基础地址 `https://${FlexKVM_IP}`，然后调用
FlexKVM agent API：

- 状态查询：`GET /api/v1/agent/state`
- 截图接口：`GET /api/v1/agent/snapshot`
- 控制接口：`POST /api/v1/agent/control`
- 所有请求必须带请求头：`Authorization: Bearer ${FlexKVM_TOKEN}`
- Agent 未启用 → `403`；API Key 缺失/错误 → `401`

### 4. 使用示例

#### Bash 方式
```bash
# 发送控制指令
./scripts/send_control.sh '{"events":[{"type":"text","value":"hello"},{"type":"delay","ms":300}]}'

# 获取截图
curl -ks -X GET "https://${FlexKVM_IP}/api/v1/agent/snapshot" \
     -H "Authorization: Bearer ${FlexKVM_TOKEN}" -o screen.jpeg
```

#### Python 方式（可选）
```python
from scripts.flexkvm_client import FlexKVMClient

client = FlexKVMClient()

# 查询状态（mode/分辨率/锁状态）
print(client.state())

# 截图
client.screenshot("desktop.jpeg")

# 输文本（同步完成，无需手动分段）
client.text("Hello from FlexKVM")

# 点击屏幕中心
client.click(0.5, 0.5)

# Win+R -> notepad -> Enter
client.run_command("notepad")

# 快捷键组合
client.key_combo("ctrl", "c")    # 复制
client.key_combo("alt", "tab")   # 切换窗口
```

#### 使用示例 JSON
```bash
curl -ks -X POST "https://${FlexKVM_IP}/api/v1/agent/control" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${FlexKVM_TOKEN}" \
  -d @examples/open_browser.json
```

## 目录结构

```
flexkvm-skill/
├── SKILL.md                    # 主技能文档（OpenClaw 规范）
├── README.md                   # 英文说明
├── README.zh-cn.md             # 本文件
├── scripts/
│   ├── send_control.sh         # Bash 快速调用脚本（curl）
│   └── flexkvm_client.py       # Python 客户端封装（完整辅助函数）
├── examples/
│   ├── open_browser.json       # 打开浏览器访问网站
│   ├── open_notepad.json       # 打开记事本并输入文字
│   ├── mouse_demo.json         # 鼠标移动/单击/双击/滚动演示
│   ├── keyboard_shortcuts.json # 快捷键演示（Ctrl+C/V、Alt+Tab、Win）
│   └── long_text_input.json    # 长文本同步输入演示
└── references/
    └── key_names.md            # hotkey 键名参考表
```

## 事件类型速查

| 事件 | 示例 | 说明 |
|:---|:---|:---|
| move | `{"type":"move","x":0.5,"y":0.5}` | 绝对移动 |
| click | `{"type":"click","button":"left","x":0.5,"y":0.5}` | 单击 |
| dblclick | `{"type":"dblclick","button":"left","x":0.5,"y":0.5}` | 双击 |
| scroll | `{"type":"scroll","dy":-3}` | 垂直滚动 [-127,127] |
| text | `{"type":"text","value":"hello"}` | 同步可打印 ASCII 文本 |
| hotkey | `{"type":"hotkey","keys":["ctrl","c"]}` | 原子快捷键 |
| delay | `{"type":"delay","ms":1000}` | 延时（0..5000ms） |

**请求限制**：单次最多 32 条事件，总执行时间不超过 60 秒，顺序执行；
中途失败返回 `applied`（已执行条数）+ `error`。

## 关键差异：同步文本

FlexKVM 的 `text` 事件由设备内部同步输入（paste 通道 30ms/字符），**输入完成
后才返回**。与"发出即返回、需外部每 30 字符补 1000ms 延时"的接口不同——
不需要分段延时惯例。延时仍用于目标机侧渲染等待（应用启动、页面加载、UI 过渡）。

## 依赖

- `curl`：HTTP 请求
- `python3` + `requests`：Python 客户端（可选）

## 协议真相源

接口契约以 `api/http/README.md`（FlexKVM 仓库）为准，本技能与其保持同步：
鉴权 `Bearer sk-*`、快照返回裸 JPEG、事件字段（`value`/`dy`/`ms`/`keys`）。