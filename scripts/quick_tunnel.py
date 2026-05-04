from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"
SITE_PATH = ROOT / "site.txt"
DEFAULT_URL = "http://127.0.0.1:8000"
TUNNEL_REGEX = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com", re.IGNORECASE)


def _find_cloudflared() -> str:
    env_path = os.getenv("CLOUDFLARED_PATH")
    if env_path and Path(env_path).exists():
        return env_path

    in_path = shutil.which("cloudflared")
    if in_path:
        return in_path

    candidates = [
        r"C:\Program Files (x86)\cloudflared\cloudflared.exe",
        r"C:\Program Files\cloudflared\cloudflared.exe",
    ]
    for item in candidates:
        if Path(item).exists():
            return item
    raise FileNotFoundError("cloudflared не найден. Укажи CLOUDFLARED_PATH или установи cloudflared.")


def _update_env(url: str) -> None:
    host = url.replace("https://", "").replace("http://", "").strip("/")
    redirect_uri = f"{url}/threads/oauth/callback/"

    updates = {
        "THREADS_REDIRECT_URI": redirect_uri,
        "DJANGO_ALLOWED_HOSTS": f"127.0.0.1,localhost,{host}",
        "DJANGO_CSRF_TRUSTED_ORIGINS": url,
        "TUNNEL_URL": url,
    }

    lines: list[str] = []
    if ENV_PATH.exists():
        lines = ENV_PATH.read_text(encoding="utf-8").splitlines()

    seen = set()
    new_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            new_lines.append(line)
            continue
        key, _ = line.split("=", 1)
        key = key.strip()
        if key in updates:
            new_lines.append(f"{key}={updates[key]}")
            seen.add(key)
        else:
            new_lines.append(line)

    for key, value in updates.items():
        if key not in seen:
            new_lines.append(f"{key}={value}")

    ENV_PATH.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    SITE_PATH.write_text(f"{url}\n", encoding="utf-8")


def main() -> int:
    url = os.getenv("TUNNEL_TARGET_URL", DEFAULT_URL)
    try:
        cloudflared = _find_cloudflared()
    except FileNotFoundError as exc:
        print(str(exc))
        return 1

    print(f"Starting quick tunnel for {url}")
    process = subprocess.Popen(
        [cloudflared, "tunnel", "--url", url],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    updated = False
    assert process.stdout is not None
    for line in process.stdout:
        sys.stdout.write(line)
        sys.stdout.flush()
        if not updated:
            match = TUNNEL_REGEX.search(line)
            if match:
                tunnel_url = match.group(0)
                _update_env(tunnel_url)
                print(f"\n✅ Tunnel URL найден: {tunnel_url}")
                print("✅ .env и site.txt обновлены.")
                updated = True

    return process.wait()


if __name__ == "__main__":
    raise SystemExit(main())
