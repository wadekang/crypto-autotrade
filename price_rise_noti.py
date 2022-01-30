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

from slack_sdk import WebClient

log = logging.getLogger()
log.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

file_handler = logging.FileHandler('noti.log')
file_handler.setFormatter(formatter)
log.addHandler(file_handler)

access = "apikey"
secret = "apikey"
client = WebClient(token='apikey')

def get_tickers():
    url = "https://api.upbit.com/v1/market/all"
    headers = {"Accept": "application/json"}

    tickers =  requests.get(url, headers=headers).json()

    remove_list = ['KRW-SNT', 'KRW-XEM', 'KRW-XLM', 'KRW-ARDR', 'KRW-TRX', 'KRW-SC', 'KRW-ZIL', 'KRW-LOOM', 'KRW-IOST', 
    'KRW-RFR', 'KRW-IQ', 'KRW-MFT', 'KRW-UPP', 'KRW-QKC', 'KRW-MOC', 'KRW-TFUEL', 'KRW-ANKR', 'KRW-AERGO', 'KRW-TT', 'KRW-CRE', 
    'KRW-MBL', 'KRW-HBAR', 'KRW-MED', 'KRW-STPT', 'KRW-ORBS', 'KRW-VET', 'KRW-CHZ', 'KRW-STMX', 'KRW-DKA', 'KRW-AHT', 'KRW-JST', 
    'KRW-MVL', 'KRW-SSX', 'KRW-META', 'KRW-FCT2', 'KRW-HUM']
    
    ticker_market = []
    ticker_kor = dict([])
    for data in tickers:
        if data['market'].startswith('KRW') and data['market'] not in remove_list:
            ticker_market.append(data['market'])
            ticker_kor[data['market']] = data['korean_name']

    return ticker_market, ticker_kor

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
    tickers, tickers_kor = get_tickers()

    upbit = pyupbit.Upbit(access, secret)
    balance = upbit.get_balance("KRW")
    if balance == None:
        log.error('api key error')
        sys.exit('api key error')

    log.info('price rise notification start')

    tick_for_time = 'KRW-XRP'
    close_prices = None
    current_prices = None
    target = 1.015
    send_list = []

    while True:
        try:
            now = datetime.datetime.now()
            start_time = get_start_time(tick_for_time)
            end_time = start_time + datetime.timedelta(minutes=5) - datetime.timedelta(seconds=3)

            if start_time < now < end_time:
                if close_prices is None:
                    # log.info('wait next turn...')
                    time.sleep(1)
                    continue

                else:
                    current_prices = await get_current_price(tickers)
                    crypto_rise_list = []
                    for ticker in tickers:
                        if ticker not in send_list and current_prices[ticker] >= close_prices[ticker] * target:
                            send_list.append(ticker)
                            ratio = round((current_prices[ticker] / close_prices[ticker] * 100) - 100, 1)
                            log.info(f"{ticker}, {tickers_kor[ticker]}: {ratio}% rise, open={close_prices[ticker]}, target={close_prices[ticker]*target}, cur={current_prices[ticker]}")
                            
                            # notification code
                            message = f"{ticker}, {tickers_kor[ticker]}: {ratio}% rise"
                            client.chat_postMessage(channel='#crypto', text=message)

            else: # last 3 seconds -> update close_prices
                close_prices = await get_current_price(tickers)
                send_list = []
                # log.info('close_prices modify')
            time.sleep(1)
        except Exception as e:
            log.error('exception', e)
            time.sleep(1)

if __name__ == "__main__":
    asyncio.run(main())
