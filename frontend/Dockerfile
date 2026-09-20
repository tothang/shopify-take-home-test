FROM node:22-slim

WORKDIR /service

COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY . .

EXPOSE 5173

CMD ["npm", "run", "start", "--", "--host", "0.0.0.0"]
