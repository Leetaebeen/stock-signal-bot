from pathlib import Path
import re


ROOT = Path.cwd()
EXCLUDED_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "data",
    "logs",
}
EXCLUDED_FILES = {".env"}
TEXT_SUFFIXES = {
    ".py",
    ".md",
    ".txt",
    ".toml",
    ".yaml",
    ".yml",
    ".json",
    ".ps1",
    ".example",
    "",
}
PATTERNS = {
    "telegram_bot_token_like": re.compile(r"\b\d{8,12}:[A-Za-z0-9_-]{25,}\b"),
    "google_api_key_like": re.compile(r"\bAIza[0-9A-Za-z_-]{20,}\b"),
    "bearer_token_literal": re.compile(r"\bBearer\s+[A-Za-z0-9._-]{20,}\b"),
    "secret_assignment": re.compile(
        r"(?i)\b(api[_-]?key|secret|token|appsecret|appkey)\b\s*[:=]\s*['\"][^'\"]{12,}['\"]"
    ),
}
ALLOWLIST_PATTERNS = (
    "sample-access-token",
    "fresh-token",
    "old-token",
    "your_app_key",
    "your_app_secret",
    "your-email@example.com",
    "AI_API_KEY=",
    "KIS_APP_SECRET=",
    "TELEGRAM_BOT_TOKEN=",
)


def main() -> None:
    findings = []
    for path in _iter_text_files(ROOT):
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        for line_no, line in enumerate(lines, start=1):
            if _is_allowlisted(line):
                continue
            for name, pattern in PATTERNS.items():
                if pattern.search(line):
                    findings.append((path.relative_to(ROOT), line_no, name))

    if not findings:
        print("security_check=ok")
        print("No hardcoded secret-like values found in tracked source candidates.")
        return

    print("security_check=findings")
    for path, line_no, name in findings:
        print(f"- {path}:{line_no} pattern={name}")
    raise SystemExit(1)


def _iter_text_files(root: Path):
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in EXCLUDED_DIRS for part in path.relative_to(root).parts):
            continue
        if path.name in EXCLUDED_FILES:
            continue
        if path.suffix not in TEXT_SUFFIXES and path.name != ".gitignore":
            continue
        yield path


def _is_allowlisted(line: str) -> bool:
    return any(item in line for item in ALLOWLIST_PATTERNS)


if __name__ == "__main__":
    main()
