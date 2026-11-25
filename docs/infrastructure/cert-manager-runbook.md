# Dev server runbook (kasyno-edu)

## What this is

One Oracle Cloud VM (Always Free, arm64) running the app at `https://dev.edu-kasyno.online`.
Three Docker containers, started with Docker Compose in `/opt/kasyno`:

| Container | Job |
|---|---|
| `kasyno-nginx-1` | Entry point: HTTPS (port 443), redirect 80 → 443, sends `/api/` to the backend and the rest to the frontend |
| `kasyno-frontend-1` | Angular app (static files) |
| `kasyno-backend-1` | FastAPI backend (uses Firebase) |

Who sets up what:

| Tool | What it does | Where |
|---|---|---|
| Terraform | Creates the cloud network and the VM | `infra-dev/terraform` |
| Ansible | Prepares the server, copies secrets | `infra-dev/ansible` |
| GitHub Actions | Builds images, deploys, checks health | `.github/workflows/cd-dev.yml` |

## 1. Normal deploy

Merge to `main`. Watch GitHub → Actions → "CD (dev)". Green means deployed.
After the deploy, the pipeline waits up to 150 s for `/api/health`. If it never answers, it rolls back to the previous version by itself and the run turns red.

Do not edit `docker-compose.yml` or `nginx/` on the server. Every deploy overwrites them from the repo. Change them in the repo.

## 2. Connect to the server

```bash
ssh -i ~/.ssh/oci_dev ubuntu@<SERVER_IP>     # IP: terraform output public_ip
cd /opt/kasyno
```

## 3. Check that it works

```bash
docker ps                                     # 3 containers, frontend and backend "healthy"
curl -s --resolve dev.edu-kasyno.online:443:127.0.0.1 https://dev.edu-kasyno.online/api/health
```

Expected answer: `{"status":"ok", ... "firebase_initialized":true}`.

## 4. Read logs

```bash
docker logs -f kasyno-backend-1      # Ctrl+C to stop
docker logs --tail 50 kasyno-nginx-1
docker logs --tail 50 kasyno-frontend-1
```

## 5. Restart

```bash
IMAGE_TAG=$(cat .image_tag) docker compose up -d          # start/update everything
IMAGE_TAG=$(cat .image_tag) docker compose restart backend
```

`.image_tag` holds the version (git commit ID) of the last successful deploy.

## 6. Roll back by hand

Best way: revert the bad commit on `main`. The CD deploys the old code again.
Emergency way, on the server (take the old commit ID from GitHub Actions or `git log`):

```bash
IMAGE_TAG=<old_commit_id> docker compose up -d
echo <old_commit_id> > .image_tag
```

## 7. Where secrets live

| Secret | Where | How to change |
|---|---|---|
| Backend `.env` and Firebase key | Only on the server (`/opt/kasyno`) | Edit `infra-dev/ansible/secrets/dev.env` (local, not in git), run `ansible-playbook -i inventory.ini secrets.yml`, then `docker compose restart backend` |
| SSH key, host, user for the CD | GitHub → Settings → Environments → `dev` → Secrets | Edit there |
| Firebase web values (frontend) | GitHub → Environments → `dev` → **Variables** | Edit there, then push a new commit (the values are baked into the image at build time) |

## 8. HTTPS certificate (manual renewal!)

Let's Encrypt certificate for `dev.edu-kasyno.online`. **Expires 2027-02-23.**
Automatic renewal is NOT set up yet. Renew by hand before about 2027-02-01
(Let's Encrypt also emails a warning to the address used at registration):

```bash
cd /opt/kasyno
IMAGE_TAG=$(cat .image_tag) docker compose run --rm certbot renew --force-renewal
IMAGE_TAG=$(cat .image_tag) docker compose exec -T nginx nginx -s reload
```

Check: `sudo openssl x509 -in certbot/conf/live/dev.edu-kasyno.online/fullchain.pem -noout -dates`

## 9. Build the server from scratch

1. `terraform apply`, then put the new IP in `inventory.ini` and in the GitHub secret `SSH_HOST`.
2. Update the `SSH_KNOWN_HOSTS` secret with the single line from `ssh-keyscan -t ed25519 <IP>`.
3. Run the Ansible server playbook, then `secrets.yml`.
4. Point the DNS record (Cloudflare) to the new IP.
5. **Certificate first:** nginx cannot start while the certificate files do not exist, because of the `443` block. So for the first deploy, comment out the whole `listen 443` server block in `nginx/default.conf`, deploy, and get the certificate:
   ```bash
   cd /opt/kasyno
   IMAGE_TAG=$(cat .image_tag) docker compose run --rm certbot certonly \
     --webroot -w /var/www/certbot -d dev.edu-kasyno.online \
     --email <YOUR_EMAIL> --agree-tos --no-eff-email
   ```
   Then put the `443` block back and deploy again.

## 10. Common problems

| What you see | Likely cause | Fix |
|---|---|---|
| CD fails: "Host key verification failed" | Wrong `SSH_KNOWN_HOSTS` secret | Use only the single `<IP> ssh-ed25519 AAAA...` line from `ssh-keyscan` |
| Health check returns 502 | Backend crashed | `docker logs kasyno-backend-1`. Usually a wrong value in `/opt/kasyno/.env` |
| Cloudflare error 521 | nginx is down or has no HTTPS | `docker ps`, `docker logs kasyno-nginx-1`; Cloudflare SSL mode should be Full (strict) |
| Browser: too many redirects | Cloudflare SSL mode is Flexible | Set it to Full (strict) |
| "Firebase nie jest skonfigurowany" | Frontend was built with empty Firebase variables | Check the `dev` Variables, then push a new commit to rebuild |
| Server files changed back by themselves | CD copies them from the repo on each deploy | Make the change in the repo |
| Google/Facebook login popup fails | Domain not allowed in Firebase | Firebase → Authentication → Settings → Authorized domains |