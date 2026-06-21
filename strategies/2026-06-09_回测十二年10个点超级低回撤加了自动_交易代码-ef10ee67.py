# Clone from JoinQuant
# postId: ef10ee67c67ce11099b18dad0207f638
# backtestId: 441fde5ce1a47282cd651066f545f2a2
# title: 回测十二年10个点超级低回撤加了自动 交易代码

# -*- coding: utf-8 -*-
# 标题：昨日炸板策略 - 按比例同步实盘版（完美融合增强版）
# 完美融合方案：保守版的高收益因子 + 综合优化版的实盘稳定性 + 增强异常处理
# 新增：13:00问题纯观察功能（只记录事实，不分析条件）和持仓对比功能

import pandas as pd
import numpy as np
import datetime as dt
from datetime import datetime, timedelta
from jqlib.technical_analysis import *
from jqdata import *
import json
import os
import time
import re
import traceback

#################################实盘交易核心组件#######################################
import hashlib
import hmac
import uuid
from urllib.parse import urlparse, parse_qs, urlencode
import requests
from requests.auth import AuthBase

your_server_addr = "111/"
secretId = "222="
secretKey = "333="

# 实盘控制类 - 修复缩进错误
class a():
    pass  # 这行必须有正确的缩进

A = a()
A.isShipan = 0  

class SignAuth(AuthBase):
    """实盘认证类"""
    def __init__(self, secret_id: str = secretId, secret_key: str = secretKey):
        self.secret_id = secret_id
        self.secret_key = secret_key

    def __call__(self, r):
        timestamp = str(int(time.time()))
        nonce = str(uuid.uuid4())
        body = r.body or b""
        parsed_url = urlparse(r.url)
        query_params = parse_qs(parsed_url.query)
        sorted_query_params = dict(sorted(query_params.items()))
        sorted_params_str = urlencode(sorted_query_params, doseq=True)
        
        sign_data = [
            r.method,
            r.path_url.split("?")[0],
            sorted_params_str,
            timestamp,
            nonce,
            body.decode('utf-8') if isinstance(body, bytes) else body
        ]
        sign_data = '\n'.join(sign_data)
        
        signature = hmac.new(self.secret_key.encode('utf-8'), sign_data.encode('utf-8'), hashlib.sha256)
        signature = signature.digest().hex()
        
        authorization = f'hmac id="{self.secret_id}", ts="{timestamp}", nonce="{nonce}", sig="{signature}"'
        r.headers['Authorization'] = authorization
        return r

def format_stock_code(raw_code):
    """统一格式化股票代码为6位数字"""
    if not raw_code:
        return None
    
    code_str = str(raw_code).strip()
    
    if code_str.isdigit() and len(code_str) == 6:
        return code_str
    
    numbers = re.findall(r'\d+', code_str)
    if not numbers:
        return None
    
    num_str = numbers[0]
    
    if len(num_str) > 6:
        num_str = num_str[:6]
    elif len(num_str) < 6:
        num_str = num_str.zfill(6)
    
    return num_str if num_str.isdigit() and len(num_str) == 6 else None

#################################实盘API函数（增强版）#######################################
def buy_stock_real(stock_code, price, vol, reason=""):
    """实盘买入函数 - 增强日志"""
    try:
        log.info(f"🚀 发送实盘买入信号 [{reason}]")
        log.info(f"  股票: {stock_code} 价格: {price:.2f} 数量: {vol}")
        
        if vol < 100:
            log.warning(f"买入数量不足100股: {vol}")
            return False
            
        if price <= 0:
            log.error(f"买入价格无效: {price}")
            return False
        
        stock_code_6 = format_stock_code(stock_code)
        if not stock_code_6:
            log.error(f"股票代码格式化失败: {stock_code}")
            return False
        
        result = requests.post(your_server_addr + "sync/buy", json={
            "code": str(stock_code_6),
            "price": float(price),
            "volume": int(vol)
        }, auth=SignAuth(), timeout=10)
        
        log.info(f"买入响应状态码: {result.status_code}")
        
        if result.status_code == 200:
            log.info(f"✅ 实盘买入信号发送成功: {stock_code_6}")
            return True
        else:
            log.error(f"❌ 实盘买入信号发送失败: HTTP状态码 {result.status_code}")
            return False
            
    except Exception as e:
        log.error(f"🔥 实盘买入异常: {e}")
        return False

def sell_stock_real(stock_code, price, vol, reason=""):
    """实盘卖出函数 - 修复版（允许卖出零股）"""
    try:
        log.info(f"📤 发送实盘卖出信号 [{reason}]")
        log.info(f"  股票: {stock_code} 价格: {price:.2f} 数量: {vol}")
        
        # 修复点：将vol < 100改为vol <= 0，允许卖出不足100股的零股
        if vol <= 0:
            log.warning(f"卖出数量无效: {vol}")
            return False
            
        if price <= 0:
            log.error(f"卖出价格无效: {price}")
            return False
        
        stock_code_6 = format_stock_code(stock_code)
        if not stock_code_6:
            log.error(f"股票代码格式化失败: {stock_code}")
            return False
        
        result = requests.post(your_server_addr + "sell", json={
            "code": str(stock_code_6),
            "price": float(price),
            "volume": int(vol)
        }, auth=SignAuth(), timeout=10)
        
        log.info(f"卖出响应状态码: {result.status_code}")
        
        if result.status_code == 200:
            log.info(f"✅ 实盘卖出信号发送成功: {stock_code_6} (数量: {vol}股)")
            return True
        else:
            log.error(f"❌ 实盘卖出信号发送失败: HTTP状态码 {result.status_code}")
            return False
            
    except Exception as e:
        log.error(f"🔥 实盘卖出异常: {e}")
        return False

def get_account_real():
    """获取实盘账户信息"""
    try:
        result = requests.get(your_server_addr + "funding", auth=SignAuth(), timeout=10)
        
        if result.status_code == 200:
            try:
                response_json = result.json()
                if 'data' in response_json:
                    return response_json['data']
            except:
                pass
        return {}
    except Exception as e:
        log.error(f"🔥 获取实盘账户异常: {e}")
        return {}

def get_position_real():
    """获取实盘持仓信息"""
    try:
        result = requests.get(your_server_addr + "position", auth=SignAuth(), timeout=10)
        
        if result.status_code == 200:
            try:
                response_json = result.json()
                if 'data' in response_json:
                    return response_json['data']
            except:
                pass
        return []
    except Exception as e:
        log.error(f"🔥 获取实盘持仓异常: {e}")
        return []

def cancel_stock_real(cancelType=1):
    """撤单函数"""
    try:
        result = requests.post(your_server_addr + "cancel", json={
            "cancelType": cancelType
        }, auth=SignAuth(), timeout=10)
        return result.status_code == 200
    except Exception as e:
        log.error(f"撤单异常: {e}")
        return False

#################################按比例同步交易系统（完美融合增强版）#######################################
class ProportionalSyncSystem:
    """按比例同步交易系统 - 完美融合增强版"""
    
    def __init__(self, context):
        # 初始化所有必要的属性
        self._initialize_attributes()
        
        # 系统状态
        self.is_shipan = A.isShipan
        self.proportional_sync = True
        
        # 关键修复1：使用保守版的比例因子范围0.1-5.0
        self.scale_factor = 1.0
        
        # 初始化更新
        self.update_real_account_info()
        
        log.info(f"🔄 按比例同步系统初始化（完美融合增强版）")
        log.info(f"  实盘模式: {'开启' if self.is_shipan==1 else '关闭'}")
        log.info(f"  比例同步: {'开启' if self.proportional_sync else '关闭'}")
        log.info(f"  比例因子范围: 0.1-5.0（保守版范围）")
        log.info(f"  属性检查机制: 已启用")
    
    def _initialize_attributes(self):
        """初始化所有必要属性 - 增强版"""
        # 账户信息
        self.real_total_value = 0
        self.real_available = 0
        self.real_positions = {}  # {股票代码: 数量}
        
        # 记录买入信息（精确计算卖出数量）
        self.buy_sim_quantities = {}  # {股票代码: 模拟盘买入数量}
        self.buy_scale_factors = {}   # {股票代码: 买入时的比例因子}
        self.buy_prices = {}          # {股票代码: 买入价格}
        self.buy_dates = {}           # {股票代码: 买入日期}
        
        # 持仓同步记录
        self.position_verification_count = 0
        self.position_errors = []
        
        # 状态恢复记录
        self.attribute_initializations = 0
        self.last_initialization_time = time.time()
        
        log.info("📋 交易系统属性初始化完成")
    
    def _ensure_attributes_exist(self):
        """确保所有必要属性都存在 - 防止属性丢失"""
        try:
            # 检查关键属性是否存在
            required_attrs = [
                'real_positions', 'buy_sim_quantities', 
                'buy_scale_factors', 'buy_prices', 'buy_dates'
            ]
            
            missing_attrs = []
            for attr in required_attrs:
                if not hasattr(self, attr):
                    missing_attrs.append(attr)
            
            if missing_attrs:
                log.warning(f"⚠️ 检测到缺失的属性: {missing_attrs}")
                log.warning("🔄 重新初始化所有属性...")
                self._initialize_attributes()
                self.attribute_initializations += 1
                log.info(f"✅ 属性重新初始化完成 (第{self.attribute_initializations}次)")
                return True
            
            return False
            
        except Exception as e:
            log.error(f"🔥 属性检查异常: {e}")
            # 强制重新初始化
            self._initialize_attributes()
            return True
    
    def update_real_account_info(self):
        """更新实盘账户信息"""
        if self.is_shipan == 0:
            return
        
        try:
            # 确保属性存在
            self._ensure_attributes_exist()
            
            # 1. 获取账户资金
            account_data = get_account_real()
            
            if account_data:
                # 智能解析账户数据
                total_fields = ['total', '总资产', 'balance', '总资金', '资产总值']
                available_fields = ['available', '可用', '可用资金', '可用余额', '可取余额']
                
                for field in total_fields:
                    if field in account_data:
                        try:
                            raw_value = account_data[field]
                            self.real_total_value = float(str(raw_value).replace(',', ''))
                            break
                        except:
                            continue
                
                for field in available_fields:
                    if field in account_data:
                        try:
                            raw_value = account_data[field]
                            self.real_available = float(str(raw_value).replace(',', ''))
                            break
                        except:
                            continue
                
                log.info(f"💰 实盘账户: 总资金={self.real_total_value:,.2f}元, 可用={self.real_available:,.2f}元")
            
            # 2. 获取持仓信息
            positions_data = get_position_real()
            
            # 确保real_positions存在
            if not hasattr(self, 'real_positions'):
                self.real_positions = {}
            
            # 临时存储新持仓
            new_positions = {}
            
            if positions_data and isinstance(positions_data, list):
                for pos in positions_data:
                    try:
                        # 提取股票代码
                        raw_code = pos.get('证券代码', '') or pos.get('股票代码', '') or pos.get('code', '') or ''
                        stock_code = format_stock_code(raw_code)
                        
                        if not stock_code:
                            continue
                        
                        # 提取持仓数量
                        qty_fields = ['可用余额', '持仓数量', 'volume', 'qty', 'current_amount', 'amount']
                        qty = 0
                        for field in qty_fields:
                            if field in pos:
                                try:
                                    qty_str = str(pos[field])
                                    qty = int(float(qty_str.replace(',', '')))
                                    if qty > 0:
                                        break
                                except:
                                    continue
                        
                        if qty > 0:
                            new_positions[stock_code] = qty
                    except Exception as e:
                        log.warning(f"持仓解析异常: {e}")
                        continue
                
                # 更新持仓
                self.real_positions = new_positions
                
                if self.real_positions:
                    log.info(f"📊 实盘持仓: {len(self.real_positions)}只股票")
                    # 添加持仓明细打印 - 新增功能
                    for code, qty in self.real_positions.items():
                        log.info(f"  {code}: {qty}股")
                else:
                    log.info("📊 实盘持仓: 0只股票")
            
        except Exception as e:
            log.error(f"🔥 更新实盘账户信息失败: {e}")
            # 发生异常时确保基本属性存在
            self._ensure_attributes_exist()
    
    def calculate_scale_factor(self, context):
        """计算比例因子 - 使用保守版范围：0.1-5.0"""
        if not self.proportional_sync or self.is_shipan == 0:
            self.scale_factor = 1.0
            return 1.0
        
        # 模拟盘总资产
        sim_total = context.portfolio.total_value
        
        # 实盘总资产
        real_total = self.real_total_value
        
        if sim_total <= 0 or real_total <= 0:
            log.warning("资产数据无效，使用比例因子1.0")
            self.scale_factor = 1.0
            return 1.0
        
        # 核心比例计算公式
        scale_factor = real_total / sim_total
        
        # 关键修复：使用保守版的安全限制 (0.1-5.0倍)
        scale_factor = max(0.1, min(scale_factor, 5.0))
        
        self.scale_factor = scale_factor
        
        log.info(f"📈 比例因子: 实盘{real_total:,.2f}元 ÷ 模拟盘{sim_total:,.2f}元 = {scale_factor:.4f}")
        
        return scale_factor
    
    def scale_quantity(self, sim_qty):
        """缩放交易数量"""
        if sim_qty <= 0:
            return 0
        
        # 计算缩放后的数量
        scaled_qty = int(round(sim_qty * self.scale_factor / 100) * 100)
        
        # 确保至少100股
        if scaled_qty > 0 and scaled_qty < 100:
            scaled_qty = 100
        
        log.info(f"缩放数量: {sim_qty} × {self.scale_factor:.4f} = {scaled_qty}")
        
        return max(0, scaled_qty)
    
    def verify_position_before_sell(self, stock_code):
        """卖出前验证持仓"""
        # 确保属性存在
        self._ensure_attributes_exist()
        
        # 强制更新持仓信息
        self.update_real_account_info()
        
        stock_code_6 = format_stock_code(stock_code)
        if not stock_code_6:
            return 0
        
        # 获取实盘实际持仓
        if not hasattr(self, 'real_positions'):
            self.real_positions = {}
        
        actual_qty = self.real_positions.get(stock_code_6, 0)
        
        if actual_qty == 0:
            log.warning(f"⚠️ 实盘持仓验证: {stock_code_6} 持仓为0")
        
        return actual_qty
    
    def execute_proportional_trade(self, context, opera, stock, price, sim_qty, reason=""):
        """执行按比例同步交易 - 完美融合增强版"""
        try:
            # 确保所有属性都存在
            self._ensure_attributes_exist()
            
            # 更新账户信息
            self.update_real_account_info()
            
            # 计算比例因子（使用保守版范围）
            self.calculate_scale_factor(context)
            
            # 股票代码格式化
            stock_code_6 = format_stock_code(stock[:6]) or stock[:6]
            
            log.info(f"📡 按比例交易信号 [{reason}]")
            log.info(f"  操作: {opera} | 股票: {stock_code_6}")
            log.info(f"  价格: {price:.2f} | 模拟数量: {sim_qty}")
            log.info(f"  当前比例因子: {self.scale_factor:.4f}")
            
            if self.is_shipan == 1:
                if opera == 'buy':
                    # 买入逻辑
                    real_qty = self.scale_quantity(sim_qty)
                    
                    # 资金检查
                    required_cash = real_qty * price * 1.01
                    if required_cash > self.real_available:
                        log.warning(f"⚠️ 实盘资金不足: 需要{required_cash:,.2f}元，可用{self.real_available:,.2f}元")
                        # 调整数量
                        adjusted_qty = int(self.real_available / (price * 1.01) // 100) * 100
                        adjusted_qty = max(100, adjusted_qty)
                        if adjusted_qty >= 100:
                            real_qty = adjusted_qty
                            log.info(f"调整买入数量为: {real_qty}股")
                        else:
                            log.error("资金完全不足，跳过买入")
                            return False, 0
                    
                    log.info(f"  价格: {price:.2f} | 模拟数量: {sim_qty} → 实盘数量: {real_qty}")
                    
                    # 执行实盘买入
                    buy_price = round(price * 1.005, 2)
                    success = buy_stock_real(stock_code_6, buy_price, real_qty, reason)
                    
                    if success:
                        # 确保记录字典存在
                        if not hasattr(self, 'buy_sim_quantities'):
                            self.buy_sim_quantities = {}
                        if not hasattr(self, 'buy_scale_factors'):
                            self.buy_scale_factors = {}
                        if not hasattr(self, 'buy_prices'):
                            self.buy_prices = {}
                        if not hasattr(self, 'buy_dates'):
                            self.buy_dates = {}
                        
                        # 记录买入信息（用于精确计算卖出）
                        self.buy_sim_quantities[stock_code_6] = sim_qty
                        self.buy_scale_factors[stock_code_6] = self.scale_factor
                        self.buy_prices[stock_code_6] = price
                        self.buy_dates[stock_code_6] = context.current_dt.date()
                        
                        # 更新本地持仓记录
                        current_qty = self.real_positions.get(stock_code_6, 0)
                        self.real_positions[stock_code_6] = current_qty + real_qty
                        
                        log.info(f"✅ 按比例买入成功: {stock_code_6}")
                        log.info(f"  买入记录已保存: 模拟{sim_qty}股, 比例因子{self.scale_factor:.4f}")
                        
                        # 稍后更新账户信息
                        time.sleep(0.5)
                        self.update_real_account_info()
                    
                    return success, real_qty
                    
                elif opera == 'sell':
                    # 卖出逻辑 - 使用精确卖出计算
                    # 1. 首先验证实盘持仓
                    actual_qty = self.verify_position_before_sell(stock_code_6)
                    
                    # 特殊情况：实盘持仓为0但模拟盘仍有持仓（可能用户手动卖出了）
                    if actual_qty <= 0:
                        log.warning(f"⚠️ 实盘持仓为0但模拟盘仍有持仓，可能用户手动卖出了")
                        log.warning(f"⚠️ 跳过实盘卖出，仅处理模拟盘卖出")
                        
                        # 返回成功但不执行实盘操作
                        return True, 0
                    
                    # 2. 计算应卖出数量
                    real_qty = 0
                    
                    # 检查是否有买入记录
                    has_buy_record = False
                    if hasattr(self, 'buy_sim_quantities') and stock_code_6 in self.buy_sim_quantities:
                        has_buy_record = True
                    
                    if has_buy_record and stock_code_6 in self.buy_scale_factors:
                        # 方法1: 使用买入时记录的信息精确计算
                        original_sim_qty = self.buy_sim_quantities[stock_code_6]
                        original_scale = self.buy_scale_factors[stock_code_6]
                        
                        # 按模拟盘卖出比例计算实盘应卖出数量
                        if sim_qty <= original_sim_qty:
                            # 按买入时的比例因子精确计算
                            real_qty = int(round(sim_qty * original_scale / 100) * 100)
                            log.info(f"📊 精确计算卖出: 模拟{sim_qty}×{original_scale:.4f}=计划{real_qty}股")
                        else:
                            # 全卖
                            real_qty = int(round(original_sim_qty * original_scale / 100) * 100)
                            log.info(f"📊 全仓卖出: 模拟{original_sim_qty}×{original_scale:.4f}=计划{real_qty}股")
                    else:
                        # 方法2: 没有买入记录，按当前比例因子计算
                        real_qty = self.scale_quantity(sim_qty)
                        log.info(f"📊 当前比例卖出: 模拟{sim_qty}×{self.scale_factor:.4f}=计划{real_qty}股")
                    
                    # 3. 确保不超过实际持仓
                    if real_qty > actual_qty:
                        log.warning(f"⚠️ 卖出数量调整: 计划{real_qty}股 → 实际持仓{actual_qty}股")
                        real_qty = actual_qty
                    
                    # 4. 处理零股
                    if real_qty < 100:
                        if actual_qty >= 100:
                            # 有持仓但计算出的数量不足100，按100股处理
                            real_qty = min(100, actual_qty)
                            log.info(f"📊 零股处理: 调整为{real_qty}股")
                        else:
                            # 持仓少于100股，全部卖出
                            real_qty = actual_qty
                            log.info(f"📊 零股卖出: 全部{real_qty}股")
                    
                    if real_qty <= 0:
                        log.error("卖出数量为0，跳过")
                        return False, 0
                    
                    log.info(f"  价格: {price:.2f} | 模拟数量: {sim_qty} → 实盘数量: {real_qty}")
                    log.info(f"  实际持仓: {actual_qty}股 | 最终卖出: {real_qty}股")
                    
                    # 5. 执行卖出
                    sell_price = round(price * 0.995, 2)
                    success = sell_stock_real(stock_code_6, sell_price, real_qty, reason)
                    
                    if success:
                        # 更新本地持仓记录
                        new_qty = actual_qty - real_qty
                        if new_qty > 0:
                            self.real_positions[stock_code_6] = new_qty
                        else:
                            # 完全卖出，清除记录
                            if stock_code_6 in self.real_positions:
                                del self.real_positions[stock_code_6]
                            if hasattr(self, 'buy_scale_factors') and stock_code_6 in self.buy_scale_factors:
                                del self.buy_scale_factors[stock_code_6]
                            if hasattr(self, 'buy_sim_quantities') and stock_code_6 in self.buy_sim_quantities:
                                del self.buy_sim_quantities[stock_code_6]
                            if hasattr(self, 'buy_prices') and stock_code_6 in self.buy_prices:
                                del self.buy_prices[stock_code_6]
                            if hasattr(self, 'buy_dates') and stock_code_6 in self.buy_dates:
                                del self.buy_dates[stock_code_6]
                        
                        log.info(f"✅ 按比例卖出成功: {stock_code_6} | 卖出{real_qty}股")
                        
                        # 稍后更新账户信息
                        time.sleep(0.5)
                        self.update_real_account_info()
                    
                    return success, real_qty
            else:
                # 回测模式
                log.info(f"📝 回测{opera}记录: {stock_code_6} {sim_qty}股")
                return True, sim_qty
                
        except Exception as e:
            log.error(f"🔥 按比例交易执行异常: {e}")
            log.error(traceback.format_exc())
            
            # 异常情况下强制重新初始化属性
            log.warning("🔄 发生异常，尝试重新初始化属性...")
            self._initialize_attributes()
            
            return False, 0
    
    def get_system_status(self, context):
        """获取系统状态"""
        self.update_real_account_info()
        self.calculate_scale_factor(context)
        
        # 确保属性存在
        self._ensure_attributes_exist()
        
        status = {
            '实盘模式': '开启' if self.is_shipan == 1 else '关闭',
            '比例同步': '开启' if self.proportional_sync else '关闭',
            '当前比例因子': f"{self.scale_factor:.4f}",
            '比例因子范围': '0.1-5.0（保守版）',
            '模拟总资产': f"{context.portfolio.total_value:,.2f}",
            '实盘总资产': f"{self.real_total_value:,.2f}",
            '实盘可用资金': f"{self.real_available:,.2f}",
            '实盘持仓数量': len(self.real_positions) if hasattr(self, 'real_positions') else 0,
            '买入记录数量': len(self.buy_sim_quantities) if hasattr(self, 'buy_sim_quantities') else 0,
            '属性初始化次数': self.attribute_initializations,
            '卖出盈利阈值': '1%（保守版）',
            '跌停打开条件': 'current_price > low_limit（保守版）',
            '状态恢复机制': '已启用'
        }
        
        return status

#################################策略核心逻辑（完美融合增强版）#######################################
g.strategy = '昨日炸板-按比例同步实盘版（完美融合增强版）'

# ==========================全局参数设置============================
# 完全使用保守版的参数
g.stock_num = 4                # 每日最大买入股票数
g.down = 0.4                   # 下引线比例
g.avoid_jan_apr_dec = True     # 是否开启1、4、12月空仓规则
g.ma_period = 10               # 均线周期
g.volume_ratio_threshold = 10  # 成交量倍数上限
g.stop_loss_ma_period = 7      # 止损均线周期（MA7）
g.min_operating_revenue = 1e8  # 最小营业收入
g.min_net_profit = 0           # 最小净利润
g.open_down_threshold = 0.970  # 开盘价下限
g.open_up_threshold = 1.1      # 开盘价上限
g.cash_reserve_ratio = 0.8     # 现金保留比例（10%）

def initialize(context):
    """初始化函数 - 完美融合增强版"""
    set_option('use_real_price', True)
    set_option('avoid_future_data', True)
    set_slippage(FixedSlippage(0.0001), type='stock')
    
    # 设置交易成本
    set_order_cost(OrderCost(
        open_tax=0, 
        close_tax=0.0005, 
        open_commission=0.0001, 
        close_commission=0.0001,
        close_today_commission=0, 
        min_commission=5
    ), type='stock')
    
    # 初始化按比例同步系统（完美融合增强版）
    try:
        g.sync_system = ProportionalSyncSystem(context)
    except Exception as e:
        log.error(f"🔥 初始化同步系统失败: {e}")
        # 创建空的同步系统
        g.sync_system = None
    
    # 策略全局变量（与保守版一致）
    g.today_list = []           # 当日观测股票
    g.buy_dates = {}            # 记录股票买入日期
    g.dieting_stocks = []       # 跌停股票列表
    g.already_bought_today = [] # 今日已买入的股票
    g.hold_list = []            # 持仓列表
    g.yesterday_HL_list = []    # 昨日涨停列表
    
    # 设置运行时间 - 完美融合增强版
    log.info("🕒 策略调度设置（完美融合增强版）:")
    log.info("  - prepare_stock_list: 09:05")
    log.info("  - perpare: 09:25:00")
    log.info("  - buy: 09:25:18")
    log.info("  - sell: 14:00 和 14:55（仅在实盘时严格时间控制）")
    log.info("  - check_dieting: every_bar（每分钟监控跌停板）")
    log.info("  - observe_13_00: 12:58, 12:59, 13:00, 13:01, 13:02（13:00问题纯观察）")
    log.info("  - print_date_separator: 15:05")
    log.info("  - reset_daily_status: 15:10")
    log.info("  - report_sync_status: 15:15")
    
    run_daily(prepare_stock_list, '9:05')
    run_daily(perpare, time="09:26:00")
    run_daily(buy, time="09:31:30")
    run_daily(sell, time='14:00')
    run_daily(sell, time='14:55')
    
    # 关键修复：完全按照保守版的跌停监控频率
    run_daily(check_dieting, time="every_bar")
    
    # 13:00问题纯观察调度（只观察，不分析）
    run_daily(observe_13_00, time="12:58")
    run_daily(observe_13_00, time="12:59")
    run_daily(observe_13_00, time="13:00")
    run_daily(observe_13_00, time="13:01")
    run_daily(observe_13_00, time="13:02")
    
    run_daily(print_date_separator, time="15:05")
    run_daily(reset_daily_status, time="15:10")
    run_daily(report_sync_status, time="15:15")
    
    # 过滤系统订单日志
    log.set_level('order', 'error')
    log.set_level('system', 'error')
    
    # 模式识别
    if A.isShipan == 1:
        log.info("🚀 实盘交易模式已启动（完美融合增强版）")
        log.info("📊 增强特性:")
        log.info("  1. 保守版的选股和买���条件（盈利1%才卖）")
        log.info("  2. 保守版的跌停打开判断（current_price > low_limit）")
        log.info("  3. 保守版的比例因子范围（0.1-5.0）")
        log.info("  4. 属性自动恢复机制")
        log.info("  5. 增强异常处理和日志记录")
        log.info("  6. 实盘持仓为0时的智能处理")
        log.info("  7. 13:00问题纯观察功能（只记录事实，不分析条件）")
        log.info("  8. 实盘/模拟盘持仓对比功能（便于诊断问题）")
    else:
        log.info("💻 模拟交易模式已启动（可测试实盘信号）")

def report_sync_status(context):
    """报告同步状态"""
    if hasattr(g, 'sync_system') and g.sync_system is not None:
        try:
            status = g.sync_system.get_system_status(context)
            log.info("=" * 70)
            log.info("📊 按比例同步系统状态报告（完美融合增强版）")
            for key, value in status.items():
                log.info(f"  {key}: {value}")
            log.info("=" * 70)
        except Exception as e:
            log.error(f"🔥 报告同步状态失败: {e}")

def reset_daily_status(context):
    """重置每日状态"""
    g.already_bought_today = []
    log.info("每日状态已重置")

def prepare_stock_list(context):
    """准备股票列表（与保守版一致）"""
    # 更新按比例同步系统账户信息
    if hasattr(g, 'sync_system') and g.sync_system is not None:
        try:
            g.sync_system.update_real_account_info()
        except Exception as e:
            log.error(f"🔥 更新同步系统账户信息失败: {e}")
    
    # 更新持仓列表
    g.hold_list = []
    for position in list(context.portfolio.positions.values()):
        stock = position.security
        g.hold_list.append(stock)
    
    # 获取昨日涨停列表
    if g.hold_list:
        try:
            df = get_price(g.hold_list, end_date=context.previous_date, 
                          frequency='daily', fields=['close', 'high_limit'], 
                          count=1, panel=False, fill_paused=False)
            df = df[df['close'] == df['high_limit']]
            g.yesterday_HL_list = list(df.code)
        except:
            g.yesterday_HL_list = []
    else:
        g.yesterday_HL_list = []
    
    log.info(f"持仓股票: {len(g.hold_list)}只, 昨日涨停: {len(g.yesterday_HL_list)}只")

def calculate_investment_amount(context, target_count):
    """计算每只股票的投资金额（与保守版一致）"""
    total_cash = context.portfolio.available_cash
    
    # 保留部分现金
    investable_cash = total_cash * (1 - g.cash_reserve_ratio)
    
    # 计算每只股票的投资金额
    if target_count > 0:
        investment_per_stock = investable_cash / target_count
    else:
        investment_per_stock = 0
    
    log.info(f"💰 资金分配: 总资金{total_cash:,.0f}元 → 可投资{investable_cash:,.0f}元 → 每只股票{investment_per_stock:,.0f}元")
    
    return investment_per_stock

def is_avoid_period(context):
    """判断是否在空仓期（与保守版一致）"""
    today_str = context.current_dt.strftime('%m-%d')
    avoid_periods = [
        ('01-15', '01-31'),
        ('04-15', '04-30'),
        ('08-15', '08-31')
    ]
    
    for start, end in avoid_periods:
        if start <= today_str <= end:
            return True
    return False

def perpare(context):
    """筛选股票（与保守版完全一致）"""
    if g.avoid_jan_apr_dec and is_avoid_period(context):
        log.info("📅 当前处于空仓期，今日不交易")
        g.today_list = []
        return
        
    g.dieting = []
    current_data = get_current_data()
    g.yesterday_high_dict = {}
    g.today_list = []
    
    # 获取股票池
    stk_list = get_st(context)
    
    # 弱转强筛选
    stk_list = rzq_list(context, stk_list)
    if len(stk_list) == 0:
        log.info("弱转强筛选后无股票")
        return
    
    # 国九条筛选
    stk_list = GJT_filter_stocks(stk_list)
    if len(stk_list) == 0:
        log.info("国九条筛选后无股票")
        return
    
    # 技术指标筛选
    stk_list = filter_stocks(context, stk_list)
    if len(stk_list) == 0:
        log.info("技术指标筛选后无股票")
        return
    
    # 获取前一日收盘价
    df = get_price(
        stk_list,
        end_date=context.previous_date,
        frequency='daily',
        fields=['close'],
        count=1,
        panel=False,
        fill_paused=False,
        skip_paused=True
    ).set_index('code')
    
    # 添加当前开盘价
    open_now_values = []
    for s in stk_list:
        try:
            open_now_values.append(current_data[s].day_open)
        except:
            open_now_values.append(None)
    
    df['open_now'] = open_now_values
    df = df.dropna(subset=['open_now'])
    
    # 筛选开盘价在设定范围内的股票
    df = df[(df['open_now'] / df['close']) < g.open_up_threshold]
    df = df[(df['open_now'] / df['close']) > g.open_down_threshold]
    
    stk_list = list(df.index)
    
    # 排除已持仓的股票
    hold_list = list(context.portfolio.positions)
    stk_list = list(set(stk_list) - set(hold_list))
    
    if len(stk_list) == 0:
        log.info("排除持仓股后无候选股票")
        return
    
    # 获取估值数据
    df_val = get_valuation(
        stk_list,
        start_date=context.previous_date,
        end_date=context.previous_date,
        fields=['turnover_ratio', 'market_cap']
    )
    
    # 合并数据
    df.index = df.index.astype(str)
    df_val['code'] = df_val['code'].astype(str)
    df_combined = pd.merge(df.reset_index(), df_val, on='code')
    
    # 计算因子：换手率 * 开盘/收盘比值
    df_combined['factor'] = df_combined['turnover_ratio'] * (df_combined['open_now'] / df_combined['close'])
    df_sorted = df_combined.sort_values(by='factor', ascending=False)
    
    # 更新今日选股列表
    g.today_list = list(df_sorted['code'])
    
    # 市场分布统计
    sh_count = len([s for s in g.today_list if s.startswith('60') or s.startswith('68')])
    sz_count = len([s for s in g.today_list if s.startswith('00')])
    log.info(f"候选股市场分布: 沪市{sh_count}只, 深市{sz_count}只")

def buy(context):
    """买入函数 - 完全复制保守版的顺序"""
    try:
        if g.avoid_jan_apr_dec and is_avoid_period(context):
            return
            
        target = filter_stocks_by_b_s(context, g.today_list)
        
        if len(target) == 0:
            log.info("无符合买入条件的候选股票")
            return
        
        hold_list = list(context.portfolio.positions)
        num = g.stock_num - len(hold_list)
        
        if num <= 0:
            log.info("已达到最大持仓数量，不再买入")
            return
            
        target = [x for x in target if x not in hold_list][:num]
        
        if len(target) > 0:
            # 智能资金分配 - 与保守版完全一致
            investment_per_stock = calculate_investment_amount(context, len(target))
            
            current_data = get_current_data()
            valid_targets = []
            
            # 检查资金是否足够买入
            for stock in target:
                price = current_data[stock].last_price
                min_shares = 100
                min_investment = price * min_shares
                
                if investment_per_stock >= min_investment:
                    valid_targets.append(stock)
                else:
                    log.warning(f"资金不足跳过 {stock}: 需要{min_investment:.0f}元，仅有{investment_per_stock:,.0f}元")
            
            if len(valid_targets) == 0:
                log.info("所有候选股票都因资金不足被跳过")
                return
                
            # 重新计算有效股票的投资金额
            actual_investment = calculate_investment_amount(context, len(valid_targets))
            
            log.info(f"🎯 实际执行: {len(valid_targets)}只股票，每只{actual_investment:,.0f}元")
            
            for stock in valid_targets:
                # 排除停牌和涨跌停无法交易的股票
                if current_data[stock].paused or \
                current_data[stock].last_price == current_data[stock].low_limit or \
                current_data[stock].last_price == current_data[stock].high_limit:
                    continue
                    
                # 获取股票名称
                try:
                    stock_name = get_security_info(stock).display_name
                except:
                    stock_name = stock
                
                # 计算买入数量 - 与保守版完全一致
                price = current_data[stock].last_price
                sim_count = int(actual_investment / price) // 100 * 100
                sim_count = max(sim_count, 100)
                
                if sim_count >= 100:
                    # 关键修复：保持保守版顺序 - 先实盘后模拟
                    # 执行按比例同步交易
                    if hasattr(g, 'sync_system') and g.sync_system is not None:
                        success, real_count = g.sync_system.execute_proportional_trade(
                            context, 'buy', stock, price, sim_count, "开盘买入"
                        )
                        if success:
                            log.info(f"✅ 按比例买入: {stock_name}({stock}) | 模拟盘{sim_count}股 → 实盘{real_count}股")
                    
                    # 执行模拟盘交易 - 在实盘信号发送后执行
                    order_value = sim_count * price
                    order = order_target_value(stock, order_value)
                    
                    if order and hasattr(order, 'filled') and order.filled > 0:
                        log.info(f"模拟盘买入 {stock_name}({stock}) | 分配资金: {actual_investment:,.0f}元")
                        g.buy_dates[stock] = context.current_dt.date()
                        g.already_bought_today.append(stock)
                else:
                    log.warning(f"买入数量不足100股: {stock}")
                    
    except Exception as e:
        log.error(f"🔥 买入函数异常: {e}")
        log.error(traceback.format_exc())

def sell(context):
    """卖出函数 - 关键修复：完全复制保守版的卖出条件 + 仅在实盘时时间控制"""
    try:
        # 记录sell函数被调用的时间（仅用于诊断）
        current_time_str = context.current_dt.strftime("%H:%M:%S")
        current_time = context.current_dt.time()
        
        # 判断是否是13:00前后
        time_diff = abs((current_time.hour * 3600 + current_time.minute * 60 + current_time.second) -
                       (13 * 3600))
        
        is_13_00_period = time_diff <= 120  # 13:00前后2分钟
        
        if is_13_00_period:
            log.info(f"⏰ sell()函数被调用于: {current_time_str}")
        
        # 关键修复2：仅在实盘模式下进行时间验证
        if A.isShipan == 1:
            allowed_times = [dt.time(), dt.time(14, 0, 0), dt.time(14, 55, 0)]
            time_valid = False
            for allowed_time in allowed_times:
                time_diff = abs((current_time.hour * 3600 + current_time.minute * 60 + current_time.second) -
                               (allowed_time.hour * 3600 + allowed_time.minute * 60 + allowed_time.second))
                if time_diff <= 200:  # 允许200秒偏差
                    time_valid = True
                    break
            
            if not time_valid:
                log.warning(f"❌ 实盘时间验证失败: {current_time_str}")
                if is_13_00_period:
                    log.info(f"  原因: 当前时间{current_time_str}不在允许的卖出时间{allowed_times}±200秒内")
                return
        
        # 执行卖出逻辑（完全复制保守版）
        hold_pos = context.portfolio.positions
        current_data = get_current_data()
        yesterday = context.previous_date
        
        # T+1规则：过滤当日买入的股票
        sellable_stocks = [s for s in hold_pos if hold_pos[s].closeable_amount > 0]
        if not sellable_stocks:
            return
        
        # 批量获取持仓数据
        ma_data = history(g.stop_loss_ma_period, 
                          unit='1d', 
                          field='close', 
                          security_list=sellable_stocks).mean()
        
        df_history = get_price(
            sellable_stocks,
            end_date=yesterday,
            frequency='daily',
            fields=['close', 'high_limit'],
            count=1,
            panel=False
        )
        
        # 关键修复3：完全按照保守版的字段赋值
        df_history['avg_cost'] = [context.portfolio.positions[s].avg_cost for s in sellable_stocks]
        df_history['price'] = [context.portfolio.positions[s].price for s in sellable_stocks]  # 关键：使用持仓价格
        df_history['today_high_limit'] = [current_data[s].high_limit for s in sellable_stocks]
        df_history['today_low_limit'] = [current_data[s].low_limit for s in sellable_stocks]
        df_history['last_price'] = [current_data[s].last_price for s in sellable_stocks]
        df_history['ma'] = [ma_data.get(s, 0) for s in sellable_stocks]
        df_history['closeable_amount'] = [context.portfolio.positions[s].closeable_amount for s in sellable_stocks]
        
        # 卖出条件 - 完全复制保守版
        cond1 = (df_history['last_price'] != df_history['today_high_limit'])
        
        # 关键修复4：盈利超过1%才卖（保守版的核心条件）
        cond2_1 = df_history['last_price'] < df_history['ma']
        cond2_2 = (df_history['price'] / df_history['avg_cost'] - 1) * 100 > 1  # 关键修复：使用price字段
        cond2_3 = (df_history['close'] == df_history['high_limit'])
        
        sell_condition = cond1 & (cond2_1 | cond2_2 | cond2_3)
        
        # 生成卖出列表
        sell_list = df_history[
            sell_condition & 
            (df_history['last_price'] > df_history['today_low_limit']) &
            (df_history['closeable_amount'] > 0)
        ].code.tolist()
        
        # 批量下单
        for s in sell_list:
            position = context.portfolio.positions[s]
            if position.closeable_amount <= 0:
                continue
                
            if current_data[s].last_price <= current_data[s].low_limit:
                log.warning(f"股票{s}处于跌停板，无法卖出")
                continue
            
            avg_cost = position.avg_cost
            current_price = position.price  # 关键：使用持仓价格
            profit_rate = (current_price / avg_cost - 1) * 100 if avg_cost > 0 else 0
            
            try:
                stock_name = get_security_info(s).display_name
            except:
                stock_name = s
            
            log.info(f"📊 计划卖出: {stock_name}({s}) | 盈亏: {profit_rate:+.1f}%")
            
            # 执行按比例同步卖出
            if hasattr(g, 'sync_system') and g.sync_system is not None:
                success, real_count = g.sync_system.execute_proportional_trade(
                    context, 'sell', s, current_price, position.closeable_amount, f"止盈止损({profit_rate:+.1f}%)"
                )
                if success:
                    log.info(f"✅ 按比例卖出: {stock_name}({s}) | 盈亏: {profit_rate:+.2f}% | 实盘{real_count}股")
            
            # 执行模拟盘卖出
            order_target_value(s, 0)
            log.info(f'模拟盘卖出 {stock_name}({s}) | 成本价:{avg_cost:.2f} 现价:{current_price:.2f} 盈亏:{profit_rate:+.2f}%')
            
    except Exception as e:
        log.error(f"🔥 卖出函数异常: {e}")
        log.error(traceback.format_exc())

def filter_stocks_by_b_s(context, stock_list, max_retry=3, retry_delay=0.5):
    """返回b_s>0的股票 - 增强容错版（与保守版一致）"""
    date = context.current_dt.strftime("%Y-%m-%d")
    valid_stocks = []

    # 重试逻辑
    for i in range(max_retry):
        df = get_call_auction(stock_list, start_date=date, end_date=date)
        
        if df is not None and not df.empty:
            df['sellmoney'] = df['a1_p']*df['a1_v'] + df['a2_p']*df['a2_v'] + df['a3_p']*df['a3_v'] + df['a4_p']*df['a4_v'] + df['a5_p']*df['a5_v']
            df['buymoney'] = df['b1_p']*df['b1_v'] + df['b2_p']*df['b2_v'] + df['b3_p']*df['b3_v'] + df['b4_p']*df['b4_v'] + df['b5_p']*df['b5_v']
            
            stocks = df[df['buymoney'] > df['sellmoney']].code.tolist()
            valid_stocks = [stock for stock in stock_list if stock in stocks]
            
            if valid_stocks:
                log.info(f"✅ 集合竞价筛选成功 (第{i+1}次尝试)，找到 {len(valid_stocks)} 只股票")
                return valid_stocks
            else:
                log.info("集合竞价数据已获取，但无b_s>0的股票")
                return valid_stocks  # 返回空列表
        
        elif i < max_retry - 1:
            time.sleep(retry_delay)
            log.warning(f"集合竞价数据获取失败，第{i+1}次重试...")
        else:
            log.error(f"集合竞价数据获取失败，已达到最大重试次数{max_retry}")
            log.warning("⚠️ 策略容错：数据获取失败，今日不买入任何股票")
            return []  # 关键修改：数据获取失败时返回空列表，不交易
    
    return valid_stocks

def get_st(context):
    """获取成分股并过滤ST股（与保守版一致）"""
    all_stocks = get_all_securities(['stock'], date=context.previous_date).index.tolist()
    all_stocks = [s for s in all_stocks if not s.startswith('30')]
    
    # 过滤ST股
    st_data = get_extras('is_st', all_stocks, count=1, end_date=context.previous_date)
    st_data = st_data.T
    st_data.columns = ['is_st']
    filtered_stocks = st_data[st_data['is_st'] == False].index.tolist()
    
    # 额外过滤名称中包含ST的股票
    final_stocks = []
    for stock in filtered_stocks:
        try:
            name = get_security_info(stock).display_name
            if 'ST' not in name:
                final_stocks.append(stock)
        except:
            final_stocks.append(stock)
    
    return final_stocks

def rzq_list(context, initial_list):
    """筛选昨日炸板的股票（与保守版一致）"""
    yesterday = context.previous_date
    
    df = get_price(
        initial_list,
        end_date=yesterday,
        frequency='daily',
        fields=['close', 'high', 'high_limit'],
        count=1,
        panel=False,
        fill_paused=False,
        skip_paused=True
    )
    
    if df.empty:
        log.info("炸板筛选：无符合条件的股票数据")
        return []
    
    cond_bomb = (df['high'] == df['high_limit']) & (df['close'] < df['high_limit'])
    result_df = df[cond_bomb].drop_duplicates(subset=['code'])
    zb_list = result_df['code'].tolist()
    
    log.info(f"炸板筛选结果：{len(zb_list)} 只股票")
    return zb_list

def filter_stocks(context, stocks):
    """技术指标筛选（与保守版一致）"""
    yesterday = context.previous_date
    group = get_price(
        stocks,
        count=g.ma_period,
        frequency='1d',
        fields=['close', 'low', 'volume'],
        end_date=yesterday,
        panel=False
    ).groupby('code')
    
    last_df = group.nth(-1)[['close','volume']]
    prev_df = group.nth(-2)[['low','volume']].add_prefix('prev_')
    mean_df = group['close'].apply(lambda x:x.mean())
    mean_df = mean_df.rename('ma', inplace=True)
    out_df = last_df.join(prev_df)
    out_df = out_df.join(mean_df)
    
    out_df = out_df[
        (out_df.close > out_df.ma) & 
        (out_df.close > out_df.prev_low) &
        (out_df.volume > out_df.prev_volume) &
        (out_df.volume < g.volume_ratio_threshold * out_df.prev_volume) &
        (out_df.close > 1)
    ]
    
    valid_stocks = out_df.index.tolist()
    return valid_stocks

def GJT_filter_stocks(stocks):
    """国九条筛选（与保守版一致）"""
    q = query(valuation.code).filter(
        valuation.code.in_(stocks),
        income.np_parent_company_owners > g.min_net_profit,
        income.net_profit > g.min_net_profit,
        income.operating_revenue > g.min_operating_revenue
    )
    df = get_fundamentals(q)
    final_list = list(df.code)
    return final_list

def check_dieting(context):
    """监控跌停板 - 关键修复5：完全复制保守版的跌停监控逻辑"""
    try:
        # 记录check_dieting函数被调用的时间（仅用于诊断）
        current_time_str = context.current_dt.strftime("%H:%M:%S")
        current_time = context.current_dt.time()
        
        # 判断是否是13:00前后
        time_diff = abs((current_time.hour * 3600 + current_time.minute * 60 + current_time.second) -
                       (13 * 3600))
        
        is_13_00_period = time_diff <= 120  # 13:00前后2分钟
        
        if is_13_00_period:
            log.info(f"⏰ check_dieting()函数被调用于: {current_time_str}")
        
        # 原有的check_dieting函数逻辑保持不变
        if not hasattr(g, 'dieting_stocks'):
            g.dieting_stocks = []
            
        # 完全复制保守版的逻辑：只在有持仓时才检查
        if len(g.dieting_stocks) == 0:
            current_data = get_current_data()
            for stock in list(context.portfolio.positions.keys()):
                position = context.portfolio.positions[stock]
                if (current_data[stock].last_price <= current_data[stock].low_limit and 
                    position.closeable_amount > 0 and 
                    stock not in g.dieting_stocks):
                    g.dieting_stocks.append(stock)
            return
            
        current_data = get_current_data()
        to_remove = []
        
        for stock in g.dieting_stocks:
            if stock not in context.portfolio.positions:
                to_remove.append(stock)
                continue
                
            position = context.portfolio.positions[stock]
            if position.closeable_amount <= 0:
                continue
            
            # 关键修复6：完全复制保守版的条件 - current_price > low_limit
            if current_data[stock].last_price > current_data[stock].low_limit:
                # 记录跌停打开的时间（关键信息）
                log.info(f"📈 {stock} 跌停板打开，触发卖出")
                if is_13_00_period:
                    log.info(f"  ⏰ 发生在: {current_time_str}")
                
                # 跌停打开，立即卖出
                cost_price = position.avg_cost
                current_price = current_data[stock].last_price
                
                # 执行按比例同步卖出
                if hasattr(g, 'sync_system') and g.sync_system is not None:
                    success, real_count = g.sync_system.execute_proportional_trade(
                        context, 'sell', stock, current_price, position.total_amount, "跌停打开止损"
                    )
                    if success:
                        log.info(f"✅ 按比例卖出跌停板: {stock} | 实盘{real_count}股")
                
                # 执行模拟盘卖出
                order_target_value(stock, 0)
                to_remove.append(stock)
        
        for stock in to_remove:
            if stock in g.dieting_stocks:
                g.dieting_stocks.remove(stock)
                
    except Exception as e:
        log.error(f"🔥 跌停监控异常: {e}")
        log.error(traceback.format_exc())

def observe_13_00(context):
    """13:00问题纯观察函数 - 只记录事实，不分析条件，同时显示实盘和模拟盘持仓对比"""
    try:
        current_time = context.current_dt.time()
        current_time_str = context.current_dt.strftime("%H:%M:%S")
        
        # 只在13:00前后2分钟内运行
        time_diff = abs((current_time.hour * 3600 + current_time.minute * 60 + current_time.second) -
                       (13 * 3600))
        
        if time_diff <= 120:  # 13:00前后2分钟
            log.info("=" * 80)
            log.info("🔍 13:00问题纯观察报告（只记录事实，不分析条件）")
            log.info("=" * 80)
            
            # 1. 基本时间信息
            log.info("📅 观察时间:")
            log.info(f"  当前时间: {current_time_str}")
            log.info(f"  距离13:00的差距: {time_diff}秒")
            
            # 2. 函数调度状态
            log.info("📋 原策略调度安排:")
            log.info(f"  - sell()函数调度: 14:00, 14:55")
            log.info(f"  - check_dieting()函数调度: every_bar (每分钟)")
            log.info(f"  - observe_13_00()函数调度: 12:58-13:02 (纯观察)")
            
            # 3. 交易模式状态
            log.info("📱 交易模式:")
            log.info(f"  - 实盘模式(A.isShipan): {A.isShipan}")
            log.info(f"  - 实盘交易: {'已启用' if A.isShipan == 1 else '已禁用'}")
            
            # 4. 模拟盘持仓事实记录
            portfolio = context.portfolio
            holdings = list(portfolio.positions.keys())
            
            log.info("📊 模拟盘持仓事实记录:")
            log.info(f"  - 持仓数量: {len(holdings)}只")
            if holdings:
                for stock in holdings:
                    position = portfolio.positions[stock]
                    try:
                        stock_name = get_security_info(stock).display_name
                    except:
                        stock_name = stock
                    # 获取当前价格
                    try:
                        current_data = get_current_data()
                        current_price = current_data[stock].last_price
                    except:
                        current_price = position.price
                    
                    log.info(f"  - {stock_name}({stock}):")
                    log.info(f"     持仓数量: {position.total_amount}股")
                    log.info(f"     可卖数量: {position.closeable_amount}股")
                    log.info(f"     成本价: {position.avg_cost:.2f}")
                    log.info(f"     当前价格: {current_price:.2f}")
                    log.info(f"     持仓市值: {position.total_amount * current_price:,.2f}元")
            else:
                log.info("  - 无持仓")
            
            # 5. 实盘持仓事实记录（新增对比功能）
            log.info("💰 实盘持仓事实记录:")
            if hasattr(g, 'sync_system') and g.sync_system is not None:
                try:
                    # 更新实盘持仓信息
                    g.sync_system.update_real_account_info()
                    
                    if hasattr(g.sync_system, 'real_positions'):
                        real_holdings = g.sync_system.real_positions
                        log.info(f"  - 实盘持仓数量: {len(real_holdings)}只")
                        
                        if real_holdings:
                            total_real_value = 0
                            for stock_code, qty in real_holdings.items():
                                # 格式化股票代码
                                stock_code_6 = format_stock_code(stock_code)
                                if stock_code_6:
                                    # 获取股票名称
                                    try:
                                        stock_name = get_security_info(stock_code_6).display_name
                                    except:
                                        stock_name = stock_code_6
                                    
                                    # 获取当前价格
                                    try:
                                        current_data = get_current_data()
                                        # 转换为聚宽格式的股票代码
                                        jq_code = stock_code_6 + '.XSHE' if stock_code_6.startswith('00') or stock_code_6.startswith('30') else stock_code_6 + '.XSHG'
                                        if jq_code in current_data:
                                            current_price = current_data[jq_code].last_price
                                        else:
                                            current_price = 0
                                    except:
                                        current_price = 0
                                    
                                    position_value = qty * current_price if current_price > 0 else 0
                                    total_real_value += position_value
                                    
                                    log.info(f"  - {stock_name}({stock_code_6}):")
                                    log.info(f"     实盘持仓: {qty}股")
                                    log.info(f"     当前价格: {current_price:.2f}")
                                    log.info(f"     持仓市值: {position_value:,.2f}元")
                                    
                                    # 与模拟盘对比
                                    if holdings:
                                        # 检查是否有对应的模拟盘持仓
                                        sim_match = None
                                        for sim_stock in holdings:
                                            sim_code_6 = format_stock_code(sim_stock[:6])
                                            if sim_code_6 == stock_code_6:
                                                sim_match = portfolio.positions[sim_stock]
                                                break
                                        
                                        if sim_match:
                                            sim_qty = sim_match.total_amount
                                            ratio = qty / sim_qty if sim_qty > 0 else 0
                                            log.info(f"     模拟盘对应持仓: {sim_qty}股")
                                            log.info(f"     实盘/模拟盘比例: {ratio:.2%}")
                                        else:
                                            log.warning(f"     注意: 模拟盘无对应持仓")
                        else:
                            log.info("  - 实盘无持仓")
                        
                        # 显示实盘资金信息
                        log.info(f"  - 实盘总资金: {g.sync_system.real_total_value:,.2f}元")
                        log.info(f"  - 实盘可用资金: {g.sync_system.real_available:,.2f}元")
                        log.info(f"  - 实盘持仓总市值: {total_real_value:,.2f}元" if real_holdings else "")
                    else:
                        log.info("  - 实盘持仓数据未初始化")
                except Exception as e:
                    log.error(f"  - 获取实盘持仓失败: {e}")
            else:
                log.info("  - 同步系统未初始化")
            
            # 6. 持仓对比分析（新���功能）
            log.info("📈 持仓对比分析:")
            if holdings and hasattr(g, 'sync_system') and g.sync_system is not None and hasattr(g.sync_system, 'real_positions'):
                real_holdings = g.sync_system.real_positions
                
                # 统计
                sim_only_count = 0  # 只在模拟盘有持仓
                real_only_count = 0  # 只在实盘有持仓
                both_count = 0  # 两边都有持仓
                
                # 检查模拟盘持仓在实盘中的情况
                for stock in holdings:
                    stock_code_6 = format_stock_code(stock[:6])
                    if stock_code_6 in real_holdings:
                        both_count += 1
                    else:
                        sim_only_count += 1
                
                # 检查实盘持仓在模拟盘中的情况
                for stock_code_6 in real_holdings.keys():
                    found = False
                    for stock in holdings:
                        if format_stock_code(stock[:6]) == stock_code_6:
                            found = True
                            break
                    if not found:
                        real_only_count += 1
                
                log.info(f"  - 持仓对比统计:")
                log.info(f"     两边都有持仓: {both_count}只")
                log.info(f"     只在模拟盘有持仓: {sim_only_count}只")
                log.info(f"     只在实盘有持仓: {real_only_count}只")
                
                if sim_only_count > 0:
                    log.warning(f"  ⚠️ 有{sim_only_count}只股票只在模拟盘有持仓，可能实盘买入失败")
                if real_only_count > 0:
                    log.warning(f"  ⚠️ 有{real_only_count}只股票只在实盘有持仓，可能是历史持仓或手动买入")
            
            # 7. 买入记录对比（新增）
            log.info("📝 买入记录对比:")
            if hasattr(g, 'sync_system') and g.sync_system is not None:
                if hasattr(g.sync_system, 'buy_sim_quantities'):
                    buy_records = g.sync_system.buy_sim_quantities
                    log.info(f"  - 买入记录数量: {len(buy_records)}条")
                    
                    if buy_records:
                        for stock, sim_qty in buy_records.items():
                            scale_factor = g.sync_system.buy_scale_factors.get(stock, 0)
                            real_qty_planned = g.sync_system.scale_quantity(sim_qty)
                            actual_qty = g.sync_system.real_positions.get(stock, 0)
                            
                            # 获取股票名称
                            try:
                                stock_name = get_security_info(stock).display_name
                            except:
                                stock_name = stock
                            
                            log.info(f"  - {stock_name}({stock}):")
                            log.info(f"     模拟买入: {sim_qty}股")
                            log.info(f"     比例因子: {scale_factor:.4f}")
                            log.info(f"     应实盘买入: {real_qty_planned}股")
                            log.info(f"     实盘实际持仓: {actual_qty}股")
                            
                            if actual_qty == 0:
                                log.warning(f"     ⚠️ 实盘持仓为0，可能未成交")
                            elif actual_qty < real_qty_planned:
                                log.warning(f"     ⚠️ 实盘持仓少于应买入数量")
                            elif actual_qty > real_qty_planned:
                                log.warning(f"     ⚠️ 实盘持仓多于应买入数量，可能手动买入")
                    else:
                        log.info("  - 今日无买入记录")
                else:
                    log.info("  - 无买入记录数据")
            else:
                log.info("  - 同步系统未初始化")
            
            # 8. 跌停列表事实记录
            log.info("📉 跌停列表事实记录:")
            if hasattr(g, 'dieting_stocks'):
                log.info(f"  - 跌停股票数量: {len(g.dieting_stocks)}")
                if g.dieting_stocks:
                    log.info(f"  - 跌停股票代码: {g.dieting_stocks}")
                else:
                    log.info("  - 跌停列表为空")
            else:
                log.info("  - 跌停列表未初始化")
            
            # 9. 函数调用追踪（关键）
            log.info("🔎 函数调用事实追踪:")
            log.info(f"  - 当前正在执行的函数: observe_13_00()")
            log.info(f"  - 观察目的: 记录13:00前后原策略的行为事实")
            log.info(f"  - 注意: 此函数只记录，不分析，不交易")
            
            # 10. 可能的原因（基于事实的推测，非分析）
            log.info("🤔 可能的原因推测（基于事实）:")
            log.info(f"  - 如果看到'实盘时间验证失败'日志:")
            log.info(f"    原因1: check_dieting()在13:00检测到跌停板打开，触发了卖出")
            log.info(f"    原因2: 其他未知的函数调用")
            log.info(f"  - 验证方法: 查看前序日志是否有跌停板打开记录")
            
            log.info("=" * 80)
            return True
        return False
    except Exception as e:
        log.error(f"🔥 13:00观察函数异常: {e}")
        log.error(traceback.format_exc())
        return False

def print_date_separator(context):
    """收盘后打印日期分隔线"""
    log.info("=" * 60)
    total_value = context.portfolio.total_value
    available_cash = context.portfolio.available_cash
    positions_value = total_value - available_cash
    positions_count = len(context.portfolio.positions)
    
    log.info(f"📈 每日收盘总结 | 总资产: {total_value:,.2f}元 | 可用资金: {available_cash:,.2f}元 | 持仓市值: {positions_value:,.2f}元 | 持仓数量: {positions_count}只")

#################################实盘切换函数#######################################
def enable_live_trading():
    """启用实盘交易模式"""
    A.isShipan = 1
    if hasattr(g, 'sync_system') and g.sync_system is not None:
        g.sync_system.is_shipan = 1
    log.info("🚀 已启用实盘交易模式（完美融合增强版）")
    log.info("📊 增强特性:")
    log.info("  1. 保守版的选股和买卖条件（盈利1%才卖）")
    log.info("  2. 保守版的跌停打开判断（current_price > low_limit）")
    log.info("  3. 保守版的比例因子范围（0.1-5.0）")
    log.info("  4. 属性自动恢复机制")
    log.info("  5. 增强异常处理和日志记录")
    log.info("  6. 实盘持仓为0时的智能处理")
    log.info("  7. 13:00问题纯观察功能（只记录事实，不分析条件）")
    log.info("  8. 实盘/模拟盘持仓对比功能（便于诊断问题）")
    log.info(f"📡 服务器地址: {your_server_addr}")

def disable_live_trading():
    """禁用实盘交易模式"""
    A.isShipan = 0
    if hasattr(g, 'sync_system') and g.sync_system is not None:
        g.sync_system.is_shipan = 0
    log.info("🔄 已禁用实盘交易模式（模拟模式）")

# 主函数
if __name__ == '__main__':
    print("=" * 70)
    print("昨日炸板策略 - 按比例同步实盘版（完美融合增强版）")
    print("=" * 70)
    print("完美融合方案：保守版的高收益因子 + 综合优化版的实盘稳定性 + 增强异常处理")
    print("=" * 70)
    print("已修复的关键问题：")
    print("1. ✅ 属性初始化问题：添加_initialize_attributes和_ensure_attributes_exist方法")
    print("2. ✅ 异常处理：所有关键函数添加try-catch，防止策略暂停")
    print("3. ✅ 状态恢复：属性丢失时自动重新初始化")
    print("4. ✅ 实盘持仓为0时的智能处理：不发送实盘信号，仅处理模拟盘")
    print("5. ✅ 增强日志：详细的异常信息和属性状态")
    print("6. ✅ 13:00问题纯观察功能：只记录事实，不分析条件，不改变原策略执行计划")
    print("7. ✅ 实盘/模拟盘持仓对比功能：便于诊断同步问题")
    print("=" * 70)
    print("实盘配置:")
    print(f"服务器地址: {your_server_addr}")
    print(f"Secret ID: {secretId}")
    print(f"Secret Key: {secretKey}")
    print("=" * 70)
    print("使用方法:")
    print("1. 回测测试: 直接运行 (A.isShipan = 0)")
    print("2. 启用实盘: 在模拟交易中运行 enable_live_trading()")
    print("3. 禁用实盘: 运行 disable_live_trading()")
    print("=" * 70)
    print("🎯 预期效果：高容错性 + 状态自动恢复 + 13:00问题纯观察 + 持仓对比诊断")
    print("=" * 70)