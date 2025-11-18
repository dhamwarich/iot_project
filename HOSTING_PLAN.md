# Cloud Hosting Plan for Plant Robot Dashboard

This document captures the next steps to move the FastAPI dashboard to a managed environment (NETPIE or an equivalent host).

## 1. Project Structure Recap

```
app.py                # FastAPI + RobotController + API routes
templates/dashboard.html
static/dashboard.css
static/dashboard.js
```

The `/state` endpoint serves data, and `/` renders the template (which loads the CSS/JS assets).

## 2. Packaging & Readiness Checklist

1. **Dependencies**: ensure `fastapi`, `uvicorn[standard]`, `jinja2` are in `requirements.txt` (create the file if missing).
2. **Entry point**: confirm that running `uvicorn app:app --host 0.0.0.0 --port $PORT` works locally.
3. **Static/Template folders**: remain relative to the project root so that cloud runners can locate them.

## 3. Rapid Tunneling Demo via ngrok

Use ngrok when you need to expose your local FastAPI server temporarily (demo, quick test, stakeholder review).

1. **Install ngrok**: download from https://ngrok.com, install binary, and run `ngrok config add-authtoken <token>` once.
2. **Run FastAPI locally**: `uvicorn app:app --host 0.0.0.0 --port 8000` (or another port if needed).
3. **Open tunnel**: in another terminal, execute `ngrok http 8000`. ngrok prints a public HTTPS URL like `https://1234abcd.ngrok.io`.
4. **Share the URL**: stakeholders can hit `/` for the dashboard and `/state` for the API while the tunnel remains active.
5. **Optional hardening**:
   - Use `ngrok http --basic-auth username:password 8000` to protect access.
   - Reserve a domain on paid plans (`ngrok http --domain plantbot.ngrok.app 8000`).
   - Add ngrok to `.env` + scripts for reproducible demos.

Limitations: ngrok tunnels die when you stop the client, free URLs rotate per session, and your machine must stay online. For 24/7 access, move to a persistent host (Render, Railway, VPS, etc.).

## 4. Deploying on NETPIE (MicroGear HTTP Service)

NETPIE normally focuses on MQTT/pub-sub. To host the dashboard:

1. **Create an app** in NETPIE portal, obtain `APPID`, `KEY`, `SECRET`.
2. **Use NETPIE Freeboard** or **Microgear HTTP hosting**: upload the static HTML/CSS/JS bundle and embed the `/state` API via public HTTPS URL (requires the FastAPI server elsewhere) OR
3. **Run FastAPI on a NETPIE Cloud VM** (if available in your plan):
   - Provision a MicroGear container / VM.
   - SSH in, install Python + project deps.
   - Run `uvicorn app:app --host 0.0.0.0 --port 80` under systemd/supervisor.
   - Configure NETPIE DNS to point to the instance.
4. **Secure API**: restrict `/state` with API key or NETPIE auth header if exposing publicly.

## 5. Alternative (Render/Railway/Vercel + MQTT via NETPIE)

If NETPIE will mainly provide the MQTT broker:

1. Deploy FastAPI to Render/Railway (Dockerfile or Procfile) so `/` and `/state` are accessible on HTTPS.
2. Point the dashboard JS to that URL (`const API_BASE = 'https://yourapp.render.com';`).
3. Use NETPIE only for device telemetry (STM32 publishes to NETPIE MQTT; FastAPI subscribes via `microgear` client or a background task).

## 6. Next Implementation Tasks

1. Add `requirements.txt` listing FastAPI, uvicorn, jinja2, gpiozero, pyserial.
2. Parameterize API base URL in `static/dashboard.js` for cloud deployment.
3. Decide hosting path:
   - **Option A**: NETPIE VM hosts FastAPI + static assets.
   - **Option B**: Managed PaaS (Render/Railway) hosts FastAPI; NETPIE remains IoT broker.
4. Add deployment instructions (Dockerfile or systemd service).
5. Implement basic auth/token for `/state` if exposed publicly.

Once we pick the hosting path, we can script the deployment (Dockerfile + Compose) or configure NETPIE Freeboard accordingly.
