FROM node:22-alpine AS builder

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .

ARG VITE_DISCORD_CLIENT_ID
ARG VITE_API_BASE_URL=
ARG VITE_MUXIVO_CONSOLE_URL=
ENV VITE_DISCORD_CLIENT_ID=$VITE_DISCORD_CLIENT_ID \
    VITE_API_BASE_URL=$VITE_API_BASE_URL \
    VITE_MUXIVO_CONSOLE_URL=$VITE_MUXIVO_CONSOLE_URL

RUN npm run build

FROM node:22-alpine AS runtime

WORKDIR /app

RUN addgroup -S activity && adduser -S activity -G activity

COPY --chown=activity:activity --from=builder /app/dist ./dist
COPY --chown=activity:activity server.mjs ./server.mjs

ENV PORT=8080

EXPOSE 8080

USER activity

CMD ["node", "server.mjs"]
