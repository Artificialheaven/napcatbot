import dearpygui.dearpygui as dpg
import globals
import time


# 消息统计数据
minute_stats = []  # 每分钟统计 [(timestamp, received, sent), ...]
current_minute_received = 0
current_minute_sent = 0
last_minute_check = time.time()


def update_minute_stats():
    """更新每分钟统计数据"""
    global current_minute_received, current_minute_sent, last_minute_check
    
    now = time.time()
    elapsed = now - last_minute_check
    
    # 每60秒记录一次
    if elapsed >= 60:
        if globals.bot_instance:
            stats = globals.bot_instance.get_stats()
            minute_stats.append({
                'time': time.strftime('%H:%M', time.localtime(now)),
                'received': current_minute_received,
                'sent': current_minute_sent
            })
            
            # 重置当前分钟计数
            current_minute_received = 0
            current_minute_sent = 0
            last_minute_check = now
            
            # 只保留最近60分钟的数据
            if len(minute_stats) > 60:
                minute_stats.pop(0)


def update_monitor_display():
    """更新监控显示"""
    if globals.bot_instance:
        stats = globals.bot_instance.get_stats()
        
        # 更新总数
        if dpg.does_item_exist("monitor_recv_total"):
            dpg.set_value("monitor_recv_total", str(stats['received']))
        if dpg.does_item_exist("monitor_sent_total"):
            dpg.set_value("monitor_sent_total", str(stats['sent']))
        
        # 更新当前分钟
        if dpg.does_item_exist("monitor_recv_current"):
            dpg.set_value("monitor_recv_current", str(current_minute_received))
        if dpg.does_item_exist("monitor_sent_current"):
            dpg.set_value("monitor_sent_current", str(current_minute_sent))
        
        # 更新图表
        update_monitor_chart()


def update_monitor_chart():
    """更新监控图表"""
    if not dpg.does_item_exist("monitor_chart_content"):
        return
    
    if not minute_stats:
        dpg.set_value("monitor_chart_content", "暂无数据，请等待一分钟...")
        return
    
    # 生成简单的柱状图（文本形式）
    chart_lines = []
    max_value = max(max(s['received'], s['sent']) for s in minute_stats) if minute_stats else 1
    if max_value == 0:
        max_value = 1
    
    chart_height = 15
    
    # 显示最近30分钟
    display_stats = minute_stats[-30:]
    
    for i, stat in enumerate(display_stats):
        recv_bar = int((stat['received'] / max_value) * chart_height)
        sent_bar = int((stat['sent'] / max_value) * chart_height)
        
        line = f"{stat['time']} | "
        line += "█" * recv_bar + " " * (chart_height - recv_bar)
        line += f" | 收:{stat['received']:3d} "
        line += "█" * sent_bar + " " * (chart_height - sent_bar)
        line += f" | 发:{stat['sent']:3d}"
        
        chart_lines.append(line)
    
    # 添加图例
    legend = "\n图例: ███ 接收消息   ███ 发送消息"
    dpg.set_value("monitor_chart_content", "\n".join(chart_lines) + legend)


def show_monitor_window():
    """显示监控窗口"""
    monitor_window = "monitor_window"
    
    # 如果窗口已存在，直接显示并更新
    if dpg.does_item_exist(monitor_window):
        dpg.show_item(monitor_window)
        update_monitor_display()
        return monitor_window
    
    # 创建新窗口
    with dpg.window(label="实时监控", tag=monitor_window, width=800, height=500, pos=[100, 50]):
        dpg.add_text("消息监控 - 实时统计", color=[255, 255, 0, 255])
        dpg.add_separator()
        
        # 实时统计卡片
        with dpg.group(horizontal=True):
            # 接收消息卡片
            with dpg.child_window(width=380, height=150):
                dpg.add_text("📨 接收消息", color=[100, 255, 100, 255])
                dpg.add_spacer(height=10)
                dpg.add_text("本分钟:", color=[200, 200, 200, 255])
                dpg.add_text(f"{current_minute_received}", color=[255, 255, 255, 255], tag="monitor_recv_current")
                dpg.add_spacer(height=10)
                dpg.add_text("总计:", color=[200, 200, 200, 255])
                dpg.add_text("0", color=[255, 255, 255, 255], tag="monitor_recv_total")
            
            # 发送消息卡片
            with dpg.child_window(width=380, height=150):
                dpg.add_text("📤 发送消息", color=[100, 100, 255, 255])
                dpg.add_spacer(height=10)
                dpg.add_text("本分钟:", color=[200, 200, 200, 255])
                dpg.add_text(f"{current_minute_sent}", color=[255, 255, 255, 255], tag="monitor_sent_current")
                dpg.add_spacer(height=10)
                dpg.add_text("总计:", color=[200, 200, 200, 255])
                dpg.add_text("0", color=[255, 255, 255, 255], tag="monitor_sent_total")
        
        dpg.add_spacer(height=20)
        dpg.add_text("最近60分钟趋势", color=[255, 255, 0, 255])
        dpg.add_separator()
        
        # 简单的文本图表
        with dpg.child_window(width=760, height=250, tag="monitor_chart"):
            dpg.add_text("加载中...", color=[200, 200, 200, 255], tag="monitor_chart_content")
    
    # 更新监控数据
    update_monitor_display()
    
    return monitor_window


def increment_received():
    """增加接收消息计数"""
    global current_minute_received
    current_minute_received += 1


def increment_sent():
    """增加发送消息计数"""
    global current_minute_sent
    current_minute_sent += 1


def get_current_stats():
    """获取当前分钟的统计数据"""
    return {
        'received': current_minute_received,
        'sent': current_minute_sent
    }

