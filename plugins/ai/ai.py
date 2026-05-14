import sys
import os

import websockets
from .silicon import ConversationManager
from .unit.web import init_web_server, get_web_server


class main:
    """AI对话插件"""

    name = "AI插件"
    description = "AI对话插件"
    version = "1.0.0"

    chats = {}
    web_server = None

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

        # 获取插件所在目录
        self.plugin_dir = os.path.dirname(os.path.abspath(__file__))
        self.db_dir = os.path.join(self.plugin_dir, 'db')
        self.prompt_path = os.path.join(self.plugin_dir, 'prompt.txt')
        print("prompt: " + os.path.join(self.plugin_dir, 'prompt.txt'))

        # 确保db目录存在
        if not os.path.exists(self.db_dir):
            os.makedirs(self.db_dir)

        print("[AI插件] 插件已初始化")
        if self.bot:
            print("[AI插件] Bot实例已注入")
        else:
            print("[AI插件] 警告: Bot实例未提供")

    async def on_start(self):
        """
        插件启动时调用（首次加载时自动执行）
        可以用于初始化数据、发送欢迎消息等
        """
        print("[AI插件] on_start 被调用")
        print(sys.executable, sys.path)

        if not self.bot:
            print("[AI插件] Bot不可用，跳过初始化")
            return

        try:
            # 初始化并启动Web服务器
            print("[AI插件] 正在启动对话展示Web服务...")
            self.web_server = init_web_server(
                db_dir=self.db_dir,
                host='0.0.0.0',
                port=5000
            )
            print("[AI插件] Web服务已启动")
            
            # 加载并显示现有历史消息
            print("[AI插件] 加载历史对话记录...")
            self.web_server.load_and_display_history()
            
            print("[AI插件] 初始化完成")
        except Exception as e:
            print(f"[AI插件] 初始化失败: {e}")
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
        print("[AI插件] 已注册消息监听器")
        return ret

    async def on_message(self, message):
        """
        处理消息事件
        :param message: 消息数据字典，包含 _plugin_name 字段
        """
        print(f"[AI插件] 收到消息: {message}")

        # 检查是否有Bot实例
        if not self.bot:
            print("[AI插件] Bot实例不可用")
            return

        try:
            # 只处理私聊消息
            if message.get('message_type') != 'private':
                return

            if message.get('user_id') != 3399752707:
                print("[AI插件] 这条消息不来自灰度的人，忽略")
                return

            user_id = message.get('user_id')
            sender_name = message.get('sender', {}).get('nickname', '未知用户')
            raw_message = message.get('raw_message', '').strip()

            print(f"[AI插件] 用户 {user_id} 的 {sender_name} 说: {raw_message}")

            # 实时展示用户消息
            if self.web_server:
                self.web_server.display_realtime_message(
                    user_id=str(user_id),
                    source='user',
                    content=raw_message
                )

            # 进行 AI 回复
            # 检查是否已有该用户的对话实例
            if user_id not in self.chats:
                # 构造数据库文件路径
                db_file = os.path.join(self.db_dir, f"{user_id}.db")
                
                # 检查数据库文件是否存在
                if os.path.exists(db_file):
                    # 从现有数据库加载对话
                    print(f"[AI插件] 从现有数据库加载对话: {db_file}")
                    self.chats[user_id] = ConversationManager(
                        conversation_id=str(user_id),
                        sqlite_path=db_file,
                        prompt_path=self.prompt_path
                    )
                else:
                    # 创建新的对话
                    print(f"[AI插件] 创建新的对话，数据库将保存在: {db_file}")
                    self.chats[user_id] = ConversationManager(
                        conversation_id=str(user_id),
                        sqlite_path=db_file,
                        prompt_path=self.prompt_path
                    )
            
            # 获取对话实例
            conversation = self.chats[user_id]
            
            # 调用AI对话（流式，包含思考过程）
            print(f"[AI插件] 正在调用AI接口（流式+思考）...")
            full_response = ""
            full_thinking = ""
            is_thinking = False
            
            # 使用流式接收
            for chunk_data in conversation.chat_stream(raw_message):
                chunk_type = chunk_data.get('type')
                chunk_text = chunk_data.get('text', '')
                
                if chunk_type == 'thinking':
                    # 处理思考过程
                    if not is_thinking:
                        is_thinking = True
                        print(f"[AI插件] 💭 AI开始思考...")
                        if self.web_server:
                            self.web_server.emit_thinking_start(str(user_id))
                    
                    full_thinking += chunk_text
                    
                    # 实时推送思考片段到前端
                    if self.web_server:
                        self.web_server.emit_streaming_chunk(
                            user_id=str(user_id),
                            chunk_data=chunk_data,
                            is_complete=False
                        )
                
                elif chunk_type == 'content':
                    # 处理正式回复
                    if is_thinking:
                        is_thinking = False
                        print(f"[AI插件] ✅ 思考完成，开始回复...")
                        if self.web_server:
                            self.web_server.emit_thinking_end(str(user_id))
                    
                    full_response += chunk_text
                    
                    # 实时推送回复片段到前端
                    if self.web_server:
                        self.web_server.emit_streaming_chunk(
                            user_id=str(user_id),
                            chunk_data=chunk_data,
                            is_complete=False
                        )
            
            # 发送流式完成信号
            if self.web_server:
                if is_thinking:
                    self.web_server.emit_thinking_end(str(user_id))
                self.web_server.emit_streaming_chunk(
                    user_id=str(user_id),
                    chunk_data={'type': 'content', 'text': ''},
                    is_complete=True
                )
            
            print(f"[AI插件] AI回复完成（思考: {len(full_thinking)} 字符，回复: {len(full_response)} 字符）")
            
            # 发送完整回复到QQ（不包含思考过程）
            if full_response:
                response = await self.bot.send_message(
                    message=full_response,
                    target_id=user_id,
                    message_type="private"
                )
                
                print(f"[AI插件] 回复成功: {response}")
            else:
                print(f"[AI插件] 警告: AI未生成回复内容")

        except Exception as e:
            print(f"[AI插件] 处理消息时出错: {e}")
            import traceback
            traceback.print_exc()
