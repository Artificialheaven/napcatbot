import sys
import json
import os

import websockets

from core.bot import logger, bot
from .rcon import RCONClient

from utils.Plugin import Plugin


class main(Plugin):
    """Hello 示例插件"""
    
    name = "我的世界"
    description = "我的世界服务器控制插件"
    version = "1.0.0"

    def __init__(self, websocket: websockets.ClientConnection, bot_instance=None):
        """
        初始化插件
        :param websocket: WebSocket连接
        :param bot_instance: Bot实例（实际上是PluginBotWrapper，会自动注入插件名）
        """
        super().__init__(websocket, bot_instance)
        self.RconClient = None
        self._initialized = False  # 防止重复初始化标志
        self.list_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'list.json')
        print("[" + self.name + "] 插件已初始化")
        if self.bot:
            print("[" + self.name + "] Bot实例已注入")
        else:
            print("[" + self.name + "] 警告: Bot实例未提供")

    async def on_start(self):
        """
        插件启动时调用（首次加载时自动执行）
        可以用于初始化数据、发送欢迎消息等
        """
        # 防止重复初始化
        if self._initialized:
            print("[" + self.name + "] 插件已初始化，跳过重复初始化")
            return
        
        print("[" + self.name + "] on_start 被调用")
        print(sys.executable, sys.path)
        
        if not self.bot:
            print("[" + self.name + "] Bot不可用，跳过初始化")
            return

        try:
            self.RconClient = RCONClient("eastcloud.top", 25575, "zxc00544")
            self.RconClient.connect()
            print("[mcs] RCON客户端已连接")
            # 确保 list.json 存在
            if not os.path.exists(self.list_file):
                with open(self.list_file, 'w', encoding='utf-8') as f:
                    json.dump({}, f, ensure_ascii=False, indent=2)
            self._initialized = True  # 标记为已初始化
            print("[mcs] 初始化完成")
        except Exception as e:
            print(f"[mcs] 初始化失败: {e}")
            import traceback
            traceback.print_exc()

    @Plugin.on_message("message")
    async def hello(self, message):
        """
        处理消息事件
        :param message: 消息数据字典，包含 _plugin_name 字段
        """
        
        # 检查是否有Bot实例
        if not self.bot:
            print("Bot实例不可用")
            return
        
        try:
            # 只处理群消息
            if message.message_type != 'group':
                return

            if message.group_id != 657585040:
                return

            if message.raw_message.startswith("注册 "):
                player_name = message.raw_message[3:]
                qq_number = str(message.user_id)
                print(f"收到注册请求 - QQ: {qq_number}, 玩家: {player_name}")

                # 读取 list.json
                with open(self.list_file, 'r', encoding='utf-8') as f:
                    player_map = json.load(f)

                # 如果该QQ号已注册过其他玩家名，移除旧白名单
                if qq_number in player_map:
                    old_name = player_map[qq_number]
                    if old_name != player_name:
                        print(f"[mcs] QQ {qq_number} 换名: {old_name} -> {player_name}, 移除旧白名单")
                        self.RconClient.execute_command(f"whitelist remove {old_name}")
                        del player_map[qq_number]

                # 如果新玩家名已被其他QQ号占用，移除其白名单
                for other_qq, other_name in player_map.items():
                    if other_name == player_name and other_qq != qq_number:
                        print(f"[mcs] 玩家名 {player_name} 已被QQ {other_qq} 占用，移除其白名单")
                        self.RconClient.execute_command(f"whitelist remove {player_name}")
                        del player_map[other_qq]
                        break

                # 添加新白名单
                resp = self.RconClient.execute_command(f"whitelist add {player_name}")
                print(f"[mcs] 白名单响应: {resp}")

                # 更新映射并保存
                player_map[qq_number] = player_name
                with open(self.list_file, 'w', encoding='utf-8') as f:
                    json.dump(player_map, f, ensure_ascii=False, indent=2)

                if resp == "Player is already whitelisted":
                    resp = f"玩家 {player_name} 已在白名单中"
                elif "Added" in resp:
                    resp = f"注册成功: {player_name}"
                await self.bot.send_message(
                    target_id=message.get("group_id"),
                    message=resp,
                    message_type="group"
                )

                    
        except Exception as e:
            print(f"[Hello插件] 处理消息时出错: {e}")
            import traceback
            traceback.print_exc()