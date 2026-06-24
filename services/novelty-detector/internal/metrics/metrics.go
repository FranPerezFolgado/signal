package metrics

import "github.com/prometheus/client_golang/prometheus"

var (
	EventsConsumed = prometheus.NewCounterVec(
		prometheus.CounterOpts{
			Name: "signal_events_consumed_total",
			Help: "Total Kafka events consumed.",
		},
		[]string{"service", "topic"},
	)

	EventsProduced = prometheus.NewCounterVec(
		prometheus.CounterOpts{
			Name: "signal_events_produced_total",
			Help: "Total Kafka events produced.",
		},
		[]string{"service", "topic"},
	)

	ProcessingErrors = prometheus.NewCounterVec(
		prometheus.CounterOpts{
			Name: "signal_processing_errors_total",
			Help: "Total processing errors.",
		},
		[]string{"service", "error_type"},
	)
)

func init() {
	prometheus.MustRegister(EventsConsumed, EventsProduced, ProcessingErrors)
}
