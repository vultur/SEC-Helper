# -*- coding: utf-8 -*-
"""GUI模块"""
import os
import requests
import tkinter as tk
from tkinter import ttk
from tkinter import filedialog
from tkinter import messagebox
from functools import partial

from utils import (
    format_bytes,
    format_date,
    format_title,
    get_access_token,
    get_system_paths,
    parse_resource,
    parse_hierarchy,
    save_file,
    set_access_token,
)
from config import AppConfig, GUIConfig

LAYOUT = GUIConfig.LAYOUT
WIDGET = GUIConfig.WIDGET


class GUI:
    """创建和管理应用程序的组件和布局"""

    def __init__(self, root):
        """初始化GUI组件"""
        self.root = root
        self._setup_window()

        # 设置全局请求会话
        self.session = requests.Session()
        self.session.proxies = {"http": None, "https": None}
        self.session.headers.update({"X-ND-AUTH": 'MAC id="0",nonce="0",mac="0"'})

        # 定义应用相关变量
        self.paths = get_system_paths()
        self.status = {}
        self.frames = {}
        self.widgets = {}

        # 定义资源相关变量
        self.documents = {}
        self.trace_ids = {}
        self.variables = {}
        self.materials = {}
        self.resources = {}

        # 创建框架和控件
        self._create_frames()
        self._create_widgets()

        # 初始化资源列表
        self._init_materials()

        # 加载本地访问令牌
        self.access_token = None
        self._load_access_token()

    def _setup_window(self):
        """设置窗口基本属性"""
        # 窗口标题
        self.root.title(AppConfig.WINDOW_TITLE)

        # 窗口属性
        self.root.attributes(
            "-topmost", AppConfig.WINDOW_TOPMOST, "-alpha", AppConfig.WINDOW_ALPHA
        )

        # 窗口大小和居中定位
        win_width, win_height = AppConfig.WINDOW_WIDTH, AppConfig.WINDOW_HEIGHT
        screen_width, screen_height = (
            self.root.winfo_screenwidth(),
            self.root.winfo_screenheight(),
        )
        x, y = (screen_width - win_width) // 2, (screen_height - win_height) // 2
        self.root.geometry(f"{win_width}x{win_height}+{x}+{y}")

        # 根窗口网格权重
        self.root.rowconfigure(0, weight=1)
        self.root.columnconfigure(0, weight=1)

    def _create_frames(self):
        """根据配置动态创建所有框架"""
        for frame_name, frame_config in LAYOUT.items():
            # 获取父框架
            master_name = frame_config["master"]
            if master_name == "root":
                master = self.root
            else:
                master = self.frames.get(master_name)

            # 创建主框架（标签或容器）
            if "text" in frame_config:
                frame = ttk.Labelframe(master, text=frame_config["text"])
            else:
                frame = ttk.Frame(master)

            # 设置框架布局
            if "grid" in frame_config:
                frame.grid(**frame_config["grid"])

            # 设置框架属性
            if "config" in frame_config:
                frame.config(**frame_config["config"])

            # 设置网格权重
            if "row_weights" in frame_config:
                for row, weight in frame_config["row_weights"]:
                    frame.rowconfigure(row, weight=weight)
            if "column_weights" in frame_config:
                for col, weight in frame_config["column_weights"]:
                    frame.columnconfigure(col, weight=weight)

            # 存储框架引用
            self.frames[frame_name] = frame

    def _create_widgets(self):
        """根据配置动态创建所有控件"""
        for widget_key, widget_config in WIDGET.items():

            # 获取父框架
            master_name = widget_config["master"]
            master = self.frames.get(master_name)

            # 获取控件类型
            widget_type = widget_config.get("type")

            # 创建变量（如果需要）
            if widget_type in ["OptionMenu", "Checkbutton", "Progressbar", "Entry"]:
                if widget_type == "Checkbutton":
                    self.variables[widget_key] = tk.BooleanVar(
                        value=widget_config.get("default", True)
                    )
                elif widget_type == "Progressbar":
                    self.variables[widget_key] = tk.DoubleVar(
                        value=widget_config.get("default", 0)
                    )
                else:
                    self.variables[widget_key] = tk.StringVar(
                        value=widget_config.get("default", "")
                    )

            # 创建控件
            if widget_type == "OptionMenu":
                if widget_key == "path_menu":
                    widget_config["options"] = list(self.paths.keys())
                    widget_config["default"] = (
                        widget_config["options"][0]
                        if widget_config["options"]
                        else "- 请选择 -"
                    )

                widget = ttk.OptionMenu(
                    master,
                    self.variables[widget_key],
                    widget_config.get("default", "- 请选择 -"),
                    *widget_config.get("options", []),
                )

                if widget_config["master"] == "material_frame":
                    self.trace_ids[widget_key] = self.variables[widget_key].trace_add(
                        "write", partial(self._update_options, widget_key)
                    )

            elif widget_type == "Checkbutton":
                widget = ttk.Checkbutton(
                    master,
                    text=widget_config.get("text", ""),
                    variable=self.variables[widget_key],
                )

            elif widget_type == "Entry":
                widget = ttk.Entry(master)
                if widget_key == "token_entry":
                    widget.bind("<FocusOut>", self._on_token_focus_out)
                    widget.bind("<FocusIn>", lambda event: event.widget.config(show=""))
                    widget.bind(
                        "<Return>", lambda event: event.widget.master.focus_set()
                    )

            elif widget_type == "Progressbar":
                widget = ttk.Progressbar(master, variable=self.variables[widget_key])

            elif widget_type == "Button":
                widget = ttk.Button(master, text=widget_config.get("text", ""))
                if widget_key == "path_button":
                    widget.config(command=self._browse_directory)
                if widget_key == "download_button":
                    widget.config(command=self._on_download_click)

            elif widget_type == "Label":
                widget = ttk.Label(master, text=widget_config.get("text", ""))

            elif widget_type == "Treeview":
                widget = ttk.Treeview(master, show="headings", selectmode="browse")
                widget["columns"] = list(widget_config["columns"].keys())
                for id, column in widget_config["columns"].items():
                    widget.heading(id, text=column["text"], anchor="center")
                    widget.column(
                        id,
                        width=column["width"],
                        minwidth=column["width"],
                        anchor=column["anchor"],
                    )

            # 设置网格布局
            if "grid" in widget_config:
                widget.grid(**widget_config["grid"])

            # 设置控件属性
            if "config" in widget_config:
                widget.config(**widget_config["config"])

            # 隐藏特殊控件（类别/学段/册次）
            if widget_key in ["category_menu", "stage_menu", "volume_menu"]:
                widget.grid_remove()

            # 存储控件引用
            self.widgets[widget_key] = widget

    def _init_materials(self):
        """初始化资源列表"""
        try:
            material_data = next(iter(self._fetch_materials().values()))
            self.materials = material_data["children"]

            # 加载教材菜单选项
            for material in self.materials.values():
                self.widgets["material_menu"]["menu"].add_command(
                    label=material["tag_name"],
                    command=lambda tag_name=material["tag_name"]: self.variables[
                        "material_menu"
                    ].set(tag_name),
                )

        except requests.RequestException:
            messagebox.showerror(
                message="数据加载异常",
                detail="请检查网络连接或重新打开应用",
            )
        except (ValueError, KeyError):
            messagebox.showerror(
                message="数据解析错误",
                detail="请重新打开应用或稍后再试",
            )
        except Exception:
            messagebox.showerror(
                message="未知错误",
                detail="请重新打开应用或稍后再试",
            )

    def _update_options(self, widget_key, *args):
        """更新选项菜单的选项

        Args:
            widget_key (str): 变量名称
            widget_key (str): 控件名称
        """
        # 是否停止后续迭代
        stop_iteration = False

        # 调整菜单选项层级
        self._adjust_widgets(widget_key)

        # 获取显示菜单名称
        widget_keys = [
            key
            for key, widget in self.widgets.items()
            if (WIDGET[key]["master"] == "material_frame" and widget.winfo_ismapped())
        ]

        # 获取当前菜单层级（遍历层级）
        widget_index = widget_keys.index(widget_key)

        # 重置后续菜单选项
        self._reset_options(widget_keys, widget_index + 1)

        # 清空当前资源列表
        resource_view = self.widgets["resource_view"]
        resource_view.delete(*resource_view.get_children())
        self.widgets["download_button"].config(state="disabled")

        # 重置任务状态标签
        self.status = {}
        self._update_status()

        # 获取子级层级数据
        materials = self.materials
        for i in range(widget_index + 1):
            selected_key = widget_keys[i]
            selected_value = self.variables[selected_key].get()
            try:
                materials = next(
                    material["children"]
                    for material in materials.values()
                    if material["tag_name"] == selected_value
                )
            except StopIteration:
                stop_iteration = True
                break

        # 更新子级菜单选项
        if widget_index < (len(widget_keys) - 1) and not stop_iteration:
            next_key = widget_keys[widget_index + 1]
            next_widget = self.widgets[next_key]

            # 添加子级菜单选项
            for material in materials.values():
                next_widget["menu"].add_command(
                    label=material["tag_name"],
                    command=lambda tag_name=material["tag_name"]: self.variables[
                        next_key
                    ].set(tag_name),
                )

            # 启用子级菜单选项
            next_widget.config(state="normal")

        if widget_index == len(widget_keys) - 1 or stop_iteration:
            # 更新资源列表视图
            self.resources = parse_resource(materials)
            self._update_resources()

            # 更新任务状态标签
            self.status["count_total"] = len(self.resources)
            self.status["size_total"] = sum(
                resource["custom_properties"].get("size", 0)
                for resource in self.resources.values()
            )
            self._update_status()

            # 启用下载按钮状态
            self.widgets["download_button"].config(state="normal")

    def _update_resources(self):
        """插入资源到列表视图"""
        for res in self.resources.values():
            self.widgets["resource_view"].insert(
                "",
                "end",
                res["id"],
                values=(
                    "  " + format_title(res["title"]),
                    (
                        res["provider_list"][0]
                        .get("name", "--")
                        .replace("义务教育信息科技课程教学指南开发课题组", "--")
                        if res["provider_list"]
                        else "--"
                    ),
                    format_bytes(res["custom_properties"].get("size", "")) + "  ",
                ),
            )

    def _download_documents(self, file_url, file_path):
        """下载资源文档"""
        response = requests.get(file_url, stream=True)
        response.raise_for_status()

        with open(file_path, "wb") as file:
            for chunk in response.iter_content(chunk_size=8192):
                file.write(chunk)

    def _update_status(self):
        """更新任务状态标签"""
        status = self.status
        widgets = self.widgets

        # 格式化文件大小
        size_total = format_bytes(status.get("size_total", 0))
        size_completed = format_bytes(status.get("size_completed", 0))
        size_text = f"{size_completed} / {size_total}" if size_completed else size_total

        # 格式化文件数量
        count_total = status.get("count_total", "?")
        count_completed = status.get("count_completed", 0)
        count_text = (
            f"📖  {count_completed} / {count_total} 个文件"
            if count_completed
            else f"📖  {count_total} 个文件"
        )

        # 更新状态标签文本
        if status:
            total_text = count_text + (f"  |  {size_text}" if size_total else "")
            widgets["total_label"].config(text=total_text)
            widgets["speed_label"].config(text=f"{status.get('download_speed', '')}")
            widgets["eta_label"].config(text=f"{status.get('download_eta', '')}")
        else:
            widgets["total_label"].config(text=WIDGET["total_label"]["text"])
            widgets["speed_label"].config(text="")
            widgets["eta_label"].config(text="")

    def _browse_directory(self):
        """自定义下载路径"""
        directory = filedialog.askdirectory(parent=self.root)

        if directory:
            # 获取目录名称
            folder_name = os.path.basename(directory)
            if not folder_name:
                folder_name = "自定义"

            # 设置默认路径
            self.variables["path_menu"].set(folder_name)

    def _adjust_widgets(self, widget_key):
        """调整菜单选项层级"""
        material_value = self.variables["material_menu"].get()
        subject_value = (
            None
            if widget_key == "material_menu"
            else self.variables["subject_menu"].get()
        )
        category_value = (
            None
            if widget_key == "material_menu"
            else self.variables["category_menu"].get()
        )

        # 处理信息科技选项
        provider_menu = self.widgets["provider_menu"]
        is_info_tech = (
            material_value in ["小学", "初中"] and subject_value == "信息科技"
        )

        if is_info_tech:
            provider_menu.grid_remove()
            self._reset_options(["provider_menu"], 0)
            self.widgets["subject_menu"].config(width=48)
        else:
            provider_menu.grid()
            self.widgets["subject_menu"].config(
                width=WIDGET["subject_menu"]["config"]["width"]
            )

        # 处理特殊教育选项
        is_spec_educ = material_value == "特殊教育"
        spec_edu_widgets = {
            "category_menu": is_spec_educ,
            "stage_menu": is_spec_educ and category_value != "培智学校",
            "provider_menu": not is_spec_educ and not is_info_tech,
        }

        for widget_key, visible in spec_edu_widgets.items():
            if not visible:
                self.widgets[widget_key].grid_remove()
                self._reset_options([widget_key], 0)
            else:
                self.widgets[widget_key].grid()

        # 处理高中年级选项
        grade_menu = self.widgets["grade_menu"]
        is_special_subject = subject_value not in ["德语", "法语"]
        is_special_grade = material_value == "高中" and is_special_subject
        if is_special_grade:
            grade_menu.grid_remove()
            self._reset_options(["grade_menu"], 0)
        else:
            grade_menu.grid()

        # 处理特殊教育选项（培智学校 >> 信息技术）
        volume_menu = self.widgets["volume_menu"]
        is_spec_edu_info_tech = (
            is_spec_educ
            and category_value == "培智学校"
            and subject_value == "信息技术"
        )

        if is_spec_edu_info_tech:
            volume_menu.grid()
            grade_menu.grid_remove()
            self._reset_options(["grade_menu"], 0)
        elif is_special_grade:
            grade_menu.grid_remove()
            volume_menu.grid_remove()
            self._reset_options(["grade_menu", "volume_menu"], 0)
        else:
            grade_menu.grid()
            volume_menu.grid_remove()
            self._reset_options(["volume_menu"], 0)

        # 强制渲染菜单选项
        self.frames["material_frame"].update_idletasks()

    def _reset_options(self, widget_keys, start_index):
        """重置剩余菜单控件"""
        for i in range(start_index, len(widget_keys)):
            widget_key = widget_keys[i]
            widget = self.widgets[widget_key]

            # 禁用菜单并清空菜单选项（保留 <全部> 选项）
            widget.config(state="disabled")
            widget["menu"].delete(1, "end")

            # 移除变量跟踪，重置为默认值，然后恢复跟踪
            widget_var = self.variables[widget_key]
            widget_var.trace_remove("write", self.trace_ids[widget_key])
            widget_var.set(WIDGET[widget_key].get("default", ""))
            self.trace_ids[widget_key] = widget_var.trace_add(
                "write", partial(self._update_options, widget_key)
            )

    def _fetch_materials(self):
        """获取教材层级数据

        Returns:
            dict: 教材层级数据字典
        """
        # 获取教材层级数据
        tags_resp = self.session.get(
            "https://s-file-1.ykt.cbern.com.cn/zxx/ndrs/tags/tch_material_tag.json"
        )
        tags_resp.raise_for_status()
        parsed_hier = parse_hierarchy(tags_resp.json().get("hierarchies", []))

        # 获取课本 URL 列表
        list_resp = self.session.get(
            "https://s-file-1.ykt.cbern.com.cn/zxx/ndrs/resources/tch_material/version/data_version.json"
        )
        list_resp.raise_for_status()
        list_data = list_resp.json()["urls"].split(",")

        # 生成课本层级数据
        for url in list_data:
            book_resp = self.session.get(url)
            book_data = book_resp.json()

            for book in book_data:
                # 解析课本路径（专题/电子教材/{学级}/{学科}/{版本}/{年级}/{册次}）
                if len(book["tag_paths"]) > 0:
                    tag_paths = book["tag_paths"][0].split("/")[2:]

                    # 获取课本层级（[电子教材]）
                    temp_hier = parsed_hier[book["tag_paths"][0].split("/")[1]]

                    # 跳过不在层级数据中的课本
                    if not tag_paths[0] in temp_hier["children"]:
                        continue

                    # 解析课本层级
                    for p in tag_paths:
                        temp_hier = temp_hier["children"].get(p, temp_hier)
                    if not temp_hier["children"]:
                        temp_hier["children"] = {}

                    # 插入课本数据
                    temp_hier["children"][book["id"]] = book

        return parsed_hier

    def _fetch_documents(self):
        """获取资源文档数据

        Returns:
            dict: 文档数据字典
        """
        documents = {}
        for res_id in self.resources.keys():
            # 获取资源文档数据
            response = self.session.get(
                f"https://s-file-1.ykt.cbern.com.cn/zxx/ndrv2/resources/tch_material/details/{res_id}.json"
            )
            response.raise_for_status()
            data = response.json()

            # 存储资源文档数据
            documents[res_id] = data

        return documents

    def _load_access_token(self):
        """读取本地访问令牌"""
        access_token = get_access_token()

        if access_token:
            # 设置全局访问令牌
            self.access_token = access_token

            # 更新访问令牌控件
            token_entry = self.widgets["token_entry"]
            token_entry.delete(0, "end")
            token_entry.insert(0, access_token)

            # 更新访问令牌变量
            self.variables["token_entry"].set(access_token)

            # 显示令牌更新提示
            notice_label = self.widgets["notice_label"]
            notice_label.config(text="🔐 令牌读取成功！")
            self.root.after(3000, lambda: notice_label.config(text=""))

            # 更新全局请求会话
            self.session.headers.update(
                {"X-ND-AUTH": f'MAC id="{access_token}",nonce="0",mac="0"'}
            )

    def _on_download_click(self):
        """处理下载按钮点击事件"""
        # self.documents = self._fetch_documents()

        # # 构建文档保存路径
        # save_path = self.paths.get(self.variables["path_menu"].get())

        # # 解析文档下载链接
        # for document in self.documents.values():
        #     file_url = document["ti_storages"][0]
        #     if not self.access_token:
        #         file_url = re.sub(
        #             r"^https?://(?:.+).ykt.cbern.com.cn/(.+)/([\da-f]{8}-[\da-f]{4}-[\da-f]{4}-[\da-f]{4}-[\da-f]{12}).pkg/(.+)\.pdf$",
        #             r"https://c1.ykt.cbern.com.cn/\1/\2.pkg/\3.pdf",
        #             file_url,
        #         )
        #     file_path = os.path.join(save_path, f"{document['title']}.pdf")
        #     thread = threading.Thread(
        #         target=self._download_documents, args=(file_url, file_path)
        #     )
        #     thread.daemon = True
        #     thread.start()

    def _on_token_focus_out(self, event):
        """处理令牌输入失去焦点事件"""
        event.widget.config(show="*")

        # 获取当前输入令牌
        entry_value = event.widget.get()

        # 仅当内容发生变化时才执行更新操作
        if entry_value != self.variables["token_entry"].get():
            # 本地保存访问令牌
            set_access_token(entry_value)

            # 更新全局访问令牌
            self.access_token = entry_value

            # 更新访问令牌变量
            self.variables["token_entry"].set(entry_value)

            # 显示令牌更新提示
            notice_label = self.widgets["notice_label"]
            notice_label.config(
                text="🔐 令牌已保存！" if entry_value else "🔐 令牌已删除！"
            )
            self.root.after(1500, lambda: notice_label.config(text=""))

            # 更新全局请求会话
            self.session.headers.update(
                {"X-ND-AUTH": f'MAC id="{entry_value}",nonce="0",mac="0"'}
            )
