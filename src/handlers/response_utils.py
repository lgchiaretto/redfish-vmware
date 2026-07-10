#!/usr/bin/env python3
"""
Shared Redfish HTTP response helpers for resource handlers.
"""

import json
import logging
from typing import Dict

logger = logging.getLogger(__name__)


def send_json_response(request_handler, status_code: int, data: Dict) -> None:
    """Send a JSON HTTP response."""
    json_data = json.dumps(data, indent=2)
    request_handler.send_response(status_code)
    request_handler.send_header('Content-Type', 'application/json')
    request_handler.send_header('Content-Length', str(len(json_data)))
    request_handler.end_headers()
    request_handler.wfile.write(json_data.encode('utf-8'))


def send_error_response(request_handler, status_code: int, message: str) -> None:
    """Send a Redfish error response."""
    error_data = {
        "error": {
            "code": f"Base.1.0.{status_code}",
            "message": message,
        }
    }
    send_json_response(request_handler, status_code, error_data)


class RedfishResponseMixin:
    """Mixin providing standard Redfish JSON response helpers."""

    def _send_json_response(self, request_handler, status_code: int, data: Dict) -> None:
        send_json_response(request_handler, status_code, data)

    def _send_error_response(self, request_handler, status_code: int, message: str) -> None:
        error_data = {
            "error": {
                "code": f"Base.1.0.{status_code}",
                "message": message,
            }
        }
        self._send_json_response(request_handler, status_code, error_data)
