# VPN (gluetun + AirVPN)

qBittorrent, slskd, music-sync (Sockseek) and the other download apps run in gluetun's network namespace. All their internet traffic goes through the VPN. If the tunnel goes down, gluetun's firewall blocks their traffic.

## Why forwarded ports matter

A **forwarded port** is a port on the VPN server that sends incoming connections through the tunnel to you. Without one, nobody can connect to you; you can only connect out.

- **Soulseek (slskd, Sockseek).** When you search, each peer with a match connects to you to send its results. If your port is closed, only peers with an open port can reach you. Results from all the others are lost. This was the cause of the poor search results with Mullvad, which removed port forwarding in 2023.
- **BitTorrent (qBittorrent).** With a closed port you can only reach peers that have an open port. Downloads of rare torrents are slower, and seeding is weak.

AirVPN gives fixed forwarded ports. Each app gets its own port, and the app must listen on that exact port.

| App | Variable in `arr/.env` | Where the app reads it |
|---|---|---|
| qBittorrent | `AIRVPN_PORT_QBITTORRENT` | Set by hand in the qBittorrent web UI. |
| slskd | `AIRVPN_PORT_SLSKD` | `SLSKD_SLSK_LISTEN_PORT` in the compose file. |
| music-sync (Sockseek) | `AIRVPN_PORT_SOCKSEEK` | `SOCKSEEK_LISTEN_PORT` in the compose file. |

gluetun opens all three on the tunnel with `FIREWALL_VPN_INPUT_PORTS`.

## Set up AirVPN

1. **Reserve 3 ports.** AirVPN Client Area > Ports. Leave "local port" empty, so the local port is the same as the public one. If the page has a device setting, choose the device of the WireGuard key from the next step, or all devices.
2. **Make a WireGuard config.** Client Area > Config Generator: Linux, WireGuard, IPv4 only, one Singapore server or the whole country. From the file, copy:
   - `PrivateKey` to `WIREGUARD_PRIVATE_KEY`
   - `PresharedKey` to `WIREGUARD_PRESHARED_KEY`
   - the IPv4 address in `Address` to `WIREGUARD_ADDRESSES`, for example `10.x.x.x/32`. Leave out the IPv6 address: IPv6 is off in gluetun's namespace.
3. **Edit `arr/.env`:**

   ```bash
   VPN_SERVICE_PROVIDER=airvpn
   VPN_TYPE=wireguard
   WIREGUARD_PRIVATE_KEY=...
   WIREGUARD_PRESHARED_KEY=...
   WIREGUARD_ADDRESSES=10.x.x.x/32
   SERVER_COUNTRIES=Singapore
   SERVER_CITIES=
   AIRVPN_PORT_QBITTORRENT=<port 1>
   AIRVPN_PORT_SLSKD=<port 2>
   AIRVPN_PORT_SOCKSEEK=<port 3>
   ```

   `SERVER_CITIES` must be empty or an AirVPN city. A Mullvad city name makes gluetun fail to start. AirVPN servers near India: Singapore, Tokyo, Taipei.
4. **Recreate the stack:** `./down_and_up.sh`, or `cd arr && docker compose up -d --build`. Every app in gluetun's namespace must be recreated when gluetun is.
5. **qBittorrent** web UI > Tools > Options:
   - Connection > Port used for incoming connections: `<port 1>`. Untick "Use different port on each startup" and "Use UPnP / NAT-PMP port forwarding".
   - Advanced > Network interface: `tun0`. qBittorrent then never sends traffic outside the tunnel, even if gluetun's firewall rules change.
6. **Check.**
   - `docker logs gluetun | grep -i "public ip"`: the IP is an AirVPN one.
   - Client Area > Ports: the test button for each port shows it is open while the app runs.
   - qBittorrent's status bar: the connection icon is green.
   - slskd web UI: searches return many more results.

## Notes

- One WireGuard key is one AirVPN device. Do not use the same key on a laptop at the same time.
- AirVPN's DNS is not used. gluetun has its own DNS over TLS.
