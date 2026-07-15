sudo apt update
sudo apt install openvpn -y
sudo cp /home/pi/13.hirubic_sonhathangbinh.ovpn /etc/openvpn/client/
sudo mv /etc/openvpn/client/13.hirubic_sonhathangbinh.ovpn /etc/openvpn/client/client.conf
sudo openvpn --config /etc/openvpn/client/client.conf
sudo systemctl enable openvpn-client@client
sudo systemctl start openvpn-client@client
systemctl status openvpn-client@client
ip a
ip route
docker compose --build -d
sudo apt install docker-compose-plugin -y
cd ~
sudo apt install docker-compose-plugin -y
sudo apt install docker-compose -y
cd DATALOGGER_nosmart/
docker compose --build -d
cd ~
sudo apt update && sudo apt install -y git curl && curl -fsSL https://get.docker.com | sh && sudo usermod -aG docker $USER && newgrp docker
sudo apt remove docker.io -y
sudo apt update && sudo apt install -y git curl && curl -fsSL https://get.docker.com | sh && sudo usermod -aG docker $USER && newgrp docker
sudo apt remove docker.io -y
sudo apt autoremove
sudo apt update && sudo apt install -y git curl && curl -fsSL https://get.docker.com | sh && sudo usermod -aG docker $USER && newgrp docker
sudo dpkg --configure -a
sudo apt --fix-broken install -y
sudo apt update
sudo apt install docker-ce docker-ce-cli containerd.io docker-compose-plugin docker-buildx-plugin -y
sudo apt purge docker-ce docker-ce-cli containerd.io -y
sudo rm -rf /var/lib/docker
curl -fsSL https://get.docker.com | sh
docker ps
systemctl status docker
sudo systemctl start docker
systemctl status docker
cd DATALOGGER_nosmart/
docker compose up --build -d
docker ps
sudo dpkg --configure -a
docker version
docker compose version
sudo reboot
sudo apt update && sudo apt install -y git docker.io && sudo usermod -aG docker $USER && newgrp docker
sudo systemctl status docker
git clone -b test https://github.com/xuanthai2110/DATALOGGER_nosmart.git
cd DATALOGGER_nosmart/
cp .env.example .env
nano .env
docker compose up --build -d
docker-compose up --build -d
docker compose up -d --build
docker ps
docker compose up -d --build
sudo usermod -aG docker pi
newgrp docker
docker ps
docker pause datalogger_uploader
docker pause datalogger_polling
docker pause datalogger_polling
docker uppause datalogger_uploader
docker unpause datalogger_uploader
cd DATALOGGER_nosmart/
git pull
docker compose up --build -d
cd DATALOGGER_nosmart/
docker logs -f datalogger_polling
docker logs -f datalogger_uploader
docker logs -f datalogger_polling
cd DATALOGGER_nosmart/
git pull
docker compose up --build -d
docker logs -f datalogger_polling
cd DATALOGGER_nosmart/
git pull
docker compose up --build -d 
docker logs -f datalogger_polling
docker logs -f datalogger_uploader
cd DATALOGGER_nosmart/
git pull
docker compose up --build -d 
git pull
docker logs -f datalogger_uploader
cd DATALOGGER_nosmart/
git pull
cd /
cd ..
cd ./
cd ..
ls
cd ./etc/ipenvpn/client/client.ovpn
cd ./etc/openvpn/client/client.ovpn
cd etc
ls
cd opem
n
cd openvpn/client/cliemt
cd openvpn/client/
ls
nano c;
nano client.conf 
sudo nano client.conf 
sudo systemctl restart openvpn-client@client
sudo nano /etc/openvpn/client/client.conf 
sudo systemctl restart openvpn-client@client
sudo systemctl enable openvpn-client@client
sudo nano /usr/local/bin/vpn_monitor.sh
sudo chmod +x /usr/local/bin/vpn_monitor.sh
sudo nano /etc/systemd/system/vpn-monitor.service
sudo nano /etc/systemd/system/vpn-monitor.timer
sudo systemctl daemon-reload
sudo systemctl enable --now vpn-monitor.timer
systemctl list-timers
journalctl -fu vpn-monitor.service
journalctl -u openvpn-client@client -f
cd DATALOGGER_nosmart/
git pull
docker compose up --build -d
docker logs -f datalogger_polling
docker pause datalogger_polling
docker pause datalogger_uploader
docker pause datalogger_evn
docker ps
docker pause datalogger_web
git pull -b test
docker pause datalogger_web
ls -l /home/pi/DATALOGGER_nosmart/backend/db_manager/data/
sudo chown -R pi:pi /home/pi/DATALOGGER_nosmart/backend/db_manager/data/
docker unpause datalogger_web
docker unpause datalogger_polling
docker unpause datalogger_uploader
docker logs -f datalogger_polling
docker compose --build -d
docker compose up --build -d
docker unpause datalogger_polling
docker ps
docker compose up --build -d
docker logs -f datalogger_polling
cd DATALOGGER_nosmart/
docker pause datalogger_polling
sudo shutdown
cd DATALOGGER_nosmart/
docker logs -f datalogger_polling
docker logs -f datalogger_uploader
cd ..
sudo nano /etc/openvpn/client/client.conf 
cd DATALOGGER_nosmart/
git pull
sudo nano /etc/openvpn/client/client.conf 
git pull
ping github.com
curl -I https://github.com
ip route
sudo nano /etc/openvpn/client/client.conf
sudo nano /usr/local/bin/vpn_monitor.sh
sudo systemctl restart openvpn-client@client
git pull
docker compose up --build -d
cd DATALOGGER_nosmart/
git pull
docker compose up --build -d
cd DATALOGGER_nosmart/
git pull
nano .env.example
nano .env
docker compose up --build -d
cd DATALOGGER_nosmart/
got pull
git pull
nano .env
cd DATALOGGER_nosmart/
cd backend/db_manager/data/
docker logs -f datalogger_polling
docker ps
cd DATALOGGER_nosmart/
docker compose up -d
cd DATALOGGER_nosmart/
docker compose up -d
docker logs -f datalogger_polling
cd DATALOGGER_nosmart/
docker logs -f datalogger_uploader
cd DATALOGGER_nosmart/
docker compose up --build -d
docker logs -f datalogger_polling
docker logs -f datalogger_uploader
docker compose up --build -d
docker logs -f datalogger_polling
docker logs -f datalogger_uploader
docker compose build base
docker pause datalogger_uploader
docker compose up --build -d
docker compose down
sudo systemctl restart containerd
sudo systemctl restart docker
docker ps
docker compose down
df -h
sudo journalctl -u containerd -n 40 --no-pager
sudo systemctl stop docker
sudo systemctl stop containerd
sudo mv /var/lib/containerd/io.containerd.metadata.v1.bolt /var/lib/containerd/io.containerd.metadata.v1.bolt.bak
sudo systemctl start containerd
sudo systemctl start docker
sudo systemctl start containerd
sudo systemctl start docker
docker compose up -d
sudo reboot
docker ps
ifconfig
ping 10.8.0.1
ip addr
sudo ss -tlnp | grep :22
cd DATALOGGER_nosmart/
docker compose up --build -d
docker builder prune -f
docker compose up --build --no-cache -d
docker compose up --build --nocache -d
docker compose up --build --no-cache -d
docker compose build --no-cache
docker compose up -d
docker logs -f datalogger_pollig
docker logs -f datalogger_polling
nano .env
docker logs -f datalogger_uploader
nano .env
docker compose up -d
nano .env
docker compose up -d
docker logs -f datalogger_uploader
docker logs -f datalogger_polling
docker compose build --no-cache
sudo systemctl restart docker
docker compose build web --no-cache
docker compose build
docker compose up -d
docker logs -f datalogger_polling
docker compose build
docker compose up -d
docker logs -f datalogger_polling
docker logs -f datalogger_web
docker logs -f datalogger_polling
docker logs -f datalogger_web
docker pause datalogger_polling
docker logs -f datalogger_web
docker r unpause datalogger_polling
docker unpause datalogger_polling
docker logs -f datalogger_polling
docker logs -f datalogger_uploader
docker logs -f datalogger_polling
