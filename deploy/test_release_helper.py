"""Local safety checks; never contact Docker or a server."""
import importlib.util
import io
import json
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

SPEC = importlib.util.spec_from_file_location("release_helper", Path(__file__).with_name("release-helper.py"))
helper = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(helper)
SHA = "a" * 40
OLD_SHA = "b" * 40
DIGEST = "sha256:" + "c" * 64
OLD_DIGEST = "sha256:" + "d" * 64


class RequestTests(unittest.TestCase):
    def test_valid_commands(self):
        for env in ("qa", "production"):
            self.assertEqual(helper.parse_request(f"deploy {env} {DIGEST} {SHA}"), (env, DIGEST, SHA))

    def test_injections_and_arbitrary_inputs_are_denied(self):
        good = f"deploy qa {DIGEST} {SHA}"
        invalid = [good + ";id", good + "\nid", good + " ", good + " --privileged",
                   good.replace("qa", "main"), good.replace("deploy", "sh"),
                   good.replace(DIGEST, "ghcr.io/other/image:latest"),
                   good.replace(SHA, "../root"), good.replace("sha256:", "sha512:"),
                   "$(id)", "", good.replace("c" * 64, "C" * 64)]
        for command in invalid:
            with self.subTest(command=command), self.assertRaises(ValueError):
                helper.parse_request(command)

    def test_framing_and_extra_arguments_are_denied(self):
        bad = [f"deploy qa {DIGEST} {SHA}", f"deploy qa {DIGEST} {SHA}\nextra\n", "x" * 300 + "\n"]
        for command in bad:
            with self.subTest(command=command), mock.patch.object(helper.os, "geteuid", return_value=0), mock.patch.object(helper.sys, "argv", ["helper"]), mock.patch.object(helper.sys, "stdin", mock.Mock(buffer=io.BytesIO(command.encode()))), self.assertRaises(ValueError):
                helper.main()
        with mock.patch.object(helper.os, "geteuid", return_value=0), mock.patch.object(helper.sys, "argv", ["helper", "extra"]), self.assertRaises(ValueError):
            helper.main()

    def test_saved_state_cannot_select_another_registry(self):
        with self.assertRaises(ValueError):
            helper.validate_state({"qa": {"image": "ghcr.io/other/image@" + DIGEST, "commit": SHA}})

    def test_untrusted_files_denied(self):
        for uid, mode in [(1000, stat.S_IFREG | 0o644), (0, stat.S_IFREG | 0o666), (0, stat.S_IFLNK | 0o777)]:
            path = mock.Mock()
            path.lstat.return_value = mock.Mock(st_uid=uid, st_mode=mode)
            with self.assertRaises(ValueError):
                helper.trusted(path)


class RollbackTests(unittest.TestCase):
    def test_failed_qa_restores_qa_and_preserves_production(self):
        old = {"qa": {"image": helper.IMAGE_PREFIX + OLD_DIGEST, "commit": OLD_SHA},
               "production": {"image": helper.IMAGE_PREFIX + OLD_DIGEST, "commit": OLD_SHA}}
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            (base / "state.json").write_text(json.dumps(old))
            helper_base = mock.patch.object(helper, "BASE", base)
            with helper_base, mock.patch.object(helper, "trusted"), mock.patch.object(helper, "run", return_value=SHA), mock.patch.object(helper, "compose") as compose, mock.patch.object(helper, "health", side_effect=[RuntimeError("bad new release"), None]), mock.patch.object(helper, "external_health"):
                with self.assertRaisesRegex(RuntimeError, "bad new release"):
                    helper.deploy("qa", DIGEST, SHA)
            self.assertEqual(json.loads((base / "state.json").read_text()), old)
            self.assertIn("QA_COMMIT=" + OLD_SHA, (base / "images.env").read_text())
            self.assertIn("PRODUCTION_COMMIT=" + OLD_SHA, (base / "images.env").read_text())
            self.assertTrue(all(call.args[-1] == "app-qa" for call in compose.call_args_list))

    def test_first_failed_release_is_removed(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            (base / "state.json").write_text("{}")
            with mock.patch.object(helper, "BASE", base), mock.patch.object(helper, "trusted"), mock.patch.object(helper, "run", return_value=SHA), mock.patch.object(helper, "compose") as compose, mock.patch.object(helper, "health", side_effect=RuntimeError("bad release")):
                with self.assertRaises(RuntimeError):
                    helper.deploy("qa", DIGEST, SHA)
            self.assertIn(mock.call("--profile", "qa", "stop", "app-qa"), compose.call_args_list)
            self.assertIn(mock.call("--profile", "qa", "rm", "--force", "app-qa"), compose.call_args_list)
            self.assertEqual((base / "images.env").read_text(), "\n")

    def test_image_label_mismatch_does_not_change_state(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            (base / "state.json").write_text("{}")
            with mock.patch.object(helper, "BASE", base), mock.patch.object(helper, "trusted"), mock.patch.object(helper, "run", return_value=OLD_SHA), mock.patch.object(helper, "compose") as compose:
                with self.assertRaisesRegex(ValueError, "revision label"):
                    helper.deploy("qa", DIGEST, SHA)
            compose.assert_not_called()
            self.assertFalse((base / "images.env").exists())


class AppContractTests(unittest.TestCase):
    """Exercise actual app response data against both helper health paths."""
    @staticmethod
    def response(environment):
        project = str(Path(__file__).resolve().parent.parent)
        if project not in sys.path:
            sys.path.insert(0, project)
        from app.main import Settings, make_handler
        handler_class = make_handler(Settings(environment, SHA))
        handler = object.__new__(handler_class)
        handler._route = lambda: "/health"
        bodies = []
        handler._send = lambda status, body, *args, **kwargs: bodies.append(body)
        handler.do_GET()
        return bodies[0]

    def test_container_check_accepts_actual_app_contract(self):
        import urllib.request
        for environment in ("qa", "production"):
            body = self.response(environment)
            def execute_compose_code(*args):
                with mock.patch.object(urllib.request, "urlopen", return_value=io.BytesIO(body)):
                    exec(args[-1], {})
            with self.subTest(environment=environment), mock.patch.object(helper, "compose", side_effect=execute_compose_code):
                helper.health(environment, SHA)

    def test_https_check_accepts_actual_contract_and_correct_host(self):
        for environment, host in (("qa", "dev.lwdgyasteri.com"), ("production", "lwdgyasteri.com")):
            with self.subTest(environment=environment), mock.patch.object(helper, "run", return_value=self.response(environment).decode()) as run:
                helper.external_health(environment, SHA)
            request = run.call_args.args[0]
            self.assertIn(f"https://{host}/health", request)
            self.assertIn(f"{host}:443:127.0.0.1", request)
            self.assertNotIn("--insecure", request)

    def test_https_check_rejects_wrong_environment_or_revision(self):
        for change in ({"environment": "production"}, {"revision": OLD_SHA}):
            body = json.loads(self.response("qa"))
            body.update(change)
            with self.subTest(change=change), mock.patch.object(helper, "run", return_value=json.dumps(body)), mock.patch.object(helper.time, "sleep"), self.assertRaises(RuntimeError):
                helper.external_health("qa", SHA)

    def test_router_domains_match_health_checks(self):
        routes = Path(__file__).with_name("routes.yaml").read_text()
        self.assertIn("Host(`dev.lwdgyasteri.com`)", routes)
        self.assertIn("Host(`lwdgyasteri.com`)", routes)
        self.assertEqual(routes.count("Host(`"), 2)


if __name__ == "__main__":
    unittest.main()
