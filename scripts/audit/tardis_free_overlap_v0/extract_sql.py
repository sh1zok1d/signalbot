"""Split the packaged SELECT script. Reject anything that is not a single SELECT."""
from __future__ import annotations

import re

_FORBIDDEN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE|GRANT|REVOKE|COPY)\b",
    re.IGNORECASE,
)


def split_selects(text: str) -> list[str]:
    if _FORBIDDEN.search(text):
        raise ValueError("SQL contains a statement this extractor must not run")
    statements = []
    for chunk in text.split(";"):
        lines = []
        for line in chunk.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("--"):
                continue
            lines.append(line)
        statement = "\n".join(lines).strip()
        if not statement:
            continue
        if not statement.upper().lstrip().startswith("SELECT"):
            raise ValueError(f"refusing non-SELECT statement: {statement[:80]!r}")
        statements.append(statement)
    if len(statements) != 6:
        raise ValueError(f"expected 6 SELECT statements, found {len(statements)}")
    return statements


def assert_sql_is_read_only(text: str) -> list[str]:
    return split_selects(text)


# Imported by the extractor after the file is read, so a hand edit of the SQL
# still has to parse as the same six statements. The tuple is filled at import
# from the sibling file to keep one source of truth.
def _load() -> tuple[str, ...]:
    from pathlib import Path
    text = Path(__file__).with_name("extract_signalbot_readonly.sql").read_text()
    return tuple(split_selects(text))


STATEMENTS = _load()
