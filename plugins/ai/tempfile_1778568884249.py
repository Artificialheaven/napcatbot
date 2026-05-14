from silicon import ConversationManager


# 新建对话，从文件加载prompt
conv = ConversationManager(
    conversation_id="chat_001",
    prompt_path="prompt.txt"
)

# 对话
# response = conv.chat("你好")
# print(response)

# 查看历史
# history = conv.history()
# for msg in history:
    # print(f"{msg['source']}: {msg['content']}")

# 总结对话
# summary = conv.summarize()
# print(summary)

# 关闭连接
conv.close()
