# syntax=docker/dockerfile:1.7
# PWA MicroForge : construction Vite (Node), puis fichiers statiques servis par nginx.
#   docker build -t microforge-pwa microforge/pwa
# Une seule image pour tous les environnements : les adresses des API sont lues au démarrage
# (MF_PUBLIC_API_DATA_URL, MF_PUBLIC_API_IA_URL) et servies dans /config.js.

FROM node:24.22.2-alpine AS build
WORKDIR /pwa
ENV PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1
COPY package.json package-lock.json .npmrc ./
RUN npm ci
COPY . .
RUN npm test && npm run build

FROM nginx:1.30.6-alpine AS pwa
# Seules les variables MF_PUBLIC_* sont substituées dans les modèles (les $uri de nginx restent intacts).
ENV MF_PUBLIC_API_DATA_URL=http://localhost:8000 \
    MF_PUBLIC_API_IA_URL=http://localhost:8001 \
    NGINX_ENVSUBST_FILTER=^MF_PUBLIC_
COPY nginx/ /etc/nginx/templates/
COPY --from=build /pwa/dist /usr/share/nginx/html
# config.js est produit par nginx à partir des variables d'environnement (voir default.conf.template).
RUN rm /usr/share/nginx/html/config.js
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s CMD wget -qO /dev/null http://127.0.0.1:8080/ || exit 1
