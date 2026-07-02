import streamlit as st
import signal as _signal
import sqlite3
import pandas as pd
from datetime import datetime

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

# ============================================================
# 数据库初始化
# ============================================================
def init_db():
    """初始化 SQLite 数据库"""
    try:
        conn = sqlite3.connect('fund_dashboard.db', check_same_thread=False)
        c = conn.cursor()
        
        # 创建基金数据表
        c.execute('''CREATE TABLE IF NOT EXISTS fund_data
                     (code TEXT, name TEXT, price REAL, chg_pct REAL,
                      week_ret REAL, month_ret REAL, three_month_ret REAL,
                      six_month_ret REAL, year_ret REAL, three_year_ret REAL,
                      update_time TEXT,
                      PRIMARY KEY (code, update_time))''')
        
        conn.commit()
        conn.close()
        print("✅ 数据库初始化成功")
    except Exception as e:
        print(f"❌ 数据库初始化失败: {e}")

def save_fund_to_db(fund_dict):
    """将基金数据写入 SQLite"""
    try:
        conn = sqlite3.connect('fund_dashboard.db', check_same_thread=False)
        c = conn.cursor()
        
        c.execute('''INSERT OR REPLACE INTO fund_data 
                     (code, name, price, chg_pct, week_ret, month_ret, 
                      three_month_ret, six_month_ret, year_ret, three_year_ret, update_time)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                  (fund_dict['代码'], 
                   fund_dict['名称'], 
                   fund_dict.get('最新价', 0),
                   fund_dict.get('日涨跌幅(%)', 0),
                   fund_dict.get('近一周(%)', 0),
                   fund_dict.get('近一月(%)', 0),
                   fund_dict.get('近3月(%)', 0),
                   fund_dict.get('近6月(%)', 0),
                   fund_dict.get('近一年(%)', 0),
                   fund_dict.get('近3年(%)', 0),
                   fund_dict.get('更新时间', datetime.now().strftime("%Y-%m-%d %H:%M:%S"))))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"数据库写入失败: {e}")
        return False

def load_fund_from_db(code):
    """从 SQLite 读取基金最新数据"""
    try:
        conn = sqlite3.connect('fund_dashboard.db', check_same_thread=False)
        c = conn.cursor()
        
        # 查询最新的数据
        c.execute('''SELECT code, name, price, chg_pct, week_ret, month_ret,
                          three_month_ret, six_month_ret, year_ret, three_year_ret, update_time
                   FROM fund_data 
                   WHERE code = ?
                   ORDER BY update_time DESC 
                   LIMIT 1''', (code,))
        
        result = c.fetchone()
        conn.close()
        
        if result:
            return {
                "代码": result[0],
                "名称": result[1],
                "最新价": result[2],
                "日涨跌幅(%)": result[3],
                "近一周(%)": result[4],
                "近一月(%)": result[5],
                "近3月(%)": result[6],
                "近6月(%)": result[7],
                "近一年(%)": result[8],
                "近3年(%)": result[9],
                "更新时间": result[10],
                "数据源": "📀 SQLite"
            }
        return None
    except Exception as e:
        print(f"数据库读取失败: {e}")
        return None

# ============================================================
# 基金数据获取
# ============================================================
def get_fund_row_from_api(code):
    """从 API 获取基金数据"""
    try:
        # 判断是场内ETF还是场外基金
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
                price = price_data.iloc[-1] if len(price_data.shape) == 1 else price_data.iloc[-1, 0]
                price = float(price)
                chg_pct = 0
            else:
                raise ValueError("无法获取基金价格数据")

        # 基金基本信息
        info_df = qs.fund_info(code)
        if info_df is None or info_df.empty:
            raise ValueError("无法获取基金基本信息")
        name = info_df["基金简称"].iloc[0]

        # 基金业绩表现
        perf = qs.fund_perfmance(code)
        if perf is None or perf.empty:
            pmap = {}
        else:
            pmap = dict(zip(perf["时间段"], perf["收益率"]))

        fund_dict = {
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
            "更新时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "数据源": "🌐 API"
        }
        
        # 写入数据库
        save_fund_to_db(fund_dict)
        
        return fund_dict
    except Exception as e:
        return {"代码": code, "名称": f"获取失败:{str(e)}", "数据源": "❌ 错误"}

def get_fund_row(code, force_refresh=False):
    """获取基金数据（优先从数据库，除非强制刷新）"""
    if not force_refresh:
        # 先尝试从数据库读取
        data = load_fund_from_db(code)
        if data:
            return data
    
    # 数据库没有数据或强制刷新，从 API 获取
    return get_fund_row_from_api(code)

# ============================================================
# 主程序
# ============================================================
# 基金分类
ETF_CODES = [
    "510300","510500","588000","159501","513100","159928","512890","512800"
]
OUTSIDE_CODES = [
    "006100","470009","375010","007751","110020","017641","021301","016440","025856","008774"
]

REFRESH_SECONDS = 300

# 初始化数据库
init_db()

st.set_page_config(page_title="仪表盘", layout="wide")
st.title("📊 仪表盘")
st.caption(f"数据来源: SQLite + qstock · 支持手动刷新")

# 创建两个 Tab
tab1, tab2 = st.tabs(["📈 场内 ETF", "🏢 场外基金"])

with tab1:
    st.subheader("场内 ETF 行情")
    
    # 手动刷新按钮
    col1, col2 = st.columns([1, 9])
    with col1:
        if st.button("🔄 刷新场内", key="refresh_etf", type="primary"):
            st.session_state.force_refresh_etf = True
            st.success("✅ 正在从 API 获取最新数据...")
            st.rerun()
    
    # 加载数据
    with st.spinner("正在加载场内 ETF 数据..."):
        rows = []
        for code in ETF_CODES:
            force = st.session_state.get('force_refresh_etf', False)
            fund_data = get_fund_row(code, force_refresh=force)
            rows.append(fund_data)
        
        # 重置强制刷新标志
        if 'force_refresh_etf' in st.session_state:
            del st.session_state.force_refresh_etf
    
    df_etf = pd.DataFrame(rows)
    st.dataframe(df_etf, use_container_width=True, hide_index=True)

with tab2:
    st.subheader("场外基金行情")
    
    # 手动刷新按钮
    col1, col2 = st.columns([1, 9])
    with col1:
        if st.button("🔄 刷新场外", key="refresh_outside", type="primary"):
            st.session_state.force_refresh_outside = True
            st.success("✅ 正在从 API 获取最新数据...")
            st.rerun()
    
    # 加载数据
    with st.spinner("正在加载场外基金数据..."):
        rows = []
        for code in OUTSIDE_CODES:
            force = st.session_state.get('force_refresh_outside', False)
            fund_data = get_fund_row(code, force_refresh=force)
            rows.append(fund_data)
        
        # 重置强制刷新标志
        if 'force_refresh_outside' in st.session_state:
            del st.session_state.force_refresh_outside
    
    df_outside = pd.DataFrame(rows)
    st.dataframe(df_outside, use_container_width=True, hide_index=True)

# 导出 Excel（合并两个 Tab 的数据）
@st.cache_data
def generate_excel():
    import io
    # 合并所有基金数据
    all_rows = []
    for code in ETF_CODES + OUTSIDE_CODES:
        data = load_fund_from_db(code)
        if data:
            all_rows.append(data)
        else:
            all_rows.append(get_fund_row_from_api(code))
    
    df_all = pd.DataFrame(all_rows)
    buffer = io.BytesIO()
    df_all.to_excel(buffer, index=False)
    return buffer.getvalue()

excel_bytes = generate_excel()
st.download_button(
    label="📥 导出Excel文件",
    data=excel_bytes,
    file_name="监控表.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)

st.info(f"💡 提示: 首次运行会从 API 获取数据并保存到数据库，后续直接从数据库读取（除非点击「刷新」按钮）")
