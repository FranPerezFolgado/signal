package main

import (
	"context"
	"log/slog"
	"os"

	"github.com/jackc/pgx/v5/pgxpool"
)

func main() {
	cfg, err := LoadConfig()
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

	consumer, err := newConfluentConsumer(cfg.KafkaBootstrapServers, cfg.KafkaConsumerGroup, clientID)
	if err != nil {
		logger.Error("kafka_consumer_init_failed", "error", err)
		os.Exit(1)
	}

	outputProducer, err := newConfluentProducer(cfg.KafkaBootstrapServers, clientID+"-output")
	if err != nil {
		logger.Error("kafka_output_producer_init_failed", "error", err)
		os.Exit(1)
	}

	dlqProducer, err := newConfluentProducer(cfg.KafkaBootstrapServers, clientID+"-dlq")
	if err != nil {
		logger.Error("kafka_dlq_producer_init_failed", "error", err)
		os.Exit(1)
	}

	artistRepo := &pgxArtistRepo{pool: pool}
	noveltyRepo := &pgxNoveltyRepo{pool: pool}
	dlq := newDLQPublisher(dlqProducer, logger)

	if err := RunConsumer(cfg, consumer, outputProducer, artistRepo, noveltyRepo, dlq, logger); err != nil {
		logger.Error("consumer_exited_with_error", "error", err)
		os.Exit(1)
	}
}
