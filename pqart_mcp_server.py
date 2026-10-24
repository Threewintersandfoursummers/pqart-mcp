#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PQArt 控制 MCP 服务器（stdio）
暴露给 WorkBuddy 的工具，用于驱动已打开、已登录模型库的 PQArt 窗口：
  - pqart_launch           启动或连接 PQArt
  - pqart_running          是否运行中
  - pqart_inspect          导出 UI 自动化树到文件并返回路径
  - pqart_click_name       按名称点击控件
  - pqart_model_library    进入模型库面板
  - pqart_download_station 下载/插入某个工作站模型
  - pqart_save_scene       保存当前场景
  - pqart_screenshot       截主窗口（产出 PNG 文件）

运行：<venv>/Scripts/python pqart_mcp_server.py
"""

import os
import sys

# 把同目录加入搜索路径，便于 import pqart_control
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

try:  # mcp 2.x：FastMCP 更名为 MCPServer
    from mcp.server.mcpserver import MCPServer as _Server
except ImportError:  # mcp 1.x 兼容
    from mcp.server.fastmcp import FastMCP as _Server
import pqart_control as pc

mcp = _Server("PQArt Controller")


@mcp.tool()
def pqart_launch() -> str:
    """启动或连接正在运行的 PQArt（竞赛版）。返回状态信息。"""
    try:
        w = pc.launch_pqart()
        return "OK: PQArt 已就绪, 窗口标题=%r" % (w.Name if w else None)
    except Exception as e:
        return "ERROR: %s" % e


@mcp.tool()
def pqart_running() -> str:
    """检查 PQArt 是否正在运行。"""
    return "running" if pc.is_running() else "not running"


@mcp.tool()
def pqart_inspect(depth: int = 12) -> str:
    """导出 PQArt 主窗口的 UI 自动化树到 ui_tree.txt，返回该文件路径。
    用于定位模型库、工作站列表、下载/插入按钮的控件名。depth 默认 12。"""
    try:
        p = pc.dump_ui_tree(max_depth=depth)
        return "UI 树已导出: %s" % p
    except Exception as e:
        return "ERROR: %s" % e


@mcp.tool()
def pqart_click_name(name: str, substring: bool = True) -> str:
    """按（包含匹配）控件名称点击。name=控件文字。返回结果。"""
    ok = pc.click_control_by_name(name, substring=substring)
    return "clicked=%s name=%r" % (ok, name)


@mcp.tool()
def pqart_model_library() -> str:
    """点击进入模型库面板（按钮文字通常含‘模型库’）。"""
    ok = pc.click_model_library()
    return "model-library clicked=%s" % ok


@mcp.tool()
def pqart_download_station(keyword: str) -> str:
    """在模型库中找到包含 keyword 的工作站项并点击下载/插入。
    keyword 例：'CHL-DS-01' 或 'PCB异形插件'。"""
    return pc.download_station(keyword)


@mcp.tool()
def pqart_save_scene(path: str = "") -> str:
    """保存当前场景。path 可选（另存为路径）。优先 Ctrl+S。"""
    return pc.save_scene(path or None)


@mcp.tool()
def pqart_window_rect() -> str:
    """返回 PQArt 主窗口的屏幕矩形 (left, top, width, height)，用于换算坐标点击。"""
    r = pc.get_pqart_rect()
    return str(r) if r else "no PQArt window"


@mcp.tool()
def pqart_click_at(x: int, y: int) -> str:
    """在屏幕坐标 (x,y) 处点击。用于 UI Automation 看不到的 WebView2 网页按钮
    （模型库的“下载/插入”）。需要你先提供按钮的屏幕坐标。"""
    pc.click_at(x, y)
    return "clicked at (%d,%d)" % (x, y)


@mcp.tool()
def pqart_screenshot() -> str:
    """截取 PQArt 主窗口到 PNG 文件并返回路径（本会话无法读图，仅供你查看）。"""
    p = pc.screenshot()
    return p or "screenshot failed"


if __name__ == "__main__":
    mcp.run()
