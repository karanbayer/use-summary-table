# Agentrix container: static UI (nginx) + Node AI relay (/api/extract).
# Exposes 8080. Requires AZURE_CLIENT_SECRET (or TFY_API_TOKEN) and
# PILOT_GATE_SECRET at runtime — see DEPLOYMENT.md Agentrix section.

FROM node:22-alpine

RUN apk add --no-cache nginx wget \
  && mkdir -p /run/nginx /usr/share/nginx/html

COPY docker/nginx.conf /etc/nginx/http.d/default.conf
COPY docker/entrypoint.sh /entrypoint.sh
COPY app/ /usr/share/nginx/html/
COPY server/ /app/server/

RUN chmod +x /entrypoint.sh \
  && rm -f /etc/nginx/http.d/default.conf.bak 2>/dev/null || true

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD wget -qO- http://127.0.0.1:8080/health || exit 1

CMD ["/entrypoint.sh"]
