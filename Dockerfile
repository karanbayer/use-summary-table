# Agentrix / Knative: single Node process serves UI + /api/* on $PORT (default 8080).
# Requires AZURE_CLIENT_SECRET (or TFY_API_TOKEN) and PILOT_GATE_SECRET at runtime.
# Soft-async jobs need knowledge/compiled (pipeline prompts) in the image.

FROM node:22-alpine

RUN apk add --no-cache wget

WORKDIR /app
COPY server/ /app/server/
COPY app/ /app/public/
COPY knowledge/compiled/ /app/knowledge/compiled/

ENV PORT=8080
ENV STATIC_ROOT=/app/public
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD wget -qO- http://127.0.0.1:8080/health || exit 1

CMD ["node", "/app/server/index.mjs"]
