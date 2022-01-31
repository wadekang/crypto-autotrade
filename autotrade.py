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

file_handler = logging.FileHandler('trade.log')
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

def get_target_price(tickers):
    ret = dict([])

    for ticker in tickers:
        df = pyupbit.get_ohlcv(ticker, "minute15", count=1)
        target_price = df.iloc[0]['close'] + (df.iloc[0]['high'] - df.iloc[0]['low']) * 0.5
        ret[ticker] = target_price
        time.sleep(0.03)

    return ret

def get_start_time(ticker, interval='minute15'):
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
    target_prices = None
    current_prices = None
    buy_list = []

    TARGET_NUM = 10

    while True:
        try:
            now = datetime.datetime.now()
            start_time = get_start_time(tick_for_time)
            end_time = start_time + datetime.timedelta(minutes=15) - datetime.timedelta(seconds=7)

            if start_time < now < end_time:
                if target_prices is None:
                    # log.info('wait next turn...')
                    time.sleep(1)
                    continue

                if len(buy_list) < TARGET_NUM:
                    current_prices = get_current_price(tickers)

                    for ticker in tickers:
                        if ticker in buy_list:
                            continue

                        if current_prices[ticker] > target_prices[ticker]:
                            krw = upbit.get_balance("KRW") / (TARGET_NUM - len(buy_list))
                            if krw > 7000:
                                result = upbit.buy_market_order(ticker, krw*0.9995)
                                log.info(f"buy: {result}")
                                buy_list.append(ticker)
                                if len(buy_list) >= TARGET_NUM:
                                    break
            else: 
                if buy_list:
                    for ticker in buy_list:
                        crypto_balance = upbit.get_balance(ticker)
                        if crypto_balance > 0:
                            result = upbit.sell_market_order(ticker, crypto_balance)
                            log.info(f"sell: {result}")
                
                buy_list = []
                target_prices = get_target_price(tickers)
            time.sleep(0.5)
        except Exception as e:
            log.error('exception', e)
            time.sleep(0.5)

if __name__ == "__main__":
    asyncio.run(main())
