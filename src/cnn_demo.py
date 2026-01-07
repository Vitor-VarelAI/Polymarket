#!/usr/bin/env python3
"""
ExaSignal CNN Demo - Demonstração da Integração Multi-Source
Mostra como as fontes sugeridas pelo usuário são integradas na CNN

Sem TensorFlow - apenas demonstra o conceito e estrutura de dados
"""

import numpy as np
from typing import Dict, List, Tuple
import random


class MultiSourceDemo:
    """
    Demonstração da integração multi-source sem precisar TensorFlow
    Mostra como as 4 fontes sugeridas são estruturadas em 8 canais
    """

    def __init__(self):
        self.image_size = 8  # Usando 8x8 para demo (não 64x64)
        print("🧠 ExaSignal CNN Multi-Source Demo")
        print("=" * 50)

    def simulate_market_scenario(self) -> Dict:
        """
        Simula um cenário de mercado com todas as fontes de dados
        """
        print("\n📊 Simulando cenário de mercado...")

        # Cenário: Election market com whale activity
        scenario = {
            'market': 'US Election Winner',
            'current_odds': 0.55,  # 55% chance Biden
            'volume': 2500000,     # $2.5M volume
            'whale_trade': {
                'size': 150000,   # $150k trade
                'direction': 'YES',
                'time_ago': 30    # 30 minutes ago
            }
        }

        # Fontes externas simuladas
        external_data = {
            'sentiment': self._simulate_sentiment(),
            'news_events': self._simulate_news(),
            'onchain_whales': self._simulate_onchain(),
            'oracle_data': self._simulate_oracle(scenario['current_odds'])
        }

        return {**scenario, **external_data}

    def _simulate_sentiment(self) -> List[float]:
        """Simula dados de sentiment (Stocktwits/X)"""
        # Mistura de sinais positivos/negativos
        sentiment = []
        for _ in range(20):
            # Simula "noise" que precede price spikes
            base_sentiment = np.random.normal(0, 0.3)
            # Adiciona "spike" recente
            if random.random() < 0.3:
                base_sentiment += random.choice([-0.8, 0.8])
            sentiment.append(base_sentiment)
        return sentiment

    def _simulate_news(self) -> List[Tuple[float, float]]:
        """Simula eventos de news terminals"""
        events = []
        # Simula alguns eventos importantes
        event_types = [
            (1800, 0.9),  # Polling data 30min ago, high importance
            (3600, 0.7),  # Speech 1h ago, medium importance
            (7200, 0.3),  # Minor news 2h ago, low importance
        ]
        return event_types

    def _simulate_onchain(self) -> List[Tuple[float, float]]:
        """Simula dados on-chain de whales"""
        transactions = []
        # Simula algumas transações grandes
        tx_sizes = [50000, 120000, 80000, 200000]  # $50k, $120k, $80k, $200k
        for i, size in enumerate(tx_sizes):
            time_ago = (i + 1) * 900  # Cada 15min
            transactions.append((time_ago, size))
        return transactions

    def _simulate_oracle(self, current_odds: float) -> List[float]:
        """Simula dados de oracles (discrepancy)"""
        # Simula diferença entre odds do mercado vs dados reais
        real_probability = 0.58  # Dados reais mostram 58%
        discrepancy = current_odds - real_probability  # -0.03 (mercado subestima)

        # Histórico de discrepâncias
        discrepancies = []
        for i in range(24):  # Últimas 24 horas
            # Discrepância varia ao longo do tempo
            noise = np.random.normal(0, 0.02)
            historical_disc = discrepancy + noise
            discrepancies.append(historical_disc)

        return discrepancies

    def create_multi_channel_image(self, data: Dict) -> np.ndarray:
        """
        Cria imagem 8-canais baseada nas fontes de dados
        Demonstra como cada fonte vira um canal visual
        """
        print("\n🎨 Criando imagem multi-canal (8 canais)...")

        channels = []

        # Canal 0-3: Dados básicos do mercado
        channels.extend(self._encode_basic_market_data(data))

        # Canal 4-7: Fontes externas sugeridas
        channels.extend(self._encode_external_sources(data))

        # Stack em array 3D: (altura, largura, canais)
        image = np.stack(channels, axis=-1)

        print(f"   📐 Imagem criada: {image.shape} (altura x largura x canais)")
        print(f"   🎯 8 canais integrados das fontes sugeridas")

        return image

    def _encode_basic_market_data(self, data: Dict) -> List[np.ndarray]:
        """Canais 0-3: Odds, Volume, Order Depth, Whale Signals"""
        channels = []

        # Canal 0: Odds history (simulado)
        odds_history = np.random.normal(data['current_odds'], 0.05, self.image_size)
        channels.append(self._series_to_image(odds_history, "Odds History"))

        # Canal 1: Volume
        volume_history = np.random.exponential(data['volume']/10, self.image_size)
        channels.append(self._series_to_image(volume_history, "Volume"))

        # Canal 2: Order depth
        depth_history = np.random.normal(0.5, 0.1, self.image_size)
        channels.append(self._series_to_image(depth_history, "Order Depth"))

        # Canal 3: Whale signals
        whale_signals = np.zeros(self.image_size)
        trade_idx = int(data['whale_trade']['time_ago'] / 60)  # Minutos para índice
        if trade_idx < self.image_size:
            whale_signals[trade_idx] = data['whale_trade']['size'] / 100000  # Normalizado
        channels.append(self._series_to_image(whale_signals, "Whale Signals"))

        return channels

    def _encode_external_sources(self, data: Dict) -> List[np.ndarray]:
        """Canais 4-7: Fontes externas sugeridas"""
        channels = []

        # Canal 4: Sentiment (Stocktwits/X)
        sentiment_channel = self._encode_sentiment(data['sentiment'])
        channels.append(sentiment_channel)

        # Canal 5: News flags (Newsquawk/Bloomberg)
        news_channel = self._encode_news_flags(data['news_events'])
        channels.append(news_channel)

        # Canal 6: On-chain whales (Etherscan/Whale Alert)
        onchain_channel = self._encode_onchain_whales(data['onchain_whales'])
        channels.append(onchain_channel)

        # Canal 7: Oracle discrepancy (UMA/Chainlink)
        oracle_channel = self._encode_oracle_data(data['oracle_data'])
        channels.append(oracle_channel)

        return channels

    def _encode_sentiment(self, sentiment_data: List[float]) -> np.ndarray:
        """Canal 4: Sentiment aggregators"""
        print("   📈 Canal 4: Sentiment (Stocktwits/X)")

        channel = np.zeros((self.image_size, self.image_size), dtype=np.uint8)

        for i, sentiment in enumerate(sentiment_data[:self.image_size]):
            # Converte sentiment (-1/+1) para grayscale (0-255)
            intensity = int((sentiment + 1) * 127.5)
            intensity = np.clip(intensity, 0, 255)
            channel[i, :] = intensity

        return channel

    def _encode_news_flags(self, news_events: List[Tuple[float, float]]) -> np.ndarray:
        """Canal 5: News terminals"""
        print("   📰 Canal 5: News Flags (Newsquawk/Bloomberg)")

        channel = np.zeros((self.image_size, self.image_size), dtype=np.uint8)

        for time_ago, importance in news_events:
            # Converte tempo para posição X
            x_pos = int((time_ago / 3600) * self.image_size)  # Última hora
            if x_pos < self.image_size:
                intensity = int(importance * 255)
                channel[:, x_pos] = intensity

        return channel

    def _encode_onchain_whales(self, whale_txs: List[Tuple[float, float]]) -> np.ndarray:
        """Canal 6: On-chain whale data"""
        print("   🐋 Canal 6: On-Chain Whales (Etherscan/Whale Alert)")

        channel = np.zeros((self.image_size, self.image_size), dtype=np.uint8)

        for time_ago, amount in whale_txs:
            x_pos = int((time_ago / 3600) * self.image_size)
            if x_pos < self.image_size:
                # Normaliza grandes transações para 0-255
                intensity = min(amount / 10000, 255)  # $100k = 255
                channel[:, x_pos] += int(intensity)

        return channel

    def _encode_oracle_data(self, oracle_data: List[float]) -> np.ndarray:
        """Canal 7: Oracle discrepancy"""
        print("   🔮 Canal 7: Oracle Discrepancy (UMA/Chainlink)")

        channel = np.zeros((self.image_size, self.image_size), dtype=np.uint8)

        for i, discrepancy in enumerate(oracle_data[:self.image_size]):
            # Converte discrepância para intensidade visual
            intensity = int((discrepancy + 0.1) * 1275)  # -0.1/+0.1 range
            intensity = np.clip(intensity, 0, 255)
            channel[i, :] = intensity

        return channel

    def _series_to_image(self, series: np.ndarray, name: str) -> np.ndarray:
        """Converte série temporal em imagem 2D"""
        # Normaliza para 0-255
        if np.max(series) == np.min(series):
            normalized = np.full_like(series, 128, dtype=np.uint8)
        else:
            normalized = ((series - np.min(series)) / (np.max(series) - np.min(series)) * 255).astype(np.uint8)

        # Cria imagem 2D (repetindo horizontalmente)
        image = np.tile(normalized.reshape(-1, 1), (1, self.image_size))
        return image

    def analyze_image(self, image: np.ndarray) -> Dict:
        """
        Análise simulada do que a CNN "veria" na imagem
        """
        print("\n🤖 Análise CNN Simulada:")
        print(f"   📊 Estatísticas da imagem: {image.shape}")

        analysis = {
            'canal_stats': {},
            'patterns_detected': [],
            'confidence_score': 0.0
        }

        # Análise por canal
        channel_names = [
            'Odds', 'Volume', 'Order Depth', 'Whale Signals',
            'Sentiment', 'News Flags', 'On-Chain Whales', 'Oracle Discrepancy'
        ]

        for i, name in enumerate(channel_names):
            channel_data = image[:, :, i]
            analysis['canal_stats'][name] = {
                'mean': float(np.mean(channel_data)),
                'std': float(np.std(channel_data)),
                'max': int(np.max(channel_data)),
                'min': int(np.min(channel_data))
            }

        # Detecção de padrões simulada
        sentiment_channel = image[:, :, 4]
        news_channel = image[:, :, 5]
        whale_channel = image[:, :, 6]

        # Padrão 1: Sentiment spike + News event
        if np.max(sentiment_channel) > 200 and np.max(news_channel) > 150:
            analysis['patterns_detected'].append("Sentiment spike com news event")

        # Padrão 2: On-chain accumulation
        if np.mean(whale_channel) > 50:
            analysis['patterns_detected'].append("On-chain whale accumulation")

        # Padrão 3: Oracle discrepancy
        oracle_channel = image[:, :, 7]
        if np.std(oracle_channel) > 30:
            analysis['patterns_detected'].append("Oracle discrepancy detected")

        # Confidence score baseado nos padrões
        base_confidence = 0.5
        pattern_bonus = len(analysis['patterns_detected']) * 0.1
        analysis['confidence_score'] = min(base_confidence + pattern_bonus, 0.9)

        return analysis

    def run_demo(self):
        """Executa demonstração completa"""
        try:
            # Simula cenário
            market_data = self.simulate_market_scenario()

            print(f"\n🏛️  Mercado: {market_data['market']}")
            print(f"📊 Odds atuais: {market_data['current_odds']:.1%}")
            print(f"💰 Volume: ${market_data['volume']:,.0f}")
            print(f"🐋 Whale trade: ${market_data['whale_trade']['size']:,.0f} ({market_data['whale_trade']['direction']})")

            # Cria imagem multi-canal
            multi_channel_image = self.create_multi_channel_image(market_data)

            # Análise simulada
            analysis = self.analyze_image(multi_channel_image)

            print("\n📈 Padrões detectados:")
            for pattern in analysis['patterns_detected']:
                print(f"   ✅ {pattern}")

            print(f"\n🎯 Confidence Score: {analysis['confidence_score']:.1%}")
            print("   📝 Baseado em sinais multi-source")

            # Resumo dos benefícios
            print("\n🎉 Benefícios da Integração Multi-Source:")
            print("   ✅ Detecção mais robusta (8 canais vs 4)")
            print("   ✅ Sinais precoces de sentiment + on-chain")
            print("   ✅ Contexto de news + oracle validation")
            print("   ✅ Redução de falsos positivos")
            print("   ✅ Melhor timing de alertas")
            return True

        except Exception as e:
            print(f"❌ Erro na demo: {e}")
            return False


def main():
    """Função principal da demo"""
    demo = MultiSourceDemo()
    success = demo.run_demo()

    if success:
        print("\n✅ Demo concluída com sucesso!")
        print("💡 Próximos passos:")
        print("   1. Instalar TensorFlow: pip install tensorflow")
        print("   2. Executar teste real: python src/cnn_test.py")
        print("   3. Integrar APIs reais das fontes externas")
    else:
        print("\n❌ Demo falhou")


if __name__ == "__main__":
    main()
