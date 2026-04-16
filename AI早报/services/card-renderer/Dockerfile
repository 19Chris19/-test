FROM mcr.microsoft.com/playwright:v1.52.0-jammy

WORKDIR /app

ENV NODE_ENV=production
ENV PORT=3000
ENV HOSTNAME=0.0.0.0

COPY package.json ./
RUN npm install

COPY next.config.mjs tsconfig.json next-env.d.ts ./
COPY src ./src

RUN npm run build

EXPOSE 3000

CMD ["npm", "run", "start", "--", "--hostname", "0.0.0.0", "--port", "3000"]
