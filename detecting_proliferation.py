import pyupbit
import numpy as np
import requests
import json
import time
import asyncio
import websockets
import datetime
import logging
import sys

log = logging.getLogger()
log.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

file_handler = logging.FileHandler('result.log')
file_handler.setFormatter(formatter)
log.addHandler(file_handler)

access = "apikey"
secret = "apikey"

def get_tickers():
    url = "https://api.upbit.com/v1/market/all"
    headers = {"Accept": "application/json"}

    tickers =  requests.get(url, headers=headers).json()

    remove_list = ['KRW-BTT', 'KRW-XEC']
    return [data['market'] for data in tickers if data['market'].startswith('KRW') and data['market'] not in remove_list]

async def get_current_price(tickers):
    ret = dict([])

    uri = 'wss://api.upbit.com/websocket/v1'
    async with websockets.connect(uri) as websocket:
        subscribe_fmt = [
                {'ticket': 'test'},
                {
                    'type': 'ticker',
                    'codes': tickers,
                    'isOnlySnapshot': True,
                },
                {'format': 'SIMPLE'}
            ]
            
        subscribe_data = json.dumps(subscribe_fmt)
        await websocket.send(subscribe_data)

        for i in range(len(tickers)):
            data = await websocket.recv()
            data = json.loads(data)
            
            ret[data['cd']] = data['tp']
    
    return ret

def get_start_time(ticker, interval='minute5'):
    df = pyupbit.get_ohlcv(ticker, interval=interval, count=1)
    return df.index[0]

async def main():
    tickers = get_tickers()

    upbit = pyupbit.Upbit(access, secret)
    balance = upbit.get_balance("KRW")
    if balance == None:
        log.error('api key error')
        sys.exit('api key error')

    log.info('autotrade start')

    tick_for_time = 'KRW-XRP'
    close_prices = None
    current_prices = None
    buy_crpyto = None
    target = 1.02

    while True:
        try:
            now = datetime.datetime.now()
            start_time = get_start_time(tick_for_time)
            end_time = start_time + datetime.timedelta(minutes=5) - datetime.timedelta(seconds=5)

            if start_time < now < end_time:
                if close_prices is None:
                    # log.info('wait next turn...')
                    time.sleep(1)
                    continue

                if buy_crpyto is None:
                    # log.info('detecting...')
                    current_prices = await get_current_price(tickers)
                    for ticker in tickers:
                        if current_prices[ticker] >= close_prices[ticker] * target:
                            log.info(f"{ticker}: detected, open={close_prices[ticker]}, cur={current_prices[ticker]}")
                            krw = upbit.get_balance("KRW")
                            if krw > 7000:
                                result = upbit.buy_market_order(ticker, krw)
                                log.info(f"buy: {result}")
                                buy_crpyto = ticker
                                break

            else: # last 5 seconds -> sell and update close_prices
                if not buy_crpyto is None:
                    crypto_balance = upbit.get_balance(buy_crpyto)
                    result = upbit.sell_market_order(buy_crpyto, crypto_balance)
                    log.info(f"sell: {result}")
                    buy_crpyto = None

                close_prices = await get_current_price(tickers)
                # log.info('close_prices modify')
            time.sleep(0.7)
        except Exception as e:
            log.error('exception', e)
            time.sleep(0.7)

if __name__ == "__main__":
    asyncio.run(main())
