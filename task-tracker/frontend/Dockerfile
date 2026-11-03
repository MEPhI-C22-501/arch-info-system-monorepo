FROM node:24-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY index.html tsconfig.json vite.config.ts ./
COPY src src
ARG VITE_OIDC_AUTHORITY=http://localhost:8081/realms/arch-info-system
ARG VITE_OIDC_CLIENT_ID=task-tracker
RUN npm run build

FROM nginx:1.29-alpine
ENV BACKEND_UPSTREAM=task-tracker-backend:8080
COPY default.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
