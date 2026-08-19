# Signal — ZimaBoard Setup Guide

Deploy Signal on a ZimaBoard running ZimaOS so it starts automatically on boot and is accessible from any device on the local network.

## Prerequisites

- ZimaBoard with ZimaOS installed (Docker Engine is pre-installed)
- SSH access to the ZimaBoard
- Your Last.fm API key and username
- Your Spotify client ID, client secret, and refresh token
- `git` and `make` available on the ZimaBoard (`sudo apt install git make` if missing)

---

## Step 1 — Find the ZimaBoard's LAN IP

SSH into the ZimaBoard and run:

```bash
ip addr show | grep "inet 192.168"
```

Note the IP (e.g. `192.168.1.42`). Assign it as a static IP or DHCP reservation in your router so it never changes.

---

## Step 2 — Clone the repository

```bash
git clone <repo-url> ~/signal
cd ~/signal
```

---

## Step 3 — Configure `.env`

```bash
cp .env.example .env
nano .env
```

Fill in these values:

| Variable | Value |
|---|---|
| `HOST_IP` | ZimaBoard's LAN IP (e.g. `192.168.1.42`) |
| `LASTFM_API_KEY` | Your Last.fm API key |
| `LASTFM_USERNAME` | Your Last.fm username |
| `SPOTIFY_CLIENT_ID` | Your Spotify app client ID |
| `SPOTIFY_CLIENT_SECRET` | Your Spotify app client secret |
| `SPOTIFY_REFRESH_TOKEN` | Your Spotify refresh token |
| `POSTGRES_PASSWORD` | A strong password (change from default `signal`) |

Leave all other values at their defaults.

---

## Step 4 — Build and start

First boot builds all images from source — this takes ~5–10 minutes:

```bash
make zima-up
```

On subsequent boots Docker reuses cached images and starts in seconds.

---

## Step 5 — Run onboarding (first time only)

Onboarding classifies your existing Spotify follows and listening history into the artist state machine. It must run **once** after the first deployment, from your development machine (requires `uv`):

```bash
# From your dev machine, with the ZimaBoard's PostgreSQL reachable:
DATABASE_URL=postgresql://signal:<POSTGRES_PASSWORD>@<HOST_IP>:5432/signal \
  uv run scripts/onboarding.py
```

Or SSH into the ZimaBoard and run it there if you have Python/uv installed.

---

## Step 6 — Verify everything is healthy

Run from the ZimaBoard:

```bash
make ps
```

Expected output — all services should show `Up` or `Up (healthy)`:

```
signal-kafka          Up (healthy)
signal-postgres       Up (healthy)
signal-kafka-init     Exited (0)      ← one-shot, exit 0 is correct
signal-migrate        Exited (0)      ← one-shot, exit 0 is correct
signal-lastfm-ingester  Up
signal-normalizer       Up
signal-enricher         Up
signal-history-tracker  Up
signal-novelty-detector Up
signal-scorer           Up
signal-artist-tracker   Up
signal-api              Up
signal-dashboard        Up
signal-kafka-exporter   Up
signal-prometheus       Up
signal-grafana          Up
```

From another device on the same network, open:

- **API (Swagger UI)**: `http://<HOST_IP>:8000/docs`
- **Dashboard**: `http://<HOST_IP>:5173`
- **Grafana**: `http://<HOST_IP>:3000`

---

## Auto-start behaviour

All services use `restart: unless-stopped`. The Docker daemon starts automatically on ZimaOS boot via systemd. This means:

- On reboot → Docker starts → all Signal containers start automatically
- On container crash → Docker restarts the container automatically
- On `make zima-down` (manual stop) → containers stay stopped until you explicitly start them again

---

## Useful commands

```bash
make ps                    # Status of all containers
make logs s=lastfm-ingester  # Live logs for a service
make zima-down             # Stop everything (keeps data)
make infra-clean           # Stop and DELETE all data volumes (destructive)
make kafka-topics          # List Kafka topics
make psql                  # Open PostgreSQL shell
```

---

## Troubleshooting

### Port conflict with another ZimaOS service

Check what's using a port:

```bash
ss -tlnp | grep 8000
```

If another service uses port 8000 (or 5173, 3000, 9090), either stop that service or change Signal's port in `infra/docker-compose.yml`.

### Kafka not ready on first boot

`kafka-init` retries automatically until Kafka is healthy (up to 10 retries × 15s). If it fails, restart it:

```bash
docker start signal-kafka-init
```

### Services fail to connect after reboot

Postgres runs a crash-recovery pass on startup. Services that connect during this window get a connection error and restart automatically. This is normal — all services have `restart: unless-stopped` and will reconnect within ~30 seconds.

### `HOST_IP` not set

If Kafka shows connection errors from external clients, check that `HOST_IP` is set in `.env` and matches the ZimaBoard's actual LAN IP. Restart Kafka after changing it:

```bash
docker restart signal-kafka
```
