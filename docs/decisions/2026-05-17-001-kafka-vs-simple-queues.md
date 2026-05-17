# ADR-001 — Kafka como bus de eventos en lugar de colas simples o HTTP síncrono

- **Status**: Accepted
- **Date**: 2026-05-17

## Context

El pipeline de Signal conecta 7 servicios que procesan plays musicales con ritmos de ingesta muy distintos: `lastfm-ingester` hace polling cada N minutos, `artist-tracker` expande el grafo cada N horas, y `normalizer`/`history-tracker`/`novelty-detector` procesan de forma continua. Necesitamos un canal de comunicación entre ellos.

Tres alternativas reales:

1. **HTTP síncrono** — cada servicio llama directamente al siguiente.
2. **Cola simple** (RabbitMQ, SQS) — mensajes en una cola que un único consumer consume.
3. **Kafka** — log de eventos distribuido donde múltiples consumers pueden leer el mismo stream de forma independiente.

## Decision

Kafka como bus de eventos central.

## Rationale

**HTTP síncrono descartado por**:
- Acoplamiento temporal: si `history-tracker` cae, `normalizer` falla también aunque el dato llegara.
- Sin buffer entre productores y consumidores con ritmos distintos.
- Sin capacidad de replay: si el `scorer` cambia su lógica, no hay forma de reprocesar el historial sin re-ingestar desde Last.fm.

**RabbitMQ (o cualquier work queue) descartado por**:
- Diseñado para el patrón "un mensaje, un consumer". Un mensaje en una queue RabbitMQ desaparece cuando un consumer lo procesa.
- `tracks.normalized` lo necesitan leer **dos consumers a la vez**: `history-tracker` (para persistir en Postgres) y `novelty-detector` (para detectar artistas nuevos). Con RabbitMQ, o duplicamos el mensaje en dos queues (acoplamiento, posibles desincronías) o un solo consumer lo distribuye internamente (perdemos desacoplamiento).
- El modelo de consumer groups de Kafka resuelve esto de forma natural: cada servicio tiene su propio offset y avanza a su propio ritmo.

**Kafka aceptado por**:
- Consumer groups independientes por servicio: cada uno mantiene su offset, puede ir más lento o rápido sin afectar a los demás.
- Replay nativo: si recalibramos los pesos del `scorer` (W1, W2, W3), podemos reprocesar `tracks.novel` desde el principio sin tocar Last.fm ni Spotify.
- Buffer natural entre productores con ritmos distintos y consumers continuos.

## Consequences

**Beneficios**:
- Múltiples consumers del mismo topic sin acoplamiento ni duplicación de mensajes.
- Replay del stream para reprocesar sin re-ingestar de fuentes externas.
- Desacoplamiento temporal: un consumer puede caer y recuperarse leyendo desde su último offset.

**Costes**:
- Más pesado operativamente que una cola simple (controller, particiones, offsets, gestión de consumer groups).
- Sobredimensionado para el volumen real del MVP (decenas de plays por día, no millones). Asumimos este coste conscientemente por las capacidades de replay y multi-consumer.

## When to reconsider

Si tras 6 meses de uso real nunca se ha usado el replay y cada topic tiene siempre un único consumer, vale la pena evaluar simplificar a RabbitMQ o incluso HTTP + retry.
