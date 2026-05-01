import importlib
import pkgutil
import inspect
import websockets
import globals
import sys
import os
import subprocess


def get_plugins_path():
    """获取 plugins 目录路径（兼容打包后的环境）"""
    if getattr(sys, 'frozen', False):
        # 打包后的环境
        application_path = os.path.dirname(sys.executable)
    else:
        # 开发环境
        application_path = os.path.dirname(os.path.abspath(__file__))
    
    return os.path.join(application_path, 'plugins')


def find_python_interpreter():
    """查找系统中的 Python 解释器"""
    # 优先使用当前运行的 Python
    python_exe = sys.executable
    
    # 验证是否可用
    try:
        result = subprocess.run(
            [python_exe, '--version'],
            capture_output=True,
            timeout=5
        )
        if result.returncode == 0:
            print(f"找到 Python 解释器: {python_exe}")
            return python_exe
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    
    # 尝试其他常见路径
    python_paths = [
        'python',
        'python3',
        'py',
    ]
    
    if sys.platform == 'win32':
        python_paths.extend([
            'C:/Python39/python.exe',
            'C:/Python310/python.exe',
            'C:/Python311/python.exe',
            'C:/Python312/python.exe',
        ])
    
    for python_path in python_paths:
        try:
            result = subprocess.run(
                [python_path, '--version'],
                capture_output=True,
                timeout=5
            )
            if result.returncode == 0:
                print(f"找到 Python 解释器: {python_path}")
                return python_path
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    
    return None


def check_package_in_lib(lib_path: str, package_name: str) -> bool:
    """
    检查包是否在指定的 lib 目录中安装
    
    :param lib_path: lib 目录路径
    :param package_name: 包名称
    :return: 是否已安装
    """
    if not os.path.exists(lib_path):
        return False
    
    try:
        # 处理版本约束，只取包名部分
        clean_name = package_name.split('>=')[0].split('<=')[0].split('==')[0].split('!=')[0].split('>')[0].split('<')[0].strip()
        clean_name = clean_name.replace('-', '_')
        
        # 检查 lib 目录下是否有对应的包文件或目录
        # Python 包可能是 .py 文件或目录
        for item in os.listdir(lib_path):
            item_lower = item.lower()
            # 检查目录或 .py 文件
            if item_lower == clean_name or item_lower.startswith(clean_name + '-'):
                return True
        
        return False
    except Exception:
        return False


def install_to_plugin_lib(requirements_file: str, plugin_name: str, plugin_dir: str) -> bool:
    """
    将依赖安装到插件的独立 lib 目录
    
    :param requirements_file: requirements.txt 文件路径
    :param plugin_name: 插件名称
    :param plugin_dir: 插件目录路径
    :return: 是否安装成功
    """
    if not os.path.exists(requirements_file):
        return True
    
    print(f"[{plugin_name}] 检测到 requirements.txt，开始检查依赖...")
    
    # 创建插件的 lib 目录
    lib_path = os.path.join(plugin_dir, 'lib')
    os.makedirs(lib_path, exist_ok=True)
    
    # 使用当前 Python 解释器
    python_exe = sys.executable
    
    try:
        # 读取 requirements.txt
        with open(requirements_file, 'r', encoding='utf-8') as f:
            requirements = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        
        if not requirements:
            print(f"[{plugin_name}] requirements.txt 为空，跳过安装")
            return True
        
        # 检查哪些包需要安装
        missing_packages = []
        installed_packages = []
        
        for req in requirements:
            if check_package_in_lib(lib_path, req):
                installed_packages.append(req)
                print(f"[{plugin_name}] ✓ 已安装: {req}")
            else:
                missing_packages.append(req)
                print(f"[{plugin_name}] ✗ 未安装: {req}")
        
        # 如果所有依赖都已安装，跳过
        if not missing_packages:
            print(f"[{plugin_name}] 所有依赖已安装，跳过安装")
            return True
        
        # 安装缺失的依赖到 lib 目录
        print(f"[{plugin_name}] 需要安装的依赖: {', '.join(missing_packages)}")
        
        cmd = [
            python_exe,
            '-m', 'pip', 'install',
            '--target', lib_path,  # 安装到指定目录
            *missing_packages,
            '--quiet',
            '--disable-pip-version-check',
            '--no-warn-script-location'
        ]
        
        print(f"[{plugin_name}] 正在安装依赖到 lib 目录...")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300
        )
        
        if result.returncode == 0:
            print(f"[{plugin_name}] 依赖安装成功到: {lib_path}")
            
            # 创建 .pth 文件以便 Python 能找到这些包
            pth_file = os.path.join(plugin_dir, f'{plugin_name}_lib.pth')
            with open(pth_file, 'w', encoding='utf-8') as f:
                f.write(lib_path + '\n')
            
            print(f"[{plugin_name}] 已创建路径配置文件: {pth_file}")
            return True
        else:
            print(f"[{plugin_name}] 依赖安装失败:")
            print(f"  stdout: {result.stdout}")
            print(f"  stderr: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print(f"[{plugin_name}] 依赖安装超时（超过5分钟）")
        return False
    except Exception as e:
        print(f"[{plugin_name}] 安装依赖时出错: {e}")
        import traceback
        traceback.print_exc()
        return False


def add_plugin_lib_to_path(plugin_dir: str, plugin_name: str):
    """
    将插件的 lib 目录添加到 sys.path
    
    :param plugin_dir: 插件目录路径
    :param plugin_name: 插件名称
    """
    lib_path = os.path.join(plugin_dir, 'lib')
    
    if os.path.exists(lib_path) and lib_path not in sys.path:
        # 将插件 lib 目录添加到 sys.path 的前面，优先使用
        sys.path.insert(0, lib_path)
        print(f"[{plugin_name}] 已添加 lib 目录到路径: {lib_path}")


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
        """加载 plugins 目录下的所有插件（基于文件夹）"""
        try:
            plugins_path = get_plugins_path()
            
            if not os.path.exists(plugins_path):
                print(f"插件目录不存在: {plugins_path}")
                return
            
            # 遍历 plugins 目录下的所有子文件夹
            for item in os.listdir(plugins_path):
                item_path = os.path.join(plugins_path, item)
                
                # 跳过非目录、__pycache__、以下划线开头的目录
                if not os.path.isdir(item_path):
                    continue
                if item.startswith('__') or item.startswith('.'):
                    continue
                
                try:
                    self.load_plugin_by_folder(item, plugins_path)
                except Exception as e:
                    print(f"加载插件 {item} 失败: {e}")
                    import traceback
                    traceback.print_exc()
            
            print(f"共加载 {len(self.plugins)} 个插件")
        except Exception as e:
            print(f"加载插件时出错: {e}")
            import traceback
            traceback.print_exc()
    
    def load_plugin_by_folder(self, folder_name: str, plugins_path: str):
        """
        通过文件夹加载插件
        
        :param folder_name: 插件文件夹名称（例如 hello）
        :param plugins_path: plugins 目录路径
        """
        plugin_dir = os.path.join(plugins_path, folder_name)
        main_file = os.path.join(plugin_dir, f"{folder_name}.py")
        
        # 检查主文件是否存在
        if not os.path.exists(main_file):
            print(f"[{folder_name}] 警告: 找不到主文件 {folder_name}.py，跳过")
            return
        
        # 检查并安装依赖到独立的 lib 目录
        requirements_file = os.path.join(plugin_dir, 'requirements.txt')
        if os.path.exists(requirements_file):
            print(f"[{folder_name}] 发现 requirements.txt")
            success = install_to_plugin_lib(requirements_file, folder_name, plugin_dir)
            
            if not success:
                print(f"[{folder_name}] 依赖安装失败，跳过此插件")
                self.plugin_info[folder_name] = {
                    'name': folder_name,
                    'description': '依赖安装失败',
                    'version': '未知',
                    'enabled': False,
                    'module_name': f"plugins.{folder_name}.{folder_name}",
                    'error': '依赖安装失败，请查看控制台输出'
                }
                return
        
        # 将插件的 lib 目录添加到 sys.path
        add_plugin_lib_to_path(plugin_dir, folder_name)
        
        # 确保插件目录有 __init__.py
        init_file = os.path.join(plugin_dir, '__init__.py')
        if not os.path.exists(init_file):
            # 自动创建空的 __init__.py
            try:
                with open(init_file, 'w', encoding='utf-8') as f:
                    f.write('# Auto-generated by plugin loader\n')
                print(f"[{folder_name}] 已自动创建 __init__.py")
            except Exception as e:
                print(f"[{folder_name}] 创建 __init__.py 失败: {e}")
                return
        
        # 将 plugins 目录添加到 sys.path（如果还没有）
        if plugins_path not in sys.path:
            sys.path.insert(0, plugins_path)
        
        # 导入模块：plugins.folder_name.folder_name
        module_name = f"plugins.{folder_name}.{folder_name}"
        
        try:
            module = importlib.import_module(module_name)
        except ImportError as e:
            print(f"导入插件 {module_name} 失败: {e}")
            self.plugin_info[folder_name] = {
                'name': folder_name,
                'description': '插件加载失败',
                'version': '未知',
                'enabled': False,
                'module_name': module_name,
                'error': f'导入失败: {str(e)}'
            }
            return
        
        # 查找模块中的 main 类
        for name, obj in inspect.getmembers(module):
            if name == 'main' and inspect.isclass(obj):
                # 为插件创建专属的 Bot 包装器（自动注入插件名）
                plugin_bot_wrapper = PluginBotWrapper(globals.bot_instance, folder_name)
                
                # 实例化插件（传入 websocket 和包装后的bot）
                plugin_instance = obj(self.websocket, plugin_bot_wrapper)
                
                # 存储插件实例
                self.plugins[folder_name] = plugin_instance
                
                # 获取插件信息
                plugin_name = getattr(plugin_instance, 'name', folder_name)
                # 更新包装器中的插件名为实际名称
                plugin_bot_wrapper._plugin_name = plugin_name
                plugin_bot_wrapper.Logger.plugin_name = plugin_name
                
                plugin_info = {
                    'name': plugin_name,
                    'description': getattr(plugin_instance, 'description', '暂无描述'),
                    'version': getattr(plugin_instance, 'version', '1.0.0'),
                    'enabled': True,
                    'module_name': module_name,
                    'folder': folder_name
                }
                self.plugin_info[folder_name] = plugin_info
                
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
                            'plugin_key': folder_name
                        })
                
                print(f"[{folder_name}] 插件加载成功")
                break
        else:
            print(f"[{folder_name}] 警告: 未找到 main 类")
            self.plugin_info[folder_name] = {
                'name': folder_name,
                'description': '未找到 main 类',
                'version': '未知',
                'enabled': False,
                'module_name': module_name,
                'error': '插件文件中未定义 main 类'
            }
    
    def load_plugin(self, module_name: str):
        """
        旧的加载方法（保留兼容性）
        推荐使用 load_plugin_by_folder
        """
        plugin_key = module_name.split('.')[-1]
        plugins_path = get_plugins_path()
        
        # 导入模块
        try:
            module = importlib.import_module(module_name)
        except ImportError as e:
            print(f"导入插件 {module_name} 失败: {e}")
            self.plugin_info[plugin_key] = {
                'name': plugin_key,
                'description': '插件加载失败',
                'version': '未知',
                'enabled': False,
                'module_name': module_name,
                'error': f'导入失败: {str(e)}'
            }
            return
        
        # 查找模块中的 main 类
        for name, obj in inspect.getmembers(module):
            if name == 'main' and inspect.isclass(obj):
                # 为插件创建专属的 Bot 包装器（自动注入插件名）
                plugin_bot_wrapper = PluginBotWrapper(globals.bot_instance, plugin_key)
                
                # 实例化插件（传入 websocket 和包装后的bot）
                plugin_instance = obj(self.websocket, plugin_bot_wrapper)
                
                # 存储插件实例
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
            try:
                # 移除旧插件
                del self.plugins[plugin_name]
                
                # 清除事件处理器
                for event_type in list(self.event_handlers.keys()):
                    self.event_handlers[event_type] = [
                        h for h in self.event_handlers[event_type]
                        if h['plugin_key'] != plugin_name
                    ]
                    if not self.event_handlers[event_type]:
                        del self.event_handlers[event_type]
                
                # 重新加载
                plugins_path = get_plugins_path()
                self.load_plugin_by_folder(plugin_name, plugins_path)
                
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


