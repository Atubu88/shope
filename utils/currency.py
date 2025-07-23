CURRENCY_SYMBOLS = {
    "RUB": "₽",
    "USD": "$",
    "EUR": "€",
    "UAH": "₴",
    "KZT": "₸",
    "KGS": "с",
    "AED": "د.إ",
}

def get_currency_symbol(code: str) -> str:
    return CURRENCY_SYMBOLS.get(code.upper(), code)
