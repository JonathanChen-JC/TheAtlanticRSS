import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import requests

# 配置
HOST = '0.0.0.0'
PORT = 8080
PING_INTERVAL = 300  # 5分钟

class HealthCheckHandler(BaseHTTPRequestHandler):
    """健康检查处理器"""
    def do_GET(self):
        if self.path == '/health':
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'OK')
        else:
            self.send_response(404)
            self.end_headers()

def run_server():
    """运行HTTP服务器"""
    server = HTTPServer((HOST, PORT), HealthCheckHandler)
    print(f"服务器启动在 http://{HOST}:{PORT}")
    server.serve_forever()

def ping_self():
    """定期ping自己"""
    while True:
        try:
            response = requests.get(f'http://localhost:{PORT}/health')
            print(f"Ping状态: {response.status_code}")
        except Exception as e:
            print(f"Ping失败: {str(e)}")
        time.sleep(PING_INTERVAL)

def main():
    """主函数"""
    try:
        # 启动HTTP服务器线程
        server_thread = threading.Thread(target=run_server, daemon=True)
        server_thread.start()
        
        # 启动ping线程
        ping_thread = threading.Thread(target=ping_self)
        ping_thread.start()
        
        # 保持主线程运行
        server_thread.join()
    except Exception as e:
        print(f"程序运行出错：{str(e)}")

if __name__ == "__main__":
    main()