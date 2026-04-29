import websockets
import requests


class main:
    """Hello 示例插件"""
    
    name = "Hello插件"
    description = "示例插件，用于测试插件系统和Bot功能"
    version = "1.0.0"

    def __init__(self, websocket: websockets.ClientConnection, bot_instance=None):
        """
        初始化插件
        :param websocket: WebSocket连接
        :param bot_instance: Bot实例（实际上是PluginBotWrapper，会自动注入插件名）
        """
        self.user_id = None
        self.nickname = None
        self.websocket = websocket
        self.bot = bot_instance
        print("[Hello插件] 插件已初始化")
        if self.bot:
            print("[Hello插件] Bot实例已注入")
        else:
            print("[Hello插件] 警告: Bot实例未提供")

    async def on_start(self):
        """
        插件启动时调用（首次加载时自动执行）
        可以用于初始化数据、发送欢迎消息等
        """
        print("[Hello插件] on_start 被调用")
        
        if not self.bot:
            print("[Hello插件] Bot不可用，跳过初始化")
            return
        
        try:
            # 示例：获取Bot信息并记录日志
            login_info = await self.bot.get_login_info()
            if login_info and 'data' in login_info:
                self.nickname = login_info['data'].get('nickname', '未知')
                self.user_id = login_info['data'].get('user_id', '未知')
                print(f"[Hello插件] Bot登录信息: {self.nickname}({self.user_id})")
            
            # 示例：获取群列表
            groups = await self.bot.get_group_list()
            if groups and 'data' in groups:
                group_count = len(groups['data'])
                print(f"[Hello插件] 共加入 {group_count} 个群")
                # Logger的来源会自动固定为插件名
                self.bot.Logger.info("框架", "任意值", f"共加入 {group_count} 个群")
            
            # 示例：获取好友列表
            friends = await self.bot.get_friend_list()
            if friends and 'data' in friends:
                friend_count = len(friends['data'])
                print(f"[Hello插件] 共有 {friend_count} 个好友")
                # Logger的来源会自动固定为插件名
                self.bot.Logger.info("框架", "任意值", f"共有 {friend_count} 个好友")

            # Logger的来源会自动固定为插件名
            self.bot.Logger.info("框架", "任意值", "插件启动完成")
            self.bot.Logger.info("框架", "任意值", "早上好，" + self.nickname)
            
            print("[Hello插件] 初始化完成")
            
        except Exception as e:
            print(f"[Hello插件] 初始化失败: {e}")
            import traceback
            traceback.print_exc()

    def regisiter(self) -> list:
        """
        返回一个列表，用于告知框架应该调用的程序
        :return: list
        """
        ret = [
            {
                "listen": "message",
                "function": self.on_message
            }
        ]
        print("[Hello插件] 已注册消息监听器")
        return ret

    async def on_message(self, message):
        """
        处理消息事件
        :param message: 消息数据字典，包含 _plugin_name 字段
        """
        print(f"[Hello插件] 收到消息: {message}")
        
        # 检查是否有Bot实例
        if not self.bot:
            print("[Hello插件] Bot实例不可用")
            return
        
        try:
            # 只处理群消息
            if message.get('message_type') != 'group':
                return
                
            group_id = message.get('group_id')
            sender_name = message.get('sender', {}).get('nickname', '未知用户')
            raw_message = message.get('raw_message', '').strip()
            
            print(f"[Hello插件] 群 {group_id} 的 {sender_name} 说: {raw_message}")
                    
            # 如果消息包含"你好"，则回复
            if '你好' in raw_message:
                reply_message = f"你好呀，{sender_name}！我是Hello插件 👋"
                
                # send_message会自动使用插件名作为来源
                response = await self.bot.send_message(
                    message=reply_message,
                    target_id=group_id,
                    message_type="group"
                )
                
                print(f"[Hello插件] 回复成功: {response}")
                    
        except Exception as e:
            print(f"[Hello插件] 处理消息时出错: {e}")
            import traceback
            traceback.print_exc()
