#!/usr/bin/env bash
# Wait for GraphDB to be ready, create the repository, and import the KG.
# Run after `docker compose up -d`:
#   docker compose exec viewsari bash /app/scripts/setup_graphdb.sh
# Or from host:
#   bash scripts/setup_graphdb.sh

set -euo pipefail

GRAPHDB_URL="${GRAPHDB_URL:-http://localhost:7200}"
REPO="${GRAPHDB_REPO:-viewsari}"
TTL_FILE="viewsari_kg.ttl"

echo "Waiting for GraphDB at ${GRAPHDB_URL} ..."
until curl -sf "${GRAPHDB_URL}/rest/repositories" > /dev/null 2>&1; do
  sleep 2
done
echo "GraphDB is up."

# Check if repository exists
if curl -sf "${GRAPHDB_URL}/rest/repositories/${REPO}" > /dev/null 2>&1; then
  echo "Repository '${REPO}' already exists."
else
  echo "Creating repository '${REPO}' ..."
  curl -sf -X POST "${GRAPHDB_URL}/rest/repositories" \
    -H "Content-Type: application/json" \
    -d "{
      \"id\": \"${REPO}\",
      \"title\": \"Viewsari Knowledge Graph\",
      \"type\": \"graphdb\",
      \"params\": {
        \"ruleset\": { \"value\": \"rdfsplus-optimized\" },
        \"disableSameAs\": { \"value\": \"true\" }
      }
    }"
  echo " done."
fi

# Check if data is already loaded
COUNT=$(curl -sf "${GRAPHDB_URL}/repositories/${REPO}" \
  -H "Accept: application/sparql-results+json" \
  --data-urlencode "query=SELECT (COUNT(*) AS ?c) WHERE { ?s ?p ?o }" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['results']['bindings'][0]['c']['value'])" 2>/dev/null || echo "0")

if [ "${COUNT}" -gt 1000 ]; then
  echo "Repository already has ${COUNT} triples. Skipping import."
else
  echo "Importing ${TTL_FILE} from server import directory ..."
  curl -sf -X POST \
    "${GRAPHDB_URL}/rest/repositories/${REPO}/import/server" \
    -H "Content-Type: application/json" \
    -d "{\"fileNames\": [\"${TTL_FILE}\"]}"
  echo "Import triggered. Waiting for completion ..."
  sleep 5
  # Poll until import finishes
  for i in $(seq 1 60); do
    NEW_COUNT=$(curl -sf "${GRAPHDB_URL}/repositories/${REPO}" \
      -H "Accept: application/sparql-results+json" \
      --data-urlencode "query=SELECT (COUNT(*) AS ?c) WHERE { ?s ?p ?o }" \
      | python3 -c "import sys,json; print(json.load(sys.stdin)['results']['bindings'][0]['c']['value'])" 2>/dev/null || echo "0")
    echo "  triples: ${NEW_COUNT}"
    if [ "${NEW_COUNT}" -gt 100000 ]; then
      echo "Import complete. ${NEW_COUNT} triples loaded."
      break
    fi
    sleep 5
  done
fi

echo "GraphDB ready at ${GRAPHDB_URL}/repositories/${REPO}"
