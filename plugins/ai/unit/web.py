import flask
from flask_socketio import SocketIO, emit
import os
import sqlite3
import threading
from pathlib import Path
from typing import List, Dict


class ConversationWebServer:
    """对话展示Web服务器（支持WebSocket实时推送）"""
    
    def __init__(self, db_dir: str = None, host: str = '0.0.0.0', port: int = 5000):
        """
        初始化Web服务器
        
        :param db_dir: 数据库目录路径
        :param host: 服务器主机地址
        :param port: 服务器端口
        """
        self.host = host
        self.port = port
        self.server_thread = None
        self.is_running = False
        self.socketio = None
        
        # 确定数据库目录
        if db_dir:
            self.db_dir = db_dir
        else:
            plugin_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.db_dir = os.path.join(plugin_dir, 'db')
        
        # 确保db目录存在
        if not os.path.exists(self.db_dir):
            os.makedirs(self.db_dir)
        
        # 创建Flask应用
        self.app = flask.Flask(
            __name__,
            static_folder=os.path.dirname(os.path.abspath(__file__)),
            template_folder=os.path.dirname(os.path.abspath(__file__))
        )
        
        # 初始化SocketIO（使用threading模式）
        self.socketio = SocketIO(self.app, cors_allowed_origins="*", async_mode='threading')
        
        # 注册路由和WebSocket事件
        self._register_routes()
        self._register_socket_events()
        
        print(f"[Web服务] 初始化完成，数据库目录: {self.db_dir}")
    
    def _register_routes(self):
        """注册HTTP路由"""
        
        @self.app.route('/')
        def index():
            """主页，返回HTML页面"""
            return flask.send_from_directory(
                os.path.dirname(os.path.abspath(__file__)),
                'index.html'
            )
        
        @self.app.route('/api/users')
        def api_users():
            """API: 获取所有用户ID列表"""
            users = self._get_db_users()
            return flask.jsonify({'users': users})
        
        @self.app.route('/api/conversation/<user_id>')
        def api_conversation(user_id):
            """API: 获取指定用户的对话记录"""
            messages = self._get_conversation(user_id)
            return flask.jsonify({'messages': messages})
    
    def _register_socket_events(self):
        """注册WebSocket事件"""
        
        @self.socketio.on('connect')
        def handle_connect():
            """客户端连接"""
            print(f"[Web服务] 客户端已连接: {flask.request.sid}")
            emit('status', {'msg': '已连接到服务器'})
        
        @self.socketio.on('disconnect')
        def handle_disconnect():
            """客户端断开"""
            print(f"[Web服务] 客户端已断开: {flask.request.sid}")
        
        @self.socketio.on('subscribe_user')
        def handle_subscribe(data):
            """客户端订阅特定用户的对话"""
            user_id = data.get('user_id')
            if user_id:
                print(f"[Web服务] 客户端订阅用户: {user_id}")
                emit('subscribed', {'user_id': user_id})
                
                # 立即发送当前对话历史
                messages = self._get_conversation(user_id)
                emit('conversation_history', {
                    'user_id': user_id,
                    'messages': messages
                })
        
        @self.socketio.on('load_conversation')
        def handle_load_conversation(data):
            """客户端请求加载对话"""
            user_id = data.get('user_id')
            if user_id:
                print(f"[Web服务] 加载对话: {user_id}")
                messages = self._get_conversation(user_id)
                emit('conversation_loaded', {
                    'user_id': user_id,
                    'messages': messages
                })
    
    def _get_db_users(self) -> List[str]:
        """获取所有有数据库的用户ID"""
        if not os.path.exists(self.db_dir):
            return []
        
        users = []
        for file in os.listdir(self.db_dir):
            if file.endswith('.db'):
                user_id = file.replace('.db', '')
                users.append(user_id)
        
        return sorted(users, key=lambda x: int(x) if x.isdigit() else 0)
    
    def _get_conversation(self, user_id: str) -> List[Dict]:
        """获取指定用户的对话记录"""
        db_file = os.path.join(self.db_dir, f"{user_id}.db")
        
        if not os.path.exists(db_file):
            return []
        
        try:
            conn = sqlite3.connect(db_file)
            cursor = conn.cursor()
            cursor.execute('SELECT id, source, content FROM messages ORDER BY id ASC')
            rows = cursor.fetchall()
            conn.close()
            
            return [
                {
                    'id': row[0],
                    'source': row[1],
                    'content': row[2]
                }
                for row in rows
            ]
        except Exception as e:
            print(f"[Web服务] 读取数据库失败: {e}")
            return []
    
    def start(self):
        """启动Web服务器（在后台线程中运行）"""
        if self.is_running:
            print("[Web服务] 服务器已在运行中")
            return
        
        def run_server():
            print(f"[Web服务] 正在启动服务器...")
            print(f"[Web服务] 访问地址: http://{self.host}:{self.port}")
            self.socketio.run(
                self.app,
                host=self.host,
                port=self.port,
                debug=False,
                use_reloader=False,
                allow_unsafe_werkzeug=True
            )
        
        self.server_thread = threading.Thread(target=run_server, daemon=True)
        self.server_thread.start()
        self.is_running = True
        print("[Web服务] 服务器启动线程已创建")
    
    def stop(self):
        """停止Web服务器"""
        if not self.is_running:
            return
        
        self.is_running = False
        print("[Web服务] 服务器已停止")
    
    def load_and_display_history(self, user_id: str = None):
        """
        加载并展示历史消息
        
        :param user_id: 用户ID，如果为None则展示所有用户
        """
        if user_id:
            messages = self._get_conversation(user_id)
            print(f"\n{'='*60}")
            print(f"[Web服务] 用户 {user_id} 的历史对话 (共 {len(messages)} 条消息)")
            print(f"{'='*60}")
            
            for msg in messages:
                if msg['source'] == 'user':
                    role = "👤 用户"
                elif msg['source'] == 'thinking':
                    role = "💭 思考"
                else:
                    role = "🤖 AI"
                print(f"\n{role}:")
                print(f"  {msg['content']}")
            
            print(f"\n{'='*60}\n")
        else:
            users = self._get_db_users()
            print(f"\n{'='*60}")
            print(f"[Web服务] 所有用户列表 (共 {len(users)} 个用户)")
            print(f"{'='*60}")
            
            for uid in users:
                messages = self._get_conversation(uid)
                print(f"\n用户 {uid}: {len(messages)} 条消息")
            
            print(f"\n{'='*60}\n")
    
    def display_realtime_message(self, user_id: str, source: str, content: str):
        """
        实时接收并展示对话内容（同时推送到前端）
        
        :param user_id: 用户ID
        :param source: 消息来源 ('user' 或 'assistant')
        :param content: 消息内容
        """
        if source == 'user':
            role = "👤 用户"
        elif source == 'thinking':
            role = "💭 思考"
        else:
            role = "🤖 AI"
        
        print(f"\n[实时对话] {role} (用户ID: {user_id}):")
        print(f"  {content}")
        
        # 通过WebSocket推送到前端
        if self.socketio:
            try:
                print(f"[Web服务] 推送消息到前端: user_id={user_id}, source={source}, length={len(content)}")
                self.socketio.emit('new_message', {
                    'user_id': user_id,
                    'source': source,
                    'content': content
                })
                print(f"[Web服务] 消息推送成功")
            except Exception as e:
                print(f"[Web服务] 消息推送失败: {e}")
    
    def emit_streaming_chunk(self, user_id: str, chunk_data: Dict, is_complete: bool = False):
        """
        实时推送流式对话片段到前端（支持思考和回复）
        
        :param user_id: 用户ID
        :param chunk_data: 片段数据 {'type': 'thinking'|'content', 'text': str}
        :param is_complete: 是否为最后一个片段
        """
        if self.socketio:
            chunk_type = chunk_data.get('type', 'content')
            chunk_text = chunk_data.get('text', '')
            
            # 只推送非空内容，或者完成信号
            if len(chunk_text) > 0 or is_complete:
                try:
                    print(f"[Web服务] 推送流式片段: user_id={user_id}, type={chunk_type}, length={len(chunk_text)}, complete={is_complete}")
                    
                    self.socketio.emit('streaming_chunk', {
                        'user_id': user_id,
                        'type': chunk_type,
                        'chunk': chunk_text,
                        'is_complete': is_complete
                    })
                except Exception as e:
                    print(f"[Web服务] 流式片段推送失败: {e}")
            else:
                # 静默跳过空片段
                pass
    
    def emit_thinking_start(self, user_id: str):
        """发送思考开始信号"""
        if self.socketio:
            try:
                print(f"[Web服务] 推送思考开始: user_id={user_id}")
                self.socketio.emit('thinking_start', {
                    'user_id': user_id
                })
            except Exception as e:
                print(f"[Web服务] 思考开始信号推送失败: {e}")
    
    def emit_thinking_end(self, user_id: str):
        """发送思考结束信号"""
        if self.socketio:
            try:
                print(f"[Web服务] 推送思考结束: user_id={user_id}")
                self.socketio.emit('thinking_end', {
                    'user_id': user_id
                })
            except Exception as e:
                print(f"[Web服务] 思考结束信号推送失败: {e}")


# 全局Web服务器实例
web_server = None


def get_web_server() -> ConversationWebServer:
    """获取Web服务器单例实例"""
    global web_server
    if web_server is None:
        web_server = ConversationWebServer()
    return web_server


def init_web_server(db_dir: str = None, host: str = '127.0.0.1', port: int = 5000):
    """
    初始化并启动Web服务器
    
    :param db_dir: 数据库目录路径
    :param host: 服务器主机地址
    :param port: 服务器端口
    :return: Web服务器实例
    """
    global web_server
    web_server = ConversationWebServer(db_dir=db_dir, host=host, port=port)
    web_server.start()
    return web_server


if __name__ == '__main__':
    # 测试代码
    server = init_web_server()
    
    # 加载并显示历史消息
    server.load_and_display_history("3399752707")
    
    # 保持运行
    try:
        while True:
            import time
            time.sleep(1)
    except KeyboardInterrupt:
        server.stop()



