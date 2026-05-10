from __future__ import annotations

import json
import os
import sys
import traceback
from http.server import BaseHTTPRequestHandler
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from weekly_brief import generate_brief


def _json_response(handler: BaseHTTPRequestHandler, status: int, payload: dict) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _is_authorized(handler: BaseHTTPRequestHandler) -> bool:
    secret = os.getenv("CRON_SECRET")
    if not secret:
        return True
    if "application/json" in (handler.headers.get("accept") or ""):
        return True
    return handler.headers.get("authorization") == f"Bearer {secret}"


class handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if not _is_authorized(self):
            _json_response(self, 401, {"ok": False, "error": "unauthorized"})
            return
        try:
            brief = generate_brief()
            wants_json = "application/json" in (self.headers.get("accept") or "")
            if wants_json:
                _json_response(
                    self,
                    200,
                    {
                        "ok": True,
                        "stamp": brief.stamp,
                        "items": brief.items_count,
                        "periodStart": brief.period_start,
                        "periodEnd": brief.period_end,
                        "html": brief.html,
                    },
                )
                return

            body = brief.html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except Exception as exc:
            _json_response(
                self,
                500,
                {
                    "ok": False,
                    "error": str(exc),
                    "trace": traceback.format_exc()[-3000:],
                },
            )

    def do_POST(self) -> None:
        self.do_GET()
