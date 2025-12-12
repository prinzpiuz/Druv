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

### Using the Same Server Setup

If you want to set up your server environment to match this repo exactly
* The setup script is built for Debian 12 (and compatible Debian-based systems).
* Run the provided post-install script (it must be a Debian derivative)

    `./debian_post_install.sh`

---

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
| [Readarr](https://readarr.com/) | Book management | /configs |
| [Prowlarr](https://wiki.servarr.com/prowlarr) | Indexer manager | /configs |
| [Bazarr](https://www.bazarr.media/) | Subtitle automation | /configs |
| [Jackett](https://github.com/Jackett/Jackett) | Indexer proxy | /configs |
| [Recyclarr](https://recyclarr.dev/) | Config sync for *Arr apps | /configs |
| [Unpackerr](https://github.com/Unpackerr/unpackerr) | Unpack Downloaded Files |/configs |
| [Flaresolverr](https://github.com/FlareSolverr/FlareSolverr) | Captcha solver | /configs |
| [SwurApp](https://github.com/OwlCaribou/swurApp) | Companion utility | /configs |
| [Synthwave](https://github.com/PranavVerma-droid/Synthwave) | Music Downloader| /configs|

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
| [Jellyseerr](https://github.com/Fallenbagel/jellyseerr) | Request manager for Jellyfin | /configs |
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

---

#### 🛠️ Tools Stack

* [Tools Compose File](tools/docker-compose.yml)
* [env File](tools/.env.sample)

| Name | Description | Config |
|------|-------------|--------|
| [Qdarnt](https://qdrant.tech/) | Vector DB |  /configs |

---

#### Never Down Stack

* [Never Down Compose File](never-down.yml)
* [env File](.env.sample)

| Name | Description | Config |
|------|-------------|--------|
| [Uptime-Kuma](https://uptimekuma.org/) | Uptime Monitor | /configs |
| [Beszel](https://beszel.dev/) | System Monitoring | /configs |
| [Quantum File Browser](https://filebrowserquantum.com/) | File Browser | /configs |

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
