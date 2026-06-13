"""
Slang 插件 — 基于 Slang DSL 的消息匹配与自动化执行
====================================================
- on_message:  接收消息，匹配数据库中的规则，执行对应 Slang 代码
- 匹配方式:    exact（完全匹配）/ fuzzy（模糊匹配）/ regex（正则匹配）
- Slang 集成:  消息上下文自动注入为变量，通过「回复」函数输出
- 数据库:      SQLite，存放在 plugins/slang/db/rules.db
"""
import re
import os
import sqlite3
import traceback

import flask
import websockets
from utils.Plugin import Plugin

from .Core.init import init as slang_init
from regs import register as base_register


class main(Plugin):
    """Slang DSL 自动化插件 — 消息匹配 + 脚本执行"""

    name = "Slang插件"
    description = "基于 Slang DSL 的消息匹配与自动化执行插件，支持完全/模糊/正则匹配"
    version = "1.0.0"

    # ── 生命周期 ────────────────────────────────────────────────

    def __init__(self, websocket: websockets.ClientConnection, bot_instance=None):
        super().__init__(websocket, bot_instance)

        # 数据库路径
        self._plugin_dir = os.path.dirname(os.path.abspath(__file__))
        self._db_dir = os.path.join(self._plugin_dir, "db")
        self._db_path = os.path.join(self._db_dir, "rules.db")
        self._db_conn: sqlite3.Connection | None = None

        # 初始化 Slang 解释器（在注册自定义函数之后）
        self.slang = self._init_slang()

        print(f"[{self.name}] 插件已初始化 (v{self.version})")
        if self.bot:
            print(f"[{self.name}] Bot实例已注入")
        else:
            print(f"[{self.name}] 警告: Bot实例未提供")

    async def on_start(self):
        """插件启动 — 初始化数据库"""
        print(f"[{self.name}] on_start 被调用")

        self._ensure_db()

        if self.bot:
            self.bot.Logger.info(self.name, "system", "Slang 插件启动完成")
        else:
            print(f"[{self.name}] 警告: Bot实例不可用，消息处理将跳过")

    # ── Slang 解释器 ────────────────────────────────────────────

    def _init_slang(self):
        """初始化 Slang 解释器，注册插件专用函数。"""
        self._register = base_register

        # —— 回复：将文本加入回复队列 ——
        def _slang_reply(parma: list, _dict: dict):
            queue = _dict.get('__reply_queue__')
            if queue is not None:
                queue.append(str(parma[0]))

        self._register.func_dict['回复'] = {
            'name': '_slang_reply', 'func': _slang_reply,
            'parma_len': 1, 'info': '发送回复消息到当前会话（群聊→群，私聊→私聊）',
        }

        # —— 回复私聊：发送私聊消息到指定 QQ ——
        def _slang_reply_private(parma: list, _dict: dict):
            queue = _dict.get('__reply_private_queue__')
            if queue is not None:
                queue.append({
                    'message': str(parma[0]),
                    'target_id': int(parma[1]),
                })

        self._register.func_dict['回复私聊'] = {
            'name': '_slang_reply_private', 'func': _slang_reply_private,
            'parma_len': 2, 'info': '发送私聊消息（参数：消息内容，目标QQ）',
        }

        # —— 回复群：发送群消息到指定群 ——
        def _slang_reply_group(parma: list, _dict: dict):
            queue = _dict.get('__reply_group_queue__')
            if queue is not None:
                queue.append({
                    'message': str(parma[0]),
                    'target_id': int(parma[1]),
                })

        self._register.func_dict['回复群'] = {
            'name': '_slang_reply_group', 'func': _slang_reply_group,
            'parma_len': 2, 'info': '发送群聊消息（参数：消息内容，目标群号）',
        }

        # 创建 Slang 实例（已知函数名在此处缓存）
        return slang_init(self._register, d={})

    # ── 数据库 ──────────────────────────────────────────────────

    def _ensure_db(self):
        """确保数据库文件及表存在，返回连接（复用已有连接）。"""
        if self._db_conn is not None:
            return self._db_conn

        os.makedirs(self._db_dir, exist_ok=True)
        conn = sqlite3.connect(self._db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS rules (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                match_type      TEXT    NOT NULL CHECK(match_type IN ('exact', 'fuzzy', 'regex')),
                match_content   TEXT    NOT NULL,
                slang_code      TEXT    NOT NULL,
                enabled         INTEGER DEFAULT 1,
                priority        INTEGER DEFAULT 0,
                description     TEXT    DEFAULT '',
                created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        self._db_conn = conn
        print(f"[{self.name}] 数据库就绪: {self._db_path}")
        return conn

    def _get_web_db(self) -> sqlite3.Connection:
        """获取一个新的数据库连接（线程安全，供 Web 路由使用）。"""
        os.makedirs(self._db_dir, exist_ok=True)
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        # 确保表存在
        conn.execute("""
            CREATE TABLE IF NOT EXISTS rules (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                match_type      TEXT    NOT NULL CHECK(match_type IN ('exact', 'fuzzy', 'regex')),
                match_content   TEXT    NOT NULL,
                slang_code      TEXT    NOT NULL,
                enabled         INTEGER DEFAULT 1,
                priority        INTEGER DEFAULT 0,
                description     TEXT    DEFAULT '',
                created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        return conn

    # ── 消息处理 ────────────────────────────────────────────────

    @Plugin.on_message("message")
    async def handle_message(self, event):
        """统一消息入口 — 匹配规则并执行 Slang 代码。"""
        if not self.bot:
            return

        raw = (event.raw_message or "").strip()
        if not raw:
            return

        # 确保数据库就绪
        self._ensure_db()

        # 匹配规则
        rule = self._match_rule(raw)
        if rule is None:
            return

        msg_type = event.message_type
        target_desc = event.group_id if msg_type == "group" else event.user_id
        sender = getattr(event.sender, 'nickname', '未知') if event.sender else '未知'
        print(f"[{self.name}] 命中规则 #{rule['id']} ({rule['match_type']}): "
              f"{msg_type}/{target_desc} {sender}: {raw[:40]}")

        # 执行 Slang
        await self._execute_slang(rule, event)

    def _match_rule(self, raw_message: str) -> dict | None:
        """在数据库中查找匹配的规则，按优先级降序、ID 升序返回第一个命中。"""
        cursor = self._db_conn.execute(
            "SELECT id, match_type, match_content, slang_code "
            "FROM rules WHERE enabled = 1 "
            "ORDER BY priority DESC, id ASC"
        )
        for row in cursor.fetchall():
            rule_id, match_type, match_content, slang_code = row
            if self._match_one(match_type, match_content, raw_message):
                return {
                    'id': rule_id,
                    'match_type': match_type,
                    'match_content': match_content,
                    'slang_code': slang_code,
                }
        return None

    @staticmethod
    def _match_one(match_type: str, match_content: str, raw_message: str) -> bool:
        """对单条规则执行匹配。"""
        if match_type == 'exact':
            return raw_message == match_content
        elif match_type == 'fuzzy':
            return match_content in raw_message
        elif match_type == 'regex':
            try:
                return bool(re.search(match_content, raw_message))
            except re.error:
                return False
        return False

    async def _execute_slang(self, rule: dict, event):
        """执行 Slang 代码并将回复队列中的消息发送出去。"""
        # 构建变量字典 —— 消息上下文 + 回复队列
        _dict = {
            '__reply_queue__': [],
            '__reply_private_queue__': [],
            '__reply_group_queue__': [],
            # 消息上下文变量
            '消息内容': event.raw_message or '',
            '发送者QQ': str(event.user_id),
            '发送者昵称': getattr(event.sender, 'nickname', '') if event.sender else '',
            '消息类型': event.message_type,
            '群号': str(event.group_id) if event.group_id else '',
            '消息ID': str(event.message_id) if hasattr(event, 'message_id') else '',
        }

        # 执行 Slang 代码（直接设置 _dict 后调用 run_room 以获取返回值）
        slang_result = ''
        try:
            self.slang._dict = _dict
            slang_result = (self.slang.run_room(rule['slang_code']) or '').strip()
        except Exception:
            print(f"[{self.name}] Slang 执行异常 (规则 #{rule['id']}):")
            traceback.print_exc()
            if self.bot:
                self.bot.Logger.error(
                    self.name, "slang",
                    f"规则 #{rule['id']} 执行异常"
                )

        # 发送当前会话的回复
        msg_type = event.message_type
        default_target = event.group_id if msg_type == 'group' else event.user_id

        for msg_text in _dict['__reply_queue__']:
            await self.bot.send_message(
                message=str(msg_text),
                target_id=default_target,
                message_type=msg_type,
            )

        # 发送私聊回复
        for item in _dict['__reply_private_queue__']:
            await self.bot.send_message(
                message=item['message'],
                target_id=item['target_id'],
                message_type='private',
            )

        # 发送群聊回复
        for item in _dict['__reply_group_queue__']:
            await self.bot.send_message(
                message=item['message'],
                target_id=item['target_id'],
                message_type='group',
            )

        # 发送 Slang 代码的返回值（非空且未通过「回复」发送时）
        if slang_result and slang_result not in _dict['__reply_queue__']:
            await self.bot.send_message(
                message=slang_result,
                target_id=default_target,
                message_type=msg_type,
            )

    # ── Web 配置热加载 ──────────────────────────────────────────

    def call_function(self, name: str, **kwargs):
        """RPC 入口 — Web 管理面板回调。"""
        if name == "load_config":
            return self.load_config(kwargs.get("config", {}))
        return super().call_function(name, **kwargs)

    def load_config(self, config: dict = None):
        """应用 Web 面板配置。"""
        if config is None:
            config = self.get_config()
        self._config = config
        print(f"[{self.name}] 配置已更新")
        return True

    # ── Web Blueprint ────────────────────────────────────────────

    def get_web_blueprint(self):
        """返回 Flask Blueprint，挂载到 /slang/ 路径下。

        提供规则管理 API：
        - GET  /             管理页面
        - GET  /api/rules    列出所有规则
        - POST /api/rules    添加规则
        - DELETE /api/rules/<id>  删除规则
        - PUT  /api/rules/<id>/toggle  切换启用状态
        """
        bp = flask.Blueprint(
            'slang',
            __name__,
            template_folder=os.path.join(self._plugin_dir, 'templates'),
        )

        # ── 页面 ──

        @bp.route('/')
        def index():
            return flask.render_template('rules.html')

        # ── API：列出规则 ──

        @bp.route('/api/rules', methods=['GET'])
        def api_list_rules():
            conn = self._get_web_db()
            try:
                rows = conn.execute(
                    "SELECT id, match_type, match_content, slang_code, "
                    "enabled, priority, description, created_at, updated_at "
                    "FROM rules ORDER BY priority DESC, id ASC"
                ).fetchall()
                rules = [dict(r) for r in rows]
                return flask.jsonify({'ok': True, 'rules': rules})
            finally:
                conn.close()

        # ── API：添加规则 ──

        @bp.route('/api/rules', methods=['POST'])
        def api_add_rule():
            data = flask.request.get_json(silent=True) or {}
            match_type = data.get('match_type', '').strip()
            match_content = data.get('match_content', '').strip()
            slang_code = data.get('slang_code', '').strip()
            priority = data.get('priority', 0)
            description = data.get('description', '').strip()

            if match_type not in ('exact', 'fuzzy', 'regex'):
                return flask.jsonify({'ok': False, 'error': 'match_type 必须为 exact/fuzzy/regex'}), 400
            if not match_content:
                return flask.jsonify({'ok': False, 'error': 'match_content 不能为空'}), 400
            if not slang_code:
                return flask.jsonify({'ok': False, 'error': 'slang_code 不能为空'}), 400

            conn = self._get_web_db()
            try:
                cur = conn.execute(
                    "INSERT INTO rules (match_type, match_content, slang_code, priority, description) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (match_type, match_content, slang_code, priority, description),
                )
                conn.commit()
                return flask.jsonify({'ok': True, 'id': cur.lastrowid})
            finally:
                conn.close()

        # ── API：删除规则 ──

        @bp.route('/api/rules/<int:rule_id>', methods=['DELETE'])
        def api_delete_rule(rule_id):
            conn = self._get_web_db()
            try:
                cur = conn.execute("DELETE FROM rules WHERE id = ?", (rule_id,))
                conn.commit()
                if cur.rowcount == 0:
                    return flask.jsonify({'ok': False, 'error': '规则不存在'}), 404
                return flask.jsonify({'ok': True})
            finally:
                conn.close()

        # ── API：编辑规则 ──

        @bp.route('/api/rules/<int:rule_id>', methods=['PUT'])
        def api_update_rule(rule_id):
            data = flask.request.get_json(silent=True) or {}
            conn = self._get_web_db()
            try:
                row = conn.execute(
                    "SELECT id FROM rules WHERE id = ?", (rule_id,)
                ).fetchone()
                if row is None:
                    return flask.jsonify({'ok': False, 'error': '规则不存在'}), 404

                fields = {}
                for col in ('match_type', 'match_content', 'slang_code',
                            'priority', 'description', 'enabled'):
                    if col in data:
                        fields[col] = data[col]
                if 'match_type' in fields and fields['match_type'] not in ('exact', 'fuzzy', 'regex'):
                    return flask.jsonify({'ok': False, 'error': 'match_type 必须为 exact/fuzzy/regex'}), 400
                if not fields:
                    return flask.jsonify({'ok': False, 'error': '无更新字段'}), 400

                set_clause = ', '.join(f"{k} = ?" for k in fields)
                values = list(fields.values())
                conn.execute(
                    f"UPDATE rules SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    values + [rule_id],
                )
                conn.commit()
                return flask.jsonify({'ok': True})
            finally:
                conn.close()

        # ── API：切换启用状态 ──

        @bp.route('/api/rules/<int:rule_id>/toggle', methods=['PUT'])
        def api_toggle_rule(rule_id):
            conn = self._get_web_db()
            try:
                row = conn.execute(
                    "SELECT enabled FROM rules WHERE id = ?", (rule_id,)
                ).fetchone()
                if row is None:
                    return flask.jsonify({'ok': False, 'error': '规则不存在'}), 404
                new_enabled = 0 if row['enabled'] else 1
                conn.execute(
                    "UPDATE rules SET enabled = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (new_enabled, rule_id),
                )
                conn.commit()
                return flask.jsonify({'ok': True, 'enabled': bool(new_enabled)})
            finally:
                conn.close()

        return bp
