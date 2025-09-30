import requests

def post_file(url: str, file_tuple, session_id: str, timeout: int = 60):
    r = requests.post(url, files={"file": file_tuple}, headers={"X-Session-ID": session_id}, timeout=timeout)
    try:
        data = r.json()
    except Exception:
        data = None
    return r.status_code, r.text, data
