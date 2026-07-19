FROM node:22-alpine

RUN npm install -g serve

COPY public /app/public

EXPOSE 3000
CMD ["serve", "-s", "/app/public", "-l", "3000"]
