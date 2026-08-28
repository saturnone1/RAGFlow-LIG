from __future__ import annotations

import os
import unittest
from unittest.mock import MagicMock, patch

from lig_runtime import container_entrypoint


class ContainerEntrypointTests(unittest.TestCase):
    def setUp(self) -> None:
        container_entrypoint.STOP.clear()
        with container_entrypoint.CHILDREN_LOCK:
            container_entrypoint.CHILDREN.clear()

    def tearDown(self) -> None:
        container_entrypoint.STOP.clear()
        with container_entrypoint.CHILDREN_LOCK:
            container_entrypoint.CHILDREN.clear()

    @patch("lig_runtime.container_entrypoint.importlib.util.find_spec", return_value=None)
    def test_docling_fails_fast_without_runtime_download(self, _find_spec: MagicMock) -> None:
        with patch.dict(os.environ, {"USE_DOCLING": "true"}, clear=False):
            with self.assertRaisesRegex(RuntimeError, "preinstalled"):
                container_entrypoint.ensure_docling()

    @patch("lig_runtime.container_entrypoint.subprocess.Popen")
    def test_spawn_registers_and_unregister_removes_child(self, popen: MagicMock) -> None:
        process = popen.return_value
        self.assertIs(container_entrypoint.spawn(["example"]), process)
        with container_entrypoint.CHILDREN_LOCK:
            self.assertEqual(container_entrypoint.CHILDREN, [process])
        container_entrypoint.unregister(process)
        with container_entrypoint.CHILDREN_LOCK:
            self.assertEqual(container_entrypoint.CHILDREN, [])

    def test_stop_children_terminates_only_running_processes(self) -> None:
        running = MagicMock()
        running.poll.return_value = None
        exited = MagicMock()
        exited.poll.return_value = 1
        with container_entrypoint.CHILDREN_LOCK:
            container_entrypoint.CHILDREN.extend([running, exited])

        container_entrypoint.stop_children()

        running.terminate.assert_called_once_with()
        exited.terminate.assert_not_called()
        self.assertTrue(container_entrypoint.STOP.is_set())

    @patch("lig_runtime.container_entrypoint.spawn")
    @patch("lig_runtime.container_entrypoint.STOP")
    def test_fast_failures_use_exponential_restart_backoff(self, stop: MagicMock, spawn: MagicMock) -> None:
        process = MagicMock()
        process.poll.return_value = 1
        spawn.return_value = process
        stop.is_set.return_value = False
        stop.wait.side_effect = [False, True]

        container_entrypoint.restart_forever(["example"])

        self.assertEqual(spawn.call_count, 2)
        self.assertEqual([call.args[0] for call in stop.wait.call_args_list], [1.0, 2.0])

    @patch("lig_runtime.container_entrypoint.spawn")
    @patch("lig_runtime.container_entrypoint.STOP")
    def test_process_creation_failures_do_not_kill_supervisor(self, stop: MagicMock, spawn: MagicMock) -> None:
        process = MagicMock()
        process.poll.return_value = 1
        spawn.side_effect = [OSError("temporarily unavailable"), process]
        stop.is_set.return_value = False
        stop.wait.side_effect = [False, True]

        with patch.object(container_entrypoint.sys, "stderr"):
            container_entrypoint.restart_forever(["example"])

        self.assertEqual(spawn.call_count, 2)
        self.assertEqual([call.args[0] for call in stop.wait.call_args_list], [1.0, 2.0])

    @patch("lig_runtime.container_entrypoint.spawn")
    @patch("lig_runtime.container_entrypoint.STOP")
    def test_shutdown_during_registration_terminates_child(self, stop: MagicMock, spawn: MagicMock) -> None:
        process = MagicMock()
        process.poll.return_value = None
        spawn.return_value = process
        stop.is_set.side_effect = [False, True, True]
        stop.wait.return_value = True

        container_entrypoint.restart_forever(["example"])

        process.terminate.assert_called_once_with()

    @patch("lig_runtime.container_entrypoint.ensure_docling")
    @patch("lig_runtime.container_entrypoint.configure_nginx")
    @patch("lig_runtime.container_entrypoint.initialize_database")
    @patch("lig_runtime.container_entrypoint.render_configuration")
    @patch("lig_runtime.container_entrypoint.subprocess.run")
    @patch("lig_runtime.container_entrypoint.signal.signal")
    def test_migrate_only_exits_before_runtime_services(
        self,
        _signal: MagicMock,
        run: MagicMock,
        render: MagicMock,
        initialize: MagicMock,
        configure_nginx: MagicMock,
        ensure_docling: MagicMock,
    ) -> None:
        with patch.object(
            container_entrypoint.sys,
            "argv",
            ["container_entrypoint", "--migrate-only", "--init-model-provider-tables"],
        ):
            self.assertEqual(container_entrypoint.main(), 0)

        render.assert_called_once_with()
        initialize.assert_called_once_with()
        run.assert_called_once()
        configure_nginx.assert_not_called()
        ensure_docling.assert_not_called()


if __name__ == "__main__":
    unittest.main()
