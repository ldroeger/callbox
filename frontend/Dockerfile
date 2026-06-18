FROM node:20-slim AS builder

WORKDIR /app

ARG REACT_APP_API_URL
ENV REACT_APP_API_URL=${REACT_APP_API_URL}

COPY package.json .
RUN npm install

COPY . .
RUN npm run build

FROM node:20-slim
WORKDIR /app
RUN npm install -g serve
COPY --from=builder /app/build ./build

CMD ["serve", "-s", "build", "-l", "3000"]
