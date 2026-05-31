package dlq

import (
	"fmt"
	"log/slog"
	"time"

	"signal/novelty-detector/internal/kafka"
)

const Topic = "novelty-detector.dlq"

// Writer is the interface for publishing to the dead-letter queue.
// Using an interface keeps consumer.go consistent: all dependencies are injected as interfaces.
type Writer interface {
	Publish(errorReason, errorDetail string, original any)
}

// Entry is the error envelope persisted to the DLQ topic.
type Entry struct {
	ErrorReason     string `json:"error_reason"`
	ErrorDetail     string `json:"error_detail"`
	OriginalPayload any    `json:"original_payload"`
	FailedAt        string `json:"failed_at"`
}

// Publisher publishes failed messages to the DLQ topic. Satisfies Writer.
type Publisher struct {
	producer kafka.Producer
	logger   *slog.Logger
}

func NewPublisher(producer kafka.Producer, logger *slog.Logger) *Publisher {
	return &Publisher{producer: producer, logger: logger}
}

// Publish sends an error entry to the DLQ topic. Best-effort: failures are logged,
// not re-raised, to avoid looping on persistent DLQ errors.
func (p *Publisher) Publish(errorReason, errorDetail string, original any) {
	entry := Entry{
		ErrorReason:     errorReason,
		ErrorDetail:     errorDetail,
		OriginalPayload: original,
		FailedAt:        time.Now().UTC().Format(time.RFC3339),
	}
	key := fmt.Sprintf("%s:%d", errorReason, time.Now().UnixNano())
	if err := p.producer.Produce(Topic, entry, key); err != nil {
		p.logger.Error("dlq_publish_failed", "error", err, "error_reason", errorReason)
	}
}
