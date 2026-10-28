#!/bin/bash
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

"$(dirname "$0")/logo.sh"

echo -e "${CYAN}
---------------------------------Starting Debian Post Install Script---------------------------------
${NC}"

# Check if the script is being run as root
if [ "$(id -u)" -ne 0 ]; then
  echo -e "${RED}This script must be run as root.${NC}"
  exit 1
fi

# $USER is root under sudo, which made root the owner of /data and /configs
# and put root, not the owner, in the docker group.
TARGET_USER=${SUDO_USER:?Run this with sudo from the account that will run the stacks.}

# Run Update

echo -e "${GREEN}Executing Updates.${NC}"
# Update the package lists
apt update

# Upgrade installed packages
apt upgrade -y

# Perform a distribution upgrade (if available)
apt dist-upgrade -y

# Clean up unused packages and cached files
apt autoremove -y
apt autoclean
echo -e "${GREEN}Update Complete.${NC}"

# Install Docker
echo -e "${GREEN}Installing Docker.${NC}"

apt install -y \
  ca-certificates \
  curl \
  gnupg

# Create directory for keyrings
install -m 0755 -d /etc/apt/keyrings

# Download and install Docker GPG key
sudo curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc

# Set appropriate permissions for Docker GPG key
sudo chmod a+r /etc/apt/keyrings/docker.asc

# Add the repository to Apt sources:
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Update package lists
apt update

# Install Docker packages
apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

groupadd -f docker
usermod -aG docker "$TARGET_USER"

echo -e "${GREEN}Docker Installed.${NC}"


#Build media directory structure

    sudo mkdir -p /data/{torrents/{books,movies,music,tv},usenet/{incomplete,complete/{books,movies,music,tv}},media/{books,movies,music,tv,personal_tv,personal_movie}}
    sudo mkdir -p /configs/{audiobookshelf,backrest,bazarr,beszel_agent_data,beszel_server_data,BloTils_Data,filebrowser,flaresolverr,gluetun,homepage,jackett,jellyfin,myspeed,myspeed_no_vpn,prowlarr,qbit,radarr,recyclarr,seerr,sonarr,synthwave,uptime-kuma}
    sudo mkdir -p /jellyfin_cache
    sudo chown -R "$TARGET_USER:$TARGET_USER" /data
    sudo chmod -R a=,a+rX,u+w,g+w /data
    sudo chown -R "$TARGET_USER:$TARGET_USER" /configs
    sudo chmod -R a=,a+rX,u+w,g+w /configs
    sudo chown -R "$TARGET_USER:$TARGET_USER" /jellyfin_cache
    sudo chmod -R a=,a+rX,u+w,g+w /jellyfin_cache

echo -e "${GREEN}Media directory structure created!${NC}"


echo -e "${GREEN}Installing Inotify${NC}"

apt install -y inotify-tools

echo -e "${GREEN}Installing Inotify Succesfull.${NC}"

echo -e "${GREEN}Installing TailScale.${NC}"

curl -fsSL https://pkgs.tailscale.com/stable/debian/bookworm.noarmor.gpg | sudo tee /usr/share/keyrings/tailscale-archive-keyring.gpg >/dev/null
curl -fsSL https://pkgs.tailscale.com/stable/debian/bookworm.tailscale-keyring.list | sudo tee /etc/apt/sources.list.d/tailscale.list

sudo apt-get update
sudo apt-get install -y tailscale

echo -e "${GREEN}Installing TailScale Succesfull.${NC}"

sudo tailscale up


echo -e "${CYAN}
-------------------------------------------------Done-------------------------------------------------
${NC}"
