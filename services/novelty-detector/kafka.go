package main

import (
	"encoding/json"
	"fmt"
	"time"

	kafka "github.com/confluentinc/confluent-kafka-go/v2/kafka"
)

// KafkaConsumer abstracts the Kafka consumer for testability.
type KafkaConsumer interface {
	Subscribe(topics []string) error
	Poll(timeoutMs int) kafka.Event
	Commit() ([]kafka.TopicPartition, error)
	Close() error
}

// KafkaProducer abstracts the Kafka producer for testability.
type KafkaProducer interface {
	Produce(topic string, payload any, key string) error
	Flush(timeoutMs int) int
	Close()
}

// confluentConsumer wraps kafka.Consumer to satisfy KafkaConsumer.
type confluentConsumer struct {
	c *kafka.Consumer
}

func newConfluentConsumer(brokers, group, clientID string) (*confluentConsumer, error) {
	c, err := kafka.NewConsumer(&kafka.ConfigMap{
		"bootstrap.servers":  brokers,
		"group.id":           group,
		"client.id":          clientID,
		"auto.offset.reset":  "earliest",
		"enable.auto.commit": false,
	})
	if err != nil {
		return nil, fmt.Errorf("create kafka consumer: %w", err)
	}
	return &confluentConsumer{c: c}, nil
}

func (cc *confluentConsumer) Subscribe(topics []string) error {
	return cc.c.SubscribeTopics(topics, nil)
}

func (cc *confluentConsumer) Poll(timeoutMs int) kafka.Event {
	return cc.c.Poll(timeoutMs)
}

func (cc *confluentConsumer) Commit() ([]kafka.TopicPartition, error) {
	return cc.c.Commit()
}

func (cc *confluentConsumer) Close() error {
	return cc.c.Close()
}

// confluentProducer wraps kafka.Producer to satisfy KafkaProducer.
type confluentProducer struct {
	p *kafka.Producer
}

func newConfluentProducer(brokers, clientID string) (*confluentProducer, error) {
	p, err := kafka.NewProducer(&kafka.ConfigMap{
		"bootstrap.servers": brokers,
		"client.id":         clientID,
	})
	if err != nil {
		return nil, fmt.Errorf("create kafka producer: %w", err)
	}
	return &confluentProducer{p: p}, nil
}

func (cp *confluentProducer) Produce(topic string, payload any, key string) error {
	data, err := json.Marshal(payload)
	if err != nil {
		return fmt.Errorf("marshal payload: %w", err)
	}

	deliveryCh := make(chan kafka.Event, 1)
	err = cp.p.Produce(&kafka.Message{
		TopicPartition: kafka.TopicPartition{Topic: &topic, Partition: kafka.PartitionAny},
		Key:            []byte(key),
		Value:          data,
	}, deliveryCh)
	if err != nil {
		return fmt.Errorf("produce message: %w", err)
	}

	// Wait for delivery report (with a short timeout to avoid blocking).
	select {
	case e := <-deliveryCh:
		m := e.(*kafka.Message)
		if m.TopicPartition.Error != nil {
			return fmt.Errorf("delivery failed: %w", m.TopicPartition.Error)
		}
	case <-time.After(5 * time.Second):
		return fmt.Errorf("delivery report timeout")
	}
	return nil
}

func (cp *confluentProducer) Flush(timeoutMs int) int {
	return cp.p.Flush(timeoutMs)
}

func (cp *confluentProducer) Close() {
	cp.p.Close()
}
