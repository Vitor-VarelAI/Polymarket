#!/usr/bin/env python3
"""
ExaSignal CNN Test - Teste inicial de validação
Baseado no paper: S&P 500 Stock's Movement Prediction using CNN

Objetivo: Validar se CNN pode predizer direção de preço em prediction markets
Meta: Bater coin flip (>50% accuracy)
"""

import numpy as np
import tensorflow as tf
from tensorflow import keras
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report
import asyncio
import logging
from typing import List, Tuple, Dict, Any
from datetime import datetime, timedelta

# Configuração logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MockMarketDataGenerator:
    """
    Gera dados de mercado simulados para teste
    Em produção, substituir por dados reais da Gamma/CLOB API
    """

    def __init__(self):
        self.image_size = 64

    def generate_synthetic_data(self, num_samples: int = 1000) -> Tuple[np.ndarray, np.ndarray]:
        """
        Gera dados sintéticos de mercado para teste
        Retorna: (images, labels) onde labels = 1 se price sobe, 0 se desce
        """
        images = []
        labels = []

        for _ in range(num_samples):
            # Gerar série temporal simulada (OHLC + Volume)
            time_series = self._generate_market_series()

            # Converter para imagem 64x64
            image = self._series_to_image(time_series)
            images.append(image)

            # Label: próximo movimento (sobe/desce)
            next_move = self._predict_next_move(time_series)
            labels.append(1 if next_move > 0 else 0)

        return np.array(images), np.array(labels)

    def _generate_market_series(self, length: int = 64) -> np.ndarray:
        """Gera série temporal simulada de mercado"""
        # Simular movimento browniano com tendência
        t = np.linspace(0, 1, length)
        trend = 0.1 * np.sin(2 * np.pi * t)  # tendência sinusoidal
        noise = 0.05 * np.random.randn(length)  # ruído
        volume = 1000 + 500 * np.random.rand(length)  # volume variável

        # Combinar: [price, volume]
        price = 100 + np.cumsum(trend + noise)
        return np.column_stack([price, volume])

    def _series_to_image(self, series: np.ndarray) -> np.ndarray:
        """Converte série temporal em imagem 64x64 grayscale"""
        # Normalizar para 0-255
        price_norm = (series[:, 0] - np.min(series[:, 0])) / (np.max(series[:, 0]) - np.min(series[:, 0]))
        volume_norm = (series[:, 1] - np.min(series[:, 1])) / (np.max(series[:, 1]) - np.min(series[:, 1]))

        # Criar imagem 2D (price × volume)
        image = np.zeros((self.image_size, self.image_size))

        # Mapear price para linhas, volume para intensidade
        for i, (p, v) in enumerate(zip(price_norm, volume_norm)):
            row = int(p * (self.image_size - 1))
            col = i * self.image_size // len(price_norm)
            image[row, col] = v * 255

        return image.astype(np.uint8)

    def _predict_next_move(self, series: np.ndarray) -> float:
        """Prediz próximo movimento (simplificado)"""
        # Regra simples: se tendência recente é positiva, sobe
        recent_prices = series[-10:, 0]  # últimos 10 pontos
        return recent_prices[-1] - recent_prices[0]


def build_cnn_model(image_size: int = 64) -> keras.Model:
    """
    CNN baseado no paper do S&P 500
    Adaptado para prediction markets
    """
    model = keras.Sequential([
        # Input layer
        keras.layers.Input(shape=(image_size, image_size, 1)),

        # Convolutional layers
        keras.layers.Conv2D(32, (3, 3), activation='relu', padding='same'),
        keras.layers.MaxPooling2D((2, 2)),
        keras.layers.BatchNormalization(),

        keras.layers.Conv2D(64, (3, 3), activation='relu', padding='same'),
        keras.layers.MaxPooling2D((2, 2)),
        keras.layers.BatchNormalization(),

        keras.layers.Conv2D(128, (3, 3), activation='relu', padding='same'),
        keras.layers.MaxPooling2D((2, 2)),
        keras.layers.BatchNormalization(),

        # Dense layers
        keras.layers.Flatten(),
        keras.layers.Dense(256, activation='relu'),
        keras.layers.Dropout(0.3),
        keras.layers.Dense(128, activation='relu'),
        keras.layers.Dropout(0.2),

        # Output: probabilidade de subir
        keras.layers.Dense(1, activation='sigmoid')
    ])

    # Compilar
    model.compile(
        optimizer='adam',
        loss='binary_crossentropy',
        metrics=['accuracy', keras.metrics.AUC()]
    )

    return model


def train_and_validate():
    """
    Função principal: treina CNN e valida performance
    """
    print("=" * 60)
    print("🧠 ExaSignal CNN Test - Validação Inicial")
    print("=" * 60)

    # 1. Gerar dados sintéticos
    print("📊 Gerando dados sintéticos...")
    data_gen = MockMarketDataGenerator()
    images, labels = data_gen.generate_synthetic_data(num_samples=2000)

    # Adicionar dimensão de canal (grayscale)
    images = images.reshape(images.shape + (1,)).astype(np.float32) / 255.0

    print(f"   📈 Dataset: {images.shape[0]} amostras")
    print(f"   🖼️  Imagens: {images.shape[1:]} (height x width x channels)")
    print(f"   📊 Labels: {np.sum(labels)} positivas, {len(labels) - np.sum(labels)} negativas")

    # 2. Split train/validation
    X_train, X_val, y_train, y_val = train_test_split(
        images, labels,
        test_size=0.2,
        random_state=42,
        stratify=labels
    )

    # 3. Construir modelo
    print("\n🏗️  Construindo modelo CNN...")
    model = build_cnn_model()
    model.summary()

    # 4. Treinar
    print("\n🎯 Iniciando treinamento...")
    early_stopping = keras.callbacks.EarlyStopping(
        monitor='val_accuracy',
        patience=10,
        restore_best_weights=True
    )

    history = model.fit(
        X_train, y_train,
        validation_data=(X_val, y_val),
        epochs=50,
        batch_size=32,
        callbacks=[early_stopping],
        verbose=1
    )

    # 5. Avaliar
    print("\n📊 Avaliando performance...")
    val_predictions = (model.predict(X_val) > 0.5).flatten()
    accuracy = accuracy_score(y_val, val_predictions)

    print(f"   🎯 Accuracy: {accuracy:.3f} ({accuracy*100:.1f}%)")
    print("   📈 Meta: >50% (bater coin flip)"
    print(f"   ✅ {'ATINGIU META' if accuracy > 0.5 else 'ABAIXO DA META'}")

    # 6. Classification report
    print("\n📋 Classification Report:")
    print(classification_report(y_val, val_predictions, target_names=['DOWN', 'UP']))

    # 7. Salvar modelo se bom
    if accuracy > 0.5:
        model.save('models/market_cnn_v0.h5')
        print(f"\n💾 Modelo salvo: models/market_cnn_v0.h5")
        print("   📝 Accuracy de validação: {:.1f}%".format(accuracy * 100))

    return accuracy > 0.5


def main():
    """Executa testes da CNN"""
    try:
        # Verificar TensorFlow
        print("🔍 Verificando TensorFlow...")
        print(f"   📦 TensorFlow version: {tf.__version__}")
        print(f"   🎮 GPUs disponíveis: {len(tf.config.list_physical_devices('GPU'))}")

        # Teste 1: CNN básica (1 canal)
        print("\n" + "="*60)
        print("🧠 TESTE 1: CNN Básica (1 canal)")
        print("="*60)
        success_basic = train_and_validate()

        # Teste 2: CNN multi-source (8 canais) - NOVO
        print("\n" + "="*60)
        print("🧠 TESTE 2: CNN Multi-Source (8 canais)")
        print("="*60)
        success_multi = validate_cnn_multi_source()

        if success_basic or success_multi:
            print("\n🎉 CNN mostrou potencial!")
            if success_multi and not success_basic:
                print("   📈 Multi-source teve melhor performance!")
            print("   Próximos passos:")
            print("   1. Substituir dados sintéticos por dados reais")
            print("   2. Implementar fontes externas sugeridas")
            print("   3. Integrar no pipeline principal")
        else:
            print("\n⚠️  CNN não bateu coin flip. Possíveis melhorias:")
            print("   1. Mais dados de treinamento")
            print("   2. Arquitetura diferente")
            print("   3. Features diferentes")

    except Exception as e:
        logger.error(f"Erro durante teste CNN: {e}")
        print(f"\n❌ Erro: {e}")
        print("💡 Verifique se TensorFlow está instalado: pip install tensorflow")


def validate_cnn_multi_source():
    """
    Teste CNN com múltiplas fontes de dados (8 canais)
    Baseado nas sugestões do usuário
    """
    print("🧠 Teste CNN Multi-Source (8 canais)")

    # 1. Gerar dados sintéticos com múltiplas fontes
    data_integrator = MultiSourceDataIntegrator()

    images = []
    labels = []

    for _ in range(1000):
        # Gerar dados simulados incluindo fontes externas
        mock_data = {
            'odds': np.random.randn(64),
            'volume': np.random.randn(64),
            'order_depth': np.random.randn(64),
            'whale_signals': np.random.randn(64),
            'sentiment': np.random.randn(20) * 0.5,  # -0.5 a +0.5
            'news_events': [(i*60, np.random.random()) for i in range(5)],  # Eventos aleatórios
            'whale_txs': [(i*120, np.random.exponential(500000)) for i in range(3)],  # Grandes txs
            'oracle_data': np.random.randn(64) * 0.2  # Pequenas discrepâncias
        }

        # Criar imagem 8-canais
        image = data_integrator.create_multi_channel_image(mock_data)
        images.append(image)

        # Label baseado em padrão complexo (simulando realidade)
        sentiment_signal = np.mean(mock_data['sentiment'][-5:])
        whale_signal = np.sum([tx[1] for tx in mock_data['whale_txs']]) / 10000000
        next_move = sentiment_signal + whale_signal
        labels.append(1 if next_move > 0.1 else 0)

    images = np.array(images).astype(np.float32) / 255.0
    labels = np.array(labels)

    print(f"   📊 Dataset: {images.shape[0]} amostras, {images.shape[1:]} (altura x largura x canais)")
    print(f"   📈 Labels: {np.sum(labels)} positivas, {len(labels) - np.sum(labels)} negativas")

    # 2. Split e treinar
    X_train, X_val, y_train, y_val = train_test_split(images, labels, test_size=0.2, random_state=42)

    # 3. Construir CNN para 8 canais
    model = build_cnn_multi_channel(input_channels=8)

    # 4. Treinar
    history = model.fit(
        X_train, y_train,
        validation_data=(X_val, y_val),
        epochs=20,
        batch_size=32,
        verbose=0
    )

    # 5. Avaliar
    val_predictions = (model.predict(X_val, verbose=0) > 0.5).flatten()
    accuracy = accuracy_score(y_val, val_predictions)

    print(".1f"    print(".1f"
    return accuracy > 0.5


class MultiSourceDataIntegrator:
    """
    Integra múltiplas fontes de dados para CNN
    Baseado nas sugestões: sentiment, news, on-chain, oracles
    """

    def __init__(self):
        self.image_size = 64

    def create_multi_channel_image(self, market_data):
        """
        Cria imagem com 8 canais baseada nas sugestões do usuário

        Canais:
        0-3: Market data (odds, volume, depth, whales)
        4: Sentiment (Stocktwits/X)
        5: News flags (Newsquawk/Bloomberg)
        6: On-chain whales (Etherscan/Whale Alert)
        7: Oracle discrepancy (UMA/Chainlink)
        """
        channels = []

        # Canais básicos (mercado)
        channels.extend(self._encode_market_data(market_data))

        # Novos canais sugeridos
        channels.extend(self._encode_external_sources(market_data))

        # Stack em array 3D
        return np.stack(channels, axis=-1)  # (64, 64, 8)

    def _encode_market_data(self, data):
        """Canais 0-3: Dados básicos do mercado"""
        return [
            self._normalize_series(data.get('odds', np.random.randn(self.image_size))),
            self._normalize_series(data.get('volume', np.random.randn(self.image_size))),
            self._normalize_series(data.get('order_depth', np.random.randn(self.image_size))),
            self._normalize_series(data.get('whale_signals', np.random.randn(self.image_size)))
        ]

    def _encode_external_sources(self, data):
        """Canais 4-7: Fontes externas sugeridas"""
        return [
            self._encode_sentiment(data.get('sentiment', [])),      # Stocktwits/X
            self._encode_news_flags(data.get('news_events', [])),    # Newsquawk
            self._encode_onchain_whales(data.get('whale_txs', [])),  # Etherscan
            self._encode_oracle_data(data.get('oracle_data', []))    # UMA/Chainlink
        ]

    def _encode_sentiment(self, sentiment_data):
        """Canal 4: Sentiment aggregators"""
        sentiment_layer = np.zeros((self.image_size, self.image_size), dtype=np.uint8)
        if sentiment_data:
            for i, sentiment in enumerate(sentiment_data[:self.image_size]):
                sentiment_norm = int((sentiment + 1) * 127.5)  # -1/+1 -> 0/255
                sentiment_layer[i, :] = sentiment_norm
        return sentiment_layer

    def _encode_news_flags(self, news_events):
        """Canal 5: News terminals"""
        news_layer = np.zeros((self.image_size, self.image_size), dtype=np.uint8)
        for event_time, importance in news_events:
            x_pos = int((event_time % 3600) / 3600 * self.image_size)
            news_layer[:, x_pos] = min(importance * 255, 255)
        return news_layer

    def _encode_onchain_whales(self, whale_transactions):
        """Canal 6: On-chain whale data"""
        whale_layer = np.zeros((self.image_size, self.image_size), dtype=np.uint8)
        for tx_time, tx_amount in whale_transactions:
            x_pos = int((tx_time % 3600) / 3600 * self.image_size)
            intensity = min(tx_amount / 1000000 * 255, 255)
            whale_layer[:, x_pos] += intensity
        return whale_layer

    def _encode_oracle_data(self, oracle_data):
        """Canal 7: Oracle discrepancy"""
        oracle_layer = np.zeros((self.image_size, self.image_size), dtype=np.uint8)
        for i, discrepancy in enumerate(oracle_data[:self.image_size]):
            disc_norm = int((discrepancy + 1) * 127.5)
            oracle_layer[i, :] = disc_norm
        return oracle_layer

    def _normalize_series(self, series):
        """Converte série temporal em imagem grayscale"""
        series = np.array(series)
        if len(series) == 0 or np.all(series == series[0]):
            return np.full((self.image_size, self.image_size), 128, dtype=np.uint8)

        min_val, max_val = np.min(series), np.max(series)
        normalized = ((series - min_val) / (max_val - min_val) * 255).astype(np.uint8)

        # Criar imagem 2D (repetir série verticalmente)
        image = np.tile(normalized.reshape(-1, 1), (1, self.image_size))
        return image


def build_cnn_multi_channel(input_channels=8):
    """CNN adaptada para múltiplos canais"""
    model = tf.keras.Sequential([
        tf.keras.layers.Input(shape=(64, 64, input_channels)),
        tf.keras.layers.Conv2D(32, (3, 3), activation='relu', padding='same'),
        tf.keras.layers.MaxPooling2D((2, 2)),
        tf.keras.layers.BatchNormalization(),
        tf.keras.layers.Conv2D(64, (3, 3), activation='relu', padding='same'),
        tf.keras.layers.MaxPooling2D((2, 2)),
        tf.keras.layers.BatchNormalization(),
        tf.keras.layers.Flatten(),
        tf.keras.layers.Dense(128, activation='relu'),
        tf.keras.layers.Dropout(0.3),
        tf.keras.layers.Dense(1, activation='sigmoid')
    ])

    model.compile(optimizer='adam', loss='binary_crossentropy', metrics=['accuracy'])
    return model


if __name__ == "__main__":
    main()
