import sqlite3
import os
from openai import OpenAI
from typing import Optional, List, Dict


class ConversationManager:
    """AI对话管理器，支持历史对话存储和检索"""
    
    def __init__(self, conversation_id: str, sqlite_path: Optional[str] = None, prompt_path: Optional[str] = None):
        """
        初始化对话管理器
        
        :param conversation_id: 对话ID
        :param sqlite_path: SQLite数据库文件路径（可选），如果提供则从该文件读取历史对话
        :param prompt_path: Prompt文件路径（可选），仅在新建对话时需要
        """
        self.conversation_id = conversation_id
        self.api_key = "sk-lrvjaltvcqsawcrjocibgjknvwqsfikirthzntdyyjrdrqqd"
        self.base_url = "https://api.siliconflow.cn/v1"
        self.model = "Pro/zai-org/GLM-4.7"
        
        # 确定数据库路径
        if sqlite_path:
            self.db_path = sqlite_path
            is_new_db = not os.path.exists(sqlite_path)
        else:
            self.db_path = f"{conversation_id}.db"
            is_new_db = not os.path.exists(self.db_path)
        
        # 初始化数据库
        self._init_database()
        
        # 如果是新数据库且提供了prompt路径，加载system prompt
        if is_new_db and prompt_path:
            self._load_system_prompt(prompt_path)
        
        # 初始化OpenAI客户端
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )
    
    def _init_database(self):
        """初始化数据库表结构"""
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL CHECK(source IN ('system', 'user', 'assistant')),
                content TEXT NOT NULL
            )
        ''')
        self.conn.commit()
    
    def _load_system_prompt(self, prompt_path: str):
        """从文件加载system prompt并保存到数据库"""
        try:
            with open(prompt_path, 'r', encoding='utf-8') as f:
                prompt_content = f.read()
            if prompt_content.strip():
                self._add_message('system', prompt_content)
        except Exception as e:
            print(f"加载prompt文件失败: {e}")
    
    def _add_message(self, source: str, content: str):
        """添加消息到数据库"""
        self.cursor.execute(
            'INSERT INTO messages (source, content) VALUES (?, ?)',
            (source, content)
        )
        self.conn.commit()
    
    def chat(self, user_message: str) -> str:
        """
        发送用户消息并获取AI回复
        
        :param user_message: 用户消息内容
        :return: AI回复内容
        """
        # 保存用户消息
        self._add_message('user', user_message)
        
        # 获取历史对话
        messages = self._get_all_messages()
        
        # 调用API获取回复
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages
        )
        
        # 获取AI回复内容
        ai_response = response.choices[0].message.content
        
        # 保存AI回复
        self._add_message('assistant', ai_response)
        
        return ai_response
    
    def history(self) -> List[Dict[str, str]]:
        """
        获取历史对话记录
        
        :return: 历史对话列表，每个元素包含id、source和content
        """
        self.cursor.execute('SELECT id, source, content FROM messages ORDER BY id ASC')
        rows = self.cursor.fetchall()
        
        return [
            {
                'id': row[0],
                'source': row[1],
                'content': row[2]
            }
            for row in rows
        ]
    
    def summarize(self) -> str:
        """
        总结当前对话内容（不计入历史对话）
        
        :return: 对话总结内容
        """
        # 获取历史对话
        messages = self._get_all_messages()
        
        # 添加总结请求（临时，不保存到数据库）
        summary_messages = messages.copy()
        summary_messages.append({
            'role': 'user',
            'content': '请总结以上对话的主要内容，简明扼要地概括讨论的要点。'
        })
        
        # 调用API获取总结
        response = self.client.chat.completions.create(
            model=self.model,
            messages=summary_messages
        )
        
        # 返回总结内容，不保存到数据库
        return response.choices[0].message.content
    
    def _get_all_messages(self) -> List[Dict[str, str]]:
        """获取所有消息并转换为OpenAI API格式"""
        self.cursor.execute('SELECT source, content FROM messages ORDER BY id ASC')
        rows = self.cursor.fetchall()
        
        return [
            {'role': row[0], 'content': row[1]}
            for row in rows
        ]
    
    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()
    
    def __del__(self):
        """析构函数，确保关闭数据库连接"""
        self.close()
