# -*- coding: utf-8 -*-
"""应用程序核心模块"""
import logging
import traceback
import tkinter as tk
from basic import Basic
from tkinter import ttk
from tkinter import messagebox
from config import COLOR_PALETTE, AppConfig
from utils import get_network_status

LAYOUT = AppConfig.LAYOUT
WIDGET = AppConfig.WIDGET


class App:
    """智慧教育平台资源下载工具"""
    def __init__(self):
        """初始化应用程序"""
        self.frames = {}
        self.modules = {}
        self.widgets = {}
        self.toplevel = None


        # 创建应用窗口
        self.root = tk.Tk()
        self._setup_window()

        # 创建界面组件
        self._create_frames()
        self._create_widgets()

        # 网络状态监控
        self.network_status = None

    def _setup_window(self):
        # 设置窗口标题、透明度和置顶状态
        self.root.title(f"{AppConfig.APP_NAME} v{AppConfig.APP_VERSION}")
        self.root.attributes("-topmost", False, "-alpha", 0.97)
        self.root.resizable(False, False)
        self.root.config(padx=12)

        # 设置窗口大小和居中显示
        win_width, win_height = 600, 400
        screen_width, screen_height = (
            self.root.winfo_screenwidth(),
            self.root.winfo_screenheight(),
        )
        x, y = (screen_width - win_width) // 2, (screen_height - win_height) // 2
        self.root.geometry(f"{win_width}x{win_height}+{x}+{y}")

        # 设置网格权重
        self.root.rowconfigure(1, weight=1)
        self.root.columnconfigure(0, weight=1)

    def _create_frames(self):
        """创建组件框架"""
        for name, config in LAYOUT.items():
            # 获取父框架
            master = (
                self.root
                if config["master"] == "root"
                else self.frames.get(config["master"], "main_frame")
            )

            # 创建组件框架
            frame = ttk.Frame(master)
            if name not in ["header_frame", "footer_frame"]:
                frame.config(border=2, relief="solid")

            # 框架布局配置
            if "grid" in config:
                frame.grid(**config["grid"])
            if "config" in config:
                frame.config(**config["config"])

            # 设置网格权重
            for row, weight in config.get("row_weights", []):
                frame.rowconfigure(row, weight=weight)
            for col, weight in config.get("column_weights", []):
                frame.columnconfigure(col, weight=weight)

            self.frames[name] = frame

    def _create_widgets(self):
        """创建组件元素"""
        for key, config in WIDGET.items():
            # 获取父框架
            master = self.frames.get(config["master"])

            # 创建组件元素（仅 Label 组件）
            if config.get("type") == "Label":
                widget = ttk.Label(master, text=config.get("text", "?"))
                if key not in [
                    "notice_label",
                    "network_label",
                    "statement_label",
                    "copyright_label",
                ]:
                    widget.config(cursor="hand")
                    widget.bind("<Button-1>", lambda e, frame_name=config['master']: self._on_label_click(frame_name))


            # 组件布局配置
            if "grid" in config:
                widget.grid(**config["grid"])
            if "config" in config:
                widget.config(**config["config"])

            self.widgets[key] = widget

    def _on_label_click(self, frame_name):
        """处理标签点击事件"""
        if frame_name == 'basic_frame':
            # 创建模块窗口并隐藏主窗口
            self.toplevel = tk.Toplevel(self.root)
            self.root.withdraw()

            # 实例化模块窗口组件
            self.modules['basic_module'] = Basic(self.toplevel)

            # 绑定模块窗口关闭事件
            self.toplevel.protocol("WM_DELETE_WINDOW", self._show_main_win)
        else:
            messagebox.showinfo(
                message="功能未开放",
                detail="该功能正在开发中...",
            )

    def _show_main_win(self):
        """返回应用主界面"""
        if self.toplevel:
            self.toplevel.destroy()
            self.toplevel = None
        self.root.deiconify()

    def _monitor_network(self):
        """监听网络状态"""
        status = get_network_status()

        # 更新网络状态
        if status["connected"] != self.network_status:
            self.network_status = status["connected"]

            if status["connected"]:
                self.widgets["network_label"].config(text="●", foreground=COLOR_PALETTE['success'])
            else:
                self.widgets["network_label"].config(
                    text="● " + status["message"], foreground=COLOR_PALETTE['error']
                )

        # 定时重复检查（10s）
        self.root.after(10000, self._monitor_network)

    def run(self):
        """运行应用程序的主循环"""
        try:
            self.root.after(100, self._monitor_network)
            self.root.mainloop()
        except Exception as e:
            logging.error(f"程序执行出错: {str(e)}")
            logging.debug(traceback.format_exc())


def main():
    """应用程序主入口函数"""
    # 配置日志级别和格式
    logging.basicConfig(
        level=logging.DEBUG, 
        format="%(filename)s(%(lineno)d)> %(message)s",
        handlers=[
            logging.FileHandler("app_errors.log"),
            logging.StreamHandler()
        ]
    )

    # 创建并运行应用程序
    app = App()
    app.run()


if __name__ == "__main__":
    main()
