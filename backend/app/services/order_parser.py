"""Interpreta a mensagem de texto do WhatsApp e extrai itens de pedido.

Formatos aceitos (um item por linha):
    "2x Pizza Calabresa"
    "2 x pizza calabresa"
    "1 Coca Lata"
    "Pizza Calabresa"      -> quantidade 1

Este parser simples por regex é o MVP; futuramente pode ser substituído
por um classificador com LLM mantendo a mesma interface (Open/Closed).
"""
import re
from dataclasses import dataclass

# Ex.: "2x Pizza", "2 X Pizza", "10 Pizza"
_LINE_PATTERN = re.compile(r"^\s*(?:(\d+)\s*[xX]?\s+)?(.+?)\s*$")


@dataclass(frozen=True)
class ParsedItem:
    """Item extraído da mensagem: nome livre + quantidade."""

    product_name: str
    quantity: int


def parse_order_message(message: str) -> list[ParsedItem]:
    """Extrai itens de pedido de uma mensagem de texto livre."""
    items: list[ParsedItem] = []
    for line in message.splitlines():
        line = line.strip()
        if not line:
            continue
        match = _LINE_PATTERN.match(line)
        if not match:
            continue
        quantity = int(match.group(1)) if match.group(1) else 1
        name = match.group(2).strip()
        if name and quantity > 0:
            items.append(ParsedItem(product_name=name, quantity=quantity))
    return items
