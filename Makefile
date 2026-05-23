# ─── Infra — Docker Compose ───────────────────────────────────────────────────

COMPOSE = docker compose -f infra/docker-compose.yml

.PHONY: up down restart logs ps kafka-topics kafka-produce kafka-consume psql infra-clean ingester-backfill ingester-poll ingester-up ingester-logs

## Arranca Kafka + Zookeeper + PostgreSQL (y crea los topics)
up:
	@$(COMPOSE) up -d
	@echo "✓ Infra arrancada. Kafka en :9092 · PostgreSQL en :5432"

## Para todos los contenedores
down:
	@$(COMPOSE) down

## Reinicia todos los contenedores
restart:
	@$(COMPOSE) restart

## Logs en tiempo real (Ctrl+C para salir). Uso: make logs s=kafka
logs:
	@$(COMPOSE) logs -f $(s)

## Estado de los contenedores
ps:
	@$(COMPOSE) ps

## Lista los topics de Kafka
kafka-topics:
	@docker exec signal-kafka kafka-topics --bootstrap-server localhost:9092 --list

## Produce un mensaje de prueba. Uso: make kafka-produce t=raw.plays
kafka-produce:
	@docker exec -it signal-kafka kafka-console-producer --bootstrap-server localhost:9092 --topic $(t)

## Consume mensajes de un topic. Uso: make kafka-consume t=raw.plays
kafka-consume:
	@docker exec -it signal-kafka kafka-console-consumer --bootstrap-server localhost:9092 --topic $(t) --from-beginning

## Abre psql contra la BD signal
psql:
	@docker exec -it signal-postgres psql -U signal -d signal

## Elimina contenedores y volúmenes (borra todos los datos)
infra-clean:
	@$(COMPOSE) down -v
	@echo "✓ Contenedores y volúmenes eliminados"

# ─── QMD — servidor MCP local para búsqueda semántica de docs ────────────────

.PHONY: qmd-setup qmd-start qmd-stop qmd-reindex qmd-status

## Instala qmd y registra la colección signal (ejecutar una vez por máquina)
qmd-setup:
	@which qmd > /dev/null 2>&1 || npm install -g @tobilu/qmd
	@bash scripts/qmd-setup.sh

## Arranca el servidor MCP en background (localhost:8181)
qmd-start:
	@qmd mcp --http --daemon
	@echo "✓ QMD arrancado en http://localhost:8181/mcp"

## Para el servidor MCP
qmd-stop:
	@qmd mcp stop && echo "✓ QMD parado" || echo "QMD no estaba corriendo"

## Re-indexa docs tras añadir o modificar ficheros
qmd-reindex:
	@echo "→ Re-indexando docs/..."
	@qmd update
	@echo "→ Re-generando embeddings..."
	@qmd embed
	@echo "✓ Hecho"

## Muestra estado del índice y del servidor
qmd-status:
	@qmd status

# ─── lastfm-ingester ──────────────────────────────────────────────────────────
# ingester-backfill / ingester-poll: run locally via uv (fast iteration, no Docker)
# ingester-up / ingester-logs: run via Docker Compose (full-stack integration)

## Carga el historial completo de Last.fm y termina (one-shot, local)
ingester-backfill:
	@uv run python -m signal_lastfm_ingester --backfill

## Arranca el polling en primer plano (local, requiere .env exportado)
ingester-poll:
	@uv run python -m signal_lastfm_ingester

## Arranca el ingester como contenedor Docker en background
ingester-up:
	@$(COMPOSE) --profile services up -d lastfm-ingester

## Muestra los logs del contenedor del ingester (Ctrl+C para salir)
ingester-logs:
	@docker logs -f signal-lastfm-ingester

# ─── normalizer ───────────────────────────────────────────────────────────────

.PHONY: normalizer-up normalizer-logs normalizer-down

## Arranca el normalizer como contenedor Docker en background
normalizer-up:
	@$(COMPOSE) --profile services up -d normalizer

## Muestra los logs del normalizer (Ctrl+C para salir)
normalizer-logs:
	@docker logs -f signal-normalizer

## Para y elimina el contenedor del normalizer
normalizer-down:
	@$(COMPOSE) stop normalizer && $(COMPOSE) rm -f normalizer

# ─── history-tracker ──────────────────────────────────────────────────────────

.PHONY: history-tracker-up history-tracker-logs history-tracker-down

## Arranca el history-tracker como contenedor Docker en background
history-tracker-up:
	@$(COMPOSE) --profile services up -d history-tracker

## Muestra los logs del history-tracker (Ctrl+C para salir)
history-tracker-logs:
	@docker logs -f signal-history-tracker

## Para y elimina el contenedor del history-tracker
history-tracker-down:
	@$(COMPOSE) stop history-tracker && $(COMPOSE) rm -f history-tracker

# ─── enricher ─────────────────────────────────────────────────────────────────

.PHONY: enricher-up enricher-logs enricher-down

## Arranca el enricher como contenedor Docker en background
enricher-up:
	@$(COMPOSE) --profile services up -d --build enricher

## Muestra los logs del enricher (Ctrl+C para salir)
enricher-logs:
	@docker logs -f signal-enricher

## Para y elimina el contenedor del enricher
enricher-down:
	@$(COMPOSE) stop enricher && $(COMPOSE) rm -f enricher

# ─── all pipeline services ────────────────────────────────────────────────────

.PHONY: services-up services-down services-restart

## Arranca (y reconstruye) todos los servicios del pipeline
services-up:
	@$(COMPOSE) --profile services up -d --build

## Para todos los servicios del pipeline (mantiene infra)
services-down:
	@$(COMPOSE) --profile services stop

## Reconstruye y reinicia todos los servicios del pipeline
services-restart:
	@$(COMPOSE) --profile services up -d --build --force-recreate

# ─── kafka-ui ─────────────────────────────────────────────────────────────────

.PHONY: kafka-ui-up kafka-ui-down

## Arranca kafka-ui en http://localhost:8080 (perfil tools)
kafka-ui-up:
	@$(COMPOSE) --profile tools up -d kafka-ui

## Para y elimina el contenedor de kafka-ui
kafka-ui-down:
	@$(COMPOSE) stop kafka-ui && $(COMPOSE) rm -f kafka-ui
