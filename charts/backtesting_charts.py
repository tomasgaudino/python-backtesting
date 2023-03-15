import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.express as px
from preprocessing.labeling import Labeling
import pandas as pd
from datetime import timedelta
import numpy as np


class BacktestingCharts:
    def __init__(self,
                 candles: pd.DataFrame,
                 std_span: int,
                 tp_std_pct: float,
                 sl_std_pct: float,
                 tl: int,
                 initial_amount_usd: float,
                 leverage: float,
                 trade_cost: float,
                 portfolio_initial_value: float):

        self.std_span = std_span
        self.tp_std_pct = tp_std_pct
        self.sl_std_pct = sl_std_pct
        self.tl = tl
        self.initial_amount_usd = initial_amount_usd
        self.leverage = leverage
        self.trade_cost = trade_cost
        self.portfolio_initial_value = portfolio_initial_value

        self.candles = self.apply_labeling(candles)

    def apply_labeling(self, candles):
        lb = Labeling()
        return lb.triple_barrier_analyzer(candles,
                                          std_span=self.std_span,
                                          tp=self.tp_std_pct,
                                          sl=self.sl_std_pct,
                                          tl=self.tl,
                                          initial_amount_usd=self.initial_amount_usd,
                                          leverage=self.leverage,
                                          trade_cost=self.trade_cost)

    def get_total_candles(self):
        return len(self.candles)

    def get_total_signals(self):
        return len(self.candles[self.candles['strat_signal'] != 0])

    def get_profitable_signals(self):
        return len(self.candles[((self.candles['lab_ret_sign'] > 0) & (self.candles['strat_signal'] != 0))])

    def get_executed_signals(self):
        return len(self.candles[self.candles['lab_active_order']])

    def get_executed_profitable_signals(self):
        return len(self.candles[(self.candles['lab_active_order']) & (self.candles['lab_ret_sign'] > 0)])

    def get_global_pnl(self):
        return self.candles.loc[self.candles['lab_active_order'], 'lab_cum_pnl'][-1]

    def get_maximum_amount(self):
        return self.candles.loc[self.candles['lab_active_order'], 'lab_amount'].max()

    def get_maximum_margin(self):
        return self.candles.loc[self.candles['lab_active_order'], 'lab_margin'].max()

    def plot_exit_events(self, all=True):
        # Filter the candles based on the condition
        if all:
            df = self.candles.loc[self.candles['strat_signal'] != 0, ['lab_exit', 'strat_signal']]
        else:
            df = self.candles.loc[self.candles['lab_active_order'], ['lab_exit', 'strat_signal']]
        df.replace({'sl': 'SL',
                    'tp': 'TP',
                    'tl': 'TL',
                    1: 'LONG',
                    -1: 'SHORT'},
                   inplace=True)

        # Compute the count of each category
        df['count'] = 1
        df = df.groupby(['lab_exit', 'strat_signal']).count().reset_index()

        # Define the color map
        color_map = {
            'SL': 'red',
            'TL': 'orange',
            'TP': 'lightgreen'
        }

        # Create the sunburst chart with custom colors
        fig = px.sunburst(df,
                          path=['lab_exit', 'strat_signal'],
                          values='count',
                          color='lab_exit',
                          color_discrete_map=color_map)

        fig.update_layout(title={'text': f"Total {'signals' if all else 'executions'}"})
        return fig

    def get_candlestick_chart(self):
        candlestick = make_subplots(rows=2,
                                    cols=1,
                                    shared_xaxes=True,
                                    vertical_spacing=0.1,
                                    row_heights=[2400, 1200])

        # Add bbands
        candlestick.add_trace(go.Scatter(x=self.candles['datetime'],
                                         y=self.candles['bbl'],
                                         marker={'color': 'purple'},
                                         name='Bollinger Band (Lower)'),
                              col=1,
                              row=1)

        candlestick.add_trace(go.Scatter(x=self.candles['datetime'],
                                         y=self.candles['bbu'],
                                         marker={'color': 'purple'},
                                         name='Bollinger Band (Upper)'),
                              col=1,
                              row=1)

        # Add ma 21
        candlestick.add_trace(go.Scatter(x=self.candles['datetime'],
                                         y=self.candles['bbm'],
                                         marker={'color': 'black'},
                                         name='MA 21'),
                              col=1,
                              row=1)

        # Add MACD with signal to lower subplot
        candlestick.add_trace(go.Scatter(x=self.candles['datetime'],
                                         y=self.candles['macd'],
                                         name="MACD"),
                              row=2,
                              col=1)

        candlestick.add_trace(go.Scatter(x=self.candles['datetime'],
                                         y=self.candles['macd_signal'],
                                         name="Signal"),
                              row=2,
                              col=1)

        # Add the MACD histogram to the lower subplot
        candlestick.add_trace(go.Bar(x=self.candles['datetime'],
                                     y=self.candles['macd_hist'],
                                     marker=dict(
                                         color=self.candles['macd_hist']
                                         .apply(lambda x: 'lightgreen' if x >= 0 else 'red')),
                                     name="MACD Hist"),
                              row=2,
                              col=1)

        candlestick = self.plot_signals(candlestick)
        candlestick = self.plot_positions(candlestick)
        candlestick.update_layout(xaxis_rangeslider_visible=False, hovermode='x unified')
        # Add candles
        candlestick.add_trace(go.Candlestick(x=self.candles['datetime'],
                                             open=self.candles['open'],
                                             high=self.candles['high'],
                                             low=self.candles['low'],
                                             close=self.candles['close'],
                                             name='Binance Candles'),
                              col=1,
                              row=1)
        return candlestick

    def get_bad_memory_hist(self):
        active_positions = self.candles[self.candles['lab_active_order']]
        fig = go.Figure(data=[go.Histogram(x=active_positions['lab_ball'])])
        return fig

    def plot_signals(self, fig):
        active_positions = self.candles[self.candles['lab_active_order']]
        # Add wrong short signals
        fig.add_trace(go.Scatter(x=active_positions.loc[(active_positions['strat_signal'] < 0) &
                                                        (active_positions['lab_ret_sign'] <= 0), 'datetime'],
                                 y=active_positions.loc[(active_positions['strat_signal'] < 0) &
                                                        (active_positions['lab_ret_sign'] <= 0), 'close'],
                                 mode='markers',
                                 name='Incorrect short signal',
                                 marker={'color': 'red',
                                         'symbol': 'triangle-down',
                                         'size': 10,
                                         'line': {'color': 'black', 'width': 0.7}}))
        # Add correct short signals
        fig.add_trace(go.Scatter(x=active_positions.loc[(active_positions['strat_signal'] < 0) &
                                                        (active_positions['lab_ret_sign'] > 0), 'datetime'],
                                 y=active_positions.loc[(active_positions['strat_signal'] < 0) &
                                                        (active_positions['lab_ret_sign'] > 0), 'close'],
                                 mode='markers',
                                 name='Correct short signal',
                                 marker={'color': 'lightgreen',
                                         'symbol': 'triangle-down',
                                         'size': 10,
                                         'line': {'color': 'black', 'width': 0.7}}))

        # Add wrong long signals
        fig.add_trace(go.Scatter(x=active_positions.loc[(active_positions['strat_signal'] > 0) &
                                                        (active_positions['lab_ret_sign'] <= 0), 'datetime'],
                                 y=active_positions.loc[(active_positions['strat_signal'] > 0) &
                                                        (active_positions['lab_ret_sign'] <= 0), 'close'],
                                 mode='markers',
                                 name='Incorrect long signal',
                                 marker={'color': 'red',
                                         'symbol': 'triangle-up',
                                         'size': 10,
                                         'line': {'color': 'black', 'width': 0.7}}))
        # Add correct long signals
        fig.add_trace(go.Scatter(x=active_positions.loc[(active_positions['strat_signal'] > 0) &
                                                        (active_positions['lab_ret_sign'] > 0), 'datetime'],
                                 y=active_positions.loc[(active_positions['strat_signal'] > 0) &
                                                        (active_positions['lab_ret_sign'] > 0), 'close'],
                                 mode='markers',
                                 name='Correct long signal',
                                 marker={'color': 'lightgreen',
                                         'symbol': 'triangle-up',
                                         'size': 10,
                                         'line': {'color': 'black', 'width': 0.7}}))
        return fig

    def plot_positions(self, fig):
        active_positions = self.candles[self.candles['lab_active_order']]
        # Add long and short positions
        for index, row in active_positions.iterrows():
            # Add TP
            if row['strat_signal'] > 0:
                fig.add_shape(type="rect",
                              fillcolor="green",
                              opacity=0.5,
                              x0=row.datetime,
                              y0=row.close,
                              x1=row.close_datetime - timedelta(hours=3),
                              y1=row.lab_tp_order,
                              line=dict(color="green"))
                # Add SL
                fig.add_shape(type="rect",
                              fillcolor="red",
                              opacity=0.5,
                              x0=row.datetime,
                              y0=row.close,
                              x1=row.close_datetime - timedelta(hours=3),
                              y1=row.lab_sl_order,
                              line=dict(color="red"))
            # Add TP
            if row['strat_signal'] < 0:
                fig.add_shape(type="rect",
                              fillcolor="green",
                              opacity=0.5,
                              x0=row.datetime,
                              y0=row.close,
                              x1=row.close_datetime - timedelta(hours=3),
                              y1=row.lab_tp_order,
                              line=dict(color="green"))
                # Add SL
                fig.add_shape(type="rect",
                              fillcolor="red",
                              opacity=0.5,
                              x0=row.datetime,
                              y0=row.close,
                              x1=row.close_datetime - timedelta(hours=3),
                              y1=row.lab_sl_order,
                              line=dict(color="red"))
        return fig

    def plot_pnl(self):
        fig = go.Figure()
        fig.add_trace(
            go.Bar(x=self.candles.loc[self.candles['lab_ret'] > 0, 'datetime'],
                   y=self.candles.loc[self.candles['lab_ret'] > 0, 'lab_ret_usd'],
                   marker={'color': '#00E805'},
                   name='Profit'))
        fig.add_trace(
            go.Bar(x=self.candles.loc[self.candles['lab_ret'] < 0, 'datetime'],
                   y=self.candles.loc[self.candles['lab_ret'] < 0, 'lab_ret_usd'],
                   marker={'color': 'violet'},
                   name='Loss'))
        fig.add_trace(go.Scatter(x=self.candles.loc[self.candles['lab_active_order'], 'datetime'],
                                 y=self.candles.loc[self.candles['lab_active_order'], 'lab_cum_pnl'],
                                 marker={'color': 'blue'},
                                 name='Cumulative PnL'))
        fig.update_layout(title='PnL Over Time')
        return fig
