FROM docker.io/ubuntu:24.04

RUN apt update
RUN apt -y upgrade
RUN apt -y install cron python3 python3-dev python3-pip python3-requests
RUN pip install goodwe --break-system-packages

RUN which python3

# copy files
COPY python /app/python
COPY shell/tibber-goodwe-loading.sh /app/tibber-goodwe-loading.sh
COPY shell/entrypoint.sh /app/entrypoint.sh
COPY shell/container_cron /etc/cron.d/container_cron

# set workdir
WORKDIR /app

# give execution rights on the cron job
RUN chmod 0644 /etc/cron.d/container_cron

# apply cron job
RUN crontab /etc/cron.d/container_cron

# run the command on container startup
CMD ["bash", "entrypoint.sh"]
