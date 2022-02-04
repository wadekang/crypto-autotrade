import pyupbit
import logging
import websockets
import asyncio
import json
import sys
import time

log = logging.getLogger()
log.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

file_handler = logging.FileHandler('cross_trade.log')
file_handler.setFormatter(formatter)
log.addHandler(file_handler)

access = "apikey"
secret = "apikey"

TARGET_CRYP = 'KRW-SAND'
INTERVAL = 'minute5'

TARGET_RATE = 1.006
LIMIT = 0.985

PERIOD = 14
SMOOTH = 3

async def get_current_price(ticker):
    uri = 'wss://api.upbit.com/websocket/v1'
    ret = None
    async with websockets.connect(uri) as websocket:
        subscribe_fmt = [
                {'ticket': 'test'},
                {
                    'type': 'ticker',
                    'codes': [ticker],
                    'isOnlySnapshot': True,
                },
                {'format': 'SIMPLE'}
            ]
            
        subscribe_data = json.dumps(subscribe_fmt)
        await websocket.send(subscribe_data)

        data = await websocket.recv()
        data = json.loads(data)
        ret = data['tp']
    
    return ret

def stochastic_rsi(ticker):
    df = pyupbit.get_ohlcv(ticker, INTERVAL, count=35)
    delta = df['close'].diff(1).dropna()
    up = delta.copy()
    down = delta.copy()
    up[up < 0] = 0
    down[down > 0] = 0

    AVG_GAIN = up.ewm(com=PERIOD-1, min_periods=PERIOD).mean()
    AVG_LOSS = abs(down.ewm(com=PERIOD-1, min_periods=PERIOD).mean())
    RS = AVG_GAIN / AVG_LOSS
    RSI = 100.0 - (100.0 / (1.0 + RS))
    df['rsi'] = RSI

    min_val = df['rsi'].rolling(window=PERIOD, center=False).min()
    max_val = df['rsi'].rolling(window=PERIOD, center=False).max()
    stoch = ((df['rsi'] - min_val) / (max_val - min_val)) * 100
    K = stoch.rolling(window=SMOOTH, center=False).mean()
    D = K.rolling(window=SMOOTH, center=False).mean()

    return K[-2:], D[-2:]

async def main():
    upbit = pyupbit.Upbit(access, secret)
    balance = upbit.get_balance("KRW")
    if balance == None:
        log.error('api key error')
        sys.exit('api key error')

    log.info('autotrade start')

    buy_cryp = False
    buy_price = None
    buy_cond = False

    log.info('waiting start')
    while True:
        K, D = stochastic_rsi(TARGET_CRYP)

        if K[-1] + 5 < D[-1]:
            log.info('detecting start')
            break
        time.sleep(2)

    while True:
        try:
            K, D = stochastic_rsi(TARGET_CRYP)

            if buy_cryp:
                if K[-1] + 2 < D[-1]:
                    cryp = upbit.get_balance(TARGET_CRYP)

                    if cryp > 0:
                        result = upbit.sell_market_order(TARGET_CRYP, cryp)
                        log.info(f"sell: {K[-1]}, {D[-1]}")
                        buy_cryp = False
                        time.sleep(60)

                else:
                    current_price = await get_current_price(TARGET_CRYP)

                    if current_price < buy_price * LIMIT: # stop loss
                        cryp = upbit.get_balance(TARGET_CRYP)

                        if cryp > 0:
                            result = upbit.sell_market_order(TARGET_CRYP, cryp)
                            log.info(f"stop loss: {current_price}, {buy_price}")
                            buy_cryp = False
                            time.sleep(60)

            else:
                if K[-1] > D[-1] + 2:
                    krw = upbit.get_balance('KRW')

                    if krw > 11000:
                        buy_price = await get_current_price(TARGET_CRYP)
                        result = upbit.buy_market_order(TARGET_CRYP, 10000)
                        log.info(f"buy: {buy_price}, 10000, {K[-1]}, {D[-1]}")
                        buy_cryp = True
                        time.sleep(60)

            time.sleep(1)
        except Exception as e:
            log.error(e)
            time.sleep(1)

if __name__ == "__main__":
    asyncio.run(main())
