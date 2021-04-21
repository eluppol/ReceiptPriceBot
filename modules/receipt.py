import logging
import re
from enum import Enum

logger = logging.getLogger()


class Receipt:
    def __init__(self, items, taxes, subtotal, total):
        self.items = items
        self.taxes = taxes
        self.subtotal = subtotal
        self.total = total


class ReceiptBuilder:
    def __init__(self):
        self.subtotal = 0
        self.total = 0
        self.items = []
        self.taxes = []
        self.subtotal_set = False
        self.total_set = False

    def add_item(self, item):
        self.items.append(item)
        return self

    def add_tax(self, item):
        self.taxes.append(item)
        return self

    def add_subtotal(self, subtotal):
        self.subtotal = subtotal
        self.subtotal_set = True
        return self

    def add_total(self, total):
        self.total = total
        self.total_set = True
        return self

    def build(self):
        if not (self.items and self.subtotal and self.total):
            raise Exception(
                f"Cannot build receipt because not all elements are present: {self.items}, {self.taxes}, {self.subtotal}, {self.total}")

        adjustment = self.total / self.subtotal
        for item in self.items:
            item.price *= adjustment
        return Receipt(self.items, self.taxes, self.subtotal, self.total)


class Priced:
    def __init__(self, name, price):
        self.name = name
        self.price = price

    def __str__(self):
        return f"{self.name}\t|\t{self.price:.2f}"


class Item(Priced):
    def __init__(self, name, description, quantity, cost):
        super().__init__(name, cost / quantity)
        self.quantity = quantity
        self.description = description

    def __str__(self):
        return f"{self.quantity}x\t|\t{self.name}\t|\t{self.price:.2f} each"


class PricedBuilder:
    def __init__(self):
        self.price = 0
        self.name = ''
        self.price_set = False

    def add_price(self, price):
        self.price = price
        self.price_set = True
        return self

    def add_name(self, name):
        self.name = name
        return self

    def build(self):
        if not self.name:
            raise Exception(f"Cannot build priced, because name is not specified: {self.name}")
        return Priced(self.name, self.price)


class ItemBuilder(PricedBuilder):
    def __init__(self, quantity):
        super().__init__()
        self.description = ''
        self.quantity = quantity

    def add_description(self, description):
        self.description = description
        return self

    def build(self):
        if not (self.name and self.quantity and self.price_set):
            raise Exception(
                f"Cannot build item, because either name, quantity or price is not specified: {self.name}, {self.quantity}, {self.price}")
        return Item(self.name, self.description, self.quantity, self.price)


class TokenType(Enum):
    NUMBER = 1
    WORD = 2
    PRICE = 3


class ReceiptItemType(Enum):
    QUANTITY = 1
    NAME = 2
    DESCRIPTION = 3
    TAX = 4
    SUBTOTAL = 5
    TOTAL = 6
    PRICE = 7


def parse_receipt(text):
    x_in_number = re.search("[\\n^][0-9]+x\\s", text)
    return [[match(token, x_in_number) for token in re.split('[;|!@\\s]', line.strip()) if token]
            for line in text.split('\n')
            if line]


def match(token: str, x_in_number):
    logger.debug(f"token: {token}")

    if token.startswith('$'):
        try:
            return TokenType.PRICE, float(re.sub('[,:;\\-]', '.', token[1:]))
        except ValueError:
            return TokenType.PRICE, 0.0
    else:
        quantity = re.sub('[.,°]', '', token)
        if x_in_number:
            if quantity and quantity[-1] == 'x':
                quantity = quantity[:-1]
            else:
                return TokenType.WORD, token

        if quantity.isnumeric():
            return TokenType.NUMBER, int(quantity)
        else:
            return TokenType.WORD, token


def annotate_receipt(parsed_receipt):
    logger.debug(f"Parsed receipt: {parsed_receipt}")
    result = []
    passed_subtotal = False
    passed_total = False
    for line in parsed_receipt:
        if not line:
            continue
        logger.debug(f"annotating: {line}")
        if line[0][0] == TokenType.WORD and str(line[0][1]).lower() == "total" and len(line) < 3 and (
                len(line) == 1 or line[1][0] == TokenType.PRICE):
            result.append((ReceiptItemType.TOTAL,))
            if len(line) == 2:
                result.append((ReceiptItemType.PRICE, line[1][1]))
            passed_total = True
            continue

        if line[0][0] == TokenType.WORD and str(line[0][1]).lower() == "subtotal" and len(line) < 3 and (
                len(line) == 1 or line[1][0] == TokenType.PRICE):
            result.append((ReceiptItemType.SUBTOTAL,))
            if len(line) == 2:
                result.append((ReceiptItemType.PRICE, line[1][1]))
            passed_subtotal = True
            continue

        if not passed_total:
            no_quantity = False
            name_list = []
            if line[0][0] == TokenType.NUMBER:
                result.append((ReceiptItemType.QUANTITY, line[0][1]))
            else:
                no_quantity = True
                name_list.append(line[0][1])

            if len(line) > 2:
                name_list += [str(x[1]) for x in line[1:-1]]

            add_price = False
            if len(line) > 1:
                if line[-1][0] == TokenType.PRICE:
                    add_price = True
                else:
                    name_list.append(line[-1][1])

            if name_list:
                name = ' '.join(name_list)
                current_type = ReceiptItemType.NAME
                if no_quantity:
                    if passed_subtotal:
                        current_type = ReceiptItemType.TAX
                    else:
                        current_type = ReceiptItemType.DESCRIPTION

                if not current_type == ReceiptItemType.DESCRIPTION or result:
                    result.append((current_type, name))

            if add_price:
                result.append((ReceiptItemType.PRICE, line[-1][1]))
        else:
            if line[-1][0] == TokenType.PRICE:
                result.append((ReceiptItemType.PRICE, line[-1][1]))
            elif str(line[-1][1]) == 'Free':
                result.append((ReceiptItemType.PRICE, 0.0))

    if not passed_total:
        logger.error(f"Lines are over, but total was not found. Not a valid receipt: {parsed_receipt}")
    return result


def process_receipt(text):
    receipt_builder = ReceiptBuilder()

    missed_prices = []

    item_builders = []
    current_item_builder = None

    tax_builders = []
    current_tax_builder = None

    passed_total = False

    annotated = annotate_receipt(parse_receipt(text))
    logger.debug(f"Annotated receipt: {annotated}")

    for token in annotated:
        tp = token[0]
        value = token[1] if len(token) > 1 else None
        if tp == ReceiptItemType.QUANTITY:
            if current_item_builder:
                item_builders.append(current_item_builder)

            current_item_builder = ItemBuilder(value)

        elif tp == ReceiptItemType.NAME:
            current_item_builder.add_name(value)
        elif tp == ReceiptItemType.DESCRIPTION:
            if current_item_builder:
                current_item_builder.add_description(value)
        elif tp == ReceiptItemType.TAX:
            if current_tax_builder:
                tax_builders.append(current_tax_builder)

            current_tax_builder = PricedBuilder()
            current_tax_builder.add_name(value)

        elif tp == ReceiptItemType.SUBTOTAL:
            if current_item_builder:
                item_builders.append(current_item_builder)
            current_item_builder = None

        elif tp == ReceiptItemType.TOTAL:
            if current_tax_builder:
                tax_builders.append(current_tax_builder)
            current_tax_builder = None
            passed_total = True

        elif tp == ReceiptItemType.PRICE:
            if current_item_builder:
                current_item_builder.add_price(value)
            elif current_tax_builder:
                current_tax_builder.add_price(value)
            elif not passed_total:
                receipt_builder.add_subtotal(value)
            else:
                missed_prices.append(value)

    try:
        total = missed_prices[-1]
        receipt_builder.add_total(total)
        missed_prices.remove(total)

        for builder in item_builders:
            if not builder.price:
                builder.add_price(missed_prices.pop(0))
            receipt_builder.add_item(builder.build())

        if not receipt_builder.subtotal_set:
            receipt_builder.add_subtotal(missed_prices.pop(0))

        for builder in tax_builders:
            if missed_prices and not builder.price_set:
                builder.add_price(missed_prices.pop())
            receipt_builder.add_tax(builder.build())

        return receipt_builder.build()
    except IndexError as e:
        logger.error("Index error", e)
        raise Exception("Cannot match prices with items, the sizes do not match")
