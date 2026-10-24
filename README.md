# pqart-mcp

MCP（Model Context Protocol）服务器：让 AI 助手通过 Windows UI 自动化驱动 **PQArt**（机器人虚拟仿真软件，竞赛版），实现启动、巡检界面、点击控件、从模型库下载工作站、保存场景、截图等操作。

## 架构

```
MCP 客户端 ──stdio(MCP)──▶ pqart_mcp_server.py
                              │  import
                              ▼
                        pqart_control.py
                              │  Windows UI Automation (pywinauto)
                              ▼
                       PQArt 竞赛版窗口
```

- `pqart_mcp_server.py`：MCP stdio 服务器（依赖 `mcp` 包，兼容 1.x / 2.x）
- `pqart_control.py`：PQArt 窗口自动化核心
- `pq1959_client.py`：pq1959.com 模型库（RobotArt）协议客户端——逆向 SOAP 接口所得

## 需求

- Windows + 已安装 PQArt（竞赛版）
- Python 3.10+，`pip install mcp pywinauto`
- PQArt 需已启动并登录模型库

## 暴露的 MCP 工具（10 个）

| 工具 | 说明 |
|---|---|
| `pqart_launch` | 启动或连接 PQArt |
| `pqart_running` | 是否运行中 |
| `pqart_inspect` | 导出 UI 自动化树到文件并返回路径 |
| `pqart_click_at` | 按坐标点击 |
| `pqart_click_name` | 按名称点击控件 |
| `pqart_window_rect` | 获取主窗口位置尺寸 |
| `pqart_model_library` | 进入模型库面板 |
| `pqart_download_station` | 从模型库下载/插入工作站模型 |
| `pqart_save_scene` | 保存当前场景 |
| `pqart_screenshot` | 截取主窗口（PNG） |

## 接入 MCP 客户端

在 `mcp.json` 里加：

```json
{
  "mcpServers": {
    "pqart": {
      "command": "python",
      "args": ["C:/path/to/pqart-mcp/pqart_mcp_server.py"]
    }
  }
}
```

## 说明

- `pq1959_client.py` 中记录了实测得到的 SOAP 协议细节（端点、命名空间、Base64+XML 包装方式），以及来自本地 CEF 缓存的授权 token；token 失效后需重新登录 PQArt 获取。
- 界面控件名以 `pqart_inspect` 导出的 UI 树为准。
