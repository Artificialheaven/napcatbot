import asyncio
import websockets
import threading
import json

import events
import main_ui
import configs
import globals
from plugin_loader import init_plugin_manager, get_plugin_manager
from bot import bot, logger


async def init_bots(websocket: websockets.ClientConnection):
    data = {
        "action": "get_login_info",
        "params": {},
        "echo": "get_login_info"
    }
    await websocket.send(str(data))


async def start():
    main_ui.add_log(
        '框架',
        'DearQQ',
        '框架正在启动中...',
        '黄色'
    )

    uri = configs.conf.get("ws_address", "ws://47.93.160.124:3001")
    headers = {"Authorization": configs.conf.get("token", "test")}
    async with websockets.connect(uri, additional_headers=headers) as websocket:
        globals.websocket = websocket
        
        # 初始化日志记录器
        bot_logger = logger(main_ui.add_log)
        
        # 初始化Bot实例
        bot_instance = bot(websocket, bot_logger)
        globals.bot_instance = bot_instance
        
        main_ui.add_log(
            '框架',
            '系统',
            'Bot实例已创建',
            '绿色'
        )
        
        # 初始化插件管理器（此时bot_instance已经设置到globals中）
        print("开始初始化插件管理器...")
        manager = init_plugin_manager(websocket)
        print(f"插件管理器初始化完成: {manager}")
        
        main_ui.add_log(
            '框架',
            '系统',
            f'插件管理器已初始化，加载了 {len(manager.plugins)} 个插件',
            '绿色'
        )

        # 主循环：接收和处理消息
        while main_ui.looping:
            _response = await websocket.recv()
            if '"meta_event_type":"heartbeat"' not in _response:
                print(f"Received response: {_response}")
            response = json.loads(_response)
            
            # 检查是否是某个请求的响应（通过echo字段匹配）
            if 'echo' in response and response['echo']:
                if globals.bot_instance and globals.bot_instance.handle_response(response['echo'], response):
                    # 这是一个API调用的响应，已经被Bot处理了
                    continue
            
            # 处理其他事件
            if await events.prase_event(response):
                main_ui.add_log(
                    '框架',
                    'DearQQ',
                    _response,
                    '黄色'
                )


if __name__ == "__main__":
    keep_loop = True

    ui = main_ui.UI()
    threading.Thread(target=lambda: asyncio.run(start())).start()
    ui.setup()
