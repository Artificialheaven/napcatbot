import socket
import struct


class RCONClient:
    """Minecraft RCON客户端"""

    # 数据包类型常量
    AUTH_RESPONSE = 2
    EXECCOMMAND_RESPONSE = 0
    AUTH_REQUEST = 3
    EXECCOMMAND_REQUEST = 2

    def __init__(self, host: str, port: int, password: str):
        """
        初始化RCON客户端

        Args:
            host: RCON服务器地址
            port: RCON端口
            password: RCON密码
        """
        self.host = host
        self.port = port
        self.password = password
        self.socket = None
        self.request_id = 1
        self.authenticated = False

    def connect(self) -> bool:
        """
        连接到RCON服务器并认证

        Returns:
            bool: 是否连接成功
        """
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.host, self.port))
            self.socket.settimeout(5.0)

            # 发送认证请求
            if self._authenticate():
                self.authenticated = True
                print("✓ RCON连接成功!")
                return True
            else:
                print("✗ 认证失败!")
                self.disconnect()
                return False

        except ConnectionRefusedError:
            print("✗ 连接被拒绝，请检查服务器地址和端口")
            return False
        except socket.timeout:
            print("✗ 连接超时")
            return False
        except Exception as e:
            print(f"✗ 连接错误: {e}")
            return False

    def disconnect(self):
        """断开RCON连接"""
        if self.socket:
            self.socket.close()
            self.socket = None
        self.authenticated = False
        print("RCON连接已断开")

    def _send_packet(self, packet_type: int, payload: str) -> int:
        """
        发送RCON数据包

        Args:
            packet_type: 数据包类型
            payload: 载荷数据

        Returns:
            int: 响应ID
        """
        # 编码payload为UTF-8
        payload_bytes = payload.encode('utf-8')

        # 构建数据包结构:
        # 4字节: 数据包长度 (request_id + packet_type + payload + 2字节空终止符)
        # 4字节: 请求ID
        # 4字节: 数据包类型
        # N字节: payload
        # 2字节: 空终止符 (\x00\x00)

        packet_length = 4 + 4 + len(payload_bytes) + 2
        request_id = self.request_id

        # 打包数据包
        packet = struct.pack('<ii', packet_length, request_id)
        packet += struct.pack('<i', packet_type)
        packet += payload_bytes
        packet += b'\x00\x00'

        # 发送数据包
        self.socket.sendall(packet)

        # 递增请求ID
        self.request_id += 1

        return request_id

    def _receive_packet(self) -> tuple:
        """
        接收RCON响应数据包

        Returns:
            tuple: (response_id, packet_type, payload)
        """
        # 读取数据包长度 (4字节)
        length_data = self._recv_exact(4)
        if not length_data:
            raise ConnectionError("无法读取数据包长度")

        packet_length = struct.unpack('<i', length_data)[0]

        # 读取剩余数据
        remaining_data = self._recv_exact(packet_length)
        if not remaining_data:
            raise ConnectionError("无法读取数据包内容")

        # 解析数据包
        response_id = struct.unpack('<i', remaining_data[0:4])[0]
        packet_type = struct.unpack('<i', remaining_data[4:8])[0]
        payload = remaining_data[8:-2].decode('utf-8')  # 去掉最后的2字节空终止符

        return response_id, packet_type, payload

    def _recv_exact(self, num_bytes: int) -> bytes:
        """
        精确接收指定字节数的数据

        Args:
            num_bytes: 需要接收的字节数

        Returns:
            bytes: 接收到的数据
        """
        data = b''
        while len(data) < num_bytes:
            chunk = self.socket.recv(num_bytes - len(data))
            if not chunk:
                return None
            data += chunk
        return data

    def _authenticate(self) -> bool:
        """
        向服务器认证

        Returns:
            bool: 是否认证成功
        """
        self._send_packet(self.AUTH_REQUEST, self.password)

        try:
            response_id, packet_type, payload = self._receive_packet()

            # 认证成功返回 AUTH_RESPONSE 类型且 response_id != -1
            # 认证失败返回 AUTH_RESPONSE 类型且 response_id == -1
            if packet_type == self.AUTH_RESPONSE and response_id != -1:
                return True
            return False
        except Exception:
            return False

    def execute_command(self, command: str) -> str:
        """
        执行RCON命令

        Args:
            command: 要执行的命令

        Returns:
            str: 命令输出结果
        """
        if not self.authenticated:
            raise Exception("未连接到RCON服务器或未认证")

        try:
            self._send_packet(self.EXECCOMMAND_REQUEST, command)
            response_id, packet_type, payload = self._receive_packet()
            return payload
        except socket.timeout:
            return "命令执行超时"
        except Exception as e:
            return f"执行命令时出错: {e}"

    def __enter__(self):
        """上下文管理器入口"""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.disconnect()


def main():
    """主函数 - 交互式RCON客户端"""
    print("=" * 50)
    print("  Minecraft RCON 客户端")
    print("=" * 50)

    # 获取连接信息
    host = input("\n服务器地址 (默认: localhost): ").strip() or "localhost"

    try:
        port = int(input("RCON端口 (默认: 25575): ").strip() or "25575")
    except ValueError:
        print("无效的端口号，使用默认端口 25575")
        port = 25575

    password = input("RCON密码: ").strip()

    if not password:
        print("错误: 密码不能为空")
        return

    # 连接并进入交互模式
    with RCONClient(host, port, password) as client:
        if not client.authenticated:
            return

        print("\n输入命令 (输入 'quit' 或 'exit' 退出):")

        while True:
            try:
                command = input("\n> ").strip()

                if command.lower() in ['quit', 'exit', 'q']:
                    break

                if not command:
                    continue

                result = client.execute_command(command)
                print(result if result else "(无输出)")

            except KeyboardInterrupt:
                print("\n\n中断操作...")
                break
            except Exception as e:
                print(f"错误: {e}")
                break


if __name__ == "__main__":
    main()
