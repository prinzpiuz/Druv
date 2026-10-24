# AGENTS.md

Instructions for coding agents working in this repository.

## What this repo is

Docker Compose setup for a personal homelab. The repo is public on GitHub.

Two hosts run it:

| Host | Role | Path on host | How it gets changes |
|---|---|---|---|
| Homelab server | Runs every stack except `public/` | `/home/druv/druv_setup` | Owner pulls and runs `./down_and_up.sh` |
| Hetzner VPS | Runs `public/` (Caddy, Beszel agent) | `~/Druv` | `.github/workflows/deploy.yml` on push to `main` |

Traffic path for public services: internet → Caddy on the VPS → Tailscale → homelab service.
Caddy routes by hostname on port 443. Do not add a public port per service.

## Layout

- `docker-compose.yml`: root project. It `include:`s `arr/`, `automation/`, `infra/`, `media/`, `backup/`, `tools/`.
- `tools/docker-compose.yml` includes `tools/dawarich/`, `tools/blotils/`, `tools/priceStalker/`.
- `never-down.yml`: separate project (Uptime Kuma, Beszel hub, Filebrowser, CouchDB). It restarts on its own.
- `public/`: separate project on the VPS. `Caddyfile.template` is the source; `start_caddy.sh` renders it with `envsubst`.
- `version.env` and `public/version.env`: pinned image tags. Committed.
- `*/.env.sample`: templates for the real `.env` files. Real `.env` files are gitignored.
- `down_and_up.sh`: the owner's deploy script for the homelab.
- `scripts/validate-compose.sh`: renders all stacks without touching a server.

## Verify every change

Run these before you say a change is done:

```bash
./scripts/validate-compose.sh     # all three stacks render
pre-commit run --all-files        # whitespace, EOF, private keys, yamlfmt
```

If you changed `public/Caddyfile.template`, CI validates it with Caddy. You can run the same check locally with the commands in `.github/workflows/caddy.yml`.

## Commands you must not run

This repo controls a live server. Do not run these unless the owner asks in this session:

- `./down_and_up.sh`, `docker compose up|down|restart|pull`, `docker system prune`
- `docker network rm`, `docker volume rm`, anything under `/configs` or `/data`
- `git push` to `main`, or any push. A push to `main` creates a release, and a push that touches `public/**` deploys to the VPS.

Read-only commands are fine: `docker compose config`, `docker ps`, `docker logs`, `docker inspect`.

## Secrets

- Never commit a `.env` file, a key, a token, or a password. The repo is public.
- Never print the contents of a real `.env` file in output or in a commit.
- A new secret goes in the stack's `.env` on the server. Add the variable name with an empty or dummy value to that stack's `.env.sample`.
- The Tailscale hostname and the `172.18.0.0/24` subnet are not secrets.

## Image versions

Every image is pinned. Never use `latest`, a floating major tag, or `pull_policy: always`.

- Image line format: `image: org/name:${NAME_VERSION:?set in version.env}`
- An image that publishes no version tags is pinned by digest: `image: org/name@${NAME_DIGEST:?set in version.env}`
- Put the variable in `version.env` under the section for its stack. Public stack images go in `public/version.env`.
- Compose does not read `version.env` by itself. `COMPOSE_ENV_FILES=.env,version.env` must be exported in the shell.
- Do not add `--env-file` to compose commands. It overrides `COMPOSE_ENV_FILES`.
- Before you bump a version, read the release notes. Say in the PR if the release is a major version or needs a migration.

Deliberate pins. Do not change these without the owner:

- `QBITTORRENT_VERSION=release-5.0.4`: version 5.2.0 exited at startup on this host.
- `GLUETUN_VERSION`: newest release tag, because the image's `latest` is a rolling build.
- Beszel hub (`BESZEL_VERSION`) and agents (`BESZEL_AGENT_VERSION`, in both version files) must stay on the same release.

## Adding a service

1. Put it in the stack whose purpose fits. Use the existing `name:` and `include:` structure.
2. Copy the shape of a nearby service: `container_name`, `restart: unless-stopped`, `env_file`, `networks: - ${NETWORK_NAME}`.
3. Pin the image as described above.
4. Config goes in `/configs/<service>`. App data goes in `/data/<service>`.
5. Check the host port is free. Search every compose file for it, including the `ports:` list on `gluetun`.
6. Add its variables to the stack's `.env.sample`.
7. Add a row to the stack's table in `README.md`.
8. Add an entry to `infra/configs/homepage/services.yaml` if the owner wants it on the dashboard.
9. Run the verify commands.

Backups: Backrest mounts only `/configs` (read-only). Anything under `/data` is not backed up unless the owner adds the path to Backrest. Say so in the PR when a new service keeps state in `/data`.

## Networking rules

- All homelab stacks share the external network `${NETWORK_NAME}` (subnet `172.18.0.0/24`). It is created by `down_and_up.sh --all`, not by compose.
- Some services have fixed IPs set from `.env` (`*_IPV4_ADDR`). Other services reach them by those IPs.
- qBittorrent, Prowlarr, Jackett, Seerr and MySpeed use `network_mode: service:gluetun`. Their ports are published on the `gluetun` service, not on their own. They stop when the VPN tunnel is down.
- `down_and_up.sh` starts `gluetun` first and waits for it to be healthy. Keep that order if you change the script.

## Exposing a service publicly

1. Add a site block to `public/Caddyfile.template`:
   ```
   name.prinzpiuz.in {
   	import proxy ${REVERSE_PROXY_URL}:<homelab-port>
   }
   ```
2. The `(proxy)` snippet already sets security headers, strips server banners and uses the Cloudflare DNS challenge. Do not copy those lines into the site block.
3. Use only `$VAR` or `${VAR}` for environment variables. Never use Caddy's `{$VAR}` form: `envsubst` consumes it before Caddy sees it.
4. Tell the owner to add the DNS record in Cloudflare. That step is outside the repo.
5. A service with an admin UI or no login needs a reason to be public. Ask first.

## Host limits

- Homelab: Intel i3-2100 (Sandy Bridge, no AVX2), about 10 GB RAM, no discrete GPU, Debian 12.
  - Do not add services that need local LLM inference or GPU transcoding. Flag the cost of anything heavy.
  - The iGPU cannot hardware-decode HEVC, so Jellyfin cannot transcode 4K HEVC. Playback depends on direct play.
  - The main TV plays HEVC, AV1 and H.264 at 4K with SDR, HDR10 and HLG. It cannot play Dolby Vision. Recyclarr and *arr profiles reject Dolby Vision without an HDR10 fallback. Keep that.
- VPS: Hetzner, 4 GB RAM. Its IP is a datacenter IP, so scrapers there get blocked more often.

## Style

- YAML is formatted by `yamlfmt` through pre-commit. Do not hand-reformat unrelated lines.
- Shell scripts: `bash`, `set -euo pipefail` for new scripts, and the `success_log`, `warning_log`, `error_log` helpers in `down_and_up.sh`.
- Add a comment only when the reason is not obvious from the code. Existing comments explain past incidents. Keep them.
- `10-livesync.ini` is owned by the CouchDB container's user. Pre-commit skips it. Do not reformat it.
- `logo.sh` `VERSION` is set by the release workflow. Do not edit it.

## Commits and pull requests

- Work on a branch. Open a PR into `main`.
- Commit messages use Conventional Commits: `feat:`, `fix:`, `chore:`, `docs:`. The release workflow reads them to choose the next version.
- One logical change per commit.
- In the PR description, list what the owner must do on the server: new `.env` values, new directories, DNS records, data migrations.
