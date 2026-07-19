FROM daios-base:latest

COPY . .

COPY docker/api/entrypoint.sh /entrypoint.sh
COPY docker/api/start.sh /start.sh
RUN chmod +x /entrypoint.sh /start.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["/start.sh"]
