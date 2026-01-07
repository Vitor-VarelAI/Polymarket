#!/bin/bash
# ===========================================
# ExaSignal - Script de Execução
# ===========================================

set -e

# Verificar ambiente virtual
if [ ! -d "venv" ]; then
    echo "🔧 Criando ambiente virtual..."
    python3 -m venv venv
fi

# Ativar venv
source venv/bin/activate

# Instalar dependências
echo "📦 Instalando dependências..."
pip install -r requirements.txt -q

# Verificar .env
if [ ! -f ".env" ]; then
    echo "⚠️  Ficheiro .env não encontrado!"
    echo "   Copie .env.example para .env e configure as variáveis."
    exit 1
fi

# Modo de execução
MODE=${1:-daemon}

if [ "$MODE" = "once" ]; then
    echo "🔍 Executando uma vez (modo teste)..."
    python -m src.main --once
elif [ "$MODE" = "daemon" ]; then
    echo "🚀 Iniciando em modo daemon (24/7)..."
    python -m src.main
else
    echo "Uso: ./scripts/run.sh [daemon|once]"
    exit 1
fi
