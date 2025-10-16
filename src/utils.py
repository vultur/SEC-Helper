import os
import json
import datetime
import platform
import requests


def parse_material(materials):
    """解析教材层级数据

    Args:
        materials: 教材层级数据

    Returns:
        dict: 教材数据字典 {tag_id: {'tag_name': str, 'children': dict}}
    """
    if not materials:
        return None

    parsed = {}
    for m in materials:
        for c in m["children"]:
            parsed[c["tag_id"]] = {
                "tag_name": c["tag_name"],
                "children": parse_material(c["hierarchies"]),
            }

    return parsed


def parse_resource(materials):
    """解析教材资源数据

    Args:
        materials: 教材层级数据

    Returns:
        dict: 资源数据字典 {res_id: res_details}
    """
    # if not materials:
    #     return None

    parsed = {}
    for res in materials.values():
        if "id" in res:
            parsed[res["id"]] = res
        elif "children" in res:
            children = parse_resource(res["children"])
            parsed.update(children)  # type: ignore

    return parsed


def format_bytes(bytes_value):
    """格式化字节大小"""
    if bytes_value == 0:
        return 0

    try:
        units = ["B", "KB", "MB", "GB", "TB"]
        size = float(bytes_value)
        unit_index = 0
        while size >= 1024 and unit_index < len(units) - 1:
            size /= 1024
            unit_index += 1
        return f"{size:.2f} {units[unit_index]}"
    except (ValueError, TypeError):
        return "--"


def format_title(title):
    """格式化资源标题"""
    prefixes = ["（根据2022年版课程标准修订）", "(根据2022年版课程标准修订)"]

    if "主义思想" in title:
        title = title.split("主义思想")[-1]

    for prefix in prefixes:
        if prefix in title:
            title = title.replace(prefix, "")

    return title.strip()


def format_date(date_str):
    """格式化日期字符串"""
    if not date_str:
        return "--"

    date_str = date_str[:-5] + date_str[-5:-2] + ":" + date_str[-2:]
    return datetime.datetime.fromisoformat(date_str).strftime("%Y-%m-%d")


def set_access_token(token: str):
    """设置访问令牌"""
    os_name = platform.system()

    if os_name == "Windows":
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, "Software\\sec-tools") as key:
            winreg.SetValueEx(key, "AccessToken", 0, winreg.REG_SZ, token)
    elif os_name in ("Linux", "Darwin"):
        base_path = os.path.expanduser("~")
        rel_path = (
            ".config/sec-tools/data.json"
            if os_name == "Linux"
            else "Library/Application Support/sec-tools/data.json"
        )
        file_path = os.path.join(base_path, rel_path)

        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "w") as f:
            json.dump({"access_token": token}, f, indent=4)


def get_access_token():
    """获取本地访问令牌"""
    token = ""
    os_name = platform.system()

    if os_name == "Windows":
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, "Software\\sec-tools", 0, winreg.KEY_READ
        ) as key:
            token, _ = winreg.QueryValueEx(key, "AccessToken")
    elif os_name in ("Linux", "Darwin"):
        base_path = os.path.expanduser("~")
        rel_path = (
            ".config/sec-tools/data.json"
            if os_name == "Linux"
            else "Library/Application Support/sec-tools/data.json"
        )
        target_file = os.path.join(base_path, rel_path)

        if os.path.exists(target_file):
            with open(target_file, "r") as f:
                token = json.load(f).get("access_token")
    return token


def get_system_paths():
    """获取系统默认目录路径

    Returns:
        dict: 路径字典
    """
    # 基本路径设置
    paths = {"user": os.path.expanduser("~")}
    os_name = platform.system()

    # 通用路径映射
    default_paths = {
        "documents": "Documents",
        "pictures": "Pictures",
        "music": "Music",
        "downloads": "Downloads",
        "desktop": "Desktop",
        "videos": "Movies" if os_name == "Darwin" else "Videos",
    }

    # 初始化所有路径
    for key, folder in default_paths.items():
        paths[key] = os.path.join(paths["user"], folder)

    # 平台特定路径处理
    if os_name == "Windows":
        if "USERPROFILE" in os.environ:
            paths["user"] = os.environ["USERPROFILE"]
            paths["documents"] = os.environ.get(
                "DOCUMENTS", os.path.join(os.environ["USERPROFILE"], "Documents")
            )

    elif os_name == "Darwin":
        try:
            from AppKit import (
                NSSearchPathForDirectoriesInDomains,
                NSUserDomainMask,
                NSDocumentDirectory,
                NSPicturesDirectory,
                NSMusicDirectory,
                NSMoviesDirectory,
                NSDownloadsDirectory,
                NSDesktopDirectory,
            )

            dir_map = {
                "documents": NSDocumentDirectory,
                "pictures": NSPicturesDirectory,
                "music": NSMusicDirectory,
                "videos": NSMoviesDirectory,
                "downloads": NSDownloadsDirectory,
                "desktop": NSDesktopDirectory,
            }

            for key, dir_type in dir_map.items():
                paths[key] = NSSearchPathForDirectoriesInDomains(
                    dir_type, NSUserDomainMask, True
                )[0]
        except ImportError:
            pass

    elif os_name == "Linux":
        xdg_map = {
            "documents": "XDG_DOCUMENTS_DIR",
            "pictures": "XDG_PICTURES_DIR",
            "music": "XDG_MUSIC_DIR",
            "videos": "XDG_VIDEOS_DIR",
            "downloads": "XDG_DOWNLOAD_DIR",
            "desktop": "XDG_DESKTOP_DIR",
        }

        for key, env_var in xdg_map.items():
            if env_var in os.environ:
                paths[key] = os.environ[env_var].replace("$HOME", paths["user"])

    # 规范化所有路径
    for key in paths:
        paths[key] = os.path.normpath(os.path.abspath(paths[key]))

    return {
        "🗂️ 下载": paths["downloads"],
        "🗂️ 文档": paths["documents"],
        "🗂️ 视频": paths["videos"],
        "🗂️ 音乐": paths["music"],
        "🗂️ 图片": paths["pictures"],
        "🗂️ 桌面": paths["desktop"],
    }


def get_network_status():
    """获取当前网络状态

    Returns:
        dict: 包含网络状态信息的字典
    """
    status = {"connected": False, "message": "网络连接未知"}

    try:
        response = requests.get(
            "https://www.baidu.com", timeout=5, allow_redirects=True
        )
        if response.status_code == 200:
            status["connected"] = True
            status["message"] = "网络连接正常"
    except requests.exceptions.RequestException:
        status["message"] = "网络连接异常"

    return status


def toggle_widget_state(widget, visible):
    widget.grid() if visible else widget.grid_remove()


def save_file(data, filename):
    """保存数据到文件"""
    save_path = os.path.join(os.path.dirname(__file__), filename)

    try:
        with open(save_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"数据已成功保存到: {save_path}")
    except Exception as e:
        print(f"保存数据失败: {str(e)}")
