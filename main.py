import streamlit as st
import datetime
import importlib
import os
from connector.binance_candles import get_binance_candles, get_all_binance_perpetuals
from charts.backtesting_charts import BacktestingCharts
import pandas as pd

st.set_page_config(layout='wide')
st.title('Backtesting lab')

# -------------------------------------------------------------------------------------------------------------------
# -------------------------------------------- PARAMS CONFIGURATION -------------------------------------------------
# -------------------------------------------------------------------------------------------------------------------
st.subheader('Params')
col1, col2, col3, col4 = st.columns(4)
with col1:
    portfolio_initial_value = st.number_input('Portfolio initial value', min_value=10.0, value=150.0)
    tl = st.number_input('TL', min_value=1, value=500)
with col2:
    initial_amount_usd = st.number_input('Initial amount USD', min_value=5.0, value=15.0)
    std_span = st.number_input('Std span', min_value=1, value=100)
with col3:
    leverage = st.number_input('Leverage', min_value=1.0, value=20.0)
    # signal_thold = st.number_input('Signal Threshold', min_value=0.0, max_value=1.0, step=0.01, value=0.7)
    tp = st.number_input('TP std %', min_value=0.0, value=1.5)
with col4:
    trade_cost = st.number_input('Trade cost (%)', min_value=0.01, value=0.06, step=0.01)
    trade_cost = trade_cost / 100
    sl = st.number_input('SL std %', min_value=0.0, value=0.75)

# -------------------------------------------------------------------------------------------------------------------
# -------------------------------------------- SIDEBAR CONFIGURATION ------------------------------------------------
# -------------------------------------------------------------------------------------------------------------------

st.sidebar.subheader('Strategy')
strategy = [f for f in os.listdir('strategies/') if f.endswith(".py")]
selected_strategy = st.sidebar.selectbox("Select a strategy", strategy)
module_name = selected_strategy[:-3]
module = importlib.import_module(f"strategies.{module_name}")

st.sidebar.subheader('Candles')
candles = pd.DataFrame()
run_local = st.sidebar.checkbox('Run locally', value=True)
if run_local:
    candles_files = [f for f in os.listdir('candles/') if f.endswith(".csv")]
    selected_candles = st.sidebar.selectbox("Select a candles file", candles_files)
    start_button = st.sidebar.button('Get candles')
    if start_button:
        candles = pd.read_csv('candles/' + selected_candles)
else:
    st.sidebar.subheader('Get candles')
    # ticker = st.sidebar.selectbox('Ticker', ['DODO-BUSD', 'APE-BUSD'])
    ticker = st.sidebar.selectbox('Ticker', get_all_binance_perpetuals())
    intervals = ['1m', '3m', '5m', '15m', '30m', '1h', '2h', '4h', '6h', '12h', '1d', '1w', '1M']
    interval = st.sidebar.selectbox('Interval', intervals, index=1)

    start_date_input = st.sidebar.date_input('Start date', value=datetime.date(2023, 2, 14))
    start_time_input = st.sidebar.time_input('Start time', value=datetime.time(12, 33))
    start_datetime = datetime.datetime.combine(start_date_input, start_time_input)
    start_timestamp = datetime.datetime.combine(start_datetime, datetime.datetime.min.time()).timestamp() * 1000

    end_date_input = st.sidebar.date_input('End date')
    end_time_input = st.sidebar.time_input('End time')
    end_datetime = datetime.datetime.combine(end_date_input, end_time_input)
    end_timestamp = datetime.datetime.combine(end_datetime, datetime.datetime.min.time()).timestamp() * 1000

    start_button = st.sidebar.button('Get candles')
    if start_button:
        candles = get_binance_candles(startdate=start_timestamp,
                                      enddate=end_timestamp,
                                      ticker=ticker,
                                      interval=interval)

if len(candles) > 0:
    bt = BacktestingCharts(module.strategy(candles),
                           std_span=std_span,
                           tp_std_pct=tp,
                           sl_std_pct=sl,
                           tl=tl,
                           portfolio_initial_value=portfolio_initial_value,
                           initial_amount_usd=initial_amount_usd,
                           leverage=leverage,
                           trade_cost=trade_cost)

    st.markdown('<hr>', unsafe_allow_html=True)

    # -------------------------------------------------------------------------------------------------------------------
    # ------------------------------------------------ PnL RESULTS ------------------------------------------------------
    # -------------------------------------------------------------------------------------------------------------------
    st.subheader('PnL Results')
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric('Portfolio initial value', portfolio_initial_value)
    with col2:
        max_margin = bt.get_maximum_margin()
        max_margin_label = f'$ {max_margin:.4f}'
        st.metric('Max margin reached', max_margin_label)
    with col3:
        global_pnl = bt.get_global_pnl()
        global_pnl_label = f'$ {global_pnl:.4f}'
        st.metric('Global PnL', global_pnl_label)
    with col4:
        return_pct = 100 * global_pnl / portfolio_initial_value
        return_pct_label = f'{return_pct:.4f} %'
        st.metric('Return %', return_pct_label)

    st.plotly_chart(bt.plot_pnl(), use_container_width=True)

    st.markdown('<hr>', unsafe_allow_html=True)

    # -------------------------------------------------------------------------------------------------------------------
    # -------------------------------------------- STRATEGY PERFORMANCE -------------------------------------------------
    # -------------------------------------------------------------------------------------------------------------------
    st.subheader('Strategy performance')
    st.success(f"A total of {bt.get_total_candles()} candles were loaded.")

    col1, col2, col3, col4 = st.columns([2, 1, 2, 1])
    with col1:
        st.plotly_chart(bt.plot_exit_events(all=True), use_container_width=True)
    with col2:
        st.markdown('')
        total_signals = float(bt.get_total_signals())
        st.metric('Total signals', bt.get_total_signals())
        st.markdown('<hr>', unsafe_allow_html=True)
        st.metric('Total profitable signals', bt.get_profitable_signals())
        st.markdown('<hr>', unsafe_allow_html=True)
        acc = f'{100 * bt.get_profitable_signals() / bt.get_total_signals():.2f} %'
        st.metric('Accuracy', acc)
    with col3:
        st.plotly_chart(bt.plot_exit_events(all=False), use_container_width=True)
    with col4:
        st.markdown('')
        executed_signals = float(bt.get_executed_signals())
        st.metric('Signals executed', f'{executed_signals:.0f}')
        st.markdown('<hr>', unsafe_allow_html=True)
        executed_good_signals = float(bt.get_executed_profitable_signals())
        st.metric('Profitable signals executed', f'{executed_good_signals:.0f}')
        st.markdown('<hr>', unsafe_allow_html=True)
        execution_accuracy = 100 * executed_good_signals / executed_signals
        st.metric("Execution's accuracy", f'{execution_accuracy:.2f} %')

    st.markdown('<hr>', unsafe_allow_html=True)

    # -------------------------------------------------------------------------------------------------------------------
    # -------------------------------------------- CANDLESTICK ANALYSIS -------------------------------------------------
    # -------------------------------------------------------------------------------------------------------------------
    st.subheader('Candlestick Analysis')
    st.plotly_chart(bt.get_candlestick_chart(), use_container_width=True)

    st.markdown('<hr>', unsafe_allow_html=True)
