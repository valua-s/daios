FROM daios-base:latest

COPY . .

COPY docker/logbot/entrypoint.sh /entrypoint.sh
COPY docker/logbot/start.sh /start.sh
RUN chmod +x /entrypoint.sh /start.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["/start.sh"]
