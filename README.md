```
          ____
         |  _ \ _ __ _   ___  __
         | | | | '__| | | \ \ / /
         | |_| | |  | |_| |\ V /
         |____/|_|   \__,_| \_/

          Setup Scripts for a HomeLab
```
---
### How to Run These Services

* Create Environment Files:
   In every service’s folder, copy the example environment file to a new .env file

* Update the .env files and other configs for each service based on your requirements.

* Run the main script to bring all your services down and up smoothly:

    `./down_and_up.sh`

### Image Versions

Every image is pinned to an exact tag. The tags live in [version.env](version.env) for the homelab stacks and in [public/version.env](public/version.env) for the public stack. Compose files reference them, for example:

```yaml
image: ghcr.io/hotio/radarr:${RADARR_VERSION:?set in version.env}
```

Unlike `.env`, these files are committed, because they hold versions and not secrets.

Compose does not read `version.env` by itself. It auto-loads only `.env` from the project directory, so the version file has to be passed in:

```bash
export COMPOSE_ENV_FILES=.env,version.env   # then any docker compose command works
docker compose config                       # check the rendered tags
```

`down_and_up.sh` exports this for you, and the deploy workflow does the same on the VPS before `docker compose pull`. Set it in your shell for manual compose commands. Two notes:

* A `--env-file` flag overrides `COMPOSE_ENV_FILES`, so do not mix them.
* `COMPOSE_ENV_FILES` has to come from the shell. Writing it inside `.env` does nothing.

If a version variable is missing, compose stops with an error such as `required variable RADARR_VERSION is missing a value` instead of starting an unpinned container.

To upgrade a service:

1. Change its value in `version.env`.
2. Run `docker compose up -d <service>`, or `./down_and_up.sh` for everything.

The new tag is not in the local image store, so compose pulls it. No `pull_policy: always` is needed, and the compose files do not set it: with fixed tags that setting only adds a registry round trip per image on every restart.

### Using the Same Server Setup

If you want to set up your server environment to match this repo exactly
* The setup script is built for Debian 12 (and compatible Debian-based systems).
* Run the provided post-install script (it must be a Debian derivative)

    `./debian_post_install.sh`

---

### Public Services

From my homelab, I have made a few services available to the public under [prinzpiuz.in](https://prinzpiuz.in). Feel free to use them if you find them useful.

 - https://blotils.prinzpiuz.in - Blog Utilites
 - https://pdftools.prinzpiuz.in - PDF Tools, that run in your browser


### Stack

#### 📦 Arr Stack

* [Arr Compose File](arr/docker-compose.yml)
* [env File](arr/.env.sample)

| Name | Description | Config |
|------|-------------|--------|
| [Gluetun](https://github.com/qdm12/gluetun) | VPN service for containers | /configs|
| [qBittorrent](https://www.qbittorrent.org/) | Torrent client | /configs |
| [Radarr](https://radarr.video/) | Movies automation | /configs |
| [Sonarr](https://sonarr.tv/) | TV automation | /configs |
| [Prowlarr](https://wiki.servarr.com/prowlarr) | Indexer manager | /configs |
| [Bazarr](https://www.bazarr.media/) | Subtitle automation | /configs |
| [Jackett](https://github.com/Jackett/Jackett) | Indexer proxy | /configs |
| [Recyclarr](https://recyclarr.dev/) | Config sync for *Arr apps | /configs |
| [Unpackerr](https://github.com/Unpackerr/unpackerr) | Unpack Downloaded Files |/configs |
| [Flaresolverr](https://github.com/FlareSolverr/FlareSolverr) | Captcha solver | /configs |
| [SwurApp](https://github.com/OwlCaribou/swurApp) | Companion utility | /configs |
| [Synthwave](https://github.com/PranavVerma-droid/Synthwave) | Music Downloader| /configs|

---

#### 🤖 Automation Stack

* [Automation Compose File](automation/docker-compose.yml)
* [env File](automation/.env.sample)
* [My Workflows](automation/workflows)

| Name | Description | Workflows |
|------|-------------|--------|
| [n8n](https://github.com/n8n-io/n8n) | Work Flow Automations |  [workflows](automation/workflows) |


---

#### 🔒 Backup Stack

* [Backup Compose File](backup/docker-compose.yml)
* [env File](backup/.env.sample)

| Name | Description | Config |
|------|-------------|--------|
| [Backrest](https://github.com/garethgeorge/backrest) | Simple backup management |  /configs |

---

#### 🖥️ Infrastructure Stack

* [Infra Compose File](infra/docker-compose.yml)
* [env File](infra/.env.sample)

| Name | Description | Config |
|------|-------------|--------|
| [Docker Proxy](https://github.com/Tecnativa/docker-socket-proxy) | Secure Docker socket proxy |  /configs |
| [Homepage](https://github.com/gethomepage/homepage) | Dashboard for homelab |  [configs](infra/configs/homepage)|
| [MySpeed](https://github.com/gnmyt/myspeed) | Self-hosted speed test |  /configs |


---

#### 🎬 Media Stack

* [Media Compose File](media/docker-compose.yml)
* [env File](media/.env.sample)

| Name | Description | Config |
|------|-------------|--------|
| [Audiobookshelf](https://www.audiobookshelf.org/) | Audiobooks streaming server | /configs |
| [Jellyfin](https://jellyfin.org/) | Media server | /configs |
| Jelly Music App | Music player for Jellyfin | none |
| [Seerr](https://github.com/seerr-team/seerr) | Request manager for Jellyfin | /configs |

---

#### 🌐 Public

You can fork this repository and customize the Caddy configuration by editing the [Caddy Template File](public/Caddyfile.template).
After updating, you can reuse the deployment scripts located in the action files to deploy your changes.

The public services are reverse proxied using [Tailscale](https://tailscale.com/), which allows secure access to only the services you want exposed to the public internet.
Use the provided Public Compose File to deploy public services.
Configure environment variables by copying and editing the env File as needed.


* [Public Compose File](public/docker-compose.yml)
* [env File](public/.env.sample)

| Name | Description | Config |
|------|-------------|--------|
| [Caddy](https://caddyserver.com/) | Reverse proxy & web server |  /configs |
| [Beszel Agent](https://beszel.dev/) | System Monitoring agent for the VPS | /configs |

---

#### 🛠️ Tools Stack

* [Tools Compose File](tools/docker-compose.yml)
* [env File](tools/.env.sample)

| Name | Description | Config |
|------|-------------|--------|
| [Qdarnt](https://qdrant.tech/) | Vector DB |  /configs |
| [BentoPDF](https://github.com/alam00000/bentopdf) | PDF Tools |  /configs |
| [dawarich](https://dawarich.app/) | Timeline Tracker |  /configs |
| [BloTils](https://github.com/prinzpiuz/BloTils) | Blog Utilities |  /configs |
| [SnapOtter](https://github.com/snapotter-hq/snapotter) | Image Tools |  /configs |
| [PriceStalker](https://github.com/mikeknight85/PriceStalker) | Price Tracker |  /configs |



---

#### Never Down Stack

* [Never Down Compose File](never-down.yml)
* [env File](.env.sample)

| Name | Description | Config |
|------|-------------|--------|
| [Uptime-Kuma](https://uptimekuma.org/) | Uptime Monitor | /configs |
| [Beszel](https://beszel.dev/) | System Monitoring | /configs |
| [Quantum File Browser](https://filebrowserquantum.com/) | File Browser | /configs |
| [Couch DB](https://couchdb.apache.org/) for [LiveSync](https://github.com/vrtmrz/obsidian-livesync) | Obsidian Plugin | /configs |

### Debug

Get container IP address:
```
docker inspect -f '{{range.NetworkSettings.Networks}}{{.IPAddress}}{{end}}' <container_name>
```

---

#### Useful Links
- [More Applications To SelfHost](https://selfh.st/)
- [Media Server Setup](https://wiki.servarr.com/)
- [TRaSH-Guides](https://trash-guides.info/)
- [Another Setup Guide](https://wiki.hydrology.cc/en/InstallInstructions)
- [Inter-Container Networking with Gluetun](https://github.com/qdm12/gluetun-wiki/blob/main/setup/inter-containers-networking.md)
