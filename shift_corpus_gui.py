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

BG = '#f6f8fb'
WHITE = '#ffffff'
INK = '#17253a'
MUTED = '#64748b'
ACCENT = '#1266c3'
BORDER = '#dce3ec'


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
        self.title('ShiftCorpus · Reddit 语料采集器')
        self.geometry('1120x820')
        self.minsize(900, 690)
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

    def _style(self):
        st = ttk.Style(self)
        st.theme_use('clam')
        st.configure('TFrame', background=BG)
        st.configure('White.TFrame', background=WHITE)
        st.configure('TLabel', background=BG, foreground=INK, font=('Helvetica', 11))
        st.configure('Muted.TLabel', background=BG, foreground=MUTED, font=('Helvetica', 10))
        st.configure('White.TLabel', background=WHITE, foreground=INK, font=('Helvetica', 10))
        st.configure('WhiteMuted.TLabel', background=WHITE, foreground=MUTED, font=('Helvetica', 10))
        st.configure('Heading.TLabel', background=BG, foreground=INK, font=('Helvetica', 22, 'bold'))
        st.configure('Subhead.TLabel', background=BG, foreground=INK, font=('Helvetica', 12, 'bold'))
        st.configure('TEntry', padding=6)
        st.configure('TCombobox', padding=5)
        st.configure('TCheckbutton', background=WHITE, foreground=INK, font=('Helvetica', 10))
        st.map('TCheckbutton', background=[('active', WHITE)])
        st.configure('Primary.TButton', background=ACCENT, foreground='white', padding=(17, 9), font=('Helvetica', 11, 'bold'))
        st.map('Primary.TButton', background=[('active', '#0e55a4'), ('disabled', '#a2b3c6')])
        st.configure('Secondary.TButton', padding=(12, 8), font=('Helvetica', 10))
        st.configure('TNotebook', background=BG, borderwidth=0)
        st.configure('TNotebook.Tab', padding=(20, 10), font=('Helvetica', 10))
        st.configure('Horizontal.TProgressbar', troughcolor='#e5ebf4', background=ACCENT, borderwidth=0)

    def _variables(self):
        defaults = dict(subreddit='politics', after='2022-05-01', before='2026-11-20',
                        period_days='180', sample_per_period='180', seed='1', min_words='5',
                        partial_policy='proportional', only_period='',
                        out=str((ROOT / 'corpus_output').resolve()))
        self.vars: dict[str, tk.Variable] = {k: tk.StringVar(value=v) for k,v in defaults.items()}
        for k in ['english', 'exclude_bots', 'exclude_nsfw', 'near_dup', 'with_posts']:
            self.vars[k] = tk.BooleanVar(value=True)
        self.status = tk.StringVar(value='就绪 · 等待开始')
        self.summary = tk.StringVar(value='')
        self.current_window = tk.StringVar(value='尚未开始')
        self.progress_label = tk.StringVar(value='—')

    def _layout(self):
        outer = ttk.Frame(self, padding=(28, 22, 28, 18))
        outer.pack(fill='both', expand=True)
        ttk.Label(outer, text='ShiftCorpus', style='Heading.TLabel').pack(anchor='w')
        ttk.Label(outer, text='Arctic Shift 研究语料采集 · 可视化参数、连接诊断和实时进度', style='Muted.TLabel').pack(anchor='w', pady=(1, 14))

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
        ttk.Label(command_header, text='即将执行的命令', style='Subhead.TLabel').pack(side='left')
        ttk.Button(command_header, text='复制命令', command=self._copy_command).pack(side='right')
        self.command_text = tk.Text(outer, height=3, bg='#eaf0f8', fg=INK,
                                     font=('Menlo', 10), wrap='word', relief='flat', padx=12, pady=9)
        self.command_text.pack(fill='x')
        self.command_text.configure(state='disabled')
        self.summary_view = ttk.Label(outer, textvariable=self.summary, style='Muted.TLabel')
        self.summary_view.pack(anchor='w', pady=(5, 0))

        actions = ttk.Frame(outer)
        actions.pack(fill='x', pady=(12, 10))
        self.start_button = ttk.Button(actions, text='▶  开始采集', style='Primary.TButton', command=self._start)
        self.start_button.pack(side='left')
        self.stop_button = ttk.Button(actions, text='■  停止', command=self._stop, state='disabled')
        self.stop_button.pack(side='left', padx=8)
        self.test_button = ttk.Button(actions, text='测试 API 连接', command=self._test_api)
        self.test_button.pack(side='left', padx=(2, 8))
        ttk.Button(actions, text='打开输出文件夹', command=self._open_folder).pack(side='left')
        ttk.Label(actions, textvariable=self.status, style='Muted.TLabel').pack(side='right')

        ttk.Label(outer, text='运行进度', style='Subhead.TLabel').pack(anchor='w', pady=(3, 5))
        self.progress = ttk.Progressbar(outer, mode='determinate', maximum=100)
        self.progress.pack(fill='x')
        status_row = ttk.Frame(outer)
        status_row.pack(fill='x', pady=(5, 5))
        ttk.Label(status_row, textvariable=self.current_window, style='Muted.TLabel').pack(side='left')
        ttk.Label(status_row, textvariable=self.progress_label, style='Muted.TLabel').pack(side='right')
        log_head = ttk.Frame(outer)
        log_head.pack(fill='x', pady=(8, 5))
        ttk.Label(log_head, text='实时日志与诊断信息', style='Subhead.TLabel').pack(side='left')
        ttk.Button(log_head, text='清空日志', command=self._clear_logs).pack(side='right')
        self.logs = scrolledtext.ScrolledText(outer, height=12, bg='#0f1c2e', fg='#d9e5f6',
                                              insertbackground='white', font=('Menlo', 10),
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
        ttk.Label(frame, text='采集范围与抽样', style='White.TLabel', font=('Helvetica', 12, 'bold')).grid(row=0, column=0, columnspan=2, sticky='w', padx=16, pady=(14, 6))
        inner = tk.Frame(frame, bg=WHITE)
        inner.grid(row=1, column=0, columnspan=2, sticky='nsew', padx=16)
        inner.grid_columnconfigure(0, weight=1)
        inner.grid_columnconfigure(1, weight=1)
        self._field(inner,'Subreddit','subreddit',0,0)
        self._field(inner,'随机种子 Seed','seed',0,1)
        self._field(inner,'开始日期（含）','after',1,0)
        self._field(inner,'结束日期（含）','before',1,1)
        self._field(inner,'窗口长度（天）','period_days',2,0)
        self._field(inner,'每完整窗口评论数','sample_per_period',2,1)
        self._field(inner,'最少词数','min_words',3,0)
        box = tk.Frame(inner, bg=WHITE)
        box.grid(row=3, column=1, sticky='ew', padx=(0,12), pady=6)
        ttk.Label(box,text='最后不足窗口',style='WhiteMuted.TLabel').pack(anchor='w',pady=(0,4))
        ttk.Combobox(box,textvariable=self.vars['partial_policy'],values=['proportional','full'],state='readonly',width=17).pack(fill='x')
        only = tk.Frame(frame,bg=WHITE)
        only.grid(row=2,column=0,columnspan=2,sticky='ew',padx=16,pady=(3,14))
        ttk.Label(only,text='仅采集指定窗口（可留空）',style='WhiteMuted.TLabel').pack(anchor='w',pady=(0,4))
        ttk.Entry(only,textvariable=self.vars['only_period']).pack(fill='x')
        ttk.Label(only,text='例如 2022-05-01_2022-10-27，适用于快速复测pilot',style='WhiteMuted.TLabel').pack(anchor='w',pady=(4,0))

    def _right(self, frame):
        ttk.Label(frame,text='清洗与输出',style='White.TLabel',font=('Helvetica',12,'bold')).pack(anchor='w',padx=16,pady=(14,10))
        for key,text in [
            ('english','仅保留英文评论'),
            ('exclude_bots','过滤已知Bot账号'),
            ('exclude_nsfw','过滤NSFW标记'),
            ('near_dup','去掉近重复文本'),
            ('with_posts','保存关联帖子标题作为上下文（不计入词频）')
        ]:
            ttk.Checkbutton(frame,text=text,variable=self.vars[key]).pack(anchor='w',padx=16,pady=3)
        ttk.Label(frame,text='输出文件夹',style='WhiteMuted.TLabel').pack(anchor='w',padx=16,pady=(16,5))
        pathrow = tk.Frame(frame,bg=WHITE)
        pathrow.pack(fill='x',padx=16)
        ttk.Entry(pathrow,textvariable=self.vars['out']).pack(side='left',fill='x',expand=True)
        ttk.Button(pathrow,text='浏览…',command=self._browse).pack(side='left',padx=(7,0))
        ttk.Label(frame,text='自动生成 AntConc TXT、索引、CSV、JSONL、query.json',style='WhiteMuted.TLabel',wraplength=400).pack(anchor='w',padx=16,pady=(10,10))

    def _values(self):
        return {k: var.get() for k,var in self.vars.items()}

    def _update_preview(self):
        try:
            values = self._values()
            cmd = make_command(values)
            text = shlex.join(cmd)
            windows,target,days=estimate_windows(values['after'],values['before'],int(values['period_days']),int(values['sample_per_period']),values['partial_policy'])
            info=f'预计 {windows} 个窗口 · 覆盖 {days} 天 · 计划采样 {target} 条评论（实际取决于API）'
        except (ValueError, KeyError) as exc:
            text=f'⚠ 参数待修正：{exc}'
            info='请检查上方参数'
        self.command_text.configure(state='normal')
        self.command_text.delete('1.0','end')
        self.command_text.insert('1.0',text)
        self.command_text.configure(state='disabled')
        self.summary.set(info)

    def _copy_command(self):
        self.clipboard_clear()
        self.clipboard_append(self.command_text.get('1.0','end').strip())
        self._log('命令已复制到剪贴板。','good')

    def _browse(self):
        selected=filedialog.askdirectory(initialdir=str(ROOT),title='选择语料输出文件夹')
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
            messagebox.showerror('采集参数有误',str(exc))
            return
        if not ENGINE.is_file():
            messagebox.showerror('缺少程序文件',f'找不到采集核心：\n{ENGINE}')
            return
        dest=Path(str(self.vars['out'].get())).expanduser()
        try: dest.mkdir(parents=True,exist_ok=True)
        except OSError as exc:
            messagebox.showerror('无法创建输出文件夹',str(exc));return
        self.stopping=False
        self.window_completed=0;self.day_progress=0;self.active_days=0
        self.progress.configure(value=0)
        self._log('\n'+'='*57)
        self._log('启动采集：'+datetime.now().strftime('%Y-%m-%d %H:%M:%S'),'good')
        self._log(shlex.join(command))
        try:
            self.proc=subprocess.Popen(command,cwd=str(ROOT),stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT,text=True,bufsize=1,errors='replace')
        except OSError as exc:
            self._log(f'程序无法启动：{exc}','error');return
        self.status.set('正在采集')
        self.start_button.configure(state='disabled')
        self.stop_button.configure(state='normal')
        threading.Thread(target=self._read_output,args=(self.proc,),daemon=True).start()

    def _read_output(self,process):
        try:
            assert process.stdout is not None
            for line in process.stdout:
                self.queue.put(('line',line.rstrip('\r\n')))
        except Exception as exc:
            self.queue.put(('line',f'日志读取错误：{exc}'))
        finally:
            code=process.wait()
            self.queue.put(('done',code))

    def _parse_progress(self,line):
        m=re.search(r'^period\s+(\d{4}-\d{2}-\d{2}_\d{4}-\d{2}-\d{2})',line)
        if m:
            self.window_completed+=1
            self.day_progress=0
            self.current_window.set('当前窗口：'+m.group(1))
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
            self.progress_label.set(f'{max(0,self.window_completed)}/{windows} 窗口 · 当前窗口第 {self.day_progress}/{self.active_days} 天')
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
                    self.status.set('完成');self.progress.configure(value=100)
                    self._log('采集完成。请检查输出文件夹。','good')
                elif self.stopping:
                    self.status.set('已停止');self._log('用户停止了采集。','warn')
                else:
                    self.status.set(f'失败（退出码 {code}）')
                    self._log('采集未正常完成；请查看上方具体API错误。','error')
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
            self.status.set('正在停止')
            self._log('已请求终止采集进程…','warn')
            self.proc.terminate()

    def _test_api(self):
        if self.test_busy:return
        self.test_busy=True
        self.test_button.configure(state='disabled')
        self._log('API诊断：正在连接 Arctic Shift…')
        threading.Thread(target=self._run_api_test,daemon=True).start()

    def _run_api_test(self):
        try:
            req=urllib.request.Request(API_TEST_URL,headers={'User-Agent':'ShiftCorpusGUI/1.0 (academic research)'})
            with urllib.request.urlopen(req,timeout=15) as response:
                status=response.status
                snippet=response.read(1_000_000)
            try:
                data=json.loads(snippet)
                detail='；收到有效JSON' if isinstance(data,(dict,list)) else '；收到响应，但JSON结构异常'
            except json.JSONDecodeError:
                detail='；返回内容不是有效JSON'
            self.queue.put(('api',(True,f'API连接成功：HTTP {status}{detail}')))
        except urllib.error.HTTPError as exc:
            self.queue.put(('api',(False,f'API服务器返回 HTTP {exc.code}：{exc.reason}')))
        except Exception as exc:
            self.queue.put(('api',(False,f'API连接失败：{type(exc).__name__}: {exc}')))

    def _open_folder(self):
        path=Path(self.vars['out'].get()).expanduser()
        path.mkdir(parents=True,exist_ok=True)
        if sys.platform=='darwin': subprocess.Popen(['open',str(path)])
        elif sys.platform=='win32':os.startfile(str(path))
        else:subprocess.Popen(['xdg-open',str(path)])

    def _close(self):
        if self.proc and self.proc.poll() is None:
            if not messagebox.askyesno('正在采集','采集仍在运行。退出将停止采集，确定退出吗？'):return
            self.proc.terminate()
        self.destroy()


if __name__=='__main__':
    try: App().mainloop()
    except tk.TclError as exc:
        print(f'无法启动Tkinter图形界面：{exc}\n请使用支持桌面的Python 3，Mac建议安装python.org发行版。',file=sys.stderr)
        raise SystemExit(1)
