# Oracle Cloud DevOps learning path (issue #46, TECH-02: CD)

Goal: deploy the Angular frontend and FastAPI backend to the shared dev server
automatically after a merge to `main`, using Oracle Cloud for the infrastructure,
the image registry (OCIR) and the secrets (Vault), all defined as code with Terraform.

Status: plan only. Nothing here has been applied to the live server.
Rule for every step: Claude proposes a diff, you review it, you run
`terraform plan` and `terraform apply` yourself.

## 1. Free tier: what to verify before applying

The figures below came from a search overview, not from Oracle's documentation, so confirm
each one on the Always Free Resources page and in the console (Billing & Cost
Management) before you create anything.

| Service | Claimed free allowance | Verify |
| --- | --- | --- |
| Container Registry (OCIR) | Up to 500 GB of image storage, home region only | This is far above the ~20 GB Object Storage allowance I remembered. Check the page |
| Vault, software-protected keys | Free, any number of keys and vaults | Use only software keys (`protection_mode = "SOFTWARE"`) |
| Vault, HSM-protected keys | Only 20 key versions in total | Avoid HSM keys entirely |
| Vault secrets | Up to 150 secrets, 40 versions each | Our needs are about 3 secrets |
| Virtual private vault | Not free | Never create one; use the default shared vault |
| Reserved public IP | One free (to verify) | Check the networking limits page |

Home region: Always Free resources apply only in the tenancy's home region. The server
is in `eu-frankfurt-1`; confirm in the console that this is your home region.
If the account is Pay As You Go, going over a limit costs money. Set a budget alert
(Billing > Budgets) before step 1.

## 2. Target architecture

```text
GitHub push to main
  -> cd.yml: reusable CI (frontend + backend)
  -> build linux/arm64 images on ubuntu-24.04-arm
  -> push to OCIR  fra.ocir.io/<namespace>/kasyno-{frontend,backend}:<sha>
  -> SSH to dev-server (deploy user)
       -> fetch secrets from OCI Vault (instance principal, no stored password)
       -> docker compose pull && up -d, verify /api/health, roll back on failure

Internet -> Caddy (80/443, HTTPS via Let's Encrypt) -> frontend (/)  and  backend (/api)
                                                             backend -> Firebase
```

## 3. Concepts you will learn

- Compartment: a folder for cloud resources. We use the root compartment.
- Tenancy namespace: a string that prefixes registry paths (`fra.ocir.io/<namespace>/...`).
- IAM user, group, policy: who may do what. Policies are written as sentences, for example
  `Allow group ci-group to manage repos in tenancy`.
- Auth token: a password for tools such as `docker login`. It is shown once.
- Dynamic group and instance principal: lets the VM itself authenticate to OCI, so no
  secret is stored on the server to fetch secrets.
- Vault, key and secret: the vault holds a master key, and secrets are encrypted with it.
- Terraform state: a file mapping your code to real resources. It can contain sensitive
  values, so it must never go to git.

## 4. The path, step by step

Each step ends with a check. Do not move on until it passes.

### Step 0: Safety net

- Create a budget alert and confirm you are in the home region.
- Back up the local Terraform state (`terraform.tfstate`) somewhere private.
- Run `terraform plan` in `infra-dev/terraform`. It should report no changes. That
  proves the code matches the live server before you touch anything.

### Step 1: Reserved IP and DNS

- Terraform: `oci_core_public_ip` with `lifetime = "RESERVED"`, attached to the
  instance's VNIC (`private_ip_id`).
- DNS: at your domain registrar, create an A record `dev.<domain>` pointing to the
  reserved IP.
- Check: `dig +short dev.<domain>` returns the IP and `ssh ubuntu@dev.<domain>` works.
- Learn: the difference between ephemeral and reserved IPs, and why DNS needs a stable
  address.

### Step 2: Container registry (OCIR)

- Terraform: `oci_artifacts_container_repository` for `kasyno-frontend` and
  `kasyno-backend`. Decide on `is_public`: true means no login is needed to pull.
- Identity for CI: an `oci_identity_user` (a service user, not you), an
  `oci_identity_group`, a membership, and a policy such as
  `Allow group <ci-group> to manage repos in tenancy`.
  Then `oci_identity_auth_token` for that user.
- The auth token ends up in the Terraform state. Prefer creating the token in the console
  (Identity > Users > Auth tokens) and storing it directly in GitHub secrets.
- Docker login values: server `fra.ocir.io`; username `<namespace>/<username>` (with
  identity domains: `<namespace>/<domain>/<username>`); password is the auth token.
- Check: from your PC, `docker login fra.ocir.io`, then push a tiny test image and see it
  in the console.
- Learn: IAM from scratch, the least-privilege idea, and how registries authenticate.

### Step 3: Dockerfiles and Compose

- Frontend: Node build stage (`--platform=$BUILDPLATFORM`), `nginx-unprivileged` final
  stage on port 8080, SPA fallback. `API_URL=/api` and the Firebase web values are build args.
- Backend: Poetry builder, slim Python 3.13 final stage, non-root user, uvicorn with
  `--proxy-headers` (the rate limiter uses the client IP), `HEALTHCHECK` on `/api/health`.
- Compose: caddy, frontend, backend; only caddy publishes 80/443; `restart: unless-stopped`.
- A `.dockerignore` for each image so `.env`, `credentials/`, `node_modules` and `.venv`
  never reach the build.
- Check: `docker compose up --build` works on your amd64 PC, and the app logs in locally.
- Learn: multi-stage builds, multi-arch images, reverse proxies.

### Step 4: Pipeline

- `cd.yml`: `on: push` to `main`; calls `ci-frontend.yml` and `ci-backend.yml`; then build
  and push both images (arm64, tagged with the commit SHA); then deploy.
- Deploy over SSH with a dedicated `deploy` user and key, pinned `known_hosts`, a GitHub
  Environment `dev`, and `concurrency` so deploys never overlap.
- Verify `/api/health` (requiring `firebase_initialized: true`) and the web page, with
  retries. On failure restore the previous tag and fail the job.
- GitHub Environment secrets: OCIR auth token and username, SSH key. Variables: server host,
  namespace, public Firebase web config.
- Check: merge a trivial change; the server runs the new SHA. Break the health check on
  purpose; the job fails and rolls back.
- Learn: CI/CD design, rollback, concurrency, secrets in pipelines.

### Step 5: Vault

- Terraform: `oci_kms_vault` (type `DEFAULT`), `oci_kms_key` (`SOFTWARE`, AES),
  `oci_vault_secret` for the backend `.env` and the Firebase service-account JSON.
- Never put real values in Terraform. Create each secret with a placeholder and add
  `lifecycle { ignore_changes = [secret_content] }`, then set the real value in the
  console or CLI.
- Access for the VM: `oci_identity_dynamic_group` matching the instance
  (`instance.id = '<ocid>'`) and a policy such as
  `Allow dynamic-group dev-server-dg to read secret-bundles in tenancy`.
- On the server (Ansible installs the OCI CLI for arm64):
  `oci secrets secret-bundle get --secret-id <ocid> --auth instance_principal`
  `--query 'data."secret-bundle-content".content' --raw-output | base64 -d > /opt/kasyno/.env`
  then `chmod 600`.
- The deploy script runs this before `docker compose up`, so `.env` and the Firebase key
  survive every deploy and never touch git or an image.
- Check: delete `/opt/kasyno/.env` on the server, run the deploy, and the file reappears.
- Learn: instance principals, secret versions and rotation, why no password is stored.

### Step 6: Domain, HTTPS and hardening

- Caddyfile uses `dev.<domain>`; Caddy gets and renews the Let's Encrypt certificate.
- Add `dev.<domain>` under Firebase Console > Authentication > Settings > Authorized
  domains, or Google and Facebook sign-in popups fail.
- Remote Terraform state in an OCI Object Storage bucket (S3-compatible backend), so
  the state stops living only on one PC.
- Teammates: public keys added through an Ansible `authorized_key` task.
- Check: `https://dev.<domain>` loads, login works, `GET /api/health` answers.

## 5. Definition of done (from the issue)

- [ ] Frontend and backend images build for linux/arm64 and run on the server.
- [ ] A merge to `main` deploys automatically, but only after CI passes.
- [ ] `.env` and the Firebase key survive every deploy and are not in git or images.
- [ ] Services restart after a deploy and after a server reboot.
- [ ] `GET /api/health` and the web interface answer at a stable URL.
- [ ] Team members can log in to the server.
- [ ] A failed health check fails the pipeline and rolls back.

## 6. Rules that apply to every step

- Never commit secrets, Terraform state, `terraform.tfvars`, private keys, `.env` files,
  Firebase keys or auth tokens.
- Publish only ports 80 and 443; the backend stays on the internal Docker network.
- Run containers as non-root and tag images by commit SHA, never only `latest`.
- Builds run in CI, never on the server (2 OCPU and 12 GB must stay free).
- Review `terraform plan` output line by line before every `apply`.

## 7. Open items

- Domain name and DNS access: confirmed that you have a domain; the name is still needed.
- OCIR repository visibility: public (simpler) or private (more to learn).
- Your public key (`oci_dev.pub`) for the Ansible access task.
- Verify the free-tier figures in section 1.
