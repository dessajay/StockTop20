# streamlit_app.py
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta
from streamlit_autorefresh import st_autorefresh
from analyzer import (
    load_tickers, save_tickers, load_holdings, save_holdings,
    analyze_all, valuation_flag, build_portfolio_plan, build_rebalance_report, now_kst,
    get_vix, get_fear_greed, FINVIZ_SEC_MAP_URL,
    earnings_calendar_for_list, news_live, news_yesterday, news_week,
    display_name, select_by_rank, refresh_top_lists
)
from i18n import T

# Language state
if "lang" not in st.session_state:
    st.session_state.lang = "KO"
lang = st.sidebar.selectbox(T("language", st.session_state.lang), ["KO","EN"],
                            index=0 if st.session_state.lang=="KO" else 1,
                            format_func=lambda x: T("lang_ko","KO") if x=="KO" else T("lang_en","KO"))
st.session_state.lang = lang

st.set_page_config(page_title=T("app_title", lang), layout="wide")
st.title(T("app_title", lang))
st.caption(T("subtitle", lang))

cfg = st.sidebar
cfg.header(T("edit_tickers", lang))

# Rank selector
cfg.subheader("Market-cap rank")
rank = cfg.selectbox("Top N (US/KR)", [10,20,30,40,50,60,70,80,90,100], index=1)

# ---- 자동 갱신 버튼 (야후 스크리너로 Top100 새로고침) ----
if cfg.button("🔄 Refresh Top100 lists (Yahoo Screener)"):
    try:
        refresh_top_lists(100)
        st.success("Top lists refreshed.")
    except Exception as e:
        st.warning(f"Failed to refresh: {e}")

data = load_tickers()
us_list_all = data.get("US", [])
kr_list_all = data.get("KR", [])
us_list, kr_list = select_by_rank(us_list_all, kr_list_all, rank)

new_us = cfg.text_area(T("us_list", lang), ",".join(us_list_all), help="e.g., NVDA, AAPL, MSFT")
new_kr = cfg.text_area(T("kr_list", lang), ",".join(kr_list_all), help="예: 005930.KS, 000660.KS")
if cfg.button(T("save_list", lang)):
    save_tickers({"US":[t.strip() for t in new_us.split(",") if t.strip()],
                  "KR":[t.strip() for t in new_kr.split(",") if t.strip()]})
    st.success("Saved." if lang=="EN" else "저장 완료.")

th = cfg.slider(T("threshold", lang), 5, 30, 10, 1) / 100.0
trend_only = cfg.checkbox(T("trend_only", lang), value=False)

auto = st.sidebar.checkbox(T("auto_refresh", lang), value=True)
interval = st.sidebar.slider(T("refresh_secs", lang), 10, 120, 30, 5)
if auto:
    st_autorefresh(interval=interval*1000, key="auto_refresh")

st.markdown(f"**{T('update_time', lang)}**: {now_kst()}")

if st.button(T("run_scan", lang)):
    st.rerun()

# Beginner tips
st.info(T("beginner_tip", lang))
st.caption(T("columns_help", lang))
st.info(T("tip_entry", lang))
st.info(T("tip_tp_sl", lang))
st.info(T("tip_trend", lang))
st.info(T("tip_valuation", lang))

# Tabs
tab_market, tab_scan, tab_earn, tab_news, tab_port = st.tabs(["📈 Market","🔎 Scanner","🗓 Earnings","📰 News","📊 Portfolio"])

with tab_market:
    col1, col2 = st.columns(2)
    with col1:
        vix = get_vix()
        st.metric("VIX (CBOE Volatility Index)", "-" if vix is None else f"{vix:.2f}")
    with col2:
        fg = get_fear_greed()
        if fg and fg.get("score") is not None:
            label = f"{fg['score']}"
            delta = fg.get("rating","")
            st.metric("CNN Fear & Greed", label, delta)
        else:
            st.warning("CNN Fear & Greed 지수를 불러오지 못했습니다. (잠시 후 다시 시도)")

    st.markdown("### Finviz Sector Map")
    st.link_button("Open Finviz Sector Map", FINVIZ_SEC_MAP_URL)

with tab_scan:
    df = analyze_all(us_list, kr_list)
    if df.empty:
        st.error(T("no_data", lang))
    else:
        df.insert(1, "Name", df["Ticker"].map(display_name))
        df["Valuation"] = df.apply(lambda r: valuation_flag(r, threshold=th), axis=1)
        if trend_only:
            df = df[df["Trend_OK"] == True]

        def earn_flag(s):
            try:
                if not s or s == "None": return ""
                d = pd.to_datetime(s).date()
                if d <= (datetime.today().date() + timedelta(days=7)):
                    return "🔔"
            except Exception:
                pass
            return ""
        df["EarningsAlert"] = df["NextEarnings"].map(earn_flag)

        st.subheader(T("scan_result", lang))
        st.dataframe(df, use_container_width=True)

        csv_bytes = df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
        st.download_button(T("download_csv", lang), data=csv_bytes, file_name="scan_live.csv", mime="text/csv")
        try:
            import openpyxl  # noqa
            from io import BytesIO
            bio = BytesIO(); df.to_excel(bio, index=False)
            st.download_button(T("download_xlsx", lang), data=bio.getvalue(), file_name="scan_live.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        except Exception:
            pass

with tab_earn:
    st.markdown("#### 내 종목 실적 캘린더 (향후 2주)")
    cal = earnings_calendar_for_list(us_list + kr_list, days_ahead=14)
    if cal.empty:
        st.info("실적 일정 데이터가 없습니다.")
    else:
        cal["Name"] = cal["Ticker"].map(display_name)
        st.dataframe(cal.sort_values("NextEarnings"), use_container_width=True)

with tab_news:
    st.markdown("### 미국 경제 뉴스")
    us_live = news_live("US"); us_yest = news_yesterday("US"); us_week = news_week("US")
    cols = st.columns(3)
    for i, (ttl, df_news) in enumerate([("실시간", us_live), ("전일", us_yest), ("최근 1주", us_week)]):
        with cols[i]:
            st.markdown(f"**{ttl}**")
            if df_news.empty:
                st.write("-")
            else:
                for _, r in df_news.head(12).iterrows():
                    st.write(f"- [{r['title']}]({r['link']})  \n  <small>{str(r['ts'])[:16]}</small>", unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### 한국 경제 뉴스")
    kr_live = news_live("KR"); kr_yest = news_yesterday("KR"); kr_week = news_week("KR")
    cols2 = st.columns(3)
    for i, (ttl, df_news) in enumerate([("실시간", kr_live), ("전일", kr_yest), ("최근 1주", kr_week)]):
        with cols2[i]:
            st.markdown(f"**{ttl}**")
            if df_news.empty:
                st.write("-")
            else:
                for _, r in df_news.head(12).iterrows():
                    st.write(f"- [{r['title']}]({r['link']})  \n  <small>{str(r['ts'])[:16]}</small>", unsafe_allow_html=True)

with tab_port:
    st.subheader(T("portfolio", lang))
    capital = st.number_input(T("capital", lang), min_value=0.0, value=100000.0, step=1000.0)
    risk_pct = st.slider(T("risk_per_trade", lang), 0.2, 5.0, 1.0, 0.1) / 100.0

    holdings = load_holdings()
    with st.expander(T("holdings_edit", lang)):
        text = ", ".join([f"{k}:{v}" for k,v in holdings.items()])
        edit = st.text_area("", value=text)
        if st.button(T("save_holdings", lang)):
            new = {}
            for tok in edit.split(","):
                if ":" in tok:
                    k,v = tok.strip().split(":")
                    try: new[k.strip()] = float(v.strip())
                    except: pass
            save_holdings
