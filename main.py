# -*- coding: utf-8 -*-

import logging
import os
import sys

from telegram.ext import Updater, CommandHandler, MessageHandler, Filters

from modules.chat import chat


def error(update, context):
    logging.getLogger().error("exception while handling an update:", exc_info=context.error)


def main():
    logging.basicConfig(level=logging.DEBUG,
                        format='[%(asctime)s][%(module)s][%(levelname)s] %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S')
    log = logging.getLogger()

    bot_token = os.environ['BOT_TOKEN']
    if not bot_token:
        log.fatal('empty BOT_TOKEN')
        sys.exit(1)

    updater = Updater(bot_token)
    updater.dispatcher.add_error_handler(error)

    updater.dispatcher.add_handler(MessageHandler(Filters.all, chat))

    log.info('registered all handlers')

    port = int(os.environ.get('PORT', '8080'))
    url = os.environ.get('URL', 'https://receipt-price-bot.herokuapp.com/')
    # add handlers
    updater.start_webhook(listen="0.0.0.0",
                          port=port,
                          url_path=bot_token,
                          webhook_url=url + bot_token)
    log.info('bot started')
    updater.idle()


if __name__ == '__main__':
    main()