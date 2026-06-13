import sqlite3
import os
from openai import OpenAI
from typing import Optional, List, Dict, Generator


class ConversationManager:
    """AI对话管理器，支持历史对话存储和检索"""

    def __init__(self, conversation_id: str, sqlite_path: Optional[str] = None, prompt_path: Optional[str] = None):
        """
        初始化对话管理器
        
        :param conversation_id: 对话ID
        :param sqlite_path: SQLite数据库文件路径（可选），如果提供则从该文件读取历史对话
        :param prompt_path: Prompt文件路径（可选），每次初始化时可以传递不同的prompt文件
        """
        self.conversation_id = conversation_id
        self.api_key = "sk-lrvjaltvcqsawcrjocibgjknvwqsfikirthzntdyyjrdrqqd"
        self.base_url = "https://api.siliconflow.cn/v1"
        self.model = "Pro/zai-org/GLM-4.7"

        # 读取prompt内容到变量
        self.prompt = None
        if prompt_path and os.path.exists(prompt_path):
            try:
                with open(prompt_path, 'r', encoding='utf-8') as f:
                    self.prompt = f.read().strip()
            except Exception as e:
                print(f"加载prompt文件失败: {e}")

        # 确定数据库路径
        if sqlite_path:
            self.db_path = sqlite_path
        else:
            self.db_path = f"{conversation_id}.db"

        # 初始化数据库
        self._init_database()

        # 初始化OpenAI客户端
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )

    def _init_database(self):
        """初始化数据库表结构（兼容旧表）"""
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
        
        # 检查表是否存在
        self.cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='messages'")
        table_exists = self.cursor.fetchone() is not None
        
        if not table_exists:
            # 表不存在，直接创建新表
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL CHECK(source IN ('user', 'assistant', 'thinking')),
                    content TEXT NOT NULL
                )
            ''')
            self.conn.commit()
            print(f"[对话管理] 创建新数据库表: {self.db_path}")
        else:
            # 表已存在，检查并更新约束
            self._migrate_table()
    
    def _migrate_table(self):
        """迁移旧表以支持 thinking 类型"""
        try:
            # 尝试插入一条测试数据来检测约束
            self.cursor.execute("INSERT INTO messages (source, content) VALUES ('thinking', 'test')")
            self.cursor.execute("DELETE FROM messages WHERE source = 'thinking' AND content = 'test'")
            self.conn.commit()
            print(f"[对话管理] 数据库表已支持 thinking 类型")
        except sqlite3.IntegrityError:
            # 约束不兼容，需要迁移
            print(f"[对话管理] 检测到旧表约束，正在迁移...")
            
            # 1. 重命名旧表
            self.cursor.execute("ALTER TABLE messages RENAME TO messages_old")
            
            # 2. 创建新表
            self.cursor.execute('''
                CREATE TABLE messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL CHECK(source IN ('user', 'assistant', 'thinking')),
                    content TEXT NOT NULL
                )
            ''')
            
            # 3. 复制数据（只复制 user 和 assistant 类型）
            self.cursor.execute('''
                INSERT INTO messages (id, source, content)
                SELECT id, source, content FROM messages_old
                WHERE source IN ('user', 'assistant')
            ''')
            
            # 4. 删除旧表
            self.cursor.execute("DROP TABLE messages_old")
            
            # 5. 提交
            self.conn.commit()
            print(f"[对话管理] 数据库表迁移完成")

    def _add_message(self, source: str, content: str):
        """添加消息到数据库"""
        self.cursor.execute(
            'INSERT INTO messages (source, content) VALUES (?, ?)',
            (source, content)
        )
        self.conn.commit()

    def chat(self, user_message: str) -> str:
        """
        发送用户消息并获取AI回复（非流式，保持兼容）
        
        :param user_message: 用户消息内容
        :return: AI回复内容
        """
        # 保存用户消息
        self._add_message('user', user_message)

        # 获取历史对话（已包含prompt）
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

    def chat_stream(self, user_message: str) -> Generator[Dict[str, str], None, None]:
        """
        发送用户消息并以流式方式获取AI回复（包含思考过程）
        
        :param user_message: 用户消息内容
        :return: 生成器，逐步返回字典 {'type': 'thinking'|'content', 'text': str}
                 - type='thinking': 思考过程片段
                 - type='content': 正式回复片段
        """
        # 保存用户消息
        self._add_message('user', user_message)

        # 获取历史对话（已包含prompt）
        messages = self._get_all_messages()

        # 调用API获取流式回复
        stream = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            stream=True
        )

        # 拼接完整回复和思考过程
        full_response = ""
        full_thinking = ""
        current_type = None

        # 逐块接收并返回
        for chunk in stream:
            delta = chunk.choices[0].delta
            
            # 检查是否有思考内容（reasoning_content 或 reasoning）
            thinking_content = getattr(delta, 'reasoning_content', None) or getattr(delta, 'reasoning', None)
            
            if thinking_content is not None and len(thinking_content) > 0:
                # 这是思考过程
                if current_type != 'thinking':
                    current_type = 'thinking'
                
                full_thinking += thinking_content
                
                result = {
                    'type': 'thinking',
                    'text': thinking_content
                }
                
                yield result
            
            # 检查是否有正式回复内容
            elif delta.content is not None and len(delta.content) > 0:
                # 这是正式回复
                if current_type != 'content':
                    current_type = 'content'
                
                content = delta.content
                full_response += content
                
                result = {
                    'type': 'content',
                    'text': content
                }
                
                yield result

        # 保存思考过程到数据库（如果有）
        if full_thinking:
            self._add_message('thinking', full_thinking)
            print(f"[对话管理] 已保存思考过程 ({len(full_thinking)} 字符)")

        # 保存完整的AI回复到数据库
        if full_response:
            self._add_message('assistant', full_response)
            print(f"[对话管理] 已保存AI回复 ({len(full_response)} 字符)")

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

    def summarize(self, summary_prompt: Optional[str] = None, save_to_history: bool = False) -> str:
        """
        总结当前对话内容
        
        :param summary_prompt: 自定义总结提示语（可选），如果不提供则使用默认提示
        :param save_to_history: 是否将总结保存到历史记录中，默认为False
        :return: 对话总结内容
        """
        # 获取历史对话（已包含prompt）
        messages = self._get_all_messages()

        # 如果没有消息，返回提示信息
        if len(messages) <= 1:  # 只有system prompt的情况
            return "暂无对话内容可总结"

        # 使用默认提示或自定义提示
        if summary_prompt is None:
            summary_prompt = '请总结以上对话的主要内容，简明扼要地概括讨论的要点。'

        # 添加总结请求（临时，不保存到数据库）
        summary_messages = messages.copy()
        summary_messages.append({
            'role': 'system',
            'content': '请总结以上对话的主要情节，按照时间段划分，将对话分段后写出每段的主要内容。'
                       '随后对小雪的人设进行描述总结，生成一份可以描述小雪这个角色并且能够让AI理解并且扮演该角色的prompt。'
                       '同时还需要总结出小雪的性格特点、行为习惯、说话风格等方面的内容，最后将这些内容整合成一份完整的角色描述。'
                       '（小雪的角色大致分为三个模式：分别是日常的温馨模式、女仆模式以及女王模式，如果对话内容中你认为有其他'
                       '模式的，也请总结出来，但一定要优先表述女仆模式和女王模式）'
        })

        try:
            # 调用API获取总结
            response = self.client.chat.completions.create(
                model=self.model,
                messages=summary_messages
            )

            # 获取总结内容
            summary_content = response.choices[0].message.content

            # 如果需要保存到历史记录
            if save_to_history:
                self._add_message('assistant', f"[对话总结] {summary_content}")

            return summary_content

        except Exception as e:
            error_msg = f"生成总结时出错: {str(e)}"
            print(error_msg)
            return error_msg

    def _get_all_messages(self) -> List[Dict[str, str]]:
        """获取所有消息并转换为OpenAI API格式，如果有prompt则添加在最前面"""
        self.cursor.execute('SELECT source, content FROM messages ORDER BY id ASC')
        rows = self.cursor.fetchall()

        messages = []

        for row in rows:
            if row[0] == 'system':
                pass
            elif row[0] == 'thinking':
                # 思考过程不发送给API，可以选择性忽略或作为上下文
                pass
            else:
                messages.append({'role': row[0], 'content': row[1]})

        # 如果有prompt，添加在最前面
        if self.prompt:
            messages.insert(0, {
                'role': 'system',
                'content': self.prompt
            })

        # print(messages)

        return messages

    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()

    def __del__(self):
        """析构函数，确保关闭数据库连接"""
        self.close()


if __name__ == "__main__":
    api_key = "sk-lrvjaltvcqsawcrjocibgjknvwqsfikirthzntdyyjrdrqqd"
    base_url = "https://api.siliconflow.cn/v1"
    model = "Pro/zai-org/GLM-4.7"

    with open("prompt.txt", "r", encoding="utf-8") as f:
        prompt_content = f.read().strip()


    def summarize_conversation():
        """总结对话内容"""
        client = OpenAI(
            api_key=api_key,
            base_url=base_url
        )
        response = client.chat.completions.create(
            model=model,
            messages=messages
        )

        return response.choices[0].message.content


    # 测试代码
    conn = sqlite3.connect("db/3399752707.db")
    cursor = conn.cursor()

    cursor.execute('SELECT id, source, content FROM messages ORDER BY id ASC')
    length = 0
    messages = []
    for i in cursor.fetchall():
        print(i)
        length += len(i[2])
        messages.append({'role': i[1], 'content': i[2]})
    messages.insert(0, {
        'role': 'system',
        'content': prompt_content
    })
    messages.append({
        'role': 'system',
        'content': '请总结以上对话的主要情节，按照时间段划分，将对话分段后写出每段的主要内容。'
                   '随后对小雪的人设进行描述总结，生成一份可以描述小雪这个角色并且能够让AI理解并且扮演该角色的prompt。'
                   '同时还需要总结出小雪的性格特点、行为习惯、说话风格等方面的内容，最后将这些内容整合成一份完整的角色描述。'
                   '（小雪的角色大致分为三个模式：分别是日常的温馨模式、女仆模式以及女王模式，如果对话内容中你认为有其他'
                   '模式的，也请总结出来，但一定要优先表述女仆模式和女王模式）'
    })
    print(length)

    print(summarize_conversation())
    conn.commit()
    conn.close()
