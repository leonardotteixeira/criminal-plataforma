FROM node:24-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
# O postinstall copia o worker do MapLibre para public/, então o script precisa existir antes.
COPY scripts ./scripts
RUN npm ci
COPY . .
# A URL da API é embutida no bundle do navegador em tempo de build.
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL NEXT_OUTPUT=standalone NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM node:24-alpine
WORKDIR /app
ENV NODE_ENV=production PORT=3000 HOSTNAME=0.0.0.0 NEXT_TELEMETRY_DISABLED=1
COPY --from=build /app/.next/standalone ./
COPY --from=build /app/.next/static ./.next/static
COPY --from=build /app/public ./public
EXPOSE 3000
CMD ["node", "server.js"]
