# Tripletex Agent Deployment Options

## Option A: GCP Cloud Run (Production)

Best for: stable, scalable production deployment.

### Prerequisites
- `gcloud` CLI installed (`brew install google-cloud-sdk`)
- `@gcplab.me` Google account credentials (provided by competition)

### Steps
1. Authenticate: `gcloud auth login` (use @gcplab.me account)
2. Set project: `gcloud config set project <PROJECT_ID>`
3. Enable APIs: `gcloud services enable run.googleapis.com artifactregistry.googleapis.com`
4. Deploy: `cd tripletex && bash deploy.sh`
5. Register the Cloud Run URL at app.ainm.no

### Notes
- Auto-scales to zero when idle (cost-efficient)
- HTTPS provided automatically
- Requires GCP project access (currently unknown)

---

## Option B: ngrok Tunnel (Immediate Local Testing)

Best for: quick testing and early submissions while GCP is being set up.

### Prerequisites
- Python 3.10+ with pip
- ngrok installed (`brew install ngrok`) and authenticated (`ngrok config add-authtoken <TOKEN>`)

### Steps
1. Run: `cd tripletex && bash expose_local.sh`
2. Copy the HTTPS URL from ngrok output
3. Register the URL at app.ainm.no

### Limitations
- URL changes on each restart (free tier)
- Requires local machine to stay running
- Not suitable for final production submission
- Free tier has request limits

---

## Option C: Alternative HTTPS Hosting

### Fly.io
```bash
# Install: brew install flyctl
fly auth login
fly launch --name tripletex-agent
fly deploy
```
- Free tier available, persistent URL, auto-HTTPS

### Railway
```bash
# Install: npm install -g @railway/cli
railway login
railway init
railway up
```
- Simple deploys from Git, auto-HTTPS

### Render
- Connect GitHub repo, auto-deploy on push
- Free tier with auto-HTTPS

---

## Recommendation

1. **Now**: Use Option B (ngrok) for immediate testing
2. **When GCP access is confirmed**: Switch to Option A (Cloud Run) for production
3. **Fallback**: Option C if GCP access is delayed
