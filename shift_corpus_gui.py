#!/usr/bin/env python3
"""ShiftCorpus Desktop: Tkinter frontend for the original Arctic Shift collector.
Standard-library only. No collection engine logic is changed here.
"""
from __future__ import annotations

import json
import os
import queue
import re
import shlex
import platform
import subprocess
import sys
import threading
import urllib.error
import urllib.request
from datetime import datetime, date, timedelta
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext

ROOT = Path(__file__).resolve().parent
ENGINE = ROOT / "shift_corpus_engine.py"
API_TEST_URL = "https://arctic-shift.photon-reddit.com/api/comments/search?subreddit=politics&limit=1"

def user_output_dir() -> Path:
    """Put generated corpora in a user-writable location on every OS."""
    documents = Path.home() / 'Documents'
    base = documents if documents.is_dir() else Path.home()
    return base / 'ShiftCorpus_Output'


def command_preview(args: list[str]) -> str:
    """Display native shell-oriented quoting without affecting subprocess argv."""
    return subprocess.list2cmdline(args) if os.name == 'nt' else shlex.join(args)


def mono_font() -> str:
    if sys.platform == 'darwin':
        return 'Menlo'
    if os.name == 'nt':
        return 'Consolas'
    return 'DejaVu Sans Mono'


def ui_font() -> str:
    if sys.platform == 'darwin':
        return 'Helvetica Neue'
    if os.name == 'nt':
        return 'Segoe UI'
    return 'DejaVu Sans'


BG = '#f6f8fb'
WHITE = '#ffffff'
INK = '#17253a'
MUTED = '#64748b'
ACCENT = '#1266c3'
BORDER = '#dce3ec'



ERROR_EN = {
    '日期格式必须是 YYYY-MM-DD，例如 2022-05-01': 'Date format must be YYYY-MM-DD, for example 2022-05-01',
    '结束日期不能早于开始日期': 'End date cannot precede start date',
    'Subreddit只能包含字母、数字或下划线': 'Subreddit may contain only letters, digits, or underscores',
    '天数、配额、Seed、最少词数均须为整数': 'Days, quota, seed and minimum word count must be integers',
    '参数超出范围：窗口1–3650天、配额1–20000、Seed非负、最低词数0–10000': 'Out of range: window 1–3650 days, quota 1–20000, nonnegative seed, min words 0–10000',
    '请选择输出文件夹': 'Choose an output folder',
    '最后窗口策略必须为proportional或full': 'Partial-window policy must be proportional or full',
    '单窗口格式应为 YYYY-MM-DD_YYYY-MM-DD': 'Single-window ID must use YYYY-MM-DD_YYYY-MM-DD',
}


# UI strings only; subprocess output remains verbatim for reproducibility.
I18N = {
    'zh': {
        'window_title': 'ShiftCorpus · Reddit 语料采集器',
        'subtitle': 'Arctic Shift 研究语料采集 · 可视化参数、连接诊断和实时进度',
        'language': '语言 / Language', 'range': '采集范围与抽样', 'filters': '清洗与输出',
        'subreddit': 'Subreddit', 'seed': '随机种子 Seed', 'after': '开始日期（含）',
        'before': '结束日期（含）', 'period_days': '窗口长度（天）',
        'sample_per_period': '每完整窗口评论数', 'min_words': '最少词数',
        'partial_policy': '最后不足窗口', 'only_period': '仅采集指定窗口（可留空）',
        'only_hint': '例如 2022-05-01_2022-10-27，适用于快速复测 pilot',
        'english': '仅保留英文评论', 'exclude_bots': '过滤已知 Bot 账号',
        'exclude_nsfw': '过滤 NSFW 标记', 'near_dup': '去掉近重复文本',
        'with_posts': '保存关联帖子标题作为上下文（不计入词频）',
        'output_folder': '输出文件夹', 'browse': '浏览…',
        'output_hint': '自动生成 AntConc TXT、索引、CSV、JSONL、query.json',
        'command': '即将执行的命令', 'copy': '复制命令', 'start': '▶  开始采集',
        'stop': '■  停止', 'test': '测试 API 连接', 'open_folder': '打开输出文件夹',
        'progress': '运行进度', 'logs': '实时日志与诊断信息', 'clear': '清空日志',
        'ready': '就绪 · 等待开始', 'not_started': '尚未开始',
        'estimated': '预计 {windows} 个窗口 · 覆盖 {days} 天 · 计划采样 {target} 条评论（实际取决于 API）',
        'invalid_params': '⚠ 参数待修正：{error}', 'check_params': '请检查上方参数',
        'copied': '命令已复制到剪贴板。', 'select_folder': '选择语料输出文件夹',
        'bad_params': '采集参数有误', 'missing_engine': '缺少程序文件',
        'missing_engine_msg': '找不到采集核心：\n{engine}', 'cannot_create': '无法创建输出文件夹',
        'launch': '启动采集：{time}', 'launch_error': '程序无法启动：{error}',
        'collecting': '正在采集', 'read_error': '日志读取错误：{error}',
        'current_window': '当前窗口：{window}',
        'progress_detail': '{done}/{total} 窗口 · 当前窗口第 {day}/{days} 天',
        'completed': '完成', 'finished': '采集完成。请检查输出文件夹。',
        'stopped': '已停止', 'stopped_msg': '用户停止了采集。',
        'failed': '失败（退出码 {code}）', 'failed_msg': '采集未正常完成；请查看上方具体 API 错误。',
        'stopping': '正在停止', 'stop_requested': '已请求终止采集进程…',
        'api_testing': 'API 诊断：正在连接 Arctic Shift…',
        'api_ok': 'API 连接成功：HTTP {status}{detail}',
        'valid_json': '；收到有效 JSON', 'bad_json_structure': '；收到响应，但 JSON 结构异常',
        'invalid_json': '；返回内容不是有效 JSON',
        'api_http_error': 'API 服务器返回 HTTP {code}：{reason}',
        'api_failure': 'API 连接失败：{kind}: {error}',
        'close_title': '正在采集', 'close_prompt': '采集仍在运行。退出将停止采集，确定退出吗？',
        'argument_error': '输入参数无效：{error}',
    },
    'en': {
        'window_title': 'ShiftCorpus · Reddit Corpus Collector',
        'subtitle': 'Arctic Shift research collector · Settings, connection diagnostics, and live progress',
        'language': 'Language / 语言', 'range': 'Collection & sampling', 'filters': 'Filters & export',
        'subreddit': 'Subreddit', 'seed': 'Random seed', 'after': 'Start date (inclusive)',
        'before': 'End date (inclusive)', 'period_days': 'Window length (days)',
        'sample_per_period': 'Comments per full window', 'min_words': 'Minimum words',
        'partial_policy': 'Partial-window policy', 'only_period': 'Single window (optional)',
        'only_hint': 'e.g. 2022-05-01_2022-10-27, to rerun the pilot',
        'english': 'English comments only', 'exclude_bots': 'Exclude known bots',
        'exclude_nsfw': 'Exclude NSFW content', 'near_dup': 'Remove near duplicates',
        'with_posts': 'Save parent post titles as context (excluded from frequency counts)',
        'output_folder': 'Output folder', 'browse': 'Browse…',
        'output_hint': 'Exports AntConc TXT, index, CSV, JSONL, and query.json',
        'command': 'Command preview', 'copy': 'Copy command', 'start': '▶  Start collection',
        'stop': '■  Stop', 'test': 'Test API connection', 'open_folder': 'Open output folder',
        'progress': 'Collection progress', 'logs': 'Live log & diagnostics', 'clear': 'Clear log',
        'ready': 'Ready · Waiting to start', 'not_started': 'Not started',
        'estimated': 'Est. {windows} windows · {days} days · target {target} comments (subject to API availability)',
        'invalid_params': '⚠ Fix parameters: {error}', 'check_params': 'Please check the settings above',
        'copied': 'Command copied to clipboard.', 'select_folder': 'Choose corpus output folder',
        'bad_params': 'Invalid collection parameters', 'missing_engine': 'Missing engine',
        'missing_engine_msg': 'Cannot find the collector engine:\n{engine}',
        'cannot_create': 'Cannot create output folder', 'launch': 'Collection started: {time}',
        'launch_error': 'Unable to launch process: {error}', 'collecting': 'Collecting',
        'read_error': 'Log reader error: {error}', 'current_window': 'Current window: {window}',
        'progress_detail': '{done}/{total} windows · day {day}/{days} of current window',
        'completed': 'Complete', 'finished': 'Collection finished. Check the output folder.',
        'stopped': 'Stopped', 'stopped_msg': 'Collection stopped by user.',
        'failed': 'Failed (exit code {code})', 'failed_msg': 'Collection did not finish; see API errors above.',
        'stopping': 'Stopping', 'stop_requested': 'Termination requested…',
        'api_testing': 'API diagnostic: connecting to Arctic Shift…',
        'api_ok': 'API connection successful: HTTP {status}{detail}',
        'valid_json': '; valid JSON received', 'bad_json_structure': '; unusual JSON structure',
        'invalid_json': '; response was not valid JSON',
        'api_http_error': 'API returned HTTP {code}: {reason}',
        'api_failure': 'API connection failed: {kind}: {error}',
        'close_title': 'Collection in progress', 'close_prompt': 'Collection is still running. Exit and stop collection?',
        'argument_error': 'Invalid arguments: {error}',
    },
}

UA = 'ShiftCorpus-Research/1.0 (academic corpus collection)'


def check_dates(start: str, end: str) -> tuple[date, date]:
    try:
        a = date.fromisoformat(start.strip())
        b = date.fromisoformat(end.strip())
    except ValueError as exc:
        raise ValueError('日期格式必须是 YYYY-MM-DD，例如 2022-05-01') from exc
    if b < a:
        raise ValueError('结束日期不能早于开始日期')
    return a, b


def estimate_windows(start: str, end: str, period_days: int, quota: int, policy: str):
    a, b = check_dates(start, end)
    total = (b - a).days + 1
    full, remainder = divmod(total, period_days)
    windows = full + bool(remainder)
    target = full * quota
    if remainder:
        target += max(1, round(quota * remainder / period_days)) if policy == 'proportional' else quota
    return windows, target, total


def make_command(v: dict[str, object], engine: Path = ENGINE) -> list[str]:
    subreddit = str(v['subreddit']).strip().removeprefix('r/')
    if not re.fullmatch(r'[A-Za-z0-9_]{2,50}', subreddit):
        raise ValueError('Subreddit只能包含字母、数字或下划线')
    a, b = check_dates(str(v['after']), str(v['before']))
    try:
        days = int(v['period_days'])
        count = int(v['sample_per_period'])
        seed = int(v['seed'])
        min_words = int(v['min_words'])
    except (TypeError, ValueError) as exc:
        raise ValueError('天数、配额、Seed、最少词数均须为整数') from exc
    if not 1 <= days <= 3650 or not 1 <= count <= 20000 or seed < 0 or not 0 <= min_words <= 10000:
        raise ValueError('参数超出范围：窗口1–3650天、配额1–20000、Seed非负、最低词数0–10000')
    out = str(v['out']).strip()
    if not out:
        raise ValueError('请选择输出文件夹')
    policy = str(v['partial_policy'])
    if policy not in ('proportional', 'full'):
        raise ValueError('最后窗口策略必须为proportional或full')
    cmd = [sys.executable, '-u', str(engine), '--subreddit', subreddit,
           '--after', a.isoformat(), '--before', b.isoformat(), '--half',
           '--period-days', str(days), '--stratified-sample',
           '--sample-per-period', str(count), '--partial-policy', policy,
           '--min-words', str(min_words), '--seed', str(seed), '--out', out]
    for key, flag in [
        ('english', '--english'), ('exclude_bots', '--exclude-bots'),
        ('exclude_nsfw', '--exclude-nsfw'), ('near_dup', '--near-dup'),
        ('with_posts', '--with-posts')
    ]:
        if v.get(key):
            cmd.append(flag)
    only = str(v.get('only_period') or '').strip()
    if only:
        # Must correspond to the window's ID, e.g. 2022-05-01_2022-10-27.
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}_\d{4}-\d{2}-\d{2}', only):
            raise ValueError('单窗口格式应为 YYYY-MM-DD_YYYY-MM-DD')
        cmd.extend(['--only-period', only])
    return cmd


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.language = tk.StringVar(value='zh')
        self.language_choice = tk.StringVar(value='中文')
        self.title(self.t('window_title'))
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        self.geometry(f'{min(1120, max(780, screen_w - 80))}x{min(820, max(620, screen_h - 100))}')
        self.minsize(min(900, max(780, screen_w - 80)), min(690, max(600, screen_h - 100)))
        self.configure(bg=BG)
        self.queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self.proc: subprocess.Popen | None = None
        self.test_busy = False
        self.stopping = False
        self.window_target = 0
        self.window_completed = 0
        self.day_progress = 0
        self.active_days = 0
        self._style()
        self._variables()
        self._layout()
        for variable in self.vars.values():
            variable.trace_add('write', lambda *_: self._update_preview())
        self._update_preview()
        self.after(120, self._poll)
        self.protocol('WM_DELETE_WINDOW', self._close)

    def error(self, error):
        raw = str(error)
        return ERROR_EN.get(raw, raw) if self.language.get() == 'en' else raw

    def t(self, key: str, **kwargs):
        value = I18N[self.language.get()][key]
        return value.format(**kwargs) if kwargs else value

    def _set_language(self, _event=None):
        self.language.set('en' if self.language_choice.get() == 'English' else 'zh')
        # Rebuild only presentation elements; keep all parameters, process and logs.
        old_logs = self.logs.get('1.0', 'end-1c') if hasattr(self, 'logs') else ''
        old_progress = self.progress['value'] if hasattr(self, 'progress') else 0
        running = self.proc is not None and self.proc.poll() is None
        old_status = getattr(self, 'status_key', 'collecting' if running else 'ready')
        if hasattr(self, 'outer'):
            self.outer.destroy()
        self.title(self.t('window_title'))
        self._layout()
        self.progress.configure(value=old_progress)
        if old_logs:
            self._log(old_logs)
        self.start_button.configure(state='disabled' if running else 'normal')
        self.stop_button.configure(state='normal' if running else 'disabled')
        self.test_button.configure(state='disabled' if self.test_busy else 'normal')
        self.status.set(self.t(old_status, **getattr(self, 'status_args', {})) if old_status in I18N[self.language.get()] else old_status)
        if self.current_window.get() not in (I18N['zh']['not_started'], I18N['en']['not_started']):
            label = self.current_window.get().split(':', 1)[-1].replace('当前窗口：', '').strip()
            self.current_window.set(self.t('current_window', window=label))
        else:
            self.current_window.set(self.t('not_started'))
        self._update_preview()

    def _status(self, key: str, **kwargs):
        self.status_key = key
        self.status_args = kwargs
        self.status.set(self.t(key, **kwargs))

    def _style(self):
        st = ttk.Style(self)
        main_font = ui_font()
        st.theme_use('clam')
        st.configure('TFrame', background=BG)
        st.configure('White.TFrame', background=WHITE)
        st.configure('TLabel', background=BG, foreground=INK, font=(main_font, 11))
        st.configure('Muted.TLabel', background=BG, foreground=MUTED, font=(main_font, 10))
        st.configure('White.TLabel', background=WHITE, foreground=INK, font=(main_font, 10))
        st.configure('WhiteMuted.TLabel', background=WHITE, foreground=MUTED, font=(main_font, 10))
        st.configure('Heading.TLabel', background=BG, foreground=INK, font=(main_font, 22, 'bold'))
        st.configure('Subhead.TLabel', background=BG, foreground=INK, font=(main_font, 12, 'bold'))
        st.configure('TEntry', padding=6)
        st.configure('TCombobox', padding=5)
        st.configure('TCheckbutton', background=WHITE, foreground=INK, font=(main_font, 10))
        st.map('TCheckbutton', background=[('active', WHITE)])
        st.configure('Primary.TButton', background=ACCENT, foreground='white', padding=(17, 9), font=(main_font, 11, 'bold'))
        st.map('Primary.TButton', background=[('active', '#0e55a4'), ('disabled', '#a2b3c6')])
        st.configure('Secondary.TButton', padding=(12, 8), font=(main_font, 10))
        st.configure('TNotebook', background=BG, borderwidth=0)
        st.configure('TNotebook.Tab', padding=(20, 10), font=(main_font, 10))
        st.configure('Horizontal.TProgressbar', troughcolor='#e5ebf4', background=ACCENT, borderwidth=0)

    def _variables(self):
        defaults = dict(subreddit='politics', after='2022-05-01', before='2026-11-20',
                        period_days='180', sample_per_period='180', seed='1', min_words='5',
                        partial_policy='proportional', only_period='',
                        out=str(user_output_dir()))
        self.vars: dict[str, tk.Variable] = {k: tk.StringVar(value=v) for k,v in defaults.items()}
        for k in ['english', 'exclude_bots', 'exclude_nsfw', 'near_dup', 'with_posts']:
            self.vars[k] = tk.BooleanVar(value=True)
        self.status_key = 'ready'
        self.status_args = {}
        self.status = tk.StringVar(value=self.t('ready'))
        self.summary = tk.StringVar(value='')
        self.current_window = tk.StringVar(value=self.t('not_started'))
        self.progress_label = tk.StringVar(value='—')

    def _layout(self):
        outer = ttk.Frame(self, padding=(28, 22, 28, 18))
        self.outer = outer
        outer.pack(fill='both', expand=True)
        top = ttk.Frame(outer)
        top.pack(fill='x')
        ttk.Label(top, text='ShiftCorpus', style='Heading.TLabel').pack(side='left')
        self.lang_combo = ttk.Combobox(top, textvariable=self.language_choice, values=['中文', 'English'], width=9, state='readonly')
        self.lang_combo.pack(side='right')
        self.lang_combo.bind('<<ComboboxSelected>>', self._set_language)
        ttk.Label(top, text=self.t('language'), style='Muted.TLabel').pack(side='right', padx=(0, 8))
        ttk.Label(outer, text=self.t('subtitle'), style='Muted.TLabel').pack(anchor='w', pady=(1, 14))

        controls = ttk.Frame(outer)
        controls.pack(fill='x')
        left = tk.Frame(controls, bg=WHITE, highlightbackground=BORDER, highlightthickness=1)
        left.pack(side='left', fill='both', expand=True, padx=(0, 10))
        right = tk.Frame(controls, bg=WHITE, highlightbackground=BORDER, highlightthickness=1)
        right.pack(side='left', fill='both', expand=True)
        self._left(left)
        self._right(right)

        command_header = ttk.Frame(outer)
        command_header.pack(fill='x', pady=(16, 5))
        ttk.Label(command_header, text=self.t('command'), style='Subhead.TLabel').pack(side='left')
        ttk.Button(command_header, text=self.t('copy'), command=self._copy_command).pack(side='right')
        self.command_text = tk.Text(outer, height=3, bg='#eaf0f8', fg=INK,
                                     font=(mono_font(), 10), wrap='word', relief='flat', padx=12, pady=9)
        self.command_text.pack(fill='x')
        self.command_text.configure(state='disabled')
        self.summary_view = ttk.Label(outer, textvariable=self.summary, style='Muted.TLabel')
        self.summary_view.pack(anchor='w', pady=(5, 0))

        actions = ttk.Frame(outer)
        actions.pack(fill='x', pady=(12, 10))
        self.start_button = ttk.Button(actions, text=self.t('start'), style='Primary.TButton', command=self._start)
        self.start_button.pack(side='left')
        self.stop_button = ttk.Button(actions, text=self.t('stop'), command=self._stop, state='disabled')
        self.stop_button.pack(side='left', padx=8)
        self.test_button = ttk.Button(actions, text=self.t('test'), command=self._test_api)
        self.test_button.pack(side='left', padx=(2, 8))
        ttk.Button(actions, text=self.t('open_folder'), command=self._open_folder).pack(side='left')
        ttk.Label(actions, textvariable=self.status, style='Muted.TLabel').pack(side='right')

        ttk.Label(outer, text=self.t('progress'), style='Subhead.TLabel').pack(anchor='w', pady=(3, 5))
        self.progress = ttk.Progressbar(outer, mode='determinate', maximum=100)
        self.progress.pack(fill='x')
        status_row = ttk.Frame(outer)
        status_row.pack(fill='x', pady=(5, 5))
        ttk.Label(status_row, textvariable=self.current_window, style='Muted.TLabel').pack(side='left')
        ttk.Label(status_row, textvariable=self.progress_label, style='Muted.TLabel').pack(side='right')
        log_head = ttk.Frame(outer)
        log_head.pack(fill='x', pady=(8, 5))
        ttk.Label(log_head, text=self.t('logs'), style='Subhead.TLabel').pack(side='left')
        ttk.Button(log_head, text=self.t('clear'), command=self._clear_logs).pack(side='right')
        self.logs = scrolledtext.ScrolledText(outer, height=12, bg='#0f1c2e', fg='#d9e5f6',
                                              insertbackground='white', font=(mono_font(), 10),
                                              wrap='word', padx=12, pady=10, relief='flat', state='disabled')
        self.logs.pack(fill='both', expand=True)
        self.logs.tag_configure('warn', foreground='#ffca89')
        self.logs.tag_configure('error', foreground='#ff9b9b')
        self.logs.tag_configure('good', foreground='#a8e9c0')

    def _field(self, parent, label, key, row, col, width=18):
        cell = tk.Frame(parent, bg=WHITE)
        cell.grid(row=row, column=col, sticky='ew', padx=(0, 12), pady=6)
        ttk.Label(cell, text=label, style='WhiteMuted.TLabel').pack(anchor='w', pady=(0, 4))
        ttk.Entry(cell, textvariable=self.vars[key], width=width).pack(fill='x')

    def _left(self, frame):
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_columnconfigure(1, weight=1)
        ttk.Label(frame, text=self.t('range'), style='White.TLabel', font=(main_font, 12, 'bold')).grid(row=0, column=0, columnspan=2, sticky='w', padx=16, pady=(14, 6))
        inner = tk.Frame(frame, bg=WHITE)
        inner.grid(row=1, column=0, columnspan=2, sticky='nsew', padx=16)
        inner.grid_columnconfigure(0, weight=1)
        inner.grid_columnconfigure(1, weight=1)
        self._field(inner,self.t('subreddit'),'subreddit',0,0)
        self._field(inner,self.t('seed'),'seed',0,1)
        self._field(inner,self.t('after'),'after',1,0)
        self._field(inner,self.t('before'),'before',1,1)
        self._field(inner,self.t('period_days'),'period_days',2,0)
        self._field(inner,self.t('sample_per_period'),'sample_per_period',2,1)
        self._field(inner,self.t('min_words'),'min_words',3,0)
        box = tk.Frame(inner, bg=WHITE)
        box.grid(row=3, column=1, sticky='ew', padx=(0,12), pady=6)
        ttk.Label(box,text=self.t('partial_policy'),style='WhiteMuted.TLabel').pack(anchor='w',pady=(0,4))
        ttk.Combobox(box,textvariable=self.vars['partial_policy'],values=['proportional','full'],state='readonly',width=17).pack(fill='x')
        only = tk.Frame(frame,bg=WHITE)
        only.grid(row=2,column=0,columnspan=2,sticky='ew',padx=16,pady=(3,14))
        ttk.Label(only,text=self.t('only_period'),style='WhiteMuted.TLabel').pack(anchor='w',pady=(0,4))
        ttk.Entry(only,textvariable=self.vars['only_period']).pack(fill='x')
        ttk.Label(only,text=self.t('only_hint'),style='WhiteMuted.TLabel').pack(anchor='w',pady=(4,0))

    def _right(self, frame):
        ttk.Label(frame,text=self.t('filters'),style='White.TLabel',font=(main_font,12,'bold')).pack(anchor='w',padx=16,pady=(14,10))
        for key,text in [
            ('english',self.t('english')),
            ('exclude_bots',self.t('exclude_bots')),
            ('exclude_nsfw',self.t('exclude_nsfw')),
            ('near_dup',self.t('near_dup')),
            ('with_posts',self.t('with_posts'))
        ]:
            ttk.Checkbutton(frame,text=text,variable=self.vars[key]).pack(anchor='w',padx=16,pady=3)
        ttk.Label(frame,text=self.t('output_folder'),style='WhiteMuted.TLabel').pack(anchor='w',padx=16,pady=(16,5))
        pathrow = tk.Frame(frame,bg=WHITE)
        pathrow.pack(fill='x',padx=16)
        ttk.Entry(pathrow,textvariable=self.vars['out']).pack(side='left',fill='x',expand=True)
        ttk.Button(pathrow,text=self.t('browse'),command=self._browse).pack(side='left',padx=(7,0))
        ttk.Label(frame,text=self.t('output_hint'),style='WhiteMuted.TLabel',wraplength=400).pack(anchor='w',padx=16,pady=(10,10))

    def _values(self):
        return {k: var.get() for k,var in self.vars.items()}

    def _update_preview(self):
        try:
            values = self._values()
            cmd = make_command(values)
            text = command_preview(cmd)
            windows,target,days=estimate_windows(values['after'],values['before'],int(values['period_days']),int(values['sample_per_period']),values['partial_policy'])
            info=self.t('estimated', windows=windows, days=days, target=target)
        except (ValueError, KeyError) as exc:
            text=self.t('invalid_params', error=self.error(exc))
            info=self.t('check_params')
        self.command_text.configure(state='normal')
        self.command_text.delete('1.0','end')
        self.command_text.insert('1.0',text)
        self.command_text.configure(state='disabled')
        self.summary.set(info)

    def _copy_command(self):
        self.clipboard_clear()
        self.clipboard_append(self.command_text.get('1.0','end').strip())
        self._log(self.t('copied'),'good')

    def _browse(self):
        selected=filedialog.askdirectory(initialdir=str(ROOT),title=self.t('select_folder'))
        if selected: self.vars['out'].set(selected)

    def _log(self,text,tag=None):
        self.logs.configure(state='normal')
        self.logs.insert('end',str(text).rstrip()+'\n',tag)
        self.logs.see('end')
        self.logs.configure(state='disabled')

    def _clear_logs(self):
        self.logs.configure(state='normal');self.logs.delete('1.0','end');self.logs.configure(state='disabled')

    def _start(self):
        if self.proc and self.proc.poll() is None:
            return
        try:
            command=make_command(self._values())
        except ValueError as exc:
            messagebox.showerror(self.t('bad_params'),self.error(exc))
            return
        if not ENGINE.is_file():
            messagebox.showerror(self.t('missing_engine'),self.t('missing_engine_msg',engine=ENGINE))
            return
        dest=Path(str(self.vars['out'].get())).expanduser()
        try: dest.mkdir(parents=True,exist_ok=True)
        except OSError as exc:
            messagebox.showerror(self.t('cannot_create'),str(exc));return
        self.stopping=False
        self.window_completed=0;self.day_progress=0;self.active_days=0
        self.progress.configure(value=0)
        self._log('\n'+'='*57)
        self._log(self.t('launch',time=datetime.now().strftime('%Y-%m-%d %H:%M:%S')),'good')
        self._log(command_preview(command))
        try:
            env = os.environ.copy()
            env['PYTHONIOENCODING'] = 'utf-8'
            popen_kw = {}
            if os.name == 'nt':
                # Keep the GUI free of a second console window on Windows.
                popen_kw['creationflags'] = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
            self.proc=subprocess.Popen(command,cwd=str(ROOT),stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT,text=True,encoding='utf-8',
                           bufsize=1,errors='replace',env=env,**popen_kw)
        except OSError as exc:
            self._log(self.t('launch_error',error=exc),'error');return
        self._status('collecting')
        self.start_button.configure(state='disabled')
        self.stop_button.configure(state='normal')
        threading.Thread(target=self._read_output,args=(self.proc,),daemon=True).start()

    def _read_output(self,process):
        try:
            assert process.stdout is not None
            for line in process.stdout:
                self.queue.put(('line',line.rstrip('\r\n')))
        except Exception as exc:
            self.queue.put(('line',self.t('read_error',error=exc)))
        finally:
            code=process.wait()
            self.queue.put(('done',code))

    def _parse_progress(self,line):
        m=re.search(r'^period\s+(\d{4}-\d{2}-\d{2}_\d{4}-\d{2}-\d{2})',line)
        if m:
            self.window_completed+=1
            self.day_progress=0
            self.current_window.set(self.t('current_window',window=m.group(1)))
        m=re.search(r'^sample\s+\S+\s+seed=\d+\s+days=(\d+)\s+target=(\d+)',line)
        if m:
            self.active_days=int(m.group(1));self.window_target=int(m.group(2))
        m=re.search(r'^\s+\d{4}-\d{2}-\d{2} quota=\d+ kept=\d+',line)
        if m:
            self.day_progress+=1
        try:
            windows,_,_=estimate_windows(self.vars['after'].get(),self.vars['before'].get(),int(self.vars['period_days'].get()),int(self.vars['sample_per_period'].get()),str(self.vars['partial_policy'].get()))
            if self.vars['only_period'].get().strip():windows=1
            value=((self.window_completed-1)+self.day_progress/max(1,self.active_days))/max(1,windows)*100
            self.progress.configure(value=max(0,min(99.5,value)))
            self.progress_label.set(self.t('progress_detail',done=max(0,self.window_completed),total=windows,day=self.day_progress,days=self.active_days))
        except ValueError: pass

    def _poll(self):
        for _ in range(120):
            try: kind,payload=self.queue.get_nowait()
            except queue.Empty:break
            if kind=='line':
                line=str(payload)
                tag=('error' if any(x in line.lower() for x in ['error','traceback','api attempt','failed','连不上','无法解析'])
                     else 'warn' if any(x in line.lower() for x in ['warning','short=','timeout']) else None)
                self._log(line,tag)
                self._parse_progress(line)
            elif kind=='done':
                code=int(payload)
                if code==0:
                    self._status('completed');self.progress.configure(value=100)
                    self._log(self.t('finished'),'good')
                elif self.stopping:
                    self._status('stopped');self._log(self.t('stopped_msg'),'warn')
                else:
                    self._status('failed',code=code)
                    self._log(self.t('failed_msg'),'error')
                self.start_button.configure(state='normal')
                self.stop_button.configure(state='disabled')
                self.proc=None
            elif kind=='api':
                self.test_busy=False
                self.test_button.configure(state='normal')
                ok,text=str(payload[0]),str(payload[1])
                self._log(text,'good' if ok=='True' else 'error')
        self.after(120,self._poll)

    def _stop(self):
        if self.proc and self.proc.poll() is None:
            self.stopping=True
            self._status('stopping')
            self._log(self.t('stop_requested'),'warn')
            self.proc.terminate()

    def _test_api(self):
        if self.test_busy:return
        self.test_busy=True
        self.test_button.configure(state='disabled')
        self._log(self.t('api_testing'))
        threading.Thread(target=self._run_api_test,args=(self.language.get(),),daemon=True).start()

    def _run_api_test(self, lang='zh'):
        def tr(key, **kwargs):
            return I18N[lang][key].format(**kwargs)
        try:
            req=urllib.request.Request(API_TEST_URL,headers={'User-Agent':UA, 'Accept':'application/json'})
            with urllib.request.urlopen(req,timeout=15) as response:
                status=response.status
                snippet=response.read(1_000_000)
            try:
                data=json.loads(snippet)
                detail=tr('valid_json') if isinstance(data,(dict,list)) else '；收到响应，但JSON结构异常'
            except json.JSONDecodeError:
                detail=tr('invalid_json')
            self.queue.put(('api',(True,tr('api_ok',status=status,detail=detail))))
        except urllib.error.HTTPError as exc:
            self.queue.put(('api',(False,tr('api_http_error',code=exc.code,reason=exc.reason))))
        except Exception as exc:
            self.queue.put(('api',(False,tr('api_failure',kind=type(exc).__name__,error=exc))))

    def _open_folder(self):
        path=Path(self.vars['out'].get()).expanduser()
        path.mkdir(parents=True,exist_ok=True)
        try:
            if sys.platform == 'darwin':
                subprocess.Popen(['open', str(path)])
            elif sys.platform == 'win32':
                os.startfile(str(path))
            else:
                subprocess.Popen(['xdg-open', str(path)])
        except (OSError, FileNotFoundError) as exc:
            messagebox.showerror(self.t('cannot_create'), str(exc))

    def _close(self):
        if self.proc and self.proc.poll() is None:
            if not messagebox.askyesno(self.t('close_title'),self.t('close_prompt')):return
            self.proc.terminate()
        self.destroy()


if __name__=='__main__':
    try: App().mainloop()
    except tk.TclError as exc:
        print(f'Unable to start the Tkinter graphical interface / 无法启动图形界面: {exc}\nInstall Python 3.10+ with Tk support and run in a graphical desktop session.',file=sys.stderr)
        raise SystemExit(1)
