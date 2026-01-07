import argparse
import datetime as dt
import os
import re
import sqlite3
import sys
from decimal import Decimal
from urllib.request import Request, urlopen

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data", "fiis.db")


def ensure_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS fiis (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL UNIQUE,
                qty REAL NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS dividends (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fii_id INTEGER NOT NULL,
                as_of_month TEXT NOT NULL,
                amount_per_share REAL NOT NULL,
                qty REAL NOT NULL,
                total REAL NOT NULL,
                fetched_at TEXT NOT NULL,
                source_url TEXT NOT NULL,
                UNIQUE (fii_id, as_of_month),
                FOREIGN KEY (fii_id) REFERENCES fiis (id) ON DELETE CASCADE
            )
            """
        )


def parse_brl_number(value_text: str) -> Decimal:
    cleaned = re.sub(r"[^0-9,\.]", "", value_text)
    if "." in cleaned and "," not in cleaned:
        if re.match(r"^\d{1,3}(\.\d{3})+$", cleaned):
            cleaned = cleaned.replace(".", "")
    if cleaned.count(",") == 1 and cleaned.count(".") >= 1:
        cleaned = cleaned.replace(".", "")
    if "," in cleaned:
        cleaned = cleaned.replace(",", ".")
    return Decimal(cleaned)


def build_last_yield_pattern() -> re.Pattern:
    label_plain = "Ultimo Rendimento"
    label_accent = "U" + chr(250) + "ltimo Rendimento"
    label_plain_alt = "Ultimo Dividendo"
    label_accent_alt = "U" + chr(250) + "ltimo Dividendo"
    label = (
        f"(?:{re.escape(label_plain)}|{re.escape(label_accent)}|"
        f"{re.escape(label_plain_alt)}|{re.escape(label_accent_alt)})"
    )

    pattern = (
        r'<div class="indicators__box">\s*'
        r'<p>\s*' + label + r'\s*</p>\s*'
        r'<p>.*?<b>\s*([^<]+)\s*</b>'
    )
    return re.compile(pattern, re.IGNORECASE | re.DOTALL)


def fetch_last_yield(ticker: str) -> Decimal:
    url = f"https://www.fundsexplorer.com.br/funds/{ticker.lower()}"
    headers = {"User-Agent": "Mozilla/5.0"}
    req = Request(url, headers=headers)
    with urlopen(req, timeout=20) as resp:
        html = resp.read().decode("utf-8", errors="ignore")

    def try_parse_amount(text: str):
        try:
            return parse_brl_number(text)
        except Exception:
            return None

    amount = None
    pattern = build_last_yield_pattern()
    match = pattern.search(html)
    if match:
        amount = try_parse_amount(match.group(1))

    if amount is None:
        alt_pattern = re.compile(
            r'<li[^>]*data-row="ultimoRendimento"[^>]*>\s*R\$\s*([^<]+)\s*</li>',
            re.IGNORECASE | re.DOTALL,
        )
        match = alt_pattern.search(html)
        if match:
            amount = try_parse_amount(match.group(1))

    if amount is None:
        data_layer_pattern = re.compile(
            r'"(?:lastdividend|ur_valor|pr_valor|avgdividend)"\s*:\s*([0-9]+(?:[\.,][0-9]+)?)',
            re.IGNORECASE,
        )
        match = data_layer_pattern.search(html)
        if match:
            amount = try_parse_amount(match.group(1))
            if amount is not None and amount > Decimal("10"):
                amount = None

    if amount is None:
        raise RuntimeError(f"Nao achei Ultimo Rendimento para {ticker}")

    return amount


def add_fii(ticker: str, qty: float):
    ensure_db()
    now = dt.datetime.utcnow().isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO fiis (ticker, qty, created_at) VALUES (?, ?, ?)",
            (ticker.upper(), qty, now),
        )


def parse_bulk_lines(lines):
    items = []
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        lower = line.lower()
        if ("fundo" in lower or "fii" in lower) and "quantidade" in lower:
            continue
        parts = re.split(r"\s+", line)
        if len(parts) < 2:
            continue
        ticker = parts[0].strip()
        qty = float(parse_brl_number(parts[1]))
        items.append((ticker, qty))
    return items


def import_fiis(path: str):
    ensure_db()
    if path == "-":
        lines = sys.stdin.read().splitlines()
    else:
        with open(path, "r", encoding="utf-8") as handle:
            lines = handle.read().splitlines()

    items = parse_bulk_lines(lines)
    if not items:
        print("Nenhum registro encontrado.")
        return

    now = dt.datetime.utcnow().isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        for ticker, qty in items:
            conn.execute(
                "INSERT OR REPLACE INTO fiis (ticker, qty, created_at) VALUES (?, ?, ?)",
                (ticker.upper(), qty, now),
            )

    print(f"Importados {len(items)} FIIs.")


def list_fiis():
    ensure_db()
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute("SELECT ticker, qty FROM fiis ORDER BY ticker").fetchall()
    if not rows:
        print("Sem FIIs cadastrados.")
        return
    for ticker, qty in rows:
        print(f"{ticker} {qty}")


def fetch_all():
    ensure_db()
    today = dt.date.today()
    as_of_month = today.strftime("%Y-%m")
    fetched_at = dt.datetime.utcnow().isoformat()

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        fiis = conn.execute("SELECT id, ticker, qty FROM fiis ORDER BY ticker").fetchall()
        if not fiis:
            print("Sem FIIs cadastrados.")
            return

        for fii_id, ticker, qty in fiis:
            try:
                amount = fetch_last_yield(ticker)
            except Exception as exc:
                print(f"{ticker}: erro ao buscar ({exc})")
                continue

            total = amount * Decimal(str(qty))
            url = f"https://www.fundsexplorer.com.br/funds/{ticker.lower()}"

            conn.execute(
                """
                INSERT INTO dividends (
                    fii_id, as_of_month, amount_per_share, qty, total, fetched_at, source_url
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(fii_id, as_of_month) DO UPDATE SET
                    amount_per_share=excluded.amount_per_share,
                    qty=excluded.qty,
                    total=excluded.total,
                    fetched_at=excluded.fetched_at,
                    source_url=excluded.source_url
                """,
                (fii_id, as_of_month, float(amount), float(qty), float(total), fetched_at, url),
            )

            print(f"{ticker}: R$ {amount} por cota (total ~ R$ {total})")


def build_parser():
    parser = argparse.ArgumentParser(
        description="Cadastra FIIs e coleta Ultimo Rendimento do Funds Explorer"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_add = sub.add_parser("add", help="Adicionar FII e quantidade")
    p_add.add_argument("ticker")
    p_add.add_argument("qty", type=float)

    p_import = sub.add_parser("import", help="Importar FIIs de um arquivo ou stdin")
    p_import.add_argument("path", nargs="?", default="-")

    sub.add_parser("list", help="Listar FIIs cadastrados")
    sub.add_parser("fetch", help="Buscar ultimo rendimento e salvar no SQLite")

    return parser


def main(argv):
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "add":
        add_fii(args.ticker, args.qty)
    elif args.command == "import":
        import_fiis(args.path)
    elif args.command == "list":
        list_fiis()
    elif args.command == "fetch":
        fetch_all()


if __name__ == "__main__":
    main(sys.argv[1:])
