import pandas as pd
import pandas_ta as ta  # noqa: F401
import numpy as np


def strategy(df: pd.DataFrame):
    bb_lenght = 100
    macd_fast = 45
    macd_slow = 90
    macd_signal = 9
    df = df.reset_index(drop=True)
    df.ta.bbands(length=bb_lenght, append=True)
    df.ta.macd(fast=macd_fast, slow=macd_slow, signal=macd_signal, append=True)
    df['macd'] = df[f"MACD_{macd_fast}_{macd_slow}_{macd_signal}"]
    df['macd_hist'] = df[f"MACDh_{macd_fast}_{macd_slow}_{macd_signal}"]
    df['macd_signal'] = df[f"MACDs_{macd_fast}_{macd_slow}_{macd_signal}"]
    df['bbl'] = df[f'BBL_{bb_lenght}_2.0']
    df['bbu'] = df[f'BBU_{bb_lenght}_2.0']
    df['bbp'] = df[f"BBP_{bb_lenght}_2.0"]
    df['bbm'] = df[f"BBM_{bb_lenght}_2.0"]
    df['strat_signal'] = np.where((0 < df['bbp']) & (df['bbp'] < 0.2) & (df['macd_hist'] > 0) & (df['macd'] < 0),
                                  1,
                                  np.where((1 > df['bbp']) & (df['bbp'] > 0.8) & (df['macd_hist'] < 0) & (df['macd'] > 0),
                                           -1,
                                           0))
    return df
