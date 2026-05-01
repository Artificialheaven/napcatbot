import json
import os
import sys


def get_application_path():
    """获取应用程序路径（兼容打包后的环境）"""
    if getattr(sys, 'frozen', False):
        # 打包后的环境
        return os.path.dirname(sys.executable)
    else:
        # 开发环境
        return os.path.dirname(os.path.abspath(__file__))


# 默认配置
default_config = {
    "show_heartbeat": True,
    "ws_address": "ws://localhost:8080",
    "token": "",
    "use_plugin_venv": True,
    "plugin_venv_python_version": "auto",
    "max_reconnect_attempts": 0,
    "reconnect_base_delay": 2,
    "reconnect_max_delay": 60
}

# 配置文件路径（使用绝对路径，兼容打包环境）
app_path = get_application_path()
config_file = os.path.join(app_path, 'config.json')

# 全局配置字典
conf = {}

# 加载配置
def load_config():
    global conf
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                conf = json.load(f)
            # 合并默认配置，确保所有键都存在
            for key, value in default_config.items():
                if key not in conf:
                    conf[key] = value
            print("配置文件加载成功")
        except Exception as e:
            print(f"配置文件加载失败: {e}")
            print("使用默认配置并备份原文件")
            # 备份原文件
            if os.path.exists(config_file):
                backup_file = config_file + '.bak'
                os.rename(config_file, backup_file)
                print(f"原配置文件已备份为 {backup_file}")
            conf = default_config.copy()
            save_config()
    else:
        print("配置文件不存在，使用默认配置")
        conf = default_config.copy()
        save_config()

# 保存配置
def save_config():
    try:
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(conf, f, indent=4, ensure_ascii=False)
        print("配置保存成功")
    except Exception as e:
        print(f"配置保存失败: {e}")

# 初始化配置
load_config()
