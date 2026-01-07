#!/usr/bin/env python3
"""
Script para testar conexões com APIs necessárias para o ExaSignal.
Execute este script após configurar suas variáveis de ambiente.
"""

import asyncio
import os
import sys
from pathlib import Path

# Adicionar src ao path
sys.path.insert(0, str(Path(__file__).parent / "src"))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("⚠️  python-dotenv não instalado. Instale com: pip install python-dotenv")
    print("   Continuando sem carregar .env...")

# Verificar variáveis de ambiente
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
EXA_API_KEY = os.getenv("EXA_API_KEY")


async def test_telegram():
    """Testa conexão com Telegram Bot API."""
    print("\n📱 Testando Telegram Bot API...")
    
    if not TELEGRAM_BOT_TOKEN:
        print("   ❌ TELEGRAM_BOT_TOKEN não encontrado no .env")
        print("   💡 Obtenha em: https://t.me/BotFather")
        return False
    
    try:
        from telegram import Bot
        
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        me = await bot.get_me()
        
        print(f"   ✅ Conectado com sucesso!")
        print(f"   📋 Bot: @{me.username} ({me.first_name})")
        print(f"   🆔 ID: {me.id}")
        return True
        
    except ImportError:
        print("   ❌ python-telegram-bot não instalado")
        print("   💡 Instale com: pip install python-telegram-bot")
        return False
    except Exception as e:
        print(f"   ❌ Erro ao conectar: {e}")
        print("   💡 Verifique se o token está correto")
        return False


def test_exa():
    """Testa conexão com Exa API."""
    print("\n🔍 Testando Exa API...")
    
    if not EXA_API_KEY:
        print("   ❌ EXA_API_KEY não encontrado no .env")
        print("   💡 Obtenha em: https://exa.ai/")
        return False
    
    try:
        from exa_py import Exa
        
        exa = Exa(api_key=EXA_API_KEY)
        
        # Teste simples de pesquisa
        print("   🔎 Executando pesquisa de teste...")
        results = exa.search(
            "AI expert prediction 2025",
            num_results=1,
            use_autoprompt=True
        )
        
        print(f"   ✅ Conectado com sucesso!")
        print(f"   📊 Resultados encontrados: {len(results.results)}")
        if results.results:
            print(f"   📄 Primeiro resultado: {results.results[0].title[:50]}...")
        return True
        
    except ImportError:
        print("   ❌ exa-py não instalado")
        print("   💡 Instale com: pip install exa-py")
        return False
    except Exception as e:
        print(f"   ❌ Erro ao conectar: {e}")
        print("   💡 Verifique se a API key está correta e se tem créditos")
        return False


def test_polymarket():
    """Testa acesso à Polymarket/Gamma API."""
    print("\n📊 Testando Polymarket/Gamma API...")
    
    try:
        import httpx
        
        # Teste com endpoint público do Gamma
        print("   🔎 Testando endpoint público...")
        
        # Exemplo de endpoint (pode variar)
        # Você precisará ajustar conforme a documentação atual
        test_url = "https://gamma.io/api/v1/markets"
        
        try:
            response = httpx.get(test_url, timeout=10)
            if response.status_code == 200:
                print("   ✅ Endpoint acessível")
                return True
            else:
                print(f"   ⚠️  Status: {response.status_code}")
                print("   💡 Pode ser necessário autenticação ou endpoint diferente")
                return False
        except httpx.RequestError as e:
            print(f"   ⚠️  Erro de conexão: {e}")
            print("   💡 Verifique sua conexão ou documentação da API")
            return False
            
    except ImportError:
        print("   ⚠️  httpx não instalado")
        print("   💡 Instale com: pip install httpx")
        return False


def check_requirements():
    """Verifica se todas as dependências estão instaladas."""
    print("\n📦 Verificando dependências...")
    
    required = {
        "python-telegram-bot": "telegram",
        "exa-py": "exa_py",
        "httpx": "httpx",
        "pyyaml": "yaml",
        "python-dotenv": "dotenv",
    }
    
    missing = []
    for package, module in required.items():
        try:
            __import__(module)
            print(f"   ✅ {package}")
        except ImportError:
            print(f"   ❌ {package} não instalado")
            missing.append(package)
    
    if missing:
        print(f"\n   💡 Instale com: pip install {' '.join(missing)}")
        return False
    
    return True


def check_files():
    """Verifica se arquivos necessários existem."""
    print("\n📁 Verificando arquivos...")
    
    files = {
        ".env": "Variáveis de ambiente",
        "markets.yaml": "Configuração de mercados",
        "requirements.txt": "Dependências Python",
    }
    
    all_exist = True
    for file, desc in files.items():
        if Path(file).exists():
            print(f"   ✅ {file} ({desc})")
        else:
            print(f"   ⚠️  {file} não encontrado ({desc})")
            if file == ".env":
                print(f"      💡 Copie de .env.example e preencha")
            elif file == "markets.yaml":
                print(f"      💡 Copie de markets.yaml.example e edite")
            all_exist = False
    
    return all_exist


async def main():
    """Executa todos os testes."""
    print("=" * 60)
    print("🧪 ExaSignal — Teste de Conexões")
    print("=" * 60)
    
    # Verificar arquivos
    files_ok = check_files()
    
    # Verificar dependências
    deps_ok = check_requirements()
    
    if not deps_ok:
        print("\n⚠️  Instale as dependências antes de continuar")
        return
    
    # Testar APIs
    telegram_ok = await test_telegram()
    exa_ok = test_exa()
    polymarket_ok = test_polymarket()
    
    # Resumo
    print("\n" + "=" * 60)
    print("📊 Resumo dos Testes")
    print("=" * 60)
    print(f"   Arquivos: {'✅' if files_ok else '⚠️'}")
    print(f"   Dependências: {'✅' if deps_ok else '❌'}")
    print(f"   Telegram Bot: {'✅' if telegram_ok else '❌'}")
    print(f"   Exa API: {'✅' if exa_ok else '❌'}")
    print(f"   Polymarket API: {'✅' if polymarket_ok else '⚠️'}")
    print("=" * 60)
    
    # Status final
    critical_ok = telegram_ok and exa_ok
    
    if critical_ok:
        print("\n✅ Conexões críticas funcionando!")
        print("🚀 Você está pronto para começar a implementação!")
    else:
        print("\n❌ Algumas conexões críticas falharam")
        print("💡 Verifique:")
        print("   1. Variáveis de ambiente no .env")
        print("   2. Chaves de API válidas")
        print("   3. Dependências instaladas")
        print("\n📖 Consulte SETUP_GUIDE.md para mais detalhes")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Teste interrompido pelo usuário")
    except Exception as e:
        print(f"\n\n❌ Erro inesperado: {e}")
        import traceback
        traceback.print_exc()

