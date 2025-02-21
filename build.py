import PyInstaller.__main__
import sys
import os

# 确保在正确的目录
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# 打包参数
options = [
    'schedule_app.py',  # 主程序文件
    '--name=日程管理',  # 生成的exe名称
    '--noconsole',  # 不显示控制台
    '--windowed',  # 使用 Windows 子系统
    '--hidden-import=PIL._tkinter_finder',  # 确保 PIL 正确导入
    '--hidden-import=win10toast',
    '--hidden-import=ttkbootstrap',
    '--hidden-import=pystray',
    '--hidden-import=PIL',
    '--hidden-import=PIL._imaging',
    '--onefile',  # 打包成单个文件
    '--clean',  # 清理临时文件
    '--noconfirm',  # 不确认覆盖
]

# 运行打包命令
PyInstaller.__main__.run(options) 