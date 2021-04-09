import os
import time
from http.server import HTTPServer, BaseHTTPRequestHandler

started_at = time.time()


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(self._html("hi!"))


def run(server_class=HTTPServer, handler_class=BaseHTTPRequestHandler):
    server_address = ('', os.environ['PORT'])
    httpd = server_class(server_address, handler_class)
    httpd.serve_forever()