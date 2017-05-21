#!/usr/bin/env bash

# Ubuntu 17.04

# TODO
# nginx, uwsgi and monit configs should be present

SOURCE=""
PROJECT=""
DOMAIN=""

# UPDATES
sudo apt dist-upgrade  -y
sudo apt update  -y
sudo apt upgrade  -y

# FILES
mkdir /home/$PROJECT
mkdir /var/www/uwsgi
cp -R ~/$SOURCE/ /home/$PROJECT/

#TODO mysql install automation
# DEPS
sudo apt install libmysqlclient-dev gcc libpng-dev zlib1g-dev default-jdk curl memcached nginx htop monit mysql-server -y
sudo mysql_secure_installation
curl -O https://artifacts.elastic.co/downloads/elasticsearch/elasticsearch-5.4.0.deb
sudo dpkg -i elasticsearch-5.4.0.deb
sudo update-rc.d elasticsearch defaults 95 10
sudo /etc/init.d/elasticsearch start
sudo cp /home/$PROJECT/monitrc /etc/monit/monitrc

# NGINX, uWSGI, SSL
cd /usr/local/sbin
sudo wget https://dl.eff.org/certbot-auto
sudo chmod a+x /usr/local/sbin/certbot-auto
sudo openssl dhparam -out /etc/ssl/certs/dhparam.pem 4096
rm /etc/nginx/sites-available/default
rm /etc/nginx/sites-enabled/default
ln /home/$PROJECT/nginx.conf /etc/nginx/sites-enabled/nginx.conf
service nginx reload
./certbot-auto certonly -a webroot --agree-tos --renew-by-default --webroot-path=/home/$PROJECT -d $DOMAIN
./certbot-auto certonly -a webroot --agree-tos --renew-by-default --webroot-path=/home/$PROJECT -d www.$DOMAIN
rm /etc/nginx/sites-enabled/nginx.conf
ln /home/$PROJECT/nginx_ssl.conf /etc/nginx/sites-enabled/nginx_ssl.conf
service nginx reload
mkdir /etc/uwsgi
mkdir /etc/uwsgi/vassals
ln /home/$PROJECT/uwsgi.ini /etc/uwsgi/vassals/$PROJECT.ini

# FIREWALL
sudo ufw allow from 127.0.0.1 to any port 11211 # memcached
sudo ufw allow from 127.0.0.1 to any port 9200 # elastic
sudo ufw allow from 127.0.0.1 to any port 3306 # mysql
sudo ufw allow from 127.0.0.1 to any port 2812 # monit
sudo ufw enable

# PYTHON
wget https://repo.continuum.io/archive/Anaconda3-4.3.1-Linux-x86_64.sh -O /usr/local/anaconda.sh
bash /usr/local/anaconda.sh -b -p /usr/local/anaconda
rm /usr/local/anaconda.sh
echo 'export PATH="/usr/local/anaconda/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
conda update --all -y

# ENVIRONMENT (& uwsgi dep fixes)
conda create --name $PROJECT python -y
cp /usr/local/anaconda/lib/libpcre.so.1 /lib/x86_64-linux-gnu/libpcre.so.1
echo 'export LD_LIBRARY_PATH="/lib/x86_64-linux-gnu:$LD_LIBRARY_PATH"' >> ~/.bashrc
echo '/bin/bash /home/$PROJECT/uwsgi.sh &' >> ~/.bashrc
source ~/.bashrc
cd /home/$PROJECT
sudo chown -R www-data:www-data /home/$PROJECT
pip install -r requirements.txt
pip install --upgrade git+https://github.com/codelucas/newspaper
python -m nltk.downloader all
python manage.py makemigrations
python manage.py migrate

sudo cat << 'EOF' >> /etc/systemd/system/uwsgi.service
[Unit]
Description=uwSGI

[Service]
WorkingDirectory=/home/$PROJECT
User=root
Group=root
Type=forking
ExecStart=/bin/bash /home/$PROJECT/uwsgi.sh

[Install]
WantedBy=multi-user.target
EOF

service uwsgi start

crontab -l | { cat; echo "1 8 * * * source /usr/local/anaconda/bin/activate $PROJECT && /usr/local/anaconda/envs/$PROJECT/bin/python /home/$PROJECT/manage.py parser"; } | crontab -
crontab -l | { cat; echo "40 8 * * * source /usr/local/anaconda/bin/activate $PROJECT && /usr/local/anaconda/envs/$PROJECT/bin/python /home/$PROJECT/manage.py twitter"; } | crontab -
crontab -l | { cat; echo "50 8 * * * source /usr/local/anaconda/bin/activate $PROJECT && /usr/local/anaconda/envs/$PROJECT/bin/python /home/$PROJECT/manage.py update_index"; } | crontab -

touch /home/$PROJECT/logs/django.log
sudo chown www-data:www-data /home/$PROJECT/logs/django.log

monit reload
monit
