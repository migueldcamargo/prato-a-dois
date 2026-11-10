#!/usr/bin/env bash
# Recria o banco de teste local "prato" com a imitação do Supabase (shim.sql) e o supabase.sql do repositório.
# Variáveis: PGHOST (padrão /tmp), PGPORT (54329), PGUSER (postgres), PRATO_DB (prato).
set -euo pipefail
cd "$(dirname "$0")/.."
export PGHOST="${PGHOST:-/tmp}" PGPORT="${PGPORT:-54329}" PGUSER="${PGUSER:-postgres}"
DB="${PRATO_DB:-prato}"
P="psql -v ON_ERROR_STOP=1 -q"
$P -c "drop database if exists $DB" -c "create database $DB" >/dev/null 2>&1
$P -d "$DB" -f dev/shim.sql
$P -d "$DB" -f supabase.sql >/dev/null 2>&1
echo "banco $DB recriado (versão $(psql -d "$DB" -tAc 'select public.versao_banco()'))"
