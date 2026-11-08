# Deployment runbook

How to run, update, back up and restore the backend in production. Works on
any Linux server with Docker (Oracle Cloud, AWS Lightsail, DigitalOcean...).
Commands run from the `deploy/` folder unless stated otherwise.

## What runs

| Service | What it is | Notes |
|---|---|---|
| `caddy` | HTTPS front door (ports 80/443) | Gets + renews the certificate for `SITE_ADDRESS` |
| `web` | Django API (gunicorn) | Not reachable from outside except through Caddy |
| `db` | PostgreSQL 18 | No published port. Data in the `pgdata` volume |
| `scheduler` | Daily jobs (`run_scheduler`) | 02:30 backup, 03:15 cleanup (India time) |
| `migrate` | One-off: migrations + cache table | Runs before `web`/`scheduler` start, then exits |

Volumes: `pgdata` (database), `backups` (local dumps), `caddy_data`
(certificates; losing it means re-issuing, and Let's Encrypt rate-limits that).

## 1. First-time server setup

Server-specific steps (creating the VM, firewall, DNS) are done in Phase 8b.
Once you have an Ubuntu server with SSH access:

```bash
# Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER        # log out and back in afterwards

# Basic hardening
sudo apt-get install -y ufw fail2ban unattended-upgrades
sudo ufw allow OpenSSH && sudo ufw allow 80 && sudo ufw allow 443 && sudo ufw allow 443/udp
sudo ufw enable
# In /etc/ssh/sshd_config: PasswordAuthentication no, PermitRootLogin no; then:
sudo systemctl restart ssh

# Code
git clone git@github.com:Het-Shukla-13/SPT_Tuition_Management_System.git
cd SPT_Tuition_Management_System && git checkout main
```

Note: Docker publishes ports past `ufw`; that's fine here because only Caddy
publishes ports (80/443). Never add `ports:` to `db` or `web`.

## 2. Configure

```bash
cd deploy
cp .env.example .env
nano .env     # fill in everything; the comments explain each value
chmod 600 .env
```

Must-haves: `SITE_ADDRESS` and `DJANGO_ALLOWED_HOSTS` (the public hostname),
`DJANGO_SECRET_KEY`, `POSTGRES_PASSWORD` (letters/digits only), email
settings, `CORS_ALLOWED_ORIGINS` (the frontend URL). The DNS name must already
point at the server, or Caddy can't get a certificate.

The app refuses to start with a weak secret key, no allowed hosts, or a
development email/SMS backend: check `docker compose logs web` if it won't start.

## 3. Start / update

```bash
git pull
docker compose up -d --build
docker compose ps            # db, web healthy; scheduler, caddy up; migrate exited (0)
curl https://<SITE_ADDRESS>/api/v1/health/ready/
```

Create the owner account once:

```bash
docker compose exec web python manage.py createsuperuser
```

## 4. Logs

```bash
docker compose logs -f web           # API requests and errors (JSON lines)
docker compose logs scheduler        # backup / cleanup results
docker compose logs caddy            # certificate issues
```

Logs rotate automatically (5 x 10 MB per service).

## 5. Backups

- Automatic: every night at `BACKUP_TIME`. The newest `BACKUP_KEEP` dumps
  are kept in the `backups` volume and (if Drive is connected) in the private
  Google Drive folder, so losing the server doesn't lose the backups.
- Manual, before any risky change:

```bash
docker compose exec scheduler python manage.py backup_database
docker compose exec scheduler python manage.py restore_database --list
```

- Copy a dump off the server:

```bash
docker compose cp scheduler:/app/backups/<file>.dump .
```

## 6. Restore (disaster recovery)

Replaces ALL data with the backup. The restore is one transaction: if it fails
halfway, nothing changes.

```bash
docker compose stop web scheduler                     # nobody writes meanwhile
docker compose run --rm web python manage.py restore_database --list
docker compose run --rm web python manage.py restore_database \
    /app/backups/db-backup-YYYYMMDD-HHMMSS.dump --confirm <POSTGRES_DB>
#   or from Drive:  --drive gdrive/<id> --confirm <POSTGRES_DB>
docker compose up -d
```

New server from scratch: steps 1-3, then this section with a dump from Drive.

**Test a restore every few months** on your laptop (`docker compose up` with
a trial `.env`, restore the latest Drive backup, log in). An untested backup
isn't a backup.

## 7. Rollback a bad release

```bash
git log --oneline -5
git checkout <previous good commit>
docker compose up -d --build
```

If the bad release ran a migration that must be undone, restore the backup
taken before the release (section 6) instead.

## 8. Rotating secrets

- `DJANGO_SECRET_KEY` / `JWT_SIGNING_KEY`: change in `.env`, then
  `docker compose up -d`. Everyone is logged out (tokens become invalid).
- `POSTGRES_PASSWORD`: change it inside PostgreSQL first
  (`docker compose exec db psql -U tuition -c "ALTER USER tuition PASSWORD '...'"`),
  then in `.env`, then `docker compose up -d`.
- Email / Google credentials: change in `.env`, `docker compose up -d`.

## 9. Trying the production stack locally

```bash
cd deploy
cp .env.example .env      # set DJANGO_SECRET_KEY, POSTGRES_PASSWORD,
                          # EMAIL_HOST_USER (any value), HTTP_PORT=8080, HTTPS_PORT=8443
docker compose up -d --build
curl -k https://localhost:8443/api/v1/health/ready/
docker compose down       # add -v to also delete the trial database
```

`SITE_ADDRESS=localhost` makes Caddy use its own local certificate, so
browsers warn and curl needs `-k`. That's expected locally.
