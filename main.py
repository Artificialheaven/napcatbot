import asyncio
import websockets
import threading
import json
import time

from core import events
from ui import main_ui
import configs
from core import globals
from utils.plugin_loader import init_plugin_manager, get_plugin_manager
from core.bot import bot, logger


async def init_bots(websocket: websockets.ClientConnection):
    data = {
        "action": "get_login_info",
        "params": {},
        "echo": "get_login_info"
    }
    await websocket.send(json.dumps(data, ensure_ascii=False))


def start_background_data_fetch():
    """在后台启动数据获取任务"""
    from ui.report_window import fetch_and_update_data
    
    def fetch_task():
        # 等待 Bot 初始化完成
        time.sleep(2)
        
        if globals.bot_instance:
            print("[系统] 开始在后台获取群列表和好友列表...")
            fetch_and_update_data()
        else:
            print("[系统] Bot 未初始化，跳过数据获取")
    
    # 启动后台线程
    thread = threading.Thread(target=fetch_task, daemon=True)
    thread.start()
    print("[系统] 后台数据获取任务已启动")


async def connect_and_run():
    """
    连接WebSocket并运行主循环
    使用循环而非递归来避免栈溢出
    """
    uri = configs.conf.get("ws_address", "ws://47.93.160.124:3001")
    headers = {"Authorization": configs.conf.get("token", "test")}
    
    # 从配置中读取重连参数
    max_attempts = configs.conf.get("max_reconnect_attempts", 0)  # 0表示无限重试
    base_delay = configs.conf.get("reconnect_base_delay", 2)
    max_delay = configs.conf.get("reconnect_max_delay", 60)
    
    reconnect_count = 0
    
    while main_ui.looping:
        # 检查是否超过最大重连次数
        if max_attempts > 0 and reconnect_count >= max_attempts:
            main_ui.add_log(
                '框架',
                '系统',
                f'已达到最大重连次数 ({max_attempts})，停止重连',
                '红色'
            )
            break
        
        # 计算重连延迟（指数退避）
        if reconnect_count > 0:
            delay = min(base_delay * (2 ** (reconnect_count - 1)), max_delay)
            main_ui.add_log(
                '框架',
                '系统',
                f'将在 {delay:.1f} 秒后尝试第 {reconnect_count + 1} 次重连...',
                '黄色'
            )
            await asyncio.sleep(delay)
        
        try:
            main_ui.add_log(
                '框架',
                'DearQQ',
                f'正在连接到 {uri}...',
                '黄色'
            )
            
            async with websockets.connect(uri, additional_headers=headers) as websocket:
                globals.websocket = websocket
                
                # 重置重连计数
                reconnect_count = 0
                
                main_ui.add_log(
                    '框架',
                    '系统',
                    'WebSocket连接成功',
                    '绿色'
                )
                
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
                
                # 发送登录信息请求
                await init_bots(websocket)
                
                # 启动后台数据获取（在插件加载完成后）
                start_background_data_fetch()

                # 主循环：接收和处理消息
                while main_ui.looping:
                    try:
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
                    
                    except websockets.exceptions.ConnectionClosed as e:
                        main_ui.add_log(
                            '框架',
                            '系统',
                            f'WebSocket连接关闭: {e.code} - {e.reason}',
                            '红色'
                        )
                        break
                    
                    except websockets.exceptions.ConnectionClosedError as e:
                        main_ui.add_log(
                            '框架',
                            '系统',
                            f'WebSocket连接错误: {e}',
                            '红色'
                        )
                        break
                    
                    except Exception as e:
                        main_ui.add_log(
                            '框架',
                            '系统',
                            f'处理消息时出错: {type(e).__name__}: {e}',
                            '红色'
                        )
                        import traceback
                        traceback.print_exc()
                        break
        
        except websockets.exceptions.InvalidStatusCode as e:
            main_ui.add_log(
                '框架',
                '系统',
                f'连接失败: HTTP {e.status_code}',
                '红色'
            )
            reconnect_count += 1
            continue
        
        except websockets.exceptions.InvalidURI:
            main_ui.add_log(
                '框架',
                '系统',
                f'无效的WebSocket URI: {uri}',
                '红色'
            )
            break
        
        except ConnectionRefusedError:
            main_ui.add_log(
                '框架',
                '系统',
                '连接被拒绝，请检查服务器是否运行',
                '红色'
            )
            reconnect_count += 1
            continue
        
        except OSError as e:
            main_ui.add_log(
                '框架',
                '系统',
                f'网络错误: {e}',
                '红色'
            )
            reconnect_count += 1
            continue
        
        except Exception as e:
            main_ui.add_log(
                '框架',
                '系统',
                f'连接错误: {type(e).__name__}: {e}',
                '红色'
            )
            reconnect_count += 1
            continue
        
        # 如果到达这里，说明内层while循环break了（连接断开）
        if not main_ui.looping:
            main_ui.add_log(
                '框架',
                '系统',
                '程序已停止，不再重连',
                '默认'
            )
            break
        
        # 准备重连
        main_ui.add_log(
            '框架',
            '系统',
            '检测到连接断开，准备重连...',
            '黄色'
        )
        
        # 清空当前的bot实例和websocket
        globals.bot_instance = None
        globals.websocket = None
        
        # 增加重连计数
        reconnect_count += 1


async def start():
    """启动函数"""
    main_ui.add_log(
        '框架',
        'DearQQ',
        '框架正在启动中...',
        '黄色'
    )
    
    try:
        await connect_and_run()
    except Exception as e:
        if main_ui.looping:
            main_ui.add_log(
                '框架',
                '系统',
                f'启动失败: {type(e).__name__}: {e}',
                '红色'
            )
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    print("DearQQ启动中...")
    keep_loop = True

    ui = main_ui.UI()
    threading.Thread(target=lambda: asyncio.run(start())).start()
    ui.setup()
