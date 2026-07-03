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


def is_noise_window(d):
    """세금 납부 주간(1·4·6·9월 15일 전후) 및 분기말 전후 여부.
    이 구간의 전주대비 변동은 캘린더 노이즈일 가능성이 높음."""
    # 세금 납부 주간: 해당 월 10~20일
    if d.month in (1, 4, 6, 9) and 10 <= d.day <= 20:
        return True
    # 분기말 역레포 윈도드레싱: 분기 마지막 4일 + 다음 분기 첫 4영업일 근사
    if d.month in (3, 6, 9, 12) and d.day >= 26:
        return True
    if d.month in (1, 4, 7, 10) and d.day <= 4:
        return True
    return False


def get_regime(chg4w, ma20_slope):
    """유동성 레짐 판정.
    축소: 4주 변화율과 MA20 기울기가 모두 마이너스 (매매 규칙의 '유동성 추세 하락' 조건)
    확장: 둘 다 플러스 / 그 외: 중립"""
    if pd.isnull(chg4w) or pd.isnull(ma20_slope):
        return None
    if chg4w < 0 and ma20_slope < 0:
        return 'CONTRACTION'
    if chg4w > 0 and ma20_slope > 0:
        return 'EXPANSION'
    return 'NEUTRAL'


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

        df['MA5'] = df['NetLiquidity'].rolling(window=5).mean()
        df['MA20'] = df['NetLiquidity'].rolling(window=20).mean()
        df['MA60'] = df['NetLiquidity'].rolling(window=60).mean()

        # ── 추세 판정 지표 ──────────────────────────────────────
        # 4주(20영업일) 변화율: 주간 노이즈를 걸러낸 핵심 추세 지표
        df['Chg4W'] = (df['NetLiquidity'] / df['NetLiquidity'].shift(20)) - 1

        # MA20 기울기: 20일 이평이 1개월 전 대비 오르는 중인지
        df['MA20Slope'] = df['MA20'] - df['MA20'].shift(20)

        # 4주 변화율의 1년 z-score: 이번 감소가 평소 변동 대비 유의미한지
        roll_mean = df['Chg4W'].rolling(250).mean()
        roll_std = df['Chg4W'].rolling(250).std()
        df['Chg4W_z'] = (df['Chg4W'] - roll_mean) / roll_std

        # 레짐 판정 (축소/중립/확장)
        df['Regime'] = df.apply(
            lambda r: get_regime(r['Chg4W'], r['MA20Slope']), axis=1)

        # 주간(금요일 마감) 연속 감소 주 수
        weekly = df['NetLiquidity'].resample('W-FRI').last()
        wchg = weekly.diff()
        streak_vals = []
        c = 0
        for v in wchg:
            if pd.notnull(v) and v < 0:
                c += 1
            else:
                c = 0
            streak_vals.append(c)
        w_streak = pd.Series(streak_vals, index=weekly.index)
        # 각 영업일을 해당 주의 금요일 값에 매핑
        df['DownStreakW'] = w_streak.reindex(df.index, method='bfill')

        # 주간 변화(5영업일)의 요인 분해: 어디서 유동성이 빠졌는가
        # NetLiquidity 5일 변화 = D5_Fed + D5_TGA + D5_RRP
        df['D5_Fed'] = df['WALCL'] - df['WALCL'].shift(5)
        df['D5_TGA'] = -(df['WDTGAL'] - df['WDTGAL'].shift(5))
        df['D5_RRP'] = -(df['RRPONTSYD'] - df['RRPONTSYD'].shift(5))

        # 캘린더 노이즈 플래그 (세금 주간, 분기말 전후)
        df['NoiseFlag'] = [is_noise_window(d) for d in df.index]
        # ────────────────────────────────────────────────────────

        df.index = df.index.strftime('%Y-%m-%d')
        df.index.name = 'Date'

        def clean(v):
            return v if pd.notnull(v) else None

        output_data = []
        for date, row in df.iterrows():
            output_data.append({
                'Date': date,
                'WALCL': clean(row['WALCL']),
                'WDTGAL': clean(row['WDTGAL']),
                'RRPONTSYD': clean(row['RRPONTSYD']),
                'NetLiquidity': clean(row['NetLiquidity']),
                'YoY': clean(row['YoY']),
                'MoM': clean(row['MoM']),
                'WoW': clean(row['WoW']),
                'MA5': clean(row['MA5']),
                'MA20': clean(row['MA20']),
                'MA60': clean(row['MA60']),
                'Chg4W': clean(row['Chg4W']),
                'MA20Slope': clean(row['MA20Slope']),
                'Chg4W_z': clean(row['Chg4W_z']),
                'Regime': row['Regime'],
                'DownStreakW': int(row['DownStreakW']) if pd.notnull(row['DownStreakW']) else None,
                'D5_Fed': clean(row['D5_Fed']),
                'D5_TGA': clean(row['D5_TGA']),
                'D5_RRP': clean(row['D5_RRP']),
                'NoiseFlag': bool(row['NoiseFlag'])
            })

        with open('data.json', 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        print("Data updated successfully.")

    except Exception as e:
        print(f"Error updating data: {e}")
        raise

if __name__ == '__main__':
    update_data()
