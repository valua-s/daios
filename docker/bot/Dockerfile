FROM daios-base:latest

COPY . .

COPY docker/bot/entrypoint.sh /entrypoint.sh
COPY docker/bot/start.sh /start.sh
RUN chmod +x /entrypoint.sh /start.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["/start.sh"]
