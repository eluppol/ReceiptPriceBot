# -*- coding: utf-8 -*-
import functools
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


def ordered_subtract(items, common_items):
    return [item for item in items if item not in common_items]


def format_receipt(receipt):
    descr_items = [[element.strip() for element in item.description.split(",")] for item in receipt.items]
    intersection = functools.reduce(lambda x, y: set(x) & set(y), descr_items)

    by_name = dict()

    for item, descr in zip(receipt.items, descr_items):
        name = item.name
        if name in by_name:
            by_name[name] &= set(descr)
        else:
            by_name[name] = set(descr)


    lines = []

    for item, description in zip(receipt.items, descr_items):
        line = f'{item.price:5.2f} {item.name} {f"({item.quantity})" if item.quantity > 1 else ""}'
        description_text = ",".join(ordered_subtract(description, by_name[item.name].union(intersection))[:2])

        if description_text:
            line += f'\n      {description_text}'

        lines.append(line)

    return '```\n' + '\n\n'.join(lines) + '```\n' + f"\n```\nSubtotal: {receipt.subtotal}\nTotal: {receipt.total}\n```"
