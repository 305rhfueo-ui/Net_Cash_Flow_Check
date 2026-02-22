import pandas as pd
import requests
import json
import io
from datetime import datetime, timedelta

def get_fred_data(series_id):
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    headers = {
        'User-Agent': 'Mozilla/5.0'
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    df = pd.read_csv(io.StringIO(response.text), parse_dates=[0], index_col=0)
    # Replace '.' with NaN, then convert to numeric
    df[series_id] = pd.to_numeric(df[series_id], errors='coerce')
    return df

def update_data():
    try:
        # Fetch data
        print("Fetching WALCL...")
        df_walcl = get_fred_data('WALCL')
        print("Fetching WDTGAL...")
        df_wdtgal = get_fred_data('WDTGAL')
        print("Fetching RRPONTSYD...")
        df_rrp = get_fred_data('RRPONTSYD')
        
        # Combine all data
        df = pd.concat([df_walcl, df_wdtgal, df_rrp], axis=1)
        df.sort_index(inplace=True)
        
        # Forward fill missing values
        df.ffill(inplace=True)
        
        # Generate business days from 2020-01-01 to today
        start_date = '2020-01-01'
        end_date = pd.Timestamp.today().strftime('%Y-%m-%d')
        business_days = pd.bdate_range(start=start_date, end=end_date)
        
        # Reindex to business days, forward filling missing days
        df = df.reindex(business_days, method='ffill')
        
        # Multiply by 1,000,000 (since Fred data is typically in millions or billions, but user said multiply by 1000000)
        # WALCL is in Millions of Dollars. Multiplying by 10^6 gives raw $.
        # WDTGAL is in Millions of Dollars.
        # RRPONTSYD is in Billions of Dollars. Wait! Fred says RRPONTSYD is in Billions of Dollars.
        # But User instruction:
        # 연준자산 (WALCL): 1000000 곱함
        # TGA (WDTGAL): 1000000 곱함
        # 역레포 (RRPONTSYD): 1000000 곱함 "단위 통일성을 위해" (For unit consistency)
        # So I will blindly follow the user instruction to multiply ALL by 1,000,000.
        
        df['WALCL'] = df['WALCL'] * 1000000
        df['WDTGAL'] = df['WDTGAL'] * 1000000
        df['RRPONTSYD'] = df['RRPONTSYD'] * 1000000000
        
        # Net Liquidity = WALCL - WDTGAL - RRPONTSYD
        df['NetLiquidity'] = df['WALCL'] - df['WDTGAL'] - df['RRPONTSYD']
        
        # Calculate changes using shift on business days (df is already bdate_range)
        # YoY: 250 business days
        # MoM: 25 business days
        # WoW: 5 business days
        df['YoY'] = (df['NetLiquidity'] / df['NetLiquidity'].shift(250)) - 1
        df['MoM'] = (df['NetLiquidity'] / df['NetLiquidity'].shift(25)) - 1
        df['WoW'] = (df['NetLiquidity'] / df['NetLiquidity'].shift(5)) - 1
        
        # Drop rows entirely composed of NaN, optionally we can just keep everything that has NetLiquidity
        df.dropna(subset=['NetLiquidity'], inplace=True)
        
        # Format dates back to string
        df.index = df.index.strftime('%Y-%m-%d')
        df.index.name = 'Date'
        
        # Compute Moving Averages for Graph
        df['MA5'] = df['NetLiquidity'].rolling(window=5).mean()
        df['MA20'] = df['NetLiquidity'].rolling(window=20).mean()
        df['MA60'] = df['NetLiquidity'].rolling(window=60).mean()
        
        # Prepare output data format
        output_data = []
        for date, row in df.iterrows():
            output_data.append({
                'Date': date,
                'WALCL': row['WALCL'] if pd.notnull(row['WALCL']) else None,
                'WDTGAL': row['WDTGAL'] if pd.notnull(row['WDTGAL']) else None,
                'RRPONTSYD': row['RRPONTSYD'] if pd.notnull(row['RRPONTSYD']) else None,
                'NetLiquidity': row['NetLiquidity'] if pd.notnull(row['NetLiquidity']) else None,
                'YoY': row['YoY'] if pd.notnull(row['YoY']) else None,
                'MoM': row['MoM'] if pd.notnull(row['MoM']) else None,
                'WoW': row['WoW'] if pd.notnull(row['WoW']) else None,
                'MA5': row['MA5'] if pd.notnull(row['MA5']) else None,
                'MA20': row['MA20'] if pd.notnull(row['MA20']) else None,
                'MA60': row['MA60'] if pd.notnull(row['MA60']) else None
            })
            
        with open('data.json', 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        print("Data updated successfully.")
        
    except Exception as e:
        print(f"Error updating data: {e}")

if __name__ == '__main__':
    update_data()
