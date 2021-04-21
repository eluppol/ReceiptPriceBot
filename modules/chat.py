# -*- coding: utf-8 -*-
import json
import logging
import os

import pytesseract
from PIL import Image
from pip._vendor import requests
from telegram import Bot, ParseMode
from .receipt import process_receipt

logger = logging.getLogger()
ocr_api_key = os.environ.get('OCR_API_KEY')


def chat(update, context):
    photo_list = update.message.photo
    if photo_list:

        logger.info("downloading file...")
        filename = 'tmp.jpg'
        file = context.bot.get_file((max(photo_list, key=lambda photo: photo.width))).download('tmp.jpg')
        if file:
            logger.info("parsing file...")
            text = process_image_online(filename)
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


def process_image_locally(filename):
    image = Image.open(filename)
    text = pytesseract.image_to_string(image)
    logger.debug(text)

    return text


def process_image_online(filename):
    if ocr_api_key:
        payload = {'isTable': True,
                   'apikey': ocr_api_key,
                   'OCREngine': 2,
                   }
        with open(filename, 'rb') as f:
            r = requests.post('https://api.ocr.space/parse/image',
                              files={filename: f},
                              data=payload,
                              )

        pages = json.loads(r.content.decode())['ParsedResults']
        result = '\n'.join([page['ParsedText'] for page in pages])
        logger.debug("Returned: " + result)
        return result


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
