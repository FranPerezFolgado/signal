from __future__ import annotations

from confluent_kafka.admin import AdminClient, OffsetSpec, _ConsumerGroupTopicPartitions as ConsumerGroupTopicPartitions
from confluent_kafka import TopicPartition

# Canonical mapping: consumer group → friendly service name + input topic label
PIPELINE_SERVICES: dict[str, tuple[str, str]] = {
    "normalizer-group": ("normalizer", "raw.plays"),
    "enricher-group": ("enricher", "tracks.normalized"),
    "history-tracker-enriched-group": ("history-tracker", "tracks.enriched"),
    "novelty-detector-group": ("novelty-detector", "tracks.enriched"),
    "scorer": ("scorer", "tracks.novel"),
}


def get_pipeline_stats(bootstrap_servers: str) -> list[dict]:
    """Query Kafka for consumer group lag and status across all pipeline services."""
    admin = AdminClient({
        "bootstrap.servers": bootstrap_servers,
        "socket.timeout.ms": 5000,
        "request.timeout.ms": 8000,
    })

    group_ids = list(PIPELINE_SERVICES.keys())

    # 1 — Active member counts
    member_counts: dict[str, int] = {}
    try:
        for gid, fut in admin.describe_consumer_groups(group_ids).items():
            try:
                member_counts[gid] = len(fut.result().members)
            except Exception:
                member_counts[gid] = 0
    except Exception:
        member_counts = {gid: 0 for gid in group_ids}

    # 2 — Committed offsets per group (API only accepts one group per call)
    committed: dict[str, dict[tuple[str, int], int]] = {}
    all_tps: set[TopicPartition] = set()
    for gid in group_ids:
        try:
            results = admin.list_consumer_group_offsets([ConsumerGroupTopicPartitions(gid)])
            for _, fut in results.items():
                try:
                    result = fut.result()
                    partitions: dict[tuple[str, int], int] = {}
                    for tp in result.topic_partitions:
                        key = (tp.topic, tp.partition)
                        partitions[key] = tp.offset if tp.offset is not None else -1
                        if tp.offset is not None and tp.offset >= 0:
                            all_tps.add(TopicPartition(tp.topic, tp.partition))
                    committed[gid] = partitions
                except Exception:
                    committed[gid] = {}
        except Exception:
            committed[gid] = {}

    # 3 — Log-end offsets (high watermarks)
    end_offsets: dict[tuple[str, int], int] = {}
    if all_tps:
        try:
            for tp, fut in admin.list_offsets(
                {tp: OffsetSpec.latest() for tp in all_tps}
            ).items():
                try:
                    end_offsets[(tp.topic, tp.partition)] = fut.result().offset
                except Exception:
                    pass
        except Exception:
            pass

    # 4 — Aggregate per service
    results: list[dict] = []
    for gid, (service, topic_hint) in PIPELINE_SERVICES.items():
        partitions = committed.get(gid, {})
        total_lag = 0
        total_processed = 0
        topics: set[str] = set()

        for (topic, part), offset in partitions.items():
            topics.add(topic)
            end = end_offsets.get((topic, part), 0)
            if offset >= 0:
                total_lag += max(0, end - offset)
                total_processed += offset
            else:
                total_lag += end

        members = member_counts.get(gid, 0)
        if members > 0 and total_lag == 0:
            status = "ACTIVE"
        elif members > 0 and total_lag > 0:
            status = "PROCESSING"
        elif total_lag > 0:
            status = "STALLED"
        else:
            status = "IDLE"

        results.append({
            "service": service,
            "group": gid,
            "topic": sorted(topics)[0] if topics else topic_hint,
            "status": status,
            "lag": total_lag,
            "processed": total_processed,
            "consumers": members,
        })

    return results
