import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
import sqlite3
from datetime import datetime, time as dt_time, timedelta  # 重命名time避免冲突
import threading
import time
from win10toast import ToastNotifier
import sys
import os
import winreg
from PIL import Image, ImageTk, ImageDraw, ImageFilter
import pystray
from ttkbootstrap.dialogs import Dialog
from ttkbootstrap.widgets import DateEntry  # 使用 DateEntry 替代 Calendar
import ctypes
import math
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.style import Style
from ttkbootstrap.dialogs import calendar as TtkCalendar  # 使用 ttkbootstrap 的日历

def create_checklist_icon():
    # 创建一个 32x32 的图标
    icon_size = (32, 32)
    icon = Image.new('RGBA', icon_size, color=(0, 0, 0, 0))
    
    # 创建绘图对象
    draw = ImageDraw.Draw(icon)
    
    # 绘制清单外框
    draw.rectangle([4, 2, 28, 30], outline=(65, 105, 225), width=2)  # 使用皇家蓝色
    
    # 绘制三条横线代表清单项
    y_positions = [8, 16, 24]
    for y in y_positions:
        # 绘制勾选框
        draw.rectangle([7, y, 11, y+4], outline=(65, 105, 225), width=1)
        # 绘制文本线
        draw.line([14, y+2, 25, y+2], fill=(65, 105, 225), width=1)
    
    return icon

class ClockPicker(tk.Canvas):
    def __init__(self, parent, var, is_hour=True, **kwargs):
        super().__init__(parent, width=200, height=200, bg='#2E3440', highlightthickness=0, **kwargs)
        self.var = var
        self.is_hour = is_hour
        self.center = (100, 100)
        self.radius = 80
        
        # 绘制表盘
        self.draw_clock_face()
        
        # 绑定事件
        self.bind('<Button-1>', self.on_click)
        self.bind('<B1-Motion>', self.on_drag)
        
    def draw_clock_face(self):
        # 绘制外圈
        self.create_oval(20, 20, 180, 180, outline='#5E81AC', width=2)
        
        # 绘制刻度和数字
        if self.is_hour:
            # 24小时制的小时显示
            for i in range(24):
                angle = math.radians(i * (360 / 24) - 90)
                r = self.radius - 20
                x = self.center[0] + r * math.cos(angle)
                y = self.center[1] + r * math.sin(angle)
                
                # 显示的数字
                self.create_text(x, y, text=str(i), fill='#D8DEE9', 
                               font=('微软雅黑', 11, 'bold'))
        else:
            # 分钟显示（每5分钟一个刻度）
            for i in range(0, 60, 5):
                angle = math.radians(i * (360 / 60) - 90)
                r = self.radius - 20
                x = self.center[0] + r * math.cos(angle)
                y = self.center[1] + r * math.sin(angle)
                
                self.create_text(x, y, text=str(i), fill='#D8DEE9', 
                               font=('微软雅黑', 11, 'bold'))
        
        # 绘制指针
        self.draw_hand()
    
    def draw_hand(self):
        # 清除旧的指针
        self.delete('hand')
        
        # 获取当前值
        value = int(self.var.get())
        if self.is_hour and value > 12:
            value -= 12
            
        # 计算角度
        angle = math.radians(value * (360 / (12 if self.is_hour else 60)) - 90)
        
        # 绘制新指针
        x = self.center[0] + self.radius * 0.7 * math.cos(angle)
        y = self.center[1] + self.radius * 0.7 * math.sin(angle)
        
        self.create_line(self.center[0], self.center[1], x, y,
                        fill='#88C0D0', width=3, tags='hand')
        
    def on_click(self, event):
        self.update_time(event)
        
    def on_drag(self, event):
        self.update_time(event)
        
    def update_time(self, event):
        # 计算角度
        dx = event.x - self.center[0]
        dy = event.y - self.center[1]
        angle = math.degrees(math.atan2(dy, dx)) + 90
        if angle < 0:
            angle += 360
            
        # 转换为时间值
        if self.is_hour:
            value = round(angle / 15) % 24  # 24小时制
        else:
            value = round(angle / 6) % 60
            
        # 更新变量
        self.var.set(f"{value:02d}")
        self.draw_hand()

class ScheduleApp(ttk.Window):
    def __init__(self):
        # 初始化 ttkbootstrap 主题
        super().__init__(themename="darkly")  # 使用深色主题
        
        # 设置窗口样式
        self.attributes('-alpha', 0.85)
        self.overrideredirect(True)
        self.attributes('-topmost', True)
        self.geometry('300x400+0+0')
        
        # 创建磨砂背景
        self.create_blur_background()
        
        # 初始化拖动变量
        self.lastClickX = 0
        self.lastClickY = 0
        
        # 创建主框架
        self.main_frame = tk.Frame(self, bg='#2E3440')
        self.main_frame.pack(fill='both', expand=True)
        
        # 初始化数据库
        self.init_database()
        
        # 创建日程列表
        self.create_schedule_list()
        
        # 添加托盘图标引用
        self.tray_icon = None
        
        # 添加提醒音乐路径
        self.notification_sound = os.path.join(os.path.dirname(__file__), 'notification.mp3')
        
        # 设置系统托盘
        self.setup_system_tray()
        
        # 启动提醒检查
        self.start_notification_checker()
        
        # 绑定事件
        self.bind('<Button-1>', self.save_last_click)
        self.bind('<B1-Motion>', self.dragging)
        self.main_frame.bind('<Double-Button-1>', self.show_add_dialog)
        
        # 添加窗口固定状态标志
        self.is_pinned = False
        
        # 绑定右键菜单
        self.bind('<Button-3>', self.show_window_menu)
        
        # 添加日期标题
        self.title_label = tk.Label(self.main_frame, 
                                   text=datetime.now().strftime('%Y年%m月%d日'),
                                   font=('微软雅黑', 14, 'bold'),
                                   fg='#D8DEE9', bg='#2E3440')
        self.title_label.pack(pady=10)
        
        # 添加窗口关闭事件处理
        self.protocol("WM_DELETE_WINDOW", self.hide_window)
        
        # 添加程序退出时的清理
        import atexit
        atexit.register(lambda: self.conn.close() if hasattr(self, 'conn') else None)

    def init_database(self):
        self.conn = sqlite3.connect('schedule.db', check_same_thread=False)
        self.cursor = self.conn.cursor()
        
        # 只在表不存在时创建表
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS schedules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                schedule_time DATETIME NOT NULL,
                repeat_type TEXT DEFAULT 'none',
                parent_id INTEGER
            )
        ''')
        self.conn.commit()

    def create_schedule_list(self):
        # 创建日程列表框架（无边框）
        self.schedule_frame = tk.Frame(self.main_frame, bg='#2E3440')
        self.schedule_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        # 刷新日程列表
        self.refresh_schedule_list()

    def create_blur_background(self):
        # 创建磨砂玻璃效果的背景
        img = Image.new('RGBA', (300, 400), (46, 52, 64, 128))  # 修改透明度为128 (50%)
        blur_img = img.filter(ImageFilter.GaussianBlur(radius=10))
        self.blur_bg = ImageTk.PhotoImage(blur_img)
        
        # 创建背景标签
        self.bg_label = tk.Label(self, image=self.blur_bg)
        self.bg_label.place(x=0, y=0, relwidth=1, relheight=1)
        
        # 创建半透明叠加层
        self.overlay_frame = tk.Frame(self, bg='#2E3440')
        self.overlay_frame.place(relwidth=1, relheight=1)
        self.attributes('-alpha', 0.5)  # 设置整体透明度为50%

    def save_last_click(self, event):
        if not self.is_pinned:  # 只在未固定状态下允许拖动
            self.lastClickX = event.x
            self.lastClickY = event.y

    def dragging(self, event):
        if not self.is_pinned:  # 只在未固定状态下允许拖动
            x = self.winfo_x() + (event.x - self.lastClickX)
            y = self.winfo_y() + (event.y - self.lastClickY)
            self.geometry(f"+{x}+{y}")

    def show_add_dialog(self, event=None):
        # 检查点击位置是否在日程项上
        clicked_widget = event.widget
        if isinstance(clicked_widget, tk.Frame) and hasattr(clicked_widget, 'schedule_id'):
            return  # 如果点击在日程项上，不显示添加对话框
        
        dialog = ttk.Toplevel(self)  # 使用 ttk.Toplevel
        dialog.title('添加日程')
        dialog.geometry('400x600')
        
        main_frame = ttk.Frame(dialog)
        main_frame.pack(fill='both', expand=True, padx=20, pady=20)
        
        # 标题
        title_frame = ttk.Frame(main_frame)
        title_frame.pack(fill='x', pady=(0, 20))
        ttk.Label(
            title_frame,
            text="新建日程",
            font=('微软雅黑', 16, 'bold')
        ).pack(side='left')
        
        # 日期和时间选择区域
        datetime_frame = ttk.LabelFrame(main_frame, text="时间", padding=15)
        datetime_frame.pack(fill='x', pady=(0, 20))
        
        # 日期选择
        date_frame = ttk.Frame(datetime_frame)
        date_frame.pack(fill='x', pady=(0, 10))
        
        current_date = datetime.now()
        date_var = tk.StringVar(value=current_date.strftime('%Y-%m-%d'))
        
        ttk.Label(
            date_frame,
            text="日期：",
            style='primary.TLabel'
        ).pack(side='left')
        
        # 使用三个下拉框选择日期
        year_var = tk.StringVar(value=str(current_date.year))
        month_var = tk.StringVar(value=str(current_date.month))
        day_var = tk.StringVar(value=str(current_date.day))
        
        # 年份选择（前后5年）
        year = ttk.Spinbox(
            date_frame,
            from_=current_date.year-5,
            to=current_date.year+5,
            width=6,
            textvariable=year_var
        )
        year.pack(side='left', padx=5)
        
        ttk.Label(date_frame, text="年").pack(side='left')
        
        # 月份选择
        month = ttk.Spinbox(
            date_frame,
            from_=1,
            to=12,
            width=4,
            textvariable=month_var
        )
        month.pack(side='left', padx=5)
        
        ttk.Label(date_frame, text="月").pack(side='left')
        
        # 日期选择
        day = ttk.Spinbox(
            date_frame,
            from_=1,
            to=31,
            width=4,
            textvariable=day_var
        )
        day.pack(side='left', padx=5)
        
        ttk.Label(date_frame, text="日").pack(side='left')
        
        # 时间选择
        time_frame = ttk.Frame(datetime_frame)
        time_frame.pack(fill='x', pady=(10, 0))
        
        ttk.Label(
            time_frame,
            text="时间：",
            style='primary.TLabel'
        ).pack(side='left')
        
        hour_var = tk.StringVar(value=str(current_date.hour))
        minute_var = tk.StringVar(value=str(current_date.minute))
        
        # 小时选择
        hour = ttk.Spinbox(
            time_frame,
            from_=0,
            to=23,
            width=4,
            textvariable=hour_var
        )
        hour.pack(side='left', padx=5)
        
        ttk.Label(time_frame, text="时").pack(side='left')
        
        # 分钟选择
        minute = ttk.Spinbox(
            time_frame,
            from_=0,
            to=59,
            width=4,
            textvariable=minute_var
        )
        minute.pack(side='left', padx=5)
        
        ttk.Label(time_frame, text="分").pack(side='left')
        
        # 重复选项
        repeat_frame = ttk.LabelFrame(main_frame, text="重复", padding=15)
        repeat_frame.pack(fill='x', pady=(0, 20))
        
        repeat_var = tk.StringVar(value='none')
        repeat_options = [
            ('不重复', 'none'),
            ('每天', 'daily'),
            ('工作日', 'workday'),
            ('每周', 'weekly')
        ]
        
        for text, value in repeat_options:
            ttk.Radiobutton(
                repeat_frame,
                text=text,
                value=value,
                variable=repeat_var,
                style='primary.TRadiobutton'
            ).pack(side='left', padx=10)
        
        # 内容输入
        content_frame = ttk.LabelFrame(main_frame, text="内容", padding=15)
        content_frame.pack(fill='x', pady=(0, 20))
        
        content_entry = ttk.Entry(
            content_frame,
            font=('微软雅黑', 11),
            width=10  # 限制显示宽度
        )
        content_entry.pack(fill='x', padx=5)
        
        def validate_content(*args):
            content = content_entry.get()
            if len(content) > 10:
                content_entry.delete(10, tk.END)
        
        content_entry.bind('<KeyRelease>', validate_content)
        
        # 添加回车保存功能
        def on_enter(event):
            save_schedule()
        
        content_entry.bind('<Return>', on_enter)
        
        # 按钮区域
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x', pady=(0, 10))
        
        def save_schedule():
            try:
                # 构建日期时间
                schedule_date = datetime(
                    int(year_var.get()),
                    int(month_var.get()),
                    int(day_var.get()),
                    int(hour_var.get()),
                    int(minute_var.get())
                )
                
                content = content_entry.get()
                if not content.strip():
                    messagebox.showwarning("警告", "请输入日程内容")
                    return
                
                self.add_schedule(content, schedule_date, repeat_var.get())
                dialog.destroy()
                
            except ValueError as e:
                messagebox.showerror("错误", "请输入有效的日期和时间")
        
        ttk.Button(
            button_frame,
            text="保存",
            command=save_schedule,
            style='success'  # 使用 ttkbootstrap 的按钮样式
        ).pack(side='right', padx=5)
        
        ttk.Button(
            button_frame,
            text="取消",
            command=dialog.destroy,
            style='secondary'  # 使用 ttkbootstrap 的按钮样式
        ).pack(side='right', padx=5)
        
        # 设置对话框位置
        dialog.update_idletasks()
        width = dialog.winfo_width()
        height = dialog.winfo_height()
        x = (dialog.winfo_screenwidth() // 2) - (width // 2)
        y = (dialog.winfo_screenheight() // 2) - (height // 2)
        dialog.geometry(f'+{x}+{y}')
        
        dialog.transient(self)
        dialog.grab_set()
        content_entry.focus_set()

    def show_context_menu(self, event, widget):
        menu = tk.Menu(self, tearoff=0)
        menu.configure(bg='#3B4252', fg='#D8DEE9', activebackground='#4C566A', activeforeground='white')
        menu.add_command(label='修改', command=lambda: self.edit_schedule(widget))
        menu.add_command(label='删除', command=lambda: self.delete_schedule(widget))
        menu.post(event.x_root, event.y_root)

    def add_schedule(self, content, schedule_time, repeat_type='none'):
        try:
            # 插入主日程
            self.cursor.execute(
                "INSERT INTO schedules (content, schedule_time, repeat_type) VALUES (?, ?, ?)",
                (content, schedule_time, repeat_type)
            )
            schedule_id = self.cursor.lastrowid
            self.conn.commit()
            
            # 如果是重复日程，生成未来30天的日程
            if repeat_type != 'none':
                self.generate_repeat_schedules(content, schedule_time, repeat_type, schedule_id)
            
            self.refresh_schedule_list()
        except Exception as e:
            messagebox.showerror("错误", f"添加日程失败：{str(e)}")

    def delete_schedule(self, widget):
        schedule_id = widget.schedule_id
        
        # 获取日程信息
        self.cursor.execute("""
            SELECT repeat_type, parent_id, schedule_time 
            FROM schedules 
            WHERE id=?
        """, (schedule_id,))
        repeat_type, parent_id, schedule_time = self.cursor.fetchone()
        
        if repeat_type != 'none' or parent_id is not None:
            # 对于重复日程，只删除当天的日程
            schedule_date = datetime.strptime(schedule_time, '%Y-%m-%d %H:%M:%S').date()
            self.cursor.execute("""
                DELETE FROM schedules 
                WHERE (id=? OR parent_id=?) 
                AND date(schedule_time)=?
            """, (schedule_id, schedule_id, schedule_date))
        else:
            # 对于非重复日程，直接删除
            self.cursor.execute("DELETE FROM schedules WHERE id=?", (schedule_id,))
        
        self.conn.commit()
        self.refresh_schedule_list()

    def refresh_schedule_list(self):
        # 清除现有显示
        for widget in self.schedule_frame.winfo_children():
            widget.destroy()
        
        # 获取今天的日程
        today = datetime.now().date()
        self.cursor.execute(
            """
            SELECT id, content, schedule_time 
            FROM schedules 
            WHERE date(schedule_time) = date('now', 'localtime')
            ORDER BY schedule_time
            """
        )
        
        # 日程背景颜色列表（Nord theme colors）
        schedule_colors = [
            ('#8FBCBB', '#2E3440'),  # 青绿色背景，深色文字
            ('#88C0D0', '#2E3440'),  # 浅蓝色背景，深色文字
            ('#81A1C1', '#ECEFF4'),  # 深蓝色背景，浅色文字
            ('#5E81AC', '#ECEFF4'),  # 靛蓝色背景，浅色文字
        ]
        
        for i, row in enumerate(self.cursor.fetchall()):
            schedule_id, content, schedule_time = row
            schedule_time = datetime.strptime(schedule_time, '%Y-%m-%d %H:%M:%S')
            time_str = schedule_time.strftime('%H:%M')
            
            # 选择背景颜色
            bg_color, fg_color = schedule_colors[i % len(schedule_colors)]
            
            # 创建日程项框架
            item_frame = tk.Frame(self.schedule_frame, bg='#2E3440')
            item_frame.schedule_id = schedule_id
            item_frame.pack(fill='x', pady=3, padx=5)
            
            # 创建内容框架
            content_frame = tk.Frame(item_frame, bg=bg_color)
            content_frame.pack(fill='x', ipady=8)
            
            # 时间标签
            time_label = tk.Label(content_frame, text=time_str, 
                                font=('微软雅黑', 11, 'bold'),
                                fg=fg_color, bg=bg_color)
            time_label.pack(side='left', padx=15)
            
            # 内容标签
            content_label = tk.Label(content_frame, text=content, 
                                   font=('微软雅黑', 12, 'bold'),
                                   fg=fg_color, bg=bg_color)
            content_label.pack(side='left', padx=10)
            
            # 为每个日程项创建独立的事件处理函数
            def create_handlers(frame, content_frame, bg_color, fg_color):
                def on_enter(e):
                    content_frame.configure(bg='#4C566A')
                    for child in content_frame.winfo_children():
                        child.configure(bg='#4C566A')
                
                def on_leave(e):
                    content_frame.configure(bg=bg_color)
                    for child in content_frame.winfo_children():
                        child.configure(bg=bg_color)
                
                return on_enter, on_leave
            
            # 获取当前日程项的处理函数
            on_enter, on_leave = create_handlers(item_frame, content_frame, bg_color, fg_color)
            
            # 绑定事件
            for widget in [item_frame, content_frame, time_label, content_label]:
                widget.bind('<Enter>', on_enter)
                widget.bind('<Leave>', on_leave)
                widget.bind('<Button-3>', lambda e, w=item_frame: self.delete_schedule(w))
                widget.bind('<Double-Button-1>', lambda e, w=item_frame: self.edit_schedule(w))
                widget.schedule_id = schedule_id

    def check_notifications(self):
        toaster = ToastNotifier()
        checked_schedules = set()  # 用于记录已经提醒过的日程
        
        while True:
            current_time = datetime.now()
            # 获取即将到来的日程（5分钟内）
            self.cursor.execute("""
                SELECT id, content, schedule_time 
                FROM schedules 
                WHERE datetime(schedule_time) > datetime('now') 
                AND datetime(schedule_time) <= datetime('now', '+5 minutes')
            """)
            
            for row in self.cursor.fetchall():
                schedule_id, content, schedule_time = row
                # 检查是否已经提醒过
                if schedule_id not in checked_schedules:
                    schedule_time = datetime.strptime(schedule_time, '%Y-%m-%d %H:%M:%S')
                    time_diff = (schedule_time - current_time).total_seconds() / 60
                    
                    if 0 <= time_diff <= 5:  # 只提醒未来5分钟内的日程
                        # 播放提醒音乐
                        try:
                            import winsound
                            winsound.PlaySound("SystemExclamation", winsound.SND_ASYNC)
                        except:
                            pass
                        
                        # 显示通知
                        toaster.show_toast(
                            "日程提醒",
                            f"即将开始的日程: {content}\n时间: {schedule_time.strftime('%H:%M')}",
                            duration=10,
                            threaded=True
                        )
                        
                        # 记录已提醒的日程
                        checked_schedules.add(schedule_id)
            
            # 清理过期的已提醒记录
            self.cursor.execute("SELECT id FROM schedules WHERE datetime(schedule_time) < datetime('now')")
            expired_ids = {row[0] for row in self.cursor.fetchall()}
            checked_schedules -= expired_ids
            
            time.sleep(30)  # 每30秒检查一次

    def setup_system_tray(self):
        # 确保之前的图标被清理
        if self.tray_icon is not None:
            self.tray_icon.stop()
        
        # 使用自定义的清单图标
        icon = create_checklist_icon()
        self.tray_icon = pystray.Icon(
            "schedule_app",
            icon,
            "日程管理",
            menu=pystray.Menu(
                pystray.MenuItem("显示", self.show_window),
                pystray.MenuItem("退出", self.quit_app)
            )
        )
        
        # 设置双击事件处理
        def on_activate(icon, button, time):
            if button == 1:  # 左键点击
                self.show_window()
        
        self.tray_icon.on_activate = on_activate
        
        # 在新线程中运行系统托盘
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def hide_window(self):
        self.withdraw()
        
    def show_window(self, icon=None, item=None):
        self.deiconify()
        self.lift()
        if self.is_pinned:
            self.attributes('-topmost', True)
        
        # 获取屏幕尺寸
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        window_width = 300
        window_height = 400
        
        # 计算窗口位置（右上角）
        x = screen_width - window_width - 20
        y = 20
        
        self.geometry(f"{window_width}x{window_height}+{x}+{y}")

    def quit_app(self, icon=None, item=None):
        # 确保清理系统托盘图标
        if self.tray_icon is not None:
            self.tray_icon.stop()
            self.tray_icon = None
        
        # 关闭数据库连接
        if hasattr(self, 'conn'):
            self.conn.commit()  # 确保所有更改都被保存
            self.conn.close()
        
        self.quit()

    def start_notification_checker(self):
        self.notification_thread = threading.Thread(target=self.check_notifications, daemon=True)
        self.notification_thread.start()

    def generate_repeat_schedules(self, content, base_time, repeat_type, parent_id):
        base_date = base_time.date()
        time_part = base_time.time()
        
        for i in range(1, 31):  # 生成未来30天的日程
            next_date = base_date + timedelta(days=i)
            
            # 根据重复类型判断是否需要创建日程
            create_schedule = False
            if repeat_type == 'daily':
                create_schedule = True
            elif repeat_type == 'workday':
                create_schedule = next_date.weekday() < 5  # 0-4 表示周一到周五
            elif repeat_type == 'weekly':
                create_schedule = next_date.weekday() == base_date.weekday()
            
            if create_schedule:
                next_time = datetime.combine(next_date, time_part)
                self.cursor.execute(
                    "INSERT INTO schedules (content, schedule_time, repeat_type, parent_id) VALUES (?, ?, ?, ?)",
                    (content, next_time, repeat_type, parent_id)
                )
        
        self.conn.commit()

    def check_and_generate_schedules(self):
        self.cursor.execute(
            "SELECT DISTINCT parent_id FROM schedules WHERE parent_id IS NOT NULL"
        )
        parent_ids = self.cursor.fetchall()
        
        for (parent_id,) in parent_ids:
            self.cursor.execute(
                "SELECT content, schedule_time, repeat_type FROM schedules WHERE id=?",
                (parent_id,)
            )
            parent = self.cursor.fetchone()
            if parent:
                content, base_time, repeat_type = parent
                base_time = datetime.strptime(base_time, '%Y-%m-%d %H:%M:%S')
                self.generate_repeat_schedules(content, base_time, repeat_type, parent_id)

    def show_window_menu(self, event):
        # 检查点击位置是否在日程项上
        clicked_widget = event.widget
        if isinstance(clicked_widget, tk.Frame) and hasattr(clicked_widget, 'schedule_id'):
            return  # 如果点击在日程项上，不显示菜单
        
        menu = tk.Menu(self, tearoff=0)
        menu.configure(bg='#3B4252', fg='#D8DEE9', 
                      activebackground='#4C566A', 
                      activeforeground='white')
        
        # 添加固定/取消固定选项
        pin_text = "取消固定" if self.is_pinned else "固定窗口"
        menu.add_command(label=pin_text, 
                        command=self.toggle_pin,
                        font=('微软雅黑', 10))
        
        # 添加隐藏选项
        menu.add_command(label="隐藏窗口", 
                        command=self.hide_window,
                        font=('微软雅黑', 10))
        
        menu.post(event.x_root, event.y_root)

    def toggle_pin(self):
        self.is_pinned = not self.is_pinned
        if self.is_pinned:
            self.attributes('-topmost', True)
            # 更明显的视觉提示
            self.configure(bg='#5E81AC')
            self.main_frame.configure(bg='#5E81AC')
            # 禁用拖动
            self.unbind('<Button-1>')
            self.unbind('<B1-Motion>')
        else:
            self.attributes('-topmost', False)
            self.configure(bg='#2E3440')
            self.main_frame.configure(bg='#2E3440')
            # 重新启用拖动
            self.bind('<Button-1>', self.save_last_click)
            self.bind('<B1-Motion>', self.dragging)

    def edit_schedule(self, widget):
        schedule_id = widget.schedule_id
        
        # 获取当前日程信息
        self.cursor.execute("""
            SELECT content, schedule_time, repeat_type 
            FROM schedules 
            WHERE id=?
        """, (schedule_id,))
        content, schedule_time, repeat_type = self.cursor.fetchone()
        current_schedule = datetime.strptime(schedule_time, '%Y-%m-%d %H:%M:%S')
        
        # 创建编辑对话框
        dialog = ttk.Toplevel(self)
        dialog.title('修改日程')
        dialog.geometry('400x600')
        
        main_frame = ttk.Frame(dialog)
        main_frame.pack(fill='both', expand=True, padx=20, pady=20)
        
        # 标题
        title_frame = ttk.Frame(main_frame)
        title_frame.pack(fill='x', pady=(0, 20))
        ttk.Label(
            title_frame,
            text="修改日程",
            font=('微软雅黑', 16, 'bold')
        ).pack(side='left')
        
        # 日期和时间选择区域
        datetime_frame = ttk.LabelFrame(main_frame, text="时间", padding=15)
        datetime_frame.pack(fill='x', pady=(0, 20))
        
        # 日期选择
        date_frame = ttk.Frame(datetime_frame)
        date_frame.pack(fill='x', pady=(0, 10))
        
        year_var = tk.StringVar(value=str(current_schedule.year))
        month_var = tk.StringVar(value=str(current_schedule.month))
        day_var = tk.StringVar(value=str(current_schedule.day))
        
        # 年份选择
        year = ttk.Spinbox(
            date_frame,
            from_=current_schedule.year-5,
            to=current_schedule.year+5,
            width=6,
            textvariable=year_var
        )
        year.pack(side='left', padx=5)
        ttk.Label(date_frame, text="年").pack(side='left')
        
        # 月份选择
        month = ttk.Spinbox(
            date_frame,
            from_=1,
            to=12,
            width=4,
            textvariable=month_var
        )
        month.pack(side='left', padx=5)
        ttk.Label(date_frame, text="月").pack(side='left')
        
        # 日期选择
        day = ttk.Spinbox(
            date_frame,
            from_=1,
            to=31,
            width=4,
            textvariable=day_var
        )
        day.pack(side='left', padx=5)
        ttk.Label(date_frame, text="日").pack(side='left')
        
        # 时间选择
        time_frame = ttk.Frame(datetime_frame)
        time_frame.pack(fill='x', pady=(10, 0))
        
        hour_var = tk.StringVar(value=str(current_schedule.hour))
        minute_var = tk.StringVar(value=str(current_schedule.minute))
        
        # 小时和分钟选择
        hour = ttk.Spinbox(
            time_frame,
            from_=0,
            to=23,
            width=4,
            textvariable=hour_var
        )
        hour.pack(side='left', padx=5)
        ttk.Label(time_frame, text="时").pack(side='left')
        
        minute = ttk.Spinbox(
            time_frame,
            from_=0,
            to=59,
            width=4,
            textvariable=minute_var
        )
        minute.pack(side='left', padx=5)
        ttk.Label(time_frame, text="分").pack(side='left')
        
        # 内容输入
        content_frame = ttk.LabelFrame(main_frame, text="内容", padding=15)
        content_frame.pack(fill='x', pady=(0, 20))
        
        content_entry = ttk.Entry(
            content_frame,
            font=('微软雅黑', 11)
        )
        content_entry.pack(fill='x', padx=5)
        content_entry.insert(0, content)  # 填入当前内容
        
        def validate_content(*args):
            if len(content_entry.get()) > 10:
                content_entry.delete(10, tk.END)
        
        content_entry.bind('<KeyRelease>', validate_content)
        
        # 保存修改
        def save_changes():
            try:
                new_time = datetime(
                    int(year_var.get()),
                    int(month_var.get()),
                    int(day_var.get()),
                    int(hour_var.get()),
                    int(minute_var.get())
                )
                
                new_content = content_entry.get().strip()
                if not new_content:
                    messagebox.showwarning("警告", "请输入日程内容")
                    return
                
                # 更新数据库
                self.cursor.execute("""
                    UPDATE schedules 
                    SET content=?, schedule_time=? 
                    WHERE id=?
                """, (new_content, new_time, schedule_id))
                
                self.conn.commit()
                self.refresh_schedule_list()
                dialog.destroy()
                
            except ValueError as e:
                messagebox.showerror("错误", "请输入有效的日期和时间")
        
        # 按钮区域
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x', pady=(0, 10))
        
        ttk.Button(
            button_frame,
            text="保存",
            command=save_changes,
            style='success'
        ).pack(side='right', padx=5)
        
        ttk.Button(
            button_frame,
            text="取消",
            command=dialog.destroy,
            style='secondary'
        ).pack(side='right', padx=5)
        
        # 设置对话框位置
        dialog.update_idletasks()
        width = dialog.winfo_width()
        height = dialog.winfo_height()
        x = (dialog.winfo_screenwidth() // 2) - (width // 2)
        y = (dialog.winfo_screenheight() // 2) - (height // 2)
        dialog.geometry(f'+{x}+{y}')
        
        dialog.transient(self)
        dialog.grab_set()
        content_entry.focus_set()

def add_to_startup():
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_ALL_ACCESS)
        executable_path = sys.executable
        if getattr(sys, 'frozen', False):
            application_path = sys.executable
        else:
            application_path = os.path.abspath(__file__)
        winreg.SetValueEx(key, "ScheduleApp", 0, winreg.REG_SZ, f'"{executable_path}" "{application_path}"')
        winreg.CloseKey(key)
        return True
    except WindowsError:
        return False

if __name__ == "__main__":
    app = ScheduleApp()
    app.mainloop() 
