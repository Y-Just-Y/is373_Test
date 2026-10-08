"""Verify the public HTTP contract and file/metadata boundaries."""

from http.client import HTTPConnection
import json
import threading
import unittest

from app.main import SECURITY_HEADERS, Settings, make_server


class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.revision = "a" * 40
        cls.server = make_server(Settings("qa", cls.revision), "127.0.0.1", 0)
        cls.thread = threading.Thread(
            target=cls.server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True
        )
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def request(self, path, method="GET", body=None):
        connection = HTTPConnection(*self.server.server_address, timeout=3)
        try:
            connection.request(method, path, body=body)
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            connection.close()

    def test_home_renders_environment_revision_and_release_marker(self):
        status, headers, body = self.request("/")
        self.assertEqual(status, 200)
        self.assertIn("text/html", headers["Content-Type"])
        html = body.decode()
        self.assertIn("Asteri Deployment Lab", html)
        self.assertIn("Release 1 —", html)
        self.assertIn("deployment baseline", html)
        self.assertIn("QA environment", html)
        self.assertIn(self.revision, html)
        self.assertNotIn("{{", html)

    def test_health_contains_only_public_release_metadata(self):
        status, headers, body = self.request("/health?ignored=secret")
        self.assertEqual(status, 200)
        self.assertEqual(headers["Content-Type"], "application/json; charset=utf-8")
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(json.loads(body), {
            "status": "ok", "app": "asteri-deployment-lab",
            "environment": "qa", "revision": self.revision,
        })
        self.assertNotIn(b"secret", body)

    def test_head_matches_get_headers_without_a_body(self):
        for path in ("/", "/health", "/styles.css", "/favicon.svg", "/missing"):
            with self.subTest(path=path):
                status, headers, body = self.request(path)
                head_status, head_headers, head_body = self.request(path, "HEAD")
                self.assertEqual(head_status, status)
                self.assertEqual(head_body, b"")
                self.assertEqual(int(head_headers["Content-Length"]), len(body))
                for name in ("Content-Type", "Cache-Control", *SECURITY_HEADERS):
                    self.assertEqual(head_headers[name], headers[name])

    def test_security_headers_apply_to_success_errors_and_assets(self):
        for path in ("/", "/health", "/styles.css", "/favicon.svg", "/missing"):
            with self.subTest(path=path):
                _, headers, _ = self.request(path)
                for name, value in SECURITY_HEADERS.items():
                    self.assertEqual(headers[name], value)
                self.assertEqual(headers["Server"], "AsteriLab")
                self.assertEqual(headers["Connection"], "close")

    def test_source_hidden_files_traversal_and_directories_are_not_public(self):
        for path in (
            "/.env", "/.git/config", "/app/main.py", "/tests/test_server.py",
            "/Dockerfile", "/site/", "/app/", "/deploy/", "/../app/main.py",
            "/%2e%2e/app/main.py", "/%2eenv", "/styles.css/../../app/main.py",
            "/%252e%252e/app/main.py", "/styles.css%00", "/%ff",
        ):
            with self.subTest(path=path):
                status, _, body = self.request(path)
                self.assertEqual(status, 404)
                self.assertEqual(body, b"Not found.\n")

    def test_methods_that_could_change_state_are_rejected(self):
        for method in ("POST", "PUT", "PATCH", "DELETE", "OPTIONS", "TRACE", "CONNECT"):
            with self.subTest(method=method):
                status, headers, body = self.request("/", method, "private-input")
                self.assertEqual(status, 405)
                self.assertEqual(headers["Allow"], "GET, HEAD")
                self.assertEqual(body, b"Method not allowed.\n")
                self.assertNotIn(b"private-input", body)

    def test_unknown_path_does_not_reflect_user_input(self):
        status, _, body = self.request("/private-token?token=private-token")
        self.assertEqual(status, 404)
        self.assertNotIn(b"private-token", body)


class SettingsTests(unittest.TestCase):
    def test_defaults_and_secrets_are_not_part_of_settings(self):
        settings = Settings.from_environment({"SECRET_KEY": "never-public"})
        self.assertEqual(settings, Settings("qa", "local", 8080))
        self.assertNotIn("never-public", repr(settings))

    def test_production_metadata_and_port(self):
        self.assertEqual(
            Settings.from_environment({"APP_ENV": "production", "RELEASE_COMMIT": "b" * 40, "PORT": "9090"}),
            Settings("production", "b" * 40, 9090),
        )

    def test_invalid_configuration_fails_without_reflecting_the_value(self):
        for key, value in (("APP_ENV", "secret-value"), ("RELEASE_COMMIT", "secret-value"), ("PORT", "secret-value"), ("PORT", "0"), ("PORT", "65536")):
            with self.subTest(key=key, value=value):
                with self.assertRaises(ValueError) as caught:
                    Settings.from_environment({key: value})
                self.assertNotIn("secret-value", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
