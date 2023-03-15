import pandas as pd
import requests
from binance.client import Client
from datetime import datetime
import time


def get_binance_data_request_(ticker, interval, start, end, limit=1000):
    """
    interval: str tick interval - 4h/1h/1d ...
    """
    columns = ['open_time', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'qav', 'num_trades', 'taker_base_vol', 'taker_quote_vol', 'ignore']
    url = f'https://www.binance.com/api/v3/klines?symbol={ticker}&interval={interval}&limit={limit}&startTime={start:.0f}&endTime={end:.0f}'
    print(url)
    data = pd.DataFrame(requests.get(url).json(), columns=columns, dtype=float)
    return data


def get_binance_candles(startdate, enddate, ticker, interval):
    client = Client()
    candles = pd.DataFrame()

    # Define the interval, ticker and other parameters
    interval = interval
    limit = 1000

    # Define interval duration in milliseconds
    interval_duration = {
        '1m': 60 * 10 ** 3,
        '3m': 180 * 10 ** 3,
        '5m': 300 * 10 ** 3,
        '15m': 900 * 10 ** 3,
        '30m': 1800 * 10 ** 3,
        '1h': 3600 * 10 ** 3,
        '2h': 7200 * 10 ** 3,
        '4h': 14400 * 10 ** 3,
        '6h': 21600 * 10 ** 3,
        '8h': 28800 * 10 ** 3,
        '12h': 43200 * 10 ** 3,
        '1d': 86400 * 10 ** 3,
        '3d': 259200 * 10 ** 3,
        '1w': 604800 * 10 ** 3,
        '1M': 2592000 * 10 ** 3
    }

    # Calculate the window size
    window = limit * interval_duration[interval]

    # Define the start and end timestamps for the first iteration
    start = startdate
    end = start + window

    # Loop until the end timestamp is greater than or equal to the max_date
    while end <= enddate + window:
        data = get_binance_data_request_(ticker.replace('-', ''), interval, start, end, limit)
        candles = pd.concat([candles, data])
        start = end
        end = start + window
        time.sleep(1)

    # Ensure time column is called open_time in timestamp (milliseconds)
    candles['datetime'] = candles['open_time'].apply(lambda x: datetime.fromtimestamp(x // 1000))
    candles = candles.drop_duplicates(subset=['open_time'])
    candles.to_csv(f'candles/{ticker}_{startdate}_{enddate}_{interval}.csv', index=False)
    return candles[['open_time', 'datetime', 'open', 'high', 'low', 'close', 'volume']]


def get_all_binance_perpetuals():
    client = Client()
    exchange_info = client.futures_exchange_info()
    symbols = exchange_info['symbols']

    # Filter perpetual trading pairs
    perpetual_pairs = [symbol['symbol'] for symbol in symbols if symbol['contractType'] == 'PERPETUAL']

    return perpetual_pairs
