# -*- coding: utf-8 -*-

import logging
import os

import pytesseract
from PIL import Image
from telegram import Bot, ParseMode

logger = logging.getLogger()

token = os.environ['BOT_TOKEN']
bot = Bot(token)


def chat(update, context):
    # logger.info("received message")
    photo_list = update.message.photo
    file_path = None
    if photo_list:

        logger.info("downloading file...")
        img = download_file(max(photo_list, key=lambda photo: photo.width))

        if img:
            logger.info("parsing file...")
            items = process_image(img)
            if items:
                text = format_receipt(items)
                print(text)
                update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


def download_file(file):
    return Image.open(bot.get_file(file).download(f'images/tmp.jpg'))


class Item:
    def __init__(self, name, quantity, cost=0.0):
        self.name = name
        self.price = cost / quantity
        self.quantity = quantity
        self.real_price = self.price

    def set_price(self, price):
        self.price = price

    def calculate_real_price(self, subtotal, total):
        self.real_price = self.price * total / subtotal

    def add_description(self, description):
        self.name = f"{self.name} ({description})"

    def __str__(self):
        return f"{self.quantity}x\t|\t{self.name}\t|\t{self.real_price:.2f} each"


def extract_price(text: str):
    if text.startswith("$"):
        return float(text[1:])
    else:
        print("Cannot extract price from: " + text)
        return 0.0


def process_image(image):
    text = pytesseract.image_to_string(image)
    print(text)
    items = []

    subtotal = 0
    total = 0

    item_before = None

    missed_prices = []

    passed_subtotal = False
    passed_total = False

    tax_count = 0

    for raw_line in text.split("\n"):
        line = raw_line.strip()
        if line:
            tokens = line.strip().split(" ")
            quantity = tokens[0].replace("x", "")

            if quantity.isnumeric():

                if tokens[-1].startswith("$"):
                    price = extract_price(tokens[-1])
                    name = " ".join([tk for tk in tokens[1:-1] if tk != "|"])
                    item_before = Item(name, int(quantity), price)
                else:
                    name = " ".join([tk for tk in tokens[1:] if tk != "|"])
                    item_before = Item(name, int(quantity))
                    print(f"No price at the line: {line}. Will add later...")

                items.append(item_before)
            else:
                if tokens[0] == "Subtotal":
                    if tokens[-1].startswith('$'):
                        subtotal = extract_price(tokens[-1])
                    passed_subtotal = True
                elif tokens[0] == "Total":
                    if tokens[-1].startswith('$'):
                        total = extract_price(tokens[-1])
                    passed_total = True
                elif passed_total and tokens[0].startswith("$"):
                    price = extract_price(tokens[0])
                    missed_prices.append(price)
                elif item_before:
                    item_before.add_description(line)
                elif passed_subtotal and not passed_total:
                    tax_count += 1
                item_before = None

    if missed_prices:
        subtotal = missed_prices[len(items)]
        total = missed_prices[len(items) + tax_count + 1]
        for item, price in zip(items, missed_prices[:len(items)]):
            item.set_price(price)

    [item.calculate_real_price(subtotal, total) for item in items]

    print(f"subtotal: {subtotal}")
    print(f"total: {total}")
    return items


def format_receipt(items):
    max_quantity = max(len(str(x.quantity)) for x in items)
    max_name = max(len(x.name) for x in items)
    max_price = max(len(str(x.real_price)) for x in items)

    return ('```\n' + '\n'.join([
        ' | '.join([field + ' ' * (max_field - len(str(field)))
                    for field, max_field in
                    zip([f'{item.quantity}x', item.name, f'{item.real_price:.2f} each'],
                        [max_quantity, max_name, max_price])])
        for item in items]) + '\n```')
