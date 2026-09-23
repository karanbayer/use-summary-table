# Agentrix / container packaging for the static Use Summary Tables app.
# Serves app/ via nginx. AI extraction (/api/*) still requires Cloudflare
# Pages Functions or a separate API container — this image is UI + regex path.

FROM nginx:1.27-alpine

COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY app/ /usr/share/nginx/html/

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD wget -qO- http://127.0.0.1:8080/health || exit 1

CMD ["nginx", "-g", "daemon off;"]
