"""
CampusFlow WhatsApp Setup Script

Run this AFTER:
  1. docker-compose up -d
  2. ngrok http 8000 (copy the https URL)

Usage:
  python setup_whatsapp.py --ngrok-url https://xxxx.ngrok-free.app
"""

import argparse
import json
import sys
import time
from typing import Optional

import httpx

EVOLUTION_BASE = "http://localhost:8080"
EVOLUTION_API_KEY = "campusflow-secret"
INSTANCE_NAME = "campusflow"

HEADERS = {
    "apikey": EVOLUTION_API_KEY,
    "Content-Type": "application/json",
}


def check_evolution_running() -> bool:
    try:
        r = httpx.get(f"{EVOLUTION_BASE}/", timeout=5)
        return r.status_code < 500
    except Exception:
        return False


def delete_instance_if_exists():
    """Delete existing instance to start fresh."""
    try:
        r = httpx.delete(
            f"{EVOLUTION_BASE}/instance/delete/{INSTANCE_NAME}",
            headers=HEADERS,
            timeout=10,
        )
        if r.status_code == 200:
            print("   (Deleted existing instance for clean setup)")
    except Exception:
        pass


def create_instance(ngrok_url: str) -> dict:
    """Create instance with webhook configured."""
    payload = {
        "instanceName": INSTANCE_NAME,
        "qrcode": True,
        "webhook": f"{ngrok_url}/api/webhooks/whatsapp",
        "webhook_by_events": True,
        "webhook_base64": False,
        "events": ["MESSAGES_UPSERT"],
    }
    r = httpx.post(
        f"{EVOLUTION_BASE}/instance/create",
        headers=HEADERS,
        json=payload,
        timeout=15,
    )
    return r.json()


def get_qr_code() -> Optional[str]:
    """Fetch QR code from the connect endpoint."""
    r = httpx.get(
        f"{EVOLUTION_BASE}/instance/connect/{INSTANCE_NAME}",
        headers=HEADERS,
        timeout=15,
    )
    data = r.json()
    # v1.8.x returns {"base64": "data:image/png;base64,...", "count": N}
    # or nested: {"qrcode": {"base64": "..."}}
    base64_val = data.get("base64")
    if base64_val:
        return base64_val
    qrcode_obj = data.get("qrcode")
    if isinstance(qrcode_obj, dict):
        return qrcode_obj.get("base64")
    return None


def check_connection_status() -> str:
    r = httpx.get(
        f"{EVOLUTION_BASE}/instance/connectionState/{INSTANCE_NAME}",
        headers=HEADERS,
        timeout=10,
    )
    data = r.json()
    # Handle both formats: {"instance": {"state": "..."}} and {"state": "..."}
    if "instance" in data:
        return data["instance"].get("state", "unknown")
    return data.get("state", "unknown")


def save_qr_as_html(base64_qr: str):
    """Save QR code as an HTML file that opens in browser."""
    # Ensure proper data URI prefix
    if not base64_qr.startswith("data:"):
        base64_qr = f"data:image/png;base64,{base64_qr}"

    html = f"""<!DOCTYPE html>
<html>
<body style="display:flex;flex-direction:column;align-items:center;font-family:sans-serif;padding:40px">
  <h2>Scan this QR code with WhatsApp</h2>
  <p>Open WhatsApp &rarr; Linked Devices &rarr; Link a Device</p>
  <img src="{base64_qr}" style="width:300px;height:300px;border:2px solid #ccc;padding:10px"/>
  <p style="color:gray;margin-top:20px">This QR code expires in 60 seconds. Re-run the script if it expires.</p>
</body>
</html>"""
    with open("whatsapp_qr.html", "w") as f:
        f.write(html)
    print("\n✅ QR code saved to whatsapp_qr.html — open it in your browser and scan with WhatsApp\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ngrok-url", required=True, help="Your ngrok public URL e.g. https://xxxx.ngrok-free.app")
    args = parser.parse_args()

    ngrok_url = args.ngrok_url.rstrip("/")

    print("🔍 Checking Evolution API...")
    if not check_evolution_running():
        print("❌ Evolution API is not running. Run: docker-compose up -d")
        sys.exit(1)
    print("✅ Evolution API is running\n")

    # Clean slate
    delete_instance_if_exists()
    time.sleep(1)

    print("📱 Creating WhatsApp instance...")
    result = create_instance(ngrok_url)

    instance_info = result.get("instance", result)
    print(f"   Instance: {json.dumps(instance_info, indent=2)}\n")

    if result.get("status", 200) >= 400 and "error" in result:
        print(f"❌ Failed to create instance: {result}")
        sys.exit(1)

    print(f"🔗 Webhook URL: {ngrok_url}/api/webhooks/whatsapp\n")

    print("📷 Fetching QR code...")
    time.sleep(3)

    # Try multiple times since QR generation can be slow
    qr = None
    for attempt in range(5):
        qr = get_qr_code()
        if qr:
            break
        print(f"   Waiting for QR code... (attempt {attempt + 1}/5)")
        time.sleep(3)

    if not qr:
        print("❌ Could not get QR code.")
        print("   Try opening http://localhost:8080 in your browser to check instance status.")
        print("   You can also re-run this script.")
        sys.exit(1)

    save_qr_as_html(qr)

    print("⏳ Waiting for you to scan the QR code (90 seconds)...")
    for i in range(18):
        time.sleep(5)
        status = check_connection_status()
        print(f"   Status: {status}")
        if status == "open":
            print("\n🎉 WhatsApp connected successfully!")
            print(f"   Webhook URL: {ngrok_url}/api/webhooks/whatsapp")
            print("   All incoming WhatsApp messages will now flow into CampusFlow.\n")
            return

    print("\n⚠️  QR code may have expired. Re-run this script to get a fresh QR code.")


if __name__ == "__main__":
    main()
