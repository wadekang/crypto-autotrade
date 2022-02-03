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

file_handler = logging.FileHandler('stochrsi.log')
file_handler.setFormatter(formatter)
log.addHandler(file_handler)

access = "apikey"
secret = "apikey"

TARGET_CRYP = 'KRW-SAND'
INTERVAL = 'minute15'

TARGET_RATE = 1.011
LIMIT = 0.993

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
    # D = round(K.rolling(window=SMOOTH, center=False).mean(), 2)

    return K[-5:]

async def main():
    upbit = pyupbit.Upbit(access, secret)
    balance = upbit.get_balance("KRW")
    if balance == None:
        log.error('api key error')
        sys.exit('api key error')

    log.info('autotrade start')

    buy_cryp = False
    buy_price = None
    stoch_rsi = None

    log.info('waiting start')
    while True:
        stoch_rsi = stochastic_rsi(TARGET_CRYP)
        cur = stoch_rsi[-1]
        before = stoch_rsi[-2]

        if cur < before - 3:
            log.info('detecting start')
            break
        time.sleep(2)

    while True:
        try:
            stoch_rsi = stochastic_rsi(TARGET_CRYP)
            cur = stoch_rsi[-1]

            if buy_cryp:
                before_max = max(stoch_rsi[:-1])
                if cur <= before_max - 3:
                    cryp = upbit.get_balance(TARGET_CRYP)

                    if cryp > 0:
                        result = upbit.sell_market_order(TARGET_CRYP, cryp)
                        log.info(f"sell: {result}")
                        buy_cryp = False

                else:
                    current_price = await get_current_price(TARGET_CRYP)

                    if current_price < buy_price * LIMIT: # stop loss
                        cryp = upbit.get_balance(TARGET_CRYP)

                        if cryp > 0:
                            result = upbit.sell_market_order(TARGET_CRYP, cryp)
                            log.info(f"stop loss: {result}")
                            buy_cryp = False
            else:
                before_min = min(stoch_rsi[:-1])
                if cur >= before_min + 3:
                    krw = upbit.get_balance('KRW')

                    if krw > 21000:
                        buy_price = await get_current_price(TARGET_CRYP)
                        result = upbit.buy_market_order(TARGET_CRYP, 20000)
                        log.info(f"buy: {result}")
                        buy_cryp = True

            time.sleep(1)
        except Exception as e:
            log.error(e)
            time.sleep(1)

if __name__ == "__main__":
    asyncio.run(main())
