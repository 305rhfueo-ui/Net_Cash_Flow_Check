import pandas as pd
import requests
import json
import time

def get_fred_data(series_id):
    url = f"https://fred.stlouisfed.org/graph/api/series/?obs=true&id={series_id}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
    }
    
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    data = response.json()
    
    obs = data['observations'][0]
    df = pd.DataFrame(obs, columns=['timestamp', series_id])
    
    # Drop rows where value is empty or '.'
    df = df[df[series_id] != '.']
    
    # Convert timestamp to date
    df['date'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('date', inplace=True)
    df.drop(columns=['timestamp'], inplace=True)
    
    df[series_id] = pd.to_numeric(df[series_id], errors='coerce')
    return df

def update_data():
    try:
        # Fetch data
        print("Fetching WALCL...")
        df_walcl = get_fred_data('WALCL')
        time.sleep(2)
        print("Fetching WDTGAL...")
        df_wdtgal = get_fred_data('WDTGAL')
        time.sleep(2)
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
        
        df['WALCL'] = df['WALCL'] * 1000000
        df['WDTGAL'] = df['WDTGAL'] * 1000000
        df['RRPONTSYD'] = df['RRPONTSYD'] * 1000000000
        
        # Net Liquidity = WALCL - WDTGAL - RRPONTSYD
        df['NetLiquidity'] = df['WALCL'] - df['WDTGAL'] - df['RRPONTSYD']
        
        df['YoY'] = (df['NetLiquidity'] / df['NetLiquidity'].shift(250)) - 1
        df['MoM'] = (df['NetLiquidity'] / df['NetLiquidity'].shift(25)) - 1
        df['WoW'] = (df['NetLiquidity'] / df['NetLiquidity'].shift(5)) - 1
        
        df.dropna(subset=['NetLiquidity'], inplace=True)
        
        df.index = df.index.strftime('%Y-%m-%d')
        df.index.name = 'Date'
        
        df['MA5'] = df['NetLiquidity'].rolling(window=5).mean()
        df['MA20'] = df['NetLiquidity'].rolling(window=20).mean()
        df['MA60'] = df['NetLiquidity'].rolling(window=60).mean()
        
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
