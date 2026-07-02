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
        
        # 创建基金列表配置表
        c.execute('''CREATE TABLE IF NOT EXISTS fund_list
                     (type TEXT, code TEXT, create_time TEXT,
                      PRIMARY KEY (type, code))''')
        
        conn.commit()
        conn.close()
        print("✅ 数据库初始化成功")
    except Exception as e:
        print(f"❌ 数据库初始化失败: {e}")

def load_fund_list():
    """从数据库加载基金列表"""
    try:
        conn = sqlite3.connect('fund_dashboard.db', check_same_thread=False)
        c = conn.cursor()
        
        # 读取场内ETF列表
        c.execute("SELECT code FROM fund_list WHERE type='etf' ORDER BY create_time")
        etf_codes = [row[0] for row in c.fetchall()]
        
        # 读取场外基金列表
        c.execute("SELECT code FROM fund_list WHERE type='outside' ORDER BY create_time")
        outside_codes = [row[0] for row in c.fetchall()]
        
        conn.close()
        
        # 如果数据库为空，插入默认数据
        if not etf_codes and not outside_codes:
            print("📊 数据库无基金列表，插入默认数据...")
            return insert_default_fund_list()
        
        return etf_codes, outside_codes
    except Exception as e:
        print(f"❌ 加载基金列表失败: {e}")
        return insert_default_fund_list()

def insert_default_fund_list():
    """插入默认基金列表到数据库"""
    default_etf = ["510300","510500","588000","159501","513100","159928","512890","512800"]
    default_outside = ["006100","470009","375010","007751","110020","017641","021301","016440","025856","008774"]
    
    try:
        conn = sqlite3.connect('fund_dashboard.db', check_same_thread=False)
        c = conn.cursor()
        
        # 插入默认场内ETF
        for code in default_etf:
            c.execute("INSERT OR IGNORE INTO fund_list (type, code, create_time) VALUES (?, ?, ?)",
                     ('etf', code, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        
        # 插入默认场外基金
        for code in default_outside:
            c.execute("INSERT OR IGNORE INTO fund_list (type, code, create_time) VALUES (?, ?, ?)",
                     ('outside', code, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        
        conn.commit()
        conn.close()
        
        print("✅ 默认基金列表已插入数据库")
        return default_etf, default_outside
    except Exception as e:
        print(f"❌ 插入默认基金列表失败: {e}")
        return default_etf, default_outside

def add_fund_to_list(fund_type, code):
    """添加基金到列表"""
    try:
        conn = sqlite3.connect('fund_dashboard.db', check_same_thread=False)
        c = conn.cursor()
        
        c.execute("INSERT OR IGNORE INTO fund_list (type, code, create_time) VALUES (?, ?, ?)",
                 (fund_type, code, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"❌ 添加基金失败: {e}")
        return False

def remove_fund_from_list(fund_type, code):
    """从列表删除基金"""
    try:
        conn = sqlite3.connect('fund_dashboard.db', check_same_thread=False)
        c = conn.cursor()
        
        c.execute("DELETE FROM fund_list WHERE type=? AND code=?", (fund_type, code))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"❌ 删除基金失败: {e}")
        return False

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
# 从数据库加载基金列表
ETF_CODES, OUTSIDE_CODES = load_fund_list()

REFRESH_SECONDS = 300

# ============================================================
# 自动更新检查
# ============================================================
def check_auto_update():
    """检查是否需要自动更新（每天早上7点后首次访问时触发）"""
    try:
        # 读取上次更新时间
        last_update_file = 'last_update.txt'
        last_update_date = None
        
        if os.path.exists(last_update_file):
            with open(last_update_file, 'r') as f:
                last_update_date = f.read().strip()
        
        # 获取当前日期和时间
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")
        current_hour = now.hour
        
        # 如果今天还没更新，且当前时间 >= 7点，则触发更新
        if last_update_date != today and current_hour >= 7:
            print(f"📊 触发自动更新: {today} {now.strftime('%H:%M:%S')}")
            
            # 从数据库重新加载基金列表
            etf_codes, outside_codes = load_fund_list()
            ALL_CODES = etf_codes + outside_codes
            
            updated_count = 0
            
            for code in ALL_CODES:
                fund_dict = get_fund_row_from_api(code)
                if "获取失败" not in fund_dict.get("名称", ""):
                    updated_count += 1
            
            # 保存更新日期
            with open(last_update_file, 'w') as f:
                f.write(today)
            
            print(f"✅ 自动更新完成: {updated_count}/{len(ALL_CODES)} 只基金")
            
            return True
        
        return False
    except Exception as e:
        print(f"❌ 自动更新检查失败: {e}")
        return False

# 初始化数据库
init_db()

# 检查并触发自动更新
check_auto_update()

st.set_page_config(page_title="仪表盘", layout="wide")
st.title("📊 仪表盘")
st.caption(f"数据来源: SQLite + qstock · 支持手动刷新")

# 创建两个 Tab
tab1, tab2 = st.tabs(["📈 场内 ETF", "🏢 场外基金"])

with tab1:
    st.subheader("场内 ETF 行情")
    
    # 手动刷新按钮
    col1, col2, col3 = st.columns([1, 1, 8])
    with col1:
        if st.button("🔄 刷新场内", key="refresh_etf", type="primary"):
            st.session_state.force_refresh_etf = True
            st.success("✅ 正在从 API 获取最新数据...")
            st.rerun()
    with col2:
        if st.button("🗑️ 管理", key="manage_etf", type="secondary"):
            st.session_state.show_etf_manage = not st.session_state.get('show_etf_manage', False)
    
    # 基金管理界面
    if st.session_state.get('show_etf_manage', False):
        with st.expander("📝 管理场内 ETF 列表", expanded=True):
            # 显示当前列表
            st.write("**当前列表：**")
            for code in ETF_CODES:
                col_a, col_b = st.columns([1, 1])
                with col_a:
                    st.text(code)
                with col_b:
                    if st.button(f"🗑️", key=f"del_etf_{code}", help="删除"):
                        if remove_fund_from_list('etf', code):
                            ETF_CODES.remove(code)
                            st.success(f"✅ 已删除 {code}")
                            st.rerun()
            
            # 添加新基金
            st.write("**添加基金：**")
            new_etf = st.text_input("输入基金代码", key="new_etf_code", placeholder="例如: 510300")
            if st.button("➕ 添加", key="add_etf_btn") and new_etf:
                code = new_etf.strip()
                if code not in ETF_CODES:
                    if add_fund_to_list('etf', code):
                        ETF_CODES.append(code)
                        st.success(f"✅ 已添加 {code}")
                        st.rerun()
                else:
                    st.warning("⚠️ 已在列表中")
    
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
    st.caption(f"当前监控 {len(ETF_CODES)} 只场内 ETF")

with tab2:
    st.subheader("场外基金行情")
    
    # 手动刷新按钮
    col1, col2, col3 = st.columns([1, 1, 8])
    with col1:
        if st.button("🔄 刷新场外", key="refresh_outside", type="primary"):
            st.session_state.force_refresh_outside = True
            st.success("✅ 正在从 API 获取最新数据...")
            st.rerun()
    with col2:
        if st.button("🗑️ 管理", key="manage_outside", type="secondary"):
            st.session_state.show_outside_manage = not st.session_state.get('show_outside_manage', False)
    
    # 基金管理界面
    if st.session_state.get('show_outside_manage', False):
        with st.expander("📝 管理场外基金列表", expanded=True):
            # 显示当前列表
            st.write("**当前列表：**")
            for code in OUTSIDE_CODES:
                col_a, col_b = st.columns([1, 1])
                with col_a:
                    st.text(code)
                with col_b:
                    if st.button(f"🗑️", key=f"del_outside_{code}", help="删除"):
                        if remove_fund_from_list('outside', code):
                            OUTSIDE_CODES.remove(code)
                            st.success(f"✅ 已删除 {code}")
                            st.rerun()
            
            # 添加新基金
            st.write("**添加基金：**")
            new_outside = st.text_input("输入基金代码", key="new_outside_code", placeholder="例如: 006100")
            if st.button("➕ 添加", key="add_outside_btn") and new_outside:
                code = new_outside.strip()
                if code not in OUTSIDE_CODES:
                    if add_fund_to_list('outside', code):
                        OUTSIDE_CODES.append(code)
                        st.success(f"✅ 已添加 {code}")
                        st.rerun()
                else:
                    st.warning("⚠️ 已在列表中")
    
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
    st.caption(f"当前监控 {len(OUTSIDE_CODES)} 只场外基金")

# 导出 Excel（合并两个 Tab 的数据）
@st.cache_data
def generate_excel():
    import io
    # 从数据库重新加载基金列表
    etf_codes, outside_codes = load_fund_list()
    all_codes = etf_codes + outside_codes
    
    # 合并所有基金数据
    all_rows = []
    for code in all_codes:
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
