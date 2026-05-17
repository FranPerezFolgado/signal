#!/bin/bash
# qmd-setup.sh — Registra la colección signal en QMD.
# Ejecutar una vez por máquina tras instalar qmd.

set -e

DOCS_PATH="$(cd "$(dirname "$0")/.." && pwd)/docs"

echo "→ Registrando colección 'signal' en QMD..."
echo "  path: $DOCS_PATH"

# Añadir colección (idempotente: si ya existe, collection add falla silenciosamente)
qmd collection add "$DOCS_PATH" --name signal --mask "**/*.md" 2>/dev/null || \
  echo "  (colección ya existía, continuando)"

# Añadir contextos para que QMD entienda qué hay en cada subcarpeta
qmd context add qmd://signal "Docs, decisiones y sesiones del proyecto Signal — sistema de discovery de artistas musicales"
qmd context add qmd://signal/adr "ADRs: decisiones de arquitectura con contexto, alternativas consideradas y justificación"
qmd context add qmd://signal/sessions "Resúmenes de sesiones de trabajo: objetivos, decisiones, cambios y próximos pasos"

echo "→ Indexando documentos..."
qmd update

echo "→ Generando embeddings (puede tardar unos minutos la primera vez)..."
qmd embed

echo ""
echo "✓ Colección 'signal' lista."
echo "  Lanza el servidor con: make qmd-start"
