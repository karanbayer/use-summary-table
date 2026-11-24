# Agentrix / Knative: single Node process serves UI + /api/* on $PORT (default 8080).
# Requires AZURE_CLIENT_SECRET (or TFY_API_TOKEN) and PILOT_GATE_SECRET at runtime.
# Soft-async knowledge JSON is baked into server/lib/ (root .dockerignore excludes knowledge/).

FROM node:22-alpine
# The app\'s one version (scripts/bump_version.py): the deploy workflow raises both lines and deploys with it.
LABEL version="1.1.42"
ENV AGENT_VERSION=1.1.42

RUN apk add --no-cache wget

WORKDIR /app
COPY server/ /app/server/
COPY app/ /app/public/

ENV PORT=8080
ENV STATIC_ROOT=/app/public
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD wget -qO- http://127.0.0.1:8080/health || exit 1

CMD ["node", "/app/server/index.mjs"]
