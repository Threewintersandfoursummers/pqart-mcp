#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PQArt (华航唯实) 离线编程软件 GUI 自动化控制库
基于 Windows UI Automation (uiautomation / pywinauto)。

设计目标：让 MCP 服务器（或脚本）能够
  1. 启动 / 连接正在运行的 PQArt
  2. 导出 UI 自动化树（用于定位模型库、工作站、下载/插入按钮）
  3. 按控件名 / 自动化ID / 路径点击
  4. 触发“下载/插入”工作站模型、摆放并保存自定义车间场景

注意：模型库是软件内嵌的 CEF 网页（chlrob.com），需要用户已登录。
若 CEF 未暴露 Web 控件，则退化为“坐标点击 + 键盘导航”方案（见 click_at）。
"""

import os
import sys
import time
import json
import subprocess

EXE = r"C:\Program Files\CHLRob\PQArt\Cpt\bin\RobotArt\bin\RobotArtCpt.exe"
HERE = os.path.dirname(os.path.abspath(__file__))
UI_TREE_PATH = os.path.join(HERE, "ui_tree.txt")
LOG_PATH = os.path.join(HERE, "pqart_control.log")


def log(*args):
    line = " ".join(str(a) for a in args)
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass
    print(line, flush=True)


# ---------------------------------------------------------------------------
# 窗口发现
# ---------------------------------------------------------------------------
def _import_uia():
    import uiautomation as auto
    return auto


def find_window(timeout=60, regex=None):
    """返回 PQArt 主窗口控制对象，找不到返回 None。

    注意：PQArt 以 WinUI4Browser(Chromium) 壳运行，窗口 pid 每次刷新都变，
    因此按 类名/标题 匹配比按 pid 可靠。模型库是 WebView2 网页，其内部 DOM
    不会被 UI Automation 暴露，故 in-app 的“下载/插入”按钮无法用名称点击，
    只能退化为坐标点击（click_at）或交给用户在界面内操作。
    """
    auto = _import_uia()
    # 顶层窗口候选：优先按类名/标题精确匹配 PQArt 主窗
    title_hints = ["PQArt", "RobotArt", "华航", "竞赛版", "WinUI 4 浏览器"]
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            for w in auto.GetRootControl().GetChildren():
                try:
                    nm = w.Name or ""
                except Exception:
                    nm = ""
                try:
                    cl = w.ClassName or ""
                except Exception:
                    cl = ""
                if cl == "WinUIDesktopWin32WindowClass":
                    return w
                if any(h in nm for h in title_hints):
                    return w
        except Exception as e:
            log("find_window scan error: %s" % e)
        time.sleep(1)
    return None


def get_pqart_rect():
    """返回 PQArt 主窗口的屏幕矩形 (left, top, width, height)，用于坐标点击换算。"""
    auto = _import_uia()
    w = find_window(timeout=10)
    if w is None:
        return None
    try:
        r = w.BoundingRectangle
        return (r.left, r.top, r.width, r.height)
    except Exception:
        return None


def is_running():
    return find_window(timeout=8) is not None


def launch_pqart():
    """若未运行则启动；返回主窗口控制对象。"""
    w = find_window(timeout=8)
    if w is not None:
        log("PQArt 已在运行。")
        return w
    log("启动 PQArt: %s" % EXE)
    subprocess.Popen([EXE])
    w = find_window(timeout=90)
    if w is None:
        raise RuntimeError("启动 PQArt 后未找到主窗口（可能卡在登录/更新）。")
    log("PQArt 主窗口已就绪。")
    return w


# ---------------------------------------------------------------------------
# UI 树导出
# ---------------------------------------------------------------------------
def dump_ui_tree(max_depth=12, root=None, out_path=UI_TREE_PATH):
    """导出从主窗口开始的 UI 自动化树到文本文件，返回路径。"""
    auto = _import_uia()
    root = root or find_window(timeout=20)
    if root is None:
        raise RuntimeError("未找到 PQArt 主窗口，无法导出 UI 树。")
    lines = []

    def walk(ctrl, depth):
        if depth > max_depth:
            return
        try:
            name = ctrl.Name
        except Exception:
            name = ""
        try:
            cls = ctrl.ClassName
        except Exception:
            cls = ""
        try:
            aid = ctrl.AutomationId
        except Exception:
            aid = ""
        try:
            ctype = ctrl.ControlTypeName
        except Exception:
            ctype = ""
        try:
            rect = ctrl.BoundingRectangle
            r = "%d,%d %dx%d" % (rect.left, rect.top, rect.width, rect.height) if rect else ""
        except Exception:
            r = ""
        indent = "  " * depth
        label = "%s[%s] name=%r class=%r aid=%r rect=%s" % (
            indent, ctype, name, cls, aid, r)
        lines.append(label)
        # 通过 children 递归
        try:
            children = ctrl.GetChildren()
            for ch in children:
                walk(ch, depth + 1)
        except Exception as e:
            lines.append("%s  (getchildren error: %s)" % (indent, e))

    lines.append("ROOT: %r" % (root.Name,))
    try:
        children = root.GetChildren()
        for ch in children:
            walk(ch, 0)
    except Exception as e:
        lines.append("root children error: %s" % e)

    text = "\n".join(lines)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(text)
    log("UI 树已导出: %s (%d 行)" % (out_path, len(lines)))
    return out_path


# ---------------------------------------------------------------------------
# 控件查找与点击
# ---------------------------------------------------------------------------
def find_control(predicate, root=None, max_depth=14, timeout=20):
    """predicate(ctrl)->bool，深度优先查找第一个匹配的控件。"""
    auto = _import_uia()
    root = root or find_window(timeout=timeout)
    if root is None:
        return None

    found = []

    def walk(ctrl, depth):
        if depth > max_depth or found:
            return
        try:
            if predicate(ctrl):
                found.append(ctrl)
                return
        except Exception:
            pass
        try:
            for ch in ctrl.GetChildren():
                walk(ch, depth + 1)
                if found:
                    return
        except Exception:
            pass

    walk(root, 0)
    return found[0] if found else None


def click_control_by_name(name, substring=True, root=None, max_depth=14):
    """按名称（包含匹配）点击控件。"""
    def pred(ctrl):
        try:
            n = ctrl.Name
        except Exception:
            return False
        if n is None:
            return False
        return (name in n) if substring else (n == name)

    ctrl = find_control(pred, root=root, max_depth=max_depth)
    if ctrl is None:
        log("未找到名称包含 %r 的控件。" % name)
        return False
    try:
        ctrl.SetActive()
        ctrl.Click()
        log("已点击控件 name=%r class=%r" % (ctrl.Name, ctrl.ClassName))
        return True
    except Exception as e:
        log("点击失败: %s" % e)
        return False


def click_model_library():
    """尝试进入模型库面板（按钮文字通常含‘模型库’）。"""
    return click_control_by_name("模型库")


def download_station(keyword):
    """
    在模型库面板中找到包含 keyword 的工作站项，并点击其‘下载’或‘插入’按钮。
    先尝试点击项本身，再在同级/子级里找下载/插入按钮。
    """
    auto = _import_uia()
    root = find_window(timeout=20)
    if root is None:
        return "未找到 PQArt 窗口"

    target = find_control(
        lambda c: (c.Name or "").find(keyword) >= 0, root=root, max_depth=16)
    if target is None:
        return "未找到包含 %r 的工作站项" % keyword

    # 在目标附近查找 下载/插入 按钮
    btn = find_control(
        lambda c: (c.Name or "") in ("下载", "插入", "下载约", "下载此模型"),
        root=target, max_depth=4)
    if btn is not None:
        btn.Click()
        return "已对 %r 点击 %r" % (keyword, btn.Name)
    # 退而求其次：点击项本身
    target.Click()
    return "已点击工作站项 %r（未找到独立下载按钮，请确认是否弹出插入）" % keyword


def save_scene(path=None):
    """通过菜单/快捷键保存场景。优先 Ctrl+S，再尝试‘保存’菜单。"""
    auto = _import_uia()
    w = find_window(timeout=20)
    if w is None:
        return "未找到窗口"
    w.SetActive()
    if path:
        # 尝试另存为流程：Alt+F -> 另存为
        try:
            w.SendKeys("{Alt}f")
            time.sleep(0.5)
            click_control_by_name("另存为")
            time.sleep(1)
            # 在文件名框输入路径
            edit = find_control(lambda c: c.ControlTypeName == "Edit", max_depth=6)
            if edit is not None:
                edit.SendKeys(path)
                time.sleep(0.3)
                click_control_by_name("保存")
                return "已另存为 %s" % path
        except Exception as e:
            log("另存为流程异常: %s" % e)
    # 退化为 Ctrl+S
    w.SendKeys("^s")
    time.sleep(1)
    # 若有保存对话框，填路径并保存
    dlg = find_window(timeout=5, regex=r".*保存.*")
    if dlg is not None:
        edit = find_control(lambda c: c.ControlTypeName == "Edit", root=dlg, max_depth=6)
        if edit is not None and path:
            edit.SendKeys(path)
            time.sleep(0.3)
            click_control_by_name("保存", root=dlg)
        return "已触发保存（Ctrl+S）"
    return "已触发 Ctrl+S"


def click_at(x, y):
    """坐标点击（CEF 网页不可自动化时的退化方案）。"""
    auto = _import_uia()
    # 使用鼠标事件
    import ctypes
    ctypes.windll.user32.SetCursorPos(int(x), int(y))
    ctypes.windll.user32.mouse_event(0x0002, 0, 0, 0, 0)  # LEFT DOWN
    ctypes.windll.user32.mouse_event(0x0004, 0, 0, 0, 0)  # LEFT UP
    log("坐标点击 (%d,%d)" % (x, y))


def screenshot(path=None):
    """截取主窗口到 PNG（供用户查看；本会话模型不支持读图，仅产出文件）。"""
    auto = _import_uia()
    w = find_window(timeout=20)
    if w is None:
        return None
    path = path or os.path.join(HERE, "pqart_shot.png")
    try:
        w.CaptureToImage(path)
        log("截图已保存: %s" % path)
        return path
    except Exception as e:
        log("截图失败: %s" % e)
        return None


# ---------------------------------------------------------------------------
# CLI 入口（便于直接运行与调试）
# ---------------------------------------------------------------------------
def main(argv):
    cmd = argv[1] if len(argv) > 1 else "inspect"
    if cmd == "launch":
        launch_pqart()
    elif cmd == "inspect":
        p = dump_ui_tree()
        print(p)
    elif cmd == "running":
        print("running" if is_running() else "not running")
    elif cmd == "model-lib":
        ok = click_model_library()
        print("model-lib clicked:", ok)
    elif cmd == "shot":
        print(screenshot())
    elif cmd == "save":
        print(save_scene(argv[2] if len(argv) > 2 else None))
    else:
        print("usage: pqart_control.py [launch|inspect|running|model-lib|shot|save [path]]")


if __name__ == "__main__":
    main(sys.argv)
