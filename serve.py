#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
极简静态服务，用于托管 build/ 目录。

必须自定义 .ics 的 Content-Type 为 text/calendar，
否则 Google 日历抓取订阅源时可能拒绝解析。

用法：
    python3 serve.py            # 监听 8080，服务 ./build
    python3 serve.py 80 ./build
"""
import os
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, 'build')


class ICSHandler(SimpleHTTPRequestHandler):
    extensions_map = dict(SimpleHTTPRequestHandler.extensions_map)
    extensions_map.update({
        '.ics': 'text/calendar; charset=utf-8',
        '.json': 'application/json; charset=utf-8',
    })

    def guess_type(self, path):
        mtype = super().guess_type(path)
        if path.endswith('.ics') and 'calendar' not in mtype:
            return 'text/calendar; charset=utf-8'
        return mtype

    def end_headers(self):
        # 允许 Google 日历等外部服务跨域抓取
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Cache-Control', 'public, max-age=1800')
        super().end_headers()

    def log_message(self, fmt, *args):
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    directory = sys.argv[2] if len(sys.argv) > 2 else ROOT
    directory = os.path.abspath(directory)
    os.makedirs(directory, exist_ok=True)
    os.chdir(directory)
    srv = ThreadingHTTPServer(('0.0.0.0', port), ICSHandler)
    print(f'serving {directory} on 0.0.0.0:{port}')
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print('\nbye')


if __name__ == '__main__':
    main()
