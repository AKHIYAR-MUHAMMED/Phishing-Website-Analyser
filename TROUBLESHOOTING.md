# PhishGuard AI — Offline Troubleshooting Guide

Quick fixes for presentation day. All commands are PowerShell/Windows unless noted.

---

### API won't start

Run it in the foreground and read the actual error:
```bash
python -m uvicorn api:app --host 127.0.0.1 --port 8000
```
Common causes: wrong working directory (must be
`E:\Final Project\Phishing-Website-Analyser`), a missing dependency (see "Python dependency
issue" below), or the port already in use (see next).

### Port 8000 already occupied

Check what's listening:
```powershell
Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
```
If something is already there and it's an old PhishGuard instance, stop it (`Ctrl+C` in its
terminal), then restart. If you must use a different port:
```bash
python -m uvicorn api:app --host 127.0.0.1 --port 8001
```
and open `http://localhost:8001/demo` instead.

### /demo doesn't load

1. Confirm the server is actually running (see "how to verify the backend is alive" below).
2. Check the uvicorn terminal for a traceback right after the `GET /demo` request line.
3. Confirm `dashboard/demo.html` exists: `Test-Path "dashboard\demo.html"` should return `True`.

### Analyze button doesn't respond

1. Open the browser DevTools console (F12) and look for a red error.
2. Check the Network tab for the `POST /api/v2/analyze` request — inspect its status code and
   response body.
3. Confirm the backend is alive (below). If the backend crashed, restart it and reload `/demo`.

### Browser console errors

Most likely a stale page — hard-refresh with `Ctrl+F5`. If the error mentions a failed fetch to
`localhost:8000`, the backend is not running or was restarted on a different port — reload
`/demo` at the correct port.

### Python dependency issue

Reinstall from the pinned requirements:
```bash
pip install -r requirements.txt
```
If a specific import fails, note the exact missing package name from the traceback and install
it directly: `pip install <package>`.

### Model/checkpoint loading issue

The GNN loads `gnn_model_demo.pt` from the project root. If it's missing or fails to load, the
GNN component reports `status: "unavailable"` and is excluded from fusion — the demo still runs,
just without the GNN score. Confirm the file exists:
```powershell
Test-Path "gnn_model_demo.pt"
```
Do not attempt to retrain it before the presentation — see `PROJECT_STATUS.md` for why.

### Website crawl failure

If a demo URL fails to crawl (timeout, connection error, DNS failure), the dashboard will show
`verdict: unavailable` with the exact reason — this is expected, correct behavior, not a bug.
Switch to a known-good URL (`github.com`, or another site you tested earlier today) and continue
the demo.

### robots.txt blocking

The live demo's crawler (`crawler/fetcher.py`, used by `/api/v2/analyze`) does not read
`robots.txt` — this is a single, human-initiated on-demand fetch, not a bulk crawl (see the
module's own docstring). robots.txt is not a cause of failure here. A `403 Forbidden` from the
target site itself is still a valid `http_status: 403` result — the page was reached but
declined, which is a legitimate, real result to show.

### Internet unavailable

The demo pipeline requires a real live HTTP fetch — it cannot analyze a URL without network
access. If internet is unavailable during the presentation, explain this limitation directly:
say what the pipeline would do (crawl → features → GNN → semantic → fusion) using
`TECHNICAL_ARCHITECTURE.md`'s diagram, and, if you have one, show a screenshot/recording of a
previous successful run instead of a live scan.

### How to verify the backend is alive

```
http://localhost:8000/api/v1/health
```
Should return `{"status":"ok"}`. If this fails, the backend process is not running or crashed —
restart it per `DEMO_GUIDE.md` §2 and re-check.
