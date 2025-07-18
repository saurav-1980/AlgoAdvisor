import streamlit as st
import requests
import pandas as pd
from bs4 import BeautifulSoup
from model_utils.forecast import run_forecast
from strategy_utils.strategy import generate_signals
import plotly.graph_objects as go

# === App title ===
st.title("\U0001F4C8 Stock Forecast App")

# === Function to fetch stock price from Screener.in ===
def fetch_company_info(ticker):
    url = f'https://www.screener.in/company/{ticker}/'
    response = requests.get(url)
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')

        try:
            price = soup.find(class_="flex flex-align-center").text.split()
            price_value = price[1]
            percent_change = price[2]
            color = "green" if "-" not in percent_change else "red"
            st.markdown(
                f"<h3>₹ {price_value} <span style='color:{color}; font-size:18px;'> {percent_change}</span></h3>",
                unsafe_allow_html=True
            )
        except:
            st.warning("⚠️ Could not fetch price details.")

# === Function to fetch historical price data from Alpha Vantage ===
def fetch_stock_history(ticker):
    API_KEY = "SJNDG3FXMS6F62L0"
    url = f'https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol={ticker}.BSE&outputsize=full&apikey={API_KEY}'
    r = requests.get(url)
    data = r.json()

    try:
        df = pd.DataFrame(data['Time Series (Daily)']).T
        df = df.astype(float)
        df = df[['4. close']]
        df.rename(columns={'4. close': 'Close'}, inplace=True)
        df = df[::-1]
        df.index = pd.to_datetime(df.index)
        df.reset_index(inplace=True)
        df.rename(columns={'index': 'Date'}, inplace=True)
        return df
    except:
        st.error("❌ Error fetching stock history.")
        return None

# === User input ===
ticker = st.text_input("Enter Stock Symbol (e.g., HAL, INFY):", "HAL")

# === Show current stock price ===
if ticker:
    fetch_company_info(ticker)

# === Button to show forecast ===
if st.button("Show Forecast"):
    df = fetch_stock_history(ticker)

    if df is not None:
        df['Date'] = pd.to_datetime(df['Date'])

        # === Tail data for last 180 days for candlestick plotting ===
        candle_df = df.tail(180).copy()

        # === Run model forecast for next N business days ===
        forecast_df = run_forecast(df, n_future=10)  # make sure your run_forecast handles future dates!

        # === Generate trading signals on historical candle data ===
        signals_df = generate_signals(candle_df)

        # === Add PnL column ===
        signals_df['PnL'] = 0.0
        entry_price = 0.0

        for i, row in signals_df.iterrows():
            if row['Signal'] == 1:
                entry_price = row['Close']
            elif row['Signal'] == -1 and entry_price != 0:
                signals_df.at[i, 'PnL'] = row['Close'] - entry_price
                entry_price = 0.0

        # === Show signal table ===
        st.subheader("🔍 Recent Signal Data (Debug)")
        st.dataframe(signals_df.tail(30)[['Date', 'Close', 'Signal', 'PnL']])

        buy_signals = signals_df[signals_df['Signal'] == 1]
        sell_signals = signals_df[signals_df['Signal'] == -1]

        st.write(f"🟢 Buy Signals: {len(buy_signals)}")
        st.write(f"🔴 Sell Signals: {len(sell_signals)}")

        # === Plotting ===
        fig = go.Figure()

        fig.add_trace(go.Candlestick(
            x=candle_df['Date'],
            open=candle_df['Close'],
            high=candle_df['Close'] * 1.01,
            low=candle_df['Close'] * 0.99,
            close=candle_df['Close'],
            name='Historical',
            increasing_line_color='green',
            decreasing_line_color='red'
        ))

        fig.add_trace(go.Scatter(
            x=forecast_df['Date'],
            y=forecast_df['Price'],
            mode='lines+markers',
            name='Forecast',
            line=dict(color='blue', dash='dash'),
            marker=dict(symbol='circle', size=6)
        ))

        fig.add_trace(go.Scatter(
            x=buy_signals['Date'],
            y=buy_signals['Close'],
            mode='markers',
            name='Buy',
            marker=dict(symbol='triangle-up', size=10, color='lime')
        ))

        fig.add_trace(go.Scatter(
            x=sell_signals['Date'],
            y=sell_signals['Close'],
            mode='markers',
            name='Sell',
            marker=dict(symbol='triangle-down', size=10, color='red')
        ))

        fig.update_layout(
            title=f"{ticker.upper()} - Historical + Forecast + Signals",
            xaxis_title='Date',
            yaxis_title='Price',
            xaxis_rangeslider_visible=False,
            template='plotly_dark',
            height=500
        )

        st.plotly_chart(fig, use_container_width=True)
