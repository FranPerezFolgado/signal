package kafka

import (
	"encoding/json"
	"fmt"
	"time"

	confluent "github.com/confluentinc/confluent-kafka-go/v2/kafka"
)

// Consumer abstracts the Kafka consumer for testability.
type Consumer interface {
	Subscribe(topics []string) error
	Poll(timeoutMs int) confluent.Event
	Commit() ([]confluent.TopicPartition, error)
	Close() error
}

// Producer abstracts the Kafka producer for testability.
type Producer interface {
	Produce(topic string, payload any, key string) error
	Flush(timeoutMs int) int
	Close()
}

// ConfluentConsumer wraps kafka.Consumer to satisfy Consumer.
type ConfluentConsumer struct {
	c *confluent.Consumer
}

func NewConsumer(brokers, group, clientID string) (*ConfluentConsumer, error) {
	c, err := confluent.NewConsumer(&confluent.ConfigMap{
		"bootstrap.servers":  brokers,
		"group.id":           group,
		"client.id":          clientID,
		"auto.offset.reset":  "earliest",
		"enable.auto.commit": false,
	})
	if err != nil {
		return nil, fmt.Errorf("create kafka consumer: %w", err)
	}
	return &ConfluentConsumer{c: c}, nil
}

func (cc *ConfluentConsumer) Subscribe(topics []string) error {
	return cc.c.SubscribeTopics(topics, nil)
}

func (cc *ConfluentConsumer) Poll(timeoutMs int) confluent.Event {
	return cc.c.Poll(timeoutMs)
}

func (cc *ConfluentConsumer) Commit() ([]confluent.TopicPartition, error) {
	return cc.c.Commit()
}

func (cc *ConfluentConsumer) Close() error {
	return cc.c.Close()
}

// ConfluentProducer wraps kafka.Producer to satisfy Producer.
type ConfluentProducer struct {
	p               *confluent.Producer
	deliveryTimeout time.Duration
}

func NewProducer(brokers, clientID string, deliveryTimeoutMs int) (*ConfluentProducer, error) {
	p, err := confluent.NewProducer(&confluent.ConfigMap{
		"bootstrap.servers": brokers,
		"client.id":         clientID,
	})
	if err != nil {
		return nil, fmt.Errorf("create kafka producer: %w", err)
	}
	return &ConfluentProducer{
		p:               p,
		deliveryTimeout: time.Duration(deliveryTimeoutMs) * time.Millisecond,
	}, nil
}

func (cp *ConfluentProducer) Produce(topic string, payload any, key string) error {
	data, err := json.Marshal(payload)
	if err != nil {
		return fmt.Errorf("marshal payload: %w", err)
	}

	deliveryCh := make(chan confluent.Event, 1)
	err = cp.p.Produce(&confluent.Message{
		TopicPartition: confluent.TopicPartition{Topic: &topic, Partition: confluent.PartitionAny},
		Key:            []byte(key),
		Value:          data,
	}, deliveryCh)
	if err != nil {
		return fmt.Errorf("produce message: %w", err)
	}

	select {
	case e := <-deliveryCh:
		m := e.(*confluent.Message)
		if m.TopicPartition.Error != nil {
			return fmt.Errorf("delivery failed: %w", m.TopicPartition.Error)
		}
	case <-time.After(cp.deliveryTimeout):
		return fmt.Errorf("delivery report timeout after %s", cp.deliveryTimeout)
	}
	return nil
}

func (cp *ConfluentProducer) Flush(timeoutMs int) int {
	return cp.p.Flush(timeoutMs)
}

func (cp *ConfluentProducer) Close() {
	cp.p.Close()
}
