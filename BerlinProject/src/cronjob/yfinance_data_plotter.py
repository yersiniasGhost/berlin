import pandas as pd
from pymongo import MongoClient
from datetime import datetime, timedelta
import numpy as np
from typing import Dict, List
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import plotly.offline as pyo


class InteractiveStockPlotter:
    def __init__(self, db_name='MTA_devel', collection_name='tick_history_cs'):
        self.client = MongoClient('mongodb://localhost:27017/')
        self.db = self.client[db_name]
        self.collection = self.db[collection_name]

        # Test connection
        try:
            self.client.server_info()
            print(f"✅ Connected to MongoDB: {db_name}.{collection_name}")
        except Exception as e:
            print(f"❌ MongoDB connection failed: {e}")
            raise

    def get_recent_data(self, days_back=7):
        """Get data from the most recent days"""
        # Since today is July 30, 2025, get data from July 2025
        current_year = 2025
        current_month = 7

        # Get documents from July 2025 (most recent data)
        query = {
            'year': current_year,
            'month': current_month
        }

        documents = list(self.collection.find(query))
        print(f"Found {len(documents)} documents for {current_year}-{current_month:02d}")

        return documents

    def convert_to_dataframe(self, documents):
        """Convert MongoDB documents to pandas DataFrame"""
        all_data = []

        for doc in documents:
            ticker = doc['ticker']
            year = doc['year']
            month = doc['month']
            interval = doc['time_increments']
            data = doc.get('data', {})

            for day, day_data in data.items():
                for timestamp, price_data in day_data.items():
                    # Convert seconds to datetime
                    seconds = int(timestamp)
                    hours = seconds // 3600
                    minutes = (seconds % 3600) // 60

                    # Create full datetime
                    try:
                        full_datetime = datetime(year, month, int(day), hours, minutes)

                        all_data.append({
                            'datetime': full_datetime,
                            'ticker': ticker,
                            'interval': interval,
                            'open': price_data['open'],
                            'high': price_data['high'],
                            'low': price_data['low'],
                            'close': price_data['close'],
                            'volume': price_data.get('volume', 0)
                        })
                    except ValueError as e:
                        print(f"Skipping invalid date: {year}-{month}-{day} {hours}:{minutes} - {e}")
                        continue

        if all_data:
            df = pd.DataFrame(all_data)
            df = df.sort_values(['ticker', 'datetime'])
            print(f"Converted {len(df)} data points to DataFrame")
            print(f"Tickers: {', '.join(sorted(df['ticker'].unique()))}")
            print(f"Date range: {df['datetime'].min()} to {df['datetime'].max()}")
            return df
        else:
            print("No data to convert")
            return pd.DataFrame()

    def plot_single_ticker_interactive(self, df, ticker, interval=None, chart_type='line'):
        """Create interactive chart for a single ticker"""
        ticker_data = df[df['ticker'] == ticker].copy()

        if interval:
            ticker_data = ticker_data[ticker_data['interval'] == interval]

        if ticker_data.empty:
            print(f"No data found for {ticker}")
            return None

        # Sort by datetime
        ticker_data = ticker_data.sort_values('datetime')

        if chart_type == 'candlestick':
            fig = go.Figure(data=go.Candlestick(
                x=ticker_data['datetime'],
                open=ticker_data['open'],
                high=ticker_data['high'],
                low=ticker_data['low'],
                close=ticker_data['close'],
                name=ticker,
                increasing_line_color='#00ff88',
                decreasing_line_color='#ff4444'
            ))

            chart_title = f'{ticker} - Candlestick Chart'
        else:
            # Line chart with volume
            fig = make_subplots(
                rows=2, cols=1,
                shared_xaxes=True,
                vertical_spacing=0.1,
                subplot_titles=(f'{ticker} - Price', 'Volume'),
                row_width=[0.7, 0.3]
            )

            # Price line
            fig.add_trace(
                go.Scatter(
                    x=ticker_data['datetime'],
                    y=ticker_data['close'],
                    mode='lines',
                    name='Close Price',
                    line=dict(color='#1f77b4', width=2),
                    hovertemplate='<b>%{fullData.name}</b><br>' +
                                  'Date: %{x}<br>' +
                                  'Price: $%{y:.2f}<br>' +
                                  '<extra></extra>'
                ),
                row=1, col=1
            )

            # Volume bars
            fig.add_trace(
                go.Bar(
                    x=ticker_data['datetime'],
                    y=ticker_data['volume'],
                    name='Volume',
                    marker_color='rgba(158,202,225,0.6)',
                    hovertemplate='<b>Volume</b><br>' +
                                  'Date: %{x}<br>' +
                                  'Volume: %{y:,.0f}<br>' +
                                  '<extra></extra>'
                ),
                row=2, col=1
            )

            chart_title = f'{ticker} - Interactive Price Chart'

        # Update layout
        fig.update_layout(
            title={
                'text': chart_title,
                'x': 0.5,
                'xanchor': 'center',
                'font': {'size': 20}
            },
            xaxis_title='Date/Time',
            yaxis_title='Price ($)',
            template='plotly_white',
            hovermode='x unified',
            height=600 if chart_type == 'line' else 500,
            showlegend=True,
            legend=dict(
                yanchor="top",
                y=0.99,
                xanchor="left",
                x=0.01
            )
        )

        # Add range selector
        fig.update_layout(
            xaxis=dict(
                rangeselector=dict(
                    buttons=list([
                        dict(count=1, label="1D", step="day", stepmode="backward"),
                        dict(count=2, label="2D", step="day", stepmode="backward"),
                        dict(count=7, label="7D", step="day", stepmode="backward"),
                        dict(step="all")
                    ])
                ),
                rangeslider=dict(visible=True),
                type="date"
            )
        )

        # Show the plot
        fig.show()
        return ticker_data

    def plot_multiple_tickers_comparison(self, df, tickers=None, max_tickers=6):
        """Create comparison chart for multiple tickers"""
        if tickers is None:
            tickers = df['ticker'].unique()[:max_tickers]

        # Normalize prices to percentage change for comparison
        fig = go.Figure()

        colors = px.colors.qualitative.Set1

        for i, ticker in enumerate(tickers[:max_tickers]):
            ticker_data = df[df['ticker'] == ticker].sort_values('datetime')

            if ticker_data.empty:
                continue

            # Calculate percentage change from first price
            first_price = ticker_data['close'].iloc[0]
            pct_change = ((ticker_data['close'] - first_price) / first_price) * 100

            fig.add_trace(
                go.Scatter(
                    x=ticker_data['datetime'],
                    y=pct_change,
                    mode='lines',
                    name=ticker,
                    line=dict(color=colors[i % len(colors)], width=2),
                    hovertemplate=f'<b>{ticker}</b><br>' +
                                  'Date: %{x}<br>' +
                                  'Change: %{y:.2f}%<br>' +
                                  '<extra></extra>'
                )
            )

        fig.update_layout(
            title={
                'text': 'Stock Price Comparison (% Change)',
                'x': 0.5,
                'xanchor': 'center',
                'font': {'size': 20}
            },
            xaxis_title='Date/Time',
            yaxis_title='Percentage Change (%)',
            template='plotly_white',
            hovermode='x unified',
            height=600,
            showlegend=True,
            legend=dict(
                yanchor="top",
                y=0.99,
                xanchor="left",
                x=0.01
            )
        )

        # Add horizontal line at 0%
        fig.add_hline(y=0, line_dash="dash", line_color="gray", alpha=0.5)

        # Add range selector
        fig.update_layout(
            xaxis=dict(
                rangeselector=dict(
                    buttons=list([
                        dict(count=1, label="1D", step="day", stepmode="backward"),
                        dict(count=2, label="2D", step="day", stepmode="backward"),
                        dict(count=7, label="7D", step="day", stepmode="backward"),
                        dict(step="all")
                    ])
                ),
                rangeslider=dict(visible=True),
                type="date"
            )
        )

        fig.show()

    def plot_heatmap_performance(self, df):
        """Create a heatmap showing daily performance by ticker"""
        # Calculate daily returns for each ticker
        daily_returns = []

        for ticker in df['ticker'].unique():
            ticker_data = df[df['ticker'] == ticker].sort_values('datetime')

            # Group by date and get last price of each day
            daily_prices = ticker_data.groupby(ticker_data['datetime'].dt.date)['close'].last()

            # Calculate daily returns
            returns = daily_prices.pct_change().dropna() * 100

            for date, return_val in returns.items():
                daily_returns.append({
                    'ticker': ticker,
                    'date': date,
                    'return': return_val
                })

        if not daily_returns:
            print("No data for heatmap")
            return

        returns_df = pd.DataFrame(daily_returns)

        # Pivot to create matrix
        heatmap_data = returns_df.pivot(index='ticker', columns='date', values='return')

        fig = go.Figure(data=go.Heatmap(
            z=heatmap_data.values,
            x=[str(date) for date in heatmap_data.columns],
            y=heatmap_data.index,
            colorscale='RdYlGn',
            zmid=0,
            text=np.around(heatmap_data.values, 2),
            texttemplate="%{text}%",
            textfont={"size": 10},
            hovertemplate='<b>%{y}</b><br>' +
                          'Date: %{x}<br>' +
                          'Return: %{z:.2f}%<br>' +
                          '<extra></extra>'
        ))

        fig.update_layout(
            title={
                'text': 'Daily Returns Heatmap (%)',
                'x': 0.5,
                'xanchor': 'center',
                'font': {'size': 20}
            },
            xaxis_title='Date',
            yaxis_title='Ticker',
            template='plotly_white',
            height=max(400, len(heatmap_data.index) * 25),
            width=max(600, len(heatmap_data.columns) * 60)
        )

        fig.show()

    def plot_volume_analysis(self, df, ticker):
        """Create volume analysis chart"""
        ticker_data = df[df['ticker'] == ticker].sort_values('datetime')

        if ticker_data.empty:
            print(f"No data found for {ticker}")
            return

        # Create subplot with price and volume
        fig = make_subplots(
            rows=3, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.05,
            subplot_titles=(f'{ticker} - Price', 'Volume', 'Price vs Volume Correlation'),
            row_heights=[0.5, 0.3, 0.2]
        )

        # Price candlestick
        fig.add_trace(
            go.Candlestick(
                x=ticker_data['datetime'],
                open=ticker_data['open'],
                high=ticker_data['high'],
                low=ticker_data['low'],
                close=ticker_data['close'],
                name='Price',
                increasing_line_color='#00ff88',
                decreasing_line_color='#ff4444'
            ),
            row=1, col=1
        )

        # Volume bars
        fig.add_trace(
            go.Bar(
                x=ticker_data['datetime'],
                y=ticker_data['volume'],
                name='Volume',
                marker_color='rgba(158,202,225,0.8)'
            ),
            row=2, col=1
        )

        # Price change vs Volume scatter
        ticker_data['price_change'] = ticker_data['close'].pct_change() * 100

        fig.add_trace(
            go.Scatter(
                x=ticker_data['volume'],
                y=ticker_data['price_change'],
                mode='markers',
                name='Price Change vs Volume',
                marker=dict(
                    size=8,
                    color=ticker_data['price_change'],
                    colorscale='RdYlGn',
                    showscale=True,
                    colorbar=dict(title="Price Change %")
                ),
                hovertemplate='Volume: %{x:,.0f}<br>' +
                              'Price Change: %{y:.2f}%<br>' +
                              '<extra></extra>'
            ),
            row=3, col=1
        )

        fig.update_layout(
            title={
                'text': f'{ticker} - Advanced Volume Analysis',
                'x': 0.5,
                'xanchor': 'center',
                'font': {'size': 20}
            },
            template='plotly_white',
            height=800,
            showlegend=True
        )

        fig.show()

    def show_data_summary(self, df):
        """Show summary of the data"""
        print("\n" + "=" * 60)
        print("DATA SUMMARY")
        print("=" * 60)

        print(f"Total data points: {len(df):,}")
        print(f"Date range: {df['datetime'].min()} to {df['datetime'].max()}")
        print(f"Unique tickers: {df['ticker'].nunique()}")
        print(f"Tickers: {', '.join(sorted(df['ticker'].unique()))}")

        # Summary by ticker
        print("\nBy Ticker:")
        for ticker in sorted(df['ticker'].unique()):
            ticker_data = df[df['ticker'] == ticker]
            count = len(ticker_data)
            min_price = ticker_data['close'].min()
            max_price = ticker_data['close'].max()
            latest_price = ticker_data.sort_values('datetime')['close'].iloc[-1]
            date_range = f"{ticker_data['datetime'].min().strftime('%m-%d')} to {ticker_data['datetime'].max().strftime('%m-%d')}"

            print(
                f"  {ticker}: {count:,} points, ${min_price:.2f}-${max_price:.2f}, latest: ${latest_price:.2f} ({date_range})")


def main():
    """Main function with interactive plotting"""
    try:
        plotter = InteractiveStockPlotter()

        # Get recent data
        print("Fetching recent data from July 2025...")
        documents = plotter.get_recent_data()

        if not documents:
            print("No recent data found!")
            return

        # Convert to DataFrame
        df = plotter.convert_to_dataframe(documents)

        if df.empty:
            print("No valid data to plot!")
            return

        # Show summary
        plotter.show_data_summary(df)

        # Interactive plotting menu
        while True:
            print("\n" + "=" * 60)
            print("🚀 INTERACTIVE STOCK CHARTS")
            print("=" * 60)
            print("1. 📈 Interactive Line Chart (single ticker)")
            print("2. 🕯️  Interactive Candlestick Chart (single ticker)")
            print("3. 📊 Multi-ticker Comparison Chart")
            print("4. 🔥 Daily Returns Heatmap")
            print("5. 📉 Volume Analysis (single ticker)")
            print("6. 📋 Show available tickers")
            print("7. 🚪 Exit")
            print("=" * 60)

            choice = input("Enter choice (1-7): ").strip()

            if choice == '1':
                available_tickers = sorted(df['ticker'].unique())
                print(f"Available tickers: {', '.join(available_tickers)}")
                ticker = input("Enter ticker symbol: ").strip().upper()

                if ticker in available_tickers:
                    plotter.plot_single_ticker_interactive(df, ticker, chart_type='line')
                else:
                    print(f"Ticker {ticker} not found!")

            elif choice == '2':
                available_tickers = sorted(df['ticker'].unique())
                print(f"Available tickers: {', '.join(available_tickers)}")
                ticker = input("Enter ticker symbol: ").strip().upper()

                if ticker in available_tickers:
                    plotter.plot_single_ticker_interactive(df, ticker, chart_type='candlestick')
                else:
                    print(f"Ticker {ticker} not found!")

            elif choice == '3':
                available_tickers = sorted(df['ticker'].unique())
                print(f"Available tickers: {', '.join(available_tickers)}")
                tickers_input = input("Enter ticker symbols (comma-separated, or press Enter for top 6): ").strip()

                if tickers_input:
                    tickers = [t.strip().upper() for t in tickers_input.split(',')]
                    tickers = [t for t in tickers if t in available_tickers]
                else:
                    tickers = available_tickers[:6]

                if tickers:
                    plotter.plot_multiple_tickers_comparison(df, tickers)
                else:
                    print("No valid tickers found!")

            elif choice == '4':
                plotter.plot_heatmap_performance(df)

            elif choice == '5':
                available_tickers = sorted(df['ticker'].unique())
                print(f"Available tickers: {', '.join(available_tickers)}")
                ticker = input("Enter ticker symbol: ").strip().upper()

                if ticker in available_tickers:
                    plotter.plot_volume_analysis(df, ticker)
                else:
                    print(f"Ticker {ticker} not found!")

            elif choice == '6':
                available_tickers = sorted(df['ticker'].unique())
                print(f"\nAvailable tickers ({len(available_tickers)}): {', '.join(available_tickers)}")

            elif choice == '7':
                print("👋 Happy trading!")
                break

            else:
                print("❌ Invalid choice. Please try again.")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # Install required package if not already installed
    try:
        import plotly
    except ImportError:
        print("Installing plotly...")
        import subprocess

        subprocess.check_call(["pip", "install", "plotly"])
        import plotly

    main()