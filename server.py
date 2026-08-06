#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Локальный сервер репетитора с запретом кеша (чтобы правки видны сразу)."""
import http.server
import socketserver

PORT = 8777


class NoCacheHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def log_message(self, *a):
        pass  # тихо


socketserver.TCPServer.allow_reuse_address = True
with socketserver.TCPServer(("0.0.0.0", PORT), NoCacheHandler) as httpd:
    httpd.serve_forever()
