#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
局域网快传 · 跨平台绿色版（v6.7 稳定版）
- 原创作者：by 斯蒂芬周
- 修复：移除2GB限制、优化聊天附件发送逻辑、增加更新检测框架与Bug反馈。
"""
import http.server
import json
import os
import queue
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
import urllib.request
import zlib
import struct
import base64
import re
import zipfile
import io
import random
import mimetypes
import webbrowser

# 平台差异导入
if sys.platform == 'win32':
    import ctypes
    import winreg

# 尝试导入托盘库
try:
    import pystray
    from PIL import Image

    HAS_TRAY = True
except ImportError:
    pystray = None
    Image = None
    HAS_TRAY = False

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
except ImportError:
    tk = None
    filedialog = None
    messagebox = None
    ttk = None

APP_VERSION = "v6.7"
APP_NAME = "LanShare"
APP_DISPLAY_NAME = "局域网快传"
AUTHOR_EMAIL = "793153432@qq.com"

# 【更新检测配置】
# 您可以把这个 JSON 放在 GitHub 的 Raw 链接里，比如：
# {"version": "v6.8", "url": "https://github.com/yourname/releases/download/v6.8/app.exe"}
UPDATE_CHECK_URL = "https://raw.githubusercontent.com/yourname/yourrepo/main/version.json"  # 替换为您自己的链接

# 跨平台字体设置
if sys.platform == 'win32':
    FONT_FAMILY = 'Microsoft YaHei'
    MONO_FONT = 'Consolas'
elif sys.platform == 'darwin':
    FONT_FAMILY = 'PingFang SC'
    MONO_FONT = 'Menlo'
else:
    FONT_FAMILY = 'Arial'
    MONO_FONT = 'Courier'

if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
    EXE_PATH = sys.executable
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    EXE_PATH = os.path.abspath(sys.argv[0])

CONFIG_FILE = os.path.join(BASE_DIR, 'lanshare_config.json')
README_FILE = os.path.join(BASE_DIR, '局域网快传_使用说明及更新日志.txt')
ICO_PATH = os.path.join(BASE_DIR, 'logo.ico')


def register_app_id():
    if sys.platform == 'win32':
        try:
            app_id = "LanShare.App"
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
            key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\AppUserModelId\" + app_id")
            winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, APP_DISPLAY_NAME)
            winreg.CloseKey(key)
        except Exception:
            pass


def add_to_startup():
    if sys.platform == 'win32':
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0,
                                 winreg.KEY_SET_VALUE)
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, f'"{EXE_PATH}" --auto-start')
            winreg.CloseKey(key)
        except Exception:
            pass
    elif sys.platform == 'darwin':
        messagebox.showinfo(APP_DISPLAY_NAME, "macOS 用户请手动前往：\n系统设置 -> 通用 -> 登录项，添加本软件。")


def remove_from_startup():
    if sys.platform == 'win32':
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0,
                                 winreg.KEY_SET_VALUE)
            winreg.DeleteValue(key, APP_NAME)
            winreg.CloseKey(key)
        except Exception:
            pass
    elif sys.platform == 'darwin':
        messagebox.showinfo(APP_DISPLAY_NAME, "macOS 用户请手动前往：\n系统设置 -> 通用 -> 登录项，移除本软件。")


def check_startup():
    if sys.platform == 'win32':
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0,
                                 winreg.KEY_READ)
            winreg.QueryValueEx(key, APP_NAME)
            winreg.CloseKey(key)
            return True
        except Exception:
            return False
    return False


def clean_old_temp_dirs():
    temp_dir = tempfile.gettempdir()
    try:
        for name in os.listdir(temp_dir):
            if name.startswith('lanshare_'):
                path = os.path.join(temp_dir, name)
                if os.path.isdir(path): shutil.rmtree(path, ignore_errors=True)
    except Exception:
        pass


def generate_readme():
    content = f"""====================================================================
局域网快传 - 完整使用说明、功能详解及更新日志
原创作者：by 斯蒂芬周
版本：{APP_VERSION}
反馈邮箱：{AUTHOR_EMAIL}
====================================================================

【模块一：核心功能详解】
1. 为什么需要 PIN 码？
   - 为了保证隐私，防止同一 WiFi 下的其他陌生人偷看或乱传文件。
   - 电脑端每次启动都会随机生成 4 位 PIN 码，手机扫码后必须输入正确才能进入系统。关掉软件重开，PIN码就会变。

2. 如何在多台手机和电脑间互传文件？
   - 电脑作为“中转站”。手机A扫码上传照片到电脑。
   - 手机B扫码进入，刷新列表就能看到手机A刚传的照片，点击即可下载。不用装APP。

3. 什么是【在线预览】？
   - 手机端点击 TXT、代码、图片、PDF、MP4/MP3 时，直接在网页里打开看，不直接下载。省流量。

4. 剪贴板互通怎么用？
   - 点击右下角【剪贴板图标】，手机端输入验证码发送到电脑，或读取电脑复制的文字。

5. 分片断点续传与自动重试
   - 传大文件时切成 2MB 的小片。如果某一片失败，手机会自动重试 3 次，保证传输。

6. 聊天框发文件发到哪里了？
   - 发送的附件会保存在电脑端设置的“共享目录”中。
   - 发送时聊天框会立刻显示“正在上传”，成功后显示为可点击下载的链接。

====================================================================
【模块二：保姆级排错指南】
如果手机扫码后无法访问：
① 检查网络：确保手机和电脑连接同一路由器 WiFi。
② 权限拦截：右键软件【以管理员身份运行】放行防火墙。
③ 代理冲突：关闭 Clash、V2Ray 等代理软件的局域网拦截。
④ IP 选错：电脑有虚拟机，请在主界面下拉框切换成真实的 WiFi IP。
⑤ 浏览器拦截：微信/QQ扫码白屏，点右上角“在浏览器中打开”。
⑥ 局域网隔离：公司网络禁止互访，用手机开热点给电脑连。

====================================================================
【模块三：历史版本迭代记录】
（详见早期版本，此处略去万字长文，保障客户端体积）

[{APP_VERSION}] 当前版本
1. 取消批量打包 2GB 限制，直接传，完事。
2. 整合聊天框发送按钮，统一选文件，增加“正在上传”气泡提示。
3. 增加【检测更新】与【Bug反馈】机制，优化界面。
====================================================================
"""
    path = os.path.join(BASE_DIR, '局域网快传_使用说明及更新日志.txt')
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8-sig') as f:
                if f"[{APP_VERSION}]" in f.read(): return
        except Exception:
            pass
    try:
        with open(path, 'w', encoding='utf-8-sig') as f:
            f.write(content)
    except Exception:
        pass


def generate_ico_file():
    if os.path.exists(ICO_PATH): return
    try:
        png_b64 = get_app_icon_data()
        png_bytes = base64.b64decode(png_b64)
        header = struct.pack("<HHH", 0, 1, 1)
        entry = struct.pack("<BBBBHHII", 64, 64, 0, 0, 1, 32, len(png_bytes), 22)
        ico_data = header + entry + png_bytes
        with open(ICO_PATH, 'wb') as f:
            f.write(ico_data)
    except Exception:
        pass


def get_app_icon_data():
    w, h = 64, 64
    raw_data = bytearray()

    def get_color(x, y):
        r_corner = 14
        dx, dy = 0, 0
        if x < r_corner and y < r_corner:
            dx, dy = r_corner - x, r_corner - y
        elif x >= w - r_corner and y < r_corner:
            dx, dy = x - (w - r_corner - 1), r_corner - y
        elif x < r_corner and y >= h - r_corner:
            dx, dy = r_corner - x, y - (h - r_corner - 1)
        elif x >= w - r_corner and y >= h - r_corner:
            dx, dy = x - (w - r_corner - 1), y - (h - r_corner - 1)
        if dx != 0 or dy != 0:
            dist = (dx * dx + dy * dy) ** 0.5
            if dist > r_corner: return (0, 0, 0, 0)
            alpha_bg = 255 if dist < r_corner - 1 else int(255 * (r_corner - dist))
        else:
            alpha_bg = 255
        r, g, b = 15, 17, 21

        def calc_dist_seg(px, py, x1, y1, x2, y2):
            _dx, _dy = x2 - x1, y2 - y1
            if _dx == 0 and _dy == 0: return ((px - x1) ** 2 + (py - y1) ** 2) ** 0.5
            t = ((px - x1) * _dx + (py - y1) * _dy) / (_dx * _dx + _dy * _dy)
            t = max(0, min(1, t))
            cx, cy = x1 + t * _dx, y1 + t * _dy
            return ((px - cx) ** 2 + (py - cy) ** 2) ** 0.5

        d_blue = min(calc_dist_seg(x, y, 16, 22, 46, 22), calc_dist_seg(x, y, 34, 10, 48, 22),
                     calc_dist_seg(x, y, 34, 34, 48, 22))
        d_green = min(calc_dist_seg(x, y, 48, 42, 18, 42), calc_dist_seg(x, y, 30, 30, 16, 42),
                      calc_dist_seg(x, y, 30, 54, 16, 42))
        thickness = 3.5
        edge_width = 1.0
        if d_blue <= thickness:
            r, g, b = 79, 140, 255
        elif d_blue <= thickness + edge_width:
            ratio = (thickness + edge_width - d_blue) / edge_width
            r = int(15 + (79 - 15) * ratio);
            g = int(17 + (140 - 17) * ratio);
            b = int(21 + (255 - 21) * ratio)
        if d_green <= thickness:
            r, g, b = 62, 207, 142
        elif d_green <= thickness + edge_width:
            ratio = (thickness + edge_width - d_green) / edge_width
            r = int(15 + (62 - 15) * ratio);
            g = int(17 + (207 - 17) * ratio);
            b = int(21 + (142 - 21) * ratio)
        return (r, g, b, alpha_bg)

    for y in range(h):
        raw_data.append(0)
        for x in range(w):
            r, g, b, a = get_color(x, y)
            raw_data.extend([r, g, b, a])
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)
    idat = zlib.compress(raw_data)
    png = b'\x89PNG\r\n\x1a\n' + struct.pack(">I", 13) + b'IHDR' + ihdr + struct.pack(">I", zlib.crc32(
        b'IHDR' + ihdr)) + struct.pack(">I", len(idat)) + b'IDAT' + idat + struct.pack(">I", zlib.crc32(
        b'IDAT' + idat)) + struct.pack(">I", 0) + b'IEND' + struct.pack(">I", zlib.crc32(b'IEND'))
    return base64.b64encode(png).decode('utf-8')


def set_app_icon(root):
    try:
        img = tk.PhotoImage(data=get_app_icon_data())
        root.iconphoto(True, img)
        root._icon_ref = img
    except Exception:
        pass


def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_config(cfg):
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def fmt_size(n):
    n = float(n)
    for u in ('B', 'KB', 'MB', 'GB'):
        if n < 1024: return f"{n:.0f} {u}" if u == 'B' else f"{n:.1f} {u}"
        n /= 1024
    return f"{n:.2f} TB"


def get_all_ips():
    ips = set()
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ips.add(s.getsockname()[0])
        s.close()
    except Exception:
        pass
    try:
        for ip in socket.gethostbyname_ex(socket.gethostname())[2]: ips.add(ip)
    except Exception:
        pass
    valid = [ip for ip in ips if not ip.startswith('127.') and not ip.startswith('169.254.')]
    return valid if valid else ['127.0.0.1']


def add_firewall_rule(port):
    if sys.platform == 'win32':
        cmd = f'netsh advfirewall firewall add rule name="LanShare_TCP_{port}" dir=in action=allow protocol=TCP localport={port}'
        try:
            subprocess.run(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           creationflags=0x08000000)
            return True
        except Exception:
            pass
    return True


def natural_sort_key(s):
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', s)]


class QR:
    EXP = [0] * 512
    LOG = [0] * 256
    _ready = False

    @classmethod
    def _init_tables(cls):
        if cls._ready: return
        x = 1
        for i in range(255):
            cls.EXP[i] = x;
            cls.LOG[x] = i;
            x <<= 1
            if x & 0x100: x ^= 0x11d
        for i in range(255, 512): cls.EXP[i] = cls.EXP[i - 255]
        cls._ready = True

    @classmethod
    def _mul(cls, a, b):
        if a == 0 or b == 0: return 0
        return cls.EXP[cls.LOG[a] + cls.LOG[b]]

    @classmethod
    def _gen_poly(cls, n):
        g = [1]
        for i in range(n):
            ng = [0] * (len(g) + 1)
            for j in range(len(g)):
                ng[j] ^= g[j];
                ng[j + 1] ^= cls._mul(g[j], cls.EXP[i])
            g = ng
        return g

    @classmethod
    def _rs(cls, msg, n):
        gen = cls._gen_poly(n);
        out = list(msg) + [0] * n
        for i in range(len(msg)):
            c = out[i]
            if c:
                for j in range(len(gen)): out[i + j] ^= cls._mul(gen[j], c)
        return out[-n:]

    def __init__(self, data):
        if isinstance(data, str): data = data.encode('utf-8')
        if len(data) > 42: raise ValueError("QR 数据过长")
        QR._init_tables();
        self.data = data;
        self.size = 29;
        self.ec_n = 26;
        self.data_n = 44
        self.m = [[-1] * self.size for _ in range(self.size)]
        self.dmods = set()
        self._build()

    def _build(self):
        self._finders();
        self._timing();
        self._alignment();
        self._reserve_format()
        cw = self._encode();
        ec = QR._rs(cw, self.ec_n);
        self._place_data(cw + ec)
        best, best_s = 0, 10 ** 9
        for mask in range(8):
            self._apply_mask(mask);
            self._write_format(mask);
            s = self._penalty()
            if s < best_s: best, best_s = mask, s
            self._apply_mask(mask)
        self._apply_mask(best);
        self._write_format(best)

    def _finders(self):
        for r0, c0 in [(0, 0), (0, self.size - 7), (self.size - 7, 0)]:
            for i in range(-1, 8):
                for j in range(-1, 8):
                    r, c = r0 + i, c0 + j
                    if not (0 <= r < self.size and 0 <= c < self.size): continue
                    if 0 <= i <= 6 and 0 <= j <= 6:
                        if i in (0, 6) or j in (0, 6) or (2 <= i <= 4 and 2 <= j <= 4):
                            self.m[r][c] = 1
                        else:
                            self.m[r][c] = 0
                    else:
                        self.m[r][c] = 0

    def _timing(self):
        for i in range(8, self.size - 8):
            v = 1 if i % 2 == 0 else 0
            if self.m[6][i] == -1: self.m[6][i] = v
            if self.m[i][6] == -1: self.m[i][6] = v

    def _alignment(self):
        cr = cc = 22
        for i in range(-2, 3):
            for j in range(-2, 3):
                r, c = cr + i, cc + j
                if not (0 <= r < self.size and 0 <= c < self.size): continue
                if self.m[r][c] != -1: continue
                self.m[r][c] = 1 if (abs(i) == 2 or abs(j) == 2 or (i == 0 and j == 0)) else 0

    def _reserve_format(self):
        for r, c in [(8, 0), (8, 1), (8, 2), (8, 3), (8, 4), (8, 5), (8, 7), (8, 8), (7, 8), (5, 8), (4, 8), (3, 8),
                     (2, 8), (1, 8), (0, 8)]: self.m[r][c] = 0
        for i in range(7): self.m[self.size - 1 - i][8] = 0
        for i in range(8): self.m[8][self.size - 8 + i] = 0

    def _encode(self):
        bits = [0, 1, 0, 0];
        n = len(self.data)
        for i in range(7, -1, -1): bits.append((n >> i) & 1)
        for b in self.data:
            for i in range(7, -1, -1): bits.append((b >> i) & 1)
        cap = self.data_n * 8;
        bits += [0] * min(4, cap - len(bits))
        while len(bits) % 8: bits.append(0)
        pads = (0xEC, 0x11);
        k = 0
        while len(bits) < cap:
            b = pads[k % 2]
            for i in range(7, -1, -1): bits.append((b >> i) & 1)
            k += 1
        out = []
        for i in range(0, len(bits), 8):
            v = 0
            for j in range(8): v = (v << 1) | bits[i + j]
            out.append(v)
        return out

    def _place_data(self, cws):
        bits = []
        for cw in cws:
            for i in range(7, -1, -1): bits.append((cw >> i) & 1)
        idx = 0;
        col = self.size - 1;
        up = True
        while col > 0:
            if col == 6: col -= 1
            rows = range(self.size - 1, -1, -1) if up else range(self.size)
            for r in rows:
                for c in (col, col - 1):
                    if self.m[r][c] == -1:
                        self.m[r][c] = bits[idx] if idx < len(bits) else 0
                        self.dmods.add((r, c));
                        idx += 1
            col -= 2;
            up = not up

    @staticmethod
    def _mask_bit(mask, r, c):
        if mask == 0: return (r + c) % 2 == 0
        if mask == 1: return r % 2 == 0
        if mask == 2: return c % 3 == 0
        if mask == 3: return (r + c) % 3 == 0
        if mask == 4: return (r // 2 + c // 3) % 2 == 0
        if mask == 5: return (r * c) % 2 + (r * c) % 3 == 0
        if mask == 6: return ((r * c) % 2 + (r * c) % 3) % 2 == 0
        return ((r + c) % 2 + (r * c) % 3) % 2 == 0

    def _apply_mask(self, mask):
        for r, c in self.dmods:
            if QR._mask_bit(mask, r, c): self.m[r][c] ^= 1

    def _write_format(self, mask):
        data = mask;
        rem = data << 10;
        g = 0b10100110111
        for i in range(4, -1, -1):
            if rem & (1 << (i + 10)): rem ^= g << i
        bits = ((data << 10) | rem) ^ 0b101010000010010
        pos1 = [(8, 0), (8, 1), (8, 2), (8, 3), (8, 4), (8, 5), (8, 7), (8, 8), (7, 8), (5, 8), (4, 8), (3, 8), (2, 8),
                (1, 8), (0, 8)]
        for i, (r, c) in enumerate(pos1): self.m[r][c] = (bits >> (14 - i)) & 1
        pos2 = [(self.size - 1 - i, 8) for i in range(7)] + [(8, self.size - 8 + i) for i in range(8)]
        for i, (r, c) in enumerate(pos2): self.m[r][c] = (bits >> (14 - i)) & 1

    def _penalty(self):
        s, n = 0, self.size
        for i in range(n):
            row = self.m[i];
            col = [self.m[j][i] for j in range(n)]
            for line in (row, col):
                run = 1
                for j in range(1, n):
                    if line[j] == line[j - 1]:
                        run += 1
                    else:
                        if run >= 5: s += run - 2
                        run = 1
                if run >= 5: s += run - 2
        for i in range(n - 1):
            for j in range(n - 1):
                if (self.m[i][j] == self.m[i][j + 1] == self.m[i + 1][j] == self.m[i + 1][j + 1]): s += 3
        return s


PAGE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no,viewport-fit=cover">
<title>局域网快传</title>
<style>
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
:root{--bg:#0f1115;--card:rgba(26,29,36,0.7);--card2:#22262e;--fg:#e8eaed;--sub:#8a8f98;--acc:#4f8cff;--ok:#3ecf8e;--line:rgba(255,255,255,0.1);--chat-w:320px;--chat-h:450px}
html,body{margin:0;padding:0;background:var(--bg);color:var(--fg);font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif;min-height:100vh}
body{background:radial-gradient(circle at top left, #1a2233, #0f1115 70%)}
.wrap{max-width:640px;margin:0 auto;padding:16px;padding-top:calc(16px + env(safe-area-inset-top));padding-bottom:80px}
h1{font-size:20px;font-weight:700;margin:8px 0 4px}
.sub{color:var(--sub);font-size:13px;margin-bottom:20px}
#login-overlay{position:fixed;top:0;left:0;width:100vw;height:100vh;background:var(--bg);display:flex;flex-direction:column;align-items:center;justify-content:center;z-index:20000}
.login-box{background:var(--card2);padding:30px;border-radius:16px;text-align:center;border:1px solid var(--line)}
.login-input{margin:20px 0;padding:12px;width:200px;text-align:center;font-size:24px;letter-spacing:8px;background:#111;border:1px solid var(--acc);color:#fff;border-radius:8px;outline:none}
.login-btn{background:var(--acc);color:#fff;border:none;padding:10px 30px;border-radius:8px;font-size:16px;cursor:pointer;width:100%}
.card{background:var(--card);backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px);border:1px solid var(--line);border-radius:16px;padding:16px;margin-bottom:16px;box-shadow:0 8px 32px rgba(0,0,0,0.2)}
.drop{border:2px dashed var(--line);border-radius:12px;padding:24px 12px;text-align:center;color:var(--sub);cursor:pointer;transition:.2s}
.drop.over{border-color:var(--acc);color:var(--acc);background:rgba(79,140,255,.08)}
.drop b{color:var(--fg);display:block;font-size:16px;margin-bottom:4px}
.row{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:12px}
.toolbar{display:flex;gap:10px;align-items:center}
.icon-btn {background: var(--card2);border: 1px solid var(--line);color: var(--fg);border-radius: 8px;width: 36px;height: 36px;display: flex;align-items: center;justify-content: center;cursor: pointer;transition: .2s;padding: 0;}
.icon-btn:active { background: var(--line); transform: scale(0.95); }
.icon-btn svg { width: 20px; height: 20px; stroke: currentColor; stroke-width: 2.5; fill: none; stroke-linecap: round; stroke-linejoin: round; }
.icon-btn.active { background: var(--acc); border-color: var(--acc); color: #fff;}
.sort-select {background: var(--card2); color: var(--fg); border: 1px solid var(--line); border-radius: 8px; padding: 8px 12px; font-size: 14px; font-weight: 500; outline: none; appearance: none; cursor: pointer;}
.sort-select option {background: var(--card2); color: var(--fg);}
.breadcrumb {display: flex; align-items: center; flex-wrap: wrap; background: rgba(79, 140, 255, 0.15); border: 1px solid rgba(79, 140, 255, 0.4); border-radius: 10px; padding: 12px 16px; font-size: 15px; margin-bottom: 14px; gap: 6px; word-break: break-all; font-weight: 600;}
.breadcrumb-item {color: var(--fg); cursor: pointer; text-decoration: underline; text-underline-offset: 4px; text-decoration-color: rgba(255,255,255,0.5); transition: 0.2s;}
.breadcrumb-item:active {opacity: 0.6;}
.breadcrumb-sep {color: var(--acc); margin: 0 4px;}
.breadcrumb-current {color: var(--acc); cursor: default;}
.cb-wrap{display:flex;align-items:center;margin-right:12px;}
.cb-wrap input{width:22px;height:22px;accent-color:var(--acc);cursor:pointer;}
#files.list{display:flex;flex-direction:column;}
#files.list .file{display:flex;align-items:center;gap:12px;padding:14px 0;border-bottom:1px solid var(--line);cursor:pointer;}
#files.list .file:last-child{border-bottom:none}
#files.list .file .ico{width:44px;height:44px;border-radius:12px;background:var(--card2);display:flex;align-items:center;justify-content:center;font-size:22px;flex:none}
#files.list .file .meta{flex:1;min-width:0}
#files.list .file .name{font-size:15px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
#files.list .file .size{font-size:12px;color:var(--sub);margin-top:2px}
.empty{color:var(--sub);text-align:center;padding:32px;font-size:14px}
.prog{height:8px;background:var(--card2);border-radius:4px;overflow:hidden;margin-top:12px;display:none}
.prog.on{display:block}
.prog i{display:block;height:100%;width:0;background:var(--ok);transition:width .2s}
#toast{position:fixed;top:50%;left:50%;transform:translate(-50%,-50%) scale(0.9);background:rgba(62,207,142,.95);backdrop-filter:blur(10px);color:#fff;padding:16px 32px;border-radius:14px;font-size:15px;font-weight:600;opacity:0;pointer-events:none;transition:all .3s;z-index:9999;text-align:center}
#toast.show{opacity:1;transform:translate(-50%,-50%) scale(1)}
#toast.err{background:rgba(229,83,75,.95)}
#action-bar{position:fixed;bottom:0;left:0;width:100%;background:var(--card2);border-top:1px solid var(--line);padding:12px 20px;display:none;justify-content:space-between;align-items:center;z-index:1000;padding-bottom:calc(12px + env(safe-area-inset-bottom));box-shadow: 0 -4px 12px rgba(0,0,0,0.2)}
#action-bar.show{display:flex}
.act-btn{background:var(--card);color:var(--fg);border:1px solid var(--line);padding:10px 18px;border-radius:8px;font-size:14px;cursor:pointer;font-weight:600;transition:0.2s;}
.act-btn:active{transform:scale(0.95)}
.act-btn.danger{background:rgba(229,83,75,0.15);color:#e5534b;border:1px solid #e5534b}
.act-btn.cancel{background:rgba(229,83,75,0.1);border:1px solid transparent;color:#e5534b;padding:10px 16px;font-weight:bold}
#chat-bubble{position:fixed;right:20px;bottom:80px;width:56px;height:56px;border-radius:50%;background:var(--acc);display:flex;align-items:center;justify-content:center;box-shadow:0 4px 12px rgba(79,140,255,0.4);cursor:pointer;z-index:990;transition:0.3s}
#chat-bubble.unread{background:#f5a623;animation:pulse 1s infinite alternate}
#clipboard-bubble{position:fixed;right:20px;bottom:150px;width:56px;height:56px;border-radius:50%;background:var(--card2);border:1px solid var(--line);display:flex;align-items:center;justify-content:center;box-shadow:0 4px 12px rgba(0,0,0,0.3);cursor:pointer;z-index:990;transition:0.3s}
@keyframes pulse{from{transform:scale(1)}to{transform:scale(1.1)}}
#chat-bubble svg, #clipboard-bubble svg{width:28px;height:28px;fill:#fff}
#chat-window{position:fixed;right:20px;bottom:90px;width:var(--chat-w);height:var(--chat-h);background:var(--card2);border:1px solid var(--line);border-radius:16px;display:none;flex-direction:column;z-index:995;box-shadow:0 10px 40px rgba(0,0,0,0.5);overflow:hidden}
#chat-window.show{display:flex}
.chat-header{background:var(--acc);color:#fff;padding:12px 16px;font-weight:600;display:flex;justify-content:space-between;align-items:center;cursor:move;user-select:none}
.chat-close{cursor:pointer;font-size:20px;line-height:1}
.chat-body{flex:1;overflow-y:auto;padding:12px;display:flex;flex-direction:column;gap:10px}
.msg{max-width:80%;padding:10px 14px;border-radius:12px;font-size:14px;word-break:break-all}
.msg.me{align-self:flex-end;background:var(--acc);color:#fff;border-bottom-right-radius:2px}
.msg.other{align-self:flex-start;background:var(--card);border:1px solid var(--line);border-bottom-left-radius:2px}
.msg img{max-width:100%;border-radius:8px;display:block;margin-top:4px}
/* 聊天底部布局 */
.chat-footer{padding:10px;border-top:1px solid var(--line);display:flex;gap:8px;background:var(--card);align-items:center;}
.chat-tools{display:flex;gap:8px;align-items:center;}
.chat-btn { background: var(--card2); border: 1px solid var(--line); width: 34px; height: 34px; border-radius: 8px; display: flex; align-items: center; justify-content: center; cursor: pointer; transition: 0.2s; }
.chat-btn:active { background: var(--line); }
.chat-btn svg { width: 20px; height: 20px; fill: var(--acc); }
.chat-input{flex:1;background:var(--card2);border:1px solid var(--line);color:var(--fg);padding:10px;border-radius:8px;outline:none;min-width:0;}
#clipboard-panel{position:fixed;right:20px;bottom:220px;width:300px;background:var(--card2);border:1px solid var(--line);border-radius:16px;display:none;flex-direction:column;z-index:995;box-shadow:0 10px 40px rgba(0,0,0,0.5);padding:16px;}
#clipboard-panel.show{display:flex;}
.clip-textarea{width:100%;height:120px;background:var(--bg);border:1px solid var(--line);border-radius:8px;color:var(--fg);padding:10px;font-size:14px;resize:none;outline:none;font-family:monospace;}
#offline-overlay {position: fixed;top: 0;left: 0;width: 100vw;height: 100vh;background: rgba(15, 17, 21, 0.9);backdrop-filter: blur(15px);display: none;flex-direction: column;align-items: center;justify-content: center;z-index: 10000;text-align: center;padding: 20px;}
#offline-overlay.show { display: flex; }
.offline-card {background: var(--card2);border: 1px solid var(--line);border-radius: 24px;padding: 40px 30px;max-width: 360px;width: 100%;box-shadow: 0 20px 50px rgba(0,0,0,0.5);animation: popIn 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);}
@keyframes popIn { from { transform: scale(0.8); opacity: 0; } to { transform: scale(1); opacity: 1; } }
.offline-icon { font-size: 64px;margin-bottom: 20px;display: inline-block;animation: float 2s ease-in-out infinite; }
@keyframes float { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-10px); } }
.offline-title { font-size: 20px;font-weight: 700;color: var(--fg);margin-bottom: 12px; }
.offline-desc { font-size: 14px;color: var(--sub);margin-bottom: 30px;line-height: 1.6; }
.btn-reconnect {background: var(--acc);color: #fff;border: none;padding: 14px 24px;border-radius: 12px;font-size: 16px;font-weight: 600;width: 100%;cursor: pointer;transition: 0.2s;}
.btn-reconnect:active { transform: scale(0.96); opacity: 0.9; }
/* 在线预览样式 */
#preview-overlay {position: fixed;top: 0;left: 0;width: 100vw;height: 100vh;background: rgba(15,17,21,0.95);backdrop-filter: blur(10px);display: none;flex-direction: column;z-index: 30000;}
#preview-overlay.show {display: flex;}
.preview-header {display: flex;justify-content: space-between;align-items: center;padding: 12px 20px;background: var(--card2);border-bottom: 1px solid var(--line);color: var(--fg);font-weight: bold;font-size: 16px;flex:none;}
.preview-close {cursor: pointer;font-size: 28px;line-height: 1;color: var(--sub);transition: 0.2s;}
.preview-close:active {color: #e5534b;}
.preview-body {flex: 1;overflow: auto;display: flex;justify-content: center;align-items: center;padding: 10px;}
.preview-body img {max-width: 100%;max-height: 100%;object-fit: contain;border-radius: 8px;}
.preview-body iframe {width: 100%;height: 100%;border: none;background: #fff;border-radius: 8px;}
.preview-body pre {width: 100%;height: 100%;margin: 0;padding: 16px;background: #1a1d24;color: #c8ccd4;white-space: pre-wrap;word-break: break-all;font-family: Consolas, monospace;font-size: 14px;overflow: auto;border-radius: 8px;}
.preview-body video, .preview-body audio {max-width: 100%;max-height: 100%;outline: none;}
</style>
</head>
<body>
<div id="login-overlay">
  <div class="login-box">
    <h2>安全验证</h2>
    <p style="color:var(--sub);font-size:13px;margin-top:8px">请输入电脑端显示的 4 位 PIN 码</p>
    <input type="text" id="pinInput" class="login-input" maxlength="4" autocomplete="off">
    <br>
    <button class="login-btn" id="loginBtn" onclick="verifyPin()">进入系统</button>
  </div>
</div>

<div class="wrap">
  <h1>局域网快传</h1>
  <div class="sub">文件互传 + 剪贴板同步 + 在线预览</div>
  <div class="card">
    <div class="drop" id="drop">
      <b>拖拽文件/文件夹至此</b>
      <span style="font-size:12px;color:var(--sub);margin-top:4px;display:block;">或点击下方按钮</span>
      <div style="margin-top:10px;display:flex;justify-content:center;gap:10px;">
        <button class="act-btn" style="padding:6px 14px;font-size:13px;" onclick="event.stopPropagation();input.click()">选择文件</button>
        <button class="act-btn" style="padding:6px 14px;font-size:13px;" onclick="event.stopPropagation();folderInput.click()">上传文件夹</button>
      </div>
    </div>
    <input type="file" id="fileInput" multiple style="display:none">
    <input type="file" id="folderInput" webkitdirectory directory multiple style="display:none">
    <div class="prog" id="prog"><i id="progBar"></i></div>
  </div>
  <div class="card">
    <div class="row">
      <b style="font-size:16px">文件浏览</b>
      <div class="toolbar">
        <button class="icon-btn" id="multiToggle" title="多选模式"><svg viewBox="0 0 24 24"><path d="M9 11l3 3L22 4"></path><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"></path></svg></button>
        <select class="sort-select" id="sortSelect"><option value="name">按名称</option><option value="mtime">按时间</option><option value="size">按大小</option></select>
        <button class="icon-btn" id="refresh"><svg viewBox="0 0 24 24"><path d="M21 12a9 9 0 1 1-9-9c2.52 0 4.93 1 6.74 2.74L21 8"></path><path d="M21 3v5h-5"></path></svg></button>
      </div>
    </div>
    <div class="breadcrumb" id="breadcrumb"></div>
    <div id="files" class="list"><div class="empty">加载中…</div></div>
  </div>
</div>

<div id="action-bar">
  <button class="act-btn cancel" onclick="toggleMulti()">✕ 取消多选</button>
  <div style="display:flex;gap:10px;align-items:center">
    <span style="font-size:13px;color:var(--sub);font-weight:bold">已选 <span id="selCount" style="color:var(--acc);font-size:16px">0</span> 项</span>
    <button class="act-btn" onclick="batchDownload()">打包下载</button>
    <button class="act-btn danger" onclick="batchDelete()">删除</button>
  </div>
</div>

<!-- 预览遮罩层 -->
<div id="preview-overlay">
  <div class="preview-header">
    <span id="previewTitle">文件预览</span>
    <span class="preview-close" onclick="closePreview()">×</span>
  </div>
  <div class="preview-body" id="previewBody"></div>
</div>

<div id="offline-overlay">
    <div class="offline-card">
        <div class="offline-icon">☕️</div>
        <div class="offline-title">与电脑的连接断开啦</div>
        <div class="offline-desc">可能是电脑端软件被关闭了。<br>大文件上传/下载已保留进度，重连后可继续。</div>
        <button class="btn-reconnect" onclick="reconnect()">重新连接</button>
    </div>
</div>

<!-- 剪贴板悬浮按钮与面板 -->
<div id="clipboard-bubble" onclick="toggleClipboard()" title="局域网剪贴板">
  <svg viewBox="0 0 24 24"><path d="M16 4h-2c0-1.1-.9-2-2-2h-4c-1.1 0-2 .9-2 2H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm-6-2h4v2h-4V2zm6 16H4V6h2v2h12V6h2v12z"/></svg>
</div>
<div id="clipboard-panel">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
    <b style="font-size:16px;">局域网剪贴板</b>
    <span onclick="toggleClipboard()" style="cursor:pointer;font-size:20px;line-height:1;">×</span>
  </div>
  <textarea id="clipboardText" class="clip-textarea" placeholder="在此输入文字，点击下方发送到电脑剪贴板..."></textarea>
  <div style="display:flex;gap:10px;margin-top:10px;">
    <button class="act-btn" onclick="sendClipboard()" style="flex:1;background:var(--acc);color:#fff;border:none;">发送到电脑</button>
    <button class="act-btn" onclick="getClipboard()" style="flex:1;">读取电脑</button>
  </div>
</div>

<div id="chat-bubble" onclick="toggleChat()"><svg viewBox="0 0 24 24"><path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2z"/></svg></div>
<div id="chat-window">
  <div class="chat-header" id="chatHeader"><span>局域网聊天</span><span class="chat-close" onclick="toggleChat()">×</span></div>
  <div class="chat-body" id="chatBody"></div>
  <!-- 修复：彻底合并为一个按钮，不再限制选图片或文件，增加多选 -->
  <div class="chat-footer">
    <div class="chat-tools">
       <input type="file" id="chatFileInput" multiple style="display:none" onchange="sendChatFiles(this.files)">
       <div class="chat-btn" onclick="document.getElementById('chatFileInput').click()" title="发送图片/文件">
           <svg viewBox="0 0 24 24"><path d="M16.5 6v11.5c0 2.21-1.79 4-4 4s-4-1.79-4-4V5c0-1.38 1.12-2.5 2.5-2.5s2.5 1.12 2.5 2.5v10.5c0 .55-.45 1-1 1s-1-.45-1-1V6H10v9.5c0 1.38 1.12 2.5 2.5 2.5s2.5-1.12 2.5-2.5V5c0-2.21-1.79-4-4-4S7 2.79 7 5v12.5c0 3.04 2.46 5.5 5.5 5.5s5.5-2.46 5.5-5.5V6h-1.5z"/></svg>
       </div>
    </div>
    <input type="text" class="chat-input" id="chatInput" onkeypress="if(event.key==='Enter') sendChatMsg()">
    <button class="act-btn" style="background:var(--acc);color:#fff;border:none" onclick="sendChatMsg()">发送</button>
  </div>
</div>
<div id="toast"></div>
<script>
let globalToken = "";
let isVerifying = false;
let hasLoggedIn = false;

function verifyPin() {
    if(isVerifying || hasLoggedIn) return;
    const pin = document.getElementById('pinInput').value.trim();
    if(pin.length !== 4) return alert('请输入完整的4位PIN码');

    isVerifying = true;
    const btn = document.getElementById('loginBtn');
    btn.textContent = '验证中...';
    btn.disabled = true;

    fetch('/verify', { 
        method:'POST', 
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pin: pin }) 
    }).then(r => {
        if(!r.ok) throw new Error('HTTP status ' + r.status);
        return r.json();
    }).then(d => {
        if(d.ok) { 
            globalToken = d.token; 
            hasLoggedIn = true;
            const overlay = document.getElementById('login-overlay');
            overlay.style.display = 'none';
            overlay.style.visibility = 'hidden';
            initSSE(); 
            refresh(); 
        } else {
            alert('PIN码错误，请检查电脑屏幕');
            isVerifying = false;
            btn.textContent = '进入系统';
            btn.disabled = false;
        }
    }).catch(e => {
        alert('验证失败，请确保电脑端已开启且网络正常');
        isVerifying = false;
        btn.textContent = '进入系统';
        btn.disabled = false;
    });
}

const $=id=>document.getElementById(id);
const filesEl=$('files'),drop=$('drop'),input=$('fileInput'),folderInput=$('folderInput'),prog=$('prog'),bar=$('progBar');
const toastEl=$('toast'),refreshBtn=$('refresh'),multiToggle=$('multiToggle');
const breadcrumb=$('breadcrumb'), sortSelect=$('sortSelect'), actionBar=$('action-bar'), selCount=$('selCount');
const offlineOverlay=$('offline-overlay');
let currentSort = 'name', isUploading = false, currentPath = '', isMultiMode = false;
let selectedItems = new Set(), currentItems = [];
let isOffline = false;

// 聊天与剪贴板面板切换
let chatOpen = false, unread = false;
function toggleChat() {
    chatOpen = !chatOpen; $('chat-window').classList.toggle('show', chatOpen);
    if(chatOpen) { unread = false; $('chat-bubble').classList.remove('unread'); $('clipboard-panel').classList.remove('show'); scrollToBottom(); }
}
function toggleClipboard() {
    const p = $('clipboard-panel');
    p.classList.toggle('show');
    if(p.classList.contains('show')) { chatOpen = false; $('chat-window').classList.remove('show'); }
}

// 剪贴板操作
async function sendClipboard() {
    const text = $('clipboardText').value;
    if(!text) return showToast('请输入文字', true);
    try {
        await fetch('/clipboard?token='+globalToken, {method:'POST', body: text});
        showToast('已同步到电脑剪贴板');
    } catch(e) { showToast('同步失败', true); }
}
async function getClipboard() {
    try {
        const res = await fetch('/clipboard?token='+globalToken);
        const data = await res.json();
        $('clipboardText').value = data.text || '';
        showToast('已读取电脑剪贴板');
    } catch(e) { showToast('读取失败', true); }
}

function scrollToBottom() { const b=$('chatBody'); b.scrollTop = b.scrollHeight; }
function sendChatMsg() {
    const text = $('chatInput').value.trim(); if(!text) return; $('chatInput').value = '';
    fetch('/chat/send?token='+globalToken, {method:'POST', body: JSON.stringify({type:'text', content:text})});
    appendMsg('me', text);
}

// 聊天发送多文件（队列处理 + 状态提示）
async function sendChatFiles(files) {
    if(!files || files.length === 0) return; 

    for (let f of files) {
        // 1. 立即插入一个“正在上传”的气泡
        const tempId = 'upload_' + Date.now() + '_' + Math.floor(Math.random()*1000);
        const d = document.createElement('div');
        d.className = `msg me`;
        d.id = tempId;
        d.innerHTML = `<span style="opacity:0.7;">正在上传: ${f.name}...</span>`;
        $('chatBody').appendChild(d);
        scrollToBottom();

        // 2. 执行上传
        prog.classList.add('on');
        bar.style.width = '0%';
        const totalChunks = Math.ceil(f.size / CHUNK_SIZE);
        const fileId = btoa(encodeURIComponent(f.name + "_" + f.size));

        try {
            for (let i = 0; i < totalChunks; i++) {
                const start = i * CHUNK_SIZE; const end = Math.min(f.size, start + CHUNK_SIZE);
                const url = `/upload?name=${encodeURIComponent(f.name)}&is_chat=1&chunk=${i}&chunks=${totalChunks}&fileId=${fileId}&token=${globalToken}`;
                await uploadChunkWithRetry(f.slice(start, end), url);
                bar.style.width = Math.round(((i + 1) / totalChunks) * 100) + '%';
            }

            // 3. 上传成功，替换气泡内容
            const isImg = ['jpg','jpeg','png','gif','webp'].includes(f.name.split('.').pop().toLowerCase());
            const msgType = isImg ? 'image' : 'file';

            if (isImg) {
                d.innerHTML = `<img src="/download/${encodeURIComponent(f.name)}?token=${globalToken}" alt="图片">`;
            } else {
                d.innerHTML = `<a href="/download/${encodeURIComponent(f.name)}?token=${globalToken}" style="color:#fff;text-decoration:underline" download>📎 ${f.name}</a>`;
            }

            // 通知其他端刷新
            fetch('/chat/send?token='+globalToken, {method:'POST', body: JSON.stringify({type:msgType, content:f.name})});

        } catch (e) {
            d.innerHTML = `<span style="color:#ffcccc;">上传失败: ${f.name}</span>`;
        }
        prog.classList.remove('on');
    }
    refresh(); // 刷新下方文件列表
    showToast('发送完成');
}

function appendMsg(sender, content, type='text') {
    const d = document.createElement('div'); d.className = `msg ${sender}`;
    if(type === 'image') d.innerHTML = `<img src="/download/${encodeURIComponent(content)}?token=${globalToken}" alt="图片">`;
    else if(type === 'file') d.innerHTML = `<a href="/download/${encodeURIComponent(content)}?token=${globalToken}" style="color:#fff;text-decoration:underline" download>📎 ${content}</a>`;
    else d.innerText = content;
    $('chatBody').appendChild(d); scrollToBottom();
}

// SSE 与 断线重连
let evtSource = null;
function initSSE() {
    if(evtSource) evtSource.close();
    evtSource = new EventSource('/events?token=' + globalToken);
    evtSource.onopen = () => { hideOffline(); };
    evtSource.onerror = (e) => { 
        if (hasLoggedIn) { showOffline(); evtSource.close(); }
    };
    evtSource.onmessage = (e) => {
        const data = JSON.parse(e.data);
        if(data.type === 'chat') {
            if(!chatOpen) { unread = true; $('chat-bubble').classList.add('unread'); }
            appendMsg('other', data.content, data.msgType);
        } else if(data.type === 'refresh') refresh();
    };
}
function showOffline() { if(!isOffline) { isOffline = true; offlineOverlay.classList.add('show'); } }
function hideOffline() { if(isOffline || offlineOverlay.classList.contains('show')) { isOffline = false; offlineOverlay.classList.remove('show'); refresh(); } }
function reconnect() {
    const btn = offlineOverlay.querySelector('.btn-reconnect');
    const originalText = btn.textContent;
    btn.textContent = '正在重连...'; btn.style.opacity = '0.7';
    const controller = new AbortController(); const timeoutId = setTimeout(() => controller.abort(), 4000); 
    fetch('/list?path=' + encodeURIComponent(currentPath) + '&token=' + globalToken + '&t=' + Date.now(), { signal: controller.signal })
        .then(r => {
            clearTimeout(timeoutId);
            if(r.ok) { hideOffline(); initSSE(); showToast('重连成功！'); }
            else throw new Error('still offline');
        }).catch(e => { clearTimeout(timeoutId); showToast('重连失败，请确保电脑端已打开且端口无变化', true); })
        .finally(() => { btn.textContent = originalText; btn.style.opacity = '1'; });
}

document.addEventListener('visibilitychange', () => { 
    if (document.visibilityState === 'visible' && hasLoggedIn) {
        if (!evtSource || evtSource.readyState === 2) {
            initSSE(); hideOffline(); refresh();
        }
    }
});

// 多选逻辑
function toggleMulti() {
    isMultiMode = !isMultiMode; selectedItems.clear();
    actionBar.classList.toggle('show', isMultiMode);
    multiToggle.classList.toggle('active', isMultiMode);
    refresh();
}
multiToggle.onclick = toggleMulti;

function handleItemClick(el, event) {
    if (isMultiMode) {
        event.preventDefault();
        const path = el.getAttribute('data-path');
        const checkbox = el.querySelector('input[type="checkbox"]');
        if (selectedItems.has(path)) {
            selectedItems.delete(path);
            if (checkbox) checkbox.checked = false;
        } else {
            selectedItems.add(path);
            if (checkbox) checkbox.checked = true;
        }
        selCount.innerText = selectedItems.size;
    } else {
        const path = el.getAttribute('data-path');
        const isDir = el.getAttribute('data-isdir') === '1';
        const name = el.querySelector('.name').innerText;
        if (isDir) {
            enterDir(path);
        } else {
            const ext = name.split('.').pop().toLowerCase();
            const textExts = ['txt', 'md', 'log', 'json', 'py', 'js', 'css', 'html', 'xml', 'csv', 'ini', 'bat', 'sh'];
            const imgExts = ['jpg', 'jpeg', 'png', 'gif', 'webp', 'svg', 'bmp', 'ico'];
            const pdfExts = ['pdf'];
            const videoExts = ['mp4', 'webm', 'ogg'];
            const audioExts = ['mp3', 'wav', 'ogg'];

            if (textExts.includes(ext) || imgExts.includes(ext) || pdfExts.includes(ext) || videoExts.includes(ext) || audioExts.includes(ext)) {
                showPreview(path, name, ext);
            } else {
                triggerDownload('/download/' + encodeURIComponent(path) + '?token=' + globalToken);
            }
        }
    }
}

// 在线预览逻辑
async function showPreview(path, name, ext) {
    const overlay = $('preview-overlay');
    const title = $('previewTitle');
    const body = $('previewBody');

    title.innerText = '预览: ' + name;
    body.innerHTML = '<div style="color:#fff;font-size:16px;">加载中...</div>';
    overlay.classList.add('show');

    const fileUrl = '/download/' + encodeURIComponent(path) + '?token=' + globalToken + '&inline=1';
    const textExts = ['txt', 'md', 'log', 'json', 'py', 'js', 'css', 'html', 'xml', 'csv', 'ini', 'bat', 'sh'];
    const imgExts = ['jpg', 'jpeg', 'png', 'gif', 'webp', 'svg', 'bmp', 'ico'];
    const pdfExts = ['pdf'];
    const videoExts = ['mp4', 'webm', 'ogg'];
    const audioExts = ['mp3', 'wav', 'ogg'];

    try {
        if (textExts.includes(ext)) {
            const res = await fetch(fileUrl);
            const arrayBuffer = await res.arrayBuffer();
            let text = "";
            try {
                text = new TextDecoder("utf-8", { fatal: true }).decode(arrayBuffer);
            } catch (e) {
                try {
                    text = new TextDecoder("gbk").decode(arrayBuffer);
                } catch (e2) {
                    text = new TextDecoder("utf-8").decode(arrayBuffer); 
                }
            }
            body.innerHTML = `<pre style="color:#fff;background:transparent;padding:0;">${escapeHtml(text)}</pre>`;
        } else if (imgExts.includes(ext)) {
            body.innerHTML = `<img src="${fileUrl}" alt="${name}">`;
        } else if (pdfExts.includes(ext)) {
            body.innerHTML = `<iframe src="${fileUrl}"></iframe>`;
        } else if (videoExts.includes(ext)) {
            body.innerHTML = `<video src="${fileUrl}" controls autoplay></video>`;
        } else if (audioExts.includes(ext)) {
            body.innerHTML = `<audio src="${fileUrl}" controls autoplay></audio>`;
        }
    } catch (e) {
        body.innerHTML = `<div style="color:#e5534b;font-size:16px;">预览失败: ${e.message}</div>`;
    }
}

function closePreview() {
    $('preview-overlay').classList.remove('show');
    $('previewBody').innerHTML = ''; 
}

function escapeHtml(unsafe) {
    return unsafe
         .replace(/&/g, "&amp;")
         .replace(/</g, "&lt;")
         .replace(/>/g, "&gt;")
         .replace(/"/g, "&quot;")
         .replace(/'/g, "&#039;");
}

function batchDownload() {
    if(!selectedItems.size) return showToast('请先选择文件', true);
    const form = document.createElement('form'); form.method='POST'; form.action='/batch_zip?token='+globalToken; form.target='_blank';
    const input = document.createElement('input'); input.type='hidden'; input.name='paths'; input.value=JSON.stringify(Array.from(selectedItems));
    form.appendChild(input); document.body.appendChild(form); form.submit(); document.body.removeChild(form);
}
async function batchDelete() {
    if(!selectedItems.size) return showToast('请先选择文件', true);
    if(!confirm(`确定删除 ${selectedItems.size} 项？`)) return;
    try {
        await fetch('/delete?token='+globalToken, {method:'POST', body: JSON.stringify({paths: Array.from(selectedItems)})});
        showToast('删除成功'); selectedItems.clear(); selCount.innerText=0; refresh();
    } catch(e) { showToast('删除失败', true); }
}

// 浏览与上传
function fmt(n){n=+n||0;if(n<1024)return n+' B';if(n<1048576)return (n/1024).toFixed(1)+' KB';if(n<1073741824)return (n/1048576).toFixed(1)+' MB';return (n/1073741824).toFixed(2)+' GB'}
function esc(s){return s.replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
function getIcon(name, isDir){
  if(isDir) return '📁';
  const ext = name.split('.').pop().toLowerCase();
  if(['jpg','jpeg','png','gif','webp','svg','bmp','ico'].includes(ext)) return '🖼️';
  if(['mp4','mkv','avi','mov','wmv','flv'].includes(ext)) return '🎬';
  if(['mp3','wav','flac','aac','ogg'].includes(ext)) return '🎵';
  if(['zip','rar','7z','tar','gz','xz'].includes(ext)) return '📦';
  if(['exe','msi','bat','cmd','apk'].includes(ext)) return '⚙️';
  if(['pdf','doc','docx','xls','xlsx','ppt','pptx'].includes(ext)) return '📄';
  if(['txt','log','md','csv','json','py','js','css','html'].includes(ext)) return '📝';
  return '📄';
}
function showToast(msg, isErr=false){
  toastEl.textContent = msg; toastEl.className = 'show' + (isErr ? ' err' : '');
  clearTimeout(window.toastTimer); window.toastTimer = setTimeout(() => { toastEl.className = ''; }, 3000);
}
function renderBreadcrumb() {
    let html = `<span class="breadcrumb-item" onclick="enterDir('')">🏠 根目录</span>`;
    if(currentPath) {
        let parts = currentPath.split('/'); let accumPath = '';
        for(let i=0; i<parts.length; i++) {
            accumPath += (accumPath ? '/' : '') + parts[i];
            html += `<span class="breadcrumb-sep">/</span>`;
            if(i === parts.length - 1) html += `<span class="breadcrumb-current">${esc(parts[i])}</span>`;
            else html += `<span class="breadcrumb-item" onclick="enterDir('${esc(accumPath)}')">${esc(parts[i])}</span>`;
        }
    }
    breadcrumb.innerHTML = html;
}
function enterDir(path) { if(!isMultiMode) { currentPath = path; refresh(); } else showToast('请先退出多选模式', true); }
function triggerDownload(url) { if(!isMultiMode) { const a=document.createElement('a'); a.href=url; a.download=''; a.style.display='none'; document.body.appendChild(a); a.click(); setTimeout(()=>document.body.removeChild(a), 100); } }

async function refresh(){
  if(isOffline) return;
  renderBreadcrumb();
  try{
    const r = await fetch(`/list?path=${encodeURIComponent(currentPath)}&sort=${currentSort}&token=${globalToken}&t=${Date.now()}`);
    if(!r.ok) { if (r.status === 404) { if (currentPath !== '') { currentPath = ''; refresh(); return; } throw new Error('目录不存在'); } throw new Error('HTTP ' + r.status); }
    const arr = await r.json(); currentItems = arr;
    if(!arr.length){filesEl.innerHTML='<div class="empty">此目录为空</div>';return;}

    filesEl.innerHTML=arr.map(f=>{
      const icon = getIcon(f.name, f.is_dir);
      const sizeStr = f.is_dir ? '文件夹' : fmt(f.size);
      const itemPath = currentPath ? currentPath + '/' + f.name : f.name;
      const isChecked = selectedItems.has(itemPath);

      const cbHtml = isMultiMode ? `<div class="cb-wrap"><input type="checkbox" ${isChecked?'checked':''} style="pointer-events:none;"></div>` : '';
      let inner = `${cbHtml}<div class="ico">${icon}</div><div class="meta"><div class="name" title="${esc(f.name)}">${esc(f.name)}</div><div class="size">${sizeStr}</div></div>`;

      return `<div class="file" onclick="handleItemClick(this, event)" data-path="${esc(itemPath)}" data-isdir="${f.is_dir ? 1 : 0}">${inner}</div>`;
    }).join('');
  } catch(e) {
      if (e instanceof TypeError || e.message.includes('Failed to fetch')) showOffline();
      else showToast('读取失败: ' + e.message, true);
  }
}

const CHUNK_SIZE = 2 * 1024 * 1024; 

async function uploadChunkWithRetry(chunkData, url, maxRetries = 3) {
    for (let attempt = 1; attempt <= maxRetries; attempt++) {
        try {
            return await new Promise((resolve, reject) => {
                const xhr = new XMLHttpRequest();
                xhr.open('POST', url);
                xhr.timeout = 15000; 
                xhr.onload = () => {
                    if (xhr.status === 200) resolve();
                    else reject(new Error('HTTP ' + xhr.status));
                };
                xhr.onerror = () => reject(new Error('网络中断'));
                xhr.ontimeout = () => reject(new Error('请求超时'));
                xhr.send(chunkData);
            });
        } catch (e) {
            if (attempt === maxRetries) throw e; 
            await new Promise(r => setTimeout(r, 1000)); 
        }
    }
}

async function uploadFileChunked(file) {
    const totalChunks = Math.ceil(file.size / CHUNK_SIZE);
    const fileId = btoa(encodeURIComponent(file.name + "_" + file.size));
    let startChunk = 0;
    try {
        const statusRes = await fetch(`/upload/status?path=${encodeURIComponent(currentPath)}&fileId=${fileId}&token=${globalToken}`);
        if(statusRes.ok) { const statusData = await statusRes.json(); startChunk = statusData.received_chunks || 0; }
    } catch(e) { }

    const relName = file.relativePath || file.webkitRelativePath || file.name;
    for (let i = startChunk; i < totalChunks; i++) {
        if (isOffline) throw new Error("网络已断开");
        const start = i * CHUNK_SIZE; const end = Math.min(file.size, start + CHUNK_SIZE);
        const url = `/upload?path=${encodeURIComponent(currentPath)}&name=${encodeURIComponent(relName)}&chunk=${i}&chunks=${totalChunks}&fileId=${fileId}&token=${globalToken}`;
        await uploadChunkWithRetry(file.slice(start, end), url);
        bar.style.width = Math.round(((i + 1) / totalChunks) * 100) + '%';
    }
}

async function uploadFiles(list){
  if(isUploading || !list.length) return;
  isUploading = true; prog.classList.add('on');
  let successCount = 0;
  for(let i=0; i<list.length; i++){ 
      try { await uploadFileChunked(list[i]); successCount++; } 
      catch(e){} 
  }
  prog.classList.remove('on'); isUploading = false; refresh();
  if(successCount > 0) showToast(`成功上传 ${successCount} 个文件`);
}

drop.onclick = () => { if(!isUploading) input.click(); };
input.onchange = () => { uploadFiles(Array.from(input.files)); input.value=''; };
folderInput.onchange = () => { uploadFiles(Array.from(folderInput.files)); folderInput.value=''; };
drop.addEventListener('dragover', e => { e.preventDefault(); drop.classList.add('over'); });
drop.addEventListener('dragleave', e => { e.preventDefault(); drop.classList.remove('over'); });
drop.addEventListener('drop', async e => {
    e.preventDefault(); drop.classList.remove('over');
    if (isUploading) return;
    const items = e.dataTransfer.items;
    const files = [];
    if (items) {
        const promises = [];
        for (let i = 0; i < items.length; i++) {
            const item = items[i].webkitGetAsEntry();
            if (item) promises.push(traverseFileTree(item, files));
        }
        await Promise.all(promises);
        uploadFiles(files);
    } else if (e.dataTransfer.files) {
        uploadFiles(Array.from(e.dataTransfer.files));
    }
});

async function traverseFileTree(item, files, path = '') {
    if (item.isFile) {
        return new Promise(resolve => {
            item.file(file => {
                file.relativePath = path + file.name;
                files.push(file);
                resolve();
            });
        });
    } else if (item.isDirectory) {
        const dirReader = item.createReader();
        let entries = [];
        let readEntries = () => {
            return new Promise(resolve => {
                dirReader.readEntries(results => {
                    if (results.length) {
                        entries = entries.concat(Array.from(results));
                        readEntries().then(resolve);
                    } else { resolve(); }
                });
            });
        };
        await readEntries();
        for (let entry of entries) {
            await traverseFileTree(entry, files, path + item.name + '/');
        }
    }
}

refreshBtn.onclick=e=>{e.preventDefault();refresh();};
const chatWindow = $('chat-window'), chatHeader = $('chatHeader');
let isDragging = false, offsetX, offsetY;
chatHeader.onmousedown = (e) => { isDragging = true; offsetX = e.clientX - chatWindow.getBoundingClientRect().left; offsetY = e.clientY - chatWindow.getBoundingClientRect().top; };
document.onmousemove = (e) => { if(!isDragging) return; chatWindow.style.left = (e.clientX - offsetX) + 'px'; chatWindow.style.top = (e.clientY - offsetY) + 'px'; chatWindow.style.right = 'auto'; chatWindow.style.bottom = 'auto'; };
document.onmouseup = () => { isDragging = false; };
</script>
</body>
</html>
"""

WECHAT_WARN_PAGE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1">
<title>请使用浏览器打开</title>
<style>
body{margin:0;padding:0;background:#0f1115;color:#e8eaed;font-family:-apple-system,sans-serif;text-align:center;padding-top:80px}
h2{font-size:22px;margin-bottom:10px}
p{color:#8a8f98;font-size:15px;margin-bottom:60px}
.arrow{font-size:60px;color:#4f8cff;animation:up 1s infinite alternate}
@keyframes up{from{transform:translateY(0)}to{transform:translateY(-15px)}}
.top-hint{position:absolute;top:10px;right:15px;color:#4f8cff;font-size:16px;font-weight:bold;display:flex;align-items:center;gap:5px}
</style>
</head>
<body>
  <div class="top-hint">点击右上角 <span style="font-size:24px">···</span></div>
  <div class="arrow">↗</div>
  <h2 style="margin-top:20px">请在浏览器中打开</h2>
  <p>微信/QQ 拦截了局域网网页<br>请点击右上角菜单，选择“在浏览器中打开”</p>
</body>
</html>
"""


class RobustServer(http.server.ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True
    timeout = 60

    def handle_error(self, request, client_address):
        exc_type, exc_value, _ = sys.exc_info()
        if exc_type in (ConnectionResetError, ConnectionAbortedError, BrokenPipeError): return
        super().handle_error(request, client_address)


class ShareServer:
    def __init__(self, root_dir, pin, app_ref):
        self.root_dir = os.path.normpath(os.path.abspath(root_dir))
        self.httpd = None
        self.port = 0
        self.log_cb = None
        self.active_sse_connections = []
        self.pin = pin
        self.auth_token = base64.b64encode(os.urandom(16)).decode('utf-8').replace('=', '')
        self.app_ref = app_ref

    def start(self):
        Handler = self._make_handler()
        base_port = 54321
        for i in range(100):
            try:
                self.httpd = RobustServer(('0.0.0.0', base_port + i), Handler)
                self.port = base_port + i
                break
            except OSError:
                continue
        if not self.httpd: raise RuntimeError("无可用端口")
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        return self.port

    def stop(self):
        for conn in list(self.active_sse_connections):
            try:
                conn.close()
            except Exception:
                pass
        self.active_sse_connections.clear()
        if self.httpd:
            try:
                self.httpd.shutdown();
                self.httpd.server_close()
            except Exception:
                pass
            self.httpd = None

    def log(self, msg):
        if self.log_cb: self.log_cb(msg)

    def broadcast(self, data):
        msg = f"data: {json.dumps(data, ensure_ascii=False)}\n\n".encode('utf-8')
        for conn in list(self.active_sse_connections):
            try:
                conn.sendall(msg)
            except Exception:
                if conn in self.active_sse_connections: self.active_sse_connections.remove(conn)

    def _get_safe_path(self, req_path):
        try:
            req_path = urllib.parse.unquote(req_path).replace('\\', '/').lstrip('/')
            if os.name == 'nt' and len(self.root_dir) > 240:
                root = "\\\\?\\" + self.root_dir
                target = os.path.normpath(os.path.join(root, req_path))
                safe = target.lower().startswith(root.lower())
            else:
                target = os.path.normpath(os.path.join(self.root_dir, req_path))
                safe = target.lower().startswith(self.root_dir.lower()) if os.name == 'nt' else target.startswith(
                    self.root_dir)
            return target if safe else None
        except Exception:
            return None

    def _make_handler(self):
        srv = self

        class Handler(http.server.BaseHTTPRequestHandler):
            protocol_version = 'HTTP/1.1'

            def log_message(self, *a):
                pass

            def end_headers(self):
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
                super().end_headers()

            def do_OPTIONS(self):
                self.send_response(200)
                self.send_header('Connection', 'close')
                self.end_headers()

            def do_GET(self):
                p = urllib.parse.urlparse(self.path)
                q = urllib.parse.parse_qs(p.query)
                token = q.get('token', [''])[0]
                if p.path == '/':
                    self._send_html()
                elif not token == srv.auth_token:
                    self.send_error(401)
                elif p.path == '/events':
                    self._handle_sse()
                elif p.path == '/list':
                    self._send_list(p.query)
                elif p.path == '/upload/status':
                    self._upload_status(p.query)
                elif p.path == '/clipboard':
                    self._get_clipboard()
                elif p.path.startswith('/download/'):
                    inline = q.get('inline', ['0'])[0]
                    self._send_file(p.path[10:], inline)
                else:
                    self.send_error(404)

            def do_POST(self):
                p = urllib.parse.urlparse(self.path)
                q = urllib.parse.parse_qs(p.query)
                token = q.get('token', [''])[0]
                length = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(length) if length > 0 else b''

                if p.path == '/verify':
                    self._verify(body)
                elif not token == srv.auth_token:
                    self.send_error(401)
                elif p.path == '/upload':
                    self._recv_file(q)
                elif p.path == '/delete':
                    self._delete_files(body)
                elif p.path == '/batch_zip':
                    self._batch_zip(body)
                elif p.path == '/chat/send':
                    self._chat_send(body)
                elif p.path == '/clipboard':
                    self._set_clipboard(body)
                else:
                    self.send_error(404)

            def _get_clipboard(self):
                srv.app_ref.clipboard_get_req.set()
                srv.app_ref.clipboard_get_req.wait(timeout=2)
                text = srv.app_ref.clipboard_get_res
                res = json.dumps({'text': text}).encode('utf-8')
                self.send_response(200)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.send_header('Content-Length', str(len(res)))
                self.send_header('Connection', 'close')
                self.end_headers()
                self.wfile.write(res)

            def _set_clipboard(self, body):
                try:
                    text = body.decode('utf-8')
                    srv.app_ref.clipboard_set_q.put(text)
                    self.send_response(200)
                    self.send_header('Connection', 'close')
                    self.end_headers()
                except Exception:
                    self.send_error(500)

            def _verify(self, body):
                try:
                    data = json.loads(body)
                    if data.get('pin') == srv.pin:
                        res = json.dumps({'ok': True, 'token': srv.auth_token}).encode()
                    else:
                        res = json.dumps({'ok': False, 'msg': 'PIN码错误'}).encode()
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Content-Length', str(len(res)))
                    self.send_header('Connection', 'close')
                    self.end_headers()
                    self.wfile.write(res)
                except Exception:
                    self.send_error(400)

            def _send_html(self):
                ua = self.headers.get('User-Agent', '').lower()
                body = WECHAT_WARN_PAGE.encode() if ('micromessenger' in ua or ' qq/' in ua) else PAGE.encode()
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Content-Length', str(len(body)))
                self.send_header('Connection', 'close')
                self.end_headers()
                self.wfile.write(body)

            def _handle_sse(self):
                self.send_response(200)
                self.send_header('Content-Type', 'text/event-stream')
                self.send_header('Cache-Control', 'no-cache')
                self.send_header('Connection', 'keep-alive')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                srv.active_sse_connections.append(self.connection)
                try:
                    while True:
                        self.wfile.write(b": keepalive\n\n")
                        self.wfile.flush()
                        time.sleep(5)
                except Exception:
                    pass
                finally:
                    if self.connection in srv.active_sse_connections:
                        srv.active_sse_connections.remove(self.connection)

            def _send_list(self, query):
                try:
                    q = urllib.parse.parse_qs(query)
                    req_path = q.get('path', [''])[0]
                    sort_mode = q.get('sort', ['name'])[0]
                    target_dir = srv._get_safe_path(req_path)
                    if not target_dir or not os.path.isdir(target_dir):
                        self.send_error(404)
                        return
                    items = []
                    for name in os.listdir(target_dir):
                        if name.startswith('.') or name in ('Thumbs.db', 'desktop.ini'): continue
                        fp = os.path.join(target_dir, name)
                        is_dir = os.path.isdir(fp)
                        st = os.stat(fp)
                        items.append(
                            {'name': name, 'size': 0 if is_dir else st.st_size, 'mtime': st.st_mtime, 'is_dir': is_dir})
                    if sort_mode == 'mtime':
                        items.sort(key=lambda x: (not x['is_dir'], -x['mtime']))
                    elif sort_mode == 'size':
                        items.sort(key=lambda x: (not x['is_dir'], -x['size']))
                    else:
                        items.sort(key=lambda x: (not x['is_dir'], natural_sort_key(x['name'])))
                    body = json.dumps(items, ensure_ascii=False).encode()
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json; charset=utf-8')
                    self.send_header('Content-Length', str(len(body)))
                    self.send_header('Connection', 'close')
                    self.end_headers()
                    self.wfile.write(body)
                except Exception:
                    self.send_error(500)

            def _upload_status(self, query):
                try:
                    q = urllib.parse.parse_qs(query)
                    req_path = q.get('path', [''])[0]
                    file_id = q.get('fileId', [''])[0]
                    target_dir = srv._get_safe_path(req_path)
                    if not target_dir or not os.path.isdir(target_dir):
                        self.send_error(400)
                        return
                    temp_name = f".tmp_{file_id}.part"
                    fp = os.path.join(target_dir, temp_name)
                    received_chunks = 0
                    if os.path.exists(fp):
                        size = os.path.getsize(fp)
                        received_chunks = size // (2 * 1024 * 1024)
                    body = json.dumps({'received_chunks': received_chunks}).encode()
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Content-Length', str(len(body)))
                    self.send_header('Connection', 'close')
                    self.end_headers()
                    self.wfile.write(body)
                except Exception:
                    self.send_error(500)

            def _send_file(self, path_str, inline='0'):
                fp = srv._get_safe_path(path_str)
                if not fp or not os.path.isfile(fp):
                    self.send_error(404)
                    return
                try:
                    st = os.stat(fp)
                    file_size = st.st_size
                    range_header = self.headers.get('Range')
                    start, end = 0, file_size - 1
                    is_partial = False
                    if range_header:
                        m = re.match(r'bytes=(\d+)-(\d*)', range_header)
                        if m:
                            is_partial = True
                            start = int(m.group(1))
                            end = int(m.group(2)) if m.group(2) else file_size - 1

                    if is_partial:
                        self.send_response(206)
                        self.send_header('Content-Range', f'bytes {start}-{end}/{file_size}')
                        length = end - start + 1
                    else:
                        self.send_response(200)
                        length = file_size

                    if inline == '1':
                        ctype, _ = mimetypes.guess_type(fp)
                        if not ctype:
                            ctype = 'text/plain; charset=utf-8' if fp.endswith(
                                ('.txt', '.log', '.md', '.py')) else 'application/octet-stream'
                        if 'text/' in ctype and 'charset' not in ctype:
                            ctype += '; charset=utf-8'
                        self.send_header('Content-Type', ctype)
                        self.send_header('Content-Disposition', 'inline')
                    else:
                        self.send_header('Content-Type', 'application/octet-stream')
                        encoded_name = urllib.parse.quote(os.path.basename(fp))
                        self.send_header('Content-Disposition',
                                         f"attachment; filename=\"{encoded_name}\"; filename*=UTF-8''{encoded_name}")

                    self.send_header('Accept-Ranges', 'bytes')
                    self.send_header('Content-Length', str(length))
                    self.send_header('Connection', 'close')
                    self.end_headers()

                    if start == 0:
                        if inline == '1':
                            srv.log(f"👀 手机在线预览: {os.path.basename(fp)}")
                        else:
                            srv.log(f"↓ 手机下载文件: {os.path.basename(fp)} ({fmt_size(file_size)})")

                    with open(fp, 'rb') as f:
                        f.seek(start)
                        while length > 0:
                            chunk = f.read(min(65536, length))
                            if not chunk: break
                            self.wfile.write(chunk)
                            length -= len(chunk)

                except Exception:
                    pass

            def _batch_zip(self, body):
                try:
                    data = json.loads(body)
                    paths = data.get('paths', [])
                    # 取消 2GB 限制，直接传
                    zip_buffer = io.BytesIO()
                    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
                        for p in paths:
                            fp = srv._get_safe_path(p)
                            if fp and os.path.exists(fp):
                                if os.path.isfile(fp):
                                    zipf.write(fp, os.path.basename(fp))
                                elif os.path.isdir(fp):
                                    for root, _, files in os.walk(fp):
                                        for f in files:
                                            full_path = os.path.join(root, f)
                                            arcname = os.path.relpath(full_path, srv.root_dir)
                                            zipf.write(full_path, arcname)
                    zip_data = zip_buffer.getvalue()
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/zip')
                    self.send_header('Content-Disposition', 'attachment; filename="LANShare_Batch.zip"')
                    self.send_header('Content-Length', str(len(zip_data)))
                    self.send_header('Connection', 'close')
                    self.end_headers()
                    srv.log(f"↓ 手机打包下载 {len(paths)} 个文件")
                    self.wfile.write(zip_data)
                except Exception:
                    self.send_error(500)

            def _delete_files(self, body):
                try:
                    data = json.loads(body)
                    paths = data.get('paths', [])
                    for p in paths:
                        fp = srv._get_safe_path(p)
                        if fp and os.path.exists(fp):
                            if os.path.isfile(fp):
                                os.remove(fp)
                            elif os.path.isdir(fp):
                                shutil.rmtree(fp)
                    self.send_response(200)
                    self.send_header('Connection', 'close')
                    self.end_headers()
                    srv.log(f"🗑 手机端删除了 {len(paths)} 个文件/文件夹")
                except Exception:
                    self.send_error(500)

            def _chat_send(self, body):
                try:
                    data = json.loads(body)
                    srv.broadcast({'type': 'chat', 'content': data.get('content'), 'msgType': data.get('type')})
                    self.send_response(200)
                    self.send_header('Connection', 'close')
                    self.end_headers()
                except Exception:
                    self.send_error(500)

            def _recv_file(self, query):
                try:
                    q = urllib.parse.parse_qs(query)
                    req_path = q.get('path', [''])[0] if q.get('is_chat', ['0'])[0] == '0' else ''
                    name = urllib.parse.unquote(q.get('name', ['upload.bin'])[0]).replace('\\', '/').strip('/')

                    if '..' in name:
                        self.send_error(403)
                        return

                    target_dir = srv._get_safe_path(req_path)
                    if not target_dir or not os.path.isdir(target_dir):
                        self.send_error(403)
                        return

                    if '/' in name:
                        parts = name.split('/')
                        filename = parts[-1]
                        subdir = '/'.join(parts[:-1])
                        target_dir = os.path.join(target_dir, subdir)
                        if not os.path.exists(target_dir):
                            os.makedirs(target_dir, exist_ok=True)
                        name = filename

                    chunk = int(q.get('chunk', ['0'])[0])
                    total = int(q.get('chunks', ['1'])[0])
                    file_id = q.get('fileId', ['temp'])[0]

                    if total > 1:
                        fp = os.path.join(target_dir, f".tmp_{file_id}.part")
                        mode = 'ab' if chunk > 0 else 'wb'
                    else:
                        base, ext = os.path.splitext(name)
                        fp = os.path.join(target_dir, name)
                        i = 1
                        while os.path.exists(fp):
                            name = f"{base}({i}){ext}"
                            fp = os.path.join(target_dir, name)
                            i += 1
                        mode = 'wb'
                    length = int(self.headers.get('Content-Length', 0))
                    with open(fp, mode) as f:
                        while length > 0:
                            buf = self.rfile.read(min(65536, length))
                            if not buf: break
                            f.write(buf)
                            length -= len(buf)
                    if chunk == total - 1 and total > 1:
                        final_fp = os.path.join(target_dir, name)
                        if os.path.exists(final_fp):
                            base, ext = os.path.splitext(final_fp)
                            final_fp = os.path.join(target_dir, f"{base}_new{ext}")
                        os.rename(fp, final_fp)

                    if chunk == total - 1:
                        if q.get('is_chat', ['0'])[0] == '1':
                            srv.log(f"＋ 收到手机聊天附件: {name}")
                        else:
                            srv.log(f"＋ 手机上传完毕: {name}")

                    res = json.dumps({'ok': True, 'name': name}).encode()
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Content-Length', str(len(res)))
                    self.send_header('Connection', 'close')
                    self.end_headers()
                    self.wfile.write(res)

                    if q.get('is_chat', ['0'])[0] == '1':
                        srv.broadcast({'type': 'refresh'})
                except Exception:
                    self.send_error(500)

        return Handler


class App:
    def __init__(self, pin):
        self.root = tk.Tk()
        self.root.title(f"{APP_DISPLAY_NAME} - by 斯蒂芬周")
        set_app_icon(self.root)
        self.root.configure(bg='#0f1115')

        w, h = 820, 700
        self.root.geometry(f"{w}x{h}")
        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.root.geometry(f"{w}x{h}+{x}+{y}")

        self.root.resizable(True, True)
        self.root.minsize(800, 600)

        self.root.protocol("WM_DELETE_WINDOW", self.hide_to_tray)

        cfg = load_config()
        custom_dir = cfg.get('share_dir')
        if custom_dir and os.path.isdir(custom_dir):
            self.share_dir = custom_dir
            self.is_temp_dir = False
        else:
            self.share_dir = tempfile.mkdtemp(prefix='lanshare_')
            self.is_temp_dir = True

        self.log_q = queue.Queue()

        self.clipboard_set_q = queue.Queue()
        self.clipboard_get_req = threading.Event()
        self.clipboard_get_res = ""

        self.server = ShareServer(self.share_dir, pin, self)
        self.server.log_cb = self.log_q.put
        self.url = ""
        self.current_ip = ""
        self.public_url = cfg.get('public_url', '')
        self.pin = pin
        self.tray_icon = None

        self._build_ui()
        self._start()
        self._poll()

        if HAS_TRAY:
            self._setup_tray()

    def _setup_tray(self):
        png_bytes = base64.b64decode(get_app_icon_data())
        pil_img = Image.open(io.BytesIO(png_bytes))
        menu = pystray.Menu(
            pystray.MenuItem('显示主界面', self._safe_show_window, default=True),
            pystray.MenuItem('退出程序', self._safe_real_quit)
        )
        self.tray_icon = pystray.Icon("LanShare", pil_img, APP_DISPLAY_NAME, menu)
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def _safe_show_window(self, icon=None, item=None):
        self.root.after(0, self.show_window)

    def _safe_real_quit(self, icon=None, item=None):
        self.root.after(0, self.real_quit)

    def show_window(self):
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def real_quit(self):
        if self.tray_icon:
            try:
                self.tray_icon.stop()
            except:
                pass
        self.server.stop()
        if self.is_temp_dir:
            try:
                shutil.rmtree(self.share_dir, ignore_errors=True)
            except Exception:
                pass
        self.root.quit()
        self.root.destroy()
        sys.exit(0)

    def hide_to_tray(self, quiet=False):
        if HAS_TRAY and self.tray_icon:
            self.root.withdraw()
            if not quiet:
                if sys.platform == 'darwin':
                    try:
                        cmd = f"osascript -e 'display notification \"程序已在后台稳定运行，点击右上角图标可恢复主界面。\" with title \"{APP_DISPLAY_NAME}\"'"
                        subprocess.run(cmd, shell=True)
                    except Exception:
                        pass
                else:
                    try:
                        self.tray_icon.notify(message="程序已在后台稳定运行，双击右下角图标可恢复主界面。",
                                              title=APP_DISPLAY_NAME)
                    except Exception:
                        pass
        else:
            self.root.iconify()
            if not quiet:
                messagebox.showinfo(APP_DISPLAY_NAME, "软件已最小化到任务栏。")

    def format_path(self, p):
        p = os.path.normpath(p)
        if len(p) <= 45: return p
        return p[:20] + " ... " + p[-20:]

    def _build_ui(self):
        outer = tk.Frame(self.root, bg='#0f1115')
        outer.pack(fill='both', expand=True, padx=18, pady=18)

        left = tk.Frame(outer, bg='#0f1115')
        left.pack(side='left', fill='y')

        tk.Label(left, text="手机扫码访问", bg='#0f1115', fg='#8a8f98', font=(FONT_FAMILY, 11)).pack(pady=(4, 10))
        self.qr_canvas = tk.Canvas(left, bg='white', highlightthickness=0, width=259, height=259)
        self.qr_canvas.pack()

        pin_frame = tk.Frame(left, bg='#1a1d24', highlightthickness=1, highlightbackground='#4f8cff')
        pin_frame.pack(pady=(10, 0), fill='x')
        tk.Label(pin_frame, text="安全连接 PIN 码", bg='#1a1d24', fg='#8a8f98', font=(FONT_FAMILY, 9)).pack(pady=(6, 0))
        tk.Label(pin_frame, text=self.pin, bg='#1a1d24', fg='#4f8cff', font=(MONO_FONT, 24, 'bold')).pack(pady=(0, 6))

        warn_frame = tk.Frame(left, bg='#2a1516', highlightthickness=1, highlightbackground='#e5534b')
        warn_frame.pack(pady=(12, 0), fill='x')
        tk.Label(warn_frame, text="⚠️ 扫码后需输入左侧 PIN 码", bg='#2a1516', fg='#e5534b',
                 font=(FONT_FAMILY, 9, 'bold')).pack(pady=(6, 2))
        tk.Label(warn_frame, text="若提示不安全，请点高级->继续前往\n微信/QQ扫码白屏？点右上角「浏览器打开」", bg='#2a1516',
                 fg='#c8ccd4', font=(FONT_FAMILY, 8)).pack(pady=(0, 6))

        tk.Label(left, text="同一 WiFi · 手机互传中转站", bg='#0f1115', fg='#555b66', font=(FONT_FAMILY, 9)).pack(
            pady=(8, 0))

        right = tk.Frame(outer, bg='#0f1115')
        right.pack(side='left', fill='both', expand=True, padx=(18, 0))

        tk.Label(right, text=APP_DISPLAY_NAME, bg='#0f1115', fg='#e8eaed', font=(FONT_FAMILY, 16, 'bold')).pack(
            anchor='w')

        self.auto_start_var = tk.BooleanVar(value=check_startup())
        cb = tk.Checkbutton(right, text="开机自动后台启动", variable=self.auto_start_var, command=self.toggle_startup,
                            bg='#0f1115', fg='#8a8f98', selectcolor='#1a1d24', activebackground='#0f1115',
                            activeforeground='#e8eaed', font=(FONT_FAMILY, 9))
        cb.pack(anchor='w', pady=(2, 12))

        card = tk.Frame(right, bg='#1a1d24', highlightthickness=1, highlightbackground='#2a2f38')
        card.pack(fill='x')
        inner = tk.Frame(card, bg='#1a1d24')
        inner.pack(fill='x', padx=14, pady=12)

        ip_row = tk.Frame(inner, bg='#1a1d24')
        ip_row.pack(fill='x')
        tk.Label(ip_row, text="本机局域网 IP", bg='#1a1d24', fg='#8a8f98', font=(FONT_FAMILY, 9)).pack(side='left')

        self.ips = get_all_ips()
        self.ip_var = tk.StringVar(value=self.ips[0] if self.ips else '')
        self.ip_combo = ttk.Combobox(ip_row, textvariable=self.ip_var, values=self.ips, state='readonly', width=18)
        self.ip_combo.pack(side='right')
        self.ip_combo.bind("<<ComboboxSelected>>", self._on_ip_change)

        self.url_label = tk.Label(inner, text="正在启动…", bg='#1a1d24', fg='#4f8cff', font=(MONO_FONT, 14, 'bold'))
        self.url_label.pack(anchor='w', pady=(4, 8))

        pub_row = tk.Frame(inner, bg='#1a1d24')
        pub_row.pack(fill='x', pady=(0, 8))
        tk.Label(pub_row, text="外网地址(可选)", bg='#1a1d24', fg='#8a8f98', font=(FONT_FAMILY, 9)).pack(side='left')
        self.pub_var = tk.StringVar(value=self.public_url)
        pub_entry = tk.Entry(pub_row, textvariable=self.pub_var, bg='#22262e', fg='#e8eaed',
                             insertbackground='#e8eaed', relief='flat', font=(MONO_FONT, 10), width=32)
        pub_entry.pack(side='right', ipady=4, padx=(8, 0))
        pub_entry.bind('<Return>', self._on_pub_change)
        pub_entry.bind('<FocusOut>', self._on_pub_change)

        dir_frame = tk.Frame(inner, bg='#1a1d24')
        dir_frame.pack(fill='x', pady=(0, 12))
        tk.Label(dir_frame, text="共享目录", bg='#1a1d24', fg='#8a8f98', font=(FONT_FAMILY, 9)).pack(side='left')
        self.dir_label = tk.Label(dir_frame, text=self.format_path(self.share_dir), bg='#1a1d24', fg='#c8ccd4',
                                  font=(MONO_FONT, 9), anchor='w')
        self.dir_label.pack(side='left', fill='x', expand=True, padx=(8, 8))
        tk.Button(dir_frame, text="更改", command=self.change_dir, bg='#22262e', fg='#c8ccd4',
                  activebackground='#2a2f38', activeforeground='white', relief='flat', bd=0, padx=8, pady=2,
                  font=(FONT_FAMILY, 9), cursor='hand2').pack(side='right')

        btns = tk.Frame(inner, bg='#1a1d24')
        btns.pack(fill='x')
        self._btn(btns, "＋ 添加文件", self.add_files, '#4f8cff')
        self._btn(btns, "打开文件夹", self.open_folder, '#2a2f38')
        self._btn(btns, "隐藏到托盘", self.hide_to_tray, '#e5534b')

        # 加入检测更新和反馈按钮
        tk.Button(btns, text="检测更新", command=self.check_update, bg='#1a1d24', fg='#8a8f98',
                  activebackground='#2a2f38', activeforeground='white', relief='flat', bd=0,
                  font=(FONT_FAMILY, 9), cursor='hand2').pack(side='right', padx=(10, 0))

        tk.Button(btns, text="Bug反馈", command=self.send_feedback, bg='#1a1d24', fg='#8a8f98',
                  activebackground='#2a2f38', activeforeground='white', relief='flat', bd=0,
                  font=(FONT_FAMILY, 9), cursor='hand2').pack(side='right')

        log_frame = tk.Frame(right, bg='#0f1115')
        log_frame.pack(fill='both', expand=True, pady=(14, 0))
        tk.Label(log_frame, text="操作日志", bg='#0f1115', fg='#8a8f98', font=(FONT_FAMILY, 9)).pack(anchor='w')
        self.log_text = tk.Text(log_frame, bg='#1a1d24', fg='#c8ccd4', insertbackground='#c8ccd4', relief='flat',
                                font=(MONO_FONT, 10), wrap='word', highlightthickness=1, highlightbackground='#2a2f38')
        self.log_text.pack(fill='both', expand=True, pady=(6, 0))
        self.log_text.config(state='disabled')

    def toggle_startup(self):
        if self.auto_start_var.get():
            add_to_startup()
        else:
            remove_from_startup()

    def _btn(self, parent, text, cmd, color):
        b = tk.Button(parent, text=text, command=cmd, bg=color, fg='white', activebackground=color,
                      activeforeground='white', relief='flat', bd=0, padx=12, pady=6,
                      font=(FONT_FAMILY, 9), cursor='hand2')
        b.pack(side='left', padx=(0, 8))
        return b

    def _start(self):
        try:
            port = self.server.start()
            if not add_firewall_rule(port):
                self.push("⚠️ 警告：自动放行防火墙失败！请右键以【管理员身份】重新运行软件。")
        except Exception as e:
            messagebox.showerror("启动失败", str(e))
            self.root.destroy()
            return

        self._update_url_and_qr()
        self.push(f"服务已启动，监听端口 {port}")
        self.push(f"安全 PIN: {self.pin}")

    def _on_ip_change(self, event=None):
        self._update_url_and_qr()

    def _on_pub_change(self, event=None):
        new_pub = self.pub_var.get().strip()
        if new_pub != self.public_url:
            self.public_url = new_pub
            cfg = load_config()
            cfg['public_url'] = self.public_url
            save_config(cfg)
            self._update_url_and_qr()

    def _update_url_and_qr(self):
        if self.public_url:
            url = self.public_url if self.public_url.startswith('http') else 'http://' + self.public_url
            self.url = url
            self.url_label.config(text=f"{self.url} (外网)", fg='#3ecf8e')
            self._draw_qr(self.url)
            return

        ip = self.ip_var.get()
        self.url = f"http://{ip}:{self.server.port}/"
        self.url_label.config(text=self.url, fg='#4f8cff')
        self._draw_qr(self.url)

    def _draw_qr(self, url):
        try:
            qr = QR(url)
        except Exception:
            return
        size, pad = 7, 4
        total = (qr.size + 2 * pad) * size
        self.qr_canvas.config(width=total, height=total)
        self.qr_canvas.delete('all')
        for r in range(qr.size):
            for c in range(qr.size):
                if qr.m[r][c]:
                    x = (c + pad) * size
                    y = (r + pad) * size
                    self.qr_canvas.create_rectangle(x, y, x + size, y + size, fill='#000', outline='')

    def push(self, msg):
        self.log_q.put(msg)

    def _poll(self):
        try:
            while True:
                msg = self.log_q.get_nowait()
                ts = time.strftime('%H:%M:%S')
                self.log_text.config(state='normal')
                self.log_text.insert('end', f"[{ts}] {msg}\n")
                self.log_text.see('end')
                self.log_text.config(state='disabled')
        except queue.Empty:
            pass

        try:
            text = self.clipboard_set_q.get_nowait()
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self.push("📋 手机端内容已同步到电脑剪贴板")
        except queue.Empty:
            pass

        if self.clipboard_get_req.is_set():
            try:
                self.clipboard_get_res = self.root.clipboard_get()
            except Exception:
                self.clipboard_get_res = ""
            self.clipboard_get_req.clear()

        self.root.after(250, self._poll)

    def check_update(self):
        def _task():
            try:
                req = urllib.request.Request(UPDATE_CHECK_URL, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=5) as r:
                    data = json.loads(r.read().decode())
                    latest = data.get("version")
                    url = data.get("url")
                    if latest and latest != APP_VERSION:
                        if messagebox.askyesno("发现新版本",
                                               f"检测到新版本 {latest}，当前版本 {APP_VERSION}。\n是否前往下载？"):
                            webbrowser.open(url)
                    else:
                        messagebox.showinfo("检查更新", "当前已是最新版本！")
            except Exception as e:
                messagebox.showerror("检查更新", f"检查失败，请检查您的网络或配置的链接。\n{e}")

        threading.Thread(target=_task, daemon=True).start()

    def send_feedback(self):
        subject = urllib.parse.quote(f"局域网快传Bug反馈 - {APP_VERSION}")
        body = urllib.parse.quote(
            f"请描述您遇到的问题：\n\n\n\n==============\n系统版本：{sys.platform}\n软件版本：{APP_VERSION}")
        url = f"mailto:{AUTHOR_EMAIL}?subject={subject}&body={body}"
        webbrowser.open(url)
        self.push("已拉起邮件客户端，请发送反馈。")

    def show_help(self):
        win = tk.Toplevel(self.root)
        win.title("外网访问与排错帮助")
        w, h = 420, 340
        win.geometry(f"{w}x{h}")
        self.root.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - w) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - h) // 2
        win.geometry(f"+{x}+{y}")

        win.configure(bg='#1a1d24')
        win.resizable(False, False)
        win.transient(self.root)
        win.grab_set()
        win.lift()
        win.focus_force()
        set_app_icon(win)

        msg = (
            "【常见问题速查】\n"
            "1. 网络检查：确保手机和电脑连接的是同一个 WiFi。\n"
            "2. 权限拦截：请右键软件选择【以管理员身份运行】。\n"
            "3. 代理冲突：关闭 Clash、V2Ray 等代理软件。\n"
            "4. 微信/QQ扫码白屏：请点右上角“在浏览器中打开”。\n"
            "5. 局域网隔离：公司/学校网络可能禁止互访，请用手机开热点。\n\n"
            "如需查看【完整的保姆级排错指南】和【外网访问教程】，\n"
            "请点击下方按钮查看详细说明文档。"
        )
        tk.Label(win, text=msg, justify='left', bg='#1a1d24', fg='#c8ccd4',
                 font=(FONT_FAMILY, 10), wraplength=380).pack(padx=20, pady=(20, 10))

        btn_frame = tk.Frame(win, bg='#1a1d24')
        btn_frame.pack(pady=10)

        def open_readme():
            try:
                if sys.platform == 'win32':
                    os.startfile(README_FILE)
                elif sys.platform == 'darwin':
                    subprocess.Popen(['open', README_FILE])
                else:
                    subprocess.Popen(['xdg-open', README_FILE])
            except Exception as e:
                messagebox.showerror("错误", f"无法打开说明文档: {e}")

        tk.Button(btn_frame, text="打开详细说明文档", command=open_readme, bg='#4f8cff', fg='white',
                  activebackground='#3a75e0', activeforeground='white', relief='flat', padx=20, pady=6,
                  cursor='hand2', font=(FONT_FAMILY, 9)).pack(side='left', padx=10)

        tk.Button(btn_frame, text="关闭", command=win.destroy, bg='#22262e', fg='white',
                  activebackground='#2a2f38', activeforeground='white', relief='flat', padx=20, pady=6,
                  cursor='hand2', font=(FONT_FAMILY, 9)).pack(side='left', padx=10)

    def show_about(self):
        win = tk.Toplevel(self.root)
        win.title("关于")
        w, h = 360, 320
        win.geometry(f"{w}x{h}")
        self.root.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - w) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - h) // 2
        win.geometry(f"+{x}+{y}")

        win.configure(bg='#1a1d24')
        win.resizable(False, False)
        win.transient(self.root)
        win.grab_set()
        win.lift()
        win.focus_force()
        set_app_icon(win)

        canvas = tk.Canvas(win, width=64, height=64, bg='#1a1d24', highlightthickness=0)
        canvas.pack(pady=(20, 10))
        img = tk.PhotoImage(data=get_app_icon_data())
        canvas.create_image(32, 32, image=img)
        canvas.image = img

        tk.Label(win, text=APP_DISPLAY_NAME, bg='#1a1d24', fg='#e8eaed', font=(FONT_FAMILY, 14, 'bold')).pack()
        tk.Label(win, text=f"版本 {APP_VERSION}", bg='#1a1d24', fg='#8a8f98', font=(FONT_FAMILY, 9)).pack(pady=(2, 12))
        tk.Label(win, text="原创作者：by 斯蒂芬周", bg='#1a1d24', fg='#4f8cff', font=(FONT_FAMILY, 12, 'bold')).pack(
            pady=(0, 16))
        tk.Label(win, text="纯本地极速互传 · 不经过外网服务器\n单文件绿色版 · 数据绝对安全",
                 bg='#1a1d24', fg='#c8ccd4', justify='center', font=(FONT_FAMILY, 9)).pack()

        tk.Button(win, text="关闭", command=win.destroy, bg='#22262e', fg='white',
                  activebackground='#2a2f38', activeforeground='white', relief='flat',
                  padx=30, pady=6, cursor='hand2', font=(FONT_FAMILY, 9)).pack(pady=(24, 10))

    def change_dir(self):
        new_dir = filedialog.askdirectory(title="选择共享目录", initialdir=self.share_dir)
        if new_dir:
            new_dir = os.path.normpath(new_dir)
            if new_dir == os.path.normpath(self.share_dir): return
            self.share_dir = new_dir
            self.is_temp_dir = False
            self.server.root_dir = os.path.normpath(os.path.abspath(new_dir))
            self.dir_label.config(text=self.format_path(self.share_dir))
            self.push(f"共享目录已切换: {self.share_dir}")
            cfg = load_config()
            cfg['share_dir'] = self.share_dir
            save_config(cfg)

    def add_files(self):
        files = filedialog.askopenfilenames(title="选择要共享的文件")
        for f in files:
            try:
                dst = os.path.join(self.share_dir, os.path.basename(f))
                if os.path.exists(dst):
                    base, ext = os.path.splitext(os.path.basename(f))
                    i = 1
                    while os.path.exists(dst):
                        dst = os.path.join(self.share_dir, f"{base}({i}){ext}")
                        i += 1
                shutil.copy2(f, dst)
                self.push(f"＋ 已共享: {os.path.basename(dst)}")
            except Exception as e:
                self.push(f"× 复制失败: {e}")

    def open_folder(self):
        try:
            if sys.platform == 'win32':
                os.startfile(self.share_dir)
            elif sys.platform == 'darwin':
                subprocess.Popen(['open', self.share_dir])
            else:
                subprocess.Popen(['xdg-open', self.share_dir])
        except Exception as e:
            self.push(f"× 打开文件夹失败: {e}")


def main():
    if tk is None: return
    register_app_id()
    generate_readme()
    if not getattr(sys, 'frozen', False):
        generate_ico_file()
    clean_old_temp_dirs()

    is_auto_start = "--auto-start" in sys.argv
    pin_code = "".join([str(random.randint(0, 9)) for _ in range(4)])

    try:
        app = App(pin_code)
        if is_auto_start:
            app.hide_to_tray(quiet=True)
            app.push("自启成功，已隐藏到系统托盘后台运行。")
        app.root.mainloop()
    except KeyboardInterrupt:
        print("\n软件已强行中断。")
        try:
            app.real_quit()
        except Exception:
            pass
        sys.exit(0)


if __name__ == '__main__':
    main()