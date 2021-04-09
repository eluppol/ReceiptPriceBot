# -*- coding: utf-8 -*-

import logging
import os

import pytesseract
from PIL import Image
from telegram import Bot, ParseMode
from .receipt import process_receipt

logger = logging.getLogger()


def chat(update, context):
    photo_list = update.message.photo
    if photo_list:

        logger.info("downloading file...")
        file = context.bot.get_file((max(photo_list, key=lambda photo: photo.width))).download(f'tmp.jpg')
        if file:
            img = Image.open(file)
            logger.info("parsing file...")
            text = process_image(img)
            if "subtotal" in text.lower():
                try:
                    receipt = process_receipt(text)
                    formatted = format_receipt(receipt)
                    logger.debug(formatted)
                    update.message.reply_text(formatted, parse_mode=ParseMode.MARKDOWN)
                except Exception as e:
                    logger.error("Receipt could not be processed", e)
                    update.message.reply_text(f"Receipt detected, but error occurred during processing: <{str(e)}>. "
                                              f"Check logs for more details")


def process_image(image):
    text = pytesseract.image_to_string(image)
    logger.debug(text)

    return text


def format_receipt(receipt):
    items = receipt.items
    max_quantity = max(len(str(x.quantity)) for x in items)
    max_name = max([len(x.name) for x in items] + [len(x.description) for x in items])
    max_price = max(len(str(x.price)) for x in items)

    return ('```\n' + '\n'.join([
        '\n'.join([' | '.join([field + ' ' * (max_field - len(str(field)))
                               for field, max_field in
                               zip([f'{item.quantity}x', item.name, f'{item.price:.2f} each'],
                                   [max_quantity, max_name, max_price])])] +
                  (item.description and [' | '.join([' ' * (max_quantity + 1), item.description + ' ' * (max_name - len(str(item.description))), ''])] or []))
        for item in items]) + '\n```') + f"\n```\nSubtotal: {receipt.subtotal}\nTotal: {receipt.total}\n```"
