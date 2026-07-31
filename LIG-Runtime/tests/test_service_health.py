from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from lig_runtime import service_health


class ServiceHealthTests(unittest.TestCase):
    @patch("lig_runtime.service_health.urlopen")
    def test_api_ready_requires_pong(self, urlopen: MagicMock) -> None:
        response = urlopen.return_value.__enter__.return_value
        response.status = 200
        response.read.return_value = b"pong"
        self.assertTrue(service_health.api_ready("http://127.0.0.1:9380"))

        response.read.return_value = b"not-pong"
        self.assertFalse(service_health.api_ready("http://127.0.0.1:9380"))

    @patch("lig_runtime.service_health.socket.create_connection")
    def test_tcp_ready_checks_embedded_mcp_listener(self, create_connection: MagicMock) -> None:
        create_connection.return_value.__enter__.return_value = object()
        self.assertTrue(service_health.tcp_ready("127.0.0.1", 9382))
        create_connection.assert_called_once_with(("127.0.0.1", 9382), timeout=5)


if __name__ == "__main__":
    unittest.main()
