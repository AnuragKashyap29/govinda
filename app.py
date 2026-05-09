# app.py  —  Govinda AI · Exotel Call Proxy
# Run:  python app.py
# Deps: pip install flask flask-cors requests

from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s  %(levelname)s  %(message)s')
log = logging.getLogger(__name__)

app = Flask(__name__)

# ── Allow ALL origins (the HTML file can be opened from any path/port) ──
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=False)

# ── Exotel credentials ────────────────────────────────────────────────────
EXOTEL_API_KEY   = '49247f52bc1daecb864dd16663e55c8eac997c200bc4e8ae'
EXOTEL_API_TOKEN = 'e0843eaed23d3a3e725b193ae6131130da6825ca39fe4934'
EXOTEL_ACCOUNT   = 'xpertnoteanalytics1'
EXOTEL_SUBDOMAIN = 'api.exotel.com'
EXOTEL_EXOPHONE  = '09513886363'
EXOTEL_URL       = f'https://{EXOTEL_SUBDOMAIN}/v1/Accounts/{EXOTEL_ACCOUNT}/Calls.json'
# ─────────────────────────────────────────────────────────────────────────


def _parse_body():
    """
    Parse incoming request body regardless of how the browser sends it.
    Handles:
      - application/x-www-form-urlencoded  (standard form POST)
      - application/json                   (JSON body)
      - raw body with query-string format
    """
    # 1. Try standard form data first
    if request.form:
        return request.form.to_dict()

    # 2. Try JSON body
    if request.is_json:
        return request.get_json(force=True, silent=True) or {}

    # 3. Try raw body as URL-encoded string
    raw = request.get_data(as_text=True)
    if raw:
        from urllib.parse import parse_qs
        parsed = parse_qs(raw)
        return {k: v[0] for k, v in parsed.items()}

    return {}


@app.route('/call', methods=['POST', 'OPTIONS'])
def make_call():
    """Proxy a call request to Exotel, bypassing browser CORS restrictions."""

    # Preflight — flask_cors handles OPTIONS automatically, but belt-and-suspenders:
    if request.method == 'OPTIONS':
        return '', 204

    data = _parse_body()
    log.info(f"Received /call request: {data}")

    to_number = data.get('To', '').strip()
    if not to_number:
        log.warning("Missing 'To' field in request")
        return jsonify({'error': 'Missing "To" phone number'}), 400

    # Build Exotel payload
    payload = {
        'From'             : data.get('From', EXOTEL_EXOPHONE),
        'To'               : to_number,
        'CallerId'         : data.get('CallerId', EXOTEL_EXOPHONE),
        'CustomField'      : data.get('CustomField', 'RKJ_LABS_FEEDBACK'),
        'Record'           : data.get('Record', 'true'),
        'RecordingChannels': data.get('RecordingChannels', 'dual'),
    }

    log.info(f"Forwarding to Exotel → To: {payload['To']}  From: {payload['From']}")

    try:
        resp = requests.post(
            EXOTEL_URL,
            auth=(EXOTEL_API_KEY, EXOTEL_API_TOKEN),
            data=payload,
            timeout=15,
        )

        log.info(f"Exotel HTTP {resp.status_code}: {resp.text[:200]}")

        # Safely parse JSON from Exotel
        try:
            exotel_data = resp.json()
        except ValueError:
            return jsonify({
                'error'  : 'Exotel returned non-JSON response',
                'details': resp.text[:500],
                'status' : resp.status_code,
            }), 502

        # Surface Exotel errors clearly
        if resp.status_code not in (200, 201):
            err_msg = (
                exotel_data.get('RestException', {}).get('Message')
                or exotel_data.get('message')
                or f'Exotel error (HTTP {resp.status_code})'
            )
            log.error(f"Exotel error: {err_msg}")
            return jsonify({'error': err_msg, 'raw': exotel_data}), resp.status_code

        return jsonify(exotel_data), resp.status_code

    except requests.exceptions.Timeout:
        log.error("Exotel request timed out")
        return jsonify({'error': 'Exotel request timed out after 15s'}), 504

    except requests.exceptions.ConnectionError as e:
        log.error(f"Connection error: {e}")
        return jsonify({'error': f'Could not reach Exotel API: {str(e)}'}), 502

    except Exception as e:
        log.exception("Unexpected error in /call")
        return jsonify({'error': str(e)}), 500


@app.route('/health', methods=['GET'])
def health():
    """Simple health-check endpoint."""
    return jsonify({
        'status' : 'ok',
        'service': 'Govinda AI Call Proxy',
        'account': EXOTEL_ACCOUNT,
        'exophone': EXOTEL_EXOPHONE,
    })


if __name__ == '__main__':
    print()
    print("=" * 56)
    print("  🧑‍⚕️   Govinda AI — Exotel Call Proxy")
    print("  🚀   http://localhost:5000")
    print("  ✅   /call   POST  — trigger outbound call")
    print("  ✅   /health GET   — service health check")
    print("=" * 56)
    print()
    app.run(host='0.0.0.0', port=5000, debug=False)