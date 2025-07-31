from typing import Dict, List
import requests


class DominanceService:
    """Obtiene la dominancia de mercado de criptomonedas usando la API pública de CoinGecko."""

    COINGECKO_URL = "https://api.coingecko.com/api/v3/global"

    # Mapeo simple para permitir sinónimos comunes
    SYMBOL_MAP = {
        "btc": "btc",
        "bitcoin": "btc",
        "eth": "eth",
        "ethereum": "eth",
        "usdt": "usdt",
        "tether": "usdt",
        "bnb": "bnb",
    }

    def fetch(self, coins: List[str]) -> Dict[str, float]:
        response = requests.get(self.COINGECKO_URL, timeout=10)
        response.raise_for_status()
        data = response.json()
        percentages: Dict[str, float] = data.get("data", {}).get("market_cap_percentage", {})

        result: Dict[str, float] = {}
        for coin in coins:
            key = self.SYMBOL_MAP.get(coin.lower(), coin.lower())
            value = percentages.get(key)
            if value is not None:
                result[key] = round(value, 2)
        return result
