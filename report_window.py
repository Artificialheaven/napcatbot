import dearpygui.dearpygui as dpg
import globals
import time


# 启动时间
start_time = time.time()


def update_report_display():
    """更新报表显示"""
    if not globals.bot_instance:
        return
    
    stats = globals.bot_instance.get_stats()
    elapsed = time.time() - start_time
    
    # 更新运行时间
    if dpg.does_item_exist("report_runtime"):
        hours = int(elapsed // 3600)
        minutes = int((elapsed % 3600) // 60)
        seconds = int(elapsed % 60)
        dpg.set_value("report_runtime", f"运行时间: {hours}小时 {minutes}分钟 {seconds}秒")
    
    # 更新统计数据
    if dpg.does_item_exist("report_recv_total"):
        dpg.set_value("report_recv_total", str(stats['received']))
    if dpg.does_item_exist("report_sent_total"):
        dpg.set_value("report_sent_total", str(stats['sent']))
    if dpg.does_item_exist("report_total"):
        dpg.set_value("report_total", str(stats['received'] + stats['sent']))
    
    # 更新速率
    if elapsed > 0:
        recv_per_min = stats['received'] / (elapsed / 60)
        sent_per_min = stats['sent'] / (elapsed / 60)
        
        if dpg.does_item_exist("report_recv_rate"):
            dpg.set_value("report_recv_rate", f"{recv_per_min:.2f} 条/分钟")
        if dpg.does_item_exist("report_sent_rate"):
            dpg.set_value("report_sent_rate", f"{sent_per_min:.2f} 条/分钟")


def show_report_window():
    """显示报表窗口"""
    report_window = "report_window"
    
    # 如果窗口已存在，直接显示并更新
    if dpg.does_item_exist(report_window):
        update_report_display()
        dpg.show_item(report_window)
        return report_window
    
    # 创建新窗口
    with dpg.window(label="统计报表", tag=report_window, width=700, height=500, pos=[150, 75]):
        dpg.add_text("消息统计报表", color=[255, 255, 0, 255])
        dpg.add_separator()
        
        # 运行时间
        elapsed = time.time() - start_time
        hours = int(elapsed // 3600)
        minutes = int((elapsed % 3600) // 60)
        seconds = int(elapsed % 60)
        
        dpg.add_text(f"运行时间: {hours}小时 {minutes}分钟 {seconds}秒", color=[200, 200, 200, 255], tag="report_runtime")
        dpg.add_spacer(height=10)
        
        # 总体统计
        with dpg.child_window(width=660, height=200):
            dpg.add_text("总体统计", color=[255, 255, 0, 255])
            dpg.add_separator()
            
            if globals.bot_instance:
                stats = globals.bot_instance.get_stats()
                
                with dpg.group(horizontal=True):
                    dpg.add_text("📨 总接收消息:", color=[100, 255, 100, 255])
                    dpg.add_text(f"{stats['received']}", color=[255, 255, 255, 255], tag="report_recv_total")
                
                dpg.add_spacer(height=10)
                
                with dpg.group(horizontal=True):
                    dpg.add_text("📤 总发送消息:", color=[100, 100, 255, 255])
                    dpg.add_text(f"{stats['sent']}", color=[255, 255, 255, 255], tag="report_sent_total")
                
                dpg.add_spacer(height=10)
                
                total = stats['received'] + stats['sent']
                with dpg.group(horizontal=True):
                    dpg.add_text("📊 消息总量:", color=[255, 255, 100, 255])
                    dpg.add_text(f"{total}", color=[255, 255, 255, 255], tag="report_total")
                
                dpg.add_spacer(height=20)
                
                # 平均速率
                if elapsed > 0:
                    recv_per_min = stats['received'] / (elapsed / 60)
                    sent_per_min = stats['sent'] / (elapsed / 60)
                    
                    with dpg.group(horizontal=True):
                        dpg.add_text("⚡ 平均接收速率:", color=[200, 200, 200, 255])
                        dpg.add_text(f"{recv_per_min:.2f} 条/分钟", color=[255, 255, 255, 255], tag="report_recv_rate")
                    
                    with dpg.group(horizontal=True):
                        dpg.add_text("⚡ 平均发送速率:", color=[200, 200, 200, 255])
                        dpg.add_text(f"{sent_per_min:.2f} 条/分钟", color=[255, 255, 255, 255], tag="report_sent_rate")
            else:
                dpg.add_text("Bot未初始化", color=[255, 100, 100, 255])
        
        dpg.add_spacer(height=20)
        
        # 刷新按钮
        with dpg.group(horizontal=True):
            dpg.add_button(
                label="刷新数据",
                width=100,
                height=30,
                callback=lambda: update_report_display()
            )
            dpg.add_button(
                label="关闭",
                width=80,
                height=30,
                callback=lambda: dpg.hide_item("report_window")
            )
    
    return report_window


def get_start_time():
    """获取启动时间"""
    return start_time

