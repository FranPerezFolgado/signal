package main

import (
	"context"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"syscall"

	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/prometheus/client_golang/prometheus/promhttp"

	"signal/novelty-detector/internal/config"
	"signal/novelty-detector/internal/consumer"
	"signal/novelty-detector/internal/dlq"
	"signal/novelty-detector/internal/kafka"
	"signal/novelty-detector/internal/repository"
)

func main() {
	cfg, err := config.Load()
	if err != nil {
		slog.Error("config_load_failed", "error", err)
		os.Exit(1)
	}

	level := slog.LevelInfo
	if cfg.LogLevel == "DEBUG" {
		level = slog.LevelDebug
	}
	logger := slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{Level: level}))

	pool, err := pgxpool.New(context.Background(), cfg.DatabaseURL)
	if err != nil {
		logger.Error("db_connect_failed", "error", err)
		os.Exit(1)
	}
	defer pool.Close()

	c, err := kafka.NewConsumer(cfg.KafkaBootstrapServers, cfg.KafkaConsumerGroup, consumer.ClientID)
	if err != nil {
		logger.Error("kafka_consumer_init_failed", "error", err)
		os.Exit(1)
	}

	outputProducer, err := kafka.NewProducer(cfg.KafkaBootstrapServers, consumer.ClientID+"-output", cfg.KafkaFlushTimeoutMs)
	if err != nil {
		logger.Error("kafka_output_producer_init_failed", "error", err)
		os.Exit(1)
	}

	dlqProducer, err := kafka.NewProducer(cfg.KafkaBootstrapServers, consumer.ClientID+"-dlq", cfg.KafkaFlushTimeoutMs)
	if err != nil {
		logger.Error("kafka_dlq_producer_init_failed", "error", err)
		os.Exit(1)
	}

	artistRepo := &repository.PgxArtistRepo{Pool: pool}
	noveltyRepo := &repository.PgxNoveltyRepo{Pool: pool}
	dlqWriter := dlq.NewPublisher(dlqProducer, logger)

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	go func() {
		port := os.Getenv("METRICS_PORT")
		if port == "" {
			port = "9100"
		}
		mux := http.NewServeMux()
		mux.Handle("/metrics", promhttp.Handler())
		if err := http.ListenAndServe(":"+port, mux); err != nil {
			logger.Error("metrics_server_failed", "error", err)
		}
	}()

	sigs := make(chan os.Signal, 1)
	signal.Notify(sigs, syscall.SIGTERM, syscall.SIGINT)
	defer signal.Stop(sigs)

	go func() {
		<-sigs
		cancel()
	}()

	if err := consumer.Run(ctx, cfg, c, outputProducer, artistRepo, noveltyRepo, dlqWriter, logger); err != nil {
		logger.Error("consumer_exited_with_error", "error", err)
		os.Exit(1)
	}
}
