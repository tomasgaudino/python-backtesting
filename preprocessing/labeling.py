import pandas as pd
import numpy as np
from datetime import timedelta


class Labeling:
    """
    Class that contains methods for preprocessing financial candles.
    """
    def triple_barrier_analyzer(self,
                                df,
                                std_span,
                                tp,
                                sl,
                                tl,
                                initial_amount_usd,
                                leverage,
                                trade_cost=0.0006):
        """
        Applies the triple-barrier method to the trades.

        Args:
            df (pandas.DataFrame): DataFrame containing financial candles.
            std_span (int): Window size for calculating the standard deviation.
            tp (float): Take-profit threshold value.
            sl (float): Stop-loss threshold value.
            tl (int): Time limit for holding a position (in minutes).
            initial_amount_usd (float): Starting amount for pnl calculation
            leverage (float): Leverage value
            trade_cost (float): The proportional cost of trading (default is 0.0006).

        Returns:
            pandas.DataFrame: DataFrame with the triple-barrier method applied to the trades.
        """
        df.index = pd.to_datetime(df['open_time'], unit='ms')
        df["lab_trgt"] = df["close"].rolling(std_span).std() / df["close"]
        df.dropna(subset="lab_trgt", inplace=True)
        df["lab_tl"] = df.index + timedelta(minutes=tl)
        results = self.apply_pt_sl_on_tl(df, ptSl=[tp, sl])
        df["close_datetime"] = results[['tp_datetime', 'sl_datetime', 'lab_tl']].dropna(how='all').min(axis=1)
        df = self.calculate_lab_ret_sign(df, trade_cost)

        df['lab_tp_order'] = df['close'] * (1 + df['lab_trgt'] * tp * df["strat_signal"])
        df['lab_sl_order'] = df['close'] * (1 - df['lab_trgt'] * sl * df["strat_signal"])
        df['lab_tp_pct'] = (1 + df['lab_trgt'] * tp * df["strat_signal"])
        df['lab_sl_pct'] = (1 - df['lab_trgt'] * sl * df["strat_signal"])
        df['lab_ret_target'] = df['lab_ret'] / df['lab_trgt']
        df['lab_active_order'] = False
        df = self.filter_active_positions(df)
        df['lab_exit'] = results[['tp_datetime', 'sl_datetime', 'lab_tl']].dropna(how='all').idxmin(axis=1)
        df['lab_exit'].replace({'tp_datetime': 'tp', 'sl_datetime': 'sl', 'lab_tl': 'tl'}, inplace=True)
        df = self.calculate_pnl(df, initial_amount_usd, leverage)
        return df

    @staticmethod
    def apply_pt_sl_on_tl(df, ptSl):
        """
        Applies a profit-taking and stop-loss strategy to the trades based on the triple-barrier method.

        Args:
            df (pandas.DataFrame): DataFrame containing financial candles.
            ptSl (List[float, float]): List containing the profit-taking and stop-loss values.

        Returns:
            pandas.DataFrame: DataFrame with the profit-taking and stop-loss values applied to the trades.
        """
        out = df[['close', 'lab_tl', 'strat_signal']].copy(deep=True)
        if ptSl[0] > 0:
            pt = ptSl[0] * df['lab_trgt']
        else:
            pt = pd.Series(index=df.index)  # NaNs
        if ptSl[1] > 0:
            sl = -ptSl[1] * df['lab_trgt']
        else:
            sl = pd.Series(index=df.index)  # NaNs

        for loc, tl in df['lab_tl'].fillna(df['close'].index[-1]).iteritems():
            signal = df.at[loc, 'strat_signal']
            df0 = df.close[loc:tl]  # path prices
            df0 = (df0 / df.close[loc] - 1) * signal
            out.loc[loc, 'strat_signal'] = signal
            out.loc[loc, 'sl_datetime'] = df0[df0 < sl[loc]].index.min()  # earliest stop loss.
            out.loc[loc, 'tp_datetime'] = df0[df0 > pt[loc]].index.min()
        return out

    @staticmethod
    def calculate_lab_ret_sign(df, trade_cost):
        """
        Calculates the return on each trade and labels each return as positive or negative. lab_ret contains trade cost.

        Args:
            df (pandas.DataFrame): DataFrame containing financial candles.
            trade_cost (float): The cost of each trade.

        Returns:
            pandas.DataFrame: DataFrame with the return on each trade and the corresponding sign label.
        """
        px = df.index.union(df['lab_tl'].values)
        px = df.close.reindex(px, method='ffill')
        df['lab_ret'] = (px.loc[df['close_datetime'].values].values / px.loc[df.index] - 1) * df['strat_signal'] - trade_cost
        df['lab_ret_sign'] = np.sign(df['lab_ret'])
        return df

    @staticmethod
    def filter_active_positions(df):
        """
        Filters out any active positions that have ended and ensures that only one position is active at a time.

        Args:
            df (pandas.DataFrame): DataFrame containing financial candles.

        Returns:
            pandas.DataFrame: DataFrame with filtered active positions.
        """
        n_exec = 0
        tp = 0
        sl = 0
        tl = 0
        side = 0
        # df = df[df['signal'] != 0]
        for index, row in df.iterrows():
            signal = row['strat_signal']
            if n_exec == 0:
                if signal != 0:
                    n_exec = 1
                    df.loc[df.index == index, 'lab_active_order'] = True
                    tp = row['lab_tp_order']
                    sl = row['lab_sl_order']
                    tl = row['lab_tl']
                    side = row['strat_signal']
                else:
                    row['lab_active_order'] = False
            elif n_exec == 1:
                end_tl = index >= tl
                end_short = (side < 0) & ((row['close'] < tp) | (row['close'] > sl))
                end_long = (side > 0) & ((row['close'] > tp) | (row['close'] < sl))
                if end_short | end_long | end_tl:
                    n_exec = 0
                    if signal != 0:
                        n_exec = 1
                        row['lab_active_order'] = True
                        tp = row['lab_tp_order']
                        sl = row['lab_sl_order']
                        tl = row['lab_tl']
                        side = row['strat_signal']
                    else:
                        row['lab_active_order'] = False

        return df

    # TODO: include margin limit in for loop
    @staticmethod
    def calculate_pnl(df, initial_amount_usd, leverage):
        """
        Calculates the profit and loss (P&L) of a trading strategy based on the given dataframe of trades.

        Args:
            df (pd.DataFrame): A Pandas dataframe with columns 'lab_active_order', 'lab_amount', 'lab_margin',
                'lab_ret_usd', 'lab_ret', and 'lab_cum_pnl', representing the active order flag, the order amount,
                the required margin, the realized USD return, the return percentage, and the cumulative P&L, respectively.
            initial_amount_usd (float): The initial amount in USD to allocate for trading.
            leverage (float): The leverage to apply for margin trading.

        Returns:
            pd.DataFrame: A Pandas dataframe with the same columns as the input `df`, updated with the calculated P&L.
        """
        df.loc[df['lab_active_order'], 'lab_amount'] = initial_amount_usd
        df.loc[df['lab_active_order'], 'lab_margin'] = df['lab_amount'] / leverage
        df.loc[df['lab_active_order'], 'lab_ret_usd'] = df['lab_amount'] * df['lab_ret']
        df.loc[df['lab_active_order'], 'lab_cum_pnl'] = df['lab_ret_usd'].cumsum().ffill()
        return df
