"""One-off helper: print store id -> LEASE|OWN from Agency 2025 sheet (run manually)."""
import json
import re
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "db" / "static_locations.py"
XLSX = Path(
    r"c:\Users\spradhan\OneDrive - Goodwill Industries of San Antonio\Desktop\My projects - Save HERE!!!\Copy of SF spreadsheet 2026.xlsx"
)


def norm(s: str) -> str:
    s = s.lower()
    for w in (
        " retail store",
        " donation station",
        " outlet retail store",
        " retail",
        " store",
        " outlet",
        " accents",
        " landing",
        " bend ",
    ):
        s = s.replace(w, "")
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def main():
    wb = openpyxl.load_workbook(XLSX, read_only=True, data_only=True)
    ws = wb["Agency 2025"]
    lease = {}
    for row in ws.iter_rows(min_row=6, values_only=True):
        name, status = row[0], row[2] if len(row) > 2 else None
        if name and status in ("LEASE", "OWN"):
            lease[norm(str(name))] = status

    text = STATIC.read_text(encoding="utf-8")
    pairs = re.findall(r'\{"id": "(\d+)", "name": "([^"]+)"', text)
    out = {}
    for sid, name in pairs:
        if sid == "CONSOLIDATED":
            continue
        n = norm(name)
        hit = lease.get(n)
        if not hit:
            for k, v in lease.items():
                if k == n or k in n or n in k:
                    hit = v
                    break
        out[sid] = hit

    print(json.dumps(out, indent=2))
    missing = [k for k, v in out.items() if not v]
    if missing:
        print("missing:", missing, file=__import__("sys").stderr)


if __name__ == "__main__":
    main()
