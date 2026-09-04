# FILE: app/esi/auth_server.py
# VERSION: 1.1.0

import http.server
import socketserver
import time
import urllib.parse
from typing import Optional, Tuple


class LoginCancelledError(Exception):
    """Raised when the user cancels the login flow."""


class LoginTimeoutError(Exception):
    """Raised when no callback is received before the timeout."""


class CallbackHandler(http.server.BaseHTTPRequestHandler):
    """
    Handles the local OAuth callback.
    """

    def do_GET(self):
        query = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(query)

        self.server.auth_code = params.get("code", [None])[0]
        self.server.auth_state = params.get("state", [None])[0]
        self.server.received_callback = True

        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()

        html = (
            b"<html><body style='background:#14171c;color:#d7dde6;"
            b"font-family:sans-serif;text-align:center;padding-top:50px;'>"
            b"<h1>Login successful!</h1>"
            b"<p>You can close this window and return to the app.</p>"
            b"</body></html>"
        )
        self.wfile.write(html)

    def log_message(self, format, *args):
        pass


class LocalAuthServer(socketserver.TCPServer):
    allow_reuse_address = True
    auth_code = None
    auth_state = None
    received_callback = False


def run_server(
    port: int = 8635,
    timeout: int = 120,
    stop_event=None,
) -> Tuple[Optional[str], Optional[str]]:
    """
    Run the local callback server until:
        - the callback arrives,
        - the timeout is reached,
        - or stop_event is set (user cancelled).
    """
    server = LocalAuthServer(("127.0.0.1", port), CallbackHandler)
    server.timeout = 1

    deadline = time.time() + timeout

    try:
        while not server.received_callback:
            if stop_event is not None and stop_event.is_set():
                raise LoginCancelledError("Login cancelled by user.")

            if time.time() > deadline:
                raise LoginTimeoutError(
                    "No login callback received within timeout."
                )

            server.handle_request()
    finally:
        server.server_close()

    return server.auth_code, server.auth_state