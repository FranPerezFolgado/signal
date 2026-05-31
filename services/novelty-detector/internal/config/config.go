package config

import (
	"fmt"
	"os"
	"strconv"
)

type Config struct {
	KafkaBootstrapServers string
	DatabaseURL           string
	KafkaConsumerGroup    string
	LogLevel              string
	AutoFollowPlays       int
	KafkaFlushTimeoutMs   int
}

func Load() (Config, error) {
	brokers := os.Getenv("KAFKA_BOOTSTRAP_SERVERS")
	if brokers == "" {
		brokers = "localhost:9092"
	}

	dbURL := os.Getenv("DATABASE_URL")
	if dbURL == "" {
		return Config{}, fmt.Errorf("DATABASE_URL is required but not set")
	}

	group := os.Getenv("KAFKA_CONSUMER_GROUP")
	if group == "" {
		group = "novelty-detector-group"
	}

	logLevel := os.Getenv("LOG_LEVEL")
	if logLevel == "" {
		logLevel = "INFO"
	}

	autoFollow := 3
	if v := os.Getenv("AUTO_FOLLOW_PLAYS"); v != "" {
		n, err := strconv.Atoi(v)
		if err != nil {
			return Config{}, fmt.Errorf("AUTO_FOLLOW_PLAYS must be an integer: %w", err)
		}
		if n < 1 {
			return Config{}, fmt.Errorf("AUTO_FOLLOW_PLAYS must be >= 1, got %d", n)
		}
		autoFollow = n
	}

	flushMs := 10000
	if v := os.Getenv("KAFKA_FLUSH_TIMEOUT_MS"); v != "" {
		n, err := strconv.Atoi(v)
		if err != nil {
			return Config{}, fmt.Errorf("KAFKA_FLUSH_TIMEOUT_MS must be an integer: %w", err)
		}
		if n < 1 {
			return Config{}, fmt.Errorf("KAFKA_FLUSH_TIMEOUT_MS must be >= 1, got %d", n)
		}
		flushMs = n
	}

	return Config{
		KafkaBootstrapServers: brokers,
		DatabaseURL:           dbURL,
		KafkaConsumerGroup:    group,
		LogLevel:              logLevel,
		AutoFollowPlays:       autoFollow,
		KafkaFlushTimeoutMs:   flushMs,
	}, nil
}
