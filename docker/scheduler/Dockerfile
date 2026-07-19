FROM daios-base:latest

COPY . .

COPY docker/scheduler/entrypoint.sh /entrypoint.sh
COPY docker/scheduler/start.sh /start.sh
RUN chmod +x /entrypoint.sh /start.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["/start.sh"]
