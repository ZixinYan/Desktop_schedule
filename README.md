# 桌面清单
---
## 功能
- 记录每天的日程安排，精确到每分钟
- 简洁干净的ui
- 快到任务开始时间自动提醒
- 隐藏到系统托盘，不影响日常使用
- 日程永久记录，不用担心开关机和误关程序造成丢失

## 具体操作
- 部署
  ```bash
  python install -r requirements.txt
  python schedule_app.py

  或者运行
  ```bash
  python install -r requirements.txt
  python build.py

  如果有一些依赖没有安装就自己安装一下再，如果用build.py打包的话去dist目录里面可以找到应用程序
  
- 使用方法
    - 空白处双击左键添加日程
    - 右键单击日程删除日程
    - 右键空白处隐藏ui
      
## UI展示

## 未来更新计划
- 美化ui
- 封装成应用方便使用
- 完善逻辑，现在只显示一天的日程，错误添加未来的日程无法正常删除
  
