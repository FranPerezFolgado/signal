package main

import (
	"fmt"
	"log/slog"
	"time"
)

const dlqTopic = "novelty-detector.dlq"

// DLQPublisher publishes failed messages to the dead-letter queue topic.
type DLQPublisher struct {
	producer KafkaProducer
	logger   *slog.Logger
}

func newDLQPublisher(producer KafkaProducer, logger *slog.Logger) *DLQPublisher {
	return &DLQPublisher{producer: producer, logger: logger}
}

// Publish sends an error entry to the DLQ topic. Always logs the error; best-effort
// produce (failure is logged but does not re-raise to avoid looping).
func (d *DLQPublisher) Publish(errorReason, errorDetail string, original any) {
	entry := DLQEntry{
		ErrorReason:     errorReason,
		ErrorDetail:     errorDetail,
		OriginalPayload: original,
		FailedAt:        time.Now().UTC().Format(time.RFC3339),
	}
	key := fmt.Sprintf("%s:%d", errorReason, time.Now().UnixNano())
	if err := d.producer.Produce(dlqTopic, entry, key); err != nil {
		d.logger.Error("dlq_publish_failed", "error", err, "error_reason", errorReason)
	}
}
