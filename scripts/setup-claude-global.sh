#!/bin/bash
# setup-claude-global.sh — Monta ~/.claude/ global para Claude Code.
# Ejecutar una vez desde la raíz del repo: bash scripts/setup-claude-global.sh

set -e
CLAUDE="$HOME/.claude"
echo "→ Creando estructura en $CLAUDE..."
mkdir -p "$CLAUDE/hooks" "$CLAUDE/commands" "$CLAUDE/agents"

# ── settings.json ─────────────────────────────────────────────────────────────
cat > "$CLAUDE/settings.json" << 'EOF'
{
  "model": "opusplan",
  "theme": "dark-ansi",
  "autoUpdatesChannel": "stable",
  "enabledPlugins": {
    "superpowers@claude-plugins-official": true,
    "qmd@qmd": true
  },
  "extraKnownMarketplaces": {
    "superpowers-marketplace": {
      "source": { "source": "github", "repo": "obra/superpowers-marketplace" }
    },
    "qmd": {
      "source": { "source": "github", "repo": "tobi/qmd" }
    }
  },
  "mcpServers": {
    "qmd": { "url": "http://localhost:8181/mcp" }
  },
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [{ "type": "command", "command": "rtk hook claude" }]
      },
      {
        "matcher": "Grep|Glob|Read|Search",
        "hooks": [{ "type": "command", "command": "~/.claude/hooks/cbm-code-discovery-gate" }]
      }
    ],
    "SessionStart": [
      { "matcher": "startup", "hooks": [{ "type": "command", "command": "~/.claude/hooks/cbm-session-reminder" }] },
      { "matcher": "resume",  "hooks": [{ "type": "command", "command": "~/.claude/hooks/cbm-session-reminder" }] },
      { "matcher": "clear",   "hooks": [{ "type": "command", "command": "~/.claude/hooks/cbm-session-reminder" }] },
      { "matcher": "compact", "hooks": [{ "type": "command", "command": "~/.claude/hooks/cbm-session-reminder" }] }
    ]
  },
  "statusLine": {
    "type": "command",
    "command": "sh ~/.claude/statusline-command.sh"
  }
}
EOF

# ── .mcp.json ─────────────────────────────────────────────────────────────────
cat > "$CLAUDE/.mcp.json" << 'EOF'
{
  "mcpServers": {
    "codebase-memory-mcp": {
      "command": "~/.local/bin/codebase-memory-mcp"
    }
  }
}
EOF

# ── CLAUDE.md ─────────────────────────────────────────────────────────────────
cat > "$CLAUDE/CLAUDE.md" << 'EOF'
## Default behavior

@RTK.md
EOF

# ── RTK.md ────────────────────────────────────────────────────────────────────
cat > "$CLAUDE/RTK.md" << 'EOF'
# RTK - Rust Token Killer

**Usage**: Token-optimized CLI proxy (60-90% savings on dev operations)

## Meta Commands (always use rtk directly)

```bash
rtk gain              # Show token savings analytics
rtk gain --history    # Show command usage history with savings
rtk discover          # Analyze Claude Code history for missed opportunities
rtk proxy <cmd>       # Execute raw command without filtering (for debugging)
```

## Hook-Based Usage

All other commands are automatically rewritten by the Claude Code hook.
Example: `git status` → `rtk git status` (transparent, 0 tokens overhead)
EOF

# ── statusline-command.sh ─────────────────────────────────────────────────────
cat > "$CLAUDE/statusline-command.sh" << 'EOF'
#!/bin/sh
input=$(cat)
model=$(echo "$input" | jq -r '.model.display_name // "Unknown"')
used=$(echo "$input" | jq -r '.context_window.used_percentage // empty')
total_in=$(echo "$input" | jq -r '.context_window.total_input_tokens // 0')
total_out=$(echo "$input" | jq -r '.context_window.total_output_tokens // 0')
total_tokens=$(( total_in + total_out ))
if [ "$total_tokens" -gt 999999 ]; then
  tokens_fmt=$(awk "BEGIN {printf \"%.1fM\", $total_tokens/1000000}")
elif [ "$total_tokens" -gt 999 ]; then
  tokens_fmt=$(awk "BEGIN {printf \"%.1fk\", $total_tokens/1000}")
else
  tokens_fmt="$total_tokens"
fi
if [ -n "$used" ]; then
  used_int=$(printf '%.0f' "$used")
  filled=$(( used_int / 5 )); empty=$(( 20 - filled ))
  bar=""; i=0
  while [ $i -lt $filled ]; do bar="${bar}█"; i=$(( i + 1 )); done
  i=0
  while [ $i -lt $empty ];  do bar="${bar}░"; i=$(( i + 1 )); done
  printf "%s  [%s] %d%%  tokens: %s" "$model" "$bar" "$used_int" "$tokens_fmt"
else
  printf "%s  [░░░░░░░░░░░░░░░░░░░░] -  tokens: %s" "$model" "$tokens_fmt"
fi
EOF

# ── hooks ─────────────────────────────────────────────────────────────────────
cat > "$CLAUDE/hooks/cbm-code-discovery-gate" << 'EOF'
#!/bin/bash
GATE=/tmp/cbm-code-discovery-gate-$PPID
find /tmp -name 'cbm-code-discovery-gate-*' -mtime +1 -delete 2>/dev/null
if [ -f "$GATE" ]; then exit 0; fi
touch "$GATE"
echo 'BLOCKED: For code discovery, use codebase-memory-mcp tools first: search_graph(name_pattern) to find functions/classes, trace_path() for call chains, get_code_snippet(qualified_name) to read source. If the graph is not indexed yet, call index_repository first. Fall back to Grep/Glob/Read only for text content search. If you need Grep, retry.' >&2
exit 2
EOF

cat > "$CLAUDE/hooks/cbm-session-reminder" << 'EOF'
#!/bin/bash
cat << 'REMINDER'
CRITICAL - Code Discovery Protocol:
1. ALWAYS use codebase-memory-mcp tools FIRST for ANY code exploration:
   - search_graph(name_pattern/label/qn_pattern) to find functions/classes/routes
   - trace_path(function_name, mode=calls|data_flow|cross_service) for call chains
   - get_code_snippet(qualified_name) to read source (NOT Read/cat)
   - query_graph(query) for complex Cypher patterns
   - get_architecture(aspects) for project structure
   - search_code(pattern) for text search (graph-augmented grep)
2. Fall back to Grep/Glob/Read ONLY for text content, config values, non-code files.
3. If a project is not indexed yet, run index_repository FIRST.
REMINDER
EOF

# ── agents (globales) ─────────────────────────────────────────────────────────
cat > "$CLAUDE/agents/code-researcher.yaml" << 'EOF'
name: code-researcher
description: Navega el codebase usando codebase-memory-mcp. Úsalo para búsquedas de código sin saturar el contexto principal.
model: haiku
tools:
  - Bash
  - Read
  - Grep
  - Glob
  - mcp__codebase-memory-mcp
EOF

cat > "$CLAUDE/agents/security-reviewer.yaml" << 'EOF'
name: security-reviewer
description: Detecta vulnerabilidades en los cambios de la rama. Solo lectura, nunca modifica ficheros.
model: haiku
tools:
  - Read
  - Grep
  - Glob
  - Bash
EOF

cat > "$CLAUDE/agents/style-reviewer.yaml" << 'EOF'
name: style-reviewer
description: Verifica convenciones de código del proyecto. Solo lectura, nunca modifica ficheros.
model: haiku
tools:
  - Read
  - Grep
  - Glob
EOF

cat > "$CLAUDE/agents/test-reviewer.yaml" << 'EOF'
name: test-reviewer
description: Analiza cobertura y calidad de tests. Solo lectura, nunca modifica ficheros.
model: haiku
tools:
  - Read
  - Grep
  - Glob
EOF

cat > "$CLAUDE/agents/doc-checker.yaml" << 'EOF'
name: doc-checker
description: Detecta documentación desactualizada cruzando cambios del código con docs existentes. Solo lectura.
model: haiku
tools:
  - Bash
  - Read
  - Grep
  - Glob
EOF

cat > "$CLAUDE/agents/plan-researcher.yaml" << 'EOF'
name: plan-researcher
description: Recopila contexto para planificación usando codebase-memory-mcp y QMD. Devuelve resumen ≤ 500 palabras.
model: haiku
tools:
  - Bash
  - Read
  - Grep
  - Glob
  - mcp__codebase-memory-mcp
  - mcp__qmd
EOF

# ── permisos ──────────────────────────────────────────────────────────────────
chmod +x "$CLAUDE/hooks/cbm-code-discovery-gate"
chmod +x "$CLAUDE/hooks/cbm-session-reminder"
chmod +x "$CLAUDE/statusline-command.sh"

# ── QMD index (~/.config/qmd/index.yml) ───────────────────────────────────────
echo ""
echo "→ Configurando QMD collections en ~/.config/qmd/index.yml..."
mkdir -p "$HOME/.config/qmd"
cat > "$HOME/.config/qmd/index.yml" << 'EOF'
# QMD Collections — una entrada por proyecto.
# Añadir aquí cada nuevo proyecto junto a su ruta de docs.

collections:
  signal:
    path: ~/dev/projects/signal/docs
    pattern: "**/*.md"
    context:
      "/": "Docs, decisiones de arquitectura y resúmenes de sesión del proyecto Signal"
      "/decisions": "ADRs — decisiones de arquitectura con contexto, alternativas y justificación"
      "/sessions": "Resúmenes de sesiones de trabajo con decisiones tomadas y próximos pasos"
EOF

echo ""
echo "✓ ~/.claude/ montado correctamente."
echo "✓ ~/.config/qmd/index.yml creado con colección 'signal'."
echo ""
echo "Siguientes pasos:"
echo "  1. brew install rtk                              (si no lo tienes)"
echo "  2. pip install codebase-memory-mcp               (o ver docs del proyecto)"
echo "  3. npm install -g @anthropic-ai/claude-code      (si no lo tienes)"
echo "  4. Desde Claude Code:"
echo "     /plugins install superpowers@claude-plugins-official"
echo "     /plugins install qmd@qmd"
echo "  5. qmd index signal                              (indexar la colección)"
echo "  6. qmd mcp --http                                (arrancar el servidor MCP)"
echo "  7. git rm -r .claude/agents/                     (limpiar agents del proyecto)"
