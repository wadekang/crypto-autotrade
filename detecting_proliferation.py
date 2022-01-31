import pyupbit
import numpy as np
import requests
import json
import time
import asyncio
from sqlalchemy import true
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

    remove_list = ['KRW-SNT', 'KRW-XEM', 'KRW-XLM', 'KRW-ARDR', 'KRW-TRX', 'KRW-SC', 'KRW-ZIL', 'KRW-LOOM', 'KRW-IOST', 
    'KRW-RFR', 'KRW-IQ', 'KRW-MFT', 'KRW-UPP', 'KRW-QKC', 'KRW-MOC', 'KRW-TFUEL', 'KRW-ANKR', 'KRW-AERGO', 'KRW-TT', 'KRW-CRE', 
    'KRW-MBL', 'KRW-HBAR', 'KRW-MED', 'KRW-STPT', 'KRW-ORBS', 'KRW-VET', 'KRW-CHZ', 'KRW-STMX', 'KRW-DKA', 'KRW-AHT', 'KRW-JST', 
    'KRW-MVL', 'KRW-SSX', 'KRW-META', 'KRW-FCT2', 'KRW-HUM', 'KRW-BTT', 'KRW-XEC']
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
    buy_crpyto = False
    target = 1.0115
    end_target = 1.017
    buy_list = []

    TARGET_NUM = 10

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

                if not buy_crpyto:
                    # log.info('detecting...')
                    current_prices = await get_current_price(tickers)
                    for ticker in tickers:
                        if ticker in buy_list:
                            continue

                        if close_prices[ticker] * target <= current_prices[ticker] < close_prices[ticker] * end_target:
                            log.info(f"{ticker}: detected, open={close_prices[ticker]}, target={close_prices[ticker] * target}, cur={current_prices[ticker]}")
                            krw = upbit.get_balance("KRW") / (TARGET_NUM - len(buy_list))
                            if krw > 7000:
                                result = upbit.buy_market_order(ticker, krw*0.9995)
                                log.info(f"buy: {result}")
                                buy_list.append(ticker)
                                if len(buy_list) >= TARGET_NUM:
                                    buy_crpyto = True
                                    break
                if buy_list:
                    current_prices = await get_current_price(buy_list)
                    for ticker in buy_list:
                        if current_prices[ticker] >= close_prices[ticker] * end_target:
                            crypto_balance = upbit.get_balance(ticker)

                            if crypto_balance > 0:
                                result = upbit.sell_market_order(ticker, crypto_balance)
                                log.info(f"sell: {result}")

            else: # last 5 seconds -> sell and update close_prices
                if buy_list:
                    for ticker in buy_list:
                        crypto_balance = upbit.get_balance(ticker)

                        if crypto_balance > 0:
                            result = upbit.sell_market_order(ticker, crypto_balance)
                            log.info(f"sell: {result}")
                    buy_list = []
                    buy_crpyto = False
                close_prices = await get_current_price(tickers)
                # log.info('close_prices modify')
            time.sleep(0.5)
        except Exception as e:
            log.error('exception', e)
            time.sleep(0.5)

if __name__ == "__main__":
    asyncio.run(main())
