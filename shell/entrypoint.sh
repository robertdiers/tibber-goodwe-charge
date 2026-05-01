printenv | grep -v "no_proxy" >> /etc/environment
python3 -V
echo 'starting cron'
cd /app
cron -f