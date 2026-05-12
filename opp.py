import streamlit as st
import streamlit.components.v1 as components
import pandas as pd

# 1. 페이지 설정 (와이드 모드)
st.set_page_config(page_title="Global Multi-Strategy Terminal", layout="wide")

# 2. 한국 주식 전종목 리스트 확보 (네이버/KRX 기준)
@st.cache_data(show_spinner="전종목 데이터를 실시간 동기화 중입니다...")
def get_krx_master_list():
    try:
        # 가장 안정적인 종목 리스트 소스 활용
        url = "https://raw.githubusercontent.com/FinanceData/FinanceDataReader/master/KRX_Stock_Symbols.csv"
        df = pd.read_csv(url)
        return df[['Symbol', 'Name', 'Market']]
    except:
        # 데이터 서버 응답 없을 시 최소 우량주 리스트 반환
        return pd.DataFrame([
            {"Symbol": "005930", "Name": "삼성전자", "Market": "KOSPI"},
            {"Symbol": "000660", "Name": "SK하이닉스", "Market": "KOSPI"},
            {"Symbol": "005935", "Name": "삼성전자우", "Market": "KOSPI"},
            {"Symbol": "006400", "Name": "삼성SDI", "Market": "KOSPI"},
            {"Symbol": "009150", "Name": "삼성전기", "Market": "KOSPI"},
            {"Symbol": "207940", "Name": "삼성바이오로직스", "Market": "KOSPI"},
            {"Symbol": "035720", "Name": "카카오", "Market": "KOSPI"}
        ])

krx_master = get_krx_master_list()

# 3. 사이드바: 종목 검색 및 코드 나열 (사용자 핵심 요구사항)
with st.sidebar:
    st.header("🔍 국/내외 종목 통합 검색")
    search_keyword = st.text_input("종목명 입력 (예: 삼성, 현대, 에코)", value="삼성")
    
    # 검색어가 포함된 모든 국내 종목 필터링
    matched_stocks = krx_master[krx_master['Name'].str.contains(search_keyword, na=False, case=False)]
    
    if not matched_stocks.empty:
        st.subheader(f"📋 '{search_keyword}' 검색 결과 ({len(matched_stocks)}건)")
        
        # [핵심] 검색된 모든 종목과 코드를 표 형태로 나열 (여기서 코드를 다 볼 수 있음)
        st.dataframe(
            matched_stocks[['Name', 'Symbol', 'Market']].sort_values(by='Name'), 
            hide_index=True, 
            height=350,
            use_container_width=True
        )
        
        # 선택 박스 (표에서 확인한 종목을 선택)
        stock_options = [f"{r['Name']} ({r['Symbol']})" for _, r in matched_stocks.sort_values(by='Name').iterrows()]
        selected_stock = st.selectbox("분석할 종목 선택", stock_options)
        
        # 트레이딩뷰용 티커 생성 (KRX:005930 형태)
        target_code = selected_stock.split("(")[1].replace(")", "")
        final_ticker = f"KRX:{target_code}"
        display_name = selected_stock.split(" (")[0]
    else:
        st.info("국내 종목 없음 -> 해외 티커 모드 (예: NVDA, TSLA)")
        final_ticker = search_keyword.upper()
        display_name = search_keyword.upper()

    st.divider()
    st.subheader("🛠️ 차트 설정")
    chart_theme = st.radio("테마", ["dark", "light"], horizontal=True)
    show_details = st.checkbox("호가 및 상세 정보 표시", value=True)

# 4. 메인 영역: 트레이딩뷰(TradingView) 프로 위젯 연동
st.title(f"📈 {display_name} 실시간 전략 터미널")

# 트레이딩뷰 위젯 소스코드 (피보나치, RSI, 이평선 등 모든 도구 포함)
tradingview_widget_code = f"""
    <div class="tradingview-widget-container" style="height:850px; width:100%;">
        <div id="tradingview_chart_container"></div>
        <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
        <script type="text/javascript">
        new TradingView.widget({{
            "autosize": true,
            "symbol": "{final_ticker}",
            "interval": "D",
            "timezone": "Asia/Seoul",
            "theme": "{chart_theme}",
            "style": "1",
            "locale": "kr",
            "toolbar_bg": "#f1f3f6",
            "enable_publishing": false,
            "withdateranges": true,
            "hide_side_toolbar": false,
            "allow_symbol_change": true,
            "details": {str(show_details).lower()},
            "hotlist": true,
            "calendar": true,
            "studies": [
                "RSI@tv-basicstudies",
                "MASimple@tv-basicstudies",
                "StochasticRSI@tv-basicstudies"
            ],
            "container_id": "tradingview_chart_container"
        }});
        </script>
    </div>
"""

# 트레이딩뷰 위젯 렌더링
components.html(tradingview_widget_code, height=850)

# 5. 사용 가이드
st.success(f"현재 {display_name} 차트를 분석 중입니다.")
st.markdown("""
> **💡 트레이딩뷰 활용 팁:**
> * **피보나치:** 왼쪽 도구 모음의 3번째 아이콘(선형 도구)에서 '피보나치 되돌림'을 선택해 차트에 직접 그릴 수 있습니다.
> * **지표:** 상단 '지표' 메뉴에서 MACD, 볼린저 밴드 등을 무제한 추가 가능합니다.
> * **실시간:** 위 데이터는 실시간으로 연동되어 정확한 매수/매도 타점을 잡기에 유리합니다.
""")
