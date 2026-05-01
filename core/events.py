import websockets
import dearpygui.dearpygui as dpg
import asyncio

from ui.main_ui import add_log
from core import globals
from utils.plugin_loader import get_plugin_manager
from ui.monitor_window import increment_received


# 存储正在运行的插件任务，用于管理和清理
plugin_tasks = set()


async def init_bots(websocket: websockets.ClientConnection):
    data = {
        "action": "get_login_info",
        "params": {},
        "echo": "get_login_info"
    }
    await websocket.send(str(data))


async def prase_event(event: dict):
    ret = True

    if 'echo' in event:
        if event['echo'] == 'get_login_info':
            dpg.set_value('name', f"{event['data']['nickname']}({event['data']['user_id']})")
            globals.bot_id = event['data']['user_id']
        globals.echo_dict[event['echo']] = event
        ret = False
        return ret

    if event['post_type'] == 'meta_event':
        if event['meta_event_type'] == 'lifecycle':
            if event['sub_type'] == 'connect':
                print('wtf')
                add_log(
                    '框架',
                    'DearQQ',
                    '已成功链接到NapcatQQ',
                    '黄色'
                )
                await init_bots(globals.websocket)
                ret = False

        if event['meta_event_type'] == 'heartbeat':
            if globals.show_heart_beat:
                add_log(
                    'Napcat',
                    '心跳',
                    '心跳包收到√',
                    '黄色'
                )
            else:
                pass
            ret = False

    if event['post_type'] == 'message':
        if event['message_type'] == 'group':
            add_log(
                f'{event["self_id"]}',
                f'{event["group_name"]}({event["group_id"]})',
                f'{event["sender"]["nickname"]}({event["sender"]["user_id"]}) 说:{event["raw_message"]}',
                '绿色'
            )
            
            # 增加接收消息计数
            increment_received()
            
            # 调用插件的消息处理函数
            plugin_manager = get_plugin_manager()
            if plugin_manager:
                handlers = plugin_manager.get_event_handlers('message')
                for handler_info in handlers:
                    try:
                        callback = handler_info['callback']
                        plugin_name = handler_info['plugin_name']
                        
                        # 检查是否是协程函数
                        if asyncio.iscoroutinefunction(callback):
                            # 创建任务并立即返回，不等待完成，传递插件名称
                            task = asyncio.create_task(_safe_execute_handler(callback, event, plugin_name))
                            plugin_tasks.add(task)
                            # 任务完成后自动从集合中移除
                            task.add_done_callback(plugin_tasks.discard)
                        else:
                            # 同步函数在线程池中执行，避免阻塞
                            loop = asyncio.get_event_loop()
                            loop.run_in_executor(None, _safe_sync_handler, callback, event)
                    except Exception as e:
                        print(f"插件处理消息失败: {e}")
                        import traceback
                        traceback.print_exc()
            
            ret = False

    return ret


async def _safe_execute_handler(handler, event, plugin_name=None):
    """安全地执行异步插件处理器"""
    try:
        # 将插件名称注入到事件对象中，供插件使用
        if plugin_name:
            event['_plugin_name'] = plugin_name
        await handler(event)
    except Exception as e:
        print(f"插件异步处理器出错: {e}")
        import traceback
        traceback.print_exc()


def _safe_sync_handler(handler, event):
    """安全地执行同步插件处理器"""
    try:
        handler(event)
    except Exception as e:
        print(f"插件同步处理器出错: {e}")
        import traceback
        traceback.print_exc()


async def cleanup_tasks():
    """清理未完成的任务（在程序退出时调用）"""
    if plugin_tasks:
        print(f"等待 {len(plugin_tasks)} 个插件任务完成...")
        await asyncio.gather(*plugin_tasks, return_exceptions=True)
        print("所有插件任务已完成")
