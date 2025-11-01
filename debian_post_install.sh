#!/bin/bash

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}
  ____
 |  _ \ _ __ _   ___   __
 | | | | '__| | | \ \ / /
 | |_| | |  | |_| |\ V /
 |____/|_|   \__,_| \_/

${NC}"

# Check if the script is being run as root
if [ "$(id -u)" -ne 0 ]; then
  echo -e "${RED}This script must be run as root.${NC}"
  exit 1
fi

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
apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin docker-compose

groupadd docker
usermod -aG docker $USER

echo -e "${GREEN}Docker Installed.${NC}"

# Install Portainer
echo -e "${GREEN}Installing Portainer.${NC}"
docker volume create portainer_data

docker run -d -p 9000:9000 --name portainer --restart=always -v /var/run/docker.sock:/var/run/docker.sock -v portainer_data:/data portainer/portainer-ce:latest

echo -e "${GREEN}Portainer Installed.${NC}"
echo -e "${GREEN}-------------------------------------------------Done-------------------------------------------------${NC}"


#Build media directory structure

    sudo mkdir -p /data/{torrents/{books,movies,music,tv},usenet/{incomplete,complete/{books,movies,music,tv}},media/{books,movies,music,tv,personal_tv,personal_movie}}
    sudo mkdir -p /configs/{qbit,qbit_manage,readarr,audiobookshelf,radarr,sonarr,prowlarr,jackett,bazarr,recyclarr,jellyseerr,jellyfin,emby,sabnzbd,homepage,scrutiny,myspeed,qbitrr/qBitManager,gluetun,tailscale/var/lib,tailscale/state}
    sudo mkdir -p /jellyfin_cache
    sudo mkdir -p /influxdb
    sudo chown -R $USER:$USER /data
    sudo chmod -R a=,a+rX,u+w,g+w /data
    sudo chown -R $USER:$USER /configs
    sudo chmod -R a=,a+rX,u+w,g+w /configs
    sudo chown -R $USER:$USER /jellyfin_cache
    sudo chmod -R a=,a+rX,u+w,g+w /jellyfin_cache
    sudo chown -R $USER:$USER /influxdb
    sudo chmod -R a=,a+rX,u+w,g+w /influxdb

echo -e "${GREEN}Media directory structure created!${NC}"

#create docker network called group
docker network create arr && echo -e "${GREEN}Docker network 'arr' created.${NC}"

echo -e "${GREEN}Installing FFProbe${NC}"

apt install unzip

cd /configs/qbitrr/qBitManager

wget https://github.com/ffbinaries/ffbinaries-prebuilt/releases/download/v6.1/ffprobe-6.1-linux-64.zip

unzip ffprobe-6.1-linux-64.zip

rm ffprobe-6.1-linux-64.zip

echo -e "${GREEN}Installing FFProbe Succesfull.${NC}"

echo -e "${GREEN}Installing Inotify${NC}"

apt install inotify-tools

echo -e "${GREEN}Installing Inotify Succesfull.${NC}"

echo -e "${GREEN}Installing TailScale.${NC}"

curl -fsSL https://pkgs.tailscale.com/stable/debian/bookworm.noarmor.gpg | sudo tee /usr/share/keyrings/tailscale-archive-keyring.gpg >/dev/null
curl -fsSL https://pkgs.tailscale.com/stable/debian/bookworm.tailscale-keyring.list | sudo tee /etc/apt/sources.list.d/tailscale.list

sudo apt-get update
sudo apt-get install tailscale

echo -e "${GREEN}Installing TailScale Succesfull.${NC}"

sudo tailscale up
