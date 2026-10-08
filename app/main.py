"""Serve only the lab's public assets and minimal release metadata."""

from dataclasses import dataclass
from html import escape
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import logging
import os
from pathlib import Path
import re
import signal
from typing import Mapping
from urllib.parse import unquote, urlsplit


SITE_DIR = Path(__file__).resolve().parent.parent / "site"
PUBLIC_ASSETS = {
    "/styles.css": ("styles.css", "text/css; charset=utf-8"),
    "/favicon.svg": ("favicon.svg", "image/svg+xml"),
}
PUBLIC_ROUTES = {"/", "/index.html", "/health", *PUBLIC_ASSETS}
SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'none'; style-src 'self'; img-src 'self'; "
        "base-uri 'none'; frame-ancestors 'none'; form-action 'none'; "
        "object-src 'none'"
    ),
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": (
        "accelerometer=(), camera=(), geolocation=(), gyroscope=(), "
        "microphone=(), payment=(), usb=()"
    ),
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
}


@dataclass(frozen=True)
class Settings:
    environment: str = "qa"
    release_commit: str = "local"
    port: int = 8080

    @classmethod
    def from_environment(cls, environ: Mapping[str, str] | None = None):
        values = os.environ if environ is None else environ
        environment = values.get("APP_ENV", "qa").lower()
        if environment not in {"qa", "production"}:
            raise ValueError("APP_ENV must be qa or production")
        release_commit = values.get("RELEASE_COMMIT", "local").lower()
        if release_commit != "local" and not re.fullmatch(r"[0-9a-f]{7,40}", release_commit):
            raise ValueError("RELEASE_COMMIT must be a Git commit or local")
        try:
            port = int(values.get("PORT", "8080"))
        except ValueError:
            raise ValueError("PORT must be an integer") from None
        if not 1 <= port <= 65535:
            raise ValueError("PORT must be between 1 and 65535")
        return cls(environment, release_commit, port)


def make_handler(settings: Settings, site_dir: Path = SITE_DIR):
    # Read a fixed allowlist once. No request can choose a filesystem path.
    template = (site_dir / "index.html").read_text(encoding="utf-8")
    page = (
        template.replace("{{APP_ENV}}", escape(settings.environment))
        .replace("{{ENV_LABEL}}", "QA" if settings.environment == "qa" else "Production")
        .replace("{{RELEASE_COMMIT}}", escape(settings.release_commit))
        .replace("{{SHORT_COMMIT}}", escape(settings.release_commit[:12]))
        .encode("utf-8")
    )
    assets = {
        route: ((site_dir / filename).read_bytes(), content_type)
        for route, (filename, content_type) in PUBLIC_ASSETS.items()
    }
    health = json.dumps(
        {
            "status": "ok",
            "app": "asteri-deployment-lab",
            "environment": settings.environment,
            "revision": settings.release_commit,
        },
        separators=(",", ":"),
    ).encode("utf-8") + b"\n"

    class LabHandler(BaseHTTPRequestHandler):
        server_version = "AsteriLab"
        sys_version = ""
        protocol_version = "HTTP/1.1"

        def version_string(self):
            return self.server_version

        def setup(self):
            super().setup()
            self.connection.settimeout(10)

        def _route(self):
            try:
                return unquote(urlsplit(getattr(self, "path", "")).path, errors="strict")
            except (ValueError, UnicodeDecodeError):
                return ""

        def _send(self, status, body, content_type, *, cache="no-store", allow=None):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", cache)
            self.send_header("Connection", "close")
            for name, value in SECURITY_HEADERS.items():
                self.send_header(name, value)
            if allow:
                self.send_header("Allow", allow)
            self.end_headers()
            self.close_connection = True
            if self.command != "HEAD":
                self.wfile.write(body)

        def do_GET(self):
            route = self._route()
            if route in {"/", "/index.html"}:
                self._send(HTTPStatus.OK, page, "text/html; charset=utf-8")
            elif route == "/health":
                self._send(HTTPStatus.OK, health, "application/json; charset=utf-8")
            elif route in assets:
                body, content_type = assets[route]
                self._send(HTTPStatus.OK, body, content_type, cache="public, max-age=300")
            else:
                self._send(HTTPStatus.NOT_FOUND, b"Not found.\n", "text/plain; charset=utf-8")

        def do_HEAD(self):
            self.do_GET()

        def _method_not_allowed(self):
            self._send(
                HTTPStatus.METHOD_NOT_ALLOWED,
                b"Method not allowed.\n",
                "text/plain; charset=utf-8",
                allow="GET, HEAD",
            )

        do_POST = _method_not_allowed
        do_PUT = _method_not_allowed
        do_PATCH = _method_not_allowed
        do_DELETE = _method_not_allowed
        do_OPTIONS = _method_not_allowed
        do_TRACE = _method_not_allowed
        do_CONNECT = _method_not_allowed

        def send_error(self, code, message=None, explain=None):
            # Parser errors also avoid reflecting request content or Python details.
            self._send(code, b"Request rejected.\n", "text/plain; charset=utf-8")

        def log_request(self, code="-", size="-"):
            route = self._route()
            route = route if route in PUBLIC_ROUTES else "/unknown"
            command = getattr(self, "command", None)
            method = command if command in {"GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "TRACE", "CONNECT"} else "OTHER"
            logging.info("request method=%s route=%s status=%s", method, route, code)

        def log_message(self, format, *args):
            # Avoid logging raw headers, query strings, or malformed request text.
            return

    return LabHandler


def make_server(settings: Settings, host="0.0.0.0", port=None, site_dir=SITE_DIR):
    server = ThreadingHTTPServer(
        (host, settings.port if port is None else port), make_handler(settings, site_dir)
    )
    server.daemon_threads = True
    return server


def _stop(_signal, _frame):
    raise KeyboardInterrupt


def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    try:
        settings = Settings.from_environment()
    except ValueError as error:
        raise SystemExit(str(error)) from None
    signal.signal(signal.SIGTERM, _stop)
    with make_server(settings) as server:
        logging.info("lab listening port=%s environment=%s", settings.port, settings.environment)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            logging.info("lab stopped")


if __name__ == "__main__":
    main()
