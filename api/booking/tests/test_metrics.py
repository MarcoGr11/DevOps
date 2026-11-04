import json
import logging
import os
from unittest import mock

from prometheus_client import REGISTRY
from rest_framework.test import APITestCase

from booking.metrics_middleware import JsonFormatter

RESOURCES_ROUTE = "api/resources/$"


def request_count(status, route=RESOURCES_ROUTE):
    labels = {"method": "GET", "route": route, "status": status}
    return REGISTRY.get_sample_value("http_requests_total", labels) or 0


class MetricsTests(APITestCase):
    def test_metrics_endpoint_is_served(self):
        response = self.client.get("/metrics")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"http_requests_total", response.content)

    def test_counter_grows_with_route_template_label(self):
        before = request_count("200")
        self.client.get("/api/resources/")
        self.assertEqual(request_count("200"), before + 1)

    def test_detail_route_uses_template_not_raw_id(self):
        self.client.get("/api/resources/123456/")
        self.assertNotIn(b"123456", self.client.get("/metrics").content)

    def test_unknown_path_has_unknown_route(self):
        before = request_count("404", route="unknown")
        self.client.get("/no/such/path/")
        self.assertEqual(request_count("404", route="unknown"), before + 1)

    def test_health_and_metrics_are_not_counted(self):
        before = request_count("200", route="api/health/")
        self.client.get("/api/health/")
        self.assertEqual(request_count("200", route="api/health/"), before)


class FailRateTests(APITestCase):
    @mock.patch.dict(os.environ, {"FAIL_RATE": "1"})
    def test_fail_rate_one_returns_500_and_is_counted(self):
        before = request_count("500")
        response = self.client.get("/api/resources/")
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json(), {"error": "injected failure"})
        self.assertEqual(request_count("500"), before + 1)

    @mock.patch.dict(os.environ, {"FAIL_RATE": "1"})
    def test_fail_rate_does_not_touch_health_or_metrics(self):
        self.assertEqual(self.client.get("/api/health/").status_code, 200)
        self.assertEqual(self.client.get("/metrics").status_code, 200)

    @mock.patch.dict(os.environ, {"FAIL_RATE": "0"})
    def test_fail_rate_zero_passes_through(self):
        self.assertEqual(self.client.get("/api/resources/").status_code, 200)


class JsonLogTests(APITestCase):
    @mock.patch.dict(os.environ, {"FAIL_RATE": "1", "APP_VERSION": "9.9.9"})
    def test_failed_request_logs_one_json_error_line(self):
        with self.assertLogs("booking.requests", level="INFO") as logs:
            self.client.get("/api/resources/")
        entry = json.loads(JsonFormatter().format(logs.records[0]))
        self.assertEqual(entry["level"], "error")
        self.assertEqual(entry["msg"], "request")
        self.assertEqual(entry["method"], "GET")
        self.assertEqual(entry["route"], RESOURCES_ROUTE)
        self.assertEqual(entry["status"], 500)
        self.assertEqual(entry["version"], "9.9.9")
        self.assertIn("duration_ms", entry)
        self.assertIn("time", entry)

    def test_ok_request_logs_info_level(self):
        with self.assertLogs("booking.requests", level="INFO") as logs:
            self.client.get("/api/resources/")
        self.assertEqual(logs.records[0].levelno, logging.INFO)
