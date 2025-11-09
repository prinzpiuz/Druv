```
                         ____
                        |  _ \ _ __ _   ___   __
                        | | | | '__| | | \ \ / /
                        | |_| | |  | |_| |\ V /
                        |____/|_|   \__,_| \_/
                         Setup Scripts For A HomelAB

```

Avaialable Services

***arr**
 - glutune - VPN service
 - qbittorrent- Torrent client
 - purgarr -
 - qbitmanage
 - radarr
 - sonarr
 - swurApp
 - readarr
 - flaresolverr
 - prowlarr
 - jackett
 - recyclarr
 - bazarr
 - unpackerr

**backup**
 - restic
 - backrest

**infra**
 - infludb
 - scrutiny
 - dockerproxy
 - homepage
 - myspeed

**media**
 - audiobookshelf
 - jellyfin
 - jellyseer

**public**



**tools**
 - qdarnt







### Debug

* **Container IP Address**
`docker inspect -f '{{range.NetworkSettings.Networks}}{{.IPAddress}}{{end}}' <Container Name>`

### Usefull Links

* [Inter Container Networking](https://github.com/qdm12/gluetun-wiki/blob/main/setup/inter-containers-networking.md)
