import json
import os
import sqlite3
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

import app

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UI_DIR = os.path.join(BASE_DIR, "ui")
DB_PATH = app.DB_PATH


def latest_month(conn):
    row = conn.execute("SELECT MAX(as_of_month) FROM dividends").fetchone()
    return row[0]


def latest_update(conn):
    row = conn.execute("SELECT MAX(fetched_at) FROM dividends").fetchone()
    return row[0]


def get_fiis(conn, month):
    rows = conn.execute(
        """
        SELECT f.ticker, f.qty, d.amount_per_share, d.total
        FROM fiis f
        LEFT JOIN dividends d
            ON d.fii_id = f.id AND d.as_of_month = ?
        ORDER BY f.ticker
        """,
        (month,),
    ).fetchall()

    result = []
    for ticker, qty, amount, total in rows:
        result.append(
            {
                "ticker": ticker,
                "qty": qty,
                "amount_per_share": amount or 0.0,
                "total": total or 0.0,
                "has_dividend": amount is not None,
            }
        )
    return result


def get_summary(conn, month):
    fiis_count = conn.execute("SELECT COUNT(*) FROM fiis").fetchone()[0]
    last = latest_update(conn)
    top_position = conn.execute(
        "SELECT ticker, qty FROM fiis ORDER BY qty DESC LIMIT 1"
    ).fetchone()

    total_estimated = 0.0
    avg_yield = 0.0
    top_yield = None

    if month:
        rows = conn.execute(
            """
            SELECT f.ticker, d.amount_per_share, d.total
            FROM fiis f
            JOIN dividends d ON d.fii_id = f.id
            WHERE d.as_of_month = ?
            ORDER BY d.amount_per_share DESC
            """,
            (month,),
        ).fetchall()
        if rows:
            amounts = [r[1] for r in rows if r[1] is not None]
            totals = [r[2] for r in rows if r[2] is not None]
            if amounts:
                avg_yield = sum(amounts) / len(amounts)
            if totals:
                total_estimated = sum(totals)
            top_yield = {"ticker": rows[0][0], "amount_per_share": rows[0][1]}

    return {
        "fiis_count": fiis_count,
        "month": month,
        "last_update": last,
        "total_estimated": total_estimated,
        "avg_yield": avg_yield,
        "top_yield": top_yield,
        "top_position": {
            "ticker": top_position[0],
            "qty": top_position[1],
        }
        if top_position
        else None,
    }


def get_timeline(conn, limit):
    rows = conn.execute(
        """
        SELECT as_of_month, SUM(total)
        FROM dividends
        GROUP BY as_of_month
        ORDER BY as_of_month DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [{"month": r[0], "total": r[1]} for r in rows]


class Handler(BaseHTTPRequestHandler):
    def _send_json(self, data, status=200):
        payload = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _serve_file(self, path):
        if path in ("", "/"):
            path = "/index.html"
        safe_path = os.path.normpath(path).lstrip("/\\")
        full_path = os.path.abspath(os.path.join(UI_DIR, safe_path))
        if not full_path.startswith(os.path.abspath(UI_DIR)):
            self.send_error(403)
            return
        if not os.path.isfile(full_path):
            self.send_error(404)
            return
        mime = "text/plain"
        if full_path.endswith(".html"):
            mime = "text/html; charset=utf-8"
        elif full_path.endswith(".css"):
            mime = "text/css; charset=utf-8"
        elif full_path.endswith(".js"):
            mime = "application/javascript; charset=utf-8"
        else:
            mime = "application/octet-stream"

        with open(full_path, "rb") as handle:
            content = handle.read()
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/"):
            app.ensure_db()
            with sqlite3.connect(DB_PATH) as conn:
                if parsed.path == "/api/fiis":
                    query = parse_qs(parsed.query)
                    month = query.get("month", [None])[0]
                    if not month:
                        month = latest_month(conn)
                    rows = get_fiis(conn, month) if month else []
                    self._send_json({"month": month, "rows": rows})
                    return
                if parsed.path == "/api/summary":
                    month = latest_month(conn)
                    summary = get_summary(conn, month)
                    self._send_json(summary)
                    return
                if parsed.path == "/api/timeline":
                    query = parse_qs(parsed.query)
                    limit = int(query.get("limit", [3])[0])
                    self._send_json({"items": get_timeline(conn, limit)})
                    return
            self.send_error(404)
            return

        self._serve_file(parsed.path)

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/fetch":
            try:
                app.fetch_all()
            except Exception as exc:
                self._send_json({"status": "error", "message": str(exc)}, status=500)
                return
            self._send_json({"status": "ok"})
            return
        self.send_error(404)


def main():
    server = HTTPServer(("0.0.0.0", 8000), Handler)
    print("Servidor em http://localhost:8000")
    server.serve_forever()


if __name__ == "__main__":
    main()
