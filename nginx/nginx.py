import sys
from os import environ
from os.path import (dirname, join, abspath)
from subprocess import call

from clint.textui import colored
from dotenv import load_dotenv


BASE_DIR = dirname(dirname(abspath(__file__)))
load_dotenv(join(BASE_DIR, '.env'))
name = environ.get("SITE_FOLDER")
host = environ.get("HOST")
print(name)
print(host)


def install_nginx():
    call(["sudo", "apt", "install", "nginx", "-y"])


def reload_nginx():
    call(["service", "nginx", "reload"])


def create_dir():
    call(["mkdir", "/etc/nginx/upstreams/"])


def write_upstream(name):
    with open('/etc/nginx/upstreams/{}.conf'.format(name), 'w') as f:
        f.write('upstream {0} {{\n\tserver unix:///home/{0}/uwsgi.sock;\n}}'.format(name))
        print(colored.green("Wrote upstream config file for {}.".format(name)))


def write_main():
    cfg = "user www-data;\nworker_processes auto;\npid /run/nginx.pid;\n\nevents {\n\tworker_connections 10000;\n}\n\nworker_rlimit_nofile 22000;\n\nhttp {\n\topen_file_cache max=200000 inactive=20s;\n\topen_file_cache_valid 60s;\n\topen_file_cache_min_uses 2;\n\topen_file_cache_errors on;\n\n\taccess_log off;\n\n\tsendfile on;\n\ttcp_nopush on;\n\ttcp_nodelay on;\n\tkeepalive_timeout 10;\n\tkeepalive_requests 100000;\n\ttypes_hash_max_size 2048;\n\tserver_tokens off;\n\n\tserver_names_hash_bucket_size 64;\n\n\tinclude /etc/nginx/mime.types;\n\tdefault_type application/octet-stream;\n\n\taccess_log /var/log/nginx/access.log;\n\terror_log /var/log/nginx/error.log;\n\n\tgzip on;\n\tgzip_disable \"msie6\";\n\tgzip_min_length 10240;\n\tgzip_vary on;\n\tgzip_proxied expired no-cache no-store private auth;\n\tgzip_comp_level 6;\n\tgzip_buffers 16 8k;\n\tgzip_http_version 1.1;\n\tgzip_types text/plain text/css application/json application/x-javascript text/xml application/xml application/xml+rss text/javascript;\n\n\tclient_body_timeout 10;\n\tsend_timeout 2;\n\n\tlimit_conn_zone $binary_remote_addr zone=conn_limit_per_ip:10m;\n\tlimit_req_zone $binary_remote_addr zone=req_limit_per_ip:10m rate=5r/s;\n\tclient_body_buffer_size  128k;\n\n\tinclude /etc/nginx/sites-enabled/*;\n\tinclude /etc/nginx/upstreams/*;\n}"

    with open('/etc/nginx/nginx.conf', 'w') as f:
        f.write(cfg)
        print(colored.green("Wrote Nginx config file."))


def write_domain(name, host):
    cfg = "server {{\n\tlisten 80;\n\tlisten [::]:80;\n\tserver_name {0};\n\n\tlocation ^~ / {{\n\t\tallow all;\n\t\tauth_basic off;\n\t\talias /home/{1}/;\n\t}}\n\n\tlocation ^~ /.well-known {{\n\t\tallow all;\n\t\tauth_basic off;\n\t\talias /home/{1}/.well-known/;\n\t}}\n}}".format(host, name)

    with open('/etc/nginx/sites-enabled/{}.conf'.format(name), 'w') as f:
        f.write(cfg)
        print(colored.green("Wrote normal config file for {}.".format(host)))


def write_ssl_domain(name, host):
    cfg = """server {{\n\tlisten 443 ssl;\n\tlisten [::]:443;\n\tserver_name {0};\n\tssl on;\n\tcharset utf-8;\n\taccess_log /var/log/nginx/{0}_access.log combined;\n\terror_log /var/log/nginx/{0}_error.log error;\n\n\tssl_certificate /etc/letsencrypt/live/{0}/fullchain.pem;\n\tssl_certificate_key /etc/letsencrypt/live/{0}/privkey.pem;\n\n\tssl_session_timeout 1d;\n\tssl_session_cache shared:SSL:50m;\n\tssl_dhparam /etc/ssl/certs/dhparam.pem;\n\tssl_protocols TLSv1 TLSv1.1 TLSv1.2;\n\tssl_ciphers\n'ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-AES128-SHA256:ECDHE-RSA-AES128-SHA256:ECDHE-ECDSA-AES128-SHA:ECDHE-RSA-AES256-SHA384:ECDHE-RSA-AES128-SHA:ECDHE-ECDSA-AES256-SHA384:ECDHE-ECDSA-AES256-SHA:ECDHE-RSA-AES256-SHA:DHE-RSA-AES128-SHA256:DHE-RSA-AES128-SHA:DHE-RSA-AES256-SHA256:DHE-RSA-AES256-SHA:ECDHE-ECDSA-DES-CBC3-SHA:ECDHE-RSA-DES-CBC3-SHA:EDH-RSA-DES-CBC3-SHA:AES128-GCM-SHA256:AES256-GCM-SHA384:AES128-SHA256:AES256-SHA256:AES128-SHA:AES256-SHA:DES-CBC3-SHA:!DSS';\tssl_prefer_server_ciphers on;\n\tadd_header Strict-Transport-Security max-age=15768000;\n\tssl_stapling on;\n\tssl_stapling_verify on;\n\n\tlocation / {{\n\t\tuwsgi_pass  {1};\n\t\tuwsgi_read_timeout 300;\n\t\tinclude /etc/nginx/uwsgi_params;\n\t\tproxy_redirect off;\n\n\t\tproxy_cache_bypass $http_cache_control;\n\t\tadd_header X-Proxy-Cache $upstream_cache_status;\n\n\t\tproxy_set_header Host $http_host;\n\t\tproxy_set_header X-Real-IP $remote_addr;\n\t\tproxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;\n\t\tproxy_set_header X-Forwarded-Proto https;\n\t}}\n\n\tlocation ^~ /.well-known {{\n\t\tallow all;\n\t\tauth_basic off;\n\t\talias /home/{1}/.well-known/;\n\t}}\n\n\tlocation /uploads/  {{\n\t\tautoindex on;\n\t\texpires 30d;\n\t\tinclude /etc/nginx/mime.types;\n\t\talias /home/{1}/uploads/;\n\t\tadd_header Cache-Control "public";\n\t}}\n\n\tlocation /static/ {{\n\t\tautoindex on;\n\t\texpires 30d;\n\t\tinclude /etc/nginx/mime.types;\n\t\talias /home/{1}/static/;\n\t\tadd_header Cache-Control "public";\n\t}}\n\n\tlocation /favicon.ico {{\n\t\talias /home/{1}/uploads/web/favicon.ico;\n\t}}\n\n\tlocation /robots.txt {{\n\t\talias /home/{1}/static/robots.txt;\n\t}}\n}}\n\nserver {{\n\tlisten 80;\n\tserver_name {0};\n\trewrite ^(.*) https://{0}$1 permanent;\n}}\n\nserver {{\n\tlisten 80;\n\tserver_name www.{0};\n\trewrite ^ https://{0}$1 permanent;\n}}\n\nserver {{\n\tlisten 443;\n\tserver_name www.{0};\n\tssl on;\n\tssl_certificate /etc/letsencrypt/live/www.{0}/fullchain.pem;\n\tssl_certificate_key /etc/letsencrypt/live/www.{0}/privkey.pem;\n\trewrite ^ https://{0}$uri permanent;\n}}""".format(host, name)

    with open('/etc/nginx/sites-enabled/{}.conf'.format(name), 'w') as f:
        f.write(cfg)
        print(colored.green("Wrote SSL config file for {}.".format(host)))


install_nginx()
create_dir()
write_main()
write_upstream(name=name)
write_domain(name=name, host=host)
#TODO generate_certificates()
write_ssl_domain(name=name, host=host)
reload_nginx()
