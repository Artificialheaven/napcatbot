import importlib
import pkgutil
import inspect
import websockets
import globals
import sys
import os


def get_plugins_path():
    """获取 plugins 目录路径（兼容打包后的环境）"""
    if getattr(sys, 'frozen', False):
        # 打包后的环境
        application_path = os.path.dirname(sys.executable)
    else:
        # 开发环境
        application_path = os.path.dirname(os.path.abspath(__file__))
    
    return os.path.join(application_path, 'plugins')


class PluginBotWrapper:
    """Bot包装器，自动注入插件名称"""
    
    def __init__(self, bot_instance, plugin_name):
        self._bot = bot_instance
        self._plugin_name = plugin_name
        # 创建专属Logger，固定插件名为来源
        self.Logger = PluginLogger(bot_instance.Logger.add_log, plugin_name)
    
    async def send_message(self, message, target_id=None, message_type="private", **kwargs):
        """发送消息（自动注入plugin_name）"""
        return await self._bot.send_message(
            message, target_id, message_type, 
            plugin_name=self._plugin_name
        )
    
    async def get_group_list(self, no_cache=False):
        """获取群列表"""
        return await self._bot.get_group_list(
            plugin_name=self._plugin_name, 
            no_cache=no_cache
        )
    
    async def get_friend_list(self):
        """获取好友列表"""
        return await self._bot.get_friend_list(
            plugin_name=self._plugin_name
        )
    
    async def get_group_info(self, group_id, no_cache=False):
        """获取群信息"""
        return await self._bot.get_group_info(
            group_id, 
            plugin_name=self._plugin_name, 
            no_cache=no_cache
        )
    
    async def get_group_member_list(self, group_id, no_cache=False):
        """获取群成员列表"""
        return await self._bot.get_group_member_list(
            group_id, 
            plugin_name=self._plugin_name, 
            no_cache=no_cache
        )
    
    async def get_group_member_info(self, group_id, user_id, no_cache=False):
        """获取群成员信息"""
        return await self._bot.get_group_member_info(
            group_id, user_id, 
            plugin_name=self._plugin_name, 
            no_cache=no_cache
        )
    
    async def get_login_info(self):
        """获取登录信息"""
        return await self._bot.get_login_info(
            plugin_name=self._plugin_name
        )
    
    async def call_api(self, action, params=None):
        """通用API调用"""
        return await self._bot.call_api(
            action, params, 
            plugin_name=self._plugin_name
        )
    
    async def call_api_parallel(self, api_calls):
        """并行调用API"""
        return await self._bot.call_api_parallel(
            api_calls, 
            plugin_name=self._plugin_name
        )
    
    async def call_api_batch(self, action, params_list):
        """批量调用API"""
        return await self._bot.call_api_batch(
            action, params_list, 
            plugin_name=self._plugin_name
        )
    
    @property
    def websocket(self):
        return self._bot.websocket
    
    @property
    def pending_requests(self):
        return self._bot.pending_requests
    
    @property
    def bot_qq(self):
        return self._bot.bot_qq


class PluginLogger:
    """插件专属Logger，固定来源为插件名"""
    
    def __init__(self, add_log_callback, plugin_name):
        self.add_log = add_log_callback
        self.plugin_name = plugin_name

    def info(self, response, source, content):
        """普通日志 - 来源强制为插件名"""
        self.add_log(response, self.plugin_name, content, '默认')

    def warning(self, response, source, content):
        """警告日志 - 来源强制为插件名"""
        self.add_log(response, self.plugin_name, content, '黄色')

    def error(self, response, source, content):
        """错误日志 - 来源强制为插件名"""
        self.add_log(response, self.plugin_name, content, '红色')

    def custom(self, response, source, content, color):
        """自定义日志 - 来源强制为插件名"""
        self.add_log(response, self.plugin_name, content, color)


class PluginManager:
    """插件管理器"""
    
    def __init__(self, websocket: websockets.ClientConnection):
        self.websocket = websocket
        self.plugins = {}
        self.plugin_info = {}
        self.event_handlers = {}
    
    def load_all_plugins(self):
        """加载 plugins 目录下的所有插件"""
        try:
            # 动态导入 plugins 包
            plugins_path = get_plugins_path()
            
            # 将 plugins 目录添加到 sys.path
            if plugins_path not in sys.path:
                sys.path.insert(0, os.path.dirname(plugins_path))
            
            import plugins
            
            # 遍历 plugins 包中的所有模块
            for importer, modname, ispkg in pkgutil.iter_modules(plugins.__path__, plugins.__name__ + "."):
                # 跳过 __pycache__ 和其他特殊目录
                if '__pycache__' in modname:
                    continue
                    
                try:
                    self.load_plugin(modname)
                    print(f"成功加载插件: {modname}")
                except Exception as e:
                    print(f"加载插件 {modname} 失败: {e}")
                    import traceback
                    traceback.print_exc()
            
            print(f"共加载 {len(self.plugins)} 个插件")
        except Exception as e:
            print(f"加载插件时出错: {e}")
            import traceback
            traceback.print_exc()
    
    def load_plugin(self, module_name: str):
        """加载单个插件"""
        # 导入模块
        module = importlib.import_module(module_name)
        
        # 查找模块中的 main 类
        for name, obj in inspect.getmembers(module):
            if name == 'main' and inspect.isclass(obj):
                # 为插件创建专属的 Bot 包装器（自动注入插件名）
                plugin_bot_wrapper = PluginBotWrapper(globals.bot_instance, module_name.split('.')[-1])
                
                # 实例化插件（传入 websocket 和包装后的bot）
                plugin_instance = obj(self.websocket, plugin_bot_wrapper)
                
                # 存储插件实例
                plugin_key = module_name.split('.')[-1]
                self.plugins[plugin_key] = plugin_instance
                
                # 获取插件信息
                plugin_name = getattr(plugin_instance, 'name', plugin_key)
                # 更新包装器中的插件名为实际名称
                plugin_bot_wrapper._plugin_name = plugin_name
                plugin_bot_wrapper.Logger.plugin_name = plugin_name
                
                plugin_info = {
                    'name': plugin_name,
                    'description': getattr(plugin_instance, 'description', '暂无描述'),
                    'version': getattr(plugin_instance, 'version', '1.0.0'),
                    'enabled': True,
                    'module_name': module_name
                }
                self.plugin_info[plugin_key] = plugin_info
                
                # 调用插件的 on_start 方法（如果存在）
                if hasattr(plugin_instance, 'on_start'):
                    try:
                        on_start_method = getattr(plugin_instance, 'on_start')
                        if inspect.iscoroutinefunction(on_start_method):
                            # 如果是异步方法，创建任务执行
                            import asyncio
                            asyncio.create_task(self._safe_call_on_start(on_start_method, plugin_name))
                            print(f"[{plugin_name}] on_start 异步任务已创建")
                        else:
                            # 如果是同步方法，直接调用
                            on_start_method()
                            print(f"[{plugin_name}] on_start 已调用")
                    except Exception as e:
                        print(f"[{plugin_name}] on_start 调用失败: {e}")
                        import traceback
                        traceback.print_exc()
                
                # 注册插件的事件监听器
                if hasattr(plugin_instance, 'regisiter'):
                    handlers = plugin_instance.regisiter()
                    for handler in handlers:
                        event_type = handler['listen']
                        callback = handler['function']
                        
                        if event_type not in self.event_handlers:
                            self.event_handlers[event_type] = []
                        
                        # 保存插件名称和处理器的映射
                        self.event_handlers[event_type].append({
                            'callback': callback,
                            'plugin_name': plugin_name,
                            'plugin_key': plugin_key
                        })
                
                break
    
    async def _safe_call_on_start(self, on_start_method, plugin_name):
        """安全地调用异步 on_start 方法"""
        try:
            await on_start_method()
            print(f"[{plugin_name}] on_start 执行完成")
        except Exception as e:
            print(f"[{plugin_name}] on_start 执行失败: {e}")
            import traceback
            traceback.print_exc()
    
    def get_event_handlers(self, event_type: str) -> list:
        """获取指定事件类型的所有处理函数"""
        return self.event_handlers.get(event_type, [])
    
    def get_plugin_list(self) -> dict:
        """获取所有插件信息"""
        return self.plugin_info
    
    def enable_plugin(self, plugin_name: str):
        """启用插件"""
        if plugin_name in self.plugin_info:
            self.plugin_info[plugin_name]['enabled'] = True
            return True
        return False
    
    def disable_plugin(self, plugin_name: str):
        """禁用插件"""
        if plugin_name in self.plugin_info:
            self.plugin_info[plugin_name]['enabled'] = False
            # 清理事件处理器
            for event_type in list(self.event_handlers.keys()):
                self.event_handlers[event_type] = [
                    h for h in self.event_handlers[event_type]
                    if not (hasattr(h['callback'], '__self__') and 
                        h['callback'].__self__.__class__.__module__.split('.')[-1] == plugin_name)
                ]
                if not self.event_handlers[event_type]:
                    del self.event_handlers[event_type]
            return True
        return False
    
    def reload_plugin(self, plugin_name: str):
        """重新加载指定插件"""
        if plugin_name in self.plugins:
            module_name = f"plugins.{plugin_name}"
            try:
                # 移除旧插件
                del self.plugins[plugin_name]
                
                # 重新加载模块
                module = importlib.import_module(module_name)
                importlib.reload(module)
                
                # 重新实例化
                self.load_plugin(module_name)
                print(f"插件 {plugin_name} 重新加载成功")
                return True
            except Exception as e:
                print(f"重新加载插件 {plugin_name} 失败: {e}")
                return False
        return False
    
    def unload_plugin(self, plugin_name: str):
        """卸载指定插件"""
        if plugin_name in self.plugins:
            del self.plugins[plugin_name]
            
            # 清理事件处理器
            for event_type in list(self.event_handlers.keys()):
                self.event_handlers[event_type] = [
                    h for h in self.event_handlers[event_type]
                    if h['plugin_key'] != plugin_name
                ]
                if not self.event_handlers[event_type]:
                    del self.event_handlers[event_type]
            
            print(f"插件 {plugin_name} 已卸载")
            return True
        return False


# 创建全局插件管理器实例
_plugin_manager = None


def get_plugin_manager() -> PluginManager:
    """获取插件管理器实例"""
    return _plugin_manager


def init_plugin_manager(websocket: websockets.ClientConnection):
    """初始化插件管理器并加载所有插件"""
    global _plugin_manager
    _plugin_manager = PluginManager(websocket)
    _plugin_manager.load_all_plugins()
    return _plugin_manager


