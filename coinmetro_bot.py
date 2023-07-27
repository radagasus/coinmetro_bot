import json
import os
import requests
import time

from command import Command, match_command

LAG = 60  # seconds to wait before refreshing cache
BOT_TOKEN = os.environ.get('BOT_TOKEN')

COINMETRO_ENDPOINT = os.environ.get('COINMETRO_ENDPOINT')
PRICES_ENDPOINT = "/exchange/prices"
NOMINATING_ASSETS = ['USD', 'EUR', 'GBP', 'BTC', 'ETH', 'AUD']

response_cache = {}


def lambda_handler(event, _):
    try:
        body = json.loads(event['body'])
        message_part = body['message'].get('text')
        text_response = generate_text_response(message_part)
        if text_response is not None:
            chat_id = body['message']['chat']['id']
            url = f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage'
            payload = {
                'chat_id': chat_id,
                'text': text_response
            }
            _ = requests.post(url, json=payload)
        return {
            "statusCode": 200
        }
    except:
        return {
            "statusCode": 200
        }


def generate_text_response(message_part):
    response = None
    command = match_command(message_part)
    if command is Command.START:
        return "Hey, I'm an unofficial bot for Coinmetro. Use the /help " \
               "command to see an overview of currently available commands."
    elif command is Command.HELP:
        return "Here's an overview of commands : \n" \
               "/admin : ping admins \n" \
               "/volume : get 24h volume"
    elif command is Command.VOLUME:
        return get_with_caching(command, get_volume)
    elif command is Command.ADMIN:
        return "@xcmonika @xcmusab @herebycm @reddug @XCMkellyXCM " \
               "@JensAtDenmark @medatank @WillDec"
    return response


def update_cache(command, response):
    response_cache.update({command: (time.time(), response)})


def get_with_caching(command, function):
    if command in response_cache:
        tic, response = response_cache.get(command)
        if time.time() - tic < LAG:
            return response
    response = function()
    update_cache(command, response)
    return response


def get_volume(nb_top=3):
    response = requests.get(f"{COINMETRO_ENDPOINT}{PRICES_ENDPOINT}")
    if response.status_code == 200:
        response_json = response.json()
        total_volume, volumes = calculate_volumes(response_json)
        top = format_top_volumes(volumes, nb_top)
        return f"The current 24h volume on Coinmetro is " \
                   f"${total_volume:,.2f}\n\n " \
                   f"Top {nb_top}: {top}"
    else:
        print("API call failed.")
    return None


def format_top_volumes(volumes, nb_top=3):
    sorted_volumes = sorted(volumes.items(), key=lambda x: x[1], reverse=True)
    top = '\n\t'.join([format_volume(sorted_volumes[i]) for i in range(3)])
    return f"\n\t{top}"


def format_volume(tuple):
    return f"${tuple[0]}: ${tuple[1]:,.2f}"


def calculate_volumes(price_data):
    total_volume = 0
    volumes = {}
    prices, rates = get_prices(price_data)
    for pair in price_data['24hInfo']:
        identifier = pair['pair']
        pair_volume = pair['v']
        nominating_asset = get_nominating_asset(identifier)
        if nominating_asset in rates:
            price = prices[identifier] * rates[nominating_asset]
            pair_volume = price * pair_volume
            total_volume = total_volume + pair_volume
            volumes.update({identifier: pair_volume})
    return total_volume, volumes


def get_prices(price_data):
    prices = {}
    rates = {'USD': 1}
    for pair in price_data['latestPrices']:
        identifier = pair['pair']
        prices.update({identifier: pair['price']})
        nominating_asset = get_nominating_asset(identifier)
        if nominating_asset is not None and nominating_asset not in rates:
            rates.update({nominating_asset: 1.0})
    for asset in rates:
        rates.update({asset: get_rate(asset, prices)})
    return prices, rates


def get_rate(asset, prices):
    if f"{asset}USD" in prices:
        return prices[f"{asset}USD"]
    elif f"USD{asset}" in prices:
        return 1 / prices[f"{asset}USD"]
    elif f"BTC{asset}" in prices:
        btc_price = prices['BTCUSD']
        return btc_price / prices[f"BTC{asset}"]
    return 1.0


def get_nominating_asset(identifier):
    for asset in NOMINATING_ASSETS:
        if identifier.endswith(asset):
            return asset
    return None
