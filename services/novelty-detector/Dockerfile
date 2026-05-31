# Stage 1 — builder: compile Go binary with CGo for confluent-kafka-go
FROM golang:1.22-alpine AS builder

RUN apk add --no-cache gcc musl-dev librdkafka-dev pkgconfig

WORKDIR /build

COPY go.mod go.sum ./
RUN go mod download

COPY cmd/ ./cmd/
COPY internal/ ./internal/
RUN go build -tags musl -o novelty-detector ./cmd/novelty-detector/

# Stage 2 — runtime: minimal Alpine image with librdkafka
FROM alpine:3.20

RUN apk add --no-cache librdkafka

COPY --from=builder /build/novelty-detector /usr/local/bin/novelty-detector

CMD ["novelty-detector"]
