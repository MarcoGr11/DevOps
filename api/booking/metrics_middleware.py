"""HTTP metrics, JSON request logs and FAIL_RATE failure injection (lab 7)."""
import json
import logging
import os
import random
import time

from django.http import HttpResponse, JsonResponse
from django.urls import Resolver404, resolve
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

# Probes and scrapes: not user traffic, never counted and never failed on purpose.
SKIP_PATHS = {"/metrics", "/api/health/", "/health"}

REQUESTS = Counter("http_requests_total", "HTTP requests", ["method", "route", "status"])
DURATION = Histogram("http_request_duration_seconds", "HTTP request duration", ["route"])

logger = logging.getLogger("booking.requests")


class JsonFormatter(logging.Formatter):
    """One JSON object per line, so Loki can parse every record with `| json`."""

    def format(self, record):
        entry = {
            "time": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname.lower(),
            "msg": record.getMessage(),
            **getattr(record, "fields", {}),
        }
        if record.exc_info:
            entry["exc"] = self.formatException(record.exc_info)
        return json.dumps(entry)


def route_of(path):
    """URL template, not the raw path: pk values in labels would explode cardinality."""
    try:
        return resolve(path).route or "unknown"
    except Resolver404:
        return "unknown"


class MetricsMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path in SKIP_PATHS:
            return self.get_response(request)

        # resolver_match is set only after the middleware chain, too late for injected failures
        route = route_of(request.path_info)
        started = time.perf_counter()
        if random.random() < float(os.environ.get("FAIL_RATE", "0")):
            response = JsonResponse({"error": "injected failure"}, status=500)
        else:
            response = self.get_response(request)
        duration = time.perf_counter() - started

        REQUESTS.labels(request.method, route, str(response.status_code)).inc()
        DURATION.labels(route).observe(duration)
        logger.log(
            logging.ERROR if response.status_code >= 500 else logging.INFO,
            "request",
            extra={
                "fields": {
                    "method": request.method,
                    "route": route,
                    "status": response.status_code,
                    "duration_ms": round(duration * 1000, 2),
                    "version": os.environ.get("APP_VERSION", "dev"),
                }
            },
        )
        return response


def metrics_view(_request):
    return HttpResponse(generate_latest(), content_type=CONTENT_TYPE_LATEST)
