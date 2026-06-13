"""CampusFlow Startup Orchestrator — auto-launches ngrok, WhatsApp bridge, and VTOP sync.

This runs during FastAPI lifespan startup and handles:
1. Start ngrok tunnel (exposes port 8000 publicly for WhatsApp webhooks)
2. Connect WhatsApp via Evolution API (Docker must be running)
3. Trigger initial VTOP sync (if session cookies exist)
"""

import asyncio
import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

BACKEND_ROOT = Path(__file__).resolve().parent.parent
EVOLUTION_BASE = os.getenv("EVOLUTION_BASE_URL", "http://localhost:8080")
EVOLUTION_API_KEY = os.getenv("EVOLUTION_API_KEY", "campusflow-secret")
INSTANCE_NAME = "campusflow"

# Global reference to ngrok tunnel so we can tear it down on shutdown
_ngrok_tunnel = None
_ngrok_url: str | None = None


def get_ngrok_url() -> str | None:
    """Return the active ngrok public URL (if tunnel is running)."""
    return _ngrok_url


async def run_startup_orchestrator():
    """Main startup sequence — called from lifespan."""
    logger.info("=" * 60)
    logger.info("CampusFlow Startup Orchestrator")
    logger.info("=" * 60)

    # Step 1: Start ngrok tunnel
    ngrok_url = await _start_ngrok()

    # Step 2: Connect WhatsApp (needs Docker + ngrok)
    if ngrok_url:
        await _setup_whatsapp(ngrok_url)
    else:
        logger.warning("Skipping WhatsApp setup — ngrok not available")

    # Step 3: Trigger initial VTOP sync (non-blocking)
    asyncio.create_task(_initial_vtop_sync(), name="startup-vtop-sync")

    logger.info("=" * 60)
    logger.info("Startup orchestration complete")
    logger.info("=" * 60)


async def _start_ngrok() -> str | None:
    """Start an ngrok tunnel on port 8000. Returns public URL or None."""
    global _ngrok_tunnel, _ngrok_url

    auth_token = os.getenv("NGROK_AUTHTOKEN")

    # Strategy 1: Try pyngrok with system ngrok binary
    try:
        from pyngrok import ngrok, conf
        from pyngrok.conf import PyngrokConfig

        # Point pyngrok to the system-installed ngrok instead of downloading
        system_ngrok = _find_system_ngrok()
        if system_ngrok:
            pyngrok_config = PyngrokConfig(ngrok_path=system_ngrok)
            conf.set_default(pyngrok_config)

        if auth_token:
            conf.get_default().auth_token = auth_token
        else:
            logger.warning("[ngrok] No NGROK_AUTHTOKEN in .env — tunnel may fail without auth")
            logger.info("[ngrok] Get a free token at: https://dashboard.ngrok.com/get-started/your-authtoken")

        logger.info("[ngrok] Starting tunnel on port 8000...")
        _ngrok_tunnel = ngrok.connect(8000, "http")
        _ngrok_url = _ngrok_tunnel.public_url

        # Ensure HTTPS
        if _ngrok_url.startswith("http://"):
            _ngrok_url = _ngrok_url.replace("http://", "https://")

        logger.info("[ngrok] ✓ Tunnel active: %s", _ngrok_url)
        return _ngrok_url

    except ImportError:
        logger.warning("[ngrok] pyngrok not installed. Run: pip install pyngrok")
    except Exception as e:
        logger.error("[ngrok] pyngrok failed: %s", e)

    # Strategy 2: Start ngrok as a subprocess and parse the API
    return await _start_ngrok_subprocess(auth_token)


def _find_system_ngrok() -> str | None:
    """Find ngrok binary on the system PATH."""
    import shutil
    path = shutil.which("ngrok")
    if path:
        logger.info("[ngrok] Using system ngrok: %s", path)
    return path


async def _start_ngrok_subprocess(auth_token: str | None) -> str | None:
    """Fallback: start ngrok as a background subprocess and get URL from its API."""
    global _ngrok_url

    ngrok_path = _find_system_ngrok()
    if not ngrok_path:
        logger.error("[ngrok] ngrok not found. Install from: https://ngrok.com/download")
        return None

    try:
        # Start ngrok in background
        logger.info("[ngrok] Starting ngrok subprocess...")
        process = subprocess.Popen(
            [ngrok_path, "http", "8000"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        # Wait for ngrok to start and get the public URL from its local API
        await asyncio.sleep(3)

        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get("http://127.0.0.1:4040/api/tunnels")
            if r.status_code == 200:
                tunnels = r.json().get("tunnels", [])
                for tunnel in tunnels:
                    if tunnel.get("proto") == "https":
                        _ngrok_url = tunnel["public_url"]
                        logger.info("[ngrok] ✓ Tunnel active (subprocess): %s", _ngrok_url)
                        return _ngrok_url
                # If no https, use first available
                if tunnels:
                    _ngrok_url = tunnels[0]["public_url"]
                    if _ngrok_url.startswith("http://"):
                        _ngrok_url = _ngrok_url.replace("http://", "https://")
                    logger.info("[ngrok] ✓ Tunnel active (subprocess): %s", _ngrok_url)
                    return _ngrok_url

        logger.warning("[ngrok] Subprocess started but couldn't get tunnel URL")
        return None

    except Exception as e:
        logger.error("[ngrok] Subprocess start failed: %s", e)
        logger.info("[ngrok] Run 'ngrok http 8000' manually in another terminal")
        return None


async def _setup_whatsapp(ngrok_url: str):
    """Connect WhatsApp via Evolution API. Docker container must be running."""
    headers = {
        "apikey": EVOLUTION_API_KEY,
        "Content-Type": "application/json",
    }

    # Check if Evolution API (Docker) is running
    logger.info("[WhatsApp] Checking Evolution API...")
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(f"{EVOLUTION_BASE}/")
            if r.status_code >= 500:
                raise Exception(f"Server error: {r.status_code}")
    except Exception as e:
        logger.warning("[WhatsApp] Evolution API not running: %s", e)
        logger.info("[WhatsApp] Start it with: docker-compose up -d (from project root)")
        # Try to auto-start Docker
        await _try_start_docker()
        # Check again
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(f"{EVOLUTION_BASE}/")
                if r.status_code >= 500:
                    raise Exception("Still not healthy")
        except Exception:
            logger.error("[WhatsApp] ✗ Evolution API still not available. Skipping WhatsApp setup.")
            return

    logger.info("[WhatsApp] ✓ Evolution API is running")

    # Check if instance already exists and is connected
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                f"{EVOLUTION_BASE}/instance/connectionState/{INSTANCE_NAME}",
                headers=headers,
            )
            if r.status_code == 200:
                data = r.json()
                state = data.get("instance", data).get("state", "unknown")
                if state == "open":
                    # Already connected — just update the webhook URL
                    logger.info("[WhatsApp] ✓ Already connected! Updating webhook URL...")
                    await _update_webhook(ngrok_url, headers)
                    return
                else:
                    logger.info("[WhatsApp] Instance exists but state=%s. Recreating...", state)
    except Exception:
        pass

    # Delete old instance and create fresh one
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.delete(
                f"{EVOLUTION_BASE}/instance/delete/{INSTANCE_NAME}",
                headers=headers,
            )
    except Exception:
        pass

    await asyncio.sleep(1)

    # Create new instance with webhook
    webhook_url = f"{ngrok_url}/api/webhooks/whatsapp"
    payload = {
        "instanceName": INSTANCE_NAME,
        "qrcode": True,
        "webhook": webhook_url,
        "webhook_by_events": True,
        "webhook_base64": False,
        "events": ["MESSAGES_UPSERT"],
    }

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(
                f"{EVOLUTION_BASE}/instance/create",
                headers=headers,
                json=payload,
            )
            result = r.json()
            logger.info("[WhatsApp] Instance created: %s", json.dumps(result.get("instance", {})))
            logger.info("[WhatsApp] Webhook URL: %s", webhook_url)
    except Exception as e:
        logger.error("[WhatsApp] Failed to create instance: %s", e)
        return

    # Fetch and save QR code
    await asyncio.sleep(3)
    await _fetch_and_save_qr(headers)

    # Wait for QR scan (check periodically in background)
    asyncio.create_task(
        _wait_for_whatsapp_connection(headers, webhook_url),
        name="whatsapp-connection-wait",
    )


async def _update_webhook(ngrok_url: str, headers: dict):
    """Update the webhook URL for an existing connected instance."""
    webhook_url = f"{ngrok_url}/api/webhooks/whatsapp"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.put(
                f"{EVOLUTION_BASE}/instance/update/{INSTANCE_NAME}",
                headers=headers,
                json={
                    "webhook": webhook_url,
                    "webhook_by_events": True,
                    "events": ["MESSAGES_UPSERT"],
                },
            )
            if r.status_code == 200:
                logger.info("[WhatsApp] ✓ Webhook updated: %s", webhook_url)
            else:
                logger.warning("[WhatsApp] Webhook update response: %s", r.text[:200])
    except Exception as e:
        logger.warning("[WhatsApp] Could not update webhook: %s", e)


async def _fetch_and_save_qr(headers: dict):
    """Fetch QR code from Evolution API and save as HTML file."""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(
                f"{EVOLUTION_BASE}/instance/connect/{INSTANCE_NAME}",
                headers=headers,
            )
            data = r.json()

        base64_qr = data.get("base64")
        if not base64_qr:
            qrcode_obj = data.get("qrcode")
            if isinstance(qrcode_obj, dict):
                base64_qr = qrcode_obj.get("base64")

        if not base64_qr:
            logger.warning("[WhatsApp] No QR code available yet")
            return

        if not base64_qr.startswith("data:"):
            base64_qr = f"data:image/png;base64,{base64_qr}"

        html = f"""<!DOCTYPE html>
<html>
<body style="display:flex;flex-direction:column;align-items:center;font-family:sans-serif;padding:40px">
  <h2>Scan this QR code with WhatsApp</h2>
  <p>Open WhatsApp &rarr; Linked Devices &rarr; Link a Device</p>
  <img src="{base64_qr}" style="width:300px;height:300px;border:2px solid #ccc;padding:10px"/>
  <p style="color:gray;margin-top:20px">This QR code expires in 60 seconds.</p>
</body>
</html>"""
        qr_path = BACKEND_ROOT / "whatsapp_qr.html"
        with open(qr_path, "w") as f:
            f.write(html)

        logger.info("[WhatsApp] ✓ QR code saved: %s", qr_path)
        logger.info("[WhatsApp] Open whatsapp_qr.html in browser and scan with WhatsApp!")

    except Exception as e:
        logger.error("[WhatsApp] Failed to fetch QR code: %s", e)


async def _wait_for_whatsapp_connection(headers: dict, webhook_url: str):
    """Background task: poll connection state until WhatsApp is connected."""
    for i in range(36):  # 3 minutes (36 * 5s)
        await asyncio.sleep(5)
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(
                    f"{EVOLUTION_BASE}/instance/connectionState/{INSTANCE_NAME}",
                    headers=headers,
                )
                data = r.json()
                state = data.get("instance", data).get("state", "unknown")
                if state == "open":
                    logger.info("[WhatsApp] ✓ Connected! Messages will flow to: %s", webhook_url)
                    return
        except Exception:
            pass

    logger.warning("[WhatsApp] QR code may have expired. Restart the backend or re-scan.")


async def _try_start_docker():
    """Attempt to start Evolution API via docker-compose."""
    compose_file = BACKEND_ROOT.parent / "docker-compose.yml"
    if not compose_file.exists():
        return

    logger.info("[WhatsApp] Attempting to start Evolution API via docker-compose...")
    try:
        result = subprocess.run(
            ["docker-compose", "up", "-d"],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(compose_file.parent),
        )
        if result.returncode == 0:
            logger.info("[WhatsApp] ✓ Docker container started")
            await asyncio.sleep(5)  # Give it time to boot
        else:
            # Try docker compose (v2) instead of docker-compose
            result = subprocess.run(
                ["docker", "compose", "up", "-d"],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=str(compose_file.parent),
            )
            if result.returncode == 0:
                logger.info("[WhatsApp] ✓ Docker container started (compose v2)")
                await asyncio.sleep(5)
            else:
                logger.warning("[WhatsApp] docker-compose failed: %s", result.stderr[:200])
    except FileNotFoundError:
        logger.warning("[WhatsApp] docker-compose not found on PATH")
    except Exception as e:
        logger.warning("[WhatsApp] Docker start failed: %s", e)


async def _initial_vtop_sync():
    """Run an initial VTOP sync if session cookies exist."""
    session_file = BACKEND_ROOT / "vtop_session.json"
    if not session_file.exists():
        logger.info("[VTOP] No session file. Run 'python vtop_login_browser.py' to login first.")
        logger.info("[VTOP] Scheduler will poll VTOP every %ss once session is available.",
                    os.getenv("VTOP_POLL_INTERVAL", "1800"))
        return

    logger.info("[VTOP] Session file found. Triggering initial sync...")

    try:
        worker_script = BACKEND_ROOT / "vtop_sync_worker.py"
        result = subprocess.run(
            [sys.executable, str(worker_script)],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(BACKEND_ROOT),
        )
        if result.returncode == 0:
            lines = [l for l in result.stdout.strip().split("\n") if l.strip()]
            if lines:
                try:
                    summary = json.loads(lines[-1])
                    logger.info("[VTOP] ✓ Initial sync complete: %s", summary)
                except json.JSONDecodeError:
                    logger.info("[VTOP] ✓ Sync finished (output: %s)", result.stdout[-200:])
        else:
            logger.warning("[VTOP] Initial sync failed: %s", result.stderr[-300:])
            if "Session expired" in result.stderr or "Session expired" in result.stdout:
                logger.info("[VTOP] Session expired. Re-run: python vtop_login_browser.py")
    except subprocess.TimeoutExpired:
        logger.warning("[VTOP] Initial sync timed out (120s)")
    except Exception as e:
        logger.error("[VTOP] Initial sync error: %s", e)


def shutdown_ngrok():
    """Kill ngrok tunnel on app shutdown."""
    global _ngrok_tunnel, _ngrok_url
    if _ngrok_tunnel:
        try:
            from pyngrok import ngrok
            ngrok.disconnect(_ngrok_tunnel.public_url)
            ngrok.kill()
            logger.info("[ngrok] Tunnel closed")
        except Exception:
            pass
    elif _ngrok_url:
        # Was started as subprocess — kill via ngrok API
        try:
            import httpx as httpx_sync
            # pyngrok kill works even if we used subprocess
            from pyngrok import ngrok
            ngrok.kill()
        except Exception:
            # Try killing ngrok process directly
            try:
                subprocess.run(
                    ["taskkill", "/f", "/im", "ngrok.exe"],
                    capture_output=True,
                    timeout=5,
                )
            except Exception:
                pass
        logger.info("[ngrok] Tunnel closed")
    _ngrok_tunnel = None
    _ngrok_url = None
