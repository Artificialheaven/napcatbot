"""
Hello 示例插件 — 演示框架全部功能
====================================
- on_message 消息处理（私聊 / 群聊，多命令）
- on_notice  通知事件（群成员增减、禁言）
- call_function  Web 配置热加载
- on_start     启动生命周期
- Logger 日志、Bot API 调用
"""
import sys
import os
import time
import asyncio

import websockets
from utils.Plugin import Plugin


class main(Plugin):
    """Hello 示例插件 — 展示全部插件能力"""

    name = "Hello插件"
    description = "示例插件，演示框架全部功能：消息/通知处理、Web配置、命令系统"
    version = "2.0.0"

    # 每日计数器（演示 call_function 可持久化状态）
    daily_count = 0
    last_date = ""

    def __init__(self, websocket: websockets.ClientConnection, bot_instance=None):
        super().__init__(websocket, bot_instance)

        # 加载插件配置
        self._config = self.get_config()

        # 命令前缀
        self.cmd_prefix = self._config.get("cmd_prefix", "/")

        # 初始化问候
        print(f"[{self.name}] 插件已初始化 (v{self.version})")
        if self.bot:
            print(f"[{self.name}] Bot实例已注入")
        else:
            print(f"[{self.name}] 警告: Bot实例未提供")

    async def on_start(self):
        """插件启动生命周期 — 首次加载 / 热重载后自动执行"""
        print(f"[{self.name}] on_start 被调用")
        print(sys.executable, sys.path)

        if not self.bot:
            print(f"[{self.name}] Bot不可用，跳过初始化")
            return

        try:
            # ---- 1. 获取 Bot 自身信息 ----
            login_info = await self.bot.get_login_info()
            if login_info and 'data' in login_info:
                self.nickname = login_info['data'].get('nickname', '未知')
                self.user_id = login_info['data'].get('user_id', '未知')
                print(f"[{self.name}] Bot: {self.nickname}({self.user_id})")

            # ---- 2. 获取群列表 ----
            groups = await self.bot.get_group_list()
            group_count = len(groups.get('data', [])) if groups else 0
            print(f"[{self.name}] 共加入 {group_count} 个群")
            self.bot.Logger.info("框架", "system", f"共加入 {group_count} 个群")

            # ---- 3. 获取好友列表 ----
            friends = await self.bot.get_friend_list()
            friend_count = len(friends.get('data', [])) if friends else 0
            print(f"[{self.name}] 共有 {friend_count} 个好友")
            self.bot.Logger.info("框架", "system", f"共有 {friend_count} 个好友")

            # ---- 4. 启动完成 ----
            self.bot.Logger.info("框架", "system", f"{self.name} 启动完成")
            self.bot.Logger.info("框架", "system", f"命令前缀: '{self.cmd_prefix}'")

            print(f"[{self.name}] 初始化完成")

        except Exception as e:
            print(f"[{self.name}] 初始化失败: {e}")
            import traceback
            traceback.print_exc()

    # ================================================================
    #  消息事件处理器
    # ================================================================
    @Plugin.on_message("message")
    async def handle_message(self, message):
        """
        统一消息入口 — 根据消息类型分发到不同处理逻辑。
        接收 MessageEvent 结构化对象。
        """
        if not self.bot:
            return

        raw = message.raw_message.strip() if message.raw_message else ""
        sender_name = message.sender.nickname if message.sender else "未知"

        if message.message_type == "group":
            await self._handle_group(message, raw, sender_name)
        elif message.message_type == "private":
            await self._handle_private(message, raw, sender_name)

    # ---- 群聊处理 ----
    async def _handle_group(self, msg, raw: str, sender: str):
        group_id = msg.group_id
        user_id = msg.user_id

        # 仅处理命令
        if not raw.startswith(self.cmd_prefix):
            return

        cmd, _, args = raw[len(self.cmd_prefix):].partition(" ")
        print(f"[{self.name}] 群 {group_id} {sender}({user_id}): {raw}")

        if cmd == "ping":
            await self._cmd_ping(msg, "group", group_id)

        elif cmd == "help":
            await self._cmd_help(msg, "group", group_id)

        elif cmd == "echo":
            await self._cmd_echo(msg, "group", group_id, args)

        elif cmd == "time":
            await self._cmd_time(msg, "group", group_id)

        elif cmd == "stats":
            await self._cmd_stats(msg, "group", group_id)

    # ---- 私聊处理 ----
    async def _handle_private(self, msg, raw: str, sender: str):
        user_id = msg.user_id

        if not raw.startswith(self.cmd_prefix):
            # 非命令私聊 → 回显帮助
            return

        cmd, _, args = raw[len(self.cmd_prefix):].partition(" ")
        print(f"[{self.name}] 私聊 {sender}({user_id}): {raw}")

        if cmd == "ping":
            await self._cmd_ping(msg, "private", user_id)

        elif cmd == "help":
            await self._cmd_help(msg, "private", user_id)

        elif cmd == "echo":
            await self._cmd_echo(msg, "private", user_id, args)

        elif cmd == "time":
            await self._cmd_time(msg, "private", user_id)

        elif cmd == "stats":
            await self._cmd_stats(msg, "private", user_id)

    # ================================================================
    #  命令实现
    # ================================================================
    async def _cmd_ping(self, msg, msg_type, target_id):
        """pong! — 延迟测试"""
        t0 = time.time()
        await self.bot.send_message(
            message=f"🏓 Pong! ({msg_type})",
            target_id=target_id, message_type=msg_type
        )
        elapsed = (time.time() - t0) * 1000
        print(f"[{self.name}] ping 延迟: {elapsed:.0f}ms")

    async def _cmd_help(self, msg, msg_type, target_id):
        """帮助信息"""
        pfx = self.cmd_prefix
        help_text = (
            f"📖 {self.name} 命令列表\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"{pfx}ping   — 延迟测试\n"
            f"{pfx}help   — 本帮助\n"
            f"{pfx}echo <内容> — 复读\n"
            f"{pfx}time   — 当前时间\n"
            f"{pfx}stats  — 每日统计"
        )
        await self.bot.send_message(
            message=help_text,
            target_id=target_id, message_type=msg_type
        )

    async def _cmd_echo(self, msg, msg_type, target_id, args: str):
        """复读消息"""
        text = args.strip() if args.strip() else "你什么都没说~"
        await self.bot.send_message(
            message=f"🦜 {text}",
            target_id=target_id, message_type=msg_type
        )

    async def _cmd_time(self, msg, msg_type, target_id):
        """当前时间"""
        now = time.strftime("%Y-%m-%d %H:%M:%S")
        await self.bot.send_message(
            message=f"⏰ 服务器时间: {now}",
            target_id=target_id, message_type=msg_type
        )

    async def _cmd_stats(self, msg, msg_type, target_id):
        """每日调用统计"""
        today = time.strftime("%Y-%m-%d")
        if today != self.last_date:
            self.daily_count = 0
            self.last_date = today
        self.daily_count += 1
        await self.bot.send_message(
            message=f"📊 今日已处理 {self.daily_count} 次命令",
            target_id=target_id, message_type=msg_type
        )

    # ================================================================
    #  通知事件处理器
    # ================================================================
    @Plugin.on_notice("notice")
    async def handle_notice(self, notice):
        """处理群通知事件：成员增加、减少、禁言等"""
        nt = notice.notice_type
        sub = getattr(notice, 'sub_type', '')
        gid = getattr(notice, 'group_id', None)

        if nt == "group_increase":
            # 新成员入群
            user_id = getattr(notice, 'user_id', 0)
            operator_id = getattr(notice, 'operator_id', 0)

            if gid and self.bot:
                await asyncio.sleep(0.5)
                await self.bot.send_message(
                    message=f"👋 欢迎新成员 [{user_id}] 加入群聊！",
                    target_id=gid, message_type="group"
                )
            print(f"[{self.name}] 群 {gid} 新成员: {user_id}")

        elif nt == "group_decrease":
            # 成员离开
            user_id = getattr(notice, 'user_id', 0)
            print(f"[{self.name}] 群 {gid} 成员离开: {user_id}")

        elif nt == "group_ban":
            # 禁言事件
            user_id = getattr(notice, 'user_id', 0)
            duration = getattr(notice, 'duration', 0)
            print(f"[{self.name}] 群 {gid} 禁言: {user_id} ({duration}s)")

        elif nt == "group_admin":
            # 管理员变动
            user_id = getattr(notice, 'user_id', 0)
            set_or_unset = "设置" if sub == "set" else "取消"
            print(f"[{self.name}] 群 {gid} {set_or_unset}管理员: {user_id}")

        # 记录日志
        if self.bot:
            self.bot.Logger.info(
                "框架", "notice",
                f"收到通知: {nt}/{sub} gid={gid}"
            )

    # ================================================================
    #  Web 配置热加载
    # ================================================================
    def call_function(self, name: str, **kwargs):
        """RPC 入口 — Web 管理面板保存配置时调用"""
        if name == "load_config":
            return self.load_config(kwargs.get("config", {}))
        if name == "reset_stats":
            self.daily_count = 0
            self.last_date = ""
            return True
        return super().call_function(name, **kwargs)

    def load_config(self, config: dict = None):
        """应用 Web 面板配置"""
        if config is None:
            config = self.get_config()
        self._config = config
        self.cmd_prefix = config.get("cmd_prefix", "/")
        print(f"[{self.name}] 配置已更新: cmd_prefix='{self.cmd_prefix}'")
        return True
