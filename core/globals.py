import websockets
import configs

show_heart_beat = configs.conf.get("show_heartbeat", True)
websocket: websockets.ClientConnection = None
echo_dict = {}
bot_instance = None
bot_id = 0
no_gui = False
