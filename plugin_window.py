import dearpygui.dearpygui as dpg


def enable_plugin(sender, app_data, user_data):
    """启用/禁用插件"""
    from plugin_loader import get_plugin_manager
    
    plugin_name = user_data
    enabled = dpg.get_value(f"plugin_enabled_{plugin_name}")
    status_tag = f"plugin_status_{plugin_name}"
    
    plugin_manager = get_plugin_manager()
    if plugin_manager:
        if enabled:
            plugin_manager.enable_plugin(plugin_name)
            status = "已启用"
            color = [0, 255, 0, 255]
        else:
            plugin_manager.disable_plugin(plugin_name)
            status = "已禁用"
            color = [255, 0, 0, 255]
        
        dpg.set_value(status_tag, f"状态: {status}")
        dpg.configure_item(status_tag, color=color)
        print(f"插件 {plugin_name} {status}")
    else:
        print("插件管理器未初始化")


def refresh_plugin_list():
    """刷新插件列表显示"""
    from plugin_loader import get_plugin_manager
    
    plugin_manager = get_plugin_manager()
    
    # 清除旧的插件列表容器
    if dpg.does_item_exist("plugin_list_container"):
        dpg.delete_item("plugin_list_container")
    
    # 创建新的容器
    with dpg.child_window(height=280, tag="plugin_list_container", parent="plugin_window"):
        if not plugin_manager or not plugin_manager.get_plugin_list():
            dpg.add_text("暂无插件", color=[150, 150, 150, 255])
            return
        
        plugin_list = plugin_manager.get_plugin_list()
        for i, (plugin_key, info) in enumerate(plugin_list.items()):
            with dpg.group(tag=f"plugin_group_{plugin_key}"):
                with dpg.group(horizontal=True):
                    dpg.add_text(f"{i + 1}. {info['name']} (v{info['version']})")
                    dpg.add_checkbox(
                        label="启用",
                        tag=f"plugin_enabled_{plugin_key}",
                        default_value=info['enabled'],
                        callback=enable_plugin,
                        user_data=plugin_key
                    )
                
                dpg.add_text(f"描述: {info['description']}", color=[200, 200, 200, 255])
                status_tag = f"plugin_status_{plugin_key}"
                status_color = [0, 255, 0, 255] if info['enabled'] else [255, 0, 0, 255]
                status_text = "状态: 已启用" if info['enabled'] else "状态: 已禁用"
                dpg.add_text(status_text, tag=status_tag, color=status_color)
                dpg.add_separator()


def create_plugin_window():
    """创建插件窗口"""
    from plugin_loader import get_plugin_manager
    
    plugin_manager = get_plugin_manager()
    
    with dpg.window(
            label="插件管理",
            width=500,
            height=450,
            tag="plugin_window",
            pos=[250, 50],
            on_close=lambda: dpg.hide_item("plugin_window")
    ):
        dpg.add_text("插件管理", color=[255, 255, 0, 255])
        dpg.add_separator()
        
        # 插件列表容器（动态填充）
        with dpg.child_window(height=280, tag="plugin_list_container"):
            if not plugin_manager or not plugin_manager.get_plugin_list():
                dpg.add_text("暂无插件，请将插件放入 plugins 目录", color=[150, 150, 150, 255])
            else:
                plugin_list = plugin_manager.get_plugin_list()
                for i, (plugin_key, info) in enumerate(plugin_list.items()):
                    with dpg.group(tag=f"plugin_group_{plugin_key}"):
                        with dpg.group(horizontal=True):
                            dpg.add_text(f"{i + 1}. {info['name']} (v{info['version']})")
                            dpg.add_checkbox(
                                label="启用",
                                tag=f"plugin_enabled_{plugin_key}",
                                default_value=info['enabled'],
                                callback=enable_plugin,
                                user_data=plugin_key
                            )
                        
                        dpg.add_text(f"描述: {info['description']}", color=[200, 200, 200, 255])
                        status_tag = f"plugin_status_{plugin_key}"
                        status_color = [0, 255, 0, 255] if info['enabled'] else [255, 0, 0, 255]
                        status_text = "状态: 已启用" if info['enabled'] else "状态: 已禁用"
                        dpg.add_text(status_text, tag=status_tag, color=status_color)
                        dpg.add_separator()

        dpg.add_spacer(height=10)

        # 插件管理按钮
        with dpg.group(horizontal=True):
            dpg.add_button(label="刷新列表", width=120, height=35, callback=refresh_plugin_list)
            dpg.add_button(label="安装新插件", width=120, height=35)
            dpg.add_button(label="更新插件", width=120, height=35)

        dpg.add_spacer(height=10)

        # 插件目录显示
        dpg.add_text("插件目录: ./plugins", color=[150, 150, 255, 255])

    # 默认隐藏插件窗口
    dpg.hide_item("plugin_window")

    return "plugin_window"