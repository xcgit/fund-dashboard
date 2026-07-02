#!/usr/bin/env python3
"""
定时更新基金数据脚本
每天早上7点通过 GitHub Actions 自动运行
"""
import signal as _signal
import sqlite3
import pandas as pd
from datetime import datetime
import os
import sys

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

# ============================================================
# 基金数据获取
# ============================================================
def get_fund_data(code):
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
        }
        
        return fund_dict
    except Exception as e:
        print(f"❌ {code} 获取失败: {e}")
        return None

# ============================================================
# 主程序
# ============================================================
def main():
    """主函数：更新所有基金数据"""
    # 基金列表
    ETF_CODES = [
        "510300","510500","588000","159501","513100","159928","512890","512800"
    ]
    OUTSIDE_CODES = [
        "006100","470009","375010","007751","110020","017641","021301","016440","025856","008774"
    ]
    
    ALL_CODES = ETF_CODES + OUTSIDE_CODES
    
    # 初始化数据库
    init_db()
    
    print(f"📊 开始更新 {len(ALL_CODES)} 只基金数据...")
    print(f"⏰ 更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    success_count = 0
    fail_count = 0
    
    for code in ALL_CODES:
        print(f"⏳ 正在获取 {code}...", end="")
        fund_dict = get_fund_data(code)
        
        if fund_dict:
            if save_fund_to_db(fund_dict):
                print(f" ✅ 成功")
                success_count += 1
            else:
                print(f" ❌ 保存失败")
                fail_count += 1
        else:
            print(f" ❌ 获取失败")
            fail_count += 1
    
    print(f"\n📊 更新完成: 成功 {success_count} 只, 失败 {fail_count} 只")
    
    # 返回状态码
    return 0 if fail_count == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
