import streamlit as st
import signal as _signal
import sqlite3
import pandas as pd
from datetime import datetime
import os

# 清除系统代理，避免干扰东方财富 API 访问
for key in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'ALL_PROXY', 'all_proxy']:
    os.environ.pop(key, None)

# qstock 懒加载：不在文件头部导入，避免导入时触发网络请求导致报错
# 只在 get_fund_row_from_api 函数内部按需导入
_qs = None

def get_qs():
    """懒加载 qstock，只在首次调用时导入"""
    global _qs
    if _qs is None:
        # 修复: Streamlit 在非主线程运行脚本，qstock 导入时注册 signal handler 会报错
        _orig_signal = _signal.signal
        def _safe_signal(signalnum, handler):
            try:
                return _orig_signal(signalnum, handler)
            except ValueError:
                pass
        _signal.signal = _safe_signal
        try:
            import qstock as qs
            _qs = qs
        finally:
            _signal.signal = _orig_signal  # 恢复原始 signal
    return _qs

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
        
        # 增量添加新字段（兼容已有数据库）
        for col in ['amount', 'scale', 'premium', 'pe', 'pb', 'dividend']:
            try:
                c.execute(f"ALTER TABLE fund_data ADD COLUMN {col} TEXT DEFAULT ''")
            except:
                pass
        
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
                      three_month_ret, six_month_ret, year_ret, three_year_ret, update_time,
                      amount, scale, premium, pe, pb, dividend)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
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
                   fund_dict.get('更新时间', datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                   str(fund_dict.get('成交额', '0')),
                   str(fund_dict.get('规模', '0')),
                   str(fund_dict.get('折溢价率(%)', 0)),
                   str(fund_dict.get('市盈率', 0)),
                   str(fund_dict.get('市净率', 0)),
                   str(fund_dict.get('股息率(%)', 0))))
        
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
                          three_month_ret, six_month_ret, year_ret, three_year_ret, update_time,
                          amount, scale, premium, pe, pb, dividend
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
                "成交额": result[11] if len(result) > 11 else "0",
                "规模": result[12] if len(result) > 12 else "0",
                "折溢价率(%)": float(result[13]) if len(result) > 13 and result[13] else 0,
                "市盈率": float(result[14]) if len(result) > 14 and result[14] else 0,
                "市净率": float(result[15]) if len(result) > 15 and result[15] else 0,
                "股息率(%)": float(result[16]) if len(result) > 16 and result[16] else 0,
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
    """从 API 获取基金数据（懒加载 qstock），错误信息写入页面"""
    try:
        qs = get_qs()
        if qs is None:
            raise ValueError("qstock 导入失败")
        
        price = None
        chg_pct = 0
        amount = 0       # 成交额
        scale = 0         # 规模(总市值)
        premium = 0       # 折溢价率
        pe = 0            # 市盈率
        pb = 0            # 市净率
        dividend = 0      # 股息率
        
        # 判断是场内ETF还是场外基金
        try:
            rt = qs.realtime_data(code=code)
            if rt is not None and not rt.empty and "最新" in rt.columns:
                price = rt["最新"].iloc[0]
                chg_pct = rt["涨幅"].iloc[0] if "涨幅" in rt.columns else 0
                # 打印所有列名方便调试（只打一次）
                if not hasattr(get_fund_row_from_api, '_debug_printed'):
                    st.info(f"realtime_data 可用列: {list(rt.columns)}")
                    get_fund_row_from_api._debug_printed = True
                # 成交额 - 字符串格式如 "1.23亿"，直接存
                if "成交额" in rt.columns:
                    amount = str(rt["成交额"].iloc[0] or '0')
                # 规模 - 用流通市值，字符串格式
                if "流通市值" in rt.columns:
                    scale = str(rt["流通市值"].iloc[0] or '0')
                elif "总市值" in rt.columns:
                    scale = str(rt["总市值"].iloc[0] or '0')
                # 折溢价率 - 通过最新价和昨收计算，或 IOPV
                if "昨收" in rt.columns and price and price > 0:
                    prev = float(rt["昨收"].iloc[0] or 0)
                    if prev > 0:
                        premium = round((price - prev) / prev * 100, 2)
                # 市盈率 - 直接是数字
                if "市盈率" in rt.columns:
                    pe = float(rt["市盈率"].iloc[0] or 0)
                # 市净率 - 不在列表里，跳过
                # 股息率 - 不在列表里，跳过
            else:
                raise ValueError("场内数据为空，尝试场外获取")
        except Exception as e1:
            st.warning(f"[{code}] 场内获取失败: {e1}")
            try:
                price_data = qs.fund_price(code)
                if price_data is not None and not price_data.empty:
                    price = price_data.iloc[-1] if len(price_data.shape) == 1 else price_data.iloc[-1, 0]
                    price = float(price)
                    chg_pct = 0
                else:
                    raise ValueError("无法获取基金价格数据")
            except Exception as e2:
                st.error(f"[{code}] 场外获取失败: {e2}")
                raise ValueError(f"场内={e1}, 场外={e2}")

        # 基金基本信息
        try:
            info_df = qs.fund_info(code)
            if info_df is None or info_df.empty:
                raise ValueError("无法获取基金基本信息")
            name = info_df["基金简称"].iloc[0]
        except Exception as e3:
            st.error(f"[{code}] 基金信息获取失败: {e3}")
            raise ValueError(f"基金信息获取失败: {e3}")

        # 基金业绩表现
        try:
            perf = qs.fund_perfmance(code)
            if perf is None or perf.empty:
                pmap = {}
            else:
                pmap = dict(zip(perf["时间段"], perf["收益率"]))
        except Exception as e4:
            st.warning(f"[{code}] 业绩获取失败: {e4}")
            pmap = {}
        
        # 获取 PE/PB/股息率（场内 ETF）
        if code.isdigit() and len(code) == 6:
            try:
                stock_info = qs.stock_info(code)
                if stock_info is not None and not stock_info.empty:
                    row = stock_info.iloc[0]
                    pe = float(row.get('市盈率-动态', row.get('市盈率', 0)) or 0)
                    pb = float(row.get('市净率', 0) or 0)
            except Exception:
                pass

        fund_dict = {
            "代码": code,
            "名称": name,
            "最新价": round(price, 4) if price else 0,
            "日涨跌幅(%)": round(chg_pct, 2) if chg_pct else 0,
            "成交额": str(amount) if amount else "0",
            "规模": str(scale) if scale else "0",
            "折溢价率(%)": round(premium, 2),
            "市盈率": round(pe, 2) if pe else 0,
            "市净率": round(pb, 2) if pb else 0,
            "股息率(%)": round(dividend, 2),
            "近一周(%)": round(pmap.get("近一周", 0), 2),
            "近一月(%)": round(pmap.get("近一月", 0), 2),
            "近3月(%)": round(pmap.get("近三月", 0), 2),
            "近6月(%)": round(pmap.get("近六月", 0), 2),
            "近一年(%)": round(pmap.get("近一年", 0), 2),
            "近3年(%)": round(pmap.get("近三年", 0), 2),
            "更新时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "数据源": "🌐 API"
        }
        
        save_fund_to_db(fund_dict)
        return fund_dict
    except Exception as e:
        return {"代码": code, "名称": f"获取失败:{str(e)[:50]}", "数据源": "❌ 错误"}

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
    
    # 按钮区：添加
    col1, col2, col3 = st.columns([1, 1, 8])
    with col1:
        add_label = "✅ 取消添加" if st.session_state.get('show_etf_add') else "➕ 添加"
        if st.button(add_label, key="add_etf_btn_toggle", type="secondary"):
            st.session_state.show_etf_add = not st.session_state.get('show_etf_add', False)
            st.rerun()
    with col2:
        if st.button("🔄 全部刷新", key="refresh_all_etf", type="primary"):
            st.session_state.refreshed_etf_codes = list(ETF_CODES)
            st.rerun()
    
    # 添加基金表单
    if st.session_state.get('show_etf_add', False):
        with st.container(border=True):
            st.markdown("**添加场内 ETF：**")
            col_a, col_b = st.columns([4, 1])
            with col_a:
                new_etf = st.text_input(
                    "基金代码", key="new_etf_code",
                    placeholder="例如: 510300", label_visibility="collapsed"
                )
            with col_b:
                if st.button("确认添加", key="confirm_add_etf", use_container_width=True) and new_etf:
                    code = new_etf.strip()
                    if code not in ETF_CODES:
                        if add_fund_to_list('etf', code):
                            ETF_CODES.append(code)
                            st.success(f"✅ 已添加 {code}")
                            st.session_state.show_etf_add = False
                            st.rerun()
                    else:
                        st.warning("⚠️ 已在列表中")
    
    # 加载数据
    with st.spinner("正在加载场内 ETF 数据..."):
        rows = []
        refreshed_codes = st.session_state.get('refreshed_etf_codes', [])
        for code in ETF_CODES:
            fund_data = get_fund_row(code, force_refresh=(code in refreshed_codes))
            rows.append(fund_data)
        if refreshed_codes:
            st.session_state.refreshed_etf_codes = []
    
    # 用 data_editor 显示，第一列是勾选框
    if rows:
        df_etf = pd.DataFrame(rows)
        df_etf.insert(0, '选择', False)
        # 其他列只读
        disabled_cols = [c for c in df_etf.columns if c != '选择']
        
        edited = st.data_editor(
            df_etf, use_container_width=True, hide_index=True,
            disabled=disabled_cols, key='editor_etf'
        )
        
        # 获取选中的基金
        selected_codes = []
        for i, row in edited.iterrows():
            if row['选择']:
                selected_codes.append(row['代码'])
        
        # 表格外操作按钮
        col_btn1, col_btn2, col_info = st.columns([1, 1, 4])
        with col_btn1:
            if st.button("🔄 刷新选中", key="refresh_sel_etf", type="primary", use_container_width=True):
                if selected_codes:
                    for code in selected_codes:
                        get_fund_row_from_api(code)
                    st.session_state.refreshed_etf_codes = selected_codes
                    st.success(f"✅ 已刷新 {len(selected_codes)} 只基金")
                    st.rerun()
                else:
                    st.warning("⚠️ 请先在表格中勾选基金")
        with col_btn2:
            if st.button("🗑️ 删除选中", key="del_sel_etf", type="secondary", use_container_width=True):
                if selected_codes:
                    for code in selected_codes:
                        remove_fund_from_list('etf', code)
                        if code in ETF_CODES:
                            ETF_CODES.remove(code)
                    st.success(f"✅ 已删除 {len(selected_codes)} 只基金")
                    st.rerun()
                else:
                    st.warning("⚠️ 请先在表格中勾选基金")
    
    st.caption(f"当前监控 {len(ETF_CODES)} 只场内 ETF")

with tab2:
    st.subheader("场外基金行情")
    
    # 按钮区：添加 / 全部刷新
    col1, col2, col3 = st.columns([1, 1, 8])
    with col1:
        add_label = "✅ 取消添加" if st.session_state.get('show_outside_add') else "➕ 添加"
        if st.button(add_label, key="add_outside_btn_toggle", type="secondary"):
            st.session_state.show_outside_add = not st.session_state.get('show_outside_add', False)
            st.rerun()
    with col2:
        if st.button("🔄 全部刷新", key="refresh_all_outside", type="primary"):
            st.session_state.refreshed_outside_codes = list(OUTSIDE_CODES)
            st.rerun()
    
    # 添加基金表单
    if st.session_state.get('show_outside_add', False):
        with st.container(border=True):
            st.markdown("**添加场外基金：**")
            col_a, col_b = st.columns([4, 1])
            with col_a:
                new_outside = st.text_input(
                    "基金代码", key="new_outside_code",
                    placeholder="例如: 006100", label_visibility="collapsed"
                )
            with col_b:
                if st.button("确认添加", key="confirm_add_outside", use_container_width=True) and new_outside:
                    code = new_outside.strip()
                    if code not in OUTSIDE_CODES:
                        if add_fund_to_list('outside', code):
                            OUTSIDE_CODES.append(code)
                            st.success(f"✅ 已添加 {code}")
                            st.session_state.show_outside_add = False
                            st.rerun()
                    else:
                        st.warning("⚠️ 已在列表中")
    
    # 加载数据
    with st.spinner("正在加载场外基金数据..."):
        rows = []
        refreshed_codes = st.session_state.get('refreshed_outside_codes', [])
        for code in OUTSIDE_CODES:
            fund_data = get_fund_row(code, force_refresh=(code in refreshed_codes))
            rows.append(fund_data)
        if refreshed_codes:
            st.session_state.refreshed_outside_codes = []
    
    # 用 data_editor 显示，第一列是勾选框
    if rows:
        df_outside = pd.DataFrame(rows)
        df_outside.insert(0, '选择', False)
        disabled_cols = [c for c in df_outside.columns if c != '选择']
        
        edited = st.data_editor(
            df_outside, use_container_width=True, hide_index=True,
            disabled=disabled_cols, key='editor_outside'
        )
        
        # 获取选中的基金
        selected_codes = []
        for i, row in edited.iterrows():
            if row['选择']:
                selected_codes.append(row['代码'])
        
        # 表格外操作按钮
        col_btn1, col_btn2, col_info = st.columns([1, 1, 4])
        with col_btn1:
            if st.button("🔄 刷新选中", key="refresh_sel_outside", type="primary", use_container_width=True):
                if selected_codes:
                    for code in selected_codes:
                        get_fund_row_from_api(code)
                    st.session_state.refreshed_outside_codes = selected_codes
                    st.success(f"✅ 已刷新 {len(selected_codes)} 只基金")
                    st.rerun()
                else:
                    st.warning("⚠️ 请先在表格中勾选基金")
        with col_btn2:
            if st.button("🗑️ 删除选中", key="del_sel_outside", type="secondary", use_container_width=True):
                if selected_codes:
                    for code in selected_codes:
                        remove_fund_from_list('outside', code)
                        if code in OUTSIDE_CODES:
                            OUTSIDE_CODES.remove(code)
                    st.success(f"✅ 已删除 {len(selected_codes)} 只基金")
                    st.rerun()
                else:
                    st.warning("⚠️ 请先在表格中勾选基金")
    
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
