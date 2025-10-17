# -*- coding: utf-8 -*-
"""Basic模块"""
import os
import logging
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
    parse_material,
    save_file,
    set_access_token,
    toggle_widget_state,
)
from config import COLOR_PALETTE, BasicConfig

LAYOUT = BasicConfig.LAYOUT
WIDGET = BasicConfig.WIDGET


class Basic:
    """中小学智慧教育平台资源下载工具"""

    def __init__(self, root, main=None):
        self.root = root
        self.main = main
        self._setup_window()

        # 全局请求会话
        self.session = requests.Session()
        self.session.proxies = {"http": None, "https": None}  # type: ignore
        self.session.headers.update({"X-ND-AUTH": 'MAC id="0",nonce="0",mac="0"'})

        # 定义应用变量
        self.paths = {}
        self.status = {}
        self.frames = {}
        self.widgets = {}

        # 定义业务变量
        self.trace_ids = {}
        self.variables = {}
        self.materials = {}
        self.resources = {}
        self.documents = {}
        self.access_token = None
        self.network_status = {}

        # 创建框架和组件
        self._create_frames()
        self._create_widgets()

        # 初始化模块数据
        self.root.after(3000, self._after_created)

    def _setup_window(self):
        # 设置窗口标题、透明度和置顶状态
        self.root.title("中小学智慧教育平台 - 资源下载工具")
        self.root.attributes("-topmost", False, "-alpha", 0.97)
        self.root.resizable(False, False)

        # 设置窗口大小和居中显示
        win_width, win_height = 800, 600
        screen_width, screen_height = (
            self.root.winfo_screenwidth(),
            self.root.winfo_screenheight(),
        )
        x, y = (screen_width - win_width) // 2, (screen_height - win_height) // 2
        self.root.geometry(f"{win_width}x{win_height}+{x}+{y}")

        # 设置网格权重
        self.root.rowconfigure(0, weight=1)
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

            # 创建组件框架（标签或容器）
            frame = (
                ttk.Labelframe(master, text=config["text"])
                if "text" in config
                else ttk.Frame(master)
            )

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

            # 获取组件类型
            widget_type = config.get("type")

            # 创建组件变量（如果需要）
            if widget_type in ["Checkbutton", "Progressbar", "OptionMenu", "Entry"]:
                if widget_type == "Checkbutton":
                    self.variables[key] = tk.BooleanVar(
                        value=config.get("default", True)
                    )
                elif widget_type == "Progressbar":
                    self.variables[key] = tk.DoubleVar(value=config.get("default", 0))
                else:
                    self.variables[key] = tk.StringVar(value=config.get("default", ""))

            # 创建组件元素（绑定变量及事件）
            if widget_type == "OptionMenu":
                widget = ttk.OptionMenu(
                    master,
                    self.variables[key],
                    config.get("default", "- 请选择 -"),
                    *config.get("options", []),
                )

                # 处理教材选择菜单（绑定变量跟踪）
                if config["master"] == "material_frame":
                    self.trace_ids[key] = self.variables[key].trace_add(
                        "write", partial(self._on_option_change, key)
                    )

            elif widget_type == "Checkbutton":
                widget = ttk.Checkbutton(
                    master,
                    text=config.get("text", "?"),
                    variable=self.variables[key],
                )

            elif widget_type == "Entry":
                widget = ttk.Entry(master)

                # 处理访问令牌输入（绑定事件）
                if key == "token_entry":
                    widget.bind("<FocusOut>", self._on_entry_focus_out)
                    widget.bind("<FocusIn>", lambda e: e.widget.config(show=""))
                    widget.bind("<Return>", lambda e: e.widget.master.focus_set())

            elif widget_type == "Progressbar":
                widget = ttk.Progressbar(master, variable=self.variables[key])

            elif widget_type == "Button":
                widget = ttk.Button(master, text=config.get("text", "?"))

                # 处理目录选择按钮（绑定事件）
                if key == "path_button":
                    widget.config(command=self._on_browse_directory)

                # 处理开始下载按钮（绑定事件）
                elif key == "download_button":
                    widget.config(command=self._on_download_click)

            elif widget_type == "Label":
                widget = ttk.Label(master, text=config.get("text", ""))

            elif widget_type == "Treeview":
                widget = ttk.Treeview(master, show="headings", selectmode="browse")
                widget["columns"] = list(config["columns"].keys())
                for id, column in config["columns"].items():
                    widget.heading(id, text=column["text"], anchor="center")
                    widget.column(
                        id,
                        width=column["width"],
                        minwidth=column["width"],
                        anchor=column["anchor"],
                    )

            # 组件布局配置
            if "grid" in config:
                widget.grid(**config["grid"])
            if "config" in config:
                widget.config(**config["config"])

            # 处理特殊组件（默认隐藏：类别/学段/册次）
            if key in ["category_menu", "stage_menu", "volume_menu"]:
                widget.grid_remove()

            self.widgets[key] = widget

    def _after_created(self):
        """初始化模块数据"""
        self._init_materials()
        self._load_system_paths()
        self._load_access_token()
        self._sync_network_status()

    def _init_materials(self):
        """加载教材资源"""
        try:
            materials = next(iter(self._fetch_materials().values()))  # type: ignore
            self.materials = materials.get("children", {})

            # 加载教材菜单选项
            material_var = self.variables["material_menu"]
            material_menu = self.widgets["material_menu"]

            for material in self.materials.values():
                tag_name = material["tag_name"]
                material_menu["menu"].add_command(
                    label=tag_name,
                    command=lambda tag_name=tag_name: material_var.set(tag_name),
                )

            # 启用教材菜单组件
            material_menu.config(state="normal")
        except Exception as e:
            logging.error(f"教材解析失败: {str(e)}")
            messagebox.showerror(
                message="教材解析失败",
                detail="请重新打开应用或稍后再试",
            )

    def _load_system_paths(self):
        """加载系统公共路径"""
        self.paths = get_system_paths()
        path_menu = self.widgets["path_menu"]

        # 更新下载位置选项
        for folder in self.paths.keys():
            path_menu["menu"].add_command(
                label=folder, command=partial(self.variables["path_menu"].set, folder)
            )

        # 启用路径相关组件，设置默认路径
        path_menu.config(state="normal")
        self.widgets["path_button"].config(state="normal")
        self.widgets["subdir_check"].config(state="normal")
        self.variables["path_menu"].set(next(iter(self.paths.keys())))

    def _load_access_token(self):
        """读取本地访问令牌"""
        access_token = get_access_token()
        token_entry = self.widgets["token_entry"]

        if access_token:
            # 更新令牌组件
            token_entry.delete(0, "end")
            token_entry.insert(0, access_token)

            # 更新令牌变量
            self.access_token = access_token
            self.variables["token_entry"].set(access_token)

            # 提示更新信息
            notice_label = self.widgets["notice_label"]
            notice_label.config(text="🔐 令牌读取成功！")
            self.root.after(3000, lambda: notice_label.config(text=""))

        # 启用令牌相关组件
        token_entry.config(state="normal")
        self.widgets["help_button"].config(state="normal")

    def _sync_network_status(self):
        """同步网络状态"""
        latest_status = self.main.network_status  # type: ignore

        # 更新网络状态（仅当状态改变时）
        if latest_status["connected"] != self.network_status.get("connected", None):
            if latest_status["connected"]:
                self.widgets["status_label"].config(
                    text="●", foreground=COLOR_PALETTE["success"]
                )
            else:
                self.widgets["status_label"].config(
                    text="● " + latest_status["message"],
                    foreground=COLOR_PALETTE["error"],
                )
            self.network_status = latest_status

        # 定时重复检查（10s）
        self.root.after(5000, self._sync_network_status)

    def _on_option_change(self, widget_key, *args):
        """处理教材菜单级联更新

        Args:
            widget_key (str): 控件名称
        """
        # 是否停止后续迭代
        stop_iteration = False

        # 更新菜单级联状态
        self._update_menu_state(widget_key)

        # 获取当前可见菜单
        widget_keys = [
            key
            for key, widget in self.widgets.items()
            if (WIDGET[key]["master"] == "material_frame" and widget.winfo_ismapped())
        ]

        # 获取当前菜单索引（作为遍历起始层级）
        widget_index = widget_keys.index(widget_key)

        # 重置后续菜单选项
        self._reset_menu_option(widget_keys, widget_index + 1)

        # 清空当前资源列表
        resource_view = self.widgets["resource_view"]
        resource_view.delete(*resource_view.get_children())
        self.widgets["download_button"].config(state="disabled")

        # 重置下载按钮状态
        self.resources = {}
        self.widgets["download_button"].config(state="disabled")

        # 重置任务状态标签
        self.status = {}
        self._update_status_label()

        # 获取级联菜单数据
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

        # 更新级联菜单组件
        if widget_index < (len(widget_keys) - 1) and not stop_iteration:
            next_key = widget_keys[widget_index + 1]
            next_widget = self.widgets[next_key]

            # 添加级联菜单选项
            for material in materials.values():
                next_widget["menu"].add_command(
                    label=material["tag_name"],
                    command=lambda tag_name=material["tag_name"]: self.variables[
                        next_key
                    ].set(tag_name),
                )

            # 启用级联菜单组件
            next_widget.config(state="normal")

        # 更新资源列表视图
        if widget_index == len(widget_keys) - 1 or stop_iteration:
            try:
                self.resources = parse_resource(materials)
                self._update_resource_view()
            except Exception as e:
                logging.error(f"资源解析失败: {str(e)}")
                messagebox.showerror(
                    message="资源解析失败",
                    detail="请重新打开应用或稍后再试",
                )

            # 更新任务状态标签
            self.status["size_total"] = sum(
                resource["custom_properties"].get("size", 0)
                for resource in self.resources.values()  # type: ignore
            )
            self.status["count_total"] = len(self.resources)  # type: ignore
            self._update_status_label()

            # 启用下载按钮组件
            if self.resources:
                self.widgets["download_button"].config(state="normal")

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

    def _on_browse_directory(self):
        """自定义下载路径"""
        directory = filedialog.askdirectory(parent=self.root)

        if directory:
            # 获取目录名称
            folder_name = os.path.basename(directory)
            if not folder_name:
                folder_name = "自定义"

            # 设置默认路径
            self.variables["path_menu"].set(folder_name)

    def _on_entry_focus_out(self, event):
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

    def _download_documents(self, file_url, file_path):
        """下载资源文档"""
        response = requests.get(file_url, stream=True)
        response.raise_for_status()

        with open(file_path, "wb") as file:
            for chunk in response.iter_content(chunk_size=8192):
                file.write(chunk)

    def _fetch_materials(self):
        """获取教材层级数据

        Returns:
            dict: 教材数据字典
        """
        try:
            # 获取教材目录层级（专题/电子教材/{学级}/{学科}/{版本}/{年级}）
            tag_data = self.session.get(BasicConfig.TAG_URL).json()
            materials = parse_material(tag_data.get("hierarchies", []))

            # 获取教材资源链接
            url_data = self.session.get(BasicConfig.RES_URL).json()
            urls = url_data.get("urls", "").split(",")

            # 生成教材层级数据
            for url in filter(None, urls):
                try:
                    res_data = self.session.get(url).json()
                    for res in res_data:
                        # 获取资源层级路径（专题/电子教材/{学级}/{学科}/{版本}/{年级}/{册次}）
                        tag_paths = res.get("tag_paths", [])
                        if not tag_paths or not tag_paths[0]:
                            continue

                        # 获取教材层级节点（使用“电子教材”为根节点）
                        path_parts = tag_paths[0].split("/")
                        temp_materials = materials[path_parts[1]]  # type: ignore

                        # 跳过不在层级数据中的资源
                        res_paths = path_parts[2:]
                        if res_paths[0] not in temp_materials.get("children", {}):
                            continue

                        # 遍历资源层级路径（{学级}/{学科}/{版本}/{年级}/{册次}）
                        for path in res_paths:
                            temp_materials = temp_materials["children"].get(
                                path, temp_materials
                            )

                        # 确保当前层级包含子节点
                        if not temp_materials["children"]:
                            temp_materials["children"] = {}

                        # 在当前层级插入资源数据
                        temp_materials["children"][res["id"]] = res
                except requests.RequestException as e:
                    logging.warning(f"获取教材数据失败 ({url}): {str(e)}")
                    continue

            return materials
        except requests.RequestException as e:
            logging.error(f"获取教材目录失败: {e}")
            messagebox.showerror(
                message="获取教材失败",
                detail=f"请检查网络连接或重新打开应用",
            )
            return {}

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

    def _update_resource_view(self):
        """更新资源列表视图"""
        for resource in self.resources.values():
            provider_list = resource.get("provider_list", [])
            provider_name = (
                provider_list[0].get("name", "--") if provider_list else "--"
            )
            FILTER_PROVIDER = "义务教育信息科技课程教学指南开发课题组"

            custom_properties = resource.get("custom_properties", {})

            self.widgets["resource_view"].insert(
                "",
                "end",
                resource["id"],
                values=(
                    f"  {format_title(resource.get('title', '?'))}",
                    provider_name.replace(FILTER_PROVIDER, "--"),
                    f"{format_bytes(custom_properties.get('size', ''))}  ",
                ),
            )

    def _update_menu_state(self, widget_key):
        """更新菜单组件状态"""
        material_value = self.variables["material_menu"].get()
        if widget_key == "material_menu":
            subject_value = category_value = None
        else:
            subject_value = self.variables["subject_menu"].get()
            category_value = self.variables["category_menu"].get()

        # 处理信息科技选项
        is_info_tech = (
            material_value in ["小学", "初中"] and subject_value == "信息科技"
        )
        if is_info_tech:
            toggle_widget_state(self.widgets["provider_menu"], False)
            self._reset_menu_option(["provider_menu"], 0)
            subject_width = 48
        else:
            toggle_widget_state(self.widgets["provider_menu"], True)
            subject_width = WIDGET["subject_menu"]["config"]["width"]

        self.widgets["subject_menu"].config(width=subject_width)

        # 处理特殊教育选项
        is_spec_educ = material_value == "特殊教育"
        spec_edu_widgets = {
            "category_menu": is_spec_educ,
            "stage_menu": is_spec_educ and category_value != "培智学校",
            "provider_menu": not (is_spec_educ or is_info_tech),
        }

        for widget_key, visible in spec_edu_widgets.items():
            toggle_widget_state(self.widgets[widget_key], visible)
            self._reset_menu_option([widget_key], 0) if not visible else None

        # 处理高中年级菜单和特殊教育信息技术
        is_special_subject = subject_value not in ["德语", "法语"]
        is_special_grade = material_value == "高中" and is_special_subject
        is_spec_edu_info_tech = (
            is_spec_educ
            and category_value == "培智学校"
            and subject_value == "信息技术"
        )

        # 处理年级菜单（显示条件：高中特殊学科或特殊教育非信息技术）
        grade_visible = not (is_special_grade or is_spec_edu_info_tech)
        toggle_widget_state(self.widgets["grade_menu"], grade_visible)
        self._reset_menu_option(["grade_menu"], 0) if not grade_visible else None

        # 处理册次菜单（显示条件：特殊教育信息技术）
        volume_visible = is_spec_edu_info_tech
        toggle_widget_state(self.widgets["volume_menu"], volume_visible)
        self._reset_menu_option(["volume_menu"], 0) if not volume_visible else None

        # 强制渲染以更新菜单组件状态
        self.frames["material_frame"].update_idletasks()

    def _update_status_label(self):
        """更新任务状态标签"""

        # 格式化文件大小
        size_total = format_bytes(self.status.get("size_total", 0))
        size_completed = format_bytes(self.status.get("size_completed", 0))
        size_text = f"{size_completed} / {size_total}" if size_completed else size_total

        # 格式化文件数量
        count_total = self.status.get("count_total", "?")
        count_completed = self.status.get("count_completed", 0)
        count_text = (
            f"📖  {count_completed} / {count_total} 个文件"
            if count_completed
            else f"📖  {count_total} 个文件"
        )

        # 更新状态标签文本
        if self.status:
            total_text = count_text + (f"  |  {size_text}" if size_total else "")
            self.widgets["total_label"].config(text=total_text)
            self.widgets["speed_label"].config(
                text=f"{self.status.get('download_speed', '')}"
            )
            self.widgets["eta_label"].config(
                text=f"{self.status.get('download_eta', '')}"
            )
        else:
            self.widgets["total_label"].config(
                text=WIDGET["total_label"].get("text", "")
            )
            self.widgets["speed_label"].config(text="")
            self.widgets["eta_label"].config(text="")

    def _reset_menu_option(self, widget_keys, start_index):
        """重置剩余教材菜单选项"""
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
                "write", partial(self._on_option_change, widget_key)
            )
