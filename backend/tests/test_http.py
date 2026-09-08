"""Exercise the shipped demo against an actual Uvicorn server and migrated DB."""

import json
import os
import secrets
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx


def test_real_http_demonstration(tmp_path):
    directory = Path(__file__).parents[1]
    env = {
        **os.environ,
        "DATABASE_URL": f"sqlite:///{tmp_path / 'http.db'}",
        "JWT_SECRET": secrets.token_urlsafe(48),
    }
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=directory,
        env=env,
        check=True,
        capture_output=True,
    )
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    server = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "mandiwise_transport.api:create_app",
            "--factory",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=directory,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        with httpx.Client(timeout=1) as client:
            for _ in range(50):
                assert server.poll() is None, "Uvicorn failed to start"
                try:
                    if client.get(f"http://127.0.0.1:{port}/health").status_code == 200:
                        break
                except httpx.TransportError:
                    time.sleep(0.1)
            else:
                raise AssertionError("Server did not become ready")
        result = subprocess.run(
            [sys.executable, "scripts/demo_client.py", "--port", str(port)],
            cwd=directory,
            env=env,
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        output = json.loads(result.stdout)
        assert output["state"] == "SETTLED"
        assert output["solo_40_quintals_inr"] == "3200.00"
        assert output["shared_80_quintals"]["total_savings_inr"] == "2700.00"
    finally:
        server.terminate()
        server.wait(timeout=10)
