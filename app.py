import streamlit as st
import signal as _signal

# 修复: Streamlit 在非主线程运行脚本，qstock 导入时注册 signal handler 会报错
_orig_signal = _signal.signal
def _safe_signal(signalnum, handler):
    try:
        return _orig_signal(signalnum, handler)
    except ValueError:
        pass
_signal.signal = _safe_signal

import qstock as qs

_signal.signal = _orig_signal  # 恢复原始 signal

import pandas as pd
from datetime import datetime

# 全部监控基金
WATCH_CODES = [
    "510300","510500","588000","159501","513100","159928","512890","512800",
    "006100","470009","375010","007751","110020","017641","021301","016440","025856","008774"
]
REFRESH_SECONDS = 300

st.set_page_config(page_title="仪表盘", layout="wide")
st.title("📊 仪表盘")
st.caption(f"每 {REFRESH_SECONDS//60} 分钟自动刷新 · 数据来源 qstock")

def get_fund_row(code):
    try:
        # 判断是场内ETF还是场外基金（简单规则：5开头多为场内ETF，场外基金用fund_price获取）
        # 实际上 qstock 的 realtime_data 对场外基金会返回空，需要区分处理
        
        # 先尝试作为场内ETF获取实时行情
        try:
            rt = qs.realtime_data(code=code)
            if rt is not None and not rt.empty and "最新" in rt.columns:
                price = rt["最新"].iloc[0]
                chg_pct = rt["涨幅"].iloc[0]
            else:
                raise ValueError("场内数据为空，尝试场外获取")
        except Exception:
            # 场外基金使用 fund_price 获取净值
            price_data = qs.fund_price(code)
            if price_data is not None and not price_data.empty:
                # fund_price 返回的是历史净值，取最新一条
                price = price_data.iloc[-1] if len(price_data.shape) == 1 else price_data.iloc[-1, 0]
                price = float(price)
                chg_pct = 0  # 场外基金没有实时涨跌幅
            else:
                raise ValueError("无法获取基金价格数据")

        # --- 基金基本信息 ---
        info_df = qs.fund_info(code)
        if info_df is None or info_df.empty:
            raise ValueError("无法获取基金基本信息")
        name = info_df["基金简称"].iloc[0]

        # --- 基金业绩表现 ---
        perf = qs.fund_perfmance(code)
        if perf is None or perf.empty:
            pmap = {}
        else:
            pmap = dict(zip(perf["时间段"], perf["收益率"]))

        return {
            "代码": code,
            "名称": name,
            "最新价": round(price, 4),
            "日涨跌幅(%)": round(chg_pct, 2),
            "近一周(%)": round(pmap.get("近一周", 0), 2),
            "近一月(%)": round(pmap.get("近一月", 0), 2),
            "近3月(%)": round(pmap.get("近三月", 0), 2),
            "近6月(%)": round(pmap.get("近六月", 0), 2),
            "近一年(%)": round(pmap.get("近一年", 0), 2),
            "近3年(%)": round(pmap.get("近三年", 0), 2),
            "更新时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    except Exception as e:
        return {"代码": code, "名称": f"获取失败:{str(e)}"}

@st.cache_data(ttl=REFRESH_SECONDS)
def load_all_fund_data():
    rows = [get_fund_row(c) for c in WATCH_CODES]
    return pd.DataFrame(rows)

df = load_all_fund_data()
st.dataframe(df, use_container_width=True, hide_index=True)

@st.cache_data
def generate_excel(df_data):
    import io
    buffer = io.BytesIO()
    df_data.to_excel(buffer, index=False)
    return buffer.getvalue()

excel_bytes = generate_excel(df)
st.download_button(
    label="📥 导出Excel文件",
    data=excel_bytes,
    file_name="监控表.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)

st.info(f"⏱ 每 {REFRESH_SECONDS//60} 分钟自动刷新最新行情")
