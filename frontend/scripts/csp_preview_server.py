#!/usr/bin/env python3
"""Serve frontend/dist with the same security headers as vercel.json for CSP smoke tests.

Usage:
  npm run build
  python3 scripts/csp_preview_server.py
  node scripts/verify_csp.mjs   # requires: npx playwright install chromium
"""
import os
import sys
from http.server import HTTPServer, SimpleHTTPRequestHandler

CSP = (
    "default-src 'self'; "
    "connect-src 'self' https://mytradingbot-project.onrender.com; "
    "img-src 'self' data:; "
    "style-src 'self'; "
    "script-src 'self'; "
    "font-src 'self'; "
    "object-src 'none'; "
    "base-uri 'self'; "
    "frame-ancestors 'none'"
)
SECURITY_HEADERS = {
    "Content-Security-Policy": CSP,
    "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=(), payment=()",
}


class CSPHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        for name, value in SECURITY_HEADERS.items():
            self.send_header(name, value)
        super().end_headers()

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        local_path = self.translate_path(path)
        if path != "/" and not os.path.isfile(local_path):
            self.path = "/index.html"
        return SimpleHTTPRequestHandler.do_GET(self)

    def log_message(self, format, *args):
        pass


def main():
    dist_dir = os.path.join(os.path.dirname(__file__), "..", "dist")
    dist_dir = os.path.abspath(dist_dir)
    if not os.path.isdir(dist_dir):
        print("Run `npm run build` first.", file=sys.stderr)
        sys.exit(1)

    os.chdir(dist_dir)
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 4173
    server = HTTPServer(("127.0.0.1", port), CSPHandler)
    print(f"CSP preview server on http://127.0.0.1:{port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
