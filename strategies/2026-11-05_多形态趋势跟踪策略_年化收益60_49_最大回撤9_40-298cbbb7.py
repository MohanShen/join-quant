# Clone from JoinQuant
# postId: 298cbbb7ce2774e80a3d3e57c035e2f9
# backtestId: 478597661948cba9cab62d695e1d0921
# title: 多形态趋势跟踪策略：年化收益60.49%｜最大回撤9.40%

# -*- coding: utf-8 -*-
# 六形态共享仓位N8/K8/D5；有概念筛选，正常运行日志。
# 六形态筛选、经济次分、买卖时点、ATR、强趋势、费用与订单隔离沿用已回测版本。

"""
资金结构与执行口径
==================
单一资金池，初始资金100%，六形态共享资金和名额；N8/K8/D5。
N=实际持仓、活跃买单及有效突破预留合计名额上限；K=每日入围数；D=单笔预算分母。
六形态共用N8/K8/D5：最多8只持仓名额、每日8只入围、单笔预算分母5。
标准单笔预算B=本池当前净值×当日有效仓位系数÷D，总敞口预算=本池净值×有效系数。
下单还要扣实际持仓、在途买单和突破预留，核对真实现金；剩余不足B时允许较小一笔。
净值30万元、有效系数80%：总敞口预算24万元、标准单笔4.8万元；剩余预算不足4.8万元时允许小笔。
不自动给旧仓加仓或轮换旧仓；D不是持仓数量，N8/D5不保证买满8只。
形态优先级：洗盘→突破→超跌→吸筹→主升→标准。完整资格与形态内次分每日只算一次，
各池筛出自身启用形态，同股归最高优先级合格形态后取前K。N、D和余额不改变候选排名。
已有持仓保留首次成交形态；跨池持仓和卖出独立，不能用另一池的现金或卖出回款下单。
15:10按平台真实资产进行持仓、成交和净值对账，报告总资产而不平均各池收益或回撤。
正常日志保留初始化规则、风险与概念池、候选条件/次分、入围、真实委托/成交、持仓与对账。
完整研究指标、AUDIT和候选指纹/缓存复用统计默认不显示；真实异常仍保留。
下方详细说明与初始化日志共同描述全部现行规则，本轮未重新调优任何形态阈值。
"""


"""

组合与资金

【运行方式】单一资金池，初始资金100%，六形态共享资金和名额；N8/K8/D5。
【排序与入围】洗盘→突破→超跌→吸筹→主升→标准；先完整资格/历史排除及形态内次分，各池同股归最高优先级合格形态后取前K。洗盘/主升/标准跨原分排名，突破/吸筹/超跌原分优先；不自动轮换旧仓。
【名额与资金】六形态共用N8/K8/D5：最多8只持仓名额、每日8只入围、单笔预算分母5。
【预算例子】净值30万元、有效系数80%：总敞口预算24万元、标准单笔4.8万元；剩余预算不足4.8万元时允许小笔。

基础池与历史数据

【基础池】上市超过50自然日，排除4/8/68/92代码前缀；历史ST/停牌和当日ST/退市名称过滤→历史中证1000→至少命中一个热门概念。
【概念池】同股同概念去重计票/金额；基础排除转融券标的、融资融券、深股通、沪股通、国企改革，额外只剔新股与次新股；保留预增概念，不用滚动池。
【概念排行】昨日涨停组按计数排名；当日09:15—09:25竞价近涨停组按计数/竞价量×涨停价金额各50%排名；两组各Top4并集最多8个；同分按计数、金额、概念名。
【板型与加速】近2日有一字/T字涨停或近5日至少2次则排除；全部N3>=2或N5>=3排除。非创业N3>=1且R3>22%或N5>=2且R5>28%；创业R3>23%/R5>31%/R2>=21%/H2>=22%/R1>=14.5%/H1>=15.5%任一排除。
【形态过滤差异】除主升外五形态另排除非创业R15>37%、创业R15>40%；主升免R15。洗盘/主升/标准执行弱阴线与十日活跃，突破/吸筹/超跌不套用；保留原震仓排除。日线截至昨日，当前只用已知开盘/报价。
【活跃度】近10完整交易日先至少1日换手>2%；再要求振幅>3.5%的天数A>2，或换手>2%的天数Vn>2，或最大振幅>5.5%，或最大高点/前收涨幅>5.5%；缺失不视为通过。

洗盘：筛选、排序与专属交易

【洗盘共同硬】开盘较昨收>1%；d=C/MA10−1在(-5%,+0.5%)；C>MA20×1.005；45<RSI<区间上限；完整止跌；十日活跃。止跌=下影>5×实体或C>O或abs(C−O)/(前收+0.0001)<0.3%。
【洗盘G1/G2】G1(-5%,-3%)：RSI<60、昨低在MA20±0.3%且阳线；G2[-3%,-1.7%)：RSI<62、前一完成行C>=该行MA20。
【洗盘G3/G4】G3[-1.7%,-0.6%)：RSI<62.5、开盘/临时MA5−1>=−1%、前一行V/VMA5>=0.60；G4[-0.6%,+0.5%)：RSI<65、开盘/临时MA5−1<=2%、S10<=4%、昨L<MA<H穿过MA5/10/20至少两条且阳线。
【洗盘边缘】G1/G2至少3/4：MA5和MA10>MA20；V/(VMA5+0.0001)<0.76或V/(VMA8+0.0001)<0.75；非量脉冲；S5>S10。G3/G4硬化S5>S10或(MA5>MA10且S5>0.6%)，余下前三边缘至少2/3。
【洗盘四项次分】开盘距临时MA5绝对偏离越小30%；abs(S5+S10)越小25%；带符号实体(C−O)/(H−L+0.0001)越大25%；V/VMA5离0.60越近20%。合格洗盘跨区间/原分统一组内排名，同分依上述顺序再代码。
【洗盘买入】09:45/09:52按普通价带和高低过滤限价尝试，未买成且仍合格可14:54补买；尾盘另需现价>=临时MA10×0.995。
【洗盘观察】首日收盘<MA10×0.995时第2持有日14:54复核，仍<临时MA10退出；首日弱势修复优先等14:55，其他退出仍有效。洗盘免指数主动卖出，但受新增资金上限约束。

突破：筛选、排序与次日分支

【突破原硬与评分】昨涨幅>4%、V/VMA5>1.3、四均线收敛<2.5%、价格偏离角>25度全部满足；六边缘至少4条，原分>=90。六边缘=扩散>1.8、实体>0.5、阳包阴、收位>0.75、量增堆叠>=2、非量脉冲。
【突破六研究硬】收位>0.75；前一完成行V/VMA5<=2；昨日VMA10/VMA20<=1.2；扩散D<=4；昨日F02=V/VMA5<=2.5；F06=(C/MA20−1)/(ATRP14/100+0.0001)<=3.5。开盘涨幅须在[3%,7%]。具体epsilon和底稿见逐股复核。
【突破五项次分】原分100/95.8333/91.6667优先；仅同原分组内上影更小、C/MA20−1更小、左30变化最大收盘回撤更小、V/VMA5更高、四均线收敛更小，各20%；同分按该顺序再代码。
【突破预留】信号日t只预留、不买；t+1使用完整t日OHLCV。预留占现金和名额，只来自原有空闲或合格ATR额度；不因普通卖出回款凭空扩大尾盘信用。
【突破涨停/阳线】优先判断t日收盘涨停：次日开盘>信号收×1.02、<信号收×0.95或<信号前日收盘，取消；否则09:30市价。非涨停阳线C>O同样检查两项下界，不设+2%上界。
【突破小阴线】t日C<=O且C>=信号前日收盘：09:52和14:55均先核验两日可见低点，若<信号前收97%或<信号前开则取消；09:52还须现价>次日开盘102%，尾盘通过低点闸门即可市价。
【突破大阴线】t日C<=O且C<信号前收：信号日量>前日1.5倍取消；否则min(信号低,次日开)<信号前收95.5%或<信号前开取消；均通过则09:30市价。分支阳线优先，不凭文字名称改变分支。
【突破余单】09:30分支仅该时点尝试，09:31撤余单并结束；小阴09:52零成交可等14:55，09:53撤上午余单、14:56最终结束；任何部分成交均不补第二笔。突破豁免普通价带/高低过滤，仍受现金、风险、T+1和自身分支门槛。
【突破专属卖出】信号日计D1，D1/D2均阴且D2收更低则观察D3；D3阴且收<MA5→D4开盘退出，D3非阴结束，否则D4仍阴→D5开盘退出。突破免14:55加速退出。

主升：筛选、排序与专属交易

【主升共同硬】S5/S10/S20均>0、昨日V/VMA5<0.8、扩散D>0.25、C>MA20×1.02、十日活跃；开盘较昨收>1%。斜率为对应MA当前行/五行前值−1，不是角度。
【主升M1】C>MA5>MA10>MA20且d<3.5%；开盘/临时MA5−1在[1%,3%)；MA10十行斜率>1%；左30变化最大收盘回撤<=18%；P=max(前一完成行涨幅,0)×该行V/VMA5<=2%。
【主升M2】MA5>MA10>MA20且C>MA10；0.975MA5<=C<=MA5；d<3%；开盘>临时MA5；昨C>O、昨日量/前一行量>=0.75、昨低/MA10−1<=1%、S5<8%。
【主升边缘】四条至少3条：下影占比>0.35或收位>0.55；D>1.1；V>VMA20×0.4；(S5>2.8%且S10>1%)或[(S5<=2.8%或S10<1%)且S5+S10>3.3%]。
【主升五项次分】量比V/VMA5接近0.60占30%；收位更高10%；带符号实体更大10%；abs(C/MA5−1)更小30%；开盘距临时MA5接近2%占20%。全合格跨原分/M1/M2排序，同分按此顺序再代码。
【主升买卖】09:52及14:54按普通买入门槛；前三持有日收盘低于固定入场前收→次日09:30退出；首日弱势优先，次日修复成功仅豁免该日、第3日重新检查；14:54适用普通均线破位，14:55适用加速退出。

吸筹、超跌、标准：v0.5.54X最终条件

【吸筹六硬】abs(C/MA20−1)<3%；RSI<40；V<VMA20×0.6或abs(V−20日最低量)<0.01；前一完成行收盘涨幅>=−2%；(C/MA20−1)/(ATRP14/100+0.0001)>=−1；均线扩散D<=1.5。前行跌幅限制未企稳下跌，ATR尺度限制价格过远低于均线。开盘>1%。
【吸筹六边至少3】MA20五行斜率较前行提升；四均线收敛<3%；新锤子；新底背离；收盘位置>0.6；价量同升。原分=75+25×边缘命中/6。
【超跌五硬】R5<−6%或RSI<28；V近20日地量或V<VMA20×0.5；C/MA60−1<−6%；前一完成行RSI<=40；昨日(H−L)/(前收+0.0001)<=3.5%。前行RSI确认此前超跌，振幅限制当前尚未收敛的大幅摆动。开盘>1%。
【超跌六边至少3】四均线收敛<4%；昨日收涨；新锤子或真阳包阴且昨日涨>2%；新底背离；低开高收；MA20五行斜率较前行改善。原分=75+25×边缘命中/6；本版超跌仍当日普通窗口买，未改为次日。
【新锤子/底背离】吸筹/超跌：下影长度>=2×实体长度且下影占比>=50%且上影占比<=15%；底背离=C<=20行收盘升序第2值(包含并列)且V>20行最低量×1.12。分母H−L+0.0001；只用截至昨日完整数据。
【标准十硬】MA5>MA10>MA20；V/VMA5>1.2；开盘涨幅>1.5%；C>MA5或MA5>=C>MA10×1.02；D>0.25；VMA5>VMA20；(S5>2%且S10>1%)或S5+S10>3.2%；十日活跃；C/MA20−1<=15%；VMA10/(VMA20+0.0001)<=1.35或VMA5/(VMA20+0.0001)<=1.7。最后量能条件是或，任一满足即可。
【标准五边至少4】开盘涨幅<5%；C/(MA5+0.0001)<1.07；C>MA5；上影占比<0.3；MACD柱>0。原分98/100只表示合格强度，合格后统一按经济次分。
【吸筹/超跌次分】原分优先，同原分五项各20%：上影更小、开盘接近+3%、C/MA5接近1.005、VMA5/VMA20更高、MACD柱/C更高。
【标准次分】上影更大20%、开盘接近+3%10%、C/MA5接近1.005为40%、VMA5/VMA20更高20%、MACD柱/C更高10%；同分按此顺序再代码。三者09:52和14:54普通买入。

共用订单与普通退出

【普通买入价带】上午报价在固定开盘[99%,101%]；尾盘在[昨收99.5%,固定开盘101%]；按分取整。普通限价单只能约束成交上限，下界依报价核验和及时撤单，不保证跳价时仍在下界上。
【普通盘中高低过滤】当前可核验最低价不得低于昨收−0.5%，最高不得超过昨收+7.5%（创业+8%）；已完成分钟截至前一分钟并加已知开盘/当前报价。
【尾盘额度】只用原有额度及已确认ATR卖出额度；概念/指数/下午大跌/其他普通退出/强趋势/加速退出不新增尾盘额度。先核回报和退出再检查买入，卖出申请不当作已到账。
【ATR退出】截至昨日15有效日线计算TA-Lib ATR14；线=max(旧线,跟踪高点−k×ATR)，只上移；前三持有日k=1.8、第4日起1.55，14:35起每分钟判断；首日不完整ATR监控。
【开盘及持有期】09:30低开>=6%退出；持有>13交易日且昨收未涨停退出，最早第14日；昨收涨停延期计数继续。七日完整收盘浮盈均<0.5%→第8日开盘；八日完整收盘无一>4%→第9日开盘。
【首日走弱修复】买入首日收盘<=前收95%只标记；第2持有日暂免ATR并14:55检查相对首日收盘修复>=4%，未修复退出；其他适用规则不因此全部豁免。
【普通公共风控】14:30起较昨收跌>=8.5%；概念每5分钟统计曾触板且开板的持仓，同概念>=3只触发该概念可卖持仓退出；首日只计数不卖，强趋势也只计数。指数警报只对适用旧仓主动降仓。
【普通均线破位】14:54仅主升/突破/标准：现价<=临时MA10×0.97或<=临时MA20×0.995退出；洗盘使用专属次日MA10观察。临时MA=过去9/19完整收盘加当前价。
【14:55非创业加速】除突破外普通持仓当前未封或近封，且A持有>=3日且昨日封板，或B近2日至少一次封板且R2>17.5%，或C昨日封板且R3>22.5%且今日触涨停。近封等效仅此规则用曾触板且涨幅>9%。
【14:55创业加速】除突破外普通持仓：A当前涨幅<=8%、持有>=3日、昨涨>15%且昨最高涨>18%；或B当前涨<=13%且R2>23%；或C当前涨<=13%、昨涨>16%且R3>25%。

强趋势独立管理

【强趋势标记】盘前持有>=4交易日、昨收/平台成本浮盈非创业>=22.4%或创业>=22.9%；标记持续到清仓，豁免ATR/期限/低开/概念/指数/下午大跌/普通观察及加速退出。
【强趋势14:54退出】任一：较昨收跌>7%；较当日可核验高点回落>9%；(高−低)/昨收>12%且现<开×0.975且现<昨收；累计收盘高点回撤>13%；连跌>=4日且复合跌>8.5%；现<=临时MA10×0.97；现<=临时MA20×0.985；另有下面H/I高开转弱两条。
【强趋势新增H/I】H=开盘/昨收−1>8%且(日高−日低)/日高>10%且现价<开盘95%；I=开盘/昨收−1>2%且(日高−日低)/昨收>12%且日高/昨收−1>=8%且现价<昨收101%且现价<开盘。任一整组成立退出；连续一字开板当日豁免同样覆盖H/I。
【强趋势开板豁免】强趋势标记期间连续>=2个完整一字涨停后，开盘或盘中首次可核验打开的当天免强趋势退出，回封不撤回豁免、次交易日恢复；已成交卖单不能撤回。

时间、日志与成交口径

【盘前时间】09:24微观/持仓核对；09:26概念池与持仓规则；09:27退出计划→仓位分析→完整选股；09:29买入计划及耗时。
【交易时间】09:30普通退出/突破对应分支；09:45洗盘；09:52主升/吸筹/超跌/标准普通买入及突破小阴；14:35起ATR；14:54普通尾盘买/专属退出；14:55突破小阴尾买/观察及加速；撤余买单09:31/09:53/14:55/14:56；15:10对账。
【真实订单】09:30卖出和突破各买点用市价单；普通买入及其他卖出用限价单；不承诺市价按开盘价成交，不以委托当成交、不以撤单申请当成功、跌停排队保留实际持仓。
【日志】合格候选→各形态次分→单条条件复核→活跃度→历史统计→候选概念；research_indicator_logs=False、log_all_indicators=False关闭完整研究指标及突破额外研究明细，保留正常候选与条件复核，每日公共合格池只输出一遍，各账户输出入围/成交/持仓/净值；候选键=日期|形态|股票；readable不刷AUDIT。
【费用】固定价差滑点0.002元，双向佣金0.0003最低5元，卖出税2023-08-28前0.001/之后0.0005；真实价格、禁止未来数据、信号强撮合关闭；成交量比例不另覆盖平台默认。
【实现边界】概念沿用显式日期security_info.concepts，历史成员/名称时点语义尚未证实；非量脉冲字段恒False、宏观MACD30根窗口继续保留。本轮未把这些研究问题改成未经回测的新规则。
【微观结构计算】上证000001.XSHG，截至昨日完成日线；S=趋势T+动量M+波动Q+结构U，理论最高130；盘前r=clip(S/100×波动乘数,0,1)，资金出逃/临时上限再取较小值
【微观/趋势T】排列：MA3>MA10>MA20>MA60得30，否则MA3>MA10>MA20得20，否则MA10>MA20得10，否则0；s=100×(MA20/5个交易日前MA20−1)，斜率分clip((s+2)×5,0,20)
【微观/趋势乖离】b=100×(昨收/MA20−1)；b>5得max(0,15−3×(b−5))，b<−5得min(20,2×abs(b))，其余15；趋势三项合计最高70
【微观/动量M】从30扣分且最低0：昨收>=10日最高收盘×0.998且近5均量<前5均量×0.85扣20；昨收>倒数第5行收盘且RSI14<倒数第5行RSI×0.98扣15；MACD(12,26,9)末柱>0且最近3柱递减扣10，可叠加
【微观/波动Q】q=ATR14/ATR60；q<0.8得20分/乘1；q>1.5得5分/乘0.5；否则q>1.2得10分/乘0.75；其余15分/乘1。四项分数先相加，再乘该系数
【微观/结构U】z=昨日指数成交量/含昨日5日均量；z>1.5且昨日涨停家数<30得2，否则z>1.5得5；否则z>1.2得10；否则z<0.7得3；其余8
【微观/风险上限】近3日>=2日收跌且量>前日1.1倍，盘前r封顶30%；盘中每5分钟采样，10分钟跌超1.5%封顶30%，11:30较昨收跌超1.5%封顶50%；取最严并锁定当天，有效r=min(盘前r,盘中上限)
【微观/数据窗口】趋势80/动量30/波动120/结构20/资金出逃5日；长度不足沿用20分/15分/(10分,乘1)/5分/未出逃。30根MACD预热限制保留，未另改分数
【预算落单】可买预算=min(B,总敞口上限−实际持仓市值−活跃买单余量预算−突破预留,真实可用现金−突破预留)；尾盘还受合格信用约束。剩余不足B允许小额，乘0.995缓冲后按限价百股取整并核对费用
【仓位实际影响】实际持仓/活跃买单/有效突破预留共同占位；不自动补足旧仓、不因新候选换股。日常r下降只约束新增；独立指数警报超限>NAV×0.5%才减非强趋势且非洗盘旧仓。T+1/强趋势或洗盘豁免/停牌/未成交可使实际仓位暂超目标
"""

STRATEGY_NAME = '多形态趋势跟踪策略_六形态共享仓位N8_K8_D5版本'
STRATEGY_VERSION = 'multi-pattern-trend-v0.5.57B-normal'

from jqdata import *
# Explicit aliases resist names exported/injected by the platform or NumPy.
from builtins import any as py_any, all as py_all, sum as py_sum, min as py_min, max as py_max, abs as py_abs, round as py_round
import copy
import traceback
import datetime as dt
import time
import json
import math
from collections import defaultdict
import pandas as pd
import numpy as np
import talib

def trend_strength_score(context):
    try:
        index_code = '000001.XSHG'
        close = attribute_history(index_code, 80, '1d', ['close'],
                                  skip_paused=True)['close']
        if len(close) < 60:
            return 20

        ma3 = close[-3:].mean()
        ma10 = close[-10:].mean()
        ma20 = close[-20:].mean()
        ma60 = close[-60:].mean()
        current = close[-1]

        bull_score = 0
        if ma3 > ma10 > ma20 > ma60:
            bull_score = 30
        elif ma3 > ma10 > ma20:
            bull_score = 20
        elif ma10 > ma20:
            bull_score = 10

        ma20_prev = close[-25:-5].mean()
        ma20_slope = (ma20 - ma20_prev) / ma20_prev * 100 if ma20_prev > 0 else 0
        slope_score = py_max(0, py_min(20, (ma20_slope + 2) * 5))

        bias_20 = (current - ma20) / ma20 * 100
        if bias_20 > 5:
            bias_score = py_max(0, 15 - (bias_20 - 5) * 3)
        elif bias_20 < -5:
            bias_score = py_min(20, py_abs(bias_20) * 2)
        else:
            bias_score = 15

        return bull_score + slope_score + bias_score
    except Exception as e:
        raise RuntimeError("趋势评分数据错误") from e

def momentum_fatigue_score(context):
    try:
        index_code = '000001.XSHG'
        hist = attribute_history(index_code, 30, '1d',
                                 ['close', 'volume', 'high', 'low'],
                                 skip_paused=True)
        if len(hist) < 20:
            return 15

        price_new_high = hist['close'][-1] >= hist['close'][-10:].max() * 0.998
        vol_recent = hist['volume'][-5:].mean()
        vol_prev = hist['volume'][-10:-5].mean()
        volume_decline = vol_recent < vol_prev * 0.85

        divergence_penalty = 0
        if price_new_high and volume_decline:
            divergence_penalty = 20

        rsi = talib.RSI(hist['close'].values, timeperiod=14)
        if len(rsi) >= 5:
            rsi_divergence = (hist['close'][-1] > hist['close'][-5] and
                              rsi[-1] < rsi[-5] * 0.98)
            if rsi_divergence:
                divergence_penalty += 15

        macd, signal, hist_macd = talib.MACD(hist['close'].values,
                                             fastperiod=12, slowperiod=26,
                                             signalperiod=9)
        if len(hist_macd) >= 4 and hist_macd[-1] > 0:
            macd_fade = (hist_macd[-1] < hist_macd[-2] and
                         hist_macd[-2] < hist_macd[-3])
            if macd_fade:
                divergence_penalty += 10

        return py_max(0, 30 - divergence_penalty)
    except Exception as e:
        raise RuntimeError("动量评分数据错误") from e

def volatility_adjustment(context):
    try:
        index_code = '000001.XSHG'
        hist = attribute_history(index_code, 120, '1d',
                                 ['close', 'high', 'low'], skip_paused=True)
        if len(hist) < 60:
            return 10, 1.0

        atr14 = talib.ATR(hist['high'].values, hist['low'].values,
                          hist['close'].values, timeperiod=14)[-1]
        atr60 = talib.ATR(hist['high'].values, hist['low'].values,
                          hist['close'].values, timeperiod=60)[-1]
        atr_ratio = atr14 / atr60 if atr60 > 0 else 1.0

        if atr_ratio < 0.8:
            return 20, 1.0
        elif atr_ratio > 1.5:
            return 5, 0.5
        elif atr_ratio > 1.2:
            return 10, 0.75
        else:
            return 15, 1.0
    except Exception as e:
        raise RuntimeError("波动评分数据错误") from e

def market_micro_structure(context):
    try:
        index_code = '000001.XSHG'
        vol_hist = attribute_history(index_code, 20, '1d',
                                     ['volume'], skip_paused=True)['volume']
        if len(vol_hist) < 5:
            return 5

        current_vol = vol_hist[-1]
        ma5_vol = vol_hist[-5:].mean()
        limit_up_count = getattr(g, 'limit_up_count', 0)

        if current_vol > ma5_vol * 1.5:
            if limit_up_count < 30:
                return 2
            else:
                return 5
        elif current_vol > ma5_vol * 1.2:
            return 10
        elif current_vol < ma5_vol * 0.7:
            return 3
        else:
            return 8
    except Exception as e:
        raise RuntimeError("市场结构数据错误") from e

def is_capital_flight(context):
    try:
        index_code = '000001.XSHG'
        hist = attribute_history(index_code, 5, '1d',
                                 ['close', 'volume'], skip_paused=True)
        if len(hist) < 4:
            return False

        down_days = 0
        for i in range(-3, 0):
            if i >= -len(hist):
                price_down = hist['close'][i] < hist['close'][i - 1]
                vol_up = hist['volume'][i] > hist['volume'][i - 1] * 1.1
                if price_down and vol_up:
                    down_days += 1
        return down_days >= 2
    except Exception as e:
        raise RuntimeError("资金出逃数据错误") from e

def calculate_position_ratio(context):
    trend_score = trend_strength_score(context)
    momentum_score = momentum_fatigue_score(context)
    vol_score, vol_coeff = volatility_adjustment(context)
    micro_score = market_micro_structure(context)

    total_score = trend_score + momentum_score + vol_score + micro_score
    base_ratio = total_score / 100.0
    adjusted_ratio = base_ratio * vol_coeff

    if is_capital_flight(context):
        adjusted_ratio = py_min(adjusted_ratio, 0.3)
        log.warning("【极端风控】资金连续出逃，仓位评分系数降至不高于30%" if g.cfg.get("apply_micro_position_ratio",True) else "【极端风控诊断】资金连续出逃，评分降至不高于30%；本对照不应用日常系数，独立指数risk_cap仍有效")

    if g.emergency_cut:
        adjusted_ratio = py_min(adjusted_ratio, g.temp_position_ratio)
        scope = "不应用日常系数" if not g.cfg.get("apply_micro_position_ratio",True) else "仅总敞口上限" if g.cfg.get("capacity_mode")=="total_cap_only" else "固定名额，单股预算与总上限按系数" if g.cfg.get("capacity_mode")=="fixed_slots_scaled_unit" else "微观系统名额/单股预算/总上限"
        log.warning(f"【临时降仓诊断】微观评分临时上限{g.temp_position_ratio:.0%}；当前作用={scope}；独立指数风控另行生效")

    final_ratio = py_max(0.0, py_min(1.0, adjusted_ratio))

    log.info(f"【微观结构仓位诊断】趋势{trend_score:.2f}/70 动量{momentum_score:.2f}/30 "
             f"波动{vol_score}/20 微观{micro_score}/10 | "
             f"综合{total_score:.2f} | 系数{final_ratio:.2%}")

    return final_ratio

def calculate_micro_structure(df, private_frame=False):
    if df is None or len(df) < 20:
        return None
    optimized = g.cfg.get('performance_optimizations', True)
    if not (optimized and private_frame): df = df.copy()
    df['returns_1d'] = df['close'].pct_change()
    df['returns_5d'] = df['close'].pct_change(5)

    for period in [5, 10, 20, 60]:
        df[f'ma{period}'] = df['close'].rolling(window=period).mean()
        if not optimized or period != 60:
            df[f'ma{period}_slope'] = (df[f'ma{period}'] - df[f'ma{period}'].shift(5)) / df[f'ma{period}'].shift(5)
        if not optimized: df[f'ma{period}_accel'] = df[f'ma{period}_slope'].diff()

    df['ma_spread_ratio'] = (py_abs(df['ma5'] - df['ma10']) / (df['ma10'] + 0.0001)) / \
                            (py_abs(df['ma10'] - df['ma20']) / (df['ma20'] + 0.0001) + 0.0001)

    ma_values = df[['ma5', 'ma10', 'ma20', 'ma60']]
    df['ma_convergence'] = ma_values.std(axis=1) / (ma_values.mean(axis=1) + 0.0001)

    deviation = (df['close'] - df['ma20']) / (df['ma20'] + 0.0001)
    df['price_ma_angle'] = np.arctan(deviation * 20) * 180 / np.pi

    df['volume_ma5'] = df['volume'].rolling(window=5).mean()
    df['volume_ma8'] = df['volume'].rolling(window=8).mean()
    df['volume_ma10'] = df['volume'].rolling(window=10).mean()
    df['volume_ma20'] = df['volume'].rolling(window=20).mean()
    df['volume_ratio'] = df['volume'] / (df['volume_ma5'] + 0.0001)
    # Selection-only ATR: frozen 15 completed rows -> final 14 TR simple mean.
    # A rolling window uses only its own preceding close; no Wilder/holding ATR.
    selection_tr = pd.concat([df['high'] - df['low'],
        (df['high'] - df['close'].shift(1)).abs(),
        (df['low'] - df['close'].shift(1)).abs()], axis=1).max(axis=1)
    selection_tr.iloc[0] = np.nan
    selection_valid = pd.Series(np.isfinite(df[['high', 'low', 'close']].values).all(axis=1) &
        (df[['high', 'low', 'close']].values > 0).all(axis=1), index=df.index)
    selection_atr = selection_tr.rolling(14).apply(lambda values: float(np.mean(values)), raw=True)
    df['research_atr14_seed_15rows'] = selection_atr.where(selection_valid.rolling(15).sum() == 15)
    df['research_atrp14_pct'] = (df['research_atr14_seed_15rows'] / df['close']) * 100.
    df['volume_min_20'] = df['volume'].rolling(20).min()
    if not optimized: df['volume_max_20'] = df['volume'].rolling(20).max()

    df['volume_increasing'] = ((df['volume'] > df['volume'].shift(1)) &
                               (df['volume'].shift(1) > df['volume'].shift(2))).astype(int)
    df['volume_stack_days'] = df['volume_increasing'].rolling(5).sum()
    df['volume_shrink'] = df['volume'] < df['volume_ma20'] * 0.6
    df['volume_pulse'] = False  # v0.2: preserve old last-row False; no negative shift

    df['volume_ma_golden'] = (df['volume_ma5'] > df['volume_ma5'].shift(1)) & \
                             (df['volume_ma5'] > df['volume_ma20']) & \
                             (df['volume_ma5'].shift(1) <= df['volume_ma20'].shift(1))
    if not optimized:
        df['volume_ratio_change'] = df['volume_ratio'].pct_change()
        df['volume_ratio_ma3'] = df['volume_ratio'].rolling(3).mean()
        df['volume_ratio_trend'] = df['volume_ratio_ma3'].diff()

    body = py_abs(df['close'] - df['open'])
    range_hl = df['high'] - df['low']
    df['body_ratio'] = body / (range_hl + 0.0001)

    upper_shadow = df['high'] - np.maximum(df['close'], df['open'])
    lower_shadow = np.minimum(df['close'], df['open']) - df['low']
    df['upper_shadow_ratio'] = upper_shadow / (range_hl + 0.0001)
    df['lower_shadow_ratio'] = lower_shadow / (range_hl + 0.0001)

    # v53: semantic hammer; shadow/body are lengths, ratios retain H-L+0.0001.
    df['hammer'] = (lower_shadow >= 2. * body) & (df['lower_shadow_ratio'] >= .5) & \
                   (df['upper_shadow_ratio'] <= .15)
    df['engulfing'] = (df['close'] > df['open']) & \
                      (df['close'].shift(1) < df['open'].shift(1)) & \
                      (df['close'] > df['open'].shift(1)) & \
                      (df['open'] < df['close'].shift(1))
    df['close_position'] = (df['close'] - df['low']) / (range_hl + 0.0001)
    df['open_position'] = (df['open'] - df['low']) / (range_hl + 0.0001)
    df['low_open_high_close'] = (df['open_position'] < 0.3) & (df['close_position'] > 0.6)

    # The second order statistic includes duplicated closes; not the second DISTINCT price.
    # A full finite 20-row window is required; no current/future intraday data enter this column.
    df['close_second_low_20'] = df['close'].rolling(20, min_periods=20).apply(
        lambda values: np.partition(values, 1)[1] if bool(np.isfinite(values).all()) else np.nan, raw=True)
    price_low = df['close'] <= df['close_second_low_20']
    volume_not_low = df['volume'] > df['volume_min_20'] * 1.12
    df['divergence_bottom'] = price_low & volume_not_low
    df['bottom_volume_multiple'] = df['volume'] / df['volume_min_20'].where(df['volume_min_20'] > 0)

    # Same ATRP as the research evidence: last 15 complete rows -> mean of final 14 TRs.
    # This is the initial ATR14 value, NOT Wilder ATR warmed over the full selection frame.
    prev_close = df['close'].shift(1)
    tr = pd.concat([df['high']-df['low'], (df['high']-prev_close).abs(),
                    (df['low']-prev_close).abs()], axis=1).max(axis=1)
    valid_hlc = pd.Series(np.isfinite(df[['high','low','close']].values).all(axis=1)
        & (df[['high','low','close']].values > 0).all(axis=1), index=df.index)
    valid15 = valid_hlc.astype(float).rolling(15, min_periods=15).sum() == 15
    df['atr14_seed_15rows'] = tr.rolling(14, min_periods=14).mean().where(valid15)
    df['atrp14_pct'] = df['atr14_seed_15rows'] / df['close'].where(df['close'] > 0) * 100.
    df['ma20_atr_deviation'] = (df['close'] / df['ma20'].where(df['ma20'] > 0) - 1.) / (df['atrp14_pct'] / 100. + .0001)
    df['amplitude_prev_close'] = (df['high']-df['low']) / (prev_close.where(prev_close > 0) + .0001)
    df['price_volume_healthy'] = (df['close'] > df['close'].shift(1)) & \
                                  (df['volume'] > df['volume'].shift(1))

    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / (loss + 0.0001)
    df['rsi_14'] = 100 - (100 / (1 + rs))

    exp1 = df['close'].ewm(span=12, adjust=False).mean()
    exp2 = df['close'].ewm(span=26, adjust=False).mean()
    df['macd_dif'] = exp1 - exp2
    df['macd_dea'] = df['macd_dif'].ewm(span=9, adjust=False).mean()
    df['macd'] = 2 * (df['macd_dif'] - df['macd_dea'])

    return df

def identify_shakeout(df):
    """震仓识别：均线频繁交叉+RSI混沌+窄幅横盘，视为洗盘陷阱，跳过"""
    if len(df) < 10:
        return False

    latest = df.iloc[-1]
    recent = df.iloc[-6:].copy()
    recent['ma5_above_ma20'] = (recent['ma5'] > recent['ma20']).astype(int)
    cross_count = py_abs(recent['ma5_above_ma20'].diff()).sum()
    frequent_cross = cross_count >= 2

    rsi_recent = df['rsi_14'].iloc[-5:]
    rsi_chaotic = (40 < latest['rsi_14'] < 60) and (rsi_recent.std() < 5)

    recent_close = df['close'].iloc[-10:]
    price_range = (recent_close.max() - recent_close.min()) / (latest['close'] + 0.0001) * 100
    price_sideways = price_range < 4

    is_shakeout = frequent_cross and rsi_chaotic and price_sideways
    if is_shakeout and g.cfg.get('log_mode')=='full':
        log.info(f"【震仓识别】均线交叉{cross_count}次, RSI混沌{rsi_chaotic}, 振幅{price_range:.2f}%")

    return is_shakeout

def main_slope_edge_condition(s5, s10):
    """严格保留S10<1%的回退边界，不擅自扩成<=；输入为五行斜率小数。"""
    try:
        s5, s10 = float(s5), float(s10)
        if not np.isfinite(s5) or not np.isfinite(s10): return False
        first = s5 > .028 and s10 > .01
        fallback = (s5 <= .028 or s10 < .01) and s5 + s10 > .033
        return bool(first or fallback)
    except (TypeError, ValueError):
        return False


def wash_stop_fall_condition(latest, prev):
    """止跌硬条件：长下影、阳线、实体/前收不足0.3%三者满足其一。"""
    def value(row, key):
        try:
            number = float(row[key])
            return number if np.isfinite(number) else float('nan')
        except (KeyError, TypeError, ValueError):
            return float('nan')
    lower, body = value(latest, 'lower_shadow_ratio'), value(latest, 'body_ratio')
    close, opening, previous = value(latest, 'close'), value(latest, 'open'), value(prev, 'close')
    shadow = np.isfinite(lower) and np.isfinite(body) and lower > 5. * body
    bullish = np.isfinite(close) and np.isfinite(opening) and close > opening
    small = (py_all(np.isfinite(x) for x in (close, opening, previous)) and previous > 0 and
             py_abs(close - opening) / (previous + .0001) < .003)
    return bool(shadow or bullish or small)


class ComboEvaluator:
    """六维形态评估器：核心条件（必须全满足）+ 边缘条件（加权得分≥90）"""

    COMBO_CONFIG = {
        'combo_1': {'name': '吸筹期地量地价', 'priority': 4},
        'combo_2': {'name': '洗盘期缩量回调', 'priority': 1},
        'combo_3': {'name': '突破型放量启动', 'priority': 2},
        'combo_4': {'name': '主升浪回踩低吸', 'priority': 5},
        'combo_5': {'name': '极端超跌反弹', 'priority': 3},
        'combo_6': {'name': '标准多头排列', 'priority': 6}
    }

    @staticmethod
    def _safe_bool(val):
        try:
            if pd.isna(val):
                return False
            if hasattr(val, '__iter__') and not isinstance(val, (str, bytes)):
                if len(val) == 0:
                    return False
                val = val.iloc[0] if hasattr(val, 'iloc') else val[0]
            return bool(val)
        except:
            return False

    @staticmethod
    def _calculate_score(core_dict, edge_dict):
        try:
            core_bool_list = [bool(ComboEvaluator._safe_bool(v)) for v in core_dict.values()]
            edge_bool_list = [bool(ComboEvaluator._safe_bool(v)) for v in edge_dict.values()]

            core_met = py_sum(core_bool_list)
            edge_met = py_sum(edge_bool_list)

            core_count = len(core_bool_list)
            edge_count = len(edge_bool_list)
            if core_count == 0:
                return False, 0.0, 0, 0

            core_pass = (core_met == core_count)
            edge_ratio = edge_met / edge_count if edge_count > 0 else 0.0

            weighted_score = (core_met / core_count * 3 + edge_ratio * 1) / 4 * 100
            return core_pass, float(weighted_score), int(core_met), int(edge_met)
        except Exception as e:
            log.error(f"【六维评估】评分计算错误: {str(e)}")
            return False, 0.0, 0, 0

    @staticmethod
    def evaluate_combo_1(latest, prev, details=None):
        """吸筹：六硬全过+六边至少三；原两项风险门槛之外，扩散D<=1.5限制相对失衡。"""
        try:
            previous_return = float(prev.get('returns_1d', np.nan))
            atr_distance = float(latest.get('ma20_atr_deviation', np.nan))
            ceilings = selection_ceiling_metrics(latest)
            core = {
                'ma20_shake': py_abs(float(latest['close']) - float(latest['ma20'])) / float(latest['ma20']) < 0.03,
                'rsi_low': float(latest['rsi_14']) < 40,
                'volume_dry': (float(latest['volume']) < float(latest['volume_ma20']) * 0.6) or \
                               (py_abs(float(latest['volume']) - float(latest['volume_min_20'])) < 0.01),
                'previous_return_floor': bool(np.isfinite(previous_return) and previous_return >= -.02 - 1e-12),
                'ma20_atr_floor': bool(np.isfinite(atr_distance) and atr_distance >= -1. - 1e-12),
                'spread_ceiling': ceilings['accumulation_spread_pass']
            }
            edge = {
                'slope_up': float(latest['ma20_slope']) > float(prev['ma20_slope']) if not pd.isna(prev['ma20_slope']) else False,
                'convergence': float(latest['ma_convergence']) < 0.03,
                'hammer': bool(latest['hammer']),
                'divergence': bool(latest['divergence_bottom']),
                'close_pos': float(latest['close_position']) > 0.6,
                'pv_healthy': bool(latest['price_volume_healthy'])
            }
            if details is not None:
                details.update(core=dict(core), edge=dict(edge))
            core_pass, weighted_score, core_met, edge_met = ComboEvaluator._calculate_score(core, edge)
            return core_pass and edge_met >= 3, weighted_score, core_met, edge_met
        except Exception as e:
            log.error(f"【六维评估】combo_1错误: {str(e)}")
            return False, 0.0, 0, 0

    @staticmethod
    def evaluate_combo_2(latest, prev, details=None):
        """洗盘四区间：全部适用硬条件；深/中3/4，浅/企稳2/3；原分只展示，合格后统一四项次分排序。"""
        try:
            evidence = washout_condition_evidence(latest, prev)
            core, edge = evidence['core'], evidence['edge']
            if details is not None:
                details.update(evidence)
            core_pass, score, core_met, edge_met = ComboEvaluator._calculate_score(core, edge)
            return bool(core_pass and edge_met >= evidence['edge_required']), score, core_met, edge_met
        except Exception as e:
            log.error('【六维评估】combo_2错误: %s' % e)
            return False, 0.0, 0, 0

    @staticmethod
    def evaluate_combo_3(latest, prev, details=None):
        """原4硬+6边缘旧分>=90，再AND研究六硬；原边缘收盘位置保留。"""
        try:
            core = {
                'breakout': float(latest['returns_1d']) > 0.04,
                'volume_surge': float(latest['volume_ratio']) > 1.3,
                'ma_converge': float(latest['ma_convergence']) < 0.025,
                'price_angle': float(latest['price_ma_angle']) > 25
            }
            edge = {
                'ma_spread': float(latest['ma_spread_ratio']) > 1.8,
                'body_strong': float(latest['body_ratio']) > 0.5,
                'engulfing': bool(latest['engulfing']),
                'close_high': float(latest['close_position']) > 0.75,
                'vol_stack': int(latest['volume_stack_days']) >= 2,
                'no_pump': not bool(latest['volume_pulse'])
            }
            research_hard, research_values, research_formulas = breakout_research_hard_conditions(latest, prev)
            core_pass, weighted_score, core_met, edge_met = ComboEvaluator._calculate_score(core, edge)
            original_pass = core_pass and weighted_score >= 90
            if details is not None:
                details.update(core=dict(core), edge=dict(edge), original_pass=bool(original_pass),
                    research_hard=dict(research_hard), research_values=dict(research_values),
                    research_formulas=dict(research_formulas))
            return original_pass and py_all(research_hard.values()), weighted_score, core_met, edge_met
        except Exception as e:
            log.error(f"【六维评估】combo_3错误: {str(e)}")
            return False, 0.0, 0, 0

    @staticmethod
    def evaluate_combo_4(latest, prev, details=None):
        """主升两个互斥子型态，全部适用硬条件＋四条边缘至少3条，原评分公式保留。"""
        try:
            evidence=main_condition_evidence(latest,prev)
            core,edge=evidence['core'],evidence['edge']
            if details is not None:details.update(evidence)
            core_pass,score,core_met,edge_met=ComboEvaluator._calculate_score(core,edge)
            return bool(core_pass and edge_met>=3),score,core_met,edge_met
        except Exception as e:
            log.error('【六维评估】combo_4错误: %s'%e)
            return False,0.0,0,0

    @staticmethod
    def evaluate_combo_5(latest, prev, details=None):
        """超跌：五硬全过+六边至少三；前行RSI确认先前弱势，昨日振幅检验摆动收敛。"""
        try:
            previous_rsi = float(prev.get('rsi_14', np.nan))
            amplitude = float(latest.get('amplitude_prev_close', np.nan))
            core = {
                'deep_fall': (float(latest['returns_5d']) < -0.06) or \
                             (float(latest['rsi_14']) < 28),
                'volume_freeze': (py_abs(float(latest['volume']) - float(latest['volume_min_20'])) < 0.01) or \
                                 (float(latest['volume']) < float(latest['volume_ma20']) * 0.5),
                'far_ma60': (float(latest['close']) - float(latest['ma60'])) / float(latest['ma60']) < -0.06,
                'previous_rsi_ceiling': bool(np.isfinite(previous_rsi) and previous_rsi <= 40. + 1e-12),
                'amplitude_ceiling': bool(np.isfinite(amplitude) and amplitude <= .035 + 1e-12)
            }
            edge = {
                'ma_converge': float(latest['ma_convergence']) < 0.04,
                'rebound': float(latest['returns_1d']) > 0,
                'hammer_engulf': bool(latest['hammer']) or \
                                 (bool(latest['engulfing']) and float(latest['returns_1d']) > 0.02 + 1e-12),
                'divergence': bool(latest['divergence_bottom']),
                'low_open_high': bool(latest['low_open_high_close']),
                'ma_slope_recover': float(latest['ma20_slope']) > float(prev['ma20_slope'])
                if not pd.isna(prev['ma20_slope']) else False
            }
            if details is not None:
                details.update(core=dict(core), edge=dict(edge))
            core_pass, weighted_score, core_met, edge_met = ComboEvaluator._calculate_score(core, edge)
            return core_pass and edge_met >= 3, weighted_score, core_met, edge_met
        except Exception as e:
            log.error(f"【六维评估】combo_5错误: {str(e)}")
            return False, 0.0, 0, 0

class selection_stage:
    """Nested wall-clock spans; each category excludes nested spans to prevent double counting."""
    def __init__(self, name):
        self.name = name
        self.profile = None
    def __enter__(self):
        self.profile = getattr(g, 'selection_profile', None)
        if self.profile is not None:
            self.span = dict(name=self.name, started=time.perf_counter(), children=0.0)
            self.profile['stack'].append(self.span)
        return self
    def __exit__(self, exc_type, exc_value, exc_tb):
        if self.profile is not None:
            elapsed = time.perf_counter() - self.span['started']
            stack = self.profile['stack']
            stack.pop()
            exclusive = py_max(0.0, elapsed - self.span['children'])
            seconds = self.profile['seconds']
            seconds[self.name] = seconds.get(self.name, 0.0) + exclusive
            counts = self.profile['counts']
            counts[self.name] = counts.get(self.name, 0) + 1
            if stack:
                stack[-1]['children'] += elapsed
        return False


def selection_timed(name, function, *args, **kwargs):
    with selection_stage(name):
        return function(*args, **kwargs)


def selection_groups(frame):
    with selection_stage('data_prepare'):
        return {str(code): sub for code, sub in frame.groupby('code')}


def selection_history_label():
    profile = getattr(g, 'selection_profile', None)
    for span in reversed(profile['stack'] if profile else []):
        if span['name'] in ('board_evaluate', 'acceleration_evaluate', 'weak_candle_evaluate', 'activity_evaluate'):
            return span['name'].replace('_evaluate', '_query')
    return 'other_history_query'


def historical_entry_candidates(stocks, asof, defer_r15=False):
    stocks = filter_prior_limit_patterns(stocks, asof)
    if stocks and g.cfg.get('entry_acceleration_filter', True):
        stocks = filter_acceleration(stocks, asof, defer_r15=defer_r15)
    elif not g.cfg.get('entry_acceleration_filter', True):
        log.info('【涨幅加速过滤】参数关闭，仅用于独立消融实验；其他新规则照常')
    return stocks


def log_candidate_concepts(stock):
    # Uses membership actually fetched for today's selection; never substitutes current memberships.
    raw_effective = list(g.concepts.get(stock, []))
    names = sorted(set(raw_effective))
    matches = sorted(set(names) & set(g.concept_pool))
    evidence = getattr(g, 'concept_member_evidence', {}).get(stock, {})
    info = getattr(g, 'qs_combo_info', {}).get(stock)
    if info is not None:
        info['concept_evidence'] = dict(signal_asof=str(evidence.get('asof', g.asof)),
                                       source=evidence.get('source', g.cfg.get('concept_source')),
                                       raw=list(evidence['raw_names']) if 'raw_names' in evidence else None,
                                       effective=list(names), matched_hot=list(matches), matched_hot_count=len(matches),
                                       duplicate_effective_entries=len(raw_effective)-len(names))
    log.info(compact_log_text('【候选概念】%s | 命中热门:%s | 有效成员:%s | 来源:%s | 查询截至%s；扩展字段历史语义待平台核验' %
             (stock_label(stock),compact_log_value(matches),compact_log_value(names),
              evidence.get('source',g.cfg.get('concept_source')),evidence.get('asof',g.asof))))


def finish_selection_profile(started):
    profile = getattr(g, 'selection_profile', None)
    if profile is None:
        return
    total = time.perf_counter() - started
    profile['total_seconds'] = total
    profile['seconds']['unclassified'] = py_max(0.0, total - py_sum(profile['seconds'].values()))
    g.selection_profile_last = dict(asof=str(g.asof), seconds=dict(profile['seconds']),
                                    counts=dict(profile['counts']), total_seconds=total)
    g.selection_profile = None
    labels = [('base_pool', '基础池'), ('index_query', '指数成分查询'),
              ('concept_api', '概念对象接口'), ('concept_attribute', '概念属性读取'), ('concept_decode', '概念解析'), ('concept_match', '概念匹配及对照'),
              ('daily_query', '形态日线查询'), ('board_query', '板型查询'),
              ('acceleration_query', '加速查询'), ('weak_candle_query', '弱阴线查询'),
              ('activity_query', '活跃度日线查询'), ('activity_turnover_query', '历史换手查询'), ('activity_evaluate', '十日活跃核验'),
              ('other_history_query', '其他历史查询'), ('data_prepare', '数据整理'),
              ('micro_compute', '指标计算'), ('shape_evaluation', '形态判断'),
              ('board_evaluate', '板型核验'), ('acceleration_evaluate', '加速核验'),
              ('weak_candle_evaluate', '弱阴线核验'), ('ranking_output', '排序与候选日志'), ('condition_logging', '形态条件明细'), ('all_indicator_logging', '所有指标观察及输出'),
              ('unclassified', '其他及调度')]
    parts = ['%s=%.3f秒/%d次' % (label, profile['seconds'].get(key, 0.0), profile['counts'].get(key, 0))
             for key, label in labels if profile['seconds'].get(key, 0.0) or key in ('concept_api','concept_match','board_query','data_prepare')]
    log.info('【选股分项耗时】总计%.3f秒 | %s | 分项互斥，查询与数据整理分别计时；次数为真实调用/处理次数' %
             (total, ' | '.join(parts)))
    audit('SELECTION_PROFILE', **g.selection_profile_last)


def get_qs_stock_list(context,date_str):
    if getattr(g,'signal_cache',None) is not None:return list(g.signal_cache)
    shared=build_shared_candidates(context,date_str)
    if not getattr(g,'signal_ok',False):return []
    return finalize_shared_candidates(context,shared,date_str)

def audit(event,**payload):
    """Default is human-readable only. Full diagnostic mode is an explicit opt-in."""
    try:human_audit(event,payload)
    except Exception as exc:
        try:log.warning('【日志展示异常】'+event+': '+str(exc))
        except Exception:pass
    if getattr(g,'cfg',{}).get('log_mode','readable')!='full':return
    record=dict(payload,event=event)
    if event=='CONFIG':record.update(strategy_name=STRATEGY_NAME,version=STRATEGY_VERSION)
    try:log.info('AUDIT '+json.dumps(record,ensure_ascii=False,sort_keys=True,default=str))
    except Exception:pass

def normalize_stock_code(stock):
    return str(stock)

def checked_daily(df, asof):
    with selection_stage('data_prepare'):
        df = df.copy()
        if 'time' in df.columns:
            df = df.sort_values('time').set_index('time')
        else:
            df = df.sort_index()
        if df.empty or not isinstance(df.index, pd.DatetimeIndex):
            raise ValueError('日线时间索引缺失')
        if df.index.has_duplicates or df.index.max().date() > pd.Timestamp(asof).date():
            raise ValueError('日线重复或超出信号截止日')
        return df

def prepare_stock_list(date):
    key = str(date)
    if key in g.base_pool:
        return list(g.base_pool[key])
    g.prepare_stage='基础股票列表'
    securities = get_all_securities(types=['stock'], date=date)
    if securities is None or securities.empty:
        raise ValueError('基础股票列表为空；禁止请求空行情列表')
    oldest = pd.Timestamp(date).date() - dt.timedelta(days=50)
    stocks = sorted(str(s) for s in securities.index if not str(s).startswith(('4','8','68','92'))
                    and pd.Timestamp(securities.loc[s, 'start_date']).date() < oldest)
    audit('POOL_STAGE',stage='上市日期及板块过滤',remaining=len(stocks),asof=date)
    if not stocks:raise ValueError('上市日期及板块过滤后为空')
    g.prepare_stage='历史ST过滤'
    st = get_extras('is_st', stocks, start_date=date, end_date=date, df=True)
    if st is None or st.empty:raise ValueError('历史ST数据为空')
    stocks = [s for s in stocks if s in st.columns and not pd.isna(st[s].iloc[-1]) and not bool(st[s].iloc[-1])]
    audit('POOL_STAGE',stage='历史ST过滤',remaining=len(stocks),asof=date)
    if not stocks:raise ValueError('历史ST过滤后为空')
    g.prepare_stage='历史停牌过滤'
    paused = get_price(stocks, end_date=date, count=1, frequency='daily', fields=['paused'] if g.cfg.get('performance_optimizations',True) else ['close','paused'], skip_paused=False, panel=False)
    if paused is None or paused.empty or not {'code','paused'}.issubset(paused.columns):
        raise ValueError('历史停牌行情为空或缺少code/paused列')
    stocks = sorted(set(paused.loc[paused.paused == 0, 'code'].astype(str)) & set(stocks))
    audit('POOL_STAGE',stage='历史停牌过滤',remaining=len(stocks),asof=date)
    if not stocks:raise ValueError('历史停牌过滤后为空')
    g.prepare_stage='当前ST及退市名称过滤'
    cd = get_current_data()
    stocks = [s for s in stocks if not cd[s].is_st and not py_any(v in cd[s].name for v in ['ST','退'])]
    audit('POOL_STAGE',stage='当前名称过滤',remaining=len(stocks),asof=date)
    if not stocks:raise ValueError('当前名称过滤后为空；禁止请求空行情列表')
    g.base_pool = {key: stocks}  # bounded to one day
    return list(stocks)

def concepts(stock):
    # Keep original allowed entries (including duplicates) for exact legacy shadow evidence.
    # Decisions that need membership already use sets; only rank_concepts changes counting.
    if stock not in g.concepts:
        source=g.cfg.get('concept_source','legacy_security_info')
        if source=='legacy_security_info':
            info=selection_timed('concept_api',get_security_info,stock,date=g.asof)
            records=selection_timed('concept_attribute',getattr,info,'concepts',None)
            if records is None:raise ValueError('原版概念字段缺失 '+stock+'；不静默切换概念分类')
            with selection_stage('concept_decode'):
                if (not isinstance(records,(list,tuple)) or
                    py_any(not isinstance(x,dict) or not isinstance(x.get('name'),str) or not x.get('name') for x in records)):
                    raise ValueError('原版概念字段结构异常 '+stock)
                names=[r['name'] for r in records]
        elif source=='historical_get_concept':
            response=selection_timed('concept_api',get_concept,stock,date=g.asof)
            with selection_stage('concept_decode'):
                if not isinstance(response,dict) or stock not in response or 'jq_concept' not in response[stock]:
                    raise ValueError('历史概念结构异常 '+stock)
                names=[r.get('concept_name',r.get('name')) for r in response[stock]['jq_concept']]
                if py_any(not isinstance(n,str) or not n for n in names):raise ValueError('历史概念名称异常 '+stock)
        else:raise ValueError('未知概念来源 '+str(source))
        if getattr(g,'concept_evidence_asof',None)!=str(g.asof):
            g.concept_member_evidence={};g.concept_evidence_asof=str(g.asof)
        excluded={'转融券标的','融资融券','深股通','沪股通','国企改革'}
        names=list(names)
        allowed=[n for n in names if n and n not in excluded]
        g.concept_member_evidence[stock]=dict(raw_names=names,source=source,asof=str(g.asof),
            effective_unique=sorted(set(allowed)),removed_duplicates=len(allowed)-len(set(allowed)))
        g.concepts[stock]=allowed
        if stock in g.cfg.get('signal_audit_codes',[]):
            audit('CONCEPT_MEMBER',stock=stock,source=source,asof=g.asof,names=allowed,
                  point_in_time='显式历史日期；扩展concepts字段的历史语义仍需平台核验')
    return g.concepts[stock]

def filter_by_concept(stocks,pool):
    """Match the final pool; optional research diagnostics never change selection."""
    with selection_stage('concept_match'):
        pool_set=set(pool);selected=[]
        for stock in stocks:
            names=concepts(stock)
            if set(names)&pool_set:selected.append(stock)
        return selected

def concept_rank_table(stats):
    """Preserve all v0.5.23 scoring weights, rank steps, tie rules and zero-money behavior."""
    if not stats:return []
    df=pd.DataFrame.from_dict(stats,orient='index').reset_index()
    df.columns=['concept','count','volume']
    score={0:1.,1:.8,2:.7,3:.6,4:.5}
    by_count=df.sort_values(['count','volume','concept'],ascending=[False,False,True],kind='mergesort').reset_index(drop=True).copy()
    by_count['count_score']=by_count.index.map(lambda i:score.get(i,.4))
    by_count['count_rank']=by_count.index+1
    by_volume=df.sort_values(['volume','count','concept'],ascending=[False,False,True],kind='mergesort').reset_index(drop=True).copy()
    by_volume['volume_score']=by_volume.index.map(lambda i:score.get(i,.4))
    by_volume['volume_rank']=by_volume.index+1
    ranked=by_count.merge(by_volume[['concept','volume_score','volume_rank']],on='concept').copy()
    ranked['total_score']=ranked['count_score'] if ranked['volume'].sum()==0 else ranked['count_score']*.5+ranked['volume_score']*.5
    ranked=ranked.sort_values(['total_score','count','volume','concept'],ascending=[False,False,False,True],kind='mergesort').reset_index(drop=True)
    ranked['rank']=ranked.index+1
    return ranked.to_dict('records')


def rank_concepts(stocks,auction_money=None):
    started=time.perf_counter()
    day=str(getattr(g,'day',g.asof));kind='auction' if auction_money is not None else 'previous'
    label='当日竞价' if auction_money is not None else '昨日涨停'
    if getattr(g,'concept_rank_key',None)!=(day,str(g.asof)):
        g.concept_rank_key=(day,str(g.asof));g.concept_rank_evidence={}
    incoming=[str(s) for s in stocks];stocks=sorted(set(incoming))
    raw={};unique={};members={};contributors=[]
    for stock in stocks:
        names=list(concepts(stock));amount=float((auction_money or {}).get(stock,0.))
        if auction_money is not None and stock not in auction_money:raise ValueError('竞价来源金额缺失 '+stock)
        if not np.isfinite(amount) or amount<0:raise ValueError('概念来源金额非有限或负值 '+stock)
        multiplicity={}
        for name in sorted(names):multiplicity[name]=multiplicity.get(name,0)+1
        for name,count in sorted(multiplicity.items()):
            raw.setdefault(name,dict(count=0,volume=0.));unique.setdefault(name,dict(count=0,volume=0.))
            # Repeated addition exactly preserves the old floating-point accumulation sequence.
            for _ in range(count):raw[name]['count']+=1;raw[name]['volume']+=amount
            unique[name]['count']+=1;unique[name]['volume']+=amount
            members.setdefault(name,[]).append(stock)
        contributors.append(dict(stock=stock,amount=amount,multiplicity=multiplicity))
    legacy=concept_rank_table(raw);dedup=concept_rank_table(unique)
    clean=concept_rank_table({n:v for n,v in unique.items() if concept_exclusion_reason(n) is None})
    actual=clean if g.cfg.get('concept_exclude_broad',False) else (dedup if g.cfg.get('concept_deduplicate',True) else legacy)
    ev=dict(day=day,asof=str(g.asof),source=g.cfg.get('concept_source'),kind=kind,
        input_rows=len(incoming),unique_stocks=len(stocks),duplicate_stock_rows=len(incoming)-len(stocks),
        legacy=legacy,dedup=dedup,members=members,contributors=contributors,
        legacy_top=[r['concept'] for r in legacy[:4]],dedup_top=[r['concept'] for r in dedup[:4]],
        clean=clean,clean_top=[r['concept'] for r in clean[:4]],exclude_broad=bool(g.cfg.get('concept_exclude_broad',False)),
        actual_top=[r['concept'] for r in actual[:4]],deduplicate=bool(g.cfg.get('concept_deduplicate',True)))
    g.concept_rank_evidence[kind]=ev
    compute_seconds=time.perf_counter()-started
    log_started=time.perf_counter()
    try:log_concept_rank_evidence(ev)
    except Exception as exc:log.warning('【概念完整排行日志异常】%s | %s；实际排名已计算，不用日志替代决策' % (label,exc))
    if g.cfg.get('concept_diagnostic_log',False):
        log.info('【概念构建耗时/%s】来源读取与两口径排序%.3f秒 | 完整排行及底稿日志%.3f秒' %
                 (label,compute_seconds,time.perf_counter()-log_started))
    audit('CONCEPT_RANK',kind=kind,asof=g.asof,top=actual[:8])
    return ev['actual_top']


def log_concept_rank_evidence(ev):
    if not g.cfg.get('concept_diagnostic_log',False):return
    label='当日竞价' if ev['kind']=='auction' else '昨日涨停'
    if getattr(g,'concept_replay_day',None):label+='·历史补建'+str(ev['day'])
    raw={r['concept']:r for r in ev['legacy']};fixed=ev['dedup']
    old_count=py_sum(r['count'] for r in ev['legacy']);new_count=py_sum(r['count'] for r in fixed)
    log_section('概念完整排行 '+label)
    log.info('【概念去重/%s】交易日%s | 成员查询截至%s | 来源股票%d只/重复来源行%d | 概念%d个 | 原条目票%d→股票票%d，去重复票%d | 执行去重:%s' %
             (label,ev['day'],ev['asof'],ev['unique_stocks'],ev['duplicate_stock_rows'],len(fixed),old_count,new_count,old_count-new_count,ev['deduplicate']))
    log.info('【概念Top4对照/%s】旧重复口径:%s | 去重口径:%s | 实际执行:%s | 新增:%s | 移出:%s' %
             (label,ev['legacy_top'],ev['dedup_top'],ev['actual_top'],sorted(set(ev['dedup_top'])-set(ev['legacy_top'])),sorted(set(ev['legacy_top'])-set(ev['dedup_top']))))
    if g.cfg.get('concept_full_ranking_log',True):
        for row in fixed:
            old=raw[row['concept']]
            log.info('【概念全排名/%s】去重第%d/旧第%d | %s | 股票票%d/旧条目票%d | 金额估算%.8f/旧重复金额%.8f元 | 数量名次%d/金额名次%d | 数量分%.4f/金额分%.4f/总分%.4f/旧总分%.4f | 去重Top4:%s/实际Top4:%s' %
                (label,row['rank'],old['rank'],row['concept'],row['count'],old['count'],row['volume'],old['volume'],
                 row['count_rank'],row['volume_rank'],row['count_score'],row['volume_score'],row['total_score'],old['total_score'],
                 row['concept'] in ev['dedup_top'],row['concept'] in ev['actual_top']))
    log.info('【概念剔除重排/%s】原始去重前4:%s | 剔除后重新计算数量/金额名次分前4:%s | 实际执行:%s | 开关:%s | 命中排除名称:%s' %
             (label,ev['dedup_top'],ev['clean_top'],ev['actual_top'],ev['exclude_broad'],sorted(r['concept'] for r in fixed if concept_exclusion_reason(r['concept']) is not None)))
    if g.cfg.get('concept_full_ranking_log',True) and ev['exclude_broad']:
        for row in ev['clean']:
            log.info('【剔除后概念全排名/%s】第%d | %s | 股票票%d/金额估算%.8f元 | 数量名次%d/金额名次%d | 数量分%.4f/金额分%.4f/总分%.4f | 前4:%s' %
                     (label,row['rank'],row['concept'],row['count'],row['volume'],row['count_rank'],row['volume_rank'],row['count_score'],row['volume_score'],row['total_score'],row['concept'] in ev['clean_top']))
    if g.cfg.get('concept_source_detail_log',True):
        for row in ev['contributors']:
            log.info('【概念来源底稿/%s】%s | 单股竞价金额估算%.8f元 | 有效概念原条目次数:%s | 去重口径同股同名仅计1票及1次金额' %
                (label,row['stock'],row['amount'],json.dumps(row['multiplicity'],ensure_ascii=False,sort_keys=True)))
    log.info('【概念金额口径/%s】竞价成交量×当日涨停价估算；非净流入/非精确成交额。单股不同概念仍各计1次，跨概念金额不可加总；昨日来源无金额时只用数量名次分' % label)


def finalize_concept_pool_evidence():
    ev=getattr(g,'concept_rank_evidence',{})
    if getattr(g,'concept_rank_key',None)!=(str(getattr(g,'day',g.asof)),str(g.asof)) or not {'previous','auction'}<=set(ev):
        raise ValueError('两来源概念排行时点不完整，禁止用过期影子概念池')
    old=sorted(set(ev['previous']['legacy_top'])|set(ev['auction']['legacy_top']))
    new=sorted(set(ev['previous']['dedup_top'])|set(ev['auction']['dedup_top']))
    clean=sorted(set(ev['previous']['clean_top'])|set(ev['auction']['clean_top']))
    raw_pool=sorted(set(ev['previous']['actual_top'])|set(ev['auction']['actual_top']))
    actual=update_rolling_concept_pool(raw_pool) if g.cfg.get('concept_rolling',False) else raw_pool
    g.concept_pool_legacy_shadow=old;g.concept_pool_dedup_shadow=new;g.concept_pool_clean_shadow=clean
    g.concept_pool=actual;g.concept_policy_valid_day=str(g.day)
    if g.cfg.get('concept_diagnostic_log',False):
        log.info('【概念池修复对照】旧并集:%s | 去重并集:%s | 剔除重排并集:%s | 实际:%s' % (old,new,clean,actual))

def build_concept_pool(context):
    prior_data=load_previous_limit_up(context)
    stocks=prior_data['stocks'];yesterday=prior_data['yesterday']
    g.limit_up_count=len(yesterday)
    g.prepare_stage='昨日涨停原版概念';prior=rank_concepts(yesterday)
    day=str(context.current_dt.date())
    # Reproduce original concept auction window; entry reference remains final day_open.
    cutoff=day+' 09:25:00'
    if pd.Timestamp(cutoff)>pd.Timestamp(context.current_dt):raise ValueError('竞价截止晚于当前时点')
    g.prepare_stage='当日竞价快照'
    auction=get_call_auction(stocks,start_date=day+' 09:15:00',end_date=cutoff,fields=['time','current','volume'])
    if auction is None or auction.empty or not {'time','code','current','volume'}.issubset(auction.columns):
        raise ValueError('竞价数据为空或结构不符；不自动改变原版窗口')
    auction=auction.copy();auction['time']=pd.to_datetime(auction['time'])
    if auction.time.isna().any() or auction.time.max()>pd.Timestamp(context.current_dt) or auction.time.min()<pd.Timestamp(day+' 09:15:00'):
        raise ValueError('竞价响应包含未来时间或跨日数据；禁止使用')
    if auction.time.max()>pd.Timestamp(cutoff):
        audit('AUCTION_BOUNDARY_NOTICE',requested_end=cutoff,actual_latest=str(auction.time.max()),
              observed_at=context.current_dt,note='接口响应边界有偏移，但快照已在当前时点形成；与原版一样使用返回快照')
    latest=auction.sort_values('time',kind='mergesort').groupby('code',sort=False).tail(1).set_index('code')
    cd=get_current_data();top=[];money={}
    # Same base-stock order as original instead of concept/name tie-break sorting.
    for s in stocks:
        if s in latest.index and float(latest.loc[s,'current'])>=cd[s].high_limit*.998:
            top.append(s);money[s]=float(latest.loc[s,'volume'])*cd[s].high_limit
    audit('AUCTION_DATA',requested_fields=['time','current','volume'],rows=len(auction),
          returned_columns=list(auction.columns),end=cutoff,latest_snapshot=str(auction.time.max()),
          note='原版概念窗口；股票买入参考仍为09:25后day_open，不用此快照强制成交')
    today=rank_concepts(top,money)
    g.concept_pool=sorted(set(prior)|set(today))
    finalize_concept_pool_evidence()
    audit('CONCEPT_POOL',asof=g.asof,source=g.cfg['concept_source'],auction_end=cutoff,
          previous=prior,auction=today,pool=g.concept_pool,limit_up_count=g.limit_up_count)

def initialize(context):
    set_option('use_real_price', True)
    set_option('avoid_future_data', True)
    set_option('match_by_signal', False)
    configure_stock_order_cost(context,force=True)
    set_slippage(FixedSlippage(.002))  # 固定价差0.002元，不是0.2%比例滑点
    set_benchmark('000852.XSHG')
    g.cfg = dict(max_count=8, selection_count=8, unit_budget_divisor=5, enabled_combo_types=('combo_2', 'combo_3', 'combo_5', 'combo_1', 'combo_4', 'combo_6'), use_concept_selection=True, wash_buy_start_time='09:45', wash_weak_priority=True, atr_n=14, atr_k=1.55, atr_early_k=1.8, atr_early_days=3, max_hold=13,
                 open_gap_exit=True, concept_exit=True, afternoon_exit=True,
                 micro_risk=True, intraday_risk_reduce=True,
                 limit_buffer=.003, cash_buffer=.005, order_timeout_minutes=2,
                 opening_order_style='market', opening_quote_tolerance=.001,
                 market_budget_buffer=.01, buy_time='09:52', monitor_interval=1,
                 afternoon_drop=.085, entry_price_cap=.01, buy_cancel_time='14:55',
                 position_quantity_mode='total_includes_locked',cancel_retry_minutes=1,cancel_max_attempts=3,
                 concept_source='legacy_security_info',tie_policy='economic_all_shapes',wash_rank_scope='all_qualified',
                 log_mode='readable', log_shape_conditions=True, research_indicator_logs=False, log_all_indicators=False, concept_deduplicate=True,
                 concept_full_ranking_log=False, concept_source_detail_log=False, concept_diagnostic_log=False,
                 concept_exclude_broad=True, concept_rolling=False, skip_selection_without_capacity=False, buy_start_time='09:52', sell_start_time='14:35', late_buy_time='14:54',
                 apply_micro_position_ratio=True, capacity_mode='fixed_slots_scaled_unit', performance_optimizations=True, selection_reference_pipeline=False, entry_acceleration_filter=True,
                 supplemental_prev_close_floor=.995, morning_open_floor=.99,
                 acceleration_exit=True, breakout_apply_intraday_filter=False, breakout_signal_conflict='limit_first', breakout_small_bear_early_low_check=True, open_gap_drop=.06,
                 strong_trend_profit=.224, strong_trend_growth_profit=.229,
                 strong_trend_age=4,
                 entry_weak_drop=.05, entry_recovery=.04,
                 signal_audit_codes=('300034.XSHE','301078.XSHE','600776.XSHG','300777.XSHE','600416.XSHG'))
    g.concept_pool_history={};g.concept_policy_valid_day=None
    g.book = {};g.orders = {};g.seen_trades=set();g.fee_seen={};g.closed=[]
    g.deferred_breakouts = {}
    g.position_archive={};g.acceleration_checked_day=None
    g.halt_reasons={};g.rollover_pending={};g.position_snapshots={}
    g.day = None;g.halted=False;g.signal_ok=False;g.qs_max_count=g.cfg['selection_count']
    run_daily(prepare_day, time='09:24')
    run_daily(prepare_holdings, time='09:26')
    run_daily(plan_sells, time='09:27')
    run_daily(plan_buys, time='09:29')
    validate_execution_times()
    run_daily(opening_exit_session,time='09:30')
    for clock in execution_sessions():run_daily(opening_session,time=clock)
    for clock in buy_cancel_times():run_daily(cancel_opening_buys,time=clock)
    run_daily(finish_day, time='15:10')
    if g.cfg['acceleration_exit'] and g.cfg['late_buy_time']!='14:55':run_daily(acceleration_session,time='14:55')
    audit('RUNTIME_BINDINGS', unqualified_any_module=getattr(any,'__module__','unknown'),
          explicit_any_module=py_any.__module__)
    log_section(STRATEGY_NAME+' 初始化 '+STRATEGY_VERSION)
    log.info('【执行时间】洗盘09:45/09:52及14:54；主升09:52/14:54；突破信号日仅预留，次日09:30三分支/小阴线%s和14:55；ATR%s起 | 普通退出09:30起' % (entry_start(),exit_start()))
    audit('CONFIG', config=g.cfg, first_order='09:30', last_order='14:56',
          slippage_type='FixedSlippage',slippage_value=.002,order_volume_ratio='platform_default_not_overridden',
          fee_policy=stock_fee_policy_text(), initial_capital=context.portfolio.total_value)

def total_qty(p):
    # Current user's exports support inclusive total_amount. No ledger-driven auto-detection.
    total=int(p.total_amount)
    locked=int(getattr(p,'locked_amount',0))
    if total<0 or locked<0:raise ValueError('负持仓字段')
    mode=g.cfg.get('position_quantity_mode','total_includes_locked')
    if mode=='total_includes_locked':return total
    if mode=='total_excludes_locked':return total+locked
    raise ValueError('未知持仓字段口径: '+str(mode))

def prepare_day(context):
    if g.day == str(context.current_dt.date()):
        return
    configure_stock_order_cost(context)
    started=time.perf_counter()
    log_section('每日盘前分析 '+str(context.current_dt.date()))
    rollover_orders(context)
    g.day=str(context.current_dt.date());g.asof=str(context.previous_date)
    g.seen_trades=set();g.orders={};g.fee_seen={};g.attempted=set();g.sold_today=set()
    g.warned=set();g.base_pool={};g.concepts={};g._micro_data_cache={};g._cache_date=g.asof
    g.concept_policy_valid_day=None
    g.qs_combo_info={};g.concept_pool=[];g.atr={};g.candidates=[];g.signal_ok=False
    g.emergency_cut=False;g.temp_position_ratio=1.;g.position_ratio=0.;g.base_ratio=0.
    g.session_quotes={};g.touched=set();g.touched_seed=set();g.afternoon_done=False;g.open_checked=False
    g.last_callback=None;g.signal_seconds=0.;g.risk_cap=1.;g.basis_blocked=set(g.book)
    g.opening_done=False;g.candidates_ready=False;g.open_checked_stocks=set()
    g.qs_max_count=g.cfg['selection_count']
    g.quote_cache={};g.prior_cache={};g.age_cache={};g.touch_until={}
    g.buy_done=False;g.profile=defaultdict(float)
    g.open_plan={};g.plan_ready=False;g.sale_planned=False;g.opening_ticks=set()
    g.buy_cancel_requested=False;g.buy_cancel_windows=set();g.attempted_windows=set();g.accel_daily_cache={}
    g.late_seed=None;g.eligibility_fills={};g.morning_checked_candidates=set();g.maturity_limit_cache={}
    g.strong_close_cache={}
    g.prepare_stage='初始化';g.prepare_retry_done=False;g.prepare_retryable=True
    g.signal_cache=None;g.position_snapshots={};g.display_names={}
    g.shared_selection_asof=None;g.shared_selection_day=None;g.shared_qualified_candidates=[];g.shared_selection_snapshot={};g.all_qualified_candidates=[]
    g.previous_limit_cache=None;g.prepare_seconds={};g.prepare_failures={};g.retry_in_progress=False
    g.macro_ready=False;g.holdings_ready=False;g.concept_ready=False;g.sell_plan_done=False
    g.selection_status='未评估';g.selection_skipped=False;g.premarket_reported=False
    prepare_macro(context)
    refresh_breakout_reservations(context)

def prepare_signals(context):
    if getattr(g,'selection_status','未评估') in ('完成','跳过'):return
    started=None
    try:
        if not getattr(g,'macro_ready',False):prepare_macro(context)
        if not getattr(g,'holdings_ready',False) or not selection_concept_ready():prepare_holdings(context)
        if not (getattr(g,'macro_ready',False) and getattr(g,'holdings_ready',False) and selection_concept_ready()):
            raise ValueError('宏观、持仓或本版所需概念筛选数据尚未就绪')
        started=time.perf_counter()
        g.prepare_stage='启用%d种形态候选' % len(enabled_combo_types())
        p=capacity_snapshot(context)
        if g.cfg.get('skip_selection_without_capacity',False) and not p['room_or_exit']:
            g.selection_status='跳过';g.selection_skipped=True;g.signal_ok=False;g.candidates_ready=False
            g.candidates=[];g.signal_cache=None
            log.info('【选股跳过】有名额或卖出计划:False；今日不计算候选，稍后临时腾仓也不补算。原持仓/退出/订单管理继续')
        else:
            g.signal_ok=True
            g.candidates=get_qs_stock_list(context,g.asof)
            if not g.signal_ok:raise ValueError('选股计算失败，见筛选异常')
            g.signal_cache=list(g.candidates);g.selection_status='完成';g.candidates_ready=True
    except Exception as exc:
        g.signal_ok=False;g.candidates_ready=False;g.selection_status='失败'
        g.prepare_retryable=(type(exc).__name__ not in ('ParamsError','TypeError') and
                            py_all(v['retryable'] for k,v in getattr(g,'prepare_failures',{}).items() if k!='concept' or use_concept_selection()))
        audit('PREPARE_ERROR',stage=g.prepare_stage,error=str(exc),action='禁止新买；09:29可重试一次，已有持仓继续管理')
    finally:
        if started is not None:add_prepare_seconds('选股阶段',started)
        log_selection_summary()

def atr_for(stock):
    if stock not in g.atr:
        h=checked_daily(get_price(stock,end_date=g.asof,count=15,frequency='daily',
                                  fields=['high','low','close'],fq='pre',skip_paused=True),g.asof)
        val=float(talib.ATR(h.high.values,h.low.values,h.close.values,timeperiod=g.cfg['atr_n'])[-1])
        if not np.isfinite(val) or val<=0:
            raise ValueError('ATR缺失 '+stock)
        g.atr[stock]=val
    return g.atr[stock]

def adjust_price_basis(context):
    restore_position_metadata(context,'盘前复权前')
    for s,b in list(g.book.items()):
        h=checked_daily(get_price(s,end_date=b['anchor_date'],count=1,frequency='daily',fields=['close'],fq='pre'),b['anchor_date'])
        ratio=float(h.close.iloc[-1])/b['anchor_close']
        if not np.isfinite(ratio) or ratio<=0:raise ValueError('复权基准异常 '+s)
        if py_abs(ratio-1)>1e-8:
            old=dict(high=b['high'],stop=b['stop'],qty=b['qty'])
            b['high']*=ratio;b['stop']*=ratio;b['anchor_close']*=ratio
            if b.get('weak_entry_close') is not None:b['weak_entry_close']*=ratio
            p=context.portfolio.positions.get(s)
            if p is not None:b['qty']=total_qty(p)
            audit('BASIS_ADJUST',stock=s,anchor_date=b['anchor_date'],ratio=ratio,before=old,
                  after=dict(high=b['high'],stop=b['stop'],qty=b['qty']),cash_dividend='依平台资金流水核对')
    reconcile_positions(context,'开盘前复权后')
    snapshot_position_metadata()

def active_order(stock, side=None):
    return py_any(v['stock']==stock and not v['terminal'] and (side is None or v['side']==side)
               for v in g.orders.values())

def exposure_value(context):
    # Canonical account valuation includes sell-frozen holdings in this user's engine.
    value=float(context.portfolio.positions_value)
    if not np.isfinite(value) or value<0:raise ValueError('账户持仓市值异常')
    return value

def sync_orders(context):
    profile_add('order_syncs',1)
    actual_orders={str(k):v for k,v in get_orders().items()}
    trades=get_trades()
    for key,t in sorted(trades.items(),key=lambda x:(x[1].time,str(x[0]))):
        tid=str(key);oid=str(t.order_id)
        if tid in g.seen_trades:
            continue
        if oid not in g.orders:
            halt_new_buys(context,'UNOWNED_FILL',tid);audit('UNOWNED_FILL',trade_id=tid,order_id=oid);g.seen_trades.add(tid);continue
        intent=g.orders[oid];s=intent['stock'];qty=py_abs(int(t.amount));price=float(t.price)
        if qty<=0:
            continue
        if intent['side']=='buy':
            if s not in g.book:
                g.book[s]=dict(qty=0,buy_value=0.,sell_value=0.,entry_date=str(t.time.date()),
                               entry_time=str(t.time),combo=dict(intent['combo']),high=price,
                               stop=price-position_atr_multiplier(context)*intent['atr'],
                               atr_initial_multiplier=position_atr_multiplier(context),
                               atr_tracking_multiplier=position_atr_multiplier(context),anchor_date=intent['anchor_date'],
                               anchor_close=intent['anchor_close'],exit_reason=None)
            b=g.book[s];b['qty']+=qty;b['buy_value']+=qty*price;b['high']=py_max(b['high'],price)
        else:
            if s not in g.book or qty>g.book[s]['qty']:
                halt_new_buys(context,'FILL_LEDGER_ERROR',tid);audit('FILL_LEDGER_ERROR',stock=s,trade_id=tid,qty=qty)
                g.seen_trades.add(tid);continue
            b=g.book[s];b['qty']-=qty;b['sell_value']+=qty*price;g.sold_today.add(s)
            if b['qty']==0:
                audit('POSITION_CLOSED',stock=s,buy_value=b['buy_value'],sell_value=b['sell_value'],
                      gross_cash_difference=b['sell_value']-b['buy_value'],entry_date=b['entry_date'],
                      combo=b['combo'],note='未计费用和分红，净盈亏以平台导出对账')
                g.closed.append(dict(stock=s,**b));del g.book[s]
                getattr(g,'position_archive',{}).pop(s,None)
        record_late_eligibility_fill(context,intent,tid,t,qty,price,intent['side']=='sell' and s not in g.book)
        intent['seen_qty']+=qty;g.seen_trades.add(tid)
        audit('FILL',stock=s,side=intent['side'],trade_id=tid,order_id=oid,time=t.time,
              qty=qty,price=price,reason=intent['reason'],
              reference_price=intent.get('reference_price'),
              reference_source=intent.get('reference_source'),
              fill_minus_reference_bps=(price/intent['reference_price']-1)*10000 if intent.get('reference_price') else None,
              order_style=intent.get('style'))
        if intent['side']=='buy' and intent.get('entry_limit') is not None and price>intent['entry_limit']+1e-8:
            halt_new_buys(context,'LIMIT_FILL_VIOLATION',oid)
            audit('LIMIT_FILL_VIOLATION',stock=s,price=price,limit=intent['entry_limit'],
                  action='保留真实成交，停止新买，核查平台撮合')
        if intent['side']=='buy' and intent.get('entry_floor') is not None and price<intent['entry_floor']-1e-10:
            intent['floor_fill_breach']=True
            audit('SUPPLEMENT_FILL_BELOW_FLOOR',stock=s,order_id=oid,trade_id=tid,price=price,floor=intent['entry_floor'],
                  action='真实成交已记账；买入限价不保证最低成交价，后续同步检查将申请撤剩单，不伪造撤回已成交股数')
        if intent.get('reference_source')=='day_open' and t.time.strftime('%H:%M')=='09:30':
            if py_abs(price-intent['reference_price'])>py_max(.011,intent['reference_price']*.02):
                halt_new_buys(context,'OPEN_FILL_REVIEW',oid)
                audit('OPEN_FILL_REVIEW',stock=s,fill_price=price,day_open=intent['reference_price'],
                      action='开盘成交偏离超过2%，暂停新买并人工核验；不修改实际成交')
    for oid,intent in g.orders.items():
        o=actual_orders.get(oid)
        if o is None:
            if context.current_dt-intent['submitted']>dt.timedelta(minutes=1):
                halt_new_buys(context,'ORDER_MISSING',oid,True);audit('ORDER_MISSING',order_id=oid)
            continue
        intent['reported_filled']=int(o.filled)
        status=str(o.status).split('.')[-1]
        if intent['seen_qty']>=int(o.filled):clear_halt(context,'ORDER_MISSING',oid,'订单重新可见且成交完整核对')
        # get_trades can lag get_orders: keep reservation until every reported fill is consumed.
        intent['terminal']=(status in ['held','canceled','rejected'] and intent['seen_qty']>=int(o.filled))
        if intent['terminal']:
            clear_halt(context,'CANCEL_UNCONFIRMED',oid,'订单终态及全部成交已确认')
        state=(status,int(o.filled),intent['seen_qty'])
        if state!=intent.get('last_state'):
            audit('ORDER_STATE',order_id=oid,stock=intent['stock'],status=status,
                  filled=int(o.filled),reconciled=intent['seen_qty'],terminal=intent['terminal'])
            intent['last_state']=state
        fee=getattr(o,'commission',None)
        if fee is not None and fee!=g.fee_seen.get(oid):
            audit('ORDER_FEE',order_id=oid,fee=fee);g.fee_seen[oid]=fee
    snapshot_position_metadata()
    for stock,p in context.portfolio.positions.items():
        if hasattr(p,'total_amount'):position_snapshot(context,stock,p)

def quote_uncached(context,stock):
    if context.current_dt.strftime('%H:%M')=='09:30':
        return opening_quote(context,stock)
    if context.current_dt.strftime('%H:%M')=='09:31':
        cd=get_current_data()[stock]
        latest=float(cd.last_price);op=float(cd.day_open)
        if cd.paused or not np.isfinite(latest) or latest<=0 or not np.isfinite(op) or op<=0:
            return None
        return dict(price=latest,high=latest,time=context.current_dt,
                    source='current_data_0931',day_open=op,observed_at=context.current_dt)
    # Strictly earlier bar; no current incomplete minute OHLC is requested.
    cutoff=context.current_dt-dt.timedelta(minutes=1)
    h=get_price(stock,end_date=cutoff,count=1,frequency='1m',
                fields=['close','high','volume'],fq='pre',skip_paused=False)
    if h is None or h.empty:
        return None
    timestamp=pd.Timestamp(h.index[-1]).to_pydatetime()
    row=h.iloc[-1]
    if timestamp>=context.current_dt or timestamp.date()!=context.current_dt.date():
        return None
    if (cutoff-timestamp).total_seconds()>60 or not np.isfinite(row.close) or row.close<=0 or row.volume<=0:
        return None
    return dict(price=float(row.close),high=float(row.high),time=timestamp)

def quote(context,stock):
    key=(context.current_dt,stock)
    if not hasattr(g,'quote_cache'):g.quote_cache={}
    if key not in g.quote_cache:
        if py_any(k[0]!=context.current_dt for k in g.quote_cache):g.quote_cache={}
        g.quote_cache[key]=quote_uncached(context,stock)
        profile_add('quote_fetches',1)
    return g.quote_cache[key]

def profile_add(name,value):
    if not hasattr(g,'profile'):g.profile=defaultdict(float)
    g.profile[name]+=value

def previous_close(stock):
    if not hasattr(g,'prior_cache'):g.prior_cache={}
    key=(g.asof,stock)
    if key not in g.prior_cache:
        h=checked_daily(get_price(stock,end_date=g.asof,count=1,frequency='daily',
                                  fields=['close'],fq='pre'),g.asof)
        value=float(h.close.iloc[-1])
        if not np.isfinite(value) or value<=0:raise ValueError('昨收缺失 '+stock)
        g.prior_cache[key]=value
    return g.prior_cache[key]

def holding_days(context,entry_date):
    if not hasattr(g,'age_cache'):g.age_cache={}
    key=(entry_date,str(context.current_dt.date()))
    if key not in g.age_cache:
        g.age_cache[key]=len(get_trade_days(start_date=entry_date,end_date=context.current_dt.date()))
    return g.age_cache[key]

def afternoon_trigger(context,stock,price):
    if context.current_dt.strftime('%H:%M')<'14:30' or not g.cfg['afternoon_exit']:return False
    return price<=previous_close(stock)*(1-g.cfg['afternoon_drop'])+1e-10

def monitoring_due(context):
    t=context.current_dt.strftime('%H:%M')
    return t>='14:30' or context.current_dt.minute%g.cfg['monitor_interval']==0

def opening_quote(context,stock):
    """Known official opening quote, NOT a previous-close or unfinished minute-bar substitute.
    Guard the engine's latest price before a market order; never force a fill at this quote.
    """
    cd=get_current_data()[stock]
    op=float(cd.day_open);latest=float(cd.last_price)
    if cd.paused or not np.isfinite(op) or op<=0 or not np.isfinite(latest) or latest<=0:
        audit('OPEN_QUOTE_BLOCKED',stock=stock,reason='开盘价/最新价无效或停牌');return None
    tolerance=py_max(.011,op*g.cfg['opening_quote_tolerance'])
    if py_abs(latest-op)>tolerance:
        audit('OPEN_QUOTE_BLOCKED',stock=stock,day_open=op,last_price=latest,
              reason='最新价与开盘价未对齐，可能仍为昨收或已快速变动；跳过开盘单')
        return None
    return dict(price=op,high=op,time=context.current_dt,source='day_open',
                observed_at=context.current_dt,last_price=latest)

def trading_minute(context):
    t=context.current_dt.strftime('%H:%M')
    return t in ('09:30','09:31') or '09:32'<=t<='11:30' or '13:02'<=t<='14:56'

def send_order(context,stock,side,qty,reason,q,combo=None):
    if side=='buy' and not combo_is_enabled((combo or {}).get('combo_type')):return False
    if side=='sell':
        refresh_exempt_exit_intents(context,stock,g.book.get(stock,{}))
        if exit_reason_exempt(context,stock,g.book.get(stock,{}),reason):return False
    if side=='sell' and maturity_cancel_pending(context,stock):return False
    if not trading_minute(context) or active_order(stock):
        return False
    clock=context.current_dt.strftime('%H:%M')
    deferred = side=='buy' and bool(q.get('deferred_breakout'))
    if side=='buy' and (combo or {}).get('combo_type')=='combo_3' and stock in breakout_cancelled_today():return False
    if side=='buy':
        if deferred:
            plan=getattr(g,'deferred_breakouts',{}).get(stock)
            if not plan or not breakout_window_allowed(context,plan):return False
            if not q.get('deferred_market') or (combo or {}).get('combo_type')!='combo_3':return False
            if not breakout_buy_allowed(context,stock,plan,q):return False
        elif not ordinary_entry_shape_allowed(clock,combo):return False
    if side=='sell' and not exit_monitor_eligible(context,stock):return False
    if side=='sell' and is_atr_reason(reason) and clock<exit_start():
        flag=(stock,'sell_time_gate')
        if flag not in g.warned:
            audit('SELL_TIME_GATE',stock=stock,reason=reason,allowed_from=exit_start());g.warned.add(flag)
        return False
    cd=get_current_data()[stock]
    if cd.paused or qty<=0:
        return False
    if side=='buy' and (cd.is_st or (not q.get('deferred_market') and q['price']>=cd.high_limit*.998)):
        return False
    if side=='sell':
        p=context.portfolio.positions.get(stock)
        qty=py_min(int(qty),int(p.closeable_amount) if p else 0)
        if qty<=0:
            flag=(stock,reason,'T1')
            if flag not in g.warned:
                audit('EXIT_DEFERRED',stock=stock,reason=reason,cause='无可卖数量/T+1');g.warned.add(flag)
            return False
    buffer=g.cfg['limit_buffer']
    raw=q['price']*(1+buffer if side=='buy' else 1-buffer)
    limit=(math.ceil(raw*100-1e-8) if side=='buy' else math.floor(raw*100+1e-8))/100.
    limit=py_min(float(cd.high_limit),py_max(float(cd.low_limit),limit))
    if side=='buy' and not q.get('deferred_market'):
        cap=q.get('entry_limit')
        if cap is None or not np.isfinite(cap) or cap<=0:
            audit('BUY_SKIP',stock=stock,reason='缺少冻结的允许买入限价');return False
        floor=q.get('entry_floor')
        if floor is None:
            floor=0. if deferred else math.ceil(previous_close(stock)*g.cfg.get('supplemental_prev_close_floor',.995)*100-1e-8)/100.
            q['entry_floor']=floor
        if not np.isfinite(floor) or (floor<=0 and not deferred) or q['price']<floor-1e-10:
            audit('BUY_SKIP',stock=stock,reason='买入报价低于本窗口允许下界或下界缺失',floor=floor,price=q['price']);return False
        limit=py_min(float(cd.high_limit),float(cap))
        if limit<float(cd.low_limit) or q['price']>limit+1e-10:return False
    meta={}
    if side=='buy':
        atr=atr_for(stock)
        meta=dict(combo=dict(combo or {}),atr=atr,anchor_date=g.asof,anchor_close=previous_close(stock))
    is_open=clock=='09:30'
    market=((side=='sell' and is_open) and g.cfg['opening_order_style']=='market') or (deferred and q.get('deferred_market',False))
    if deferred and market: limit=float(cd.high_limit)
    style=MarketOrderStyle() if market else LimitOrderStyle(limit)
    audit('ORDER_INTENT',stock=stock,side=side,qty=qty,limit=None if market else limit,quote=q,
          order_style='market' if market else 'limit',
          signal_asof=g.asof,reason=reason,combo=combo)
    try:
        o=order(stock,qty if side=='buy' else -qty,style=style)
    except Exception as e:
        audit('ORDER_REJECTED',stock=stock,error=str(e),reason=reason);return False
    if o is None:
        audit('ORDER_REJECTED',stock=stock,error='返回 None',reason=reason);return False
    oid=str(o.order_id)
    reserve_price=py_max(limit,q['price']*(1+g.cfg['market_budget_buffer'])) if market and side=='buy' else limit
    g.orders[oid]=dict(stock=stock,side=side,qty=qty,limit=reserve_price,reason=reason,
                       reference_price=q['price'],reference_source=q.get('source','completed_minute'),
                       style='market' if market else 'limit',
                       entry_limit=limit if side=='buy' and not market else None,
                       entry_floor=q.get('entry_floor') if side=='buy' else None,
                       expires_at=add_clock(clock,1) if deferred else buy_expiry(clock) if side=='buy' else None,
                       deferred_breakout=deferred, deferred_market=bool(q.get('deferred_market')),
                       plan_reference=q.get('plan_reference'),
                       native_order_id=o.order_id,reported_filled=int(o.filled),
                       submitted=context.current_dt,seen_qty=0,terminal=False,**meta)
    audit('ORDER_ACCEPTED',order_id=oid,stock=stock,side=side,qty=qty)
    sync_orders(context)
    return True

def cancel_expired(context, all_orders=False):
    requested = False; clock = context.current_dt.strftime('%H:%M')
    for oid, intent in list(g.orders.items()):
        if intent['terminal'] or preserve_limit_queue(context, oid, intent): continue
        if intent['side'] == 'buy':
            expiry = intent.get('expires_at')
            if not expiry:
                submitted_clock = intent['submitted'].strftime('%H:%M')
                expiry = add_clock(submitted_clock,1) if intent.get('deferred_breakout') else buy_expiry(submitted_clock)
            expired = clock >= expiry
        else: expired = context.current_dt - intent['submitted'] >= dt.timedelta(minutes=g.cfg['order_timeout_minutes'])
        if all_orders or expired: requested = request_cancel(context, oid, '收盘' if all_orders else '窗口结束/超时') or requested
    if requested: sync_orders(context)

def risk_monitor(context):
    if not g.cfg['micro_risk'] or context.current_dt.minute%5:
        return
    q=quote(context,'000001.XSHG')
    if not q:
        return
    session='am' if context.current_dt.hour<12 else 'pm'
    key=(session,context.current_dt)
    g.session_quotes[key]=q['price']
    prior=g.session_quotes.get((session,context.current_dt-dt.timedelta(minutes=10)))
    cap=1.
    if prior and q['price']/prior-1<-.015:
        cap=.3
    if context.current_dt.strftime('%H:%M')=='11:30':
        h=checked_daily(get_price('000001.XSHG',end_date=g.asof,count=1,fields=['close']),g.asof)
        if q['price']/float(h.close.iloc[-1])-1<-.015:
            g.risk_cap=py_min(g.risk_cap,.5)
    if cap<1 or g.risk_cap<1:
        g.risk_cap=py_min(g.risk_cap,cap)  # latch for day; no automatic buying back
        old=g.position_ratio;g.position_ratio=py_min(g.base_ratio,g.risk_cap)
        if old!=g.position_ratio:
            audit('RISK_CAP_CHANGE',before=old,after=g.position_ratio,trigger='指数风险')

def reduce_exposure(context):
    if not g.cfg['intraday_risk_reduce']:
        return
    refresh_all_exit_exemptions(context)
    nav=float(context.portfolio.total_value)
    exposure=exposure_value(context)
    excess=exposure-nav*exposure_target_ratio()
    # Cap is an order constraint. Do not churn on ordinary price drift: reduce only after index alarm.
    if g.risk_cap>=1 or excess<=nav*.005:
        return
    for s,b in sorted(g.book.items(),key=lambda x:(x[1]['combo'].get('priority',99),x[0]),reverse=True):
        if exit_reason_exempt(context,s,b,'指数风险降仓') or not exit_monitor_eligible(context,s,b):continue
        if py_any(not o['terminal'] and o['side']=='sell' for o in g.orders.values()):
            return
        p=context.portfolio.positions.get(s)
        q=quote(context,s)
        if p is None or not q or int(p.closeable_amount)<=0:
            continue
        qty=py_min(int(p.closeable_amount),int(math.ceil(excess/q['price']/100))*100)
        if send_order(context,s,'sell',qty,'指数风险降仓',q):
            return
    if excess>0:
        flag=('risk','T1')
        if flag not in g.warned:
            audit('RISK_CAP_UNACHIEVABLE',excess=excess,cause='强趋势或洗盘指数卖出豁免/T+1/停牌/行情缺失或未成交；风险上限仍约束新增买入');g.warned.add(flag)

def manage_positions(context):
    profile_add('position_checks',1)
    cd=get_current_data();concept_quotes={}
    concept_due=g.cfg['concept_exit'] and context.current_dt.minute%5==0
    for stock,b in list(g.book.items()):
        refresh_exempt_exit_intents(context,stock,b)
        eligible=exit_monitor_eligible(context,stock,b)
        if not eligible and not concept_due:continue
        if stock in g.basis_blocked:
            if (stock,'basis') not in g.warned:
                audit('EXIT_DATA_BLOCKED',stock=stock,reason='历史价格基准未核对，避免错误除权止损/概念计数')
                g.warned.add((stock,'basis'))
            continue
        q=quote(context,stock)
        if not q:continue
        if concept_due and observe_concept_touch(context,stock,q,cd[stock]):
            concept_quotes[stock]=q
        if not eligible:continue
        refresh_exempt_exit_intents(context,stock,b)
        # Strong labels are sticky; their ATR line is archival only. Observation-day
        # positions still update the trailing line but cannot generate or execute ATR.
        if not b.get('strong_trend'):
            if q['time']>=pd.Timestamp(b['entry_time']).to_pydatetime():
                b['high']=py_max(b['high'],q['price'])
            try:
                multiplier=position_atr_multiplier(context,b)
                old_stop=b['stop'];daily_atr=atr_for(stock)
                b['stop']=py_max(old_stop,b['high']-multiplier*daily_atr)
                b['atr_last_update']=dict(old_stop=float(old_stop),daily_atr=float(daily_atr),
                    raw_line=float(b['high']-multiplier*daily_atr),updated_at=str(context.current_dt))
                if b.get('atr_tracking_multiplier')!=multiplier:
                    log.info('【ATR倍数切换】%s | 实际买入%s/第%d交易日 | %.2f倍 | 高点%.3f/ATR%.4f | 旧线%.3f→新线%.3f | 退出仍从%s起' % (stock_label(stock),b['entry_date'],holding_days(context,b['entry_date']),multiplier,b['high'],daily_atr,old_stop,b['stop'],exit_start()))
                    b['atr_tracking_multiplier']=multiplier
            except Exception as exc:audit('ATR_DATA_ERROR',stock=stock,error=str(exc))
        age=holding_days(context,b['entry_date'])
        reason=resolve_position_exit(context,stock,b,q,cd[stock],age)
        if reason:
            if is_atr_reason(reason):log_atr_trigger_evidence(context,stock,b,q)
            b['exit_reason']=reason
            send_order(context,stock,'sell',b['qty'],reason,q)
    g.open_checked=True
    if concept_due:apply_concept_breaks(context,concept_quotes,cd)
    strong_tail_session(context)
    ordinary_tail_trend_session(context)
    washout_tail_session(context)
    observation_tail_session(context)
    snapshot_position_metadata()

def record_opening_exits(context):
    if g.day != str(context.current_dt.date()): prepare_day(context)
    log_section('开盘退出计划'); cd = get_current_data()
    for stock, book in list(g.book.items()):
        if not exit_monitor_eligible(context, stock, book) or stock in g.basis_blocked: continue
        try:
            refresh_exempt_exit_intents(context,stock,book)
            activate_close_exit_plan(context,stock,book)
            due = refresh_maturity_intent(context, stock, book)
            pending = book.get('exit_reason')
            reason = pending if pending and not is_atr_reason(pending) and not is_maturity_reason(pending) else None
            if due: reason = reason or '持仓超过%d交易日且昨收未涨停退出' % g.cfg['max_hold']
            op = float(cd[stock].day_open)
            if (not book.get('strong_trend') and g.cfg['open_gap_exit'] and np.isfinite(op)
                    and op > 0 and op / previous_close(stock) - 1 <= -g.cfg['open_gap_drop']+1e-12):
                reason = reason or '开盘低开6%'
            if reason:
                book['exit_reason'] = reason; g.sale_planned = True
                audit('LOCAL_SELL_PLAN', stock=stock, reason=reason, planned_at=context.current_dt,
                      note='保存有效普通退出意图，最早09:30执行；强趋势/次日观察豁免已核验')
            elif is_atr_reason(pending) and not exit_reason_exempt(context,stock,book,pending):
                g.sale_planned = True
                audit('LOCAL_SELL_PLAN', stock=stock, reason=pending, planned_at=context.current_dt,
                      note='可卖阶段ATR退出仍待执行，不得早于' + exit_start())
        except Exception as exc: audit('SELL_PLAN_ERROR', stock=stock, error=str(exc))

def build_buy_plan(context):
    if g.day != str(context.current_dt.date()): prepare_day(context)
    capture_late_seed(context)
    if g.plan_ready or not g.signal_ok or g.halted: return
    g.plan_ready = True
    log_section('买入信号计划'); current = get_current_data()
    for stock in g.candidates:
        if stock in breakout_cancelled_today() and g.qs_combo_info.get(stock,{}).get('combo_type')=='combo_3': continue
        try:
            reference = float(current[stock].day_open); previous = previous_close(stock)
            if not py_all(np.isfinite(v) and v > 0 for v in (reference, previous)):
                raise ValueError('固定开盘/昨收无效')
            cap = math.floor(reference * (1 + g.cfg['entry_price_cap']) * 100 + 1e-8) / 100.
            morning = math.ceil(reference * g.cfg['morning_open_floor'] * 100 - 1e-8) / 100.
            late = math.ceil(previous * g.cfg['supplemental_prev_close_floor'] * 100 - 1e-8) / 100.
            combo = dict(g.qs_combo_info[stock])
            g.open_plan[stock] = dict(reference=reference, previous_close=previous,
                morning_lower_limit=morning, late_lower_limit=late, lower_limit=morning,
                limit=cap, combo=combo, initial=False)
            if combo.get('combo_type') == 'combo_3':
                log.info('【突破待预留/尚未委托】%s | 信号日昨收%.3f | 信号日只预留绝不买；次日按完整t/t-1量价分四分支执行；实际名额及合格额度不足不绑定' % (stock_label(stock), previous))
            else:
                log.info('【买入计划/尚未委托】%s | 入场形态:%s | 固定开盘%.3f/昨收%.3f | %s允许[%.2f,%.2f] | %s允许[%.2f,%.2f] | 上下界倒置的窗口不买' %
                    (stock_label(stock), main_shape_display_name(combo), reference, previous, (g.cfg['wash_buy_start_time']+'/'+entry_start()) if combo.get('combo_type')=='combo_2' else entry_start(), morning, cap, g.cfg['late_buy_time'], late, cap))
        except Exception as exc: audit('BUY_PLAN_SKIP', stock=stock, reason=str(exc))


def entry_quote(context, stock, plan):
    current = get_current_data()[stock]; price = float(current.last_price)
    if current.paused or not np.isfinite(price) or price <= 0: return None
    floor, cap = ordinary_price_band(context, plan)
    return dict(price=price, high=price, time=context.current_dt, source='current_data_entry',
        observed_at=context.current_dt, plan_reference=plan['reference'],
        entry_limit=cap, entry_floor=floor, is_initial_entry=False)

def buy_candidates(context):
    clock=context.current_dt.strftime('%H:%M')
    if clock not in entry_sessions() or g.halted or not g.signal_ok or not g.plan_ready:return
    rebalance_breakout_reservations(context)
    late=clock==g.cfg['late_buy_time']
    ratio=sizing_ratio();ceiling=exposure_target_ratio();slots=position_slot_limit()
    if late:
        credit=late_eligibility_snapshot(context)
        if not credit['ready'] or credit['cash']<=0 or credit['slots']<=0:return
    # Washout has first priority for today's executable plans. New breakout
    # reservations follow that attempt; prior-day reservations stay binding.
    for phase in (0,1):
        if phase==1:reserve_breakout_plans(context)
        for stock,plan in g.open_plan.items():
            if g.halted:return
            combo=plan['combo'].get('combo_type')
            if combo=='combo_3' or ((combo=='combo_2') != (phase==0)):continue
            if not ordinary_entry_shape_allowed(clock,plan['combo']):continue
            if not late:g.morning_checked_candidates.add(stock)
            elif stock not in g.morning_checked_candidates:continue
            if (clock,stock) in g.attempted_windows or stock in g.sold_today or stock in g.book or active_order(stock):continue
            if stock in getattr(g,'deferred_breakouts',{}):continue
            if slots<=0 or ceiling<=0:continue
            live={o['stock'] for o in g.orders.values() if o['side']=='buy' and not o['terminal']}
            deferred=breakout_pending_snapshot()
            if len(set(g.book)|live|deferred['stocks'])>=slots:continue
            q=entry_quote(context,stock,plan)
            if q is None:continue
            if q['entry_floor']>q['entry_limit'] or q['price']<q['entry_floor']-1e-10 or q['price']>q['entry_limit']+1e-10:
                log.info('【本时点不买】%s | %s报价%.3f不在允许买入区间[%.2f,%.2f]；后续合法窗口可重新检查' % (stock_label(stock),clock,q['price'],q['entry_floor'],q['entry_limit']));continue
            if not intraday_entry_allowed(context,stock,q):continue
            if late and combo=='combo_2' and not washout_late_entry_allowed(context,stock,q['price']):continue
            cd=get_current_data()[stock]
            if cd.paused or cd.is_st or q['price']>=cd.high_limit*.998:continue
            nav=float(context.portfolio.total_value)
            reserve=py_sum(py_max(0,o['qty']-o['seen_qty'])*o['limit'] for o in g.orders.values() if o['side']=='buy' and not o['terminal'])
            cash_cap=py_max(0.,float(context.portfolio.available_cash)-deferred['cash'])
            if late:
                credit=late_eligibility_snapshot(context)
                if not credit['ready'] or credit['slots']<=0:continue
                cash_cap=py_min(cash_cap,py_max(0.,credit['cash']))
            budget=py_min(nav*ratio/unit_budget_divisor(),nav*ceiling-exposure_value(context)-reserve-deferred['cash'],cash_cap)
            qty=int(py_max(0.,budget)*(1-g.cfg['cash_buffer'])/plan['limit']/100)*100
            while qty>=100 and qty*plan['limit']+estimated_order_fee('buy',qty*plan['limit'])>cash_cap+1e-8:qty-=100
            if qty<100:continue
            g.attempted_windows.add((clock,stock))
            reason='尾盘首轮未完成计划限价买入' if late else ('洗盘独立09:45限价买入' if clock==g.cfg['wash_buy_start_time'] else '首轮允许区间限价买入')
            try:send_order(context,stock,'buy',qty,reason,q,plan['combo'])
            except Exception as exc:audit('BUY_DATA_ERROR',stock=stock,error=str(exc))


def opening_session(context):
    clock = context.current_dt.strftime('%H:%M')
    if clock not in execution_sessions(): return
    if g.day != str(context.current_dt.date()): prepare_day(context)
    if clock in g.opening_ticks: return
    g.opening_ticks.add(clock)
    if clock != '14:55' or py_any(breakout_window_allowed(context,p) for p in getattr(g,'deferred_breakouts',{}).values()):
        log_section('交易窗口 ' + clock)
    if clock != '14:55' or py_any(breakout_window_allowed(context,p) for p in getattr(g,'deferred_breakouts',{}).values()):
        log_capacity(context, '窗口开始')
    started = time.perf_counter()
    try:
        refresh_all_exit_exemptions(context)
        sync_orders(context); cancel_expired(context); cancel_unsafe_supplemental_buys(context)
        manage_positions(context)
        risk_monitor(context); reduce_exposure(context)
        if clock == '14:55': acceleration_session(context)
        sync_orders(context)
        deferred_breakout_session(context)
        buy_candidates(context)
    except Exception as exc:
        halt_new_buys(context, 'OPENING_ERROR'); audit('OPENING_ERROR', error=str(exc))
    finally: audit('PROFILE', stage='opening_' + clock, seconds=time.perf_counter() - started)

def buy_session(context):
    # Compatibility wrapper for the previous version's test/interface name.
    opening_session(context)

def cancel_opening_buys(context):
    clock = context.current_dt.strftime('%H:%M')
    if clock not in buy_cancel_times(): return
    if not hasattr(g, 'buy_cancel_windows'): g.buy_cancel_windows = set()
    if clock in g.buy_cancel_windows: return
    g.buy_cancel_windows.add(clock)
    for oid, intent in list(g.orders.items()):
        if intent['side'] == 'buy' and not intent['terminal'] and clock >= intent.get('expires_at',clock):
            request_cancel(context, oid, clock + '独立买入窗口结束')
    sync_orders(context)
    expire_deferred_breakouts(context)

def handle_data(context,data):
    clock=context.current_dt.strftime('%H:%M')
    if clock=='09:30':
        opening_exit_session(context);return
    if clock in execution_sessions():
        opening_session(context);return
    if g.day!=str(context.current_dt.date()):prepare_day(context)
    if not trading_minute(context):
        # Observe/cancel stale exits through the close; never create new trades here.
        if '09:30' <= clock <= '15:00': refresh_all_exit_exemptions(context)
        return
    started=time.perf_counter()
    try:
        refresh_all_exit_exemptions(context)
        if py_any(not o['terminal'] for o in g.orders.values()):
            sync_orders(context);cancel_expired(context);cancel_unsafe_supplemental_buys(context)
        cancel_opening_buys(context)
        expire_deferred_breakouts(context)
        risk_monitor(context)
        if monitoring_due(context):manage_positions(context)
        acceleration_session(context)
        reduce_exposure(context)
        if clock=='14:56':
            cancel_expired(context,all_orders=True);expire_deferred_breakouts(context)
    except Exception as e:
        halt_new_buys(context,'ENGINE_ERROR');audit('ENGINE_ERROR',error=str(e),action='禁止新买，后续分钟继续管理持仓')
    finally:
        profile_add('intraday_seconds',time.perf_counter()-started);profile_add('minute_callbacks',1)

def finish_day(context):
    sync_orders(context)
    expire_deferred_breakouts(context)
    ok=reconcile_positions(context,'日末')
    mark_entry_day_observation(context)
    record_close_exit_observations(context)
    record_washout_close_state(context)
    record_breakout_close_observations(context)
    snapshot_position_metadata()
    log_holdings(context,show_exits=False)
    log_section('日末账户与成交汇总')
    log_capacity(context,'日末')
    trades=get_trades();buy_qty=sell_qty=buy_value=sell_value=0;matched=0
    for tid,t in trades.items():
        intent=g.orders.get(str(t.order_id))
        if not intent:continue
        qty=py_abs(int(t.amount));value=qty*float(t.price);matched+=1
        if intent['side']=='buy':buy_qty+=qty;buy_value+=value
        else:sell_qty+=qty;sell_value+=value
    fees=py_sum(float(v) for v in g.fee_seen.values() if v is not None)
    log.info('【当日实际成交】平台Trade回报%d笔 | 可关联本策略%d笔 | 买入%d股/%.2f元 | 卖出%d股/%.2f元 | 已读订单费用%.2f元 | 未结束平台订单%d笔 | 持仓对账:%s' %
             (len(trades),matched,buy_qty,buy_value,sell_qty,sell_value,fees,len(get_open_orders()),'一致' if ok else '异常'))
    audit('PROFILE_DAY',counters=dict(getattr(g,'profile',{})),note='仅回调耗时，不等于平台总耗时')
    for s,b in g.book.items():audit('POSITION_STATE',stock=s,state=b)
    audit('DAY_END',day=g.day,nav=context.portfolio.total_value,cash=context.portfolio.available_cash,
          exposure=context.portfolio.positions_value,risk_ratio=g.position_ratio,halted=g.halted,
          halt_reasons=getattr(g,'halt_reasons',{}),actual_fills=len(g.seen_trades),open_orders=len(get_open_orders()),
          note='依实际成交记账；日结自动撤单在次日重新核销')
    record(risk_ratio=g.position_ratio,exposure_ratio=context.portfolio.positions_value/context.portfolio.total_value)
    # Only the reconstructible selection DataFrames are discarded, after all accounting.
    # Never clear book, orders, archives, candidates, open_plan or accounting state here.
    if g.cfg.get('performance_optimizations', True):
        cached_frames = len(getattr(g, '_micro_data_cache', {}))
        g._micro_data_cache = {}
        log.info('【日末缓存清理】已释放%d份可重建选股指标表；真实持仓、订单和元数据保留' % cached_frames)

def halt_new_buys(context, reason, key='account', recoverable=False, **details):
    if not hasattr(g,'halt_reasons'):g.halt_reasons={}
    token=reason+':'+str(key)
    if token not in g.halt_reasons:
        g.halt_reasons[token]=dict(reason=reason,key=str(key),since=str(context.current_dt),recoverable=recoverable)
        audit('HALT_SET',token=token,details=details,**g.halt_reasons[token])
    g.halted=True

def clear_halt(context, reason, key='account', evidence=''):
    token=reason+':'+str(key)
    if token in getattr(g,'halt_reasons',{}):
        old=g.halt_reasons.pop(token)
        audit('HALT_CLEARED',token=token,since=old['since'],evidence=evidence)
        g.halted=bool(g.halt_reasons)

def position_snapshot(context, stock, p, force=False):
    raw={name:getattr(p,name,None) for name in
         ('total_amount','locked_amount','closeable_amount','today_amount','price','value')}
    raw['accounted_qty']=total_qty(p);raw['ledger_qty']=g.book.get(stock,{}).get('qty',0)
    state=tuple(raw.values())
    if not hasattr(g,'position_snapshots'):g.position_snapshots={}
    # Intraday only log quantity/lock changes, not every tick's mark-to-market price.
    signature=state[:4]+(raw['accounted_qty'],raw['ledger_qty'])
    if force or g.position_snapshots.get(stock)!=signature:
        audit('POSITION_RAW',stock=stock,mode=g.cfg['position_quantity_mode'],fields=raw)
        g.position_snapshots[stock]=signature

def reconcile_positions(context, stage):
    restore_position_metadata(context,stage)
    mismatches=[]
    positions=context.portfolio.positions
    for s in sorted(set(positions)|set(g.book)):
        p=positions.get(s);actual=total_qty(p) if p is not None else 0
        expected=int(g.book.get(s,{}).get('qty',0))
        if p is not None:position_snapshot(context,s,p,force=True)
        if actual!=expected:
            mismatches.append(s)
            halt_new_buys(context,'POSITION_MISMATCH',s,True,actual=actual,expected=expected,stage=stage)
            audit('RECONCILE_ERROR',stock=s,ledger=expected,platform=actual,stage=stage)
        else:
            g.basis_blocked.discard(s)
    pending=py_any(not o['terminal'] for o in g.orders.values())
    opened=get_open_orders()
    # Recovery requires an independent fresh position read AND no unsettled orders.
    if not mismatches and not pending and not opened:
        for token,record in list(getattr(g,'halt_reasons',{}).items()):
            if record['reason']=='POSITION_MISMATCH':
                clear_halt(context,record['reason'],record['key'],'全部持仓与成交账本一致且无待结订单')
        for oid,old in list(getattr(g,'rollover_pending',{}).items()):
            if old['seen_qty']<old.get('reported_filled',0):continue
            audit('ROLLOVER_RECONCILED',order_id=oid,stock=old['stock'],seen_qty=old['seen_qty'],
                  evidence='新交易日无活动订单，持仓与成交账本一致；不伪造昨日撤单回报')
            clear_halt(context,'DAY_ROLLOVER',oid,'日切后无活动订单且股数完整对账')
            clear_halt(context,'ORDER_MISSING',oid,'日切后无活动订单且股数完整对账')
            clear_halt(context,'CANCEL_UNCONFIRMED',oid,'日切后无活动订单且股数完整对账')
            del g.rollover_pending[oid]
    if not mismatches:audit('RECONCILE_OK',stage=stage,positions=len(g.book),halted=g.halted)
    return not mismatches

def rollover_orders(context):
    if not getattr(g,'day',None):return
    if g.day==str(context.current_dt.date()):return
    # Preserve evidence before today's order namespace replaces yesterday's namespace.
    if not hasattr(g,'rollover_pending'):g.rollover_pending={}
    for oid,o in g.orders.items():
        if not o['terminal']:
            g.rollover_pending[oid]=dict(o)
            halt_new_buys(context,'DAY_ROLLOVER',oid,True,stock=o['stock'],reported=o.get('reported_filled',0),seen=o['seen_qty'])
    audit('ORDER_DAY_ARCHIVE',day=g.day,orders=len(g.orders),unsettled=len(g.rollover_pending))

def preserve_limit_queue(context, oid, intent):
    if intent['side']!='sell' or intent.get('style')!='limit':return False
    cd=get_current_data()[intent['stock']]
    price=float(cd.last_price);low=float(cd.low_limit)
    keep=np.isfinite(price) and low>0 and price<=low+.005 and py_abs(intent['limit']-low)<=.005
    if keep and not intent.get('limit_queue_logged'):
        audit('LIMIT_DOWN_QUEUE_HELD',order_id=oid,stock=intent['stock'],limit=intent['limit'],price=price)
        intent['limit_queue_logged']=True
    if not keep:intent['limit_queue_logged']=False
    return keep

def request_cancel(context, oid, reason):
    intent=g.orders[oid]
    if intent['terminal']:return False
    last=intent.get('cancel_last_at')
    if last and context.current_dt-last<dt.timedelta(minutes=g.cfg.get('cancel_retry_minutes',1)):return False
    attempts=intent.get('cancel_attempts',0)
    if attempts>=g.cfg.get('cancel_max_attempts',3):
        halt_new_buys(context,'CANCEL_UNCONFIRMED',oid,True,attempts=attempts)
        return False
    live={str(k):v for k,v in get_orders().items()}
    native=live.get(oid)
    intent['cancel_last_at']=context.current_dt;intent['cancel_attempts']=attempts+1
    if native is None:
        audit('CANCEL_LOOKUP_MISS',order_id=oid,attempt=attempts+1,reason=reason)
        return False
    if str(native.status).split('.')[-1] in ('held','canceled','rejected'):
        # A terminal Order may precede its Trades; sync_orders still consumes all fills.
        return False
    try:
        result=cancel_order(native)  # native platform Order, never our normalized string key
        audit('CANCEL_RESULT',order_id=oid,native_id_type=type(native.order_id).__name__,
              attempt=attempts+1,reason=reason,returned=result is not None,
              returned_status=str(getattr(result,'status',None)),
              note='接口返回不等于最终撤成，仍按Order和Trade确认')
    except Exception as e:
        audit('CANCEL_ERROR',order_id=oid,attempt=attempts+1,error=str(e))
    return True

def add_clock(clock, minutes):
    return (dt.datetime.strptime(clock,'%H:%M')+dt.timedelta(minutes=minutes)).strftime('%H:%M')

def entry_start():
    return g.cfg.get('buy_start_time',g.cfg.get('buy_time','09:30'))

def exit_start():
    return g.cfg.get('sell_start_time','09:30')

def entry_sessions():
    windows=[entry_start(),g.cfg['late_buy_time']]
    if combo_is_enabled('combo_2'):windows.append(g.cfg['wash_buy_start_time'])
    return sorted(set(windows))


def execution_sessions():
    return sorted(set(entry_sessions()+['14:55']))

def validate_execution_times():
    if g.cfg.get('capacity_mode','total_cap_only') not in ('total_cap_only','legacy_scaled','fixed_slots_scaled_unit'):
        raise ValueError('capacity_mode仅允许total_cap_only、legacy_scaled或fixed_slots_scaled_unit')
    def valid_clock(value):
        try:return dt.datetime.strptime(value,'%H:%M').strftime('%H:%M')==value
        except Exception:return False
    for key in ('max_count','selection_count'):
        value=g.cfg.get(key)
        if isinstance(value,bool) or not isinstance(value,int) or value<=0: raise ValueError(key+'须为正整数')
    unit_budget_divisor()  # validate the independent budget denominator too
    wash=g.cfg.get('wash_buy_start_time','')
    buy=entry_start();atr=exit_start();late=g.cfg.get('late_buy_time','')
    if not valid_clock(wash) or not '09:30'<=wash<buy: raise ValueError('洗盘独立买点须在09:30之后且早于普通首轮')
    if not valid_clock(buy) or not ('09:30'<=buy<='11:29' or '13:02'<=buy<='14:54'):
        raise ValueError('buy_start_time须为有效交易时刻HH:MM，上午09:30—11:29或下午13:02—14:54')
    if not valid_clock(atr) or not ('09:30'<=atr<='11:30' or '13:02'<=atr<='14:55'):
        raise ValueError('sell_start_time是ATR开始时间，须为09:30—11:30或13:02—14:55的HH:MM')
    if not valid_clock(late) or not '13:02'<=late<='14:55':
        raise ValueError('late_buy_time须为13:02—14:55的HH:MM')
    if buy>=late:raise ValueError('普通首轮买入时间必须早于尾盘买入时间')
    # ATR start is independent of buy windows. It never creates a buy callback.
    g.cfg['buy_time']=buy
    g.cfg['buy_cancel_time']=buy_cancel_times()[-1]


def log_section(title):
    try:log.info('========== '+str(title).replace('\n',' ').replace('\r','')+' ==========')
    except Exception:pass

def stock_label(stock):
    if not hasattr(g,'display_names'):g.display_names={}
    if stock not in g.display_names:
        try:g.display_names[stock]=str(get_current_data()[stock].name)
        except Exception:g.display_names[stock]='名称暂缺'
    return str(stock)+'('+g.display_names[stock]+')'

def log_capacity(context, stage):
    try:_log_capacity_impl(context,stage)
    except Exception as exc:
        try:log.warning('【仓位展示不可用】'+str(exc)+'；不得据缺失字段编造可买名额')
        except Exception:pass

def _log_capacity_impl(context, stage):
    p = capacity_snapshot(context)
    log.info('【仓位/%s】配置上限%d只/单笔分母%d | 微观系数%.2f%%/单股标准预算比例%.2f%%/总敞口上限%.2f%% | 当前名额%d只 | 实际持仓%d只 | 未成交买单新增占位%d只 | 剩余名额%d只' %
             (stage, p['n'], p['unit_divisor'], p['micro_ratio']*100, p['ratio']/p['unit_divisor']*100, p['exposure_target']*100, p['slots'], len(p['actual']), len(p['pending']-p['actual']), p['free']))
    if p['deferred_stocks']:
        log.info('【突破预留占用】%d个名额/当前有效预算%.2f元；这是计划预留，不是持仓或已委托订单' % (len(p['deferred_stocks']),p['deferred_cash']))
    log.info('【资金】净值%.2f | 持仓市值%.2f(%.2f%%) | 可用现金%.2f | 单笔预算上限%.2f（取整/缓冲前） | 停买:%s' %
             (p['nav'], p['value'], p['value']/p['nav']*100 if p['nav'] else 0, context.portfolio.available_cash, p['budget'], g.halted))
    log.info('【新增条件】有剩余名额:%s | 有卖出计划可能腾仓:%s | 有名额或卖出计划:%s | 有资金预算:%s | 信号状态:%s | 当前买入检查点:%s' %
             (p['free']>0, p['planned'], p['room_or_exit'], p['budget']>0, getattr(g, 'selection_status', '未评估'), context.current_dt.strftime('%H:%M') in entry_sessions()))

def _human_audit_core(event,p):
    side={'buy':'买入','sell':'卖出'}.get(p.get('side'),p.get('side',''))
    stock=stock_label(p['stock']) if p.get('stock') else ''
    if event=='LOCAL_BUY_PLAN':
        log.info('【买入计划/尚未委托】%s | 开盘基准%.3f | 昨收%s | 允许买入区间[%s,%.2f] | 买入资金名额满足:%s' % (stock,p['reference'],p.get('previous_close'),p.get('lower_limit'),p['limit'],p['initial_cash_and_slot']))
    elif event=='LOCAL_SELL_PLAN':log.info('【卖出计划/尚未委托】%s | %s' % (stock,p['reason']))
    elif event=='ORDER_INTENT':
        log.info('【准备委托】%s %s %s股 | %s | 限价:%s | 原因:%s' % (side,stock,p['qty'],'市价单' if p['order_style']=='market' else '限价单',p.get('limit'),p['reason']))
    elif event=='ORDER_ACCEPTED':log.info('【平台已返回订单/须核对状态】%s %s %s股 | 订单%s（可能立即取消，成交以Trade为准）' % (side,stock,p['qty'],p['order_id']))
    elif event=='FILL':
        deviation=p.get('fill_minus_reference_bps')
        log.info('【实际成交】%s %s %s股 × %.3f | 成交时间%s | Trade=%s | Order=%s | 报价基准%s(%s) | 相对报价%s | 原因:%s' %
                 (side,stock,p['qty'],p['price'],p['time'],p['trade_id'],p['order_id'],p.get('reference_price'),p.get('reference_source'),('%.3f%%'%(deviation/100)) if deviation is not None else '无',p['reason']))
        if p.get('side')=='buy' and p['stock'] in g.book:
            b=g.book[p['stock']]
            log.info('【成交后初始化】%s | 入场形态:%s | 入场ATR线%.3f（首日不执行） | 首次成交ATR倍数%s | 入场高点%.3f | 固定百分比止盈:未启用' %
                     (stock,b.get('combo',{}).get('combo_name','入场记录缺失'),b['stop'],b.get('atr_initial_multiplier','未记录'),b['high']))
    elif event=='ORDER_STATE':log.info('【订单状态】%s | Order=%s | 平台状态%s | 平台已成交%s股/账本已核对%s股 | 核对终结:%s' % (stock,p['order_id'],p['status'],p['filled'],p['reconciled'],p['terminal']))
    elif event=='POSITION_CLOSED':log.info('【持仓已平】%s | 买入金额%.2f | 卖出金额%.2f | 毛现金差额%.2f（未计费用/分红，不称净收益）' % (stock,p['buy_value'],p['sell_value'],p['gross_cash_difference']))
    elif event=='CONCEPT_POOL':log.info('【概念池】历史日期%s | 昨日涨停家数:%s（基础池口径） | 昨日涨停概念:%s | 今日竞价概念:%s | 合并:%s' % (p['asof'],p.get('limit_up_count','未返回'),p['previous'],p['auction'],p['pool']))
    elif event=='PREPARED':log.info('【盘前完成】日线截至%s | 入围%d只 | 仓位系数%.2f%%' % (p['daily_asof'],p['candidates'],p['risk_ratio']*100))
    elif event=='SIGNAL_FUNNEL':log.info('【筛选诊断汇总】'+readable_fields(p))
    elif event=='PROFILE':
        if p.get('stage')=='prepare':log.info('【盘前耗时】%.3f秒（回调耗时）'%p['seconds'])
    elif event=='EXIT_DEFERRED':log.warning('【退出待执行】%s | %s | %s；退出意图保留' % (stock,p['reason'],p['cause']))
    elif event=='LIMIT_DOWN_QUEUE_HELD':log.info('【跌停排队保留】%s | 订单%s | 限价%s' % (stock,p['order_id'],p['limit']))
    elif event in ('BUY_WAIT_CAPACITY','BUY_WAIT_CASH','BUY_ABANDON_WEAK','BUY_ABANDON_CHASE','BUY_PLAN_BLOCKED','BUY_BLOCKED_PLAN','BUY_PLAN_SKIP','BUY_SKIP','OPEN_QUOTE_BLOCKED','ORDER_REJECTED','SELL_TIME_GATE'):
        log.info('【未下单/'+event+'】'+readable_fields(p))
    elif event in ('HALT_SET','HALT_CLEARED','RISK_CAP_CHANGE','CANCEL_RESULT','ROLLOVER_RECONCILED'):
        log.info('【状态变化/'+event+'】'+readable_fields(p))

def log_holdings(context,show_exits=True):
    try:_log_holdings_impl(context,show_exits)
    except Exception as exc:
        try:log.warning('【持仓展示不可用】'+str(exc)+'；请核验平台持仓导出')
        except Exception:pass

def _log_holdings_impl(context,show_exits=True):
    log_section('实际持仓与有效退出规则' if show_exits else '实际持仓')
    count=0
    for s,p in context.portfolio.positions.items():
        qty=total_qty(p)
        if qty<=0:continue
        count+=1;b=g.book.get(s)
        cost=float(getattr(p,'avg_cost',float('nan')));price=float(getattr(p,'price',float('nan')))
        value=float(getattr(p,'value',float('nan')))
        gain=(price/cost-1)*100 if np.isfinite(cost) and cost>0 and np.isfinite(price) else None
        combo=b.get('combo',{}) if b else {};typename=main_shape_display_name(combo,'入场形态缺失/需核对')
        age=holding_days(context,b['entry_date']) if b else None
        state='强趋势' if b and b.get('strong_trend') else ('次日修复观察' if b and observation_atr_exempt(context,b) else '普通')
        log.info('【实际持仓】%s | 入场形态:%s | 状态:%s | 持有交易日:%s | 总股数%d/可卖%s/冻结%s | 平台成本%s/现价%s | 浮盈亏%s | 市值%.2f' %
                 (stock_label(s),typename,state,age,qty,getattr(p,'closeable_amount','缺失'),getattr(p,'locked_amount','缺失'),
                  '%.3f'%cost if np.isfinite(cost) else '缺失','%.3f'%price if np.isfinite(price) else '缺失',
                  '%.2f%%'%gain if gain is not None else '不可计算',value))
        if not show_exits or not b:continue
        if not exit_monitor_eligible(context,s,b):
            log.info('【首日持仓保护】%s | 仅参与概念炸板计数，不生成自身卖出/不追踪盘中ATR；日末记录收盘浮盈/对应形态观察，并检查首日跌5%%观察信号 | 入场ATR线%.3f仅存档' %(s,b['stop']))
            continue
        if b.get('strong_trend'):
            log.info('【有效退出】%s | 强趋势自%s永久标记至清仓 | 豁免所有普通退出和指数/概念/下午大跌 | 开板豁免日不执行；其余仅14:54七条件（含现价<=临时MA10×0.97或<=临时MA20×0.985）：跌昨收>7%%、距日高>9%%、振幅>12%%且现<开×0.975且现<昨收、收盘高点回撤>13%%、连跌>=4日且复合跌>8.5%% | 待退出:%s' %
                     (s,b.get('strong_mark_date'),b.get('exit_reason') or '无'))
            continue
        plan=b.get('close_exit_plan')
        if plan:log.info('【收盘退出计划】%s | 信号日%s | %s | 依实际成交完成退出' % (s,plan['signal_date'],plan['reason']))
        stop=float(b['stop']);atr=g.atr.get(s)
        stop_cost=(stop/cost-1)*100 if np.isfinite(cost) and cost>0 else None
        distance=(price-stop)/price*100 if np.isfinite(price) and price>0 else None
        atr_state='次日观察豁免（恢复日当天仍豁免）' if observation_atr_exempt(context,b) else '按允许时间生效'
        log.info('【有效退出】%s | 今日适用ATR%d×%.2f:%s | 今日ATR:%s | 已记录跟踪线%.3f/相对成本%s/现价距线%s | 待退出:%s | 超过%d交易日且昨收未涨停到期 | 低开6%%/14:30跌8.5%%/概念/普通加速有效；指数减仓:%s；主升前三日前收/洗盘次日MA10/突破D3-D4及第7和第8日收盘浮盈另判；标准/突破/主升浪另有14:54 MA破位退出，突破豁免14:55加速' %
                 (s,g.cfg['atr_n'],position_atr_multiplier(context,b),atr_state,'%.4f'%atr if atr is not None else '尚未计算',stop,
                  '%.2f%%'%stop_cost if stop_cost is not None else '不可计算','%.2f%%'%distance if distance is not None else '不可计算',
                  b.get('exit_reason') or '无',g.cfg['max_hold'],'洗盘豁免（买入仍受风险上限）' if combo.get('combo_type')=='combo_2' else '生效'))
    if count==0:log.info('【实际持仓】空仓')

def breakout_economic_factor_values(frame):
    """Five T-1 factors, from the existing frozen frame only; no data requests."""
    row = frame.iloc[-1]
    def number(key):
        try:
            value = float(row.get(key))
            return value if np.isfinite(value) else float('nan')
        except (TypeError, ValueError):
            return float('nan')
    c, o, h, l = [number(key) for key in ('close', 'open', 'high', 'low')]
    ma5, ma10, ma20, ma60 = [number(key) for key in ('ma5', 'ma10', 'ma20', 'ma60')]
    volume, vma5 = number('volume'), number('volume_ma5')
    upper = ((h - py_max(o, c)) / (h - l + .0001)
             if py_all(np.isfinite(v) for v in (c, o, h, l)) and h >= py_max(o, c, l) else float('nan'))
    extension = c / ma20 - 1. if np.isfinite(c) and np.isfinite(ma20) and ma20 > 0 else float('nan')
    drawdown = float('nan')
    try:
        closes = frame['close'].iloc[-31:].astype(float).values
        if len(closes) == 31 and bool(np.isfinite(closes).all()) and bool((closes > 0).all()):
            drawdown = float(np.max(1. - closes / np.maximum.accumulate(closes)))
    except (KeyError, TypeError, ValueError):
        pass
    volume_ratio = volume / (vma5 + .0001) if np.isfinite(volume) and np.isfinite(vma5) and vma5 > 0 else float('nan')
    mas = np.array([ma5, ma10, ma20, ma60], dtype=float)
    convergence = float(np.std(mas, ddof=1) / (np.mean(mas) + .0001)) if bool(np.isfinite(mas).all()) and bool((mas > 0).all()) else float('nan')
    return dict(upper_shadow=upper, ma20_extension=extension, left30_drawdown=drawdown,
                volume_over_vma5=volume_ratio, ma4_convergence=convergence)



def compact_log_text(value):
    """只格式化观察文字；等义符号避HTML转义，禁止用于决策计算。"""
    import html
    import re
    text = html.unescape(str(value)).replace('"','').replace("'",'')
    text = text.replace('>=','≥').replace('<=','≤').replace('>','＞').replace('<','＜')
    text = re.sub(r'(?<![\w.])-?\d+\.\d{10,}(?:[eE][+-]?\d+)?',
                  lambda match: format(float(match.group()), '.10g'), text)
    return text.replace('\n',' ').replace('\r',' ')


def compact_log_value(value):
    """明文字典：无JSON引号；仅显示，缺失不伪装为0。"""
    if value is None: return '缺失'
    if isinstance(value, (bool, np.bool_)): return str(bool(value))
    if isinstance(value, (int, np.integer)): return str(int(value))
    if isinstance(value, (float, np.floating)):
        return format(float(value), '.10g') if np.isfinite(value) else '缺失'
    if isinstance(value, dict):
        return '{' + ', '.join(compact_log_text(k)+':'+compact_log_value(v) for k,v in value.items()) + '}'
    if isinstance(value, (tuple,list)):
        return '[' + ', '.join(compact_log_value(v) for v in value) + ']'
    return compact_log_text(value)


def compact_economic_terms(item, evidence, definitions):
    """复用正式排序生成的分项；不重算百分位、不改候选状态。"""
    raw=evidence.get('raw_inputs', {})
    parts=[]
    for index, (key, label, raw_key, direction, weight) in enumerate(definitions,1):
        value=raw.get(raw_key)
        if key == 'negative_open_provisional_ma5_distance':
            value=py_abs(value) if value is not None else None
        elif key == 'negative_slope5_sum_absolute':
            value=py_abs(value) if value is not None else None
        points=item.get('tie_weighted_points',{}).get(key)
        percentile=item.get('tie_percentiles',{}).get(key)
        parts.append('%d.%s=%s（%s；权重%s%%；百分位%s；贡献%s分）' %
            (index,label,compact_log_value(value),direction,compact_log_value(weight*100),
             compact_log_value(percentile),compact_log_value(points)))
    return '；'.join(parts)



def log_breakout_economic_score(item):
    if item.get('combo_type') != 'combo_3': return
    evidence=item.get('breakout_economic',{})
    labels={'upper_shadow':'(H−max(O,C))/(H−L+0.0001)', 'ma20_extension':'C/MA20−1',
            'left30_drawdown':'左30次收盘变化最大回撤', 'volume_over_vma5':'V/(VMA5+0.0001)',
            'ma4_convergence':'std(MA5,10,20,60;ddof=1)/(四MA均值+0.0001)'}
    parts=[]
    for index,key in enumerate(evidence.get('factor_order',[]),1):
        percentile=evidence.get('percentile',{}).get(key,0.)
        points=evidence.get('contributions',{}).get(key,percentile*20.)
        parts.append('%d.%s=%s（%s；权重20%%；百分位%s；贡献%s分）' %
            (index,labels.get(key,key),compact_log_value(evidence.get('raw',{}).get(key)),
             '越大越优' if key=='volume_over_vma5' else '越小越优',compact_log_value(percentile),compact_log_value(points)))
    log.info(compact_log_text('【突破五项次分】%s | 原分%s优先/同原分组%d只 | %s | 合计%s分；同分依1→5再代码' %
        (stock_label(item['stock']),compact_log_value(item.get('score')),evidence.get('group_size',0),'；'.join(parts),compact_log_value(item.get('tie_score')))))


def _v50_rank_same_score(items, frame_cache):
    groups = {}
    wash_scope = washout_rank_scope() if py_any(item['combo_type'] == 'combo_2' for item in items) else None
    for item in items:
        item['tie_score'] = 0.0
        unified = item['combo_type'] in ('combo_4','combo_6') or (item['combo_type'] == 'combo_2' and wash_scope == 'all_qualified')
        score_group = None if unified else item['score']
        groups.setdefault((item['combo_type'], item['priority'], score_group), []).append(item)
    old_names = ('upper_shadow', 'negative_open_target_03_distance', 'negative_ma5_target_005_distance',
                 'volume_ma5_over_ma20', 'macd_over_close')
    for key, group in groups.items():
        matrix = []
        is_wash = key[0] == 'combo_2'
        is_main = key[0] == 'combo_4'
        is_breakout = key[0] == 'combo_3'
        for item in group:
            frame = frame_cache[item['stock']]
            row = frame.iloc[-1]
            if is_wash:
                evidence = washout_economic_evidence(item, frame, getattr(g, 'asof', None))
                names, weights = tuple(evidence['names']), tuple(evidence['weights'])
                finite = [v if v is not None else float('nan') for v in evidence['vector']]
                item['washout_economic_evidence'] = evidence
                item['tie_weights'] = dict(zip(names, weights))
                item['tie_rank_context'] = dict(scope=wash_scope, group_size=len(group), primary_score_group=key[2],
                    percentile_method='average ascending rank / group_size; missing=0',
                    sort_order='priority → ' + ('economic' if wash_scope == 'all_qualified' else 'primary score → economic') + ' → raw four-vector → code')
            elif is_main:
                evidence = main_economic_evidence(item, frame, getattr(g, 'asof', None))
                names, weights = tuple(evidence['names']), tuple(evidence['weights'])
                finite = [v if v is not None else float('nan') for v in evidence['vector']]
                item['main_economic_evidence'] = evidence
                item['tie_weights'] = dict(zip(names, weights))
                item['tie_rank_context'] = dict(scope='all_qualified', group_size=len(group), primary_score_group=None,
                    percentile_method='average ascending rank / group_size; missing=0',
                    sort_order='priority → economic → raw five-vector → code; primary score is eligibility only')
            elif is_breakout:
                raw = breakout_economic_factor_values(frame)
                factor_order = ('upper_shadow','ma20_extension','left30_drawdown','volume_over_vma5','ma4_convergence')
                names = ('negative_upper_shadow','negative_ma20_extension','negative_left30_drawdown','volume_over_vma5','negative_ma4_convergence')
                weights = (.2,)*5
                values = [-raw['upper_shadow'],-raw['ma20_extension'],-raw['left30_drawdown'],raw['volume_over_vma5'],-raw['ma4_convergence']]
                finite = [py_round(v,12) if np.isfinite(v) else float('nan') for v in values]
                item['breakout_economic'] = dict(schema='breakout-economic/v0545',factor_order=list(factor_order),weights=list(weights),primary_score_priority=True,group_size=len(group),
                    raw={name:float(raw[name]) if np.isfinite(raw[name]) else None for name in factor_order},asof=str(frame.index[-1]),drawdown_observations=31,
                    basis='冻结日线截至昨日；同形态同原分组内平均秩；31收盘/30次变化；五项各20%',missing_policy='缺失贡献0；同分缺失置后；无新增硬剔除')
            else:
                names = old_names
                def ratio(a, b):
                    a = float(a); b = float(b)
                    return a / b if np.isfinite(a) and np.isfinite(b) and b > 0 else float('nan')
                values = [float(row['upper_shadow_ratio']), -py_abs(float(item['open_chg']) / 100. - .03),
                          -py_abs(ratio(row['close'], row['ma5']) - 1.005), ratio(row['volume_ma5'], row['volume_ma20']),
                          ratio(row['macd'], row['close'])]
                finite = [py_round(v, 12) if np.isfinite(v) else float('nan') for v in values]
            item['tie_features'] = dict(zip(names, [v if np.isfinite(v) else None for v in finite]))
            item['tie_raw_order'] = [v if np.isfinite(v) else None for v in finite]
            matrix.append(finite)
        percentile = pd.DataFrame(matrix).rank(method='average', ascending=True, na_option='keep').fillna(0) / len(group)
        scores = percentile.mul(list(weights), axis=1).sum(axis=1) * 100 if (is_wash or is_main) else percentile.mean(axis=1) * 100
        for i, item in enumerate(group):
            item['tie_score'] = float(scores.iloc[i])
            if is_breakout:
                item['breakout_economic']['percentile']=dict(zip(factor_order,[float(v) for v in percentile.iloc[i]]))
                item['breakout_economic']['contributions']=dict(zip(factor_order,[float(v)*20. for v in percentile.iloc[i]]))
            if is_wash or is_main:
                item['tie_percentiles'] = dict(zip(names, [float(v) for v in percentile.iloc[i]]))
                item['tie_average_ranks'] = dict(zip(names, [float(v * len(group)) for v in percentile.iloc[i]]))
                item['tie_weighted_points'] = dict(zip(names, [float(v * w * 100.) for v, w in zip(percentile.iloc[i], weights)]))
    def rank_key(item):
        vector = tuple(-v if v is not None else float('inf') for v in item['tie_raw_order'])
        unified = item['combo_type'] in ('combo_4','combo_6') or (item['combo_type'] == 'combo_2' and wash_scope == 'all_qualified')
        primary_order = 0.0 if unified else -item['score']
        return (item['priority'], primary_order, -py_round(item['tie_score'], 12), vector, item['stock'])
    items.sort(key=rank_key)
    return items


def is_atr_reason(reason):
    return reason=='ATR14跟踪止损'

def atr_enabled_now(context):
    return context.current_dt.strftime('%H:%M')>=exit_start()

def resolve_position_exit(context, stock, b, q, cd, age):
    if not exit_monitor_eligible(context, stock, b): return None
    refresh_exempt_exit_intents(context, stock, b)
    if b.get('strong_trend'):
        return b.get('exit_reason') if is_strong_exit_reason(b.get('exit_reason')) else None
    activate_close_exit_plan(context, stock, b)
    due = refresh_maturity_intent(context, stock, b, age); pending = b.get('exit_reason')
    hard = pending if pending and not is_atr_reason(pending) and not is_maturity_reason(pending) else None
    if not hard and due: hard = '持仓超过%d交易日且昨收未涨停退出' % g.cfg['max_hold']
    if stock not in g.open_checked_stocks and g.cfg['open_gap_exit']:
        if cd.day_open / previous_close(stock) - 1 <= -g.cfg['open_gap_drop'] + 1e-12: hard = hard or '开盘低开6%'
        g.open_checked_stocks.add(stock)
    if afternoon_trigger(context, stock, q['price']): hard = hard or '14:30后较昨收跌幅达到8.5%'
    if hard: return hard
    if observation_atr_exempt(context, b) or not atr_enabled_now(context): return None
    if is_atr_reason(pending): return pending
    return 'ATR14跟踪止损' if q['price'] <= b['stop'] else None

def supplemental_floor(plan):
    return plan.get('lower_limit')

def cancel_unsafe_supplemental_buys(context):
    pending = [(oid, intent) for oid, intent in g.orders.items() if intent['side'] == 'buy' and not intent['terminal']]
    if not pending: return
    current = get_current_data(); requested = False
    for oid, intent in pending:
        try:
            price = float(current[intent['stock']].last_price)
            floor, cap = intent.get('entry_floor'), intent.get('entry_limit')
            if intent.get('deferred_breakout'):
                invalid=not np.isfinite(price) or price<=0
                outside=invalid or (not intent.get('deferred_market') and (cap is None or price>cap+1e-10 or (floor is not None and price<floor-1e-10) or intent.get('floor_fill_breach',False)))
                if outside: requested=request_cancel(context,oid,'突破延迟买单专属价格失效') or requested
                continue
            invalid = not np.isfinite(price) or price <= 0 or floor is None or cap is None
            outside = invalid or price < floor - 1e-10 or price > cap + 1e-10 or intent.get('floor_fill_breach', False)
            if outside:
                audit('BUY_BAND_CANCEL', stock=intent['stock'], order_id=oid, price=price, floor=floor, limit=cap,
                      note='申请撤未成交余量；限价不能保证最低成交价，真实已成交不能撤回')
                requested = request_cancel(context, oid, '最新报价越过允许区间/行情不可核验') or requested
        except Exception as exc:
            audit('BUY_BAND_QUOTE_ERROR', order_id=oid, error=str(exc))
            requested = request_cancel(context, oid, '买单报价核验失败') or requested
    if requested: sync_orders(context)

def exit_monitor_eligible(context, stock, book=None):
    """Exit signals start on a later date than the first actual entry fill; no T+0 signals."""
    b = book if book is not None else g.book.get(stock)
    if not b or not b.get('entry_date'):
        return False
    return pd.Timestamp(b['entry_date']).date() < context.current_dt.date()

def snapshot_position_metadata():
    if not hasattr(g, 'position_archive'):
        g.position_archive = {}
    for stock, b in g.book.items():
        if int(b.get('qty', 0)) > 0:
            g.position_archive[stock] = copy.deepcopy(b)

def restore_position_metadata(context, stage):
    """Recover only an independently saved known lot; never invent entry age or pattern."""
    for stock, position in context.portfolio.positions.items():
        actual = total_qty(position)
        if actual <= 0 or stock in g.book:
            continue
        saved = getattr(g, 'position_archive', {}).get(stock)
        pending = active_order(stock)
        if (saved and int(saved.get('qty', 0)) == actual and not pending
                and py_all(k in saved for k in ('entry_date', 'entry_time', 'combo', 'high', 'stop', 'anchor_date', 'anchor_close'))):
            g.book[stock] = copy.deepcopy(saved)
            g.basis_blocked.add(stock)
            audit('POSITION_METADATA_RESTORED', stock=stock, qty=actual, stage=stage,
                  entry_date=saved['entry_date'], source='已确认成交/持仓元数据备份',
                  action='恢复身份，等待价格基准核查；未制造成交或重设买入日期')
        else:
            halt_new_buys(context, 'POSITION_MISMATCH', stock, True, actual=actual, expected=0, stage=stage)
            audit('POSITION_METADATA_MISSING', stock=stock, qty=actual, stage=stage,
                  action='平台持仓继续显示并计入仓位；证据不足不猜入场日期/形态，暂停新买并保留其余持仓管理')

def price_at_limit(price, limit):
    # A-share stock tick is 0.01 yuan. Half a tick tolerates floating representation, not one-tick gaps.
    return (np.isfinite(price) and np.isfinite(limit) and price > 0 and limit > 0
            and py_abs(float(price) - float(limit)) < .005)

def prior_limit_pattern(row):
    """Yesterday's unadjusted OHLC against yesterday's actual high_limit, not a 10% approximation."""
    vals = [float(row[k]) for k in ('open', 'high', 'low', 'close')]
    op, high, low, close = vals
    if not py_all(np.isfinite(x) and x > 0 for x in vals):
        raise ValueError('昨日OHLC缺失或非正')
    if (not np.isfinite(float(row['paused'])) or bool(row['paused'])
            or not np.isfinite(float(row['volume'])) or float(row['volume']) <= 0):
        raise ValueError('昨日停牌/无成交')
    if high < py_max(op, close, low) - 1e-6 or low > py_min(op, close, high) + 1e-6:
        raise ValueError('昨日OHLC次序异常')
    limit = float(row['high_limit'])
    if np.isposinf(limit):
        return None  # Exchange day without a finite upper limit is not a limit-board pattern.
    if not np.isfinite(limit) or limit <= 0 or high > limit + .005:
        raise ValueError('昨日涨停价缺失/与OHLC不一致')
    if py_all(price_at_limit(x, limit) for x in vals):
        return '昨日一字涨停'
    if (price_at_limit(op, limit) and price_at_limit(high, limit)
            and price_at_limit(close, limit) and low < limit - .005):
        return '昨日T字涨停'
    return None

def filter_prior_limit_patterns(stocks, asof):
    with selection_stage('board_evaluate'):
        prime_entry_filter_history(stocks, asof, adjusted=False)
        kept, rejected, missing = [], [], []
        for stock in stocks:
            try:
                raw = entry_filter_frame(stock, asof, adjusted=False)
                evidence = prior_pattern_evidence(raw, asof)
                if evidence['excluded']:
                    rejected.append(dict(stock=stock, **evidence))
                else:
                    kept.append(stock)
            except Exception as exc:
                missing.append(dict(stock=stock, reason=str(exc)))
        log.info('【趋势股-板型过滤】%d只 → %d只 | 近2日至少1次或近5日至少2次一字/T字涨停排除%d只/不可核验%d只 | 截至%s' %
                 (len(stocks), len(kept), len(rejected), len(missing), asof))
        audit('PRIOR_LIMIT_FILTER', asof=asof, price_basis='fq=None', before=len(stocks), after=len(kept),
              excluded=rejected, unverifiable=missing,
              rule='近2个交易日>=1次或近5个交易日>=2次涨停一字/T字；无法核验者不入选')
        return kept

def acceleration_history(stock):
    cached = getattr(g, 'accel_daily_cache', {}).get(stock)
    if cached is not None and cached['asof'] == str(g.asof): return dict(cached)
    prime_entry_filter_history([stock], g.asof, adjusted=False)
    prime_entry_filter_history([stock], g.asof, adjusted=True)
    evidence = acceleration_evidence(entry_filter_frame(stock, g.asof, False),
                                     entry_filter_frame(stock, g.asof, True), g.asof)
    if not hasattr(g, 'accel_daily_cache'): g.accel_daily_cache = {}
    g.accel_daily_cache[stock] = evidence
    return dict(evidence)

def acceleration_session(context):
    if not g.cfg.get('acceleration_exit') or context.current_dt.strftime('%H:%M')!='14:55':return
    day=str(context.current_dt.date())
    if getattr(g,'acceleration_checked_day',None)==day:return
    g.acceleration_checked_day=day
    sync_orders(context)
    # Usually called by manage_positions first; keep direct scheduled invocation safe.
    observation_tail_session(context)
    log_section('14:55 加速后走弱退出检查')
    current=get_current_data()
    for stock,book in list(g.book.items()):
        if not exit_monitor_eligible(context,stock,book) or stock in g.basis_blocked or book.get('strong_trend') or book.get('combo',{}).get('combo_type')=='combo_3':continue
        try:
            cd=current[stock]
            if cd.paused:continue
            price=float(cd.last_price);limit=float(cd.high_limit)
            if not np.isfinite(price) or price<=0 or np.isnan(limit) or limit<=0 or (np.isfinite(limit) and price>limit+.005):
                raise ValueError('14:55报价/涨停价不可核验')
            evidence=late_acceleration_evidence(stock)
            age=holding_days(context,book['entry_date'])
            current_return=price/previous_close(stock)-1
            touch=None; sealed=price_at_limit(price,limit)
            if not is_growth_board(stock) and not sealed:
                need_touch=(current_return>.09+1e-12 or
                    (evidence['c_available'] and evidence['yesterday_limit_up'] and evidence['r3']>.225+1e-12))
                if need_touch:
                    try: touch=observed_exact_limit_touch(context,stock,price,limit)
                    except Exception as exc: evidence=dict(evidence,errors=dict(evidence['errors'],TODAY_TOUCH=str(exc)))
                if current_return>.09+1e-12:
                    sealed=bool(touch) if touch is not None else None
            signals=late_acceleration_signals(stock,evidence,age,current_return,sealed,touch)
            for rule,error in evidence['errors'].items():
                log.warning('【尾盘加速数据异常】%s | 规则%s: %s；只跳过缺证据规则' %(stock_label(stock),rule,error))
            fmt=lambda v:'未知' if v is None else '%.2f%%'%(v*100)
            log.info('【尾盘加速检查】%s | 持有%d交易日 | 昨封%s/N2=%s/R1=%s/R2=%s/R3=%s/昨高涨幅=%s | 当前涨幅%s/加速专用封板或近封%s | A=%s/B=%s/C=%s/今日触板=%s' %
                     (stock_label(stock),age,evidence['yesterday_limit_up'],evidence['n2'],fmt(evidence['r1']),fmt(evidence['r2']),fmt(evidence['r3']),fmt(evidence['h1']),
                      fmt(current_return),sealed,signals['A'],signals['B'],signals['C'],touch))
            labels='/'.join(k for k in ('A','B','C') if signals[k] is True)
            if not labels:continue
            reason='14:55加速后走弱退出:'+labels
            if not book.get('exit_reason') or is_atr_reason(book['exit_reason']):book['exit_reason']=reason
            q=dict(price=price,high=price,time=context.current_dt,source='current_data_14:55',observed_at=context.current_dt)
            send_order(context,stock,'sell',book['qty'],book['exit_reason'],q)
        except Exception as exc:audit('ACCELERATION_DATA_ERROR',stock=stock,error=str(exc),action='跳过缺证据规则；真实持仓/其他退出继续')
    snapshot_position_metadata()

def observe_concept_touch(context,stock,q,cd):
    """Observe today's board history for concept counting only; never modify the ATR ledger."""
    try:
        clock=context.current_dt.strftime('%H:%M')
        if clock not in ('09:30','09:31'):
            if not hasattr(g,'touch_until'):g.touch_until={}
            cutoff=context.current_dt-dt.timedelta(minutes=1)
            begin=g.touch_until.get(stock,pd.Timestamp(g.day+' 09:30:00').to_pydatetime())
            if stock not in g.touched and begin<=cutoff:
                h=get_price(stock,start_date=begin,end_date=cutoff,frequency='1m',fields=['high'],fq='pre')
                if h is not None and not h.empty:
                    if not isinstance(h.index,pd.DatetimeIndex) or h.index.has_duplicates:
                        raise ValueError('概念触板分钟索引异常')
                    if h.index.min()<pd.Timestamp(begin) or h.index.max()>pd.Timestamp(cutoff):
                        raise ValueError('概念触板分钟数据超出已完成区间')
                    highs=pd.to_numeric(h['high'],errors='coerce')
                    if not py_all(np.isfinite(float(v)) and float(v)>0 for v in highs):
                        raise ValueError('概念触板价格异常')
                    if float(highs.max())>=cd.high_limit*.998:g.touched.add(stock)
                    g.touch_until[stock]=h.index.max().to_pydatetime()+dt.timedelta(minutes=1)
        if q['high']>=cd.high_limit*.998:g.touched.add(stock)
        return True
    except Exception as exc:
        audit('CONCEPT_EXIT_DATA_ERROR',stock=stock,error=str(exc),action='本次不计该股概念信号；ATR与其他有效持仓管理继续')
        return False

def apply_concept_breaks(context, quotes, cd):
    broken = defaultdict(set); memberships = {}
    for stock, q in quotes.items():
        try:
            memberships[stock] = set(concepts(stock))
            if stock in g.touched and q['price'] < cd[stock].high_limit * .995:
                for concept in memberships[stock]: broken[concept].add(stock)
        except Exception as exc: audit('CONCEPT_EXIT_DATA_ERROR', stock=stock, error=str(exc))
    for concept, stocks in sorted(broken.items()):
        if len(stocks) < 3: continue
        targets = []; protected = []; strong_protected = []
        for stock in sorted(quotes):
            if concept not in memberships.get(stock, set()) or stock not in g.book: continue
            b = g.book[stock]
            if b.get('strong_trend'):
                strong_protected.append(stock); continue
            if not exit_monitor_eligible(context, stock, b):
                protected.append(stock); continue
            targets.append(stock)
            if not b['exit_reason'] or is_atr_reason(b['exit_reason']): b['exit_reason'] = '概念炸板:' + concept
            send_order(context, stock, 'sell', b['qty'], b['exit_reason'], quotes[stock])
        flag = ('concept_count', concept, tuple(sorted(stocks)), tuple(targets), tuple(protected), tuple(strong_protected))
        if flag not in g.warned:
            audit('CONCEPT_BREAK_COUNT', concept=concept, count=len(stocks), counted=sorted(stocks),
                eligible_targets=targets, day0_protected=protected, strong_protected=strong_protected,
                note='首日及强趋势均参与计数但不产生该退出；实际成交另看Trade')
            g.warned.add(flag)

def readable_fields(payload):
    labels={'stock':'股票','order_id':'订单','reason':'原因','error':'错误','action':'处理','price':'报价',
            'qty':'股数','limit':'限价','floor':'下界','stage':'阶段','token':'标记','evidence':'依据',
            'count':'数量','cash':'现金','nav':'净值','status':'状态','actual':'实际','expected':'预期'}
    def clean(value):
        if isinstance(value,dict):return '；'.join(str(k)+'='+clean(v) for k,v in value.items())
        if isinstance(value,(list,tuple,set)):return ', '.join(clean(x) for x in value)
        return str(value).replace('\n',' / ').replace('\r','')
    return ' | '.join(labels.get(k,k)+':'+clean(v) for k,v in payload.items() if k!='traceback')

def human_audit(event,p):
    if event=='CONFIG':
        log_strategy_overview()
    elif event=='SIGNAL_FUNNEL':
        log.info('【筛选诊断】基础池%s只 | 已评估%s只 | 合格%s只 | 日线不足%s只 | 个股异常%s只' %
                 (p.get('pool'),p.get('evaluated'),p.get('qualified'),p.get('missing_daily'),p.get('stock_errors')))
    elif event=='ORDER_FEE':log.info('【订单费用】订单%s | 平台已返回费用%.4f元' % (p['order_id'],p['fee']))
    elif event=='CONCEPT_BREAK_COUNT':
        log.info('【概念炸板计数】%s | 不同股票%d只:%s | 允许退出:%s | 首日仅计数:%s | 强趋势仅计数:%s' %
                 (p['concept'],p['count'],','.join(p['counted']),','.join(p['eligible_targets']) or '无',','.join(p['day0_protected']) or '无',','.join(p.get('strong_protected',[])) or '无'))
    elif event=='PRIOR_LIMIT_FILTER':
        for item in p.get('excluded',[]):
            log.info('【板型排除】%s | %s | %s' % (stock_label(item['stock']), item['reason'],
                     '；'.join('%s:%s(开%.2f/高%.2f/低%.2f/收%.2f/涨停%.2f)' % (x['date'], x['pattern'], x['open'], x['high'], x['low'], x['close'], x['high_limit']) for x in item['pattern_days'])))
        if p.get('unverifiable'):log.warning('【板型数据不可核验】'+readable_fields({'股票及原因':p['unverifiable']}))
    elif event=='ACCELERATION_CHECK':
        log.info('【加速退出检查】%s | 昨日涨停:%s | 前两日累计:%.2f%% | 当前涨停:%s | 加速条件:%s | 报价%.3f' %
                 (stock_label(p['stock']),p['yesterday_limit_up'],p['return_two_days']*100,p['at_limit'],p['accelerated'],p['price']))
    elif event in ('PROFILE','PREPARED','CONFIG_RAW','RUNTIME_BINDINGS','POSITION_RAW','POSITION_STATE','DAY_END','TIE_RANKING'):
        return
    elif (py_any(word in event for word in ('ERROR','MISSING','VIOLATION','UNCONFIRMED','UNOWNED'))
          or event in ('SUPPLEMENT_FILL_BELOW_FLOOR','OPEN_FILL_REVIEW')):
        log.warning('【异常/'+event+'】'+readable_fields(p))
    elif event in ('POSITION_METADATA_RESTORED','BASIS_ADJUST','SUPPLEMENT_FLOOR_CANCEL','RISK_CAP_UNACHIEVABLE','ORDER_DAY_ARCHIVE'):
        log.info('【持仓与订单/'+event+'】'+readable_fields(p))
    else:_human_audit_core(event,p)

def log_strategy_overview():
    """仅输出说明；不请求行情、不改变账户状态或筛选结果。"""
    log_section('组合与资金')
    log_micro_position_rules()
    log.info('【运行方式】单一资金池，初始资金100%，六形态共享资金和名额；N8/K8/D5。')
    log.info('【排序与入围】洗盘→突破→超跌→吸筹→主升→标准；先完整资格/历史排除及形态内次分，各池同股归最高优先级合格形态后取前K。洗盘/主升/标准跨原分排名，突破/吸筹/超跌原分优先；不自动轮换旧仓。')
    log.info('【名额与资金】六形态共用N8/K8/D5：最多8只持仓名额、每日8只入围、单笔预算分母5。')
    log.info('【预算例子】净值30万元、有效系数80%：总敞口预算24万元、标准单笔4.8万元；剩余预算不足4.8万元时允许小笔。')
    log_section('基础池与历史数据')
    log.info('【基础池】上市超过50自然日，排除4/8/68/92代码前缀；历史ST/停牌和当日ST/退市名称过滤→历史中证1000→至少命中一个热门概念。')
    log.info('【概念池】同股同概念去重计票/金额；基础排除转融券标的、融资融券、深股通、沪股通、国企改革，额外只剔新股与次新股；保留预增概念，不用滚动池。')
    log.info('【概念排行】昨日涨停组按计数排名；当日09:15—09:25竞价近涨停组按计数/竞价量×涨停价金额各50%排名；两组各Top4并集最多8个；同分按计数、金额、概念名。')
    log.info('【板型与加速】近2日有一字/T字涨停或近5日至少2次则排除；全部N3>=2或N5>=3排除。非创业N3>=1且R3>22%或N5>=2且R5>28%；创业R3>23%/R5>31%/R2>=21%/H2>=22%/R1>=14.5%/H1>=15.5%任一排除。')
    log.info('【形态过滤差异】除主升外五形态另排除非创业R15>37%、创业R15>40%；主升免R15。洗盘/主升/标准执行弱阴线与十日活跃，突破/吸筹/超跌不套用；保留原震仓排除。日线截至昨日，当前只用已知开盘/报价。')
    log.info('【活跃度】近10完整交易日先至少1日换手>2%；再要求振幅>3.5%的天数A>2，或换手>2%的天数Vn>2，或最大振幅>5.5%，或最大高点/前收涨幅>5.5%；缺失不视为通过。')
    log_section('洗盘：筛选、排序与专属交易')
    log.info('【洗盘共同硬】开盘较昨收>1%；d=C/MA10−1在(-5%,+0.5%)；C>MA20×1.005；45<RSI<区间上限；完整止跌；十日活跃。止跌=下影>5×实体或C>O或abs(C−O)/(前收+0.0001)<0.3%。')
    log.info('【洗盘G1/G2】G1(-5%,-3%)：RSI<60、昨低在MA20±0.3%且阳线；G2[-3%,-1.7%)：RSI<62、前一完成行C>=该行MA20。')
    log.info('【洗盘G3/G4】G3[-1.7%,-0.6%)：RSI<62.5、开盘/临时MA5−1>=−1%、前一行V/VMA5>=0.60；G4[-0.6%,+0.5%)：RSI<65、开盘/临时MA5−1<=2%、S10<=4%、昨L<MA<H穿过MA5/10/20至少两条且阳线。')
    log.info('【洗盘边缘】G1/G2至少3/4：MA5和MA10>MA20；V/(VMA5+0.0001)<0.76或V/(VMA8+0.0001)<0.75；非量脉冲；S5>S10。G3/G4硬化S5>S10或(MA5>MA10且S5>0.6%)，余下前三边缘至少2/3。')
    log.info('【洗盘四项次分】开盘距临时MA5绝对偏离越小30%；abs(S5+S10)越小25%；带符号实体(C−O)/(H−L+0.0001)越大25%；V/VMA5离0.60越近20%。合格洗盘跨区间/原分统一组内排名，同分依上述顺序再代码。')
    log.info('【洗盘买入】09:45/09:52按普通价带和高低过滤限价尝试，未买成且仍合格可14:54补买；尾盘另需现价>=临时MA10×0.995。')
    log.info('【洗盘观察】首日收盘<MA10×0.995时第2持有日14:54复核，仍<临时MA10退出；首日弱势修复优先等14:55，其他退出仍有效。洗盘免指数主动卖出，但受新增资金上限约束。')
    log_section('突破：筛选、排序与次日分支')
    log.info('【突破原硬与评分】昨涨幅>4%、V/VMA5>1.3、四均线收敛<2.5%、价格偏离角>25度全部满足；六边缘至少4条，原分>=90。六边缘=扩散>1.8、实体>0.5、阳包阴、收位>0.75、量增堆叠>=2、非量脉冲。')
    log.info('【突破六研究硬】收位>0.75；前一完成行V/VMA5<=2；昨日VMA10/VMA20<=1.2；扩散D<=4；昨日F02=V/VMA5<=2.5；F06=(C/MA20−1)/(ATRP14/100+0.0001)<=3.5。开盘涨幅须在[3%,7%]。具体epsilon和底稿见逐股复核。')
    log.info('【突破五项次分】原分100/95.8333/91.6667优先；仅同原分组内上影更小、C/MA20−1更小、左30变化最大收盘回撤更小、V/VMA5更高、四均线收敛更小，各20%；同分按该顺序再代码。')
    log.info('【突破预留】信号日t只预留、不买；t+1使用完整t日OHLCV。预留占现金和名额，只来自原有空闲或合格ATR额度；不因普通卖出回款凭空扩大尾盘信用。')
    log.info('【突破涨停/阳线】优先判断t日收盘涨停：次日开盘>信号收×1.02、<信号收×0.95或<信号前日收盘，取消；否则09:30市价。非涨停阳线C>O同样检查两项下界，不设+2%上界。')
    log.info('【突破小阴线】t日C<=O且C>=信号前日收盘：09:52和14:55均先核验两日可见低点，若<信号前收97%或<信号前开则取消；09:52还须现价>次日开盘102%，尾盘通过低点闸门即可市价。')
    log.info('【突破大阴线】t日C<=O且C<信号前收：信号日量>前日1.5倍取消；否则min(信号低,次日开)<信号前收95.5%或<信号前开取消；均通过则09:30市价。分支阳线优先，不凭文字名称改变分支。')
    log.info('【突破余单】09:30分支仅该时点尝试，09:31撤余单并结束；小阴09:52零成交可等14:55，09:53撤上午余单、14:56最终结束；任何部分成交均不补第二笔。突破豁免普通价带/高低过滤，仍受现金、风险、T+1和自身分支门槛。')
    log.info('【突破专属卖出】信号日计D1，D1/D2均阴且D2收更低则观察D3；D3阴且收<MA5→D4开盘退出，D3非阴结束，否则D4仍阴→D5开盘退出。突破免14:55加速退出。')
    log_section('主升：筛选、排序与专属交易')
    log.info('【主升共同硬】S5/S10/S20均>0、昨日V/VMA5<0.8、扩散D>0.25、C>MA20×1.02、十日活跃；开盘较昨收>1%。斜率为对应MA当前行/五行前值−1，不是角度。')
    log.info('【主升M1】C>MA5>MA10>MA20且d<3.5%；开盘/临时MA5−1在[1%,3%)；MA10十行斜率>1%；左30变化最大收盘回撤<=18%；P=max(前一完成行涨幅,0)×该行V/VMA5<=2%。')
    log.info('【主升M2】MA5>MA10>MA20且C>MA10；0.975MA5<=C<=MA5；d<3%；开盘>临时MA5；昨C>O、昨日量/前一行量>=0.75、昨低/MA10−1<=1%、S5<8%。')
    log.info('【主升边缘】四条至少3条：下影占比>0.35或收位>0.55；D>1.1；V>VMA20×0.4；(S5>2.8%且S10>1%)或[(S5<=2.8%或S10<1%)且S5+S10>3.3%]。')
    log.info('【主升五项次分】量比V/VMA5接近0.60占30%；收位更高10%；带符号实体更大10%；abs(C/MA5−1)更小30%；开盘距临时MA5接近2%占20%。全合格跨原分/M1/M2排序，同分按此顺序再代码。')
    log.info('【主升买卖】09:52及14:54按普通买入门槛；前三持有日收盘低于固定入场前收→次日09:30退出；首日弱势优先，次日修复成功仅豁免该日、第3日重新检查；14:54适用普通均线破位，14:55适用加速退出。')
    log_section('吸筹、超跌、标准：v0.5.54X最终条件')
    log.info('【吸筹六硬】abs(C/MA20−1)<3%；RSI<40；V<VMA20×0.6或abs(V−20日最低量)<0.01；前一完成行收盘涨幅>=−2%；(C/MA20−1)/(ATRP14/100+0.0001)>=−1；均线扩散D<=1.5。前行跌幅限制未企稳下跌，ATR尺度限制价格过远低于均线。开盘>1%。')
    log.info('【吸筹六边至少3】MA20五行斜率较前行提升；四均线收敛<3%；新锤子；新底背离；收盘位置>0.6；价量同升。原分=75+25×边缘命中/6。')
    log.info('【超跌五硬】R5<−6%或RSI<28；V近20日地量或V<VMA20×0.5；C/MA60−1<−6%；前一完成行RSI<=40；昨日(H−L)/(前收+0.0001)<=3.5%。前行RSI确认此前超跌，振幅限制当前尚未收敛的大幅摆动。开盘>1%。')
    log.info('【超跌六边至少3】四均线收敛<4%；昨日收涨；新锤子或真阳包阴且昨日涨>2%；新底背离；低开高收；MA20五行斜率较前行改善。原分=75+25×边缘命中/6；本版超跌仍当日普通窗口买，未改为次日。')
    log.info('【新锤子/底背离】吸筹/超跌：下影长度>=2×实体长度且下影占比>=50%且上影占比<=15%；底背离=C<=20行收盘升序第2值(包含并列)且V>20行最低量×1.12。分母H−L+0.0001；只用截至昨日完整数据。')
    log.info('【标准十硬】MA5>MA10>MA20；V/VMA5>1.2；开盘涨幅>1.5%；C>MA5或MA5>=C>MA10×1.02；D>0.25；VMA5>VMA20；(S5>2%且S10>1%)或S5+S10>3.2%；十日活跃；C/MA20−1<=15%；VMA10/(VMA20+0.0001)<=1.35或VMA5/(VMA20+0.0001)<=1.7。最后量能条件是或，任一满足即可。')
    log.info('【标准五边至少4】开盘涨幅<5%；C/(MA5+0.0001)<1.07；C>MA5；上影占比<0.3；MACD柱>0。原分98/100只表示合格强度，合格后统一按经济次分。')
    log.info('【吸筹/超跌次分】原分优先，同原分五项各20%：上影更小、开盘接近+3%、C/MA5接近1.005、VMA5/VMA20更高、MACD柱/C更高。')
    log.info('【标准次分】上影更大20%、开盘接近+3%10%、C/MA5接近1.005为40%、VMA5/VMA20更高20%、MACD柱/C更高10%；同分按此顺序再代码。三者09:52和14:54普通买入。')
    log_section('共用订单与普通退出')
    log.info('【普通买入价带】上午报价在固定开盘[99%,101%]；尾盘在[昨收99.5%,固定开盘101%]；按分取整。普通限价单只能约束成交上限，下界依报价核验和及时撤单，不保证跳价时仍在下界上。')
    log.info('【普通盘中高低过滤】当前可核验最低价不得低于昨收−0.5%，最高不得超过昨收+7.5%（创业+8%）；已完成分钟截至前一分钟并加已知开盘/当前报价。')
    log.info('【尾盘额度】只用原有额度及已确认ATR卖出额度；概念/指数/下午大跌/其他普通退出/强趋势/加速退出不新增尾盘额度。先核回报和退出再检查买入，卖出申请不当作已到账。')
    log.info('【ATR退出】截至昨日15有效日线计算TA-Lib ATR14；线=max(旧线,跟踪高点−k×ATR)，只上移；前三持有日k=1.8、第4日起1.55，14:35起每分钟判断；首日不完整ATR监控。')
    log.info('【开盘及持有期】09:30低开>=6%退出；持有>13交易日且昨收未涨停退出，最早第14日；昨收涨停延期计数继续。七日完整收盘浮盈均<0.5%→第8日开盘；八日完整收盘无一>4%→第9日开盘。')
    log.info('【首日走弱修复】买入首日收盘<=前收95%只标记；第2持有日暂免ATR并14:55检查相对首日收盘修复>=4%，未修复退出；其他适用规则不因此全部豁免。')
    log.info('【普通公共风控】14:30起较昨收跌>=8.5%；概念每5分钟统计曾触板且开板的持仓，同概念>=3只触发该概念可卖持仓退出；首日只计数不卖，强趋势也只计数。指数警报只对适用旧仓主动降仓。')
    log.info('【普通均线破位】14:54仅主升/突破/标准：现价<=临时MA10×0.97或<=临时MA20×0.995退出；洗盘使用专属次日MA10观察。临时MA=过去9/19完整收盘加当前价。')
    log.info('【14:55非创业加速】除突破外普通持仓当前未封或近封，且A持有>=3日且昨日封板，或B近2日至少一次封板且R2>17.5%，或C昨日封板且R3>22.5%且今日触涨停。近封等效仅此规则用曾触板且涨幅>9%。')
    log.info('【14:55创业加速】除突破外普通持仓：A当前涨幅<=8%、持有>=3日、昨涨>15%且昨最高涨>18%；或B当前涨<=13%且R2>23%；或C当前涨<=13%、昨涨>16%且R3>25%。')
    log_section('强趋势独立管理')
    log.info('【强趋势标记】盘前持有>=4交易日、昨收/平台成本浮盈非创业>=22.4%或创业>=22.9%；标记持续到清仓，豁免ATR/期限/低开/概念/指数/下午大跌/普通观察及加速退出。')
    log.info('【强趋势14:54退出】任一：较昨收跌>7%；较当日可核验高点回落>9%；(高−低)/昨收>12%且现<开×0.975且现<昨收；累计收盘高点回撤>13%；连跌>=4日且复合跌>8.5%；现<=临时MA10×0.97；现<=临时MA20×0.985；另有下面H/I高开转弱两条。')
    log.info('【强趋势新增H/I】H=开盘/昨收−1>8%且(日高−日低)/日高>10%且现价<开盘95%；I=开盘/昨收−1>2%且(日高−日低)/昨收>12%且日高/昨收−1>=8%且现价<昨收101%且现价<开盘。任一整组成立退出；连续一字开板当日豁免同样覆盖H/I。')
    log.info('【强趋势开板豁免】强趋势标记期间连续>=2个完整一字涨停后，开盘或盘中首次可核验打开的当天免强趋势退出，回封不撤回豁免、次交易日恢复；已成交卖单不能撤回。')
    log_section('时间、日志与成交口径')
    log.info('【盘前时间】09:24微观/持仓核对；09:26概念池与持仓规则；09:27退出计划→仓位分析→完整选股；09:29买入计划及耗时。')
    log.info('【交易时间】09:30普通退出/突破对应分支；09:45洗盘；09:52主升/吸筹/超跌/标准普通买入及突破小阴；14:35起ATR；14:54普通尾盘买/专属退出；14:55突破小阴尾买/观察及加速；撤余买单09:31/09:53/14:55/14:56；15:10对账。')
    log.info('【真实订单】09:30卖出和突破各买点用市价单；普通买入及其他卖出用限价单；不承诺市价按开盘价成交，不以委托当成交、不以撤单申请当成功、跌停排队保留实际持仓。')
    log.info('【日志】合格候选→各形态次分→单条条件复核→活跃度→历史统计→候选概念；research_indicator_logs=False、log_all_indicators=False关闭完整研究指标及突破额外研究明细，保留正常候选与条件复核，每日公共合格池只输出一遍，各账户输出入围/成交/持仓/净值；候选键=日期|形态|股票；readable不刷AUDIT。')
    log.info('【费用】固定价差滑点0.002元，双向佣金0.0003最低5元，卖出税2023-08-28前0.001/之后0.0005；真实价格、禁止未来数据、信号强撮合关闭；成交量比例不另覆盖平台默认。')
    log.info('【实现边界】概念沿用显式日期security_info.concepts，历史成员/名称时点语义尚未证实；非量脉冲字段恒False、宏观MACD30根窗口继续保留。本轮未把这些研究问题改成未经回测的新规则。')



def load_previous_limit_up(context):
    cached=getattr(g,'previous_limit_cache',None)
    if cached and cached['asof']==g.asof:return cached
    stocks=prepare_stock_list(g.asof)
    if not stocks:raise ValueError('昨日涨停统计基础池为空')
    price=get_price(stocks,end_date=g.asof,count=1,frequency='daily',fields=['close','high_limit'],
                    panel=False,fill_paused=False,skip_paused=False)
    if price is None or price.empty or not {'code','close','high_limit'}.issubset(price.columns):
        raise ValueError('昨日涨停行情为空或缺列')
    if 'time' in price.columns:
        dates=pd.to_datetime(price.time)
        if dates.isna().any() or py_any(d.date()!=pd.Timestamp(g.asof).date() for d in dates):
            raise ValueError('昨日涨停行情日期不符')
    price=price.dropna()
    yesterday=list(price.loc[price.close==price.high_limit,'code'].astype(str))
    cached=dict(asof=g.asof,stocks=stocks,yesterday=yesterday)
    g.previous_limit_cache=cached
    return cached

def add_prepare_seconds(stage,started):
    if not hasattr(g,'prepare_seconds'):g.prepare_seconds={}
    g.prepare_seconds[stage]=g.prepare_seconds.get(stage,0.)+time.perf_counter()-started

def prepare_macro(context):
    if getattr(g,'macro_ready',False):return
    if not prepare_stage_allowed('macro'):return
    started=time.perf_counter()
    try:
        g.prepare_stage='昨日涨停家数与仓位评分'
        g.limit_up_count=len(load_previous_limit_up(context)['yesterday'])
        g.base_ratio=calculate_position_ratio(context) if g.cfg['micro_risk'] else 1.
        g.position_ratio=g.base_ratio;g.macro_ready=True
        getattr(g,'prepare_failures',{}).pop('macro',None)
        if not g.cfg['micro_risk']:log.info('【微观结构仓位诊断】评分关闭，系数100.00%')
    except Exception as exc:
        mark_prepare_failure('macro',exc)
        audit('PREPARE_ERROR',stage=g.prepare_stage,error=str(exc),action='禁止新买，保留持仓管理；盘前后续阶段至多重试')
    finally:add_prepare_seconds('宏观及昨日统计',started)

def prepare_holdings(context):
    if g.day!=str(context.current_dt.date()):prepare_day(context)
    if getattr(g,'holdings_ready',False) and getattr(g,'concept_ready',False):return
    holdings_display_due=False
    started=time.perf_counter()
    try:
        g.prepare_stage='实际持仓与价格基准核对'
        if not getattr(g,'holdings_ready',False) and prepare_stage_allowed('holdings'):
            adjust_price_basis(context)
            prepare_exit_states(context)
            holdings_display_due=True
            g.holdings_ready=True
            getattr(g,'prepare_failures',{}).pop('holdings',None)
    except Exception as exc:
        mark_prepare_failure('holdings',exc)
        audit('PREPARE_ERROR',stage=g.prepare_stage,error=str(exc),action='持仓核对失败，禁止新买并保留原状态')
    finally:add_prepare_seconds('持仓核对',started)
    if not getattr(g,'macro_ready',False):prepare_macro(context)
    if not getattr(g,'concept_ready',False) and prepare_stage_allowed('concept'):
        started=time.perf_counter()
        try:
            build_concept_pool(context);g.concept_ready=True
            getattr(g,'prepare_failures',{}).pop('concept',None)
        except Exception as exc:
            mark_prepare_failure('concept',exc)
            audit('PREPARE_ERROR',stage=g.prepare_stage,error=str(exc),action=('禁止新买，09:29可重试；不修改持仓' if use_concept_selection() else '仅概念观察数据未就绪；本版无概念选股不因此停止，持仓概念退出独立查询'))
        finally:add_prepare_seconds('概念池',started)
    if holdings_display_due:log_holdings(context)

def capacity_snapshot(context):
    ratio = sizing_ratio(); ceiling = exposure_target_ratio(); n = int(g.cfg['max_count']); divisor = unit_budget_divisor()
    slots = position_slot_limit()
    actual = {s for s, p in context.portfolio.positions.items() if total_qty(p) > 0}
    pending = {o['stock'] for o in g.orders.values() if o['side'] == 'buy' and not o['terminal']}
    rebalance_breakout_reservations(context)
    deferred = breakout_pending_snapshot()
    free = py_max(0, slots - len(actual | pending | deferred['stocks']))
    reserve = py_sum(py_max(0, o['qty'] - o['seen_qty']) * o['limit'] for o in g.orders.values() if o['side'] == 'buy' and not o['terminal'])
    nav = float(context.portfolio.total_value); value = exposure_value(context)
    budget = py_max(0, py_min(nav * ratio / divisor, nav * ceiling - value - reserve - deferred['cash'], float(context.portfolio.available_cash) - deferred['cash']))
    planned = bool(getattr(g, 'sale_planned', False)) or py_any(o['side'] == 'sell' and not o['terminal'] for o in g.orders.values())
    return dict(ratio=ratio, micro_ratio=float(g.position_ratio), exposure_target=ceiling, n=n, unit_divisor=divisor, slots=slots,
                actual=actual, pending=pending, free=free, reserve=reserve, nav=nav, value=value, budget=budget,
                planned=planned, room_or_exit=(free > 0 or planned), deferred_stocks=deferred['stocks'], deferred_cash=deferred['cash'])

def plan_sells(context):
    if g.day!=str(context.current_dt.date()):prepare_day(context)
    if not getattr(g,'holdings_ready',False):prepare_holdings(context)
    if not getattr(g,'sell_plan_done',False):
        started=time.perf_counter()
        try:
            record_opening_exits(context)
            g.sell_plan_done=True
            if not g.sale_planned:log.info('【开盘退出计划】当前无已确认的退出计划；ATR新信号到允许时间再判断')
            log_section('盘前仓位分析')
            log_capacity(context,'盘前')
        finally:add_prepare_seconds('退出计划',started)
    prepare_signals(context)

def log_selection_summary():
    log_section('选股总结')
    state=getattr(g,'selection_status','未评估')
    if state!='完成':
        log.info('【选股总结】状态:%s | 本日未形成可用候选；不表示全市场没有合格股票' % state)
        return
    log.info('【选股总结】状态:完成 | 实际入围%d只/入围上限%d只 | 持仓上限%d只；入围不等于实际买入' % (len(g.candidates),g.cfg['selection_count'],g.cfg['max_count']))
    for stock in g.candidates:
        info=g.qs_combo_info.get(stock,{})
        log.info('【入围标的】%s | %s | 原分%.2f | 次分%.4f | 开盘涨幅%.2f%%' %
                 (stock_label(stock),main_shape_display_name(info),info.get('score',0.),info.get('tie_score',0.),info.get('open_chg',0.)))

def plan_buys(context):
    if g.day!=str(context.current_dt.date()):prepare_day(context)
    if getattr(g,'premarket_reported',False):return
    if not getattr(g,'sell_plan_done',False):plan_sells(context)
    if getattr(g,'selection_status','未评估')=='失败' and not g.prepare_retry_done and getattr(g,'prepare_retryable',True):
        g.prepare_retry_done=True
        g.retry_in_progress=True
        try:prepare_signals(context)
        finally:g.retry_in_progress=False
    started=time.perf_counter()
    try:
        capture_late_seed(context)
        if getattr(g,'selection_status','未评估')!='完成':
            log_section('买入信号计划')
            log.info('【买入计划】不生成订单计划 | 选股状态:%s' % getattr(g,'selection_status','未评估'))
            g.plan_ready=True;g.open_plan={}
        else:
            build_buy_plan(context)
        reserve_breakout_plans(context)
        log_deferred_plans(context)
    except Exception as exc:
        g.signal_ok=False
        audit('PREPARE_ERROR',stage='买入计划',error=str(exc),action='禁止新买，保留已有持仓管理')
    finally:
        add_prepare_seconds('买入计划',started)
        g.premarket_reported=True
        log.info('【盘前完成】日线截至%s | 选股状态:%s | 入围%d只 | 仓位系数%.2f%% | 计划可用:%s' %
                 (g.asof,getattr(g,'selection_status','未评估'),len(g.candidates),g.position_ratio*100,g.signal_ok and g.plan_ready))
        parts=getattr(g,'prepare_seconds',{})
        log.info('【盘前耗时】累计计算%.3f秒 | %s；不含定时回调间等待，非平台总耗时' %
                 (py_sum(parts.values()),' | '.join(k+'=%.3f秒'%v for k,v in parts.items())))

def prepare_stage_allowed(stage):
    failure=getattr(g,'prepare_failures',{}).get(stage)
    return failure is None or (getattr(g,'retry_in_progress',False) and failure['retryable'])

def mark_prepare_failure(stage,exc):
    if not hasattr(g,'prepare_failures'):g.prepare_failures={}
    g.prepare_failures[stage]=dict(retryable=type(exc).__name__ not in ('ParamsError','TypeError'),error=str(exc))

def sizing_ratio():
    if g.cfg.get('capacity_mode', 'total_cap_only') == 'total_cap_only': return 1.0
    return float(g.position_ratio) if g.cfg.get('apply_micro_position_ratio', True) else 1.0

def exposure_target_ratio():
    return float(g.position_ratio) if g.cfg.get('apply_micro_position_ratio', True) else py_min(1.0, float(g.risk_cap))

def is_growth_board(stock):
    return str(stock).startswith(('300', '301'))

def buy_cancel_times():
    return sorted(set(['09:31','14:56',add_clock(entry_start(),1),add_clock(g.cfg['late_buy_time'],1)]))


def buy_expiry(clock):
    if clock in (g.cfg['wash_buy_start_time'],entry_start()):return add_clock(entry_start(),1)
    if clock==g.cfg['late_buy_time']:return add_clock(g.cfg['late_buy_time'],1)
    raise ValueError('非普通买入窗口，禁止生成买单到期时间:'+str(clock))


def acceleration_evidence(raw, adjusted, asof):
    # Preserve the previous six-day activity check. R15 only extends aligned
    # adjusted closes, not the no-pause requirement into unrelated earlier days.
    raw = verified_entry_window(raw, asof, 6)
    adjusted = verified_entry_window(adjusted, asof, 16, activity_count=6)
    seals = []
    for close, limit in zip(raw.close, raw.high_limit):
        close = float(close); limit = float(limit)
        if np.isnan(limit) or limit <= 0 or (np.isfinite(limit) and close > limit + .005):
            raise ValueError('涨幅加速涨停价与收盘价不一致')
        seals.append(price_at_limit(close, limit))
    close = [float(v) for v in adjusted.close]
    high = [float(v) for v in adjusted.high.iloc[-2:]]
    if not py_all(np.isfinite(v) and v > 0 for v in high):
        raise ValueError('涨幅加速窗口最高价无效')
    if py_any(h < c - 1e-8 for h, c in zip(high, close[-2:])):
        raise ValueError('涨幅加速窗口最高价小于收盘价')
    return dict(asof=str(asof), n3=py_sum(seals[-3:]), n5=py_sum(seals[-5:]), n2=py_sum(seals[-2:]),
                r1=close[-1] / close[-2] - 1, r2=close[-1] / close[-3] - 1,
                r3=close[-1] / close[-4] - 1, r5=close[-1] / close[-6] - 1,
                r15=close[-1] / close[-16] - 1,
                high_r1=high[-1] / close[-2] - 1,
                high_r2=py_max(high[-2:]) / close[-3] - 1,
                yesterday_limit_up=bool(seals[-1]), raw_close=float(raw.close.iloc[-1]),
                raw_high_limit=float(raw.high_limit.iloc[-1]), first_date=str(adjusted.index[0].date()),
                return_basis='fq=pre，同一16日窗口', limit_basis='fq=None')

def acceleration_filter_reasons(stock, evidence, combo_type=None, defer_r15=False):
    n3, n5 = evidence['n3'], evidence['n5']
    reasons = []
    if n3 >= 2: reasons.append('近3日涨停不少于2次')
    if n5 >= 3: reasons.append('近5日涨停不少于3次')
    if is_growth_board(stock):
        if evidence['r3'] > .23 + 1e-12: reasons.append('创业板R3>23%')
        if evidence['r5'] > .31 + 1e-12: reasons.append('创业板R5>31%')
        if evidence['r2'] >= .21 - 1e-12: reasons.append('创业板R2>=21%')
        if evidence['high_r2'] >= .22 - 1e-12: reasons.append('创业板近2日最高价/大前日收盘-1>=22%')
        if evidence['r1'] >= .145 - 1e-12: reasons.append('创业板昨日涨幅>=14.5%')
        if evidence['high_r1'] >= .155 - 1e-12: reasons.append('创业板昨日最高价/前日收盘-1>=15.5%')
        if not defer_r15 and combo_type != 'combo_4' and evidence['r15'] > .40 + 1e-12: reasons.append('创业板R15>40%')
    else:
        if n3 >= 1 and evidence['r3'] > .22 + 1e-12: reasons.append('非创业近3日至少1次涨停且R3>22%')
        if n5 >= 2 and evidence['r5'] > .28 + 1e-12: reasons.append('非创业近5日至少2次涨停且R5>28%')
        if not defer_r15 and combo_type != 'combo_4' and evidence['r15'] > .37 + 1e-12: reasons.append('非创业R15>37%')
    return reasons

def filter_acceleration(stocks, asof, combo_type=None, defer_r15=False):
    with selection_stage('acceleration_evaluate'):
        if not hasattr(g, 'accel_daily_cache'): g.accel_daily_cache = {}
        prime_entry_filter_history(stocks, asof, adjusted=False)
        prime_entry_filter_history(stocks, asof, adjusted=True)
        kept, excluded, missing = [], [], []
        for stock in stocks:
            try:
                evidence = acceleration_evidence(entry_filter_frame(stock, asof, False),
                                                 entry_filter_frame(stock, asof, True), asof)
                g.accel_daily_cache[stock] = evidence
                reasons = acceleration_filter_reasons(stock, evidence, combo_type=combo_type, defer_r15=defer_r15)
                if reasons:
                    excluded.append(stock)
                    log.info('【涨幅加速排除】%s | N3=%d/N5=%d | R1=%.2f%%/R2=%.2f%%/R3=%.2f%%/R5=%.2f%%/R15=%.2f%% | 近1日/2日最高涨幅%.2f%%/%.2f%% | %s' %
                             (stock_label(stock), evidence['n3'], evidence['n5'], evidence['r1']*100,
                              evidence['r2']*100, evidence['r3']*100, evidence['r5']*100, evidence['r15']*100,
                              evidence['high_r1']*100, evidence['high_r2']*100, '；'.join(reasons)))
                else: kept.append(stock)
            except Exception as exc:
                missing.append(stock)
                log.warning('【涨幅加速不可核验】%s | %s；本日不入选，不按未加速处理' % (stock_label(stock), exc))
        log.info('【涨幅加速过滤】%d只 → %d只 | 加速排除%d只/不可核验%d只 | 数据截至%s' %
                 (len(stocks), len(kept), len(excluded), len(missing), asof))
        return kept

def log_candidate_history(stock):
    try:
        evidence = acceleration_history(stock)
        log.info('【候选历史统计】%s | N3=%d/N5=%d | R1=%.2f%%/R2=%.2f%%/R3=%.2f%%/R5=%.2f%%/R15=%.2f%% | 近1日/2日最高涨幅%.2f%%/%.2f%% | 截至%s' %
                 (stock_label(stock), evidence['n3'], evidence['n5'], evidence['r1']*100,
                  evidence['r2']*100, evidence['r3']*100, evidence['r5']*100, evidence['r15']*100,
                  evidence['high_r1']*100, evidence['high_r2']*100, evidence['asof']))
    except Exception as exc:
        audit('CANDIDATE_HISTORY_ERROR', stock=stock, error=str(exc), action='仅诊断缺失；不伪造历史统计')

def observed_exact_limit_touch(context, stock, current_price, high_limit):
    if price_at_limit(current_price, high_limit):return True
    if not np.isfinite(high_limit) or high_limit <= 0:return False
    ext=intraday_extrema(context,stock,current_price)
    if ext.get('high') is not None and price_at_limit(ext['high'],high_limit):return True
    if not ext['valid']:raise ValueError(ext.get('error','今日实际触板证据不完整'))
    return False

def late_acceleration_evidence(stock):
    if not hasattr(g,'late_exit_history_cache'):g.late_exit_history_cache={}
    key=(str(g.asof),stock)
    if key in g.late_exit_history_cache:return g.late_exit_history_cache[key]
    evidence=dict(a_available=False,b_available=False,c_available=False,
                  yesterday_limit_up=None,n2=None,r1=None,r2=None,r3=None,h1=None,errors={})
    def history(count,raw):
        fields=['close','high','high_limit','paused','volume'] if raw else ['close','high','paused','volume']
        h=checked_daily(get_price(stock,end_date=g.asof,count=count,frequency='daily',fields=fields,
                        fq=None if raw else 'pre',skip_paused=False),g.asof)
        expected=[pd.Timestamp(v).date() for v in get_trade_days(end_date=g.asof,count=count)]
        if len(expected)!=count or list(h.index.date)!=expected:raise ValueError('尾盘历史日期缺失/错位')
        if not py_all(np.isfinite(float(v)) and float(v)>0 for v in h.close):raise ValueError('尾盘收盘价无效')
        if py_any(bool(v) for v in h.paused) or not py_all(np.isfinite(float(v)) and float(v)>0 for v in h.volume):
            raise ValueError('尾盘历史含停牌/无成交')
        if not py_all(np.isfinite(float(v)) and float(v)>0 for v in h.high):raise ValueError('历史最高价无效')
        if raw:
            if py_any(np.isnan(float(x)) or float(x)<=0 or (np.isfinite(float(x)) and float(c)>float(x)+.005)
                      for c,x in zip(h.close,h.high_limit)):raise ValueError('涨停价不可核验')
        elif not py_all(np.isfinite(float(v)) and float(v)>0 for v in h.high):raise ValueError('历史最高价无效')
        return h
    growth=is_growth_board(stock)
    try:
        if growth:
            two=history(2,False)
            evidence['r1']=float(two.close.iloc[-1])/float(two.close.iloc[-2])-1
            evidence['h1']=float(two.high.iloc[-1])/float(two.close.iloc[-2])-1
        else:
            row=history(1,True).iloc[-1]
            two=history(2,False)
            r1=float(two.close.iloc[-1])/float(two.close.iloc[-2])-1
            evidence['yesterday_limit_up']=acceleration_near_sealed(float(row.close),float(row.high),float(row.high_limit),r1)
        evidence['a_available']=True
    except Exception as exc:evidence['errors']['A']=str(exc)
    try:
        three=history(3,False)
        evidence['r2']=float(three.close.iloc[-1])/float(three.close.iloc[-3])-1
        if not growth:
            two=history(2,True)
            returns=[float(three.close.iloc[i])/float(three.close.iloc[i-1])-1 for i in (1,2)]
            evidence['n2']=py_sum(acceleration_near_sealed(float(row.close),float(row.high),float(row.high_limit),r) for (_,row),r in zip(two.iterrows(),returns))
        evidence['b_available']=True
    except Exception as exc:evidence['errors']['B']=str(exc)
    try:
        four=history(4,False)
        evidence['r3']=float(four.close.iloc[-1])/float(four.close.iloc[-4])-1
        if growth:evidence['r1']=float(four.close.iloc[-1])/float(four.close.iloc[-2])-1
        elif evidence['yesterday_limit_up'] is None:
            row=history(1,True).iloc[-1]
            two=history(2,False)
            r1=float(two.close.iloc[-1])/float(two.close.iloc[-2])-1
            evidence['yesterday_limit_up']=acceleration_near_sealed(float(row.close),float(row.high),float(row.high_limit),r1)
        evidence['c_available']=True
    except Exception as exc:evidence['errors']['C']=str(exc)
    g.late_exit_history_cache[key]=evidence
    return evidence

def opening_exit_session(context):
    if context.current_dt.strftime('%H:%M') != '09:30': return
    if g.day != str(context.current_dt.date()): prepare_day(context)
    if 'ordinary_exit_0930' in g.opening_ticks: return
    g.opening_ticks.add('ordinary_exit_0930')
    try:
        refresh_all_exit_exemptions(context)
        sync_orders(context); cancel_expired(context); manage_positions(context); sync_orders(context)
        deferred_breakout_session(context)
    except Exception as exc:
        halt_new_buys(context, 'OPENING_EXIT_ERROR'); audit('OPENING_EXIT_ERROR', error=str(exc))

def is_maturity_reason(reason):
    return bool(reason) and (reason == '第10个交易日退出' or
            (str(reason).startswith('持仓超过') and str(reason).endswith('交易日且昨收未涨停退出')))

def yesterday_sealed_for_maturity(stock):
    if not hasattr(g, 'maturity_limit_cache'): g.maturity_limit_cache = {}
    key = (str(g.asof), stock)
    if key in g.maturity_limit_cache: return g.maturity_limit_cache[key]
    try:
        h = checked_daily(get_price(stock, end_date=g.asof, count=1, frequency='daily',
                          fields=['close', 'high_limit', 'paused', 'volume'], fq=None, skip_paused=False), g.asof)
        if len(h) != 1 or h.index[-1].date() != pd.Timestamp(g.asof).date():
            raise ValueError('昨日封板判断日期缺失/错位')
        row = h.iloc[-1]; close = float(row.close); limit = float(row.high_limit)
        if bool(row.paused) or not np.isfinite(float(row.volume)) or row.volume <= 0:
            raise ValueError('昨日停牌/无成交，不能判定有效收盘封板')
        if not np.isfinite(close) or close <= 0 or np.isnan(limit) or limit <= 0 or (np.isfinite(limit) and close > limit + .005):
            raise ValueError('昨日收盘/涨停价不可核验')
        answer = bool(price_at_limit(close, limit))
    except Exception as exc:
        answer = None
        log.warning('【到期规则数据异常】%s | %s；本日暂停到期规则，其他退出照常' % (stock_label(stock), exc))
    g.maturity_limit_cache[key] = answer
    return answer

def maturity_due(context, stock, book, age=None):
    if book.get('strong_trend'):return False
    age = holding_days(context, book['entry_date']) if age is None else age
    if age <= g.cfg['max_hold']: return False
    sealed = yesterday_sealed_for_maturity(stock)
    if sealed is None: return False
    sealed = bool(sealed)
    if sealed:
        flag = ('maturity_limit_defer', stock)
        if flag not in g.warned:
            log.info('【到期延期】%s | 持有第%d交易日，昨日收盘涨停；天数继续累计，其他退出照常' % (stock_label(stock), age))
            g.warned.add(flag)
    return not sealed

def maturity_cancel_pending(context, stock):
    """Only cancellation of obsolete maturity orders; never remove actual fills/book."""
    pending = False
    for oid, intent in list(g.orders.items()):
        if intent['stock'] != stock or not intent.get('obsolete_maturity') or intent['terminal']: continue
        pending = True
        try: request_cancel(context, oid, '退出规则豁免/到期条件不成立，撤失效退出余单')
        except Exception as exc: audit('MATURITY_CANCEL_ERROR', stock=stock, order_id=oid, error=str(exc))
    old_items = [(oid, intent) for oid, intent in getattr(g, 'rollover_pending', {}).items()
                 if intent['stock'] == stock and intent.get('obsolete_maturity') and not intent['terminal']]
    if old_items:
        try:
            natives = {str(k): v for k, v in get_orders().items()}
            natives.update({str(k): v for k, v in get_open_orders().items()})
            for oid, intent in old_items:
                native = natives.get(str(oid))
                if native is None:
                    # A daily order may expire normally. Preserve archive for ordinary
                    # reconciliation rather than inventing a canceled Order response.
                    if intent['seen_qty'] < intent.get('reported_filled', 0): pending = True
                    continue
                status = str(native.status).split('.')[-1]
                if status in ('held', 'canceled', 'rejected'):
                    if intent['seen_qty'] < int(native.filled): pending = True
                    continue
                pending = True
                last = intent.get('maturity_cancel_last_at')
                if last and context.current_dt - last < dt.timedelta(minutes=1): continue
                intent['maturity_cancel_last_at'] = context.current_dt
                cancel_order(native)
                audit('MATURITY_ROLLOVER_CANCEL', stock=stock, order_id=oid,
                      note='只撤失效退出余单，等待平台终态与真实成交核对，不删除持仓')
        except Exception as exc:
            pending = True
            audit('MATURITY_CANCEL_ERROR', stock=stock, error=str(exc))
    return pending

def refresh_maturity_intent(context, stock, book, age=None):
    relevant = is_maturity_reason(book.get('exit_reason')) or py_any(
        intent['stock'] == stock and is_maturity_reason(intent.get('reason')) and not intent['terminal']
        for source in (g.orders, getattr(g, 'rollover_pending', {})) for intent in source.values())
    due = maturity_due(context, stock, book, age)
    if relevant and not due:
        if is_maturity_reason(book.get('exit_reason')):
            old = book['exit_reason']; book['exit_reason'] = None
            log.info('【到期意图重评】%s | 清除%s；保留真实持仓、ATR及其他退出规则' % (stock_label(stock), old))
        for source in (g.orders, getattr(g, 'rollover_pending', {})):
            for intent in source.values():
                if intent['stock'] == stock and is_maturity_reason(intent.get('reason')) and not intent['terminal']:
                    intent['obsolete_maturity'] = True
        maturity_cancel_pending(context, stock)
    return due

def capture_late_seed(context):
    if getattr(g, 'late_seed', None) is not None: return
    if context.current_dt.strftime('%H:%M') >= '09:30': return
    if not getattr(g, 'macro_ready', False) or not getattr(g, 'holdings_ready', False): return
    nav = float(context.portfolio.total_value)
    actual = {s for s, p in context.portfolio.positions.items() if total_qty(p) > 0}
    pending = {o['stock'] for o in g.orders.values() if o['side'] == 'buy' and not o['terminal']}
    reserve = py_sum(py_max(0, o['qty'] - o['seen_qty']) * o['limit'] for o in g.orders.values()
                     if o['side'] == 'buy' and not o['terminal'])
    cash = py_max(0., py_min(float(context.portfolio.available_cash),
                            nav * exposure_target_ratio() - exposure_value(context) - reserve))
    slots = py_max(0, position_slot_limit() - len(actual | pending))
    g.late_seed = dict(day=g.day, at=str(context.current_dt), cash=cash, slots=slots,
                       nav=nav, cap=exposure_target_ratio(), held=sorted(actual), reserved=sorted(pending))
    audit('LATE_SEED', seed=g.late_seed, atr_fill_start=exit_start(), atr_fill_cutoff=g.cfg['late_buy_time'],
          note='普通开盘退出前原有资格；默认规则不逐日刷来源日志')

def record_late_eligibility_fill(context, intent, trade_id, trade, qty, price, closed):
    if not hasattr(g, 'eligibility_fills'): g.eligibility_fills = {}
    if trade_id in g.eligibility_fills: return
    if trade.time.date() != context.current_dt.date():
        halt_new_buys(context, 'LATE_CREDIT_DATE_ERROR', trade_id)
        return
    gross = qty * price
    intent['seen_value'] = intent.get('seen_value', 0.) + gross
    start=dt.datetime.combine(context.current_dt.date(),dt.datetime.strptime(exit_start(),'%H:%M').time())
    cutoff=dt.datetime.combine(context.current_dt.date(),dt.datetime.strptime(g.cfg['late_buy_time'],'%H:%M').time())
    qualifying = (intent['side']=='sell' and is_atr_reason(intent.get('reason')) and
                  start<=trade.time<=cutoff and trade.time<=context.current_dt)
    g.eligibility_fills[trade_id] = dict(stock=intent['stock'], side=intent['side'], gross=gross,
                                       time=str(trade.time), qualified_atr=qualifying,
                                       closed=bool(closed), reason=intent.get('reason'))
    audit('LATE_CREDIT_FILL', trade_id=trade_id, **g.eligibility_fills[trade_id])

def estimated_order_fee(side, gross):
    if gross <= 0: return 0.
    # prepare_day/initialize已同步平台费用；未初始化不默认为万五，避免早期回测低估卖出费用。
    rate = g.effective_sell_stamp_tax if HISTORICAL_STAMP_TAX else .0005
    return py_max(5., gross * .0003) + (gross * rate if side == 'sell' else 0.)

def late_eligibility_snapshot(context):
    seed = getattr(g, 'late_seed', None)
    if not seed or seed.get('day') != g.day:
        return dict(ready=False, cash=0., slots=0, reason='缺普通开盘退出前原有资格快照')
    fills = list(getattr(g, 'eligibility_fills', {}).values())
    qualified = [f for f in fills if f['qualified_atr']]
    buy_stocks = {f['stock'] for f in fills if f['side'] == 'buy'}
    closed_atr = {f['stock'] for f in qualified if f['closed']}
    qualified_gross = py_sum(f['gross'] for f in qualified)
    buy_gross = py_sum(f['gross'] for f in fills if f['side'] == 'buy')
    fees = 0.; reserve = 0.; reserved_stocks = set()
    for oid, intent in g.orders.items():
        gross = intent.get('seen_value', 0.)
        reported = g.fee_seen.get(oid)
        known = reported is not None and np.isfinite(float(reported)) and float(reported) >= 0
        estimate = estimated_order_fee(intent['side'], gross)
        # Even a terminal Order can expose commission=0 before fees settle. Source
        # credit uses the conservative maximum; actual platform fee logs stay intact.
        accrued = py_max(float(reported), estimate) if known else estimate
        fees += accrued
        if intent['side'] == 'buy' and not intent['terminal']:
            remaining = py_max(0, intent['qty'] - intent['seen_qty']) * intent['limit']
            reserve += remaining + py_max(0., estimated_order_fee('buy', gross + remaining) - accrued)
            reserved_stocks.add(intent['stock'])
    deferred=breakout_pending_snapshot()
    cash = seed['cash'] + qualified_gross - buy_gross - fees - reserve - deferred['cash']
    slots = seed['slots'] + len(closed_atr) - len(buy_stocks | reserved_stocks | deferred['stocks'])
    return dict(ready=True, cash=cash, slots=slots, seed_cash=seed['cash'], seed_slots=seed['slots'],
                atr_gross=qualified_gross, atr_closed=len(closed_atr), buy_gross=buy_gross,
                fees=fees, reserve=reserve, buy_slots=len(buy_stocks | reserved_stocks))

def unit_budget_divisor():
    """Independent per-entry budget divisor; never changes holding/finalist limits.

    Missing field falls back to max_count only for persisted pre-v0.5.48 state.
    Invalid configuration fails explicitly rather than silently changing risk.
    """
    value = g.cfg.get('unit_budget_divisor', g.cfg.get('max_count'))
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError('unit_budget_divisor须为正整数')
    return value


def position_slot_limit():
    n = int(g.cfg['max_count'])
    if g.cfg.get('capacity_mode', 'total_cap_only') != 'legacy_scaled': return n
    ratio = sizing_ratio()
    return py_max(1, int(n * ratio)) if ratio > 0 else 0

def acceleration_b_signal(stock, evidence):
    if not evidence['b_available']:return False
    if is_growth_board(stock):return evidence['r2']>.23+1e-12
    return evidence['n2']>=1 and evidence['r2']>.175+1e-12


# v0.5.19: all historical entry filters use complete exchange dates ending T-1.
def entry_expected_dates(asof, count):
    key = (str(asof), int(count))
    if not hasattr(g, 'entry_calendar_cache'): g.entry_calendar_cache = {}
    if key not in g.entry_calendar_cache:
        g.entry_calendar_cache[key] = [pd.Timestamp(d).date() for d in get_trade_days(end_date=asof, count=count)]
    return g.entry_calendar_cache[key]

def prime_entry_filter_history(stocks, asof, adjusted):
    if getattr(g, 'entry_filter_asof', None) != str(asof):
        g.entry_filter_asof = str(asof)
        g.entry_raw_history = {}; g.entry_adjusted_history = {}; g.entry_calendar_cache = {}
    cache = g.entry_adjusted_history if adjusted else g.entry_raw_history
    fields = ['open', 'high', 'low', 'close', 'paused', 'volume']
    if not adjusted: fields += ['high_limit', 'low_limit']
    missing = [str(stock) for stock in stocks if str(stock) not in cache]
    for offset in range(0, len(missing), 200):
        batch = missing[offset:offset + 200]
        frame = selection_timed(selection_history_label(), get_price, batch, end_date=asof, count=16, frequency='daily', fields=fields,
                          fq='pre' if adjusted else None, skip_paused=False, panel=False)
        if frame is None or frame.empty or 'code' not in frame.columns:
            raise ValueError('历史入场过滤批量日线不可核验；禁止绕过')
        grouped = selection_groups(frame)
        for stock in batch:
            try:
                cache[stock] = checked_daily(grouped[stock], asof)
            except Exception as exc:
                cache[stock] = str(exc)

def entry_filter_frame(stock, asof, adjusted):
    if getattr(g, 'entry_filter_asof', None) != str(asof):
        raise ValueError('入场过滤历史缓存日期不符')
    cache = g.entry_adjusted_history if adjusted else g.entry_raw_history
    frame = cache.get(stock)
    if not isinstance(frame, pd.DataFrame): raise ValueError('历史行情缺失/不可核验:%s' % frame)
    return frame

def verified_entry_window(frame, asof, count, activity_count=None):
    frame = checked_daily(frame, asof).iloc[-count:]
    expected = entry_expected_dates(asof, count)
    if len(expected) != count or len(frame) != count or list(frame.index.date) != expected:
        raise ValueError('历史窗口不足%d个完整交易日或日期错位' % count)
    activity_count = count if activity_count is None else int(activity_count)
    if activity_count < 1 or activity_count > count:
        raise ValueError('历史活动性核验窗口无效')
    active = frame.iloc[-activity_count:]
    if py_any(not np.isfinite(float(v)) or bool(v) for v in active.paused):
        raise ValueError('历史窗口含停牌/停牌状态缺失')
    if not py_all(np.isfinite(float(v)) and float(v) > 0 for v in active.volume):
        raise ValueError('历史窗口含无成交数据')
    if not py_all(np.isfinite(float(v)) and float(v) > 0 for v in frame.close):
        raise ValueError('历史窗口收盘价无效')
    return frame

def prior_pattern_evidence(raw, asof):
    window = verified_entry_window(raw, asof, 5)
    hits = []
    for when, row in window.iterrows():
        pattern = prior_limit_pattern(row)
        if pattern:
            hits.append(dict(date=str(when.date()), pattern=pattern.replace('昨日', ''),
                             **{k: float(row[k]) for k in ('open', 'high', 'low', 'close', 'high_limit')}))
    two_dates = set(str(x.date()) for x in window.index[-2:])
    n2 = py_sum(item['date'] in two_dates for item in hits)
    n5 = len(hits)
    return dict(excluded=n2 >= 1 or n5 >= 2, n2=n2, n5=n5, pattern_days=hits,
                reason='近2日一字/T字涨停%d次，近5日%d次' % (n2, n5))

def weak_candle_evidence(stock, raw, adjusted, asof):
    raw = verified_entry_window(raw, asof, 5)
    adjusted = verified_entry_window(adjusted, asof, 5)
    hits = []
    for i in range(1, 5):
        row = raw.iloc[i]
        values = [float(row[k]) for k in ('open', 'high', 'low', 'close')]
        op, high, low, close = values
        lower = float(row['low_limit'])
        if not py_all(np.isfinite(v) and v > 0 for v in values): raise ValueError('弱势阴线OHLC不可核验')
        if high < py_max(op, low, close) - 1e-8 or low > py_min(op, high, close) + 1e-8:
            raise ValueError('弱势阴线OHLC次序异常')
        if np.isnan(lower) or lower < 0 or (lower > 0 and low < lower - .005):
            raise ValueError('弱势阴线实际跌停价缺失/不一致')
        one_price_down = lower > 0 and py_all(price_at_limit(v, lower) for v in values)
        if one_price_down: continue  # One-price limit-down is explicitly exempt.
        t_limit_down = (lower > 0 and price_at_limit(op, lower) and price_at_limit(close, lower)
                        and price_at_limit(low, lower) and high > lower + .005)
        red_candle = close < op - 1e-12
        return_one = float(adjusted.close.iloc[i]) / float(adjusted.close.iloc[i - 1]) - 1
        if t_limit_down:
            reject = True
            reason = 'T字跌停：开收最低在实际跌停价、盘中打开过'
        elif is_growth_board(stock):
            low_return = float(adjusted.low.iloc[i]) / float(adjusted.close.iloc[i - 1]) - 1
            reject = red_candle and (return_one < -.10 - 1e-12 or low_return < -.11 - 1e-12)
            reason = '创业板收盘跌超10%%或盘中低点跌超11%%，且收盘低于开盘；收盘/低点收益=%.4f%%/%.4f%%' % (return_one * 100, low_return * 100)
        else:
            reject = red_candle and price_at_limit(low, lower) and high > lower + .005
            reason = '非创业板盘中触跌停且开板过、收盘低于开盘'
        if reject:
            hits.append(dict(date=str(raw.index[i].date()), reason=reason, return_one=return_one,
                             open=op, high=high, low=low, close=close, low_limit=lower))
    return hits

def filter_weak_shape_candidates(items, asof):
    with selection_stage('weak_candle_evaluate'):
        targets = [item['stock'] for item in items if item['combo_type'] in ('combo_2', 'combo_4', 'combo_6')]
        prime_entry_filter_history(targets, asof, False)
        prime_entry_filter_history(targets, asof, True)
        kept, excluded, missing = [], 0, 0
        for item in items:
            stock = item['stock']
            if item['combo_type'] not in ('combo_2', 'combo_4', 'combo_6'):
                kept.append(item); continue
            try:
                hits = weak_candle_evidence(stock, entry_filter_frame(stock, asof, False),
                                            entry_filter_frame(stock, asof, True), asof)
                if hits:
                    excluded += 1
                    log.info('【形态弱势阴线排除】%s | %s | %s' % (stock_label(stock), item['combo_name'],
                             '；'.join('%s:%s(日涨幅%.2f%%)' % (x['date'], x['reason'], x['return_one']*100) for x in hits)))
                else:
                    kept.append(item)
            except Exception as exc:
                missing += 1
                log.warning('【形态弱势阴线不可核验】%s | %s；本日不入选' % (stock_label(stock), exc))
        log.info('【形态弱势阴线过滤】原形态合格%d只 → %d只 | 近4日弱阴线/T字跌停排除%d只/不可核验%d只；只约束洗盘、主升浪回踩、标准多头，一字跌停豁免' %
                 (len(items), len(kept), excluded, missing))
        return kept


def intraday_extrema(context,stock,current_price=None):
    """Completed bars strictly before now plus known open/current quote; no final daily OHLC.

    The platform timestamps minutes by their end. At 14:54 the completed window
    ends 14:53. A transient peak/trough during the excluded minute can be missed;
    valid means full deliberately lagged coverage, not tick-complete coverage.
    """
    try:
        now=context.current_dt;day=str(now.date());clock=now.strftime('%H:%M')
        cd=get_current_data()[stock]
        opening=float(cd.day_open)
        current=float(cd.last_price) if current_price is None else float(current_price)
        if cd.paused or not py_all(np.isfinite(x) and x>0 for x in (opening,current)):
            raise ValueError('停牌或当日开盘/当前报价无效')
        if clock<'09:30' or clock>'15:00':raise ValueError('不在可观测当日交易时段')
        key=(now,stock)
        if not hasattr(g,'intraday_extrema_cache') or getattr(g,'intraday_extrema_cache_time',None)!=now:
            g.intraday_extrema_cache={};g.intraday_extrema_cache_time=now
        if key not in g.intraday_extrema_cache:
            cutoff=now-dt.timedelta(minutes=1)
            expected=pd.date_range(day+' 09:31',day+' 11:30',freq='min').union(
                     pd.date_range(day+' 13:01',day+' 15:00',freq='min'))
            expected=expected[expected<=pd.Timestamp(cutoff)]
            if not len(expected):
                base=dict(valid=True,high=opening,low=opening,through='开盘快照')
            else:
                begin=dt.datetime.combine(now.date(),dt.time(9,30))
                h=get_price(stock,start_date=begin,end_date=cutoff,frequency='1m',fields=['high','low'],fq='pre',skip_paused=False)
                if h is None or h.empty or not isinstance(h.index,pd.DatetimeIndex) or h.index.has_duplicates:
                    raise ValueError('当日分钟极值行情缺失/索引异常')
                if h.index.min()<pd.Timestamp(begin) or h.index.max()>pd.Timestamp(cutoff):raise ValueError('分钟极值含越界/未来时间')
                values=np.asarray(h[['high','low']],dtype=float)
                if not np.isfinite(values).all() or (values<=0).any() or (values[:,0]<values[:,1]).any():
                    raise ValueError('当日分钟high/low无效')
                missing=expected.difference(h.index)
                base=dict(valid=not len(missing),high=py_max(opening,float(h.high.max())),
                          low=py_min(opening,float(h.low.min())),through=str(cutoff))
                if len(missing):base['error']='缺%d个已完成交易分钟，首缺%s'%(len(missing),missing[0])
            g.intraday_extrema_cache[key]=base
        result=dict(g.intraday_extrema_cache[key])
        result['high']=py_max(result['high'],current);result['low']=py_min(result['low'],current)
        result['quote_at']=str(now)
        return result
    except Exception as exc:return dict(valid=False,high=None,low=None,through=None,error=str(exc))

def strong_trend_qualified(stock,age,profit):
    threshold=g.cfg['strong_trend_growth_profit'] if is_growth_board(stock) else g.cfg['strong_trend_profit']
    return age>=g.cfg['strong_trend_age'] and np.isfinite(profit) and profit>=threshold-1e-12

def observation_atr_exempt(context,book):
    # Calendar strings select the recorded next trading day; no weekend arithmetic.
    day=str(context.current_dt.date())
    return book.get('weak_observation_day')==day or book.get('weak_atr_exempt_day')==day

def strong_oneword_history(context, stock, book):
    """At least two immediately prior exchange sessions, raw OHLC vs same-day limit."""
    day = str(context.current_dt.date()); asof = str(context.previous_date)
    mark = book.get('strong_mark_date')
    key = (str(stock), asof, str(mark))
    if not hasattr(g, 'strong_oneword_history_cache'): g.strong_oneword_history_cache = {}
    if key in g.strong_oneword_history_cache: return g.strong_oneword_history_cache[key]
    result = dict(available=False, eligible=False, asof=asof, mark_date=mark, dates=[], days=[], error=None)
    try:
        if not mark or str(mark) > day: raise ValueError('强趋势标记日期缺失/晚于今日')
        expected = [pd.Timestamp(v).date() for v in get_trade_days(end_date=asof, count=2)]
        if len(expected) != 2 or expected[-1] != pd.Timestamp(asof).date():
            raise ValueError('连续一字涨停交易所日期缺失/错位')
        result['dates'] = [str(v) for v in expected]
        if expected[0] < pd.Timestamp(mark).date():
            result.update(available=True, eligible=False, reason='强趋势标记后不足两个完整交易日')
        else:
            h = checked_daily(get_price(stock, end_date=asof, count=2, frequency='daily',
                fields=['open','high','low','close','high_limit','paused','volume'], fq=None, skip_paused=False), asof)
            if len(h) != 2 or list(h.index.date) != expected: raise ValueError('一字涨停历史未覆盖两个指定完整交易日')
            detail = []
            for when, row in h.iterrows():
                values = {field: float(row[field]) for field in ('open','high','low','close','high_limit','paused','volume')}
                prices = [values[f] for f in ('open','high','low','close','high_limit')]
                if not py_all(np.isfinite(v) and v>0 for v in prices): raise ValueError('一字涨停历史OHLC/涨停价缺失或无有限涨停价')
                if not np.isfinite(values['paused']) or values['paused'] not in (0.,1.) or not np.isfinite(values['volume']) or values['volume']<0:
                    raise ValueError('一字涨停历史停牌/成交量无效')
                if ((values['paused']==1. and values['volume']!=0.) or (values['paused']==0. and values['volume']<=0.)):
                    raise ValueError('一字涨停历史停牌与成交量冲突')
                if (values['high']<py_max(values['open'],values['close'],values['low'])-1e-8
                        or values['low']>py_min(values['open'],values['close'],values['high'])+1e-8
                        or values['high']>values['high_limit']+.005):
                    raise ValueError('一字涨停历史OHLC次序/涨停价异常')
                one = values['paused']==0. and values['volume']>0. and py_all(price_at_limit(values[f],values['high_limit']) for f in ('open','high','low','close'))
                detail.append(dict(date=str(when.date()), one_word_limit=bool(one), **values))
            result.update(available=True, eligible=bool(py_all(r['one_word_limit'] for r in detail)), days=detail,
                          price_basis='fq=None; each row compared with its own high_limit',
                          reason='最近两完整交易日均为标记期间一字涨停' if py_all(r['one_word_limit'] for r in detail) else '最近两完整交易日并非连续一字涨停')
    except Exception as exc: result['error'] = str(exc)
    g.strong_oneword_history_cache[key] = result
    return result

def strong_openboard_evidence(context, stock):
    """Known open/current quote plus incremental raw completed-minute lows, never today's daily low."""
    now = context.current_dt; day = str(now.date()); clock = now.strftime('%H:%M')
    result = dict(available=False, opened=False, source=None, asof=str(now), error=None)
    try:
        if clock < '09:25' or clock > '15:00': raise ValueError('不在当日开盘价/盘口可核验时段')
        cd = get_current_data()[stock]
        op, price, limit = float(cd.day_open), float(cd.last_price), float(cd.high_limit)
        if (cd.paused or not py_all(np.isfinite(v) and v>0 for v in (op,limit))
                or (clock>'09:30' and (not np.isfinite(price) or price<=0))):
            raise ValueError('当前停牌或开盘/最新价/涨停价不可核验')
        if op>limit+.005 or (clock>'09:30' and price>limit+.005): raise ValueError('当前原始价格高于涨停价，口径待核验')
        result.update(open=op, price=price if np.isfinite(price) else None, high_limit=limit)
        if op < limit-.005:
            result.update(available=True, opened=True, source='已知当日开盘价', low=op, through='开盘快照')
            return result
        # Before continuous trading last_price may still be yesterday's close.
        if clock < '09:30':
            result.update(available=True, opened=False, source='当日开盘涨停，等待可核验盘中行情')
            return result
        # At the exact 09:30 callback the engine can still expose yesterday's last_price.
        # Official day_open is usable; a divergent last_price is not proof of opening-up.
        observed_price = op if clock == '09:30' else price
        if observed_price < limit-.005:
            result.update(available=True, opened=True, source='当前可核验报价', low=price, through=str(now))
            return result
        if getattr(g, 'strong_openboard_cache_day', None) != day:
            g.strong_openboard_cache_day = day; g.strong_openboard_minute_cache = {}
        cache = g.strong_openboard_minute_cache.setdefault(str(stock),dict(rows={},last_checked=None,error=None))
        cutoff = now-dt.timedelta(minutes=1)
        expected = pd.date_range(day+' 09:31',day+' 11:30',freq='min').union(pd.date_range(day+' 13:01',day+' 15:00',freq='min'))
        expected = expected[expected<=pd.Timestamp(cutoff)]
        missing = [v for v in expected if str(v) not in cache['rows']]
        if missing and cache['last_checked'] != str(now):
            cache['last_checked'] = str(now)
            try:
                start = missing[0]-dt.timedelta(minutes=1)
                h = get_price(stock,start_date=start,end_date=cutoff,frequency='1m',
                    fields=['high','low','volume'],fq=None,skip_paused=False)
                if h is None or h.empty or not isinstance(h.index,pd.DatetimeIndex) or h.index.has_duplicates:
                    raise ValueError('强趋势开板分钟数据缺失/索引异常')
                if h.index.min()<pd.Timestamp(start) or h.index.max()>pd.Timestamp(cutoff): raise ValueError('强趋势开板分钟含越界/未来时点')
                staged = {}
                for when,row in h.iterrows():
                    if when not in expected: continue
                    high,low,volume=float(row['high']),float(row['low']),float(row['volume'])
                    if (not py_all(np.isfinite(v) for v in (high,low,volume)) or low<=0 or high<low
                            or high>limit+.005 or volume<0): raise ValueError('强趋势开板分钟high/low/volume无效')
                    staged[str(when)] = dict(high=high,low=low,volume=volume)
                cache['rows'].update(staged); cache['error']=None
            except Exception as exc: cache['error']=str(exc)
        missing = [v for v in expected if str(v) not in cache['rows']]
        if missing: raise ValueError(cache.get('error') or ('强趋势开板分钟缺%d行，首缺%s' % (len(missing),missing[0])))
        traded = [cache['rows'][str(v)] for v in expected if cache['rows'][str(v)]['volume']>0]
        low = py_min([op,observed_price]+[v['low'] for v in traded])
        result.update(available=True, opened=bool(low<limit-.005), source='截至前一分钟完整原始分钟low+已知开盘/现价',
                      low=low, through=str(cutoff), completed_minutes=len(expected), active_minutes=len(traded), price_basis='fq=None')
    except Exception as exc: result['error']=str(exc)
    return result

def strong_oneword_observation_exempt(context, stock, book):
    """Sticky for the observed opening-up day only; never reset the strong-trend book."""
    if not book.get('strong_trend'): return False
    day = str(context.current_dt.date())
    if book.get('strong_oneword_observation_day') == day: return True
    # At most one status read per callback timestamp; future minutes may prove opening-up.
    if book.get('strong_oneword_last_probe') == str(context.current_dt): return False
    book['strong_oneword_last_probe'] = str(context.current_dt)
    history = strong_oneword_history(context, stock, book)
    if not history['available'] or not history['eligible']:
        if not history['available'] and book.get('strong_oneword_warning_day') != day:
            book['strong_oneword_warning_day'] = day
            log.warning('【强趋势一字板观察不可核验】%s | 截至%s | %s；不新增豁免，原退出规则继续' % (stock_label(stock),history['asof'],history.get('error')))
        return False
    opened = strong_openboard_evidence(context, stock)
    if opened['available'] and opened['opened']:
        book['strong_oneword_observation_day'] = day
        book['strong_oneword_observation_evidence'] = dict(observed_at=str(context.current_dt),history=history,opening=opened)
        log.info('【强趋势一字板开板观察】%s | 连续一字日%s | 首次核验%s/来源%s/低价%.3f/当日涨停%.3f | 仅今日豁免全部强趋势退出，撤失效余卖单；实际成交保留，下一交易日恢复，强趋势/成本/高点不重置' %
            (stock_label(stock),history['dates'],context.current_dt,opened['source'],opened['low'],opened['high_limit']))
        return True
    if not opened['available'] and book.get('strong_oneword_quote_warning_day') != day:
        book['strong_oneword_quote_warning_day'] = day
        log.warning('【强趋势开板观察数据缺失】%s | %s；不推断已开板，原退出规则继续' % (stock_label(stock),opened.get('error')))
    return False

def refresh_all_exit_exemptions(context):
    """Runs before order maintenance/continuation, even outside five-minute risk checks."""
    for stock,book in list(g.book.items()):
        if book.get('strong_trend') or book.get('combo',{}).get('combo_type')=='combo_2':
            refresh_exempt_exit_intents(context,stock,book)

def exit_reason_exempt(context, stock, book, reason):
    if not reason: return False
    if book.get('strong_trend'):
        return strong_oneword_observation_exempt(context, stock, book) or not is_strong_exit_reason(reason)
    # Pattern-specific exemption affects active selling only, not risk_cap/buy budgets.
    if book.get('combo', {}).get('combo_type') == 'combo_2' and reason == '指数风险降仓':
        return True
    return observation_atr_exempt(context, book) and (is_atr_reason(reason) or is_early_anchor_reason(reason))

def refresh_exempt_exit_intents(context, stock, book):
    # Observe before inspecting an old intent, even when this stock has no new quote
    # for ordinary risk management. Do not clear actual holdings/fills/high-water marks.
    if book.get('strong_trend'):
        strong_oneword_observation_exempt(context, stock, book)
    old = book.get('exit_reason')
    if exit_reason_exempt(context, stock, book, old):
        book['exit_reason'] = None
        log.info('【退出意图豁免】%s | 清除%s；保留真实持仓和成交，失效余单撤成前不重叠下单' % (stock_label(stock), old))
    changed = False
    for source in (g.orders, getattr(g, 'rollover_pending', {})):
        for intent in source.values():
            if (intent['stock'] == stock and intent['side'] == 'sell' and not intent['terminal']
                    and exit_reason_exempt(context, stock, book, intent.get('reason'))):
                intent['obsolete_maturity'] = True
                intent['exit_exemption_day'] = str(context.current_dt.date())
                changed = True
    if changed:
        maturity_cancel_pending(context, stock)

def prepare_exit_states(context):
    day = str(context.current_dt.date())
    for stock, book in list(g.book.items()):
        if stock in g.basis_blocked or not exit_monitor_eligible(context, stock, book): continue
        try:
            age = holding_days(context, book['entry_date'])
            if book.get('weak_entry_marked') and age == 2:
                book['weak_observation_day'] = day; book['weak_atr_exempt_day'] = day
            elif book.get('weak_entry_marked') and age > 2 and book.get('weak_state') == 'pending':
                log.warning('【次日观察未完成】%s | 未获得完整尾盘判定；恢复其他退出监控并保留真实持仓，须核验原观察日' % stock_label(stock))
                book['weak_state'] = 'unresolved_expired'
            if not book.get('strong_trend'):
                position = context.portfolio.positions.get(stock)
                cost = float(getattr(position, 'avg_cost', float('nan'))); prev = previous_close(stock)
                if not py_all(np.isfinite(v) and v > 0 for v in (cost, prev)):
                    raise ValueError('平台成本/前收无效，不能标记强趋势')
                profit = prev / cost - 1
                if strong_trend_qualified(stock, age, profit):
                    book.update(strong_trend=True, strong_mark_date=day, strong_mark_profit=profit,
                        strong_mark_age=age, strong_mark_anchor_date=g.asof)
                    log.info('【强趋势标记】%s | 第%d交易日 | 前收%.3f/平台成本%.3f/浮盈%.2f%% | 至清仓仅受强趋势尾盘退出；收盘高点从%s纳入' %
                        (stock_label(stock), age, prev, cost, profit * 100, g.asof))
            refresh_exempt_exit_intents(context, stock, book)
            activate_close_exit_plan(context, stock, book)
        except Exception as exc:
            log.warning('【持仓状态数据异常】%s | %s；不删除持仓、不臆造强趋势标记' % (stock_label(stock), exc))
    prepare_washout_states(context)
    snapshot_position_metadata()

def strong_tail_session(context):
    if context.current_dt.strftime('%H:%M') != '14:54': return
    day = str(context.current_dt.date())
    for stock, book in list(g.book.items()):
        if not book.get('strong_trend') or not exit_monitor_eligible(context, stock, book) or stock in g.basis_blocked: continue
        if book.get('strong_tail_checked') == day: continue
        book['strong_tail_checked'] = day
        try:
            refresh_exempt_exit_intents(context, stock, book)
            if strong_oneword_observation_exempt(context, stock, book): continue
            cd = get_current_data()[stock]; price = float(cd.last_price); previous = previous_close(stock)
            if cd.paused or not py_all(np.isfinite(v) and v > 0 for v in (price, previous)):
                raise ValueError('强趋势14:54报价/昨收无效或停牌')
            ext = dict(valid=False, error='尚未核验')
            try: ext = intraday_extrema(context, stock, price)
            except Exception as exc: ext['error'] = str(exc)
            dates = []; closes = []; history_error = None
            try: dates, closes = strong_close_history(context, stock, book)
            except Exception as exc: history_error = str(exc)
            signals, values = strong_tail_evidence(price, previous, float(cd.day_open), ext, dates, closes, book.get('strong_mark_anchor_date'))
            signals['F'] = None; signals['G'] = None
            try:
                ma = provisional_tail_mas(context, stock, price, (10,20))
                values['ma10'] = ma['ma10']; values['ma20'] = ma['ma20']
                if ma['ma20'] is not None: signals['G'] = bool(price <= ma['ma20']*.985+1e-10)
                if ma['ma10'] is not None: signals['F'] = bool(price <= ma['ma10']*.97+1e-10)
                if ma['errors']: log.warning('【强趋势MA数据缺失】%s | %s；A—E及H/I仍独立判断' % (stock_label(stock), ma['errors']))
            except Exception as exc:
                values['ma10'] = None; values['ma20'] = None
                log.warning('【强趋势MA数据缺失】%s | %s；A—E及H/I仍独立判断' % (stock_label(stock), exc))
            log.info('【强趋势F条件】%s | 14:54现价%.4f | 临时MA10:%s | 现价<=MA10×0.97:%s | 过去9个收盘截至%s，今日仅当前报价' %
                (stock_label(stock), price, values['ma10'], signals['F'], g.asof))
            log.info('【强趋势G条件】%s | 14:54现价%.4f | 临时MA20:%s | 现价<=MA20×0.985:%s | 过去19个收盘截至%s，今日仅当前报价' %
                (stock_label(stock),price,values['ma20'],signals['G'],g.asof))
            triggered = [key for key, value in sorted(signals.items()) if value is True]
            def percent(value): return '缺失' if value is None else '%.2f%%' % (value * 100)
            log.info('【强趋势尾盘检查】%s | 现价%.3f | 较昨收%s/距日高回落%s/振幅%s/收盘高点回撤%s | 连跌%s日/复合涨跌%s | A日跌7 B高点9 C振幅12且现<开×0.975且现<昨收 D累计13 E连跌4且8.5 F现<=MA10×0.97 G现<=MA20×0.985 H高开8且高低差/高10且现<开95 I高开2且振幅12且最高涨8且现<昨收101且现<开:%s' %
                (stock_label(stock), price, percent(values['day_return']), percent(values['high_drawdown']), percent(values['amplitude']),
                 percent(values['close_drawdown']), values['down_days'], percent(values['down_return']), str(signals)))
            log.info('【强趋势C条件】%s | 振幅%s>12%% | 现价%.4f<开盘%.4f×0.975=%.4f:%s | 现价<昨收%.4f:%s | 同时成立:%s' %
                (stock_label(stock), percent(values['amplitude']), price, values['opening'], values['opening_floor'],
                 values['below_opening_floor'], previous, values['below_previous'], signals['C']))
            log.info('【强趋势H条件】%s | 开盘较昨收%s>8%% | (日高-日低)/日高%s>10%% | 现价较开盘%s<-5%% | 分项:%s | 同时成立:%s' %
                (stock_label(stock), percent(values['opening_return']), percent(values['intraday_peak_to_trough']),
                 percent(values['price_vs_open']), values['H_checks'], signals['H']))
            log.info('【强趋势I条件】%s | 开盘较昨收%s>2%% | (日高-日低)/昨收%s>12%% | 日高较昨收%s>=8%% | 现价%.4f<昨收×1.01=%.4f且<开盘%.4f | 分项:%s | 同时成立:%s' %
                (stock_label(stock), percent(values['opening_return']), percent(values['amplitude']), percent(values['high_return']),
                 price, previous*1.01, float(cd.day_open), values['I_checks'], signals['I']))
            if not ext.get('valid') or history_error:
                log.warning('【强趋势部分数据缺失】%s | 分钟:%s | 收盘:%s；只执行可核验的独立条件' %
                    (stock_label(stock), ext.get('error', '完整'), history_error or '完整'))
            if not triggered: continue
            reason = book.get('exit_reason') or ('14:54强趋势走弱退出:' + '/'.join(triggered))
            book['exit_reason'] = reason
            book['strong_exit_evidence'] = dict(day=day, signals=signals, values=values, price=price,
                previous=previous, opening=float(cd.day_open), extrema=ext)
            q = dict(price=price, high=ext.get('high', price), time=context.current_dt,
                source='current_data_14:54', observed_at=context.current_dt)
            send_order(context, stock, 'sell', book['qty'], reason, q)
        except Exception as exc:
            log.warning('【强趋势尾盘数据异常】%s | %s；不臆造新退出，已确认的强趋势退出余单继续管理' % (stock_label(stock), exc))

def mark_entry_day_observation(context):
    day=str(context.current_dt.date())
    for stock,book in list(g.book.items()):
        if book['entry_date']!=day or book.get('weak_entry_evaluated')==day:continue
        try:
            h=checked_daily(get_price(stock,end_date=day,count=2,frequency='daily',fields=['close','volume','paused'],fq='pre',skip_paused=False),day)
            expected=[pd.Timestamp(v).date() for v in get_trade_days(end_date=day,count=2)]
            if len(expected)!=2 or list(h.index.date)!=expected:raise ValueError('首日观察收盘历史日期缺失/错位')
            if py_any(bool(v) for v in h.paused) or not py_all(np.isfinite(float(v)) and float(v)>0 for v in h.volume):raise ValueError('首日观察收盘历史停牌/无量')
            close=float(h.close.iloc[-1]);prev=float(h.close.iloc[-2])
            if not py_all(np.isfinite(v) and v>0 for v in (close,prev)):raise ValueError('首日观察收盘价无效')
            change=close/prev-1;book['weak_entry_evaluated']=day
            if change<=-g.cfg['entry_weak_drop']+1e-12:
                book.update(weak_entry_marked=True,weak_entry_close=close,weak_entry_change=change,weak_state='pending')
                log.info('【首日走弱观察】%s | 收盘%.3f/前收%.3f/涨跌%.2f%% | 仅标记次日14:55修复观察，首日不卖出；次日豁免ATR，其他退出有效'%(stock_label(stock),close,prev,change*100))
        except Exception as exc:log.warning('【首日观察数据异常】%s | %s；未生成缺证据观察信号'%(stock_label(stock),exc))

def recovery_observation_passed(price,entry_day_close):
    return price/entry_day_close-1>=g.cfg['entry_recovery']-1e-12

def observation_tail_session(context):
    if context.current_dt.strftime('%H:%M')!='14:55':return
    day=str(context.current_dt.date())
    for stock,book in list(g.book.items()):
        if book.get('strong_trend') or book.get('weak_observation_day')!=day or book.get('weak_tail_checked')==day:continue
        if not exit_monitor_eligible(context,stock,book) or stock in g.basis_blocked:continue
        try:
            cd=get_current_data()[stock];price=float(cd.last_price);base=float(book['weak_entry_close'])
            if cd.paused or not py_all(np.isfinite(v) and v>0 for v in (price,base)):raise ValueError('次日观察报价/买日收盘基准不可用')
            passed=recovery_observation_passed(price,base)
            book['weak_tail_checked']=day;book['weak_atr_exempt_day']=day
            book['weak_state']='recovered' if passed else 'exit_pending'
            log.info('【次日修复检查】%s | 14:55现价%.3f/买日复权收盘%.3f | 修复%.2f%%/要求至少4%% | 修复成功:%s；当天ATR仍豁免'%(stock_label(stock),price,base,(price/base-1)*100,passed))
            if passed:continue
            reason=book.get('exit_reason') or '14:55首日走弱次日修复不足4%退出'
            book['exit_reason']=reason
            q=dict(price=price,high=price,time=context.current_dt,source='current_data_14:55',observed_at=context.current_dt)
            send_order(context,stock,'sell',book['qty'],reason,q)
        except Exception as exc:log.warning('【次日修复数据异常】%s | %s；保持真实持仓及其他退出，不凭缺失报价生成修复结论'%(stock_label(stock),exc))

def late_acceleration_signals(stock,evidence,age,current_return,at_limit,touch):
    signals=dict(A=None,B=None,C=None)
    growth=is_growth_board(stock)
    if not growth and at_limit is None: return signals
    if growth:
        if evidence['a_available']:signals['A']=bool(current_return<=.08+1e-12 and age>=3 and evidence['r1']>.15+1e-12 and evidence['h1']>.18+1e-12)
        if evidence['b_available']:signals['B']=bool(current_return<=.13+1e-12 and evidence['r2']>.23+1e-12)
        if evidence['c_available']:signals['C']=bool(current_return<=.13+1e-12 and evidence['r1']>.16+1e-12 and evidence['r3']>.25+1e-12)
    else:
        if evidence['a_available']:signals['A']=bool(not at_limit and age>=3 and evidence['yesterday_limit_up'])
        if evidence['b_available']:signals['B']=bool(not at_limit and evidence['n2']>=1 and evidence['r2']>.175+1e-12)
        if evidence['c_available']:
            core=not at_limit and evidence['yesterday_limit_up'] and evidence['r3']>.225+1e-12
            signals['C']=bool(core and touch) if not core or touch is not None else None
    return signals


def breakout_pending_snapshot(exclude=None):
    """Unfilled conceptual reservations; actual open orders are accounted separately."""
    plans = getattr(g, 'deferred_breakouts', {})
    pending = {s:p for s,p in plans.items() if s != exclude and p.get('status') == 'reserved'
               and p.get('effective_budget',p['budget'])>0 and s not in g.book and not active_order(s, 'buy')}
    return dict(stocks=set(pending), cash=py_sum(float(p.get('effective_budget',p['budget'])) for p in pending.values()))

def rebalance_breakout_reservations(context):
    """Current caps bind promises as well as orders; avoid mutual-blocking when r falls."""
    held={s for s,p in context.portfolio.positions.items() if total_qty(p)>0}
    live={o['stock'] for o in g.orders.values() if o['side']=='buy' and not o['terminal']}
    reserve=py_sum(py_max(0,o['qty']-o['seen_qty'])*o['limit'] for o in g.orders.values() if o['side']=='buy' and not o['terminal'])
    nav=float(context.portfolio.total_value)
    cash=py_max(0.,py_min(float(context.portfolio.available_cash),nav*exposure_target_ratio()-exposure_value(context)-reserve))
    slots=py_max(0,position_slot_limit()-len(held|live))
    plans=getattr(g,'deferred_breakouts',{})
    for stock,p in sorted(plans.items(),key=lambda x:(x[1]['signal_day'],x[1]['combo'].get('priority',99),-x[1]['combo'].get('score',0),-x[1]['combo'].get('tie_score',0),x[0])):
        p['effective_budget']=0.
        if p.get('status')!='reserved' or stock in held|live or slots<=0: continue
        value=py_min(float(p['budget']),nav*sizing_ratio()/unit_budget_divisor(),cash)
        if value<=0: continue
        p['effective_budget']=value;cash-=value;slots-=1

def breakout_cancelled_today():
    """A cancelled prior-day breakout cannot consume a new slot today; reset next day."""
    if getattr(g, 'breakout_cancelled_day', None) != g.day:
        g.breakout_cancelled_day = g.day
        g.breakout_cancelled_stocks = set()
    return g.breakout_cancelled_stocks


def filter_cancelled_breakout_candidates(items):
    blocked=breakout_cancelled_today()
    removed=[item['stock'] for item in items if item['combo_type']=='combo_3' and item['stock'] in blocked]
    if removed:
        log.info('【突破取消当日排除】%s | 仅取消突破归属；同股其他形态不受该计划污染' % '、'.join(stock_label(stock) for stock in removed))
    return [item for item in items if item['combo_type']!='combo_3' or item['stock'] not in blocked]


def breakout_signal_day_evidence(raw, adjusted, reference_date, signal_day, asof):
    """Only complete t-1/t daily rows; prices share today's pre-adjustment basis."""
    reference_date = str(pd.Timestamp(reference_date).date())
    signal_day = str(pd.Timestamp(signal_day).date())
    if signal_day != str(pd.Timestamp(asof).date()):
        raise ValueError('突破信号日复核只允许次交易日使用已完成昨日数据')
    expected = [reference_date, signal_day]
    for frame in (raw, adjusted):
        if frame is None or not isinstance(frame.index, pd.DatetimeIndex) or frame.index.has_duplicates:
            raise ValueError('突破信号日复核日线索引缺失/重复')
        if len(frame) != 2 or [str(pd.Timestamp(d).date()) for d in frame.index] != expected:
            raise ValueError('突破信号日复核日线不完整或日期错位')
    raw_values = raw[['open', 'high', 'low', 'close', 'high_limit', 'volume', 'paused']].astype(float)
    adjusted_values = adjusted[['open', 'high', 'low', 'close', 'volume']].astype(float)
    if not np.isfinite(raw_values.values).all() or not np.isfinite(adjusted_values.values).all():
        raise ValueError('突破信号日复核存在非有限行情')
    if bool((raw_values.paused != 0).any()) or bool((raw_values.volume <= 0).any()):
        raise ValueError('突破信号日或前一交易日停牌/无成交')
    if bool((raw_values[['open','high','low','close','high_limit']] <= 0).any().any()) or bool((adjusted_values <= 0).any().any()):
        raise ValueError('突破信号日复核价格或成交量非正')
    for frame in (raw_values, adjusted_values):
        if bool((frame.high < frame[['open','close','low']].max(axis=1)).any()) or bool((frame.low > frame[['open','close']].min(axis=1)).any()):
            raise ValueError('突破信号日复核OHLC内部矛盾')
    evidence = dict(signal_day=signal_day, reference_date=reference_date,
        signal_open_raw=float(raw.open.iloc[1]), signal_close_raw=float(raw.close.iloc[1]),
        signal_high_limit_raw=float(raw.high_limit.iloc[1]),
        signal_open_adjusted=float(adjusted.open.iloc[1]), signal_high_adjusted=float(adjusted.high.iloc[1]),
        signal_low_adjusted=float(adjusted.low.iloc[1]), signal_close_adjusted=float(adjusted.close.iloc[1]),
        previous_open_adjusted=float(adjusted.open.iloc[0]), previous_high_adjusted=float(adjusted.high.iloc[0]),
        previous_low_adjusted=float(adjusted.low.iloc[0]), previous_close_adjusted=float(adjusted.close.iloc[0]),
        signal_volume_shares=float(raw.volume.iloc[1]), previous_volume_shares=float(raw.volume.iloc[0]),
        volume_ratio=float(raw.volume.iloc[1])/float(raw.volume.iloc[0]),
        closed_at_limit=price_at_limit(float(raw.close.iloc[1]), float(raw.high_limit.iloc[1])))
    evidence['branch'] = breakout_next_day_branch(evidence)
    return evidence


def review_breakout_signal_day(context, stock, plan):
    """Classify the four t+1 branches using complete t/t-1 evidence before selection."""
    if plan.get('signal_review_day') == g.day:
        return bool(plan.get('signal_review'))
    attempt = (g.day, context.current_dt.strftime('%H:%M'))
    if plan.get('signal_review_attempt') == attempt: return False
    plan['signal_review_attempt'] = attempt
    try:
        if pd.Timestamp(plan['signal_day']).date() >= context.current_dt.date():
            raise ValueError('禁止读取尚未完成的突破信号日日线')
        expected = [str(pd.Timestamp(d).date()) for d in get_trade_days(end_date=g.asof, count=2)]
        if expected != [str(plan['reference_date']), str(plan['signal_day'])]:
            raise ValueError('突破t-1/t不是连续且完整的最近两交易日')
        raw = checked_daily(get_price(stock, end_date=g.asof, count=2, frequency='daily',
            fields=['open','high','low','close','high_limit','volume','paused'], fq=None, skip_paused=False), g.asof)
        adjusted = checked_daily(get_price(stock, end_date=g.asof, count=2, frequency='daily',
            fields=['open','high','low','close','volume'], fq='pre', skip_paused=False), g.asof)
        evidence = breakout_signal_day_evidence(raw, adjusted, plan['reference_date'], plan['signal_day'], g.asof)
        plan['signal_review'] = evidence
        plan['signal_review_day'] = g.day
        log.info('【突破次日分支复核】%s | 信号%s/参考%s | 分支:%s（涨停优先） | 同复权t开/收/低%.4f/%.4f/%.4f，t-1开/收%.4f/%.4f | 原始成交量%.0f/%.0f=%.4f倍 | 信号日绝不买入' %
            (stock_label(stock), plan['signal_day'], plan['reference_date'], breakout_branch_label(evidence['branch']),
             evidence['signal_open_adjusted'], evidence['signal_close_adjusted'], evidence['signal_low_adjusted'],
             evidence['previous_open_adjusted'], evidence['previous_close_adjusted'],
             evidence['signal_volume_shares'], evidence['previous_volume_shares'], evidence['volume_ratio']))
        if evidence['branch'] == 'large_bearish' and evidence['signal_volume_shares'] > evidence['previous_volume_shares']*1.5:
            cancel_breakout_plan(context, stock, plan, '大阴分支：t日成交量严格大于t-1日1.5倍，取消整计划')
        return True
    except Exception as exc:
        plan.pop('signal_review_day', None); plan.pop('signal_review', None)
        log.warning('【突破次日分支缺证据】%s | %s；暂不买入，保留预留至允许窗口/最终到期再核验' % (stock_label(stock), exc))
        return False


def refresh_breakout_reservations(context):
    """Keep reservations/live orders until terminal fills reconcile; never delete book."""
    if not hasattr(g, 'deferred_breakouts'): g.deferred_breakouts = {}
    breakout_cancelled_today()
    clock = context.current_dt.strftime('%H:%M')
    for stock, plan in list(g.deferred_breakouts.items()):
        if plan.get('status') == 'cancel_pending':
            if not active_order(stock, 'buy'):
                plan['status'] = 'expired' if plan.get('expiry_requested') else 'cancelled'
                log.info('【突破预留释放】%s | 活跃买单终态且全部真实成交已核对；持仓保留' % stock_label(stock))
        elif stock in g.book:
            plan['status'] = 'filled'
        elif plan.get('status') == 'reserved':
            elapsed = breakout_day_number(context, plan)
            if elapsed == 2:
                review_breakout_signal_day(context, stock, plan)
                branch = plan.get('signal_review', {}).get('branch')
                deadline = breakout_plan_deadline(branch)
                if plan.get('status') == 'reserved' and clock >= deadline:
                    plan['expiry_requested'] = True
                    cancel_breakout_plan(context, stock, plan, '次日%s窗口结束，撤余单并结束整计划；不跨窗口补买' % deadline)
                elif plan.get('status') == 'reserved' and clock >= '09:30':
                    breakout_limit_open_gap_allowed(context, stock, plan)
            elif elapsed > 2:
                plan['expiry_requested'] = True
                cancel_breakout_plan(context, stock, plan, '次交易日已结束，撤余单并释放未成交预留')
        if plan.get('status') in ('filled','expired','cancelled') and not active_order(stock, 'buy'):
            g.deferred_breakouts.pop(stock, None)

def breakout_due_today(context, stock, plan):
    if plan.get('status') != 'reserved' or stock in g.book: return False
    dates = get_trade_days(start_date=plan['signal_day'], end_date=g.day)
    return len(dates) == 2 and str(pd.Timestamp(dates[-1]).date()) == g.day

def intraday_entry_allowed(context, stock, q):
    """Strictly known intraday extrema, no final daily high/low before market close."""
    evidence = intraday_extrema(context, stock, current_price=q['price'])
    if not evidence.get('valid'):
        log.info('【本时点不买】%s | 当日高低点不可完整核验:%s' % (stock_label(stock),evidence.get('error','缺失')))
        return False
    current = get_current_data()[stock]
    opening = float(current.day_open); prior = previous_close(stock)
    if not np.isfinite(opening) or opening <= 0 or not np.isfinite(prior) or prior <= 0: return False
    cap = .08 if is_growth_board(stock) else .075
    low_move = evidence['low']/prior-1.; high_move = evidence['high']/prior-1.
    reasons=[]
    if low_move < -.005-1e-12: reasons.append('最低较昨收低于-0.5%')
    if high_move > cap+1e-12: reasons.append('最高较昨收超过%.1f%%' % (cap*100))
    if reasons:
        log.info('【本时点不买】%s | %s | 最低/昨收%.3f%% 最高/昨收%.3f%% | 分钟截至%s' %
                 (stock_label(stock),'、'.join(reasons),low_move*100,high_move*100,evidence.get('through')))
        return False
    return True

def reserve_breakout_plans(context):
    """Bind only existing/qualified ATR credit before the late check; never invent freed cash."""
    if g.halted or not g.signal_ok or not g.plan_ready: return
    clock=context.current_dt.strftime('%H:%M')
    if clock not in ['09:29',g.cfg['wash_buy_start_time'],entry_start(),g.cfg['late_buy_time']]: return
    # Today's newly ranked washout plans get their first executable opportunity
    # before new breakout promises bind the same free slot. Older promises remain.
    if clock=='09:29' and py_any(p['combo'].get('combo_type')=='combo_2' and s not in g.book
            for s,p in g.open_plan.items()): return
    refresh_breakout_reservations(context)
    rebalance_breakout_reservations(context)
    for stock, plan in g.open_plan.items():
        if plan['combo'].get('combo_type') != 'combo_3': continue
        if stock in g.book or stock in g.sold_today or stock in g.deferred_breakouts or stock in breakout_cancelled_today() or active_order(stock): continue
        credit=late_eligibility_snapshot(context)
        if not credit['ready'] or credit['slots'] <= 0 or credit['cash'] <= 0: continue
        held={s for s,p in context.portfolio.positions.items() if total_qty(p)>0}
        live={o['stock'] for o in g.orders.values() if o['side']=='buy' and not o['terminal']}
        reserved=breakout_pending_snapshot()
        if len(held|live|reserved['stocks']) >= position_slot_limit(): continue
        nav=float(context.portfolio.total_value)
        order_cash=py_sum(py_max(0,o['qty']-o['seen_qty'])*o['limit'] for o in g.orders.values() if o['side']=='buy' and not o['terminal'])
        budget=py_min(nav*sizing_ratio()/unit_budget_divisor(),credit['cash'],
                      nav*exposure_target_ratio()-exposure_value(context)-order_cash-reserved['cash'],
                      float(context.portfolio.available_cash)-reserved['cash'])
        if not np.isfinite(budget) or budget <= 0: continue
        ref=float(plan['previous_close'])
        # A reservation smaller than one board lot is not a usable position.
        if budget*(1-g.cfg['cash_buffer']) < 100*ref*1.01+estimated_order_fee('buy',100*ref*1.01): continue
        g.deferred_breakouts[stock]=dict(signal_day=g.day,reference_date=g.asof,reference_close=ref,
            budget=float(budget),effective_budget=float(budget),combo=dict(plan['combo'],breakout_signal_day=g.day,breakout_reference_date=g.asof),status='reserved',attempted=[],last_reference=None)
        log.info('【突破延迟预留】%s | 信号%s | 参考昨收%.3f | 预留上限%.2f元/1名额 | 信号日只预留；次日涨停/阳线/大阴09:30，小阴09:52或14:55；次日先核验完整t/t-1同复权日线' %
                 (stock_label(stock),g.day,ref,budget))

def deferred_reference(context, plan, stock):
    if plan.get('reference_checked_day') == g.day: return float(plan['last_reference'])
    h=checked_daily(get_price(stock,end_date=plan['reference_date'],count=1,frequency='daily',fields=['close'],fq='pre'),plan['reference_date'])
    if len(h)!=1 or pd.Timestamp(h.index[-1]).date()!=pd.Timestamp(plan['reference_date']).date():
        raise ValueError('突破延迟参考收盘日期错位')
    value=float(h.close.iloc[-1])
    if not np.isfinite(value) or value<=0: raise ValueError('突破延迟参考昨收无效')
    plan['last_reference']=value;plan['reference_checked_day']=g.day
    return value

def deferred_breakout_session(context):
    clock = context.current_dt.strftime('%H:%M')
    if clock not in ('09:30',entry_start(),'14:55'): return
    refresh_breakout_reservations(context)
    if g.halted or not getattr(g,'macro_ready',False) or not getattr(g,'holdings_ready',False): return
    rebalance_breakout_reservations(context)
    for stock, plan in list(g.deferred_breakouts.items()):
        if not breakout_window_allowed(context, plan) or stock in g.book or stock in g.sold_today or active_order(stock): continue
        attempt = str(context.current_dt.date())+' '+clock
        if attempt in plan.setdefault('attempted',[]): continue
        plan['attempted'].append(attempt)
        try:
            q = deferred_entry_quote(context, stock)
            if q is None: continue
            if not breakout_buy_allowed(context, stock, plan, q): continue
            cd = get_current_data()[stock]
            if cd.paused or cd.is_st:
                log.info('【突破本窗口不买】%s | 停牌或ST；不绕过交易状态限制' % stock_label(stock)); continue
            ref = float(plan['signal_review']['previous_close_adjusted'])
            held = {s for s,p in context.portfolio.positions.items() if total_qty(p)>0}
            live = {o['stock'] for o in g.orders.values() if o['side']=='buy' and not o['terminal']}
            other = breakout_pending_snapshot(exclude=stock)
            if len(held|live|other['stocks']) >= position_slot_limit(): continue
            reserve = py_sum(py_max(0,o['qty']-o['seen_qty'])*o['limit'] for o in g.orders.values() if o['side']=='buy' and not o['terminal'])
            nav = float(context.portfolio.total_value)
            cash = py_max(0.,float(context.portfolio.available_cash)-other['cash'])
            budget = py_min(float(plan.get('effective_budget',plan['budget'])),nav*sizing_ratio()/unit_budget_divisor(),
                nav*exposure_target_ratio()-exposure_value(context)-reserve-other['cash'],cash)
            if clock == '14:55':
                credit = late_eligibility_snapshot(context); own = breakout_pending_snapshot()
                own_cash = float(plan.get('effective_budget',plan['budget'])) if stock in own['stocks'] else 0.
                own_slot = 1 if stock in own['stocks'] else 0
                if not credit['ready'] or credit['slots']+own_slot <= 0: continue
                budget = py_min(budget,py_max(0.,credit['cash']+own_cash))
            worst = float(cd.high_limit)
            if not np.isfinite(worst) or worst <= 0: raise ValueError('涨停保护价缺失，无法核验市价买入最大预算')
            if not np.isfinite(budget) or not np.isfinite(cash): raise ValueError('实际现金或有效预算非有限')
            qty = int(py_max(0.,budget)*(1-g.cfg['cash_buffer'])/worst/100)*100
            while qty >= 100 and qty*worst+estimated_order_fee('buy',qty*worst)>cash+1e-8: qty -= 100
            if qty < 100: continue
            q.update(entry_limit=None,entry_floor=None,plan_reference=ref,deferred_breakout=True,deferred_market=True)
            combo = dict(plan['combo'],breakout_signal_day=plan['signal_day'],breakout_reference_date=plan['reference_date'])
            why = '突破次日%s分支%s市价尝试' % (breakout_branch_label(plan['signal_review']['branch']),clock)
            send_order(context,stock,'buy',qty,why,q,combo)
        except Exception as exc:
            log.warning('【突破执行缺证据】%s | %s；本窗口不买，不以缺失行情判通过' % (stock_label(stock),exc))
            audit('DEFERRED_BREAKOUT_ERROR',stock=stock,error=str(exc))

def expire_deferred_breakouts(context):
    # Call after order synchronization at 09:31/09:53/14:56 and following minutes.
    # The shared refresh expires morning branches at 09:31 and small/unknown at 14:56.
    # A 09:52 partial fill stays a real holding and cannot receive a second buy at 14:55.
    refresh_breakout_reservations(context)

def log_deferred_plans(context):
    for stock,plan in getattr(g,'deferred_breakouts',{}).items():
        if plan.get('status') != 'reserved': continue
        log.info('【突破次日预留】%s | t=%s/t-1=%s/原参考收盘%.3f | 上限%.2f/当前可用%.2f元 | 今日可执行:%s | 信号日只预留；次日涨停/阳线/大阴09:30，小阴09:52或14:55；全部市价，余单1分钟后撤' %
            (stock_label(stock),plan['signal_day'],plan['reference_date'],plan['reference_close'],plan['budget'],
             plan.get('effective_budget',plan['budget']),breakout_due_today(context,stock,plan)))


def is_strong_exit_reason(reason):
    return str(reason or '').startswith('14:54强趋势走弱退出:')


def is_early_anchor_reason(reason):
    return str(reason or '').startswith('前三日收盘低于入场前收:')


def ordinary_price_band(context, plan):
    """Freeze the open and prior close at plan time; choose only this window's floor."""
    clock = context.current_dt.strftime('%H:%M')
    if clock in (g.cfg['wash_buy_start_time'], entry_start()):
        floor = plan['morning_lower_limit']
    elif clock == g.cfg['late_buy_time']:
        floor = plan['late_lower_limit']
    else:
        raise ValueError('当前不是普通买入窗口')
    return float(floor), float(plan['limit'])


def deferred_entry_quote(context, stock):
    """Known current quote/open only; all breakout buys bypass ordinary price/extrema bands."""
    if context.current_dt.strftime('%H:%M') == '09:30':
        # Preserve the original stale-opening-quote gate and day_open fill audit.
        opening = opening_quote(context,stock)
        if opening is not None: opening['day_open'] = opening['price']
        return opening
    current = get_current_data()[stock]
    price = float(current.last_price); opening = float(current.day_open)
    if current.paused or not py_all(np.isfinite(v) and v>0 for v in (price,opening)):
        log.info('【突破报价不可核验】%s | 停牌或当日开盘/当前报价缺失；本窗口不买' % stock_label(stock))
        return None
    return dict(price=price,high=price,day_open=opening,time=context.current_dt,
        source='current_data_breakout_entry',observed_at=context.current_dt)


def activate_close_exit_plan(context, stock, book):
    """A close signal is only actionable on a later trading day; never erase the position."""
    plan = book.get('close_exit_plan')
    if not plan: return
    reason = plan['reason']
    if book.get('strong_trend') or (is_early_anchor_reason(reason) and observation_atr_exempt(context, book)):
        log.info('【收盘计划豁免】%s | %s | 强趋势或次日修复观察优先；保留实际持仓' % (stock_label(stock), reason))
        book.pop('close_exit_plan', None)
        return
    if str(context.current_dt.date()) <= plan['signal_date'] or not exit_monitor_eligible(context, stock, book): return
    existing = book.get('exit_reason')
    # Already required emergency/recovery sales retain their actual cause; a close plan outranks ATR/maturity.
    if not existing or is_atr_reason(existing) or is_maturity_reason(existing):
        book['exit_reason'] = reason


def record_close_exit_observations(context):
    """After 15:00 only. Actual daily avg_cost snapshots; missing records never mean zero profit."""
    if context.current_dt.strftime('%H:%M') < '15:00': return
    day = str(context.current_dt.date())
    for stock, book in list(g.book.items()):
        position = context.portfolio.positions.get(stock)
        if position is None or total_qty(position) <= 0 or stock in g.basis_blocked: continue
        try:
            frame = checked_daily(get_price(stock, end_date=day, count=1, frequency='daily',
                fields=['close'], fq='pre'), day)
            if str(frame.index[-1].date()) != day: raise ValueError('缺当日已完成收盘')
            close = float(frame.close.iloc[-1]); cost = float(position.avg_cost)
            if not py_all(np.isfinite(v) and v > 0 for v in (close, cost)): raise ValueError('收盘或平台成本无效')
            age = holding_days(context, book['entry_date']); gain = close / cost - 1.
            history = book.setdefault('close_profit_history', {})
            history[day] = dict(age=age, close=close, avg_cost=cost, gain=gain)
            if book.get('strong_trend'):
                book.pop('close_exit_plan', None)
                continue
            combo = book.get('combo', {}).get('combo_type')
            if combo == 'combo_4' and 1 <= age <= 3:
                base = float(book['anchor_close'])
                if not np.isfinite(base) or base <= 0: raise ValueError('实际买入日前收基准缺失')
                weak_first = age == 1 and book.get('weak_entry_marked')
                weak_unverified = age == 1 and book.get('weak_entry_evaluated') != day
                recovery_day = age == 2 and book.get('weak_entry_marked')
                recovered = recovery_day and book.get('weak_state') == 'recovered'
                unresolved = recovery_day and book.get('weak_state') not in ('recovered', 'exit_pending')
                skipped = weak_first or weak_unverified or recovered or unresolved
                trigger = close < base - 1e-10 and not skipped
                log.info('【前三日收盘检查】%s | 第%d日 | 收盘%.3f/入场前收复权基准%.3f | 弱势观察优先跳过:%s | 次交易日开盘计划:%s' %
                    (stock_label(stock), age, close, base, skipped, trigger))
                if trigger:
                    # A failed recovery already has a stronger pending exit; do not overwrite its reason.
                    book['close_exit_plan'] = dict(reason='前三日收盘低于入场前收:第%d日信号' % age,
                        signal_date=day, signal_age=age, signal_close=close, reference_close=base)
            if age == 7:
                expected = [str(pd.Timestamp(x).date()) for x in get_trade_days(start_date=book['entry_date'], end_date=day)]
                valid = len(expected) == 7 and py_all(
                    d in history and history[d].get('age') == index + 1 and
                    np.isfinite(history[d].get('gain', float('nan')))
                    for index, d in enumerate(expected))
                if not valid:
                    log.warning('【七日浮盈检查】%s | 未有完整连续7个持有交易日收盘记录；不推断全部低于0.5%%，不新增该退出' % stock_label(stock))
                else:
                    peak = py_max(history[d]['gain'] for d in expected)
                    trigger = peak < .005 - 1e-12
                    schedule_new = bool(trigger and not book.get('close_exit_plan'))
                    log.info('【七日浮盈检查】%s | 完整7日收盘浮盈百分数:%s | 最大浮盈%.6f%% | 全部低于0.5%%:%s | 新增第8交易日09:30退出计划:%s' %
                        (stock_label(stock), json.dumps({d: history[d]['gain'] * 100. for d in expected}, ensure_ascii=False, allow_nan=False),
                         peak * 100., trigger, schedule_new))
                    if schedule_new:
                        book['close_exit_plan'] = dict(reason='七日收盘浮盈全部低于0.5%:第8交易日开盘退出',
                            signal_date=day, signal_age=age, maximum_close_profit=peak)
            if age == 8 and str(book.get('close_exit_plan', {}).get('reason', '')).startswith('七日收盘浮盈全部低于0.5%:'):
                log.info('【七日退出计划续存】%s | 第8日仍有真实持仓，保留原计划和实际退出原因，等待后续成交对账，不改写为第9日新信号' % stock_label(stock))
                continue
            if age == 8:
                expected = [str(pd.Timestamp(x).date()) for x in get_trade_days(start_date=book['entry_date'], end_date=day)]
                valid = len(expected) == 8 and py_all(d in history and np.isfinite(history[d].get('gain', float('nan'))) for d in expected)
                if not valid:
                    log.warning('【八日浮盈检查】%s | 每日收盘记录不完整；不推断从未超过4%%，不新增该退出' % stock_label(stock))
                else:
                    peak = py_max(history[d]['gain'] for d in expected); trigger = peak <= .04 + 1e-12
                    log.info('【八日浮盈检查】%s | 完整8日收盘最大浮盈%.3f%% | 未曾超过4%%:%s | 第9交易日开盘退出:%s' %
                        (stock_label(stock), peak * 100, trigger, trigger))
                    if trigger:
                        book['close_exit_plan'] = dict(reason='八日收盘浮盈从未超过4%:第9交易日开盘退出',
                            signal_date=day, signal_age=age, maximum_close_profit=peak)
        except Exception as exc:
            log.warning('【收盘退出数据异常】%s | %s；保留真实持仓和已有有效计划' % (stock_label(stock), exc))


def strong_close_history(context, stock, book):
    """Completed closes on one current pre-adjusted basis; no intraday final daily close."""
    anchor = book.get('strong_mark_anchor_date')
    if not anchor: raise ValueError('强趋势标记基准日期缺失')
    start = py_min(str(book['anchor_date']), str(anchor)); end = str(g.asof)
    key = (stock, start, end)
    if not hasattr(g, 'strong_close_cache'): g.strong_close_cache = {}
    if key not in g.strong_close_cache:
        frame = checked_daily(get_price(stock, start_date=start, end_date=end, frequency='daily',
            fields=['close'], fq='pre', skip_paused=False), end)
        expected = [pd.Timestamp(x).date() for x in get_trade_days(start_date=start, end_date=end)]
        dates = list(frame.index.date)
        if dates != expected or not expected: raise ValueError('强趋势跨日收盘记录缺失/错位')
        values = [float(x) for x in frame.close]
        if not py_all(np.isfinite(x) and x > 0 for x in values): raise ValueError('强趋势收盘价格无效')
        g.strong_close_cache[key] = (dates, values)
    return g.strong_close_cache[key]


def strong_tail_evidence(price, previous, opening, extrema, dates, closes, anchor):
    """Independent predicates: unavailable extrema must not suppress a verifiable daily loss."""
    signals = dict(A=price / previous - 1 < -.07 - 1e-12, B=None, C=None, D=None, E=None, H=None, I=None)
    values = dict(day_return=price / previous - 1, high_drawdown=None, amplitude=None,
        close_peak=None, close_drawdown=None, down_days=None, down_return=None,
        opening=opening, previous=previous, opening_floor=opening * .975, below_opening_floor=None, below_previous=price < previous - 1e-10)
    if np.isfinite(opening) and opening > 0:
        values['below_opening_floor'] = bool(price < opening * .975 - 1e-10)
    if extrema.get('valid'):
        high = float(extrema['high']); low = float(extrema['low'])
        values['high_drawdown'] = 1 - price / high; values['amplitude'] = (high - low) / previous
        signals['B'] = values['high_drawdown'] > .09 + 1e-12
        signals['C'] = values['amplitude'] > .12 + 1e-12 and np.isfinite(opening) and opening > 0 and price < opening * .975 - 1e-10 and price < previous - 1e-10
    # H/I are independent high-open reversal exits, with the same completed-minute extrema.
    values.update(opening_return=None, intraday_peak_to_trough=None, price_vs_open=None, high_return=None)
    values['H_checks'] = None; values['I_checks'] = None
    if (extrema.get('valid') and np.isfinite(opening) and opening > 0
            and py_all(np.isfinite(v) and v > 0 for v in (high, low, previous, price))
            and high >= low):
        values.update(opening_return=opening / previous - 1.,
                      intraday_peak_to_trough=(high - low) / high,
                      price_vs_open=price / opening - 1., high_return=high / previous - 1.)
        h_checks = dict(gap_above_8=bool(values['opening_return'] > .08 + 1e-12),
                        high_low_drop_above_10=bool(values['intraday_peak_to_trough'] > .10 + 1e-12),
                        price_below_open_5=bool(values['price_vs_open'] < -.05 - 1e-12))
        i_checks = dict(gap_above_2=bool(values['opening_return'] > .02 + 1e-12),
                        amplitude_above_12=bool(values['amplitude'] > .12 + 1e-12),
                        high_return_at_least_8=bool(values['high_return'] >= .08 - 1e-12),
                        price_below_previous_101=bool(price < previous * 1.01 - 1e-10),
                        price_below_open=bool(price < opening - 1e-10))
        values['H_checks'] = h_checks; values['I_checks'] = i_checks
        signals['H'] = py_all(h_checks.values()); signals['I'] = py_all(i_checks.values())
    if dates and closes and anchor:
        selected = [v for d, v in zip(dates, closes) if pd.Timestamp(d).date() >= pd.Timestamp(anchor).date()]
        if selected:
            peak = py_max(selected + [price]); values['close_peak'] = peak
            values['close_drawdown'] = 1 - price / peak
            signals['D'] = values['close_drawdown'] > .13 + 1e-12
        # Consecutive falls are measured over held days, including today's observed quote.
        sequence = list(closes) + [price]; end = len(sequence) - 1; start = end
        while start > 0 and sequence[start] < sequence[start - 1] - 1e-10: start -= 1
        days = end - start; move = price / sequence[start] - 1.
        values.update(down_days=days, down_return=move)
        signals['E'] = days >= 4 and move < -.085 - 1e-12
    return signals, values


def activity_shape_rule(evidence, combo, asof=None):
    """本轮标准采用已确认洗盘/主升口径：2%换手、5.5%振幅或冲高。"""
    if combo not in ('combo_2', 'combo_4', 'combo_6'):
        raise ValueError('十日活跃硬条件仅适用于洗盘/主升/标准')
    uses_high_branch = True
    turn_threshold = 2.
    amplitude_peak_threshold = .055
    rows = evidence.get('days', [])
    known = bool(evidence.get('available')) and len(rows) == 10
    known = known and (asof is None or str(evidence.get('asof')) == str(asof))
    days = [str(row.get('day')) for row in rows]
    known = known and len(set(days)) == 10 and days == sorted(days)
    effective_asof = str(asof) if asof is not None else str(evidence.get('asof'))
    known = known and len(days) == 10 and days[-1] == effective_asof and py_all(day <= effective_asof for day in days)
    if known:
        try:
            known = py_all(np.isfinite(float(row.get('amplitude', float('nan'))))
                           and np.isfinite(float(row.get('turnover_percent', float('nan'))))
                           and float(row['amplitude']) >= 0 and float(row['turnover_percent']) >= 0 for row in rows)
        except (TypeError, ValueError):
            known = False
    high_known = False
    if known:
        try:
            high_known = py_all(np.isfinite(float(row.get('high_rise', float('nan'))))
                                and float(row['high_rise']) > -1. for row in rows)
        except (TypeError, ValueError):
            high_known = False
    # All enabled activity gates require actual dated high/previous-close; no amplitude substitution.
    if uses_high_branch and not high_known:
        known = False
    amp_count = turn_count = peak = high_peak = None
    first = second = False
    if known:
        amp_count = int(py_sum(float(row['amplitude']) > .035 + 1e-12 for row in rows))
        turn_count = int(py_sum(float(row['turnover_percent']) > turn_threshold + 1e-12 for row in rows))
        peak = float(py_max(float(row['amplitude']) for row in rows))
        high_peak = float(py_max(float(row['high_rise']) for row in rows)) if high_known else None
        first = turn_count >= 1
        second = turn_count > 2 or amp_count > 2 or peak > amplitude_peak_threshold + 1e-12
        if uses_high_branch:
            second = second or high_peak > .055 + 1e-12
    passed = bool(known and first and second)
    reason = ('通过' if passed else '十日历史数据不可核验' if not known else
              '十日换手均未超过门槛' if not first else
              '第二层四个活跃分支均不满足' if uses_high_branch else '第二层三个活跃分支均不满足')
    error = evidence.get('error', '') if not known else ''
    if uses_high_branch and not high_known and not error:
        error = '十日最高价/前收冲高数据缺失或不可核验；不以振幅替代'
    return dict(combo=combo, asof=evidence.get('asof'), available=bool(known), passed=passed,
                turnover_threshold_percent=turn_threshold, amplitude_threshold_percent=3.5,
                peak_threshold_percent=amplitude_peak_threshold * 100.,
                max_high_rise_threshold_percent=5.5 if uses_high_branch else None,
                amplitude_count=amp_count, turnover_count=turn_count,
                peak_amplitude_percent=peak * 100. if peak is not None else None,
                peak_high_rise_percent=high_peak * 100. if high_peak is not None else None,
                first_layer=bool(first), second_layer=bool(second), reason=reason, error=error,
                amplitude_percent_by_date={str(row['day']): float(row['amplitude']) * 100. for row in rows} if known else {},
                turnover_percent_by_date={str(row['day']): float(row['turnover_percent']) for row in rows} if known else {},
                high_rise_percent_by_date={str(row['day']): float(row['high_rise']) * 100. for row in rows} if known and high_known else {})


def shape_activity_snapshot(stock, combo, asof=None):
    """Read cached evidence only; no data request or state mutation."""
    if asof is None:
        asof = getattr(g, 'asof', None)
    evidence = getattr(g, 'activity_evidence', {}).get(str(stock), {})
    result = activity_shape_rule(evidence, combo, asof)
    result['stock'] = str(stock)
    return result



def activity_snapshot_text(snapshot):
    """Compact, finite, dated statistics used by candidate and rejection logs."""
    v = snapshot
    content = dict(截至=v.get('asof'), 可核验=v['available'],
                   规则='V>=1且(V>2或A>2或最大振幅>5.5%或最大冲高>5.5%)',
                   振幅达标阈值百分数=v['amplitude_threshold_percent'],
                   换手达标阈值百分数=v['turnover_threshold_percent'],
                   最大振幅阈值百分数=v['peak_threshold_percent'],
                   A=v['amplitude_count'], V=v['turnover_count'],
                   最大振幅百分数=v['peak_amplitude_percent'], 最大冲高百分数=v.get('peak_high_rise_percent'),
                   第一层=v['first_layer'], 第二层=v['second_layer'], 通过=v['passed'],
                   原因=v['reason'], 错误=v.get('error', ''),
                   振幅百分数=v['amplitude_percent_by_date'], 换手率百分数=v['turnover_percent_by_date'], 冲高百分数=v.get('high_rise_percent_by_date', {}))
    return json.dumps(content, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


def standard_slope_pass(slope5, slope10):
    """Pass individual thresholds together OR total slope>3.2%; finite T-1 inputs only."""
    try:
        slope5, slope10 = float(slope5), float(slope10)
        if not np.isfinite(slope5) or not np.isfinite(slope10): return False
        both = slope5 > .02 + 1e-12 and slope10 > .01 + 1e-12
        fallback = slope5 + slope10 > .032 + 1e-12
        return bool(both or fallback)
    except (TypeError, ValueError):
        return False


def prime_qualified_activity_observation(items, asof):
    """Complete nonmain/standard survivors' historical statistics; never filter items."""
    if getattr(g, 'activity_asof', None) != str(asof):
        g.activity_asof = str(asof)
        g.activity_evidence = {}
        g.activity_rejection_logged = set()
    stocks = list(dict.fromkeys(str(item['stock']) for item in items))
    targets = [stock for stock in stocks if not (g.activity_evidence.get(stock, {}).get('available')
               and str(g.activity_evidence[stock].get('asof')) == str(asof))]
    for offset in range(0, len(targets), 200):
        batch = targets[offset:offset + 200]
        try:
            with selection_stage('activity_evaluate'):
                # This helper reuses the selection's dated price cache where already primed.
                prime_entry_filter_history(batch, asof, True)
                table = fetch_activity_turnover(batch, asof)
                if not isinstance(table, pd.DataFrame) or not {'code', 'day', 'turnover_ratio'} <= set(table.columns):
                    raise ValueError('批量历史换手率没有code/day/turnover_ratio字段')
                grouped = selection_groups(table)
                for stock in batch:
                    try:
                        evidence = activity_evidence_10d(entry_filter_frame(stock, asof, True), grouped.get(stock), asof)
                    except Exception as exc:
                        evidence = dict(available=False, asof=str(asof), error=str(exc))
                    g.activity_evidence[stock] = evidence
        except Exception as exc:
            for stock in batch:
                g.activity_evidence[stock] = dict(available=False, asof=str(asof), error=str(exc))
    missing = [stock for stock in stocks if not g.activity_evidence.get(stock, {}).get('available')]
    if targets:
        log.info('【候选活跃度底稿补全】候选%d只 | 本次补查%d只 | 不可核验%d只；只补观察数据，不改变已合格候选/原分/排序' %
                 (len(stocks), len(targets), len(missing)))
    return dict(candidates=len(stocks), queried=len(targets), unavailable=len(missing), unavailable_stocks=missing)


def standard_bull_conditions(latest, open_chg):
    """标准多头硬/边缘共用唯一判据，展示和正式筛选不另造公式。"""
    ma5, ma10, ma20 = [float(latest[k]) for k in ('ma5', 'ma10', 'ma20')]
    close = float(latest['close'])
    ceilings = selection_ceiling_metrics(latest)
    core = dict(
        ma_bull=ma5 > ma10 > ma20,
        volume_surge=float(latest['volume_ratio']) > 1.2,
        opening_strong=open_chg > 1.5,
        price_location=(close > ma5 or (ma5 >= close > ma10 * 1.02)),
        spread_floor=float(latest['ma_spread_ratio']) > .25,
        volume_ma_bull=float(latest['volume_ma5']) > float(latest['volume_ma20']),
        slope_strong=standard_slope_pass(latest.get('ma5_slope'), latest.get('ma10_slope')),
        activity_10d=ComboEvaluator._safe_bool(latest.get('activity_standard_pass', False)),
        price_ma20_ceiling=ceilings['standard_price_pass'],
        volume_expansion_ceiling=ceilings['standard_volume_or_pass'])
    edge = dict(
        opening_not_hot=open_chg < 5.,
        close_not_far_ma5=close / (ma5 + .0001) < 1.07,
        close_above_ma5=close > ma5,
        upper_shadow_short=float(latest['upper_shadow_ratio']) < .3,
        macd_positive=float(latest['macd']) > 0)
    return core, edge


def standard_bull_edge_pass(edge_met):
    return int(edge_met) >= 4


def standard_bull_display_score(edge_met, edge_count):
    # Display-only score. Eligibility is explicit edge count, never a rounded score.
    return 90. + 10. * float(edge_met) / float(edge_count)


def _v50_log_candidate_conditions(item, rank):
    """只读冻结形态帧；复用正式评估器，失败仅影响展示，绝不请求行情或改变候选。"""
    if not g.cfg.get('log_shape_conditions', True):
        return
    stock = str(item.get('stock', '股票缺失'))
    try:
        df = getattr(g, '_micro_data_cache', {}).get(stock)
        minimum_rows = 2 if item.get('combo_type') in ('combo_2','combo_3','combo_4') else 7
        if df is None or len(df) < minimum_rows:
            log.warning('【形态条件不可复核】%s | 冻结形态日线缺失/不足，不能输出通过结论' % stock)
            return
        latest, prev = df.iloc[-1], df.iloc[-2]
        combo = item.get('combo_type')
        missing = set()

        def num(key, row=latest):
            try:
                value = float(row[key])
                if not np.isfinite(value):
                    missing.add(str(key))
                return value
            except Exception:
                missing.add(str(key))
                return float('nan')

        def fmt(value, percent=False):
            try:
                value = float(value)
                if not np.isfinite(value):
                    return '缺失/非有限值'
                return ('%.12g%%' % (value * 100)) if percent else ('%.12g' % value)
            except Exception:
                return '缺失/不可转换'

        def ratio(a, b):
            if not np.isfinite(a) or not np.isfinite(b) or b == 0:
                return float('nan')
            return a / b

        def truth(value):
            try:
                if pd.isna(value):
                    return '缺失，不能确认'
                return str(bool(value))
            except Exception:
                return '缺失，不能确认'

        def compare(a, op, b):
            if not np.isfinite(a) or not np.isfinite(b):
                return '缺失，不能确认'
            checks = {'>': lambda: a > b, '<': lambda: a < b,
                      '>=': lambda: a >= b, '<=': lambda: a <= b,
                      '==': lambda: a == b}
            return truth(checks[op]())

        def date_at(pos):
            row = df.iloc[pos]
            value = row.get('time', row.get('date', df.index[pos]))
            try:
                return str(value.date())
            except Exception:
                return str(value)

        def slope(period, pos=-1):
            row, lag = df.iloc[pos], df.iloc[pos - 5]
            current, old = num('ma%d' % period, row), num('ma%d' % period, lag)
            value = num('ma%d_slope' % period, row)
            return ('MA%d[%s]=%s，MA%d[%s]=%s；(当前MA−5行前MA)/5行前MA=%s；缓存斜率=%s' %
                    (period, date_at(pos), fmt(current), period, date_at(pos - 5), fmt(old),
                     fmt(ratio(current - old, old), True), fmt(value, True)))

        def volume_ratio_text(threshold, operator='<'):
            v, vm = num('volume'), num('volume_ma5')
            return ('V/(VMA5+0.0001)%s%s；V=%s，VMA5=%s，实际量比=%s' %
                    (operator, fmt(threshold), fmt(v), fmt(vm), fmt(num('volume_ratio'))))

        def deviation_text(period):
            c, ma = num('close'), num('ma%d' % period)
            return 'C=%s，MA%d=%s，(C−MA%d)/MA%d=%s，绝对偏离=%s' % (
                fmt(c), period, fmt(ma), period, period, fmt(ratio(c - ma, ma), True),
                fmt(py_abs(ratio(c - ma, ma)), True))

        def convergence_text(threshold):
            values = [num('ma%d' % p) for p in (5, 10, 20, 60)]
            return ('std(MA5,MA10,MA20,MA60,ddof=1)/(四均线均值+0.0001)<%s；四MA=[%s]，收敛度=%s' %
                    (fmt(threshold), ','.join(fmt(x) for x in values), fmt(num('ma_convergence'))))

        def spread_text(threshold):
            ma5, ma10, ma20 = num('ma5'), num('ma10'), num('ma20')
            a = ratio(py_abs(ma5 - ma10), ma10 + 0.0001)
            b = ratio(py_abs(ma10 - ma20), ma20 + 0.0001)
            return ('[|MA5−MA10|/(MA10+0.0001)]/[|MA10−MA20|/(MA20+0.0001)+0.0001]>%s；'
                    'MA5/10/20=%s/%s/%s，分子=%s，第二间距=%s，扩散比=%s' %
                    (fmt(threshold), fmt(ma5), fmt(ma10), fmt(ma20), fmt(a), fmt(b), fmt(num('ma_spread_ratio'))))

        def rsi_text():
            changes = df['close'].diff()
            gains = changes.where(changes > 0, 0).iloc[-14:].mean()
            losses = (-changes.where(changes < 0, 0)).iloc[-14:].mean()
            return ('RSI=100−100/[1+14行平均上涨/(14行平均下跌绝对值+0.0001)]；'
                    '平均上涨=%s，平均下跌=%s，RSI=%s' % (fmt(gains), fmt(losses), fmt(num('rsi_14'))))

        c, o, h, l, v = [num(k) for k in ('close', 'open', 'high', 'low', 'volume')]
        pc, po, pv = num('close', prev), num('open', prev), num('volume', prev)
        ma5, ma10, ma20, ma60 = [num('ma%d' % p) for p in (5, 10, 20, 60)]
        body = py_abs(c - o)
        lower = py_min(c, o) - l if np.isfinite(c) and np.isfinite(o) else float('nan')
        upper = h - py_max(c, o) if np.isfinite(c) and np.isfinite(o) else float('nan')
        candle = ('O/H/L/C=%s/%s/%s/%s；实体=|C−O|=%s，下影=min(O,C)−L=%s，上影=H−max(O,C)=%s；'
                  '占比均除(H−L+0.0001)=%s；实体/下影/上影占比=%s/%s/%s' %
                  (fmt(o), fmt(h), fmt(l), fmt(c), fmt(body), fmt(lower), fmt(upper), fmt(h - l + 0.0001),
                   fmt(num('body_ratio')), fmt(num('lower_shadow_ratio')), fmt(num('upper_shadow_ratio'))))

        def close_position_text(threshold):
            return ('(C−L)/(H−L+0.0001)>%s；C=%s，L=%s，H=%s，收盘位置=%s' %
                    (fmt(threshold), fmt(c), fmt(l), fmt(h), fmt(num('close_position'))))

        def hammer_text():
            lr, br, ur = num('lower_shadow_ratio'), num('body_ratio'), num('upper_shadow_ratio')
            return ('锤子线=(下影占比>0.5 且 实体占比<0.3 且 上影占比<0.1)；'
                    '下影=%s>%s:%s；实体=%s<%s:%s；上影=%s<%s:%s；缓存锤子线=%s' %
                    (fmt(lr), '0.5', compare(lr, '>', .5), fmt(br), '0.3', compare(br, '<', .3),
                     fmt(ur), '0.1', compare(ur, '<', .1), truth(latest.get('hammer'))))

        def engulfing_text():
            return ('阳包阴=(C>O 且 前C<前O 且 C>前O 且 O<前C)；'
                    '%s>%s:%s，%s<%s:%s，%s>%s:%s，%s<%s:%s；缓存阳包阴=%s' %
                    (fmt(c), fmt(o), compare(c, '>', o), fmt(pc), fmt(po), compare(pc, '<', po),
                     fmt(c), fmt(po), compare(c, '>', po), fmt(o), fmt(pc), compare(o, '<', pc),
                     truth(latest.get('engulfing'))))

        def divergence_text():
            lowclose, lowvolume = df['close'].iloc[-20:].min(), num('volume_min_20')
            return ('底背离=(C等于近20行最低收盘 且 V>近20行最低量×1.2)；'
                    'C=%s，最低收盘=%s，相等:%s；V=%s，最低量=%s，1.2倍=%s，量条件:%s；缓存=%s' %
                    (fmt(c), fmt(lowclose), compare(c, '==', lowclose), fmt(v), fmt(lowvolume),
                     fmt(lowvolume * 1.2), compare(v, '>', lowvolume * 1.2), truth(latest.get('divergence_bottom'))))

        def pulse_text():
            return ('not volume_pulse；缓存volume_pulse=%s；当前指标实现固定False，此边缘实际恒成立，不代表已完成脉冲识别' %
                    truth(latest.get('volume_pulse')))

        def volume_floor_text(multiplier):
            vm, minimum = num('volume_ma20'), num('volume_min_20')
            return ('V<%s×VMA20 或 |V−近20行最低量|<0.01；V=%s，VMA20=%s，倍数阈值=%s，分支一:%s；'
                    '最低量=%s，绝对差=%s，分支二:%s' %
                    (fmt(multiplier), fmt(v), fmt(vm), fmt(vm * multiplier), compare(v, '<', vm * multiplier),
                     fmt(minimum), fmt(py_abs(v - minimum)), compare(py_abs(v - minimum), '<', .01)))

        opening = float(item.get('open_chg', float('nan')))
        detail = {}
        if combo == 'combo_6':
            core, edge = standard_bull_conditions(latest, opening)
            core_met = py_sum(1 for value in core.values() if ComboEvaluator._safe_bool(value))
            edge_met = py_sum(1 for value in edge.values() if ComboEvaluator._safe_bool(value))
            score = standard_bull_display_score(edge_met, len(edge))
            passed = core_met == len(core) and standard_bull_edge_pass(edge_met)
        else:
            fn = getattr(ComboEvaluator, 'evaluate_' + str(combo))
            passed, score, core_met, edge_met = fn(latest, prev, details=detail)
            core, edge = detail.get('core'), detail.get('edge')
            if not isinstance(core, dict) or not isinstance(edge, dict):
                raise ValueError('正式评估器没有返回条件字典，不臆造条件通过情况')

        opening_pass = bool(np.isfinite(opening) and
                            ((3 <= opening <= 7) if combo == 'combo_3' else
                             (opening > 1.5 if combo == 'combo_6' else opening > 1)))
        names = getattr(g, 'display_names', {})
        label = stock + ('(' + str(names[stock]) + ')' if stock in names else '')
        consistent = (bool(passed) and opening_pass and py_abs(float(item['score']) - float(score)) < 1e-8 and
                      int(item['core_met']) == int(core_met) and int(item['edge_met']) == int(edge_met))
        if not consistent:
            log.warning('【形态复核不一致】%s | 原记录分/硬/边缘=%s/%s/%s，复核=%s/%s/%s；仅告警，不改候选或委托' %
                        (stock, item.get('score'), item.get('core_met'), item.get('edge_met'), score, core_met, edge_met))
        rows = {}

        if combo == 'combo_1':
            rows = {
                'ma20_shake': ('贴近MA20', '|C−MA20|/MA20<0.03；' + deviation_text(20)),
                'rsi_low': ('RSI偏低', 'RSI<40；' + rsi_text()),
                'volume_dry': ('地量', volume_floor_text(.6)),
                'slope_up': ('MA20斜率改善', '本行MA20斜率>前一行斜率；本行：' + slope(20) + '；前一行：' + slope(20, -2)),
                'convergence': ('均线收敛', convergence_text(.03)),
                'hammer': ('锤子线', hammer_text()),
                'divergence': ('量价底背离', divergence_text()),
                'close_pos': ('收盘位置', close_position_text(.6)),
                'pv_healthy': ('价量齐升', 'C>前C 且 V>前V；%s>%s:%s，%s>%s:%s；缓存=%s' %
                               (fmt(c), fmt(pc), compare(c, '>', pc), fmt(v), fmt(pv), compare(v, '>', pv), truth(latest.get('price_volume_healthy'))))}
        elif combo == 'combo_2':
            rows = dict(detail['condition_descriptions'])
        elif combo == 'combo_3':
            angle = num('price_ma_angle')
            rows = {
                'breakout': ('昨日上涨突破', 'R1=C/前C−1>4%%；C=%s，前C=%s，R1=%s' % (fmt(c), fmt(pc), fmt(num('returns_1d'), True))),
                'volume_surge': ('放量', volume_ratio_text(1.3, '>')),
                'ma_converge': ('均线收敛', convergence_text(.025)),
                'price_angle': ('价格偏离角度', 'atan([(C−MA20)/(MA20+0.0001)]×20)×180/π>25度；C=%s，MA20=%s，角度=%s度' %
                                (fmt(c), fmt(ma20), fmt(angle))),
                'ma_spread': ('均线扩散', spread_text(1.8)),
                'body_strong': ('实体强', '|C−O|/(H−L+0.0001)>0.5；实体=%s，实际占比=%s' % (fmt(body), fmt(num('body_ratio')))),
                'engulfing': ('阳包阴', engulfing_text()),
                'close_high': ('收盘靠近高点', close_position_text(.75)),
                'vol_stack': ('近期量增堆叠', '近5行中，V[t]>V[t−1]>V[t−2]的标志求和>=2；实际缓存和=%s' % fmt(num('volume_stack_days'))),
                'no_pump': ('非量脉冲', pulse_text())}
        elif combo == 'combo_4':
            rows=dict(detail['condition_descriptions'])
        elif combo == 'combo_5':
            r5, rsi = num('returns_5d'), num('rsi_14')
            r1 = num('returns_1d')
            rows = {
                'deep_fall': ('深跌或极低RSI', 'R5=C/C[5行前]−1<-6%% 或 RSI<28；C=%s，5行前C=%s，R5=%s，分支一:%s；%s，分支二:%s' %
                              (fmt(c), fmt(num('close', df.iloc[-6])), fmt(r5, True), compare(r5, '<', -.06), rsi_text(), compare(rsi, '<', 28))),
                'volume_freeze': ('量能冻结', volume_floor_text(.5)),
                'far_ma60': ('远低于MA60', '(C−MA60)/MA60<-0.06；' + deviation_text(60)),
                'ma_converge': ('均线收敛', convergence_text(.04)),
                'rebound': ('昨日反弹', 'R1=C/前C−1>0；C=%s，前C=%s，R1=%s' % (fmt(c), fmt(pc), fmt(r1, True))),
                'hammer_engulf': ('锤子或较强阳包阴形态', '锤子线 或 (阳包阴 且 R1>3%%)；%s；%s；R1=%s，R1>3%%:%s；本条件没有额外成交量要求' %
                                  (hammer_text(), engulfing_text(), fmt(r1, True), compare(r1, '>', .03))),
                'divergence': ('量价底背离', divergence_text()),
                'low_open_high': ('日内低开高收位置', '开盘位置=(O−L)/(H−L+0.0001)<0.3 且 收盘位置>0.6；开盘位置=%s，子项:%s；收盘位置=%s，子项:%s；缓存=%s' %
                                  (fmt(num('open_position')), compare(num('open_position'), '<', .3), fmt(num('close_position')), compare(num('close_position'), '>', .6), truth(latest.get('low_open_high_close')))),
                'ma_slope_recover': ('MA20斜率改善', '本行MA20斜率>前一行斜率；本行：' + slope(20) + '；前一行：' + slope(20, -2))}
        elif combo == 'combo_6':
            rows = {
                'ma_bull': ('均线多头', 'MA5>MA10>MA20；%s>%s>%s；两个子项=%s/%s' %
                            (fmt(ma5), fmt(ma10), fmt(ma20), compare(ma5, '>', ma10), compare(ma10, '>', ma20))),
                'volume_surge': ('放量', volume_ratio_text(1.2, '>')),
                'opening_strong': ('当日开盘偏强', '100×(固定当日开盘/昨收−1)>1.5；实际开盘涨幅=%s%%，昨收=%s，按该比率反算开盘=%s' %
                                   (fmt(opening), fmt(c), fmt(c * (1 + opening / 100)))),
                'opening_not_hot': ('开盘不过热', '开盘涨幅<5%%；实际=%s%%' % fmt(opening)),
                'volume_ma_bull': ('量均线多头', 'VMA5>VMA20；%s>%s' % (fmt(num('volume_ma5')), fmt(num('volume_ma20')))),
                'close_above_ma5': ('昨收高于MA5', 'C>MA5；%s>%s' % (fmt(c), fmt(ma5))),
                'upper_shadow_short': ('上影占比小', '[H−max(O,C)]/(H−L+0.0001)<0.3；上影=%s，实际占比=%s' % (fmt(upper), fmt(num('upper_shadow_ratio')))),
                'macd_positive': ('MACD柱为正', 'MACD柱=2×(DIF−DEA)>0；DIF=%s，DEA=%s，实际柱=%s；DIF=EMA12−EMA26，DEA=EMA9(DIF)' %
                                  (fmt(num('macd_dif')), fmt(num('macd_dea')), fmt(num('macd'))))}
        else:
            raise ValueError('未知形态' + str(combo))

        if combo == 'combo_2':
            ev = shape_activity_snapshot(stock, combo)
            rows['activity_10d'] = ('洗盘十日活跃硬门槛',
                '截至昨日完整十日；V=count(换手>2%%)，A=count((H−L)/前收>3.5%%)，Q=max(H/前收−1)；'
                '全部数据可核验且V>=1且[A>2或V>2或最大振幅>5.5%%或Q>5.5%%]；'
                '严格比较沿用活跃度1e-12机器容差；A=%s，V=%s，最大振幅=%s%%，Q=%s%%，'
                '第一层=%s，第二层=%s，可核验=%s，正式帧activity_wash_pass=%s，截至%s' %
                (ev.get('amplitude_count'), ev.get('turnover_count'), ev.get('peak_amplitude_percent'),
                 ev.get('peak_high_rise_percent'), ev.get('first_layer'), ev.get('second_layer'),
                 ev.get('available'), truth(latest.get('activity_wash_pass')), ev.get('asof')))
        if combo == 'combo_6':
            ev = shape_activity_snapshot(stock, combo)
            rows['spread_floor'] = ('均线扩散硬门槛', spread_text(.25))
            rows['activity_10d'] = ('十日两层活跃硬门槛',
                'A=振幅>3.5%%天数，V=换手>%s%%天数；要求V>=1且(V>2或A>2或最大振幅>%s%%)；A=%s，V=%s，最大振幅=%s%%，第一层=%s/第二层=%s，可核验=%s；截至%s' %
                (ev['turnover_threshold_percent'], ev['peak_threshold_percent'], ev['amplitude_count'], ev['turnover_count'],
                 ev['peak_amplitude_percent'], ev['first_layer'], ev['second_layer'], ev['available'], ev['asof']))
        if combo == 'combo_4':
            ev=shape_activity_snapshot(stock,combo)
            rows['activity_10d']=('主升十日四分支活跃硬条件',
                'V>=1且(A>2或V>2或最大振幅>5.5%%或最大冲高>5.5%%)；A=振幅>3.5%%天数，V=换手>2%%天数；'
                'A=%s，V=%s，最大振幅=%s%%，最大冲高=%s%%，第一层=%s，第二层=%s，可核验=%s，截至%s；严格阈值沿用1e-12机器容差' %
                (ev['amplitude_count'],ev['turnover_count'],ev['peak_amplitude_percent'],ev['peak_high_rise_percent'],
                 ev['first_layer'],ev['second_layer'],ev['available'],ev['asof']))
        if combo == 'combo_6':
            rows['price_location'] = ('价格相对短均线位置', 'C>MA5 或 MA5>=C>MA10×1.02；C/MA5/MA10=%s/%s/%s；两分支=%s/%s' %
                (fmt(c), fmt(ma5), fmt(ma10), truth(c > ma5), truth(ma5 >= c > ma10 * 1.02)))
            rows['slope_strong'] = ('短均线分段斜率', '(S5>2%且S10>1%)或(S5+S10>3.2%)；S5/S10均为五行变化率；' + slope(5) + '；' + slope(10) + '；斜率和=' + fmt(num('ma5_slope') + num('ma10_slope'), True))
            rows['close_not_far_ma5'] = ('昨收距MA5不过远', 'C/(MA5+0.0001)<1.07；C=%s，MA5=%s，比值=%s' %
                (fmt(c), fmt(ma5), fmt(ratio(c, ma5 + .0001))))
        condition_parts = []
        for group_name, conditions in (('硬条件', core), ('边缘条件', edge)):
            for number, (key, raw_value) in enumerate(conditions.items(), 1):
                name, calculation = rows.get(key, ('条件说明缺失', '正式条件键=' + str(key)))
                if key not in rows:
                    log.warning('【形态字段映射缺失】%s | %s；不能仅凭名称补写公式' % (stock, key))
                condition_parts.append('%s%d[%s/%s] 要求及计算:%s，符合:%s' %
                    (group_name, number, key, name, calculation, truth(raw_value)))

        if combo == 'combo_3':
            research=detail.get('research_hard',{})
            values=detail.get('research_values',{})
            formulas=detail.get('research_formulas',{})
            for number,(key,passed_raw) in enumerate(research.items(),1):
                condition_parts.append('附加硬R%d[%s] %s；实际=%s，符合:%s' %
                    (number,key,formulas.get(key,'公式缺失'),fmt(values.get(key)),truth(passed_raw)))
        subtype=(detail.get('zone_id','')+'/'+detail.get('zone_name','')+detail.get('zone_range','')) if combo=='combo_2' else \
                (detail.get('subtype_id','')+'/'+detail.get('subtype_name','') if combo=='combo_4' else '突破')
        qualification=('边缘至少%d/%d，原分只展示' % (detail['edge_required'],len(edge))) if combo=='combo_2' else \
                      ('边缘至少3/4，原分只展示' if combo=='combo_4' else '原分≥90且附加六硬全满足，原分优先')
        formula='75×%d/%d+25×%d/%d=%s' % (core_met,len(core),edge_met,len(edge),fmt(score))
        line='【形态条件复核】排名%d | %s | %s/%s | 昨日%s，前一完成行%s | %s | 开盘%s，实际%s%%，符合:%s | 评分%s；%s；复核合格:%s | 数字仅显示，布尔取正式未舍入结果' % \
            (rank,label,item.get('combo_name',combo),subtype,date_at(-1),date_at(-2),'；'.join(condition_parts),
             '3%≤涨幅≤7%' if combo=='combo_3' else '涨幅＞1%',fmt(opening),truth(opening_pass),formula,qualification,truth(passed))
        log.info(compact_log_text(line))
        if missing:
            log.warning('【形态底稿字段缺失】%s | %s；上方缺失值未替换成0；条件最终布尔仍为正式评估器返回值，须核查数据' %
                        (stock, ','.join(sorted(missing))))
    except Exception as exc:
        log.warning('【形态条件展示异常】%s | %s；只影响日志，不变更原候选/评分/交易' % (stock, str(exc)))

def activity_evidence_10d(adjusted, turnover, asof):
    """Reuse 11 cached daily OHLC rows for ten exact exchange-day amplitudes/high rises."""
    window = checked_daily(adjusted, asof).iloc[-11:]
    expected = entry_expected_dates(asof, 11)
    if len(expected) != 11 or len(window) != 11 or list(window.index.date) != expected:
        raise ValueError('活跃度日线未覆盖昨日及此前10个完整交易所日期，禁止用个股非停牌行替代')
    if not py_all(np.isfinite(float(x)) and float(x) > 0 for x in window.close):
        raise ValueError('活跃度前收/收盘价格不可核验')
    days = [str(x.date()) for x in window.index[-10:]]
    if not isinstance(turnover, pd.DataFrame) or not {'day', 'turnover_ratio'} <= set(turnover.columns):
        raise ValueError('历史换手率day/turnover_ratio字段缺失')
    table = turnover.copy()
    table['day'] = table['day'].map(lambda x: str(pd.Timestamp(x).date()))
    if table['day'].duplicated().any() or py_any(day > str(asof) for day in table['day']):
        raise ValueError('历史换手率日期重复或晚于昨日')
    if py_any(day not in days for day in table['day']):
        raise ValueError('历史换手率包含指定10日以外的日期；不以更早交易日替代停牌日')
    table = table.set_index('day')
    detail = []
    for i in range(1, 11):
        row = window.iloc[i]
        high, low, previous = float(row['high']), float(row['low']), float(window.close.iloc[i - 1])
        close, opening = float(row['close']), float(row['open'])
        paused, volume = float(row['paused']), float(row['volume'])
        if not np.isfinite(paused) or paused not in (0., 1.) or not np.isfinite(volume) or volume < 0:
            raise ValueError('十日活跃度停牌/成交量不可核验')
        if (paused == 1. and volume != 0.) or (paused == 0. and volume <= 0.):
            raise ValueError('十日活跃度停牌状态与成交量冲突')
        if (not py_all(np.isfinite(x) and x > 0 for x in (high, low, previous, close, opening))
                or high < py_max(close, opening, low) - 1e-8 or low > py_min(close, opening, high) + 1e-8):
            raise ValueError('十日活跃度OHLC缺失/次序异常')
        day = days[i - 1]
        raw_high_rise = high / previous - 1.
        raw_amplitude = (high - low) / previous
        if paused == 1.:
            known_turn = float(table.loc[day, 'turnover_ratio']) if day in table.index else float('nan')
            if np.isfinite(known_turn) and known_turn != 0.:
                raise ValueError('已停牌零成交日却报告非零历史换手率：' + day)
            # Verified paused AND zero volume is affirmative evidence of inactivity.
            # Raw OHLC-derived ratios are preserved separately; no missing value becomes 0.
            amplitude, turn, high_rise = 0., 0., 0.
            turn_source = '已核验停牌且成交量为0，不计振幅/换手/冲高达标；不由换手缺行推断停牌'
        else:
            if day not in table.index:
                raise ValueError('非停牌日历史换手率缺行：' + day)
            turn = float(table.loc[day, 'turnover_ratio'])
            if not np.isfinite(turn) or turn < 0:
                raise ValueError('非停牌日历史换手率缺失/负数：' + day)
            amplitude, high_rise = raw_amplitude, raw_high_rise
            turn_source = 'historical valuation.turnover_ratio (%)'
        detail.append(dict(day=day, open=opening, high=high, low=low, close=close, previous_close=previous,
                           amplitude=amplitude, high_rise=high_rise,
                           raw_amplitude=raw_amplitude, raw_high_rise=raw_high_rise,
                           turnover_percent=turn, paused=bool(paused), volume=volume, turnover_source=turn_source,
                           amplitude_pass=amplitude > .035 + 1e-12,
                           turnover_pass=turn > 2. + 1e-12))
    result = dict(available=True,
                  amplitude_count=int(py_sum(item['amplitude_pass'] for item in detail)),
                  turnover_count=int(py_sum(item['turnover_pass'] for item in detail)),
                  max_high_rise=float(py_max(item['high_rise'] for item in detail)),
                  days=detail, asof=str(asof), source='historical valuation.turnover_ratio (%)',
                  price_source='entry_adjusted_history: same frozen pre-adjusted OHLC frame, skip_paused=False',
                  high_rise_definition='H/previous_close-1; verified paused zero-volume day contributes 0; raw_high_rise retained')
    result['passed'] = activity_shape_rule(result, 'combo_4', asof)['passed']
    return result


def fetch_activity_turnover(stocks, asof):
    """按历史日期批量取换手；不允许用当前流通股本回算过去。"""
    api = globals().get('get_valuation')
    if callable(api):
        try:
            return selection_timed('activity_turnover_query', api, stocks, end_date=asof,
                                   count=10, fields=['turnover_ratio'])
        except Exception as exc:
            log.warning('【十日活跃度接口回退】get_valuation不可用:%s；改用显式截止昨日的连续市值表' % exc)
    request = query(valuation.code, valuation.turnover_ratio).filter(valuation.code.in_(stocks))
    return selection_timed('activity_turnover_query', get_fundamentals_continuously,
                           request, end_date=asof, count=10, panel=False)


def prime_activity_candidates(stocks, asof, current_data):
    """Probe each enabled shape without its own activity gate, then batch once."""
    if getattr(g, 'activity_asof', None) != str(asof):
        g.activity_asof = str(asof)
        g.activity_evidence = {}
        g.activity_rejection_logged = set()
    targets, possible_shapes = [], {}
    for stock in stocks:
        stock = str(stock)
        if stock in g.activity_evidence:
            continue
        df = g._micro_data_cache.get(stock)
        if df is None or len(df) < 11:
            continue
        df = attach_washout_timing_evidence(df, current_data[stock].day_open, asof)
        latest, previous = df.iloc[-1].copy(), df.iloc[-2]
        try:
            # Probe-only flags do not mutate the cached frame or final shape verdict.
            latest['activity_wash_pass'] = True
            latest['activity_main_pass'] = True
            latest['activity_standard_pass'] = True
            for field,value in main_opening_inputs(df,current_data[stock].day_open,asof)['fields'].items():
                latest[field]=value
            gap = (float(current_data[stock].day_open) / float(latest['close']) - 1.) * 100.
            possible, probe_errors = [], []
            for combo in ('combo_2', 'combo_4', 'combo_6'):
                if not combo_is_enabled(combo):
                    continue
                try:
                    if combo == 'combo_6':
                        core, edge = standard_bull_conditions(latest, gap)
                        ok = (py_all(ComboEvaluator._safe_bool(v) for v in core.values())
                              and standard_bull_edge_pass(py_sum(ComboEvaluator._safe_bool(v) for v in edge.values())))
                    elif gap > 1.:
                        evaluator = ComboEvaluator.evaluate_combo_2 if combo == 'combo_2' else ComboEvaluator.evaluate_combo_4
                        ok = bool(evaluator(latest, previous)[0])
                    else:
                        ok = False
                    if ok:
                        possible.append(combo)
                except Exception as exc:
                    # A broken/missing observation for one shape must not block another.
                    probe_errors.append(combo + ':' + str(exc))
            if possible:
                targets.append(stock)
                possible_shapes[stock] = possible
            else:
                g.activity_evidence[stock] = dict(available=False, passed=False, asof=str(asof),
                    error=('预核验失败:' + ';'.join(probe_errors) if probe_errors else '其余硬/边缘条件不合格，无需查询换手'),
                    skipped=not bool(probe_errors))
        except Exception as exc:
            g.activity_evidence[stock] = dict(available=False, passed=False, asof=str(asof), error='预核验失败:' + str(exc))
    for offset in range(0, len(targets), 200):
        batch = targets[offset:offset + 200]
        try:
            with selection_stage('activity_evaluate'):
                prime_entry_filter_history(batch, asof, True)
                table = fetch_activity_turnover(batch, asof)
                if not isinstance(table, pd.DataFrame) or not {'code', 'day', 'turnover_ratio'} <= set(table.columns):
                    raise ValueError('批量历史换手率没有code/day/turnover_ratio字段')
                grouped = selection_groups(table)
                for stock in batch:
                    try:
                        evidence = activity_evidence_10d(entry_filter_frame(stock, asof, True), grouped.get(stock), asof)
                    except Exception as exc:
                        evidence = dict(available=False, passed=False, asof=str(asof), error=str(exc))
                    g.activity_evidence[stock] = evidence
        except Exception as exc:
            for stock in batch:
                g.activity_evidence[stock] = dict(available=False, passed=False, asof=str(asof), error=str(exc))
            log.warning('【十日活跃度批量不可核验】%d只 | %s；洗盘/主升/标准对应硬条件不放行，不以0或当前换手替代历史数据' % (len(batch), exc))
    rejected, unknown, passed = [], [], []
    for stock in targets:
        snapshots = [shape_activity_snapshot(stock, combo, asof) for combo in possible_shapes[stock]]
        failures = [v for v in snapshots if not v['passed']]
        if failures:
            rejected.append(stock)
            if py_any(not v['available'] for v in failures):
                unknown.append(stock)
            if stock not in g.activity_rejection_logged:
                g.activity_rejection_logged.add(stock)
                payload = {ComboEvaluator.COMBO_CONFIG[v['combo']]['name']: json.loads(activity_snapshot_text(v)) for v in failures}
                log.info('【十日活跃度核验过滤】%s | 仅拒绝列示形态，其他形态仍按自身规则核验 | %s' %
                         (stock_label(stock), json.dumps(payload, ensure_ascii=False, separators=(',', ':'), allow_nan=False)))
        if py_any(v['passed'] for v in snapshots):
            passed.append(stock)
    if targets:
        log.info('【十日活跃度核验过滤汇总】预核验%d只 | 至少一种形态活跃合格%d只 | 存在未通过形态%d只(含不可核验%d只) | 排除明细:%s；均为截至昨日完整10个交易日' %
                 (len(targets), len(passed), len(rejected), len(unknown), [stock_label(s) for s in rejected]))


def attach_activity_evidence(stock, df, asof, current_data):
    df=attach_washout_timing_evidence(df,current_data[stock].day_open,asof)
    opening_fields=main_opening_inputs(df,current_data[stock].day_open,asof)['fields']
    for field,value in opening_fields.items():
        if field not in df.columns:df[field]=False if isinstance(value,bool) else float('nan')
        df.at[df.index[-1],field]=value
    if getattr(g, 'activity_asof', None) != str(asof) or stock not in getattr(g, 'activity_evidence', {}):
        prime_activity_candidates([stock], asof, current_data)
    for combo, field in (('combo_2', 'activity_wash_pass'), ('combo_4', 'activity_main_pass'), ('combo_6', 'activity_standard_pass')):
        if field not in df.columns:
            df[field] = False
        df.at[df.index[-1], field] = shape_activity_snapshot(stock, combo, asof)['passed'] if combo_is_enabled(combo) else False
    # Compatibility alias retains main-rule semantics, never washing-rule semantics.
    if 'activity_pass' not in df.columns:
        df['activity_pass'] = False
    df.at[df.index[-1], 'activity_pass'] = df.at[df.index[-1], 'activity_main_pass']
    return df





def position_atr_multiplier(context, book=None):
    """First actual-fill day is day 1; no calendar-day or signal-day counting."""
    if book is None:
        # Only used while initializing a genuinely new position from its first Trade.
        age = 1
    else:
        age = holding_days(context, book['entry_date'])
        if age < 1: raise ValueError('ATR持有交易日无效，不能臆造倍数')
    return g.cfg['atr_early_k'] if age <= g.cfg['atr_early_days'] else g.cfg['atr_k']


def provisional_tail_mas(context, stock, price, periods=(10, 20)):
    """14:54 provisional MA: N-1 completed closes plus the SAME current quote, fq=pre."""
    periods = tuple(sorted(set(int(n) for n in periods)))
    result = dict(price=price, asof=str(g.asof), at=str(context.current_dt), errors={})
    for n in periods: result['ma%d' % n] = None
    if context.current_dt.strftime('%H:%M') != '14:54': raise ValueError('临时尾盘MA仅14:54计算')
    if not np.isfinite(price) or price <= 0: raise ValueError('临时尾盘MA当前报价无效')
    count = py_max(periods) - 1
    key = (stock, str(g.asof), count)
    if not hasattr(g, 'tail_ma_history_cache'): g.tail_ma_history_cache = {}
    if key not in g.tail_ma_history_cache:
        frame = checked_daily(get_price(stock, end_date=g.asof, count=count, frequency='daily',
            fields=['close'], fq='pre', skip_paused=False), g.asof)
        g.tail_ma_history_cache[key] = frame
    frame = g.tail_ma_history_cache[key]
    # use_real_price=True gives current quotes and current pre-adjusted history one basis.
    # Cross-check the already validated prior close; do not calculate across mixed bases.
    previous = previous_close(stock)
    for n in periods:
        try:
            expected = [pd.Timestamp(d).date() for d in get_trade_days(end_date=g.asof, count=n-1)]
            tail = frame.tail(n-1)
            if len(expected) != n-1 or list(tail.index.date) != expected:
                raise ValueError('缺完整%d个已完成收盘/交易日错位' % (n-1))
            values = [float(v) for v in tail.close]
            if not py_all(np.isfinite(v) and v > 0 for v in values): raise ValueError('历史收盘价无效')
            if not np.isfinite(previous) or previous <= 0 or py_abs(values[-1]-previous) > .005 + 1e-10:
                raise ValueError('历史末收与已核验昨收基准不一致')
            result['ma%d' % n] = (py_sum(values)+price)/float(n)
        except Exception as exc: result['errors']['ma%d' % n] = str(exc)
    return result


def ordinary_tail_trend_session(context):
    """Ordinary exit only: combo_3/4/6. Its fills NEVER qualify as ATR buy credit."""
    if context.current_dt.strftime('%H:%M') != '14:54': return
    day = str(context.current_dt.date())
    current = get_current_data()
    for stock, book in list(g.book.items()):
        if book.get('strong_trend') or book.get('combo', {}).get('combo_type') not in ('combo_3', 'combo_4', 'combo_6'): continue
        if not exit_monitor_eligible(context, stock, book) or stock in g.basis_blocked: continue
        if book.get('ordinary_tail_trend_checked') == day: continue
        book['ordinary_tail_trend_checked'] = day
        try:
            cd = current[stock]; price = float(cd.last_price)
            if cd.paused or not np.isfinite(price) or price <= 0: raise ValueError('14:54报价无效/停牌')
            ma = provisional_tail_mas(context, stock, price)
            signals = dict(MA10=None, MA20=None)
            if ma['ma10'] is not None: signals['MA10'] = bool(price <= ma['ma10']*.97+1e-10)
            if ma['ma20'] is not None: signals['MA20'] = bool(price <= ma['ma20']*.995+1e-10)
            log.info('【普通趋势破位检查】%s | 14:54现价%.4f | 临时MA10:%s/MA20:%s | 现价<=MA10×0.97:%s/<=MA20×0.995:%s | 历史截至%s' %
                (stock_label(stock), price, ma['ma10'], ma['ma20'], signals['MA10'], signals['MA20'], g.asof))
            if ma['errors']: log.warning('【普通趋势破位数据缺失】%s | %s；仅使用可核验的独立均线条件' % (stock_label(stock), ma['errors']))
            labels = '/'.join(k for k,v in signals.items() if v is True)
            if not labels: continue
            # Preserve an already submitted/latched cause; never relabel an actual ATR order.
            reason = book.get('exit_reason') or ('14:54普通趋势破位退出:' + labels)
            book['exit_reason'] = reason
            book['ordinary_tail_trend_evidence'] = dict(day=day, signals=signals, values=ma)
            q = dict(price=price, high=price, time=context.current_dt, source='current_data_14:54', observed_at=context.current_dt)
            send_order(context, stock, 'sell', book['qty'], reason, q)
        except Exception as exc:
            log.warning('【普通趋势破位异常】%s | %s；不生成无证据退出，保留真实持仓' % (stock_label(stock), exc))


def acceleration_near_sealed(close, high, high_limit, day_return):
    """Only acceleration exits: exact close limit OR touched limit and final/known return>9%."""
    return bool(price_at_limit(close, high_limit) or
                (price_at_limit(high, high_limit) and day_return > .09+1e-12))


def log_micro_position_rules():
    """Static formula disclosure, no quotes/API calls and no score mutation."""
    log.info('【微观结构计算】上证000001.XSHG，截至昨日完成日线；S=趋势T+动量M+波动Q+结构U，理论最高130；盘前r=clip(S/100×波动乘数,0,1)，资金出逃/临时上限再取较小值')
    log.info('【微观/趋势T】排列：MA3>MA10>MA20>MA60得30，否则MA3>MA10>MA20得20，否则MA10>MA20得10，否则0；s=100×(MA20/5个交易日前MA20−1)，斜率分clip((s+2)×5,0,20)')
    log.info('【微观/趋势乖离】b=100×(昨收/MA20−1)；b>5得max(0,15−3×(b−5))，b<−5得min(20,2×abs(b))，其余15；趋势三项合计最高70')
    log.info('【微观/动量M】从30扣分且最低0：昨收>=10日最高收盘×0.998且近5均量<前5均量×0.85扣20；昨收>倒数第5行收盘且RSI14<倒数第5行RSI×0.98扣15；MACD(12,26,9)末柱>0且最近3柱递减扣10，可叠加')
    log.info('【微观/波动Q】q=ATR14/ATR60；q<0.8得20分/乘1；q>1.5得5分/乘0.5；否则q>1.2得10分/乘0.75；其余15分/乘1。四项分数先相加，再乘该系数')
    log.info('【微观/结构U】z=昨日指数成交量/含昨日5日均量；z>1.5且昨日涨停家数<30得2，否则z>1.5得5；否则z>1.2得10；否则z<0.7得3；其余8')
    log.info('【微观/风险上限】近3日>=2日收跌且量>前日1.1倍，盘前r封顶30%；盘中每5分钟采样，10分钟跌超1.5%封顶30%，11:30较昨收跌超1.5%封顶50%；取最严并锁定当天，有效r=min(盘前r,盘中上限)')
    log.info('【微观/数据窗口】趋势80/动量30/波动120/结构20/资金出逃5日；长度不足沿用20分/15分/(10分,乘1)/5分/未出逃。30根MACD预热限制保留，未另改分数')
    n=int(g.cfg['max_count']); divisor=unit_budget_divisor(); scaled=g.cfg['capacity_mode']=='legacy_scaled'
    slots=py_max(1,int(n*.8)) if scaled else n
    log.info('【仓位公式】持仓N=%d/入围K=%d/单笔分母D=%d，%s；单只标准预算B=NAV×r/D，总敞口上限NAV×r；三参数独立，固定名额版同样使用微观r，不是每天100%%仓位' % (n,g.cfg['selection_count'],divisor,'r>0名额=max(1,floor(N×r))，r=0无名额' if scaled else '固定N个名额，r=0禁止新增'))
    log.info('【预算落单】可买预算=min(B,总敞口上限−实际持仓市值−活跃买单余量预算−突破预留,真实可用现金−突破预留)；尾盘还受合格信用约束。剩余不足B允许小额，乘0.995缓冲后按限价百股取整并核对费用')
    log.info('【仓位示例】假设NAV=300000且r=80%%：最多%d只，单只标准%.2f元/%.4f%%，总预算上限240000元；空仓假设依次使用名额的建仓总额上限约%.4f%%（受总预算限制，未扣费用/百股舍入，不保证可填满名额）；这是假设算例，不是实际账户' % (slots,300000*.8/divisor,80./divisor,py_min(80.,slots*80./divisor)))
    log.info('【仓位实际影响】实际持仓/活跃买单/有效突破预留共同占位；不自动补足旧仓、不因新候选换股。日常r下降只约束新增；独立指数警报超限>NAV×0.5%才减非强趋势且非洗盘旧仓。T+1/强趋势或洗盘豁免/停牌/未成交可使实际仓位暂超目标')


def concept_exclusion_reason(name):
    # Only this exact label is removed BEFORE ranking. Earnings labels stay eligible.
    return '新股与次新股' if name == '新股与次新股' else None


def rolling_concept_counts(history,calendar,day):
    """Calendar must include exactly five completed/known observation days ending today."""
    if len(calendar)!=5 or calendar!=sorted(set(calendar)) or calendar[-1]!=day:
        raise ValueError('概念滚动交易日历必须完整5日并截至今日')
    if py_any(d not in history for d in calendar):raise ValueError('概念滚动池尚有缺失日期，禁止降级为短窗口')
    current=set(history[day]['pool']);rows=[]
    for name in sorted(set().union(*(set(history[d]['pool']) for d in calendar))):
        n5=py_sum(name in history[d]['pool'] for d in calendar)
        n3=py_sum(name in history[d]['pool'] for d in calendar[-3:])
        rows.append(dict(concept=name,n5=n5,n3=n3,today=name in current,
                         passed=name in current and (n5>=3 or n3>=2)))
    return rows


def concept_history_price(stocks,day,fields):
    frame=get_price(stocks,end_date=day,count=1,frequency='daily',fields=fields,
                    panel=False,fill_paused=False,skip_paused=False,fq=None)
    if frame is None or frame.empty or not set(['code','time']+list(fields))<=set(frame.columns):
        raise ValueError('概念历史补建行情缺失 '+str(day)+' '+str(fields))
    times=pd.to_datetime(frame['time'])
    if times.isna().any() or py_any(str(x.date())!=day for x in times):
        raise ValueError('概念历史补建行情日期不符 '+day)
    if frame['code'].astype(str).duplicated().any():raise ValueError('概念历史补建单日行情重复股票 '+day)
    return frame


def historical_concept_pool(day,asof):
    """Reconstruct H's 09:26 pool with H-1 membership and H's 09:15-09:25 auction.
    Never use current_data for a past day's ST, name or price limit; never use H's close to pick source stocks.
    Historical security names / extension concepts still depend on the platform's historical semantics.
    """
    if not (asof<day<str(g.day)):raise ValueError('概念补建日期必须早于当前回测日，且前收日期更早')
    started=time.perf_counter()
    securities=get_all_securities(types=['stock'],date=asof)
    observed=get_all_securities(types=['stock'],date=day)
    if securities is None or securities.empty or observed is None or observed.empty:
        raise ValueError('概念历史补建股票列表缺失 '+day)
    if 'start_date' not in securities.columns or 'display_name' not in observed.columns:
        raise ValueError('概念历史补建缺少上市日或历史名称 '+day)
    oldest=pd.Timestamp(asof).date()-dt.timedelta(days=50)
    stocks=sorted(str(s) for s in securities.index if not str(s).startswith(('4','8','68','92'))
                  and pd.Timestamp(securities.loc[s,'start_date']).date()<oldest and s in observed.index)
    if not stocks:raise ValueError('概念历史补建基础池为空 '+day)
    for stamp in (asof,day):
        st=get_extras('is_st',stocks,start_date=stamp,end_date=stamp,df=True)
        if st is None or st.empty or len(st)!=1 or str(pd.Timestamp(st.index[-1]).date())!=stamp:
            raise ValueError('概念历史补建ST日期/数据异常 '+stamp)
        stocks=[s for s in stocks if s in st.columns and not pd.isna(st[s].iloc[-1]) and not bool(st[s].iloc[-1])]
        if not stocks:raise ValueError('概念历史补建ST过滤后为空 '+stamp)
    paused=concept_history_price(stocks,asof,['paused'])
    stocks=sorted(set(paused.loc[paused.paused==0,'code'].astype(str))&set(stocks))
    stocks=[s for s in stocks if isinstance(observed.loc[s,'display_name'],str)
            and not py_any(x in observed.loc[s,'display_name'] for x in ('ST','退'))]
    if not stocks:raise ValueError('概念历史补建停牌/名称过滤后为空 '+day)
    prices=concept_history_price(stocks,asof,['close','high_limit']).dropna()
    yesterday=list(prices.loc[prices.close==prices.high_limit,'code'].astype(str))
    limits=concept_history_price(stocks,day,['high_limit']).set_index('code')['high_limit']
    cutoff=day+' 09:25:00';observed_at=pd.Timestamp(day+' 09:26:00')
    auction=get_call_auction(stocks,start_date=day+' 09:15:00',end_date=cutoff,fields=['time','current','volume'])
    if auction is None or auction.empty or not {'time','code','current','volume'}<=set(auction.columns):
        raise ValueError('概念历史补建竞价缺失或结构不符 '+day)
    auction=auction.copy();auction['time']=pd.to_datetime(auction['time'])
    if auction.time.isna().any() or auction.time.max()>observed_at or auction.time.min()<pd.Timestamp(day+' 09:15:00'):
        raise ValueError('概念历史补建竞价越过该日09:26可见边界 '+day)
    latest=auction.sort_values('time',kind='mergesort').groupby('code',sort=False).tail(1).set_index('code')
    top=[];money={}
    for s in stocks:
        if s not in latest.index:continue
        if s not in limits.index or not np.isfinite(float(limits.loc[s])) or float(limits.loc[s])<=0:
            raise ValueError('概念历史补建竞价股涨停价缺失 '+day+' '+s)
        limit=float(limits.loc[s]);quote=float(latest.loc[s,'current']);volume=float(latest.loc[s,'volume'])
        if not np.isfinite(quote) or not np.isfinite(volume) or volume<0:raise ValueError('概念历史补建竞价数值异常 '+day+' '+s)
        if quote>=limit*.998:top.append(s);money[s]=volume*limit
    # Isolate all global member/ranking caches touched by concepts/rank_concepts; restore even on error.
    fields=('day','asof','concepts','concept_evidence_asof','concept_member_evidence',
            'concept_rank_key','concept_rank_evidence','concept_replay_day')
    saved={k:(hasattr(g,k),getattr(g,k,None)) for k in fields}
    try:
        g.day=day;g.asof=asof;g.concepts={};g.concept_replay_day=day
        g.concept_evidence_asof=None;g.concept_member_evidence={};g.concept_rank_key=None;g.concept_rank_evidence={}
        previous=rank_concepts(yesterday);current=rank_concepts(top,money)
        pool=sorted(set(previous)|set(current))
        row=dict(day=day,asof=asof,pool=pool,origin='historical_rebuild',previous=previous,auction=current)
    finally:
        for k,(exists,value) in saved.items():
            if exists:setattr(g,k,value)
            elif hasattr(g,k):delattr(g,k)
    log.info('【概念历史补建】交易日%s | 成员截至%s | 昨日来源%d只/竞价来源%d只 | 昨日前4:%s/竞价前4:%s | 剔除后原始并集:%s | 耗时%.3f秒；未使用该日盘后收盘挑选来源，历史名称及概念依赖平台返回' %
             (day,asof,len(yesterday),len(top),previous,current,pool,time.perf_counter()-started))
    return row


def update_rolling_concept_pool(raw_pool):
    day=str(g.day)
    calendar=[str(pd.Timestamp(v).date()) for v in get_trade_days(end_date=day,count=6)]
    if len(calendar)!=6 or calendar!=sorted(set(calendar)) or calendar[-1]!=day:
        raise ValueError('概念补建需取得截至今日6个交易日(最早一日提供前收)，禁止使用自然日替代')
    window=calendar[-5:]
    history=dict(getattr(g,'concept_pool_history',{}))
    for i,hday in enumerate(window[:-1],start=1):
        if hday not in history:
            history[hday]=historical_concept_pool(hday,calendar[i-1])
            g.concept_pool_history=dict(history)  # cache only each successfully reconstructed date
    history[day]=dict(day=day,asof=str(g.asof),pool=sorted(set(raw_pool)),origin='live_observation')
    history={d:history[d] for d in window}  # one raw merged pool per exchange day, bounded to five
    rows=rolling_concept_counts(history,window,day)
    g.concept_pool_history=history;g.concept_rolling_evidence=rows
    for d in window:
        log.info('【概念滚动记录】交易日%s | 来源%s | 剔除后原始并集:%s' % (d,history[d]['origin'],history[d]['pool']))
    for r in rows:
        log.info('【概念滚动判定】%s | 当天上榜:%s | 五日%d/三日%d | 通过:%s' %
                 (r['concept'],r['today'],r['n5'],r['n3'],r['passed']))
    result=[r['concept'] for r in rows if r['passed']]
    log.info('【概念滚动池】含当日完整5个交易日%s | 当日原始并集:%s | 实际热门:%s | 条件:当天上榜且(五日>=3或三日>=2)；空池不补足不绕过' % (window,raw_pool,result))
    return result





def log_candidate_shape_observation(item, rank):
    """One dated line per candidate; own hard gates share authoritative evidence."""
    combo = item.get('combo_type')
    try:
        stock = str(item['stock'])
        hard_activity = combo in ('combo_2', 'combo_4', 'combo_6')
        snapshot = shape_activity_snapshot(stock, combo if hard_activity else 'combo_4')
        mode = '本形态硬条件' if hard_activity else '仅观察，参考2%换手口径，不据此筛选本形态'
        log.info('【十日活跃度统计】排名%d | %s | %s | %s' %
                 (rank, stock_label(stock), item.get('combo_name', combo) + ' | ' + mode, activity_snapshot_text(snapshot)))
    except Exception as exc:
        log.warning('【十日活跃度统计异常】%s | %s；只影响展示，不修改候选' % (item.get('stock'), exc))


def observation_json(value):
    """Observation transport: finite native JSON; never use missing values as zero."""
    def clean(x):
        if isinstance(x, dict): return {str(k): clean(v) for k, v in x.items()}
        if isinstance(x, (list, tuple)): return [clean(v) for v in x]
        if x is None: return None
        if isinstance(x, (bool, np.bool_)): return bool(x)
        if isinstance(x, (int, np.integer)): return int(x)
        if isinstance(x, (float, np.floating)):
            return float(x) if np.isfinite(x) else None
        if isinstance(x, (pd.Timestamp, dt.datetime, dt.date)): return str(x)
        return str(x)
    return json.dumps(clean(value), ensure_ascii=False, separators=(',', ':'), allow_nan=False)


def _v50_candidate_all_indicators(item, rank):
    """Finite, versioned T-1 observation snapshot; no API calls or strategy mutation."""
    stock = str(item['stock'])
    frame = getattr(g, '_micro_data_cache', {}).get(stock)
    if frame is None or len(frame) < 20: raise ValueError('指标观察冻结日线不足20行')
    dates = pd.DatetimeIndex(frame.index)
    if dates.has_duplicates or not dates.is_monotonic_increasing:
        raise ValueError('指标观察日线日期重复或未排序')
    if py_any(x.date() > pd.Timestamp(g.asof).date() for x in dates):
        raise ValueError('指标观察包含信号日前一交易日之后的数据')
    if dates[-1].date() != pd.Timestamp(g.asof).date():
        raise ValueError('指标观察末日不等于昨日，不能冒充昨日数据')
    last, prev = frame.iloc[-1], frame.iloc[-2]
    def number(x):
        try:
            x = float(x)
            return x if np.isfinite(x) else None
        except Exception: return None
    def val(key, row=last): return number(row.get(key))
    def safe_ratio(a, b, eps=0.):
        a, b = number(a), number(b)
        return a / (b + eps) if a is not None and b is not None and b + eps != 0 else None
    def mean_tail(series, count):
        values = [number(x) for x in series.iloc[-count:]]
        return py_sum(values) / count if len(values) == count and py_all(x is not None for x in values) else None
    def raw(row):
        # These are the exact columns of the frozen decision frame, not a second data query.
        return {str(k): (bool(v) if isinstance(v, (bool, np.bool_)) else number(v)) for k, v in row.items()}
    c, o, h, l, v = [val(k) for k in ('close', 'open', 'high', 'low', 'volume')]
    close, volume = frame['close'], frame['volume']
    slopes, slope_inputs = {}, {}
    for period in (5, 10, 20):
        for lag in (3, 5, 10, 15):
            key = 'MA%d_slope%d_ratio' % (period, lag)
            now = val('ma%d' % period)
            before = val('ma%d' % period, frame.iloc[-1-lag]) if len(frame) > lag else None
            result = safe_ratio(now, before)
            slopes[key] = result - 1. if result is not None else None
            slope_inputs[key] = dict(now=now, before=before, before_date=str(dates[-1-lag].date()))
    vm = {'VM%d' % n: mean_tail(volume, n) for n in (3, 5, 8, 10, 20)}
    v_ratios = {'V_over_VM%d_eps' % n: safe_ratio(v, vm['VM%d' % n], .0001) for n in (3, 5, 8, 10, 20)}
    mas = {n: val('ma%d' % n) for n in (5, 10, 20, 60)}
    convergence = {}
    for periods, name in (((5, 10, 20), 'ma3_convergence_ddof1'), ((5, 10, 20, 60), 'ma4_convergence_ddof1')):
        values = [mas[n] for n in periods]
        convergence[name] = float(np.std(values, ddof=1) / (np.mean(values) + .0001)) if py_all(x is not None for x in values) else None
    offset = {'C_vs_MA%d_ratio' % n: (safe_ratio(c, mas[n]) - 1. if safe_ratio(c, mas[n]) is not None else None) for n in (5, 10, 20)}
    ma_bull = mas[5] > mas[10] > mas[20] if py_all(mas[n] is not None for n in (5, 10, 20)) else None
    price_bull = c > mas[5] > mas[10] > mas[20] if c is not None and ma_bull is not None else None
    stack = {}
    for pos in range(-5, 0):
        a, b, cc = [val('volume', frame.iloc[pos-k]) for k in (0, 1, 2)]
        stack[str(dates[pos].date())] = dict(V=a, V_prev=b, V_prev2=cc,
            increasing=a > b > cc if py_all(x is not None for x in (a, b, cc)) else None)
    opening_pct = number(item.get('open_chg'))
    delta = close.diff()
    rsi_gain = delta.where(delta > 0, 0).rolling(14).mean()
    rsi_loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    ema12, ema26 = close.ewm(span=12, adjust=False).mean(), close.ewm(span=26, adjust=False).mean()
    shake_flags = (frame['ma5'].iloc[-6:] > frame['ma20'].iloc[-6:]).astype(int)
    supporting = dict(close_lag5=val('close', frame.iloc[-6]),
        rsi14_average_gain=number(rsi_gain.iloc[-1]), rsi14_average_loss=number(rsi_loss.iloc[-1]),
        ema12=number(ema12.iloc[-1]), ema26=number(ema26.iloc[-1]),
        recent6_ma5_above_ma20={str(d.date()):int(x) for d,x in shake_flags.items()},
        recent6_ma_cross_count=number(shake_flags.diff().abs().sum()),
        rsi_last5={str(d.date()):number(x) for d,x in frame['rsi_14'].iloc[-5:].items()},
        rsi_last5_std_ddof1=number(frame['rsi_14'].iloc[-5:].std(ddof=1)),
        recent10_close_range_ratio=safe_ratio(close.iloc[-10:].max()-close.iloc[-10:].min(),c,.0001),
        volume_last7={str(d.date()):number(x) for d,x in volume.iloc[-7:].items()})
    # Approved additions are observation only; compute using existing frozen rows.
    path = close.iloc[-11:]
    er_distance = number(path.iloc[-1] - path.iloc[0])
    er_length = number(path.diff().abs().iloc[1:].sum())
    er = safe_ratio(py_abs(er_distance), er_length) if er_distance is not None else None
    er_signed = safe_ratio(er_distance, er_length)
    if er_length == 0. and er_distance == 0.: er = er_signed = 0.
    if len(path) != 11 or not bool(np.isfinite(path).all()):
        er = er_signed = er_distance = er_length = None
    last15 = frame.iloc[-15:]
    tr = pd.concat([last15['high']-last15['low'],
                    (last15['high']-last15['close'].shift(1)).abs(),
                    (last15['low']-last15['close'].shift(1)).abs()], axis=1).max(axis=1).iloc[1:]
    atr_source_valid = bool(np.isfinite(last15[['high','low','close']].values).all()) and bool((last15[['high','low','close']].values > 0).all())
    atr_seed = number(tr.mean()) if len(tr) == 14 and bool(np.isfinite(tr).all()) and atr_source_valid else None
    atrp = safe_ratio(atr_seed, c)
    cmf_rows = frame.iloc[-20:]
    money_flow, cmf_volume, cmf_flat_days = [], [], 0
    for _, row in cmf_rows.iterrows():
        hh, ll, cc, vv = [val(key, row) for key in ('high','low','close','volume')]
        if not py_all(x is not None for x in (hh,ll,cc,vv)) or hh < ll or vv < 0 or not ll <= cc <= hh:
            money_flow = []; break
        multiplier = (2.*cc-hh-ll)/(hh-ll) if hh != ll else 0.
        if hh == ll: cmf_flat_days += 1
        money_flow.append(multiplier*vv); cmf_volume.append(vv)
    cmf = safe_ratio(py_sum(money_flow), py_sum(cmf_volume)) if len(money_flow) == 20 else None
    # 左侧结构仅观察：用已有冻结日线，不增加请求，不作为本轮硬/边缘条件。
    left_structure = {}
    for window in (15, 30):
        block = frame.iloc[-(window + 1):]
        key = 'last%d_changes' % window
        if len(block) != window + 1:
            left_structure[key] = dict(available=False, reason='冻结日线不足')
            continue
        prices = block[['open', 'high', 'low', 'close']].astype(float)
        valid = bool(np.isfinite(prices.values).all()) and bool((prices.values > 0).all())
        valid = valid and bool((prices.high >= prices[['open', 'close', 'low']].max(axis=1)).all())
        valid = valid and bool((prices.low <= prices[['open', 'close', 'high']].min(axis=1)).all())
        if not valid:
            left_structure[key] = dict(available=False, reason='价格缺失或OHLC不一致')
            continue
        changes = prices.iloc[1:]
        prior_close = prices.close.shift(1).iloc[1:]
        prior_low = prices.low.shift(1).iloc[1:]
        gaps = changes.open / prior_close - 1.
        full_gaps = changes.high / prior_low - 1.
        down_full = full_gaps[full_gaps < 0.]
        drawdown = prices.close / prices.close.cummax() - 1.
        trough = drawdown.idxmin()
        peak = prices.loc[:trough, 'close'].idxmax()
        left_structure[key] = dict(available=True, start=str(block.index[0].date()), end=str(block.index[-1].date()),
            close_return_ratio=number(prices.close.iloc[-1] / prices.close.iloc[0] - 1.),
            max_close_drawdown_ratio=number(drawdown.min()), drawdown_peak_date=str(peak.date()), drawdown_trough_date=str(trough.date()),
            close_vs_window_high_ratio=number(prices.close.iloc[-1] / changes.high.max() - 1.),
            close_vs_window_low_ratio=number(prices.close.iloc[-1] / changes.low.min() - 1.),
            min_open_gap_ratio=number(gaps.min()), min_open_gap_date=str(gaps.idxmin().date()),
            downward_full_gap_count=int(len(down_full)),
            largest_downward_full_gap_ratio=number(down_full.min()) if len(down_full) else 0.,
            full_gap_dates={str(day.date()): number(value) for day, value in down_full.items()},
            basis='window+1个收盘覆盖window个变化；回撤=收盘/此前累计最高收盘-1；开盘缺口=O/前C-1；完整向下缺口=H/前L-1<0；主升M1左30收盘回撤为硬门槛，其余左侧统计仅观察')
    added = dict(left_structure=left_structure, ER10=er, ER10_signed=er_signed, ER10_net_change=er_distance, ER10_path_length=er_length, ER10_zero_path=er_length==0. if er_length is not None else None,
        ATR14_seed_15rows=atr_seed, ATRP14_pct=atrp*100. if atrp is not None else None,
        CMF20=cmf, CMF20_volume_sum=py_sum(cmf_volume) if len(money_flow)==20 else None, CMF20_flat_days=cmf_flat_days if len(money_flow)==20 else None,
        basis='ER:11收盘/10变化；ATRP:15日线后14个TR均值/昨收，与现有15根ATR初始化口径一致，不改退出ATR；CMF:H=L乘子0；ER/ATRP/CMF仅观察，left_structure中M1左30回撤参与筛选')
    values = dict(slopes=slopes, slope_inputs=slope_inputs, volume_means=vm, volume_ratios=v_ratios,
        convergence=convergence, price_ma_offsets=offset, ma_bull=ma_bull, price_ma_bull=price_bull,
        opening_gap_pct=opening_pct, known_opening=number(item.get('known_day_open')),
        price_ma_angle_deg=val('price_ma_angle'), ma_spread_ratio=val('ma_spread_ratio'),
        rsi14_simple=val('rsi_14'), body_ratio=val('body_ratio'), upper_shadow_ratio=val('upper_shadow_ratio'),
        lower_shadow_ratio=val('lower_shadow_ratio'), close_position_ratio=val('close_position'),
        open_position_ratio=val('open_position'), macd_dif=val('macd_dif'), macd_dea=val('macd_dea'),
        macd_histogram=val('macd'), volume_stack5=val('volume_stack_days'), volume_stack_inputs=stack,
        recent20_min_close=number(close.iloc[-20:].min()), recent20_min_volume=number(volume.iloc[-20:].min()),
        previous_ma20_slope=val('ma20_slope', prev),
        real_body=py_abs(c-o) if c is not None and o is not None else None,
        lower_shadow=py_min(o,c)-l if py_all(x is not None for x in (o,c,l)) else None,
        upper_shadow=h-py_max(o,c) if py_all(x is not None for x in (o,c,h)) else None)
    if item.get('combo_type') == 'combo_2':
        values['washout_four_zones'] = washout_condition_evidence(last, prev)
        values['washout_economic'] = washout_economic_evidence(item, frame, g.asof)
        values['washout_economic']['ranking'] = dict(weights=item.get('tie_weights'), average_ranks=item.get('tie_average_ranks'), percentiles=item.get('tie_percentiles'), weighted_points=item.get('tie_weighted_points'), context=item.get('tie_rank_context'), score=item.get('tie_score'), raw_order=item.get('tie_raw_order'))
    if item.get('combo_type') == 'combo_4':
        values['main_dual_subtypes'] = main_condition_evidence(last,prev)
        values['main_opening_inputs'] = main_opening_inputs(frame,item.get('known_day_open'),g.asof)
        values['main_economic'] = item.get('main_economic_evidence') or main_economic_evidence(item,frame,g.asof)
        values['main_economic']['ranking'] = dict(weights=item.get('tie_weights'), average_ranks=item.get('tie_average_ranks'), percentiles=item.get('tie_percentiles'), weighted_points=item.get('tie_weighted_points'), context=item.get('tie_rank_context'), score=item.get('tie_score'), raw_order=item.get('tie_raw_order'))
    values['activity_10d'] = activity_observation_payload(stock, g.asof)
    research_hard,research_values,research_formulas=breakout_research_hard_conditions(last,prev)
    research_gate=dict(enabled=item.get('combo_type')=='combo_3',conditions=research_hard,values=research_values,formulas=research_formulas,passed=py_all(research_hard.values()),original_score_unchanged=True)
    return dict(schema='candidate-indicators/v0546',stock=stock,name=getattr(g,'display_names',{}).get(stock),signal_date=str(getattr(g,'day','')),
        asof=str(g.asof),shape=item.get('combo_name'),combo=item.get('combo_type'),rank=int(rank),
        score=item.get('score'),economic_score=item.get('tie_score'),observation_only=False,
        breakout_research_hard=research_gate,breakout_economic=item.get('breakout_economic'),
        priority=item.get('priority'),in_top_n=stock in getattr(g,'qs_combo_info',{}),economic_features=item.get('tie_features'),
        history_rows=len(frame),history_start=str(dates[0].date()),price_basis='same frozen pre-adjusted selection frame',
        row_dates=dict(yesterday=str(dates[-1].date()),previous=str(dates[-2].date())),
        raw_yesterday=raw(last),raw_previous=raw(prev),metrics=values,supporting=supporting,additional_observations=added,
        units='price=元; volume=平台股量; money=元; *_ratio和斜率为小数比例; *_pct为百分数; angle=度; RSI=0..100',
        slope_basis='n行前表示shift(n)，两端相隔n行；沿用形态冻结日线，停牌跳过时不冒充连续交易所日期',
        null_policy='缺失/非有限=JSON null，不用0代替；volume_pulse=false是沿用的常量而非实测脉冲')


def log_candidate_all_indicators(item, rank):
    # 实际运行版不调用重型只读观察构造；研究时将research_indicator_logs和log_all_indicators均设True，并同步初始化与账户配置。
    # 完整指标构造与序列化代码保留，不删减后续研究指标或决策缓存。
    if not g.cfg.get('research_indicator_logs', False): return
    if not g.cfg.get('log_all_indicators', True): return
    try:
        log.info('【所有指标统计】' + observation_json(candidate_all_indicators(item, rank)))
    except Exception as exc:
        log.warning('【所有指标统计不可核验】%s | %s；观察失败不影响原选股及订单' % (item.get('stock'), exc))


def ordinary_entry_shape_allowed(clock, combo):
    """形态专属首轮窗口；突破形态由独立延迟计划处理。"""
    kind = combo.get('combo_type') if isinstance(combo, dict) else combo
    if kind not in ('combo_1', 'combo_2', 'combo_4', 'combo_5', 'combo_6'):
        return False
    common = (entry_start(), g.cfg['late_buy_time'])
    return clock in common or (kind == 'combo_2' and clock == g.cfg.get('wash_buy_start_time', '09:45'))


def washout_late_entry_allowed(context, stock, price):
    """仅14:54洗盘新增买入门槛；缺历史/报价不买，不能把缺失当通过。"""
    if context.current_dt.strftime('%H:%M') != '14:54':
        return False
    try:
        ma = provisional_tail_mas(context, stock, float(price), (10,))
        ma10 = ma.get('ma10')
        if ma10 is None or not np.isfinite(ma10) or ma10 <= 0 or ma.get('errors'):
            raise ValueError('洗盘尾盘买入临时MA10不可核验:%s' % ma.get('errors'))
        if not np.isfinite(price) or price <= 0:
            raise ValueError('洗盘尾盘买入报价不可核验')
        passed = bool(price >= ma10 * .995)
        log.info('【洗盘尾盘买入MA核验】%s | 现价%.4f/临时MA10%.4f/0.995阈值%.4f | 通过:%s' %
                 (stock_label(stock), price, ma10, ma10 * .995, passed))
        return passed
    except Exception as exc:
        log.warning('【洗盘尾盘买入数据缺失】%s | %s；本窗口不新增该买单' % (stock_label(stock), exc))
        return False


def washout_completed_ma10(context, stock, end_date):
    """明确截止日的10个完整交易日收盘；每日缓存隔离复权观察日。"""
    end_date = str(pd.Timestamp(end_date).date())
    today = str(context.current_dt.date())
    if end_date > today or (end_date == today and context.current_dt.strftime('%H:%M') < '15:00'):
        raise ValueError('不能读取尚未完成的当日日线收盘')
    key = (stock, today, end_date)
    if not hasattr(g, 'wash_ma10_history_cache'):
        g.wash_ma10_history_cache = {}
    if key not in g.wash_ma10_history_cache:
        frame = checked_daily(get_price(stock, end_date=end_date, count=10, frequency='daily',
            fields=['close'], fq='pre', skip_paused=False), end_date)
        expected = [pd.Timestamp(day).date() for day in get_trade_days(end_date=end_date, count=10)]
        if len(expected) != 10 or len(frame) != 10 or list(frame.index.date) != expected:
            raise ValueError('洗盘观察缺完整10个交易日收盘或日期不一致')
        values = [float(v) for v in frame.close]
        if not py_all(np.isfinite(v) and v > 0 for v in values):
            raise ValueError('洗盘观察收盘价格无效')
        if end_date == str(g.asof):
            previous = previous_close(stock)
            if not np.isfinite(previous) or previous <= 0 or py_abs(values[-1] - previous) > .005 + 1e-10:
                raise ValueError('洗盘观察历史末收与已核验前收基准不一致')
        ma10 = py_sum(values) / 10.
        g.wash_ma10_history_cache[key] = dict(asof=end_date, valuation_day=today, close=values[-1], ma10=ma10,
            threshold=ma10 * .995, passed=bool(values[-1] >= ma10 * .995),
            dates=[str(d) for d in expected], completed_closes=values)
    return dict(g.wash_ma10_history_cache[key])


def record_washout_close_state(context):
    """买入首日收盘只保存观察证据，不委托卖出、不删除实际持仓。"""
    if context.current_dt.strftime('%H:%M') < '15:00':
        return
    day = str(context.current_dt.date())
    for stock, book in list(g.book.items()):
        if book.get('combo', {}).get('combo_type') != 'combo_2' or book.get('entry_date') != day:
            continue
        position = context.portfolio.positions.get(stock)
        if position is None or total_qty(position) <= 0 or stock in g.basis_blocked or book.get('strong_trend'):
            continue
        if book.get('wash_ma10_close_recorded') == day:
            continue
        try:
            evidence = washout_completed_ma10(context, stock, day)
            book['wash_ma10_entry_evidence'] = evidence
            book['wash_ma10_state'] = 'normal' if evidence['passed'] else 'awaiting_day2_tail'
            book['wash_ma10_close_recorded'] = day
            log.info('【洗盘首日收盘观察】%s | 收盘%.4f/MA10%.4f/0.995阈值%.4f | 首日突破:%s；只记录，次日盘前再核验，首日不卖' %
                     (stock_label(stock), evidence['close'], evidence['ma10'], evidence['threshold'], evidence['passed']))
        except Exception as exc:
            book['wash_ma10_state'] = 'evidence_unavailable'
            book['wash_ma10_entry_error'] = str(exc)
            log.warning('【洗盘首日收盘数据异常】%s | %s；保留实际持仓，次日盘前可重查，不据缺失安排退出' %
                        (stock_label(stock), exc))


def prepare_washout_states(context):
    """第二个持有交易日复核首日收盘；第三日起该一次性观察不再生成新信号。"""
    day = str(context.current_dt.date())
    for stock, book in list(g.book.items()):
        if book.get('combo', {}).get('combo_type') != 'combo_2':
            continue
        position = context.portfolio.positions.get(stock)
        if position is None or total_qty(position) <= 0 or stock in g.basis_blocked:
            continue
        if book.get('strong_trend'):
            book['wash_ma10_state'] = 'strong_exempt'
            continue
        try:
            age = holding_days(context, book['entry_date'])
            if age <= 1:
                continue
            if age > 2:
                if book.get('wash_ma10_state') in ('awaiting_day2_tail', 'evidence_unavailable'):
                    book['wash_ma10_state'] = 'observation_expired'
                    log.warning('【洗盘次日观察到期】%s | 第%d交易日仍未有完整MA10观察结论；不补造卖出，其他退出继续有效' %
                                (stock_label(stock), age))
                continue
            if book.get('wash_ma10_prepared_day') == day:
                continue
            if str(g.asof) != str(book['entry_date']):
                raise ValueError('第2持有交易日的前一交易日不等于首次买入日')
            evidence = washout_completed_ma10(context, stock, g.asof)
            book['wash_ma10_entry_evidence'] = evidence
            book['wash_ma10_state'] = 'normal' if evidence['passed'] else 'awaiting_day2_tail'
            book['wash_ma10_prepared_day'] = day
            log.info('【洗盘次日盘前观察】%s | 首日收盘%.4f/完整MA10%.4f/0.995阈值%.4f | 突破成功:%s | 次日14:54待观察:%s' %
                     (stock_label(stock), evidence['close'], evidence['ma10'], evidence['threshold'], evidence['passed'], not evidence['passed']))
        except Exception as exc:
            book['wash_ma10_state'] = 'evidence_unavailable'
            log.warning('【洗盘次日盘前数据异常】%s | %s；不推断突破失败，保留真实持仓及其他退出' % (stock_label(stock), exc))


def washout_tail_session(context):
    """第二持有交易日14:54，首日未确认突破者再比较现价与临时MA10。"""
    if context.current_dt.strftime('%H:%M') != '14:54':
        return
    day = str(context.current_dt.date())
    for stock, book in list(g.book.items()):
        if book.get('combo', {}).get('combo_type') != 'combo_2' or book.get('strong_trend'):
            continue
        if stock in g.basis_blocked or not exit_monitor_eligible(context, stock, book):
            continue
        position = context.portfolio.positions.get(stock)
        if position is None or total_qty(position) <= 0:
            continue
        if book.get('wash_ma10_state') != 'awaiting_day2_tail' or book.get('wash_ma10_tail_checked') == day:
            continue
        try:
            if holding_days(context, book['entry_date']) != 2:
                continue
            if g.cfg.get('wash_weak_priority', True) and observation_atr_exempt(context, book):
                book['wash_ma10_tail_checked'] = day
                book['wash_ma10_state'] = 'weak_recovery_priority'
                log.info('【洗盘次日观察让位】%s | 首日走弱次日14:55修复观察优先，本日不由洗盘MA10观察提前退出' % stock_label(stock))
                continue
            current = get_current_data()[stock]
            price = float(current.last_price)
            if current.paused or not np.isfinite(price) or price <= 0:
                raise ValueError('洗盘次日14:54报价无效/停牌')
            ma = provisional_tail_mas(context, stock, price, (10,))
            ma10 = ma.get('ma10')
            if ma10 is None or not np.isfinite(ma10) or ma10 <= 0 or ma.get('errors'):
                raise ValueError('洗盘次日临时MA10不可核验:%s' % ma.get('errors'))
            failed = bool(price < ma10)
            book['wash_ma10_tail_checked'] = day
            book['wash_ma10_tail_evidence'] = dict(day=day, price=price, ma10=ma10, failed=failed)
            book['wash_ma10_state'] = 'exit_pending' if failed else 'normal'
            log.info('【洗盘次日尾盘观察】%s | 现价%.4f/临时MA10%.4f | 低于MA10退出:%s；现价等于MA10视为成功，其他退出照常' %
                     (stock_label(stock), price, ma10, failed))
            if not failed:
                continue
            reason = book.get('exit_reason') or '14:54洗盘次日未收复MA10退出'
            book['exit_reason'] = reason
            q = dict(price=price, high=price, time=context.current_dt,
                     source='current_data_washout_14:54', observed_at=context.current_dt)
            send_order(context, stock, 'sell', book['qty'], reason, q)
        except Exception as exc:
            log.warning('【洗盘次日尾盘数据异常】%s | %s；保留真实持仓和已确认退出，不凭缺失新增卖出' % (stock_label(stock), exc))



def breakout_day_number(context, plan):
    dates = get_trade_days(start_date=plan['signal_day'], end_date=str(context.current_dt.date()))
    if not len(dates) or str(pd.Timestamp(dates[-1]).date()) != str(context.current_dt.date()): return 0
    return len(dates)


def breakout_window_allowed(context, plan):
    if plan.get('status') != 'reserved' or breakout_day_number(context,plan) != 2: return False
    if plan.get('signal_review_day') != str(context.current_dt.date()): return False
    branch = plan.get('signal_review',{}).get('branch')
    clock = context.current_dt.strftime('%H:%M')
    if branch == 'small_bearish': return clock in (entry_start(),'14:55')
    return branch in ('limit_up','bullish','large_bearish') and clock == '09:30'


def cancel_breakout_plan(context, stock, plan, reason):
    plan.update(status='cancel_pending',cancel_reason=reason)
    breakout_cancelled_today().add(stock)
    for oid,intent in list(g.orders.items()):
        if intent['stock']==stock and intent['side']=='buy' and not intent['terminal']:
            request_cancel(context,oid,reason)
    if not active_order(stock,'buy'):
        plan['status'] = 'expired' if plan.get('expiry_requested') else 'cancelled'
    log.info('【突破计划结束/待撤】%s | %s | 状态%s；活跃买单终态且真实成交核对完成后释放，真实book不删除' %
        (stock_label(stock),reason,plan['status']))






def record_breakout_close_observations(context):
    """Signal day=D1. Observe completed D3/D4; never use the same-day future close."""
    if context.current_dt.strftime('%H:%M') < '15:00': return
    day = str(context.current_dt.date())
    for stock, book in list(g.book.items()):
        if book.get('combo', {}).get('combo_type') != 'combo_3' or book.get('strong_trend') or stock in g.basis_blocked: continue
        signal = book.get('combo', {}).get('breakout_signal_day')
        if not signal or book.get('breakout_close_observed') == day: continue
        dates = [str(pd.Timestamp(d).date()) for d in get_trade_days(start_date=signal, end_date=day)]
        number = len(dates)
        if number not in (3, 4): continue
        try:
            frame = checked_daily(get_price(stock, end_date=day, count=8, frequency='daily',
                fields=['open', 'close', 'volume', 'paused'], fq='pre', skip_paused=False), day)
            expected = [pd.Timestamp(d).date() for d in get_trade_days(end_date=day, count=8)]
            if len(expected) != 8 or list(frame.index.date) != expected: raise ValueError('突破观察缺完整8日/交易日期错位')
            if not np.isfinite(frame[['open','close','volume','paused']].values.astype(float)).all(): raise ValueError('突破观察日线非有限')
            if bool((frame[['open','close']] <= 0).any().any()): raise ValueError('突破观察价格非正')
            signal_rows = frame.loc[pd.Timestamp(dates[0]):pd.Timestamp(dates[-1])]
            if len(signal_rows) != number or bool((signal_rows.paused != 0).any()) or bool((signal_rows.volume <= 0).any()):
                raise ValueError('突破观察段停牌/无量/缺日期，不臆造连续阴线')
            rows = [frame.loc[pd.Timestamp(d)] for d in dates]
            ma5_d3 = float(frame.close.loc[:pd.Timestamp(dates[2])].tail(5).mean())
            bearish = [float(row.close) < float(row.open)-1e-10 for row in rows]
            base = bearish[0] and bearish[1] and float(rows[1].close) < float(rows[0].close)-1e-10
            d3_below = float(rows[2].close) < ma5_d3-1e-10
            trigger = bool(base and bearish[2] and (d3_below if number == 3 else (not d3_below and bearish[3])))
            book['breakout_close_observed'] = day
            book['breakout_close_observation'] = dict(signal_day=signal, day_number=number,
                bearish=bearish, base_two_day_decline=bool(base), ma5_d3=ma5_d3,
                d3_below_ma5=bool(d3_below), trigger=trigger)
            log.info('【突破连续阴线观察】%s | 信号%s/第%d交易日 | 阴线序列%s | 前两日阴且第二收更低:%s | D3收%.3f/MA5%.3f | 次日09:30计划:%s' %
                (stock_label(stock), signal, number, bearish, base, float(rows[2].close), ma5_d3, trigger))
            if trigger and not book.get('close_exit_plan'):
                book['close_exit_plan'] = dict(reason='突破信号第%d日连续阴线走弱:次日开盘退出' % number,
                    signal_date=day, signal_age=holding_days(context, book['entry_date']), breakout_signal_day=signal,
                    evidence=dict(book['breakout_close_observation']))
        except Exception as exc:
            log.warning('【突破连续阴线观察缺证据】%s | %s；保留实际持仓和其他退出' % (stock_label(stock), exc))


def log_atr_trigger_evidence(context, stock, book, quote_value):
    """Log only once per actual trigger/unchanged pending intent, not every minute."""
    key = str(context.current_dt.date())
    if book.get('atr_trigger_logged') == key: return
    book['atr_trigger_logged'] = key
    data = dict(book.get('atr_last_update', {}))
    data.update(at=str(context.current_dt), asof=str(g.asof), price=float(quote_value['price']),
        high=float(book['high']), stop=float(book['stop']), holding_day=holding_days(context, book['entry_date']),
        multiplier=position_atr_multiplier(context, book), quote_time=str(quote_value.get('time')))
    book['atr_trigger_evidence'] = data
    log.info('【ATR触发依据】%s | %s' % (stock_label(stock), json.dumps(data, ensure_ascii=False, default=str, allow_nan=False)))

def enabled_combo_types():
    """Fixed research universe; priority comes from the unchanged shape configuration."""
    allowed = tuple('combo_%d' % i for i in range(1, 7))
    configured = g.cfg.get('enabled_combo_types', allowed)
    if not isinstance(configured, (tuple, list, set)) or not configured:
        raise ValueError('enabled_combo_types须为非空形态列表')
    if py_any(not isinstance(x, str) or x not in allowed for x in configured):
        raise ValueError('enabled_combo_types含未知形态，禁止静默切换')
    return tuple(sorted(set(configured), key=lambda x: ComboEvaluator.COMBO_CONFIG[x]['priority']))


def combo_is_enabled(combo_type):
    return combo_type in enabled_combo_types()


def use_concept_selection():
    value = g.cfg.get('use_concept_selection', True)
    if not isinstance(value, bool):
        raise ValueError('use_concept_selection须为True或False')
    return value


def selection_concept_ready():
    return not use_concept_selection() or bool(getattr(g, 'concept_ready', False))


def log_candidate_concepts_observation(stock):
    """Without concept gating, query only qualified names and never mutate selection on failure."""
    try:
        if not use_concept_selection():
            concepts(stock)
        log_candidate_concepts(stock)
    except Exception as exc:
        log.warning('【候选概念】%s | 观察数据不可核验:%s；不改变已合格候选、排名或委托' % (stock_label(stock), exc))


def breakout_limit_open_gap_allowed(context, stock, plan):
    """Compatibility gate: all morning branches use their fixed t+1 opening rules."""
    if plan.get('status') != 'reserved' or breakout_day_number(context,plan) != 2: return False
    if plan.get('signal_review_day') != str(context.current_dt.date()) or not plan.get('signal_review'): return False
    evidence = plan['signal_review']
    if evidence.get('branch') == 'small_bearish': return True
    if context.current_dt.strftime('%H:%M') < '09:30': return False
    try:
        current = get_current_data()[stock]; opening = float(current.day_open)
        if current.paused: raise ValueError('当日停牌')
        decision = breakout_next_day_action(evidence,opening,'09:30')
        plan['opening_review'] = dict(decision,opening=opening,observed_at=str(context.current_dt))
        if decision['action'] == 'cancel':
            cancel_breakout_plan(context,stock,plan,decision['reason']); return False
        if decision['action'] == 'block': raise ValueError(decision['reason'])
        return decision['action'] == 'buy'
    except Exception as exc:
        marker = (str(context.current_dt.date()),context.current_dt.strftime('%H:%M'))
        if plan.get('opening_review_error_at') != marker:
            plan['opening_review_error_at'] = marker
            log.warning('【突破开盘条件缺证据】%s | %s；本窗口不买' % (stock_label(stock),exc))
        return False

def breakout_research_hard_conditions(latest, prev):
    """Six extra gates from frozen completed rows; independent of original 4+6 score."""
    def number(row, key):
        try:
            value = float(row.get(key))
            return value if np.isfinite(value) else float('nan')
        except Exception:
            return float('nan')
    def ratio(a, b):
        return a / b if np.isfinite(a) and np.isfinite(b) and b != 0 else float('nan')
    c, h, l = [number(latest, key) for key in ('close', 'high', 'low')]
    ma5, ma10, ma20 = [number(latest, 'ma%d' % p) for p in (5, 10, 20)]
    atrp = number(latest, 'research_atrp14_pct')
    values = dict(
        close_high=(c - l) / (h - l + .0001) if py_all(np.isfinite(x) for x in (c, h, l)) else float('nan'),
        previous_volume_ratio=ratio(number(prev, 'volume'), number(prev, 'volume_ma5') + .0001),
        middle_volume_ratio=ratio(number(latest, 'volume_ma10'), number(latest, 'volume_ma20') + .0001),
        spread_ceiling=ratio(ratio(py_abs(ma5 - ma10), ma10 + .0001),
                             ratio(py_abs(ma10 - ma20), ma20 + .0001) + .0001),
        volume_ceiling=ratio(number(latest, 'volume'), number(latest, 'volume_ma5') + .0001),
        ma20_atr_extension=ratio(ratio(c, ma20) - 1., atrp / 100. + .0001))
    conditions = dict(close_high=bool(np.isfinite(values['close_high']) and values['close_high'] > .75))
    for key, ceiling in (('previous_volume_ratio', 2.), ('middle_volume_ratio', 1.2),
                         ('spread_ceiling', 4.), ('volume_ceiling', 2.5), ('ma20_atr_extension', 3.5)):
        conditions[key] = bool(np.isfinite(values[key]) and values[key] <= ceiling)
    formulas = dict(
        close_high='昨日(C-L)/(H-L+0.0001)>0.75；原边缘close_high继续计分',
        previous_volume_ratio='前一完成行V/(VMA5+0.0001)<=2；VMA5含该行',
        middle_volume_ratio='昨日VMA10/(VMA20+0.0001)<=1.2；均量含昨日',
        spread_ceiling='D=[abs(MA5-MA10)/(MA10+0.0001)]/[abs(MA10-MA20)/(MA20+0.0001)+0.0001]<=4',
        volume_ceiling='昨日V/(VMA5+0.0001)<=2.5；原H2>1.3同时保留',
        ma20_atr_extension='F06/R07=(C/MA20-1)/(ATRP14_pct/100+0.0001)<=3.5；ATRP14_pct=100*A/C；A=末15行后14TR简单均值')
    return conditions, values, formulas

def log_breakout_research_hard_conditions(stock, latest, prev, details, score, stage):
    """Research-only rejection traces; qualified candidates use one combined condition line."""
    if not g.cfg.get('research_indicator_logs', False): return
    try:
        hard, values, formulas = (details.get(key, {}) for key in
                                  ('research_hard', 'research_values', 'research_formulas'))
        if len(hard) != 6:
            raise ValueError('研究六硬明细缺失')
        parts = []
        for number, (key, passed) in enumerate(hard.items(), 1):
            value = values.get(key, float('nan'))
            rendered = '%.12g' % value if np.isfinite(value) else '缺失/非有限值'
            parts.append('R%d[%s] %s；实际=%s，符合:%s' %
                         (number, key, formulas[key], rendered, bool(passed)))
        log.info('【突破研究六硬】%s | %s | 昨日行=%s，前一完成行=%s | %s | 六硬全部通过:%s | '
                 '旧分=%.8f；仍按原4硬+6边缘计算，须原4硬全中且旧分>=90；六硬只附加AND，不改原分；同原分排序使用v0.5.45突破五经济次分' %
                 (stock, stage, getattr(latest, 'name', '冻结昨日'), getattr(prev, 'name', '前一完成行'),
                  '；'.join(parts), py_all(hard.values()), score))
    except Exception as exc:
        log.warning('【突破研究六硬展示异常】%s | %s；仅展示失败，不改筛选' % (stock, exc))

def breakout_next_day_branch(evidence):
    # Limit close always wins; equality of close/open belongs to a non-bullish branch.
    if evidence['closed_at_limit']: return 'limit_up'
    if evidence['signal_close_adjusted'] > evidence['signal_open_adjusted']: return 'bullish'
    if evidence['signal_close_adjusted'] >= evidence['previous_close_adjusted']: return 'small_bearish'
    return 'large_bearish'

def breakout_branch_label(branch):
    return {'limit_up':'涨停','bullish':'阳线','small_bearish':'小阴/平盘','large_bearish':'大阴'}.get(branch,'证据未齐')

def breakout_plan_deadline(branch):
    return '09:31' if branch in ('limit_up','bullish','large_bearish') else '14:56'

def breakout_next_day_action(evidence, opening, clock, price=None, today_low=None, early_low_check=True, entry_time='09:52'):
    """Pure strict-boundary branch decision. Unknown values block, equality is allowed.

    User confirmed the same two-day-low guard at the configured early time and 14:55.
    early_low_check remains explicit for isolated policy comparison tests.
    """
    try:
        keys = ('signal_open_adjusted','signal_close_adjusted','signal_low_adjusted',
                'previous_open_adjusted','previous_close_adjusted','signal_volume_shares','previous_volume_shares')
        values = {key:float(evidence[key]) for key in keys}
        if not py_all(np.isfinite(v) and v>0 for v in values.values()): raise ValueError('t/t-1完整量价缺失')
        if not isinstance(evidence.get('closed_at_limit'), (bool,np.bool_)): raise ValueError('t日真实收盘涨停证据缺失')
        if not isinstance(early_low_check,bool): raise ValueError('小阴09:52低点检查开关须为布尔值')
        branch = breakout_next_day_branch(evidence)
        def result(action,reason): return dict(action=action,reason=reason,branch=branch)
        if branch == 'large_bearish' and values['signal_volume_shares'] > values['previous_volume_shares']*1.5:
            return result('cancel','大阴分支t日成交量>t-1日成交量1.5倍')
        opening = float(opening)
        if not np.isfinite(opening) or opening <= 0: raise ValueError('t+1已知开盘价缺失')
        close = values['signal_close_adjusted']; previous = values['previous_close_adjusted']; previous_open = values['previous_open_adjusted']
        if branch in ('limit_up','bullish'):
            if branch == 'limit_up' and opening > close*1.02: return result('cancel','涨停分支t+1开盘>t收盘1.02倍')
            if opening < close*.95: return result('cancel','%s分支t+1开盘<t收盘0.95倍' % breakout_branch_label(branch))
            if opening < previous: return result('cancel','%s分支t+1开盘<t-1收盘' % breakout_branch_label(branch))
            return result('buy' if clock=='09:30' else 'wait','仅次日09:30市价；09:31撤余单结束')
        if branch == 'large_bearish':
            low = py_min(values['signal_low_adjusted'],opening)
            if low < previous*.955: return result('cancel','大阴分支min(t低,t+1开)<t-1收盘0.955倍')
            if low < previous_open: return result('cancel','大阴分支min(t低,t+1开)<t-1开盘')
            return result('buy' if clock=='09:30' else 'wait','仅次日09:30市价；09:31撤余单结束')
        if clock not in (entry_time,'14:55'): return result('wait','小阴分支仅次日%s/14:55执行' % entry_time)
        if clock == '14:55' or early_low_check:
            low_now = float(today_low)
            if not np.isfinite(low_now) or low_now <= 0: raise ValueError('t+1可核验低点缺失')
            low = py_min(values['signal_low_adjusted'],low_now)
            if low < previous*.97: return result('cancel','小阴分支两日最低<t-1收盘0.97倍')
            if low < previous_open: return result('cancel','小阴分支两日最低<t-1开盘')
        if clock == '14:55': return result('buy','小阴分支14:55两日低点未破底线，市价尝试')
        price = float(price)
        if not np.isfinite(price) or price <= 0: raise ValueError('%s当前报价缺失' % entry_time)
        if price > opening*1.02: return result('buy','小阴分支%s报价>当日开盘1.02倍，市价尝试' % entry_time)
        return result('wait','小阴分支%s报价未严格超过开盘1.02倍，等待14:55' % entry_time)
    except (KeyError,TypeError,ValueError) as exc:
        return dict(action='block',reason=str(exc),branch=None)

def breakout_buy_allowed(context, stock, plan, q):
    """Execution and send_order share this gate; neither can bypass branch rules."""
    if not breakout_window_allowed(context,plan): return False
    if stock in g.book or stock in g.sold_today: return False
    try:
        if str(g.asof) != str(plan['signal_day']): raise ValueError('次日同复权参考截止日与t日不符')
        fresh = deferred_entry_quote(context,stock)
        if fresh is None: return False
        q.update(fresh)
        evidence = plan['signal_review']; clock = context.current_dt.strftime('%H:%M')
        early = g.cfg.get('breakout_small_bear_early_low_check',True)
        low = None
        if evidence.get('branch') == 'small_bearish' and (clock=='14:55' or early):
            low_evidence = breakout_two_day_low_evidence(context,stock,plan,q['price'])
            plan['two_day_low_review'] = low_evidence; low = low_evidence['today_low']
        decision = breakout_next_day_action(evidence,q['day_open'],clock,price=q['price'],today_low=low,
            early_low_check=early,entry_time=entry_start())
        plan['last_entry_decision'] = dict(decision,at=str(context.current_dt),price=q['price'],opening=q['day_open'])
        if decision['action'] == 'cancel':
            cancel_breakout_plan(context,stock,plan,decision['reason']); return False
        if decision['action'] != 'buy':
            log.info('【突破本窗口不买】%s | %s' % (stock_label(stock),decision['reason'])); return False
        return True
    except Exception as exc:
        log.warning('【突破分支买前复核失败】%s | %s；阻止买入' % (stock_label(stock),exc))
        return False

def breakout_two_day_low_evidence(context, stock, plan, price):
    """Two-day low = completed signal-day low + verifiable current-session low.

    intraday_extrema verifies every completed minute through now-1 minute and
    includes today's known open/current quote. It never asks for t+1 daily OHLC.
    """
    if breakout_day_number(context,plan) != 2:
        raise ValueError('突破两日低点只能在信号次交易日核验')
    if plan.get('signal_review_day') != str(context.current_dt.date()):
        raise ValueError('突破两日低点缺少当前复权基准的完整t日日线')
    evidence = intraday_extrema(context,stock,current_price=price)
    if not evidence.get('valid'):
        raise ValueError('突破t+1截至此刻低点不可完整核验:%s' % evidence.get('error','缺失'))
    today_low = float(evidence['low']); signal_low = float(plan['signal_review']['signal_low_adjusted'])
    if not py_all(np.isfinite(v) and v>0 for v in (today_low,signal_low)):
        raise ValueError('突破两日低点非正或非有限')
    return dict(today_low=today_low,signal_low=signal_low,two_day_low=py_min(today_low,signal_low),
        through=evidence.get('through'),quote_at=evidence.get('quote_at'),
        note='仅已完成前一分钟+当日开盘/当前报价；并非逐tick最低价')


def main_opening_inputs(frame, day_open, asof):
    """已知开盘合成MA5，并把同一历史底稿前移至预核验和正式条件。

    All callers continue using ['fields']; therefore both
    prime_activity_candidates and attach_activity_evidence receive identical
    new hard-condition inputs before ComboEvaluator.evaluate_combo_4 runs.
    """
    from decimal import Decimal, localcontext
    fields = dict(main_known_day_open=float('nan'), main_opening_ma5=float('nan'),
                  main_opening_history_valid=False, main_opening_close_sum4=float('nan'),
                  main_opening_above_ma5=False, main_opening_relative_ma5=float('nan'),
                  main_opening_band_1_3=False)
    evidence = dict(fields=fields, closes4=[], dates4=[], asof=str(asof), error='',
                    formula='(冻结帧截至昨日最近4个已完成收盘行之和+当日已知day_open)/5；沿用skip_paused，不承诺连续交易所日期')
    try:
        opening = float(day_open)
        if not np.isfinite(opening) or opening <= 0:
            raise ValueError('day_open缺失/无效')
        fields['main_known_day_open'] = opening
        rows = frame.iloc[-4:]
        values = [float(x) for x in rows['close']]
        dates = [str(pd.Timestamp(x).date()) for x in rows.index]
        cutoff = str(pd.Timestamp(asof).date())
        evidence.update(closes4=values, dates4=dates, asof=cutoff)
        if len(rows) != 4 or len(set(dates)) != 4 or dates != sorted(dates) or dates[-1] != cutoff or py_any(d > cutoff for d in dates):
            raise ValueError('缺少截至昨日的4个完整、升序且唯一的收盘日期')
        if not py_all(np.isfinite(x) and x > 0 for x in values):
            raise ValueError('历史收盘缺失/非正数')
        with localcontext() as decimal_context:
            decimal_context.prec = 40
            exact_sum = py_sum(Decimal(str(v)) for v in values)
            exact_opening = Decimal(str(opening))
            total = exact_sum + exact_opening
            above = exact_opening * Decimal('4') > exact_sum
            # opening / ((sum4+opening)/5) in [1.01, 1.03), including exact 1%.
            lower = exact_opening * Decimal('5') >= total * Decimal('1.01')
            upper = exact_opening * Decimal('5') < total * Decimal('1.03')
            evidence['decimal_comparison'] = '4*day_open=%s > sum4=%s' % (exact_opening * Decimal('4'), exact_sum)
            evidence['opening_band_comparison'] = dict(
                opening_x5=str(exact_opening * Decimal('5')),
                lower_rhs=str(total * Decimal('1.01')),
                upper_rhs=str(total * Decimal('1.03')),
                lower_inclusive=bool(lower), upper_exclusive=bool(upper))
        opening_ma5 = (py_sum(values) + opening) / 5.
        fields.update(main_opening_ma5=opening_ma5, main_opening_history_valid=True,
                      main_opening_close_sum4=py_sum(values), main_opening_above_ma5=bool(above),
                      main_opening_relative_ma5=opening / opening_ma5 - 1.,
                      main_opening_band_1_3=bool(lower and upper))
    except Exception as exc:
        evidence['error'] = str(exc)
    history = main_history_inputs(frame, asof)
    fields.update(history['fields'])
    evidence['history'] = history
    return evidence


def main_condition_evidence(latest, prev):
    """正式判定、换手预核验和日志共用：两个互斥子型态＋原四边缘至少三。

    M1: C>MA5>MA10>MA20. M2: MA5>MA10>MA20, C>MA10 and
    0.975*MA5<=C<=MA5. C=MA5 belongs to M2; no .995 split remains.
    New historic hard inputs MUST be attached by main_opening_inputs before
    evaluation; absent inputs fail closed rather than being made up in logging.
    """
    def num(key, row=None):
        row = latest if row is None else row
        try:
            value = float(row[key])
            return value if np.isfinite(value) else float('nan')
        except (KeyError, TypeError, ValueError):
            return float('nan')
    def gt(a, b):
        return bool(np.isfinite(a) and np.isfinite(b) and a > b)
    def lt(a, b):
        return bool(np.isfinite(a) and np.isfinite(b) and a < b)
    def le(a, b):
        return bool(np.isfinite(a) and np.isfinite(b) and a <= b)
    def valid(key):
        return ComboEvaluator._safe_bool(latest.get(key, False))
    def fmt(value):
        return repr(float(value)) if np.isfinite(value) else '缺失/非有限值'

    c, o, low, ma5, ma10, ma20 = [num(k) for k in ('close', 'open', 'low', 'ma5', 'ma10', 'ma20')]
    s5, s10, s20 = [num(k) for k in ('ma5_slope', 'ma10_slope', 'ma20_slope')]
    spread, vr, volume, vm20 = [num(k) for k in ('ma_spread_ratio', 'volume_ratio', 'volume', 'volume_ma20')]
    opening, ma5_open = num('main_known_day_open'), num('main_opening_ma5')
    opening_valid = valid('main_opening_history_valid')
    ma_bull = gt(ma5, ma10) and gt(ma10, ma20)
    near_price = bool(ma_bull and gt(c, ma5))
    below_price = bool(ma_bull and gt(c, ma10) and
                       washout_relative_compare(c, ma5, -.025, '>=') and le(c, ma5))
    near_distance = washout_relative_compare(c, ma10, .035, '<')
    below_distance = washout_relative_compare(c, ma10, .03, '<')
    open_above = bool(opening_valid and gt(opening, 0) and gt(ma5_open, 0) and
                      valid('main_opening_above_ma5'))
    subtype = 'near5' if near_price else ('below5' if below_price else None)
    name = {'near5':'MA5附近回踩', 'below5':'MA5下方回踩'}.get(subtype, '不属于两种子型态')

    # Existing seven shared hard gates and all four original edges are unchanged.
    core = dict(bull_arrange=near_price if subtype == 'near5' else below_price if subtype == 'below5' else False,
                touch_ma10=near_distance if subtype == 'near5' else below_distance if subtype == 'below5' else False,
                ma_all_up=bool(gt(s5, 0) and gt(s10, 0) and gt(s20, 0)),
                vol_shrink=bool(np.isfinite(vr) and vr < .8),
                spread_floor=gt(spread, .25),
                above_ma20_safe=washout_relative_compare(c, ma20, .02, '>'),
                activity_10d=valid('activity_main_pass'))

    long_slope = num('main_ma10_slope10')
    lag10 = num('main_ma10_lag10')
    dd30 = num('main_left30_max_close_drawdown')
    dd_peak, dd_trough = num('main_left30_peak_close'), num('main_left30_trough_close')
    prior_shock = num('main_prior_up_volume_shock')
    previous_volume = num('volume', prev)
    volume_change = num('main_volume_over_previous')
    low_deviation = num('main_yesterday_low_over_ma10')
    opening_band = bool(opening_valid and valid('main_opening_band_1_3'))
    long_slope_pass = bool(valid('main_ma10_slope10_valid') and
                          washout_relative_compare(ma10, lag10, .01, '>'))
    drawdown_pass = bool(valid('main_left30_valid') and
                        washout_relative_compare(dd_trough, dd_peak, -.18, '>='))
    prior_shock_pass = bool(valid('main_prior_shock_valid') and le(prior_shock, .02))
    volume_change_pass = bool(valid('main_volume_change_valid') and
                             washout_relative_compare(volume, previous_volume + .0001, -.25, '>='))
    low_pass = bool(valid('main_yesterday_low_ma10_valid') and
                    washout_relative_compare(low, ma10, .01, '<='))
    if subtype == 'near5':
        core.update(opening_live_ma5_band=opening_band,
                    ma10_slope10_up=long_slope_pass,
                    left30_drawdown_cap=drawdown_pass,
                    prior_up_volume_shock_cap=prior_shock_pass)
    elif subtype == 'below5':
        core.update(opening_above_ma5=open_above,
                    yesterday_bullish=gt(c, o),
                    adjacent_volume_floor=volume_change_pass,
                    low_touch_ma10=low_pass,
                    ma5_slope5_cap=lt(s5, .08))

    edge = dict(shadow_or_close=bool(gt(num('lower_shadow_ratio'), .35) or gt(num('close_position'), .55)),
                ma_spread=gt(spread, 1.1),
                vol_healthy=gt(volume, vm20 * .4),
                slope_accelerate=main_slope_edge_condition(s5, s10))
    d = (c - ma10) / ma10 if np.isfinite(c) and np.isfinite(ma10) and ma10 > 0 else float('nan')
    price_formula = ('C>MA5>MA10>MA20' if subtype == 'near5' else
                     'MA5>MA10>MA20且C>MA10>MA20且0.975×MA5<=C<=MA5' if subtype == 'below5' else
                     'M1要求C>MA5；M2要求0.975×MA5<=C<=MA5且C>MA10；均须MA5>MA10>MA20')
    descriptions = {
        'bull_arrange': ('主升子型态价格链', price_formula + '；C/MA5/MA10/MA20=%s/%s/%s/%s；M1=%s，M2=%s' % (fmt(c), fmt(ma5), fmt(ma10), fmt(ma20), near_price, below_price)),
        'touch_ma10': ('有符号MA10距离', 'd=(C−MA10)/MA10；M1 d<3.5%%，M2 d<3%%；实际=%s，M1=%s，M2=%s' % (fmt(d), near_distance, below_distance)),
        'ma_all_up': ('三均线均向上', 'S5>0且S10>0且S20>0；五行斜率=%s/%s/%s' % (fmt(s5), fmt(s10), fmt(s20))),
        'vol_shrink': ('昨日缩量', 'V/(VMA5+0.0001)<0.8；实际=%s' % fmt(vr)),
        'spread_floor': ('均线扩散硬门槛', '[abs(MA5−MA10)/(MA10+0.0001)]/[abs(MA10−MA20)/(MA20+0.0001)+0.0001]>0.25；实际=%s' % fmt(spread)),
        'above_ma20_safe': ('MA20缓冲', 'C>MA20×1.02；C=%s，MA20=%s' % (fmt(c), fmt(ma20))),
        'activity_10d': ('主升十日四分支活跃', '可核验且V>=1且(A>2或V>2或最大振幅>5.5%或最大冲高>5.5%)；A=振幅>3.5%天数，V=换手>2%天数；activity_main_pass=' + str(core['activity_10d'])),
        'opening_live_ma5_band': ('M1开盘距临时MA5', '临时MA5=(截至昨日4收盘和+当日已知开盘)/5；1%%<=开盘/临时MA5−1<3%%；开盘=%s，临时MA5=%s，偏离=%s；边界用Decimal原值交叉比较；有效=%s' % (fmt(opening), fmt(ma5_open), fmt(num('main_opening_relative_ma5')), opening_valid)),
        'ma10_slope10_up': ('M1中期趋势向上', 'MA10[-1]/MA10[-11]−1>1%%；当前=%s，十行前=%s，斜率=%s；有效=%s' % (fmt(ma10), fmt(lag10), fmt(long_slope), valid('main_ma10_slope10_valid'))),
        'left30_drawdown_cap': ('M1左30收盘回撤', '31个完成收盘覆盖30个变化；min(C/截至该行累计最高C−1)>=−18%%；signed回撤=%s，峰收=%s，谷收=%s；有效=%s' % (fmt(dd30), fmt(dd_peak), fmt(dd_trough), valid('main_left30_valid'))),
        'prior_up_volume_shock_cap': ('M1前一完成行量价冲击', 'P=max(昨日之前一完成行涨幅,0)×该行V/(该行VMA5+0.0001)<=0.02；涨幅=%s，量比=%s，P=%s；有效=%s' % (fmt(num('main_previous_return_1d')), fmt(num('main_previous_volume_ratio5')), fmt(prior_shock), valid('main_prior_shock_valid'))),
        'opening_above_ma5': ('M2当日开盘站上临时MA5', 'day_open>(截至昨日4收盘和+day_open)/5；以4×day_open>4收盘和精确比较；开盘=%s，临时MA5=%s，有效=%s' % (fmt(opening), fmt(ma5_open), opening_valid)),
        'yesterday_bullish': ('M2昨日阳线', 'C>O；C=%s，O=%s；不以小实体/平盘代替阳线' % (fmt(c), fmt(o))),
        'adjacent_volume_floor': ('M2相邻成交量', '昨日V/(前一完成行V+0.0001)>=0.75，沿用静态证据口径；昨日V=%s，前一行V=%s，比例=%s；有效=%s' % (fmt(volume), fmt(previous_volume), fmt(volume_change), valid('main_volume_change_valid'))),
        'low_touch_ma10': ('M2昨日低点距MA10', '昨日L/昨日MA10−1<=1%%；L=%s，MA10=%s，偏离=%s；有效=%s' % (fmt(low), fmt(ma10), fmt(low_deviation), valid('main_yesterday_low_ma10_valid'))),
        'ma5_slope5_cap': ('M2短期涨速上限', 'MA5五行斜率<8%%；实际=%s' % fmt(s5)),
        'shadow_or_close': ('下影或收盘位置', '下影占比>0.35或收盘位置>0.55；两者=%s/%s' % (fmt(num('lower_shadow_ratio')), fmt(num('close_position')))),
        'ma_spread': ('边缘均线扩散', '均线扩散比>1.1；实际=%s' % fmt(spread)),
        'vol_healthy': ('量能不过低', 'V>VMA20×0.4；V=%s，VMA20=%s' % (fmt(volume), fmt(vm20))),
        'slope_accelerate': ('主升分段斜率', '(S5>2.8%%且S10>1%%)或[(S5<=2.8%%或S10<1%%)且S5+S10>3.3%%]；S5/S10/和=%s/%s/%s；S10恰1%%不自动进入回退' % (fmt(s5), fmt(s10), fmt(s5+s10)))
    }
    return dict(core=core, edge=edge, subtype_id=subtype, subtype_name=name,
                edge_required=3, condition_descriptions=descriptions,
                subtype_checks=dict(near5_price=near_price, near5_distance=near_distance,
                    near5_opening_band=opening_band, near5_slope10=long_slope_pass,
                    near5_left30=drawdown_pass, near5_prior_shock=prior_shock_pass,
                    below5_price=below_price, below5_distance=below_distance, below5_opening=open_above,
                    below5_bullish=gt(c,o), below5_adjacent_volume=volume_change_pass,
                    below5_low=low_pass, below5_slope_cap=lt(s5,.08)),
                values=dict(close=c, open=o, low=low, ma5=ma5, ma10=ma10, ma20=ma20,
                    d=d, scaled_ma5_near=ma5, scaled_ma5_below=.975*ma5,
                    s5=s5, s10=s10, s20=s20, slope_sum=s5+s10, spread=spread,
                    volume_ratio5=vr, known_day_open=opening, ma5_at_open=ma5_open,
                    opening_history_valid=opening_valid, opening_above_ma5=open_above,
                    opening_vs_live_ma5=num('main_opening_relative_ma5'), ma10_slope10=long_slope,
                    left30_max_close_drawdown=dd30, prior_up_volume_shock=prior_shock,
                    adjacent_volume_ratio=volume_change, yesterday_low_ma10=low_deviation),
                scoring_formula='原分75×硬条件命中率+25×边缘命中率；全部适用硬条件且四条边缘至少3条；子型态同优先级',
                boundary_basis='M1严格C>MA5；M2两端包含0.975MA5和MA5且严格C>MA10；开盘MA5偏离[1%,3%)；比例边界用Decimal(str原始值)交叉比较，不加宽容差；P按冻结帧量价乘积<=0.02',
                time_basis='所有日线指标仅截至昨日冻结帧；两类都使用当日已知竞价开盘合成临时MA5；P取昨日之前一完成行，非信号日')


def main_candidate_metadata(latest, prev):
    evidence = main_condition_evidence(latest, prev)
    values = evidence['values']
    return dict(main_subtype_id=evidence['subtype_id'], main_subtype_name=evidence['subtype_name'],
                main_deviation_ma10=values['d'], main_edge_required=evidence['edge_required'],
                main_edge_total=len(evidence['edge']), main_core_total=len(evidence['core']),
                main_condition_version='v0539', main_known_day_open=values['known_day_open'],
                main_opening_ma5=values['ma5_at_open'],
                main_opening_vs_live_ma5=values['opening_vs_live_ma5'],
                main_ma10_slope10=values['ma10_slope10'],
                main_left30_drawdown=values['left30_max_close_drawdown'],
                main_prior_up_volume_shock=values['prior_up_volume_shock'],
                main_adjacent_volume_ratio=values['adjacent_volume_ratio'],
                main_yesterday_low_ma10=values['yesterday_low_ma10'])


def main_shape_display_name(combo,fallback='缺失'):
    name=combo.get('combo_name',fallback)
    if combo.get('combo_type')=='combo_2':
        zone=combo.get('washout_zone_id')
        detail=' '.join(str(x) for x in (zone,combo.get('washout_zone_name'),combo.get('washout_zone_range')) if x)
        return name+' / '+detail if detail and (not zone or str(zone) not in name) else name
    subtype=combo.get('main_subtype_name') if combo.get('combo_type')=='combo_4' else None
    return name+' / '+subtype if subtype and subtype not in name else name


def main_history_inputs(frame, asof):
    """One frozen-frame source for pre-probe, final main conditions and evidence.

    MA10 ten-row slope uses shift(10), not ten calendar days. Left-30 drawdown
    uses 31 closes / 30 observed changes, matching the preceding study exactly.
    P uses the row BEFORE yesterday (usually T-2), not yesterday or today's gap.
    Missing evidence fails only its corresponding hard gate; it is never zero.
    """
    fields = dict(
        main_history_dates_valid=False,
        main_ma10_slope10_valid=False, main_ma10_slope10=float('nan'),
        main_ma10_lag10=float('nan'),
        main_left30_valid=False, main_left30_max_close_drawdown=float('nan'),
        main_left30_peak_close=float('nan'), main_left30_trough_close=float('nan'),
        main_prior_shock_valid=False, main_prior_up_volume_shock=float('nan'),
        main_previous_return_1d=float('nan'), main_previous_volume_ratio5=float('nan'),
        main_volume_change_valid=False, main_volume_over_previous=float('nan'),
        main_yesterday_low_ma10_valid=False, main_yesterday_low_over_ma10=float('nan'))
    result = dict(schema='main-history-inputs/v0539', fields=fields,
                  asof=str(asof), row_dates={}, errors={}, inputs={},
                  basis='仅冻结选股帧；S10十行=MA10[-1]/MA10[-11]-1；左30用31收盘覆盖30变化；P取昨日之前一完成行；不新增请求')

    def finite(value, positive=False, nonnegative=False):
        value = float(value)
        if not np.isfinite(value):
            raise ValueError('非有限数值')
        if positive and value <= 0:
            raise ValueError('要求正数')
        if nonnegative and value < 0:
            raise ValueError('要求非负数')
        return value

    try:
        if frame is None or len(frame) < 3:
            raise ValueError('至少需要三个已完成日线行')
        dates = pd.DatetimeIndex(frame.index)
        cutoff = pd.Timestamp(asof).date()
        if dates.hasnans or dates.has_duplicates or not dates.is_monotonic_increasing:
            raise ValueError('冻结日线日期缺失、重复或未排序')
        date_values = [x.date() for x in dates]
        if len(set(date_values)) != len(date_values):
            raise ValueError('同一交易日期出现多行')
        if date_values[-1] != cutoff or py_any(day > cutoff for day in date_values):
            raise ValueError('冻结帧末日必须为asof，且不得含asof之后数据')
        latest, previous = frame.iloc[-1], frame.iloc[-2]
        result['row_dates'] = dict(yesterday=str(date_values[-1]),
                                   previous=str(date_values[-2]),
                                   previous_previous=str(date_values[-3]))
        result['asof'] = str(cutoff)
        fields['main_history_dates_valid'] = True
    except Exception as exc:
        result['errors']['dates'] = str(exc)
        return result

    try:
        if len(frame) < 11:
            raise ValueError('MA10十行斜率缺少第11行锚点')
        now = finite(latest['ma10'], positive=True)
        before = finite(frame.iloc[-11]['ma10'], positive=True)
        fields.update(main_ma10_slope10_valid=True,
                      main_ma10_slope10=now / before - 1., main_ma10_lag10=before)
        result['inputs']['ma10_slope10'] = dict(now=now, before=before,
                    before_date=str(dates[-11].date()), lag_rows=10)
    except Exception as exc:
        result['errors']['ma10_slope10'] = str(exc)

    try:
        block = frame.iloc[-31:]
        if len(block) != 31:
            raise ValueError('左30日回撤需要31行完整OHLC')
        prices = block[['open', 'high', 'low', 'close']].astype(float)
        if not bool(np.isfinite(prices.values).all()) or not bool((prices.values > 0).all()):
            raise ValueError('左30日价格缺失或非正')
        if not bool((prices.high >= prices[['open', 'close', 'low']].max(axis=1)).all()):
            raise ValueError('左30日最高价不符合OHLC关系')
        if not bool((prices.low <= prices[['open', 'close', 'high']].min(axis=1)).all()):
            raise ValueError('左30日最低价不符合OHLC关系')
        closes = prices.close
        drawdowns = closes / closes.cummax() - 1.
        trough = drawdowns.idxmin()
        peak = closes.loc[:trough].idxmax()
        peak_price, trough_price = float(closes.loc[peak]), float(closes.loc[trough])
        fields.update(main_left30_valid=True,
                      main_left30_max_close_drawdown=float(drawdowns.min()),
                      main_left30_peak_close=peak_price, main_left30_trough_close=trough_price)
        result['inputs']['left30'] = dict(start=str(block.index[0].date()),
                    end=str(block.index[-1].date()), close_rows=31, change_rows=30,
                    peak_date=str(peak.date()), trough_date=str(trough.date()),
                    peak_close=peak_price, trough_close=trough_price,
                    max_close_drawdown_ratio=float(drawdowns.min()))
    except Exception as exc:
        result['errors']['left30'] = str(exc)

    try:
        # Reuse the exact original decision-frame pct_change value. Do not
        # silently substitute yesterday's return or a separately fetched series.
        ret = finite(previous['returns_1d'])
        prev_volume = finite(previous['volume'], nonnegative=True)
        prev_vm5 = finite(previous['volume_ma5'], positive=True)
        prev_ratio = prev_volume / (prev_vm5 + .0001)
        shock = py_max(ret, 0.) * prev_ratio
        fields.update(main_prior_shock_valid=True, main_prior_up_volume_shock=shock,
                      main_previous_return_1d=ret, main_previous_volume_ratio5=prev_ratio)
        result['inputs']['prior_up_volume_shock'] = dict(date=str(dates[-2].date()),
                    return_1d=ret, volume=prev_volume, volume_ma5=prev_vm5,
                    volume_ratio5=prev_ratio, value=shock,
                    formula='max(前一完成行returns_1d,0)*前一完成行V/(前一完成行VMA5+0.0001)')
    except Exception as exc:
        result['errors']['prior_up_volume_shock'] = str(exc)

    try:
        current_volume = finite(latest['volume'], nonnegative=True)
        previous_volume = finite(previous['volume'], nonnegative=True)
        fields.update(main_volume_change_valid=True,
                      main_volume_over_previous=current_volume / (previous_volume + .0001))
        result['inputs']['volume_change'] = dict(yesterday_volume=current_volume,
                    previous_volume=previous_volume, yesterday=str(dates[-1].date()),
                    previous=str(dates[-2].date()), denominator_epsilon=.0001)
    except Exception as exc:
        result['errors']['volume_change'] = str(exc)

    try:
        low = finite(latest['low'], positive=True)
        ma10 = finite(latest['ma10'], positive=True)
        fields.update(main_yesterday_low_ma10_valid=True,
                      main_yesterday_low_over_ma10=low / ma10 - 1.)
        result['inputs']['yesterday_low_ma10'] = dict(low=low, ma10=ma10)
    except Exception as exc:
        result['errors']['yesterday_low_ma10'] = str(exc)
    return result


def main_economic_evidence(item, frame, asof=None):
    """主升五项30/10/10/30/20次分；冻结昨日历史和当日已知开盘，无额外行情请求。"""
    def number(value):
        try:
            value = float(value)
            return value if np.isfinite(value) else float('nan')
        except (ValueError, TypeError):
            return float('nan')
    row = frame.iloc[-1]
    opening = main_opening_inputs(frame, item.get('known_day_open'), asof)
    fields = opening['fields']
    c, o, h, l, ma5, v, vm5 = [number(row.get(key)) for key in
                               ('close', 'open', 'high', 'low', 'ma5', 'volume', 'volume_ma5')]
    opening_price = number(fields.get('main_known_day_open'))
    live_ma5 = number(fields.get('main_opening_ma5'))
    valid_ohlc = (py_all(np.isfinite(x) and x > 0 for x in (c,o,h,l)) and
                  h >= py_max(c,o,l) and l <= py_min(c,o,h))
    volume_ratio = v / (vm5 + .0001) if np.isfinite(v) and v >= 0 and np.isfinite(vm5) and vm5 > 0 else float('nan')
    close_position = (c-l)/(h-l+.0001) if valid_ohlc else float('nan')
    signed_body = (c-o)/(h-l+.0001) if valid_ohlc else float('nan')
    deviation = c/ma5-1. if np.isfinite(c) and c > 0 and np.isfinite(ma5) and ma5 > 0 else float('nan')
    volume_target_distance = py_abs(volume_ratio-.60)
    deviation_distance = py_abs(deviation)
    open_deviation = opening_price/live_ma5-1. if fields.get('main_opening_history_valid') and live_ma5 > 0 else float('nan')
    names = ('negative_volume_ratio5_target060_distance', 'close_position', 'signed_body_ratio',
             'negative_relative_ma5_absolute_distance', 'negative_open_live_ma5_target02_distance')
    vector = [-volume_target_distance, close_position, signed_body, -deviation_distance, -py_abs(open_deviation-.02)]
    missing = []
    dates = [str(pd.Timestamp(x).date()) for x in frame.index]
    cutoff = str(pd.Timestamp(asof).date()) if asof is not None else None
    row_valid = bool(cutoff is not None and dates and dates[-1] == cutoff and
                     dates == sorted(dates) and len(set(dates)) == len(dates) and py_all(d <= cutoff for d in dates))
    if not row_valid:
        vector = [float('nan')] * 5
        missing.append('冻结日线日期不完整或晚于昨日')
    if not valid_ohlc: missing.append('昨日OHLC不可核验')
    if not fields.get('main_opening_history_valid'): missing.append('当日开盘合成MA5不可核验')
    for name,value in zip(names,vector):
        if not np.isfinite(value): missing.append('次分缺失:'+name)
    clean = lambda value: float(value) if np.isfinite(value) else None
    return dict(schema='main-economic/v0548', names=list(names), weights=[.30,.10,.10,.30,.20],
                vector=[clean(x) for x in vector], valid=not missing, missing=missing,
                raw_inputs=dict(asof=cutoff, historical_window_valid=row_valid,
                    yesterday_close=clean(c), yesterday_open=clean(o), yesterday_high=clean(h), yesterday_low=clean(l),
                    yesterday_ma5=clean(ma5), yesterday_volume=clean(v), yesterday_vma5=clean(vm5),
                    volume_ratio5_eps=clean(volume_ratio), close_position=clean(close_position), signed_body_ratio=clean(signed_body),
                    relative_ma5_deviation=clean(deviation), relative_ma5_absolute_distance=clean(deviation_distance),
                    volume_target060_distance=clean(volume_target_distance), known_day_open=clean(opening_price), provisional_ma5_at_open=clean(live_ma5),
                    open_to_provisional_ma5_minus1=clean(open_deviation), open_target02_distance=clean(py_abs(open_deviation-.02)),
                    historical_closes4=opening.get('closes4'), historical_dates4=opening.get('dates4')),
                formulas=['-abs(V/(VMA5+0.0001)-0.60)，越大越优', '(C-L)/(H-L+0.0001)，越大越优',
                          '(C-O)/(H-L+0.0001)，带符号，越大越优',
                          '-abs(C/MA5-1)，越大越优；正负对称、越贴近MA5越优',
                          '-abs(day_open/MA5_open-1-0.02)，越大越优'],
                direction='五项平均秩百分位按30/10/10/30/20加权；所有方向向量越大越优',
                scope='全部合格combo_4跨M1/M2及93.75/100统一排名；不单独分配子型态名额',
                tie_break='同经济次分按1→5未舍入方向向量；全同按代码，原分不再参与排序',
                units='所有偏离、实体、位置均为小数比例；量比无量纲', future_data_used=False)



def log_main_economic_ranking(item, rank):
    if item.get('combo_type') != 'combo_4': return
    evidence=item.get('main_economic_evidence',{})
    definitions=(
        ('negative_volume_ratio5_target060_distance','abs(V/(VMA5+0.0001)−0.60)','volume_target060_distance','越小越优',.30),
        ('close_position','(C−L)/(H−L+0.0001)','close_position','越大越优',.10),
        ('signed_body_ratio','(C−O)/(H−L+0.0001)','signed_body_ratio','越大越优，阳正阴负',.10),
        ('negative_relative_ma5_absolute_distance','abs(C/MA5−1)','relative_ma5_absolute_distance','越小越优',.30),
        ('negative_open_live_ma5_target02_distance','abs(开盘/临时MA5−1−0.02)','open_target02_distance','越小越优',.2))
    log.info(compact_log_text('【主升五项次分】排名%d | %s | %s | 合计%s分；全部合格主升跨原分排名，同分依1→5再代码' %
        (rank,stock_label(item['stock']),compact_economic_terms(item,evidence,definitions),compact_log_value(item.get('tie_score')))))


def candidate_shape_r15_allowed(stock, combo_type, asof):
    """R15依形态决定；主升豁免，其他形态在优先级归类前判定，以便回退下一形态。"""
    if combo_type == 'combo_4' or not g.cfg.get('entry_acceleration_filter', True): return True
    try:
        prime_entry_filter_history([stock], asof, adjusted=True)
        frame = verified_entry_window(entry_filter_frame(stock, asof, True), asof, 16, activity_count=6)
        values = pd.to_numeric(frame['close'].iloc[-16:], errors='coerce')
        if len(values) != 16 or not np.isfinite(values).all() or (values <= 0).any():
            raise ValueError('R15需要16个完整有效收盘')
        r15 = float(values.iloc[-1]/values.iloc[0]-1.)
        threshold = .40 if is_growth_board(stock) else .37
        if r15 > threshold + 1e-12:
            log.info('【形态R15排除】%s | %s | R15=%.2f%%>%.2f%%；仅拒绝该形态，继续检查其他启用形态' %
                     (stock_label(stock),combo_type,r15*100,threshold*100))
            return False
        return True
    except Exception as exc:
        log.warning('【形态R15不可核验】%s | %s | %s；该形态不通过' % (stock_label(stock),combo_type,exc))
        return False


def activity_observation_payload(stock, asof=None):
    """Read-only dated ten-day payload for all-indicator logs; performs no API calls."""
    if asof is None:
        asof = getattr(g, 'asof', None)
    evidence = getattr(g, 'activity_evidence', {}).get(str(stock), {})
    snapshots = {combo: activity_shape_rule(evidence, combo, asof) for combo in ('combo_2', 'combo_4', 'combo_6')}
    known = snapshots['combo_2']['available']
    rows = evidence.get('days', []) if known else []
    def finite(value):
        try:
            number = float(value)
            return number if np.isfinite(number) else None
        except (TypeError, ValueError):
            return None
    fields = ('open', 'high', 'low', 'close', 'previous_close', 'volume', 'amplitude',
              'high_rise', 'raw_amplitude', 'raw_high_rise', 'turnover_percent')
    by_date = {str(row['day']): dict({key: finite(row.get(key)) for key in fields},
                                   paused=bool(row.get('paused')), turnover_source=row.get('turnover_source')) for row in rows}
    return dict(schema='activity-observation/v0532', stock=str(stock), asof=str(asof),
                available=bool(known), days=by_date, shape_rules=snapshots,
                high_rise_percent_by_date=snapshots['combo_2']['high_rise_percent_by_date'],
                max_high_rise_percent=snapshots['combo_2']['peak_high_rise_percent'],
                price_source=evidence.get('price_source'), source=evidence.get('source'),
                units='amplitude/high_rise为小数；turnover_percent及*_percent为百分数',
                paused_policy='核验paused=1且volume=0的日期保留，活跃度有效值为0；原始OHLC比例另列raw_*',
                missing_policy='不可核验不填0，不改变候选，只展示真实缓存',
                error=snapshots['combo_2'].get('error', ''))


def washout_relative_compare(price, reference, boundary, operator):
    """比较price/reference−1与边界；Decimal仅避免商/差运算残差，不加epsilon。

    原MA的已有小数残差仍保留，不用“近似相等”擅自改写严格条件。
    """
    from decimal import Decimal, localcontext
    try:
        price, reference, boundary = float(price), float(reference), float(boundary)
        if not py_all(np.isfinite(x) for x in (price, reference, boundary)) or reference <= 0:
            return False
        with localcontext() as decimal_context:
            decimal_context.prec = 40
            left = Decimal(str(price))
            right = Decimal(str(reference)) * (Decimal('1') + Decimal(str(boundary)))
            if operator == '>': return bool(left > right)
            if operator == '>=': return bool(left >= right)
            if operator == '<': return bool(left < right)
            if operator == '<=': return bool(left <= right)
            raise ValueError('洗盘比较操作符非法: ' + str(operator))
    except (TypeError, ValueError, ArithmeticError):
        return False


def washout_zone(close, ma10):
    """完整日线四区间；两端开区间，内部界值归右区，不额外改变形态优先级。"""
    if not (washout_relative_compare(close, ma10, -.05, '>') and
            washout_relative_compare(close, ma10, .005, '<')):
        return None
    if washout_relative_compare(close, ma10, -.03, '<'): return 'G1'
    if washout_relative_compare(close, ma10, -.017, '<'): return 'G2'
    if washout_relative_compare(close, ma10, -.006, '<'): return 'G3'
    return 'G4'


def washout_condition_evidence(latest, prev):
    """洗盘正式条件、展示公式与计算底稿的唯一来源；不请求行情、不修改状态。"""
    def number(row, key):
        try:
            value = float(row[key])
            return value if np.isfinite(value) else float('nan')
        except (KeyError, TypeError, ValueError):
            return float('nan')
    def finite_gt(left, right):
        return bool(np.isfinite(left) and np.isfinite(right) and left > right)
    def ratio(left, right):
        return left / right if np.isfinite(left) and np.isfinite(right) and right > 0 else float('nan')
    def display(value):
        return repr(float(value)) if np.isfinite(value) else '缺失/非有限值'
    c, o, h, low = [number(latest, k) for k in ('close', 'open', 'high', 'low')]
    ma5, ma10, ma20 = [number(latest, k) for k in ('ma5', 'ma10', 'ma20')]
    s5, s10 = [number(latest, k) for k in ('ma5_slope', 'ma10_slope')]
    rsi, volume, vm5, vm8, vr5 = [number(latest, k) for k in ('rsi_14', 'volume', 'volume_ma5', 'volume_ma8', 'volume_ratio')]
    previous = number(prev, 'close')
    body, lower = number(latest, 'body_ratio'), number(latest, 'lower_shadow_ratio')
    zone = washout_zone(c, ma10)
    zones = {'G1': ('深度回调', '(-5%,-3%)'), 'G2': ('中度回调', '[-3%,-1.7%)'),
             'G3': ('浅度回调', '[-1.7%,-0.6%)'), 'G4': ('企稳区', '[-0.6%,+0.5%)')}
    zone_name, zone_range = zones.get(zone, ('区间外/不可核验', '(-5%,+0.5%)之外或数据无效'))
    rsi_upper = {'G1': 60., 'G2': 62., 'G3': 62.5, 'G4': 65.}.get(zone, float('nan'))
    timing = latest.get('washout_timing_evidence')
    timing = timing if isinstance(timing, dict) else {}
    timing_checks = timing.get('checks', {})
    timing_keys = {'G2': ('g2_prev_above_ma20',),
                   'G3': ('g3_open_ma5_floor', 'g3_prev_volume_floor'),
                   'G4': ('g4_open_ma5_ceiling', 'g4_ma10_slope_ceiling')}.get(zone, ())
    vr5 = ratio(volume, vm5 + .0001)
    vr8 = ratio(volume, vm8 + .0001)
    shrink_vma5 = bool(np.isfinite(vr5) and vr5 < .76)
    shrink_vma8 = bool(np.isfinite(vr8) and vr8 < .75)
    no_pulse_value = latest.get('volume_pulse')
    try:
        no_pulse = bool(pd.notna(no_pulse_value) and not bool(no_pulse_value))
    except (TypeError, ValueError):
        no_pulse = False
    old_slope = finite_gt(s5, s10)
    new_slope = bool(old_slope or (finite_gt(ma5, ma10) and finite_gt(s5, .006)))
    bullish = finite_gt(c, o)
    deep_low_near = bool(washout_relative_compare(low, ma20, -.003, '>=') and
                         washout_relative_compare(low, ma20, .003, '<='))
    crosses = {name: bool(finite_gt(ma, low) and finite_gt(h, ma))
               for name, ma in [('MA5', ma5), ('MA10', ma10), ('MA20', ma20)]}
    cross_count = py_sum(crosses.values())
    stop_fall = wash_stop_fall_condition(latest, prev)
    activity_pass = ComboEvaluator._safe_bool(latest.get('activity_wash_pass', False))
    core = {
        'touch_ma10': zone is not None,
        'above_ma20': washout_relative_compare(c, ma20, .005, '>'),
        'rsi_neutral': bool(np.isfinite(rsi) and np.isfinite(rsi_upper) and 45 < rsi < rsi_upper),
        'stop_fall': stop_fall,
        'activity_10d': activity_pass
    }
    edge = {
        'ma_bull': bool(finite_gt(ma5, ma20) and finite_gt(ma10, ma20)),
        'volume_shrink': bool(shrink_vma5 or shrink_vma8),
        'no_pulse': no_pulse
    }
    if zone in ('G3', 'G4'):
        core['shallow_slope'] = new_slope
        edge_required = 2
    else:
        edge['slope_diff'] = old_slope
        edge_required = 3
    if zone == 'G1': core['deep_ma20_bullish'] = bool(deep_low_near and bullish)
    if zone == 'G4': core['stabilization_bullish'] = bool(cross_count >= 2 and bullish)
    for key in timing_keys:
        core[key] = ComboEvaluator._safe_bool(timing_checks.get(key, False))
    d = ratio(c - ma10, ma10)
    low_offset = ratio(low, ma20) - 1.
    small_body = ratio(py_abs(c-o), previous + .0001)
    descriptions = {
        'touch_ma10': ('MA10四区间', '-5%%<d=(C−MA10)/MA10<+0.5%%；C=%s，MA10=%s，d=%s，所属%s/%s/%s；内部界值归右区，使用原始值Decimal交叉比较、不加epsilon' % (display(c), display(ma10), display(d), zone, zone_name, zone_range)),
        'above_ma20': ('站上MA20缓冲', 'C>MA20×1.005；C=%s，MA20=%s，倍数阈值=%s；原始十进制交叉比较' % (display(c), display(ma20), display(ma20*1.005))),
        'rsi_neutral': ('分区RSI硬门槛', '45<RSI<%s；所属%s，RSI=%s；G1/G2/G3/G4上限60/62/62.5/65，严格不含等号' % (display(rsi_upper), zone, display(rsi))),
        'stop_fall': ('止跌硬条件（OR仅计一项）', '下影占比>5×实体占比 或 C>O 或 abs(C−O)/(前收+0.0001)<0.003；下影=%s，实体=%s，C/O/前收=%s/%s/%s，实体/前收=%s；三分支=%s/%s/%s' % (display(lower),display(body),display(c),display(o),display(previous),display(small_body),finite_gt(lower,5.*body),bullish,bool(np.isfinite(small_body) and previous>0 and small_body<.003))),
        'activity_10d': ('洗盘十日活跃硬门槛', '使用截至昨日十个完整交易日核验后的activity_wash_pass；缺失/NaN=False；缓存=%s；逐日振幅/换手及冲高证据见十日活跃度统计' % activity_pass),
        'ma_bull': ('短均线高于MA20', 'MA5>MA20且MA10>MA20；MA5/MA10/MA20=%s/%s/%s' % (display(ma5),display(ma10),display(ma20))),
        'volume_shrink': ('昨日缩量（VMA5或VMA8，仅计一项）', 'V/(VMA5+0.0001)<0.76 或 V/(VMA8+0.0001)<0.75；V=%s，VMA5=%s，VMA8=%s，量比5/8=%s/%s；两分支=%s/%s，整体=%s' % (display(volume),display(vm5),display(vm8),display(vr5),display(vr8),shrink_vma5,shrink_vma8,bool(shrink_vma5 or shrink_vma8))),
        'no_pulse': ('非量脉冲', 'not volume_pulse；缓存=%s；当前指标固定False，此项实际恒成立，不代表实测脉冲' % no_pulse_value),
        'slope_diff': ('MA5斜率强于MA10', 'S5>S10；S5/S10均为五行变化率；S5=%s，S10=%s' % (display(s5),display(s10))),
        'shallow_slope': ('浅部斜率硬门槛', 'S5>S10 或 (MA5>MA10且S5>0.006)；S5/S10=%s/%s，MA5/MA10=%s/%s；两分支=%s/%s' % (display(s5),display(s10),display(ma5),display(ma10),old_slope,bool(finite_gt(ma5,ma10) and finite_gt(s5,.006)))),
        'deep_ma20_bullish': ('深部低点贴MA20且阳线', '-0.003<=L/MA20−1<=0.003且C>O；L/MA20=%s/%s，偏离=%s，贴线=%s，C>O=%s；不含O贴MA20分支' % (display(low),display(ma20),display(low_offset),deep_low_near,bullish)),
        'stabilization_bullish': ('企稳日内范围跨两条均线且阳线', '同一MA满足L<MA<H，MA5/10/20至少两条且C>O；L/H=%s/%s，MA5/10/20=%s/%s/%s；逐线=%s，条数=%s，C>O=%s；均为昨日，不推断穿越方向' % (display(low),display(h),display(ma5),display(ma10),display(ma20),crosses,cross_count,bullish))
    }
    descriptions.update({
        'g2_prev_above_ma20': ('中度前一完成行收盘守住MA20', 'C[prev]>=MA20[prev]；前一完成行日期=%s，C/MA20=%s/%s；完成行日期可核验=%s' % (timing.get('previous_date'), timing.get('previous_close'), timing.get('previous_ma20'), timing.get('date_coverage'))),
        'g3_open_ma5_floor': ('浅度开盘相对临时MA5下限', 'O_today/MA5_open-1>=-0.01；O=%s，MA5_open=%s，偏离=%s；MA5_open=(此前4完整收盘%s+已知开盘)/5，日期=%s；缺失不替代昨日MA5' % (timing.get('known_day_open'), timing.get('provisional_ma5_at_open'), timing.get('open_to_provisional_ma5_minus1'), timing.get('historical_closes4'), timing.get('historical_dates4'))),
        'g3_prev_volume_floor': ('浅度前一完成行量比下限', 'V[prev]/(VMA5[prev]+0.0001)>=0.60；前一完成行日期=%s，V/VMA5=%s/%s，量比=%s；含等号' % (timing.get('previous_date'), timing.get('previous_volume'), timing.get('previous_vma5'), timing.get('previous_volume_ratio5_eps'))),
        'g4_open_ma5_ceiling': ('企稳开盘相对临时MA5上限', 'O_today/MA5_open-1<=0.02；O=%s，MA5_open=%s，偏离=%s；MA5_open=(此前4完整收盘%s+已知开盘)/5，日期=%s；缺失不替代昨日MA5' % (timing.get('known_day_open'), timing.get('provisional_ma5_at_open'), timing.get('open_to_provisional_ma5_minus1'), timing.get('historical_closes4'), timing.get('historical_dates4'))),
        'g4_ma10_slope_ceiling': ('企稳MA10五行斜率上限', '昨日MA10五行斜率<=0.04；正式值沿用缓存(昨日MA10−shift(5)MA10)/shift(5)MA10；昨日MA10=%s，五行前=%s/MA10=%s，缓存五行斜率=%s；含等号，按完成行及实际日期核验' % (timing.get('ma10_current'), timing.get('ma10_lag5_date'), timing.get('ma10_lag5'), timing.get('ma10_five_interval_slope')))
    })
    return dict(core=core, edge=edge, zone_id=zone, zone_name=zone_name, zone_range=zone_range,
                timing_evidence=timing,
                edge_required=edge_required, condition_descriptions=descriptions,
                scoring_formula='75*硬条件命中率+25*边缘条件命中率；合格=全部硬条件且边缘命中>=%d/%d，原分仅展示不参与排序；所有合格洗盘统一按新四项经济次分，不另设区间优先级' % (edge_required,len(edge)),
                values=dict(d=d, close=c, open=o, high=h, low=low, previous_close=previous, ma5=ma5,ma10=ma10,ma20=ma20,
                            s5=s5,s10=s10,rsi=rsi,rsi_upper=rsi_upper,body_ratio=body,lower_shadow_ratio=lower,small_body_ratio=small_body,
                            volume_ratio5=vr5,volume_ratio8=vr8,volume_shrink_threshold=.76,
                            volume_shrink_vma5_threshold=.76,volume_shrink_vma8_threshold=.75,
                            volume_shrink_vma5_pass=shrink_vma5,volume_shrink_vma8_pass=shrink_vma8,
                            volume_shrink_pass=bool(shrink_vma5 or shrink_vma8),shallow_slope_threshold=.006,
                            low_ma20_offset=low_offset,deep_low_near=deep_low_near,
                            bullish=bullish,crosses=crosses,cross_count=cross_count,old_slope=old_slope,new_slope=new_slope,
                            activity_wash_pass=activity_pass),
                time_basis='前一完成行prev/五行前shift(5)沿用冻结帧skip_paused行口径并列明实际日期；临时MA5用此前4完整收盘+当日已知开盘；无未来收盘/最高/最低',
                boundary_basis='相对MA的边界以Decimal(str原始float)交叉比较，保留原MA已有精度，不加近等容差；L<MA<H严格比较')


def washout_candidate_metadata(latest, prev, details=None):
    """入围/交易归属附带区间证据；只附标签，不改变候选优先级或评分。"""
    evidence = details if details is not None else washout_condition_evidence(latest, prev)
    return dict(washout_zone_id=evidence['zone_id'], washout_zone_name=evidence['zone_name'],
                washout_zone_range=evidence['zone_range'], wash_deviation_ma10=evidence['values']['d'],
                wash_edge_required=evidence['edge_required'], wash_edge_total=len(evidence['edge']),
                wash_core_total=len(evidence['core']), wash_condition_version='v0542',
                washout_timing_evidence=evidence['timing_evidence'])


def washout_rank_scope():
    """洗盘排序范围由显式配置决定；不改变其他形态的分组。"""
    scope = g.cfg.get('wash_rank_scope', 'all_qualified')
    if scope not in ('same_primary_score', 'all_qualified'):
        raise ValueError('wash_rank_scope仅支持same_primary_score或all_qualified')
    return scope


def washout_economic_evidence(item, frame, asof=None):
    """只用截至昨日的冻结日线和选股时已知day_open，生成洗盘四项方向向量。

    不以昨收反算开盘价；不读取信号日收盘/日内最高价，也不追加行情请求。
    原始向量不舍入：越大越优，缺失由排名层按该项0百分位处理并记录原因。
    """
    def number(value):
        try:
            value = float(value)
            return value if np.isfinite(value) else float('nan')
        except (TypeError, ValueError):
            return float('nan')
    def divide(left, right):
        return left / right if np.isfinite(left) and np.isfinite(right) and right > 0 else float('nan')
    row = frame.iloc[-1]
    names = ('negative_open_provisional_ma5_distance', 'negative_slope5_sum_absolute',
             'signed_body_ratio', 'negative_volume_ratio5_target060_distance')
    weights = (.30, .25, .25, .20)
    timing = row.get('washout_timing_evidence')
    timing = timing if isinstance(timing, dict) else {}
    opening = number(timing.get('known_day_open'))
    close4 = [number(v) for v in timing.get('historical_closes4', [])]
    dates = list(timing.get('historical_dates4', []))
    cutoff = str(pd.Timestamp(asof).date()) if asof is not None else None
    same_asof = bool(cutoff is not None and timing.get('asof') == cutoff)
    history_valid = bool(same_asof and timing.get('historical_window_valid', False))
    row_time_valid = bool(same_asof and timing.get('decision_row_time_valid', False))
    opening_valid = bool(timing.get('opening_valid', False) and np.isfinite(opening) and opening > 0)
    temporary_ma5 = number(timing.get('provisional_ma5_at_open'))
    opening_deviation = number(timing.get('open_to_provisional_ma5_minus1'))
    s5, s10 = number(row.get('ma5_slope')), number(row.get('ma10_slope'))
    c, o, high, low = [number(row.get(k)) for k in ('close', 'open', 'high', 'low')]
    ohlc_valid = (py_all(np.isfinite(v) and v > 0 for v in (c, o, high, low)) and
                  high >= py_max(c, o, low) and low <= py_min(c, o, high))
    signed_body = (c - o) / (high - low + .0001) if ohlc_valid else float('nan')
    volume, vm5 = number(row.get('volume')), number(row.get('volume_ma5'))
    volume_ratio5 = divide(volume, vm5 + .0001) if volume >= 0 and vm5 >= 0 else float('nan')
    vector = [-py_abs(opening_deviation), -py_abs(s5+s10), signed_body, -py_abs(volume_ratio5-.60)]
    if not row_time_valid: vector = [float('nan')] * 4
    missing = []
    if not history_valid: missing.append('临时MA5的昨日及此前3个完整收盘/日期不可核验')
    if not opening_valid: missing.append('known_day_open未记录或无效，不反算、不补未来价格')
    if not ohlc_valid: missing.append('昨日OHLC缺失/不一致，带符号实体无效')
    for name, value in zip(names, vector):
        if not np.isfinite(value): missing.append('次分项缺失:' + name)
    clean = lambda x: float(x) if np.isfinite(x) else None
    return dict(schema='washout-economic/v0548', timing_evidence=timing, names=list(names), weights=list(weights),
                vector=[clean(v) for v in vector], direction='四项方向向量均越大越好；平均秩百分数按30/25/25/20加权',
                raw_inputs=dict(known_day_open=clean(opening), historical_closes4=[clean(v) for v in close4],
                    historical_dates4=dates, asof=cutoff, historical_window_valid=bool(history_valid),
                    decision_row_time_valid=row_time_valid,
                    provisional_ma5_at_open=clean(temporary_ma5), open_to_provisional_ma5_minus1=clean(opening_deviation),
                    yesterday_ma5_slope=clean(s5), yesterday_ma10_slope=clean(s10), slope_sum=clean(s5+s10),
                    yesterday_open=clean(o), yesterday_high=clean(high), yesterday_low=clean(low), yesterday_close=clean(c),
                    signed_body_ratio=clean(signed_body), yesterday_volume=clean(volume), yesterday_vma5=clean(vm5),
                    volume_ratio5_eps=clean(volume_ratio5),volume_target060_distance=clean(py_abs(volume_ratio5-.60))),
                formulas=['-abs(day_open/((昨日及此前3个收盘之和+day_open)/5)-1)',
                          '-abs(昨日MA5五行斜率+昨日MA10五行斜率)',
                          '(昨日C-昨日O)/(昨日H-昨日L+0.0001)',
                          '-abs(昨日V/(昨日VMA5+0.0001)-0.60)'],
                units='斜率/偏离/实体占比均为小数比率，不把百分数与小数混用；量比无量纲',
                missing=missing, future_data_used=False,
                tie_break='合成次分同分按未舍入四项方向向量1→4，再全相同按股票代码；不以区间另加优先级')



def log_washout_economic_ranking(item, rank):
    if item.get('combo_type') != 'combo_2': return
    evidence=item.get('washout_economic_evidence',{})
    definitions=(
        ('negative_open_provisional_ma5_distance','abs(开盘/临时MA5−1)','open_to_provisional_ma5_minus1','越小越优',.30),
        ('negative_slope5_sum_absolute','abs(S5+S10)','slope_sum','越小越优',.25),
        ('signed_body_ratio','(C−O)/(H−L+0.0001)','signed_body_ratio','越大越优，阳正阴负',.25),
        ('negative_volume_ratio5_target060_distance','abs(V/(VMA5+0.0001)−0.60)','volume_target060_distance','越小越优',.20))
    log.info(compact_log_text('【洗盘四项次分】排名%d | %s | %s | 合计%s分；全部合格洗盘跨原分排名，同分依1→4再代码' %
        (rank,stock_label(item['stock']),compact_economic_terms(item,evidence,definitions),compact_log_value(item.get('tie_score')))))


def build_washout_timing_evidence(frame, day_open, asof, expected_dates=None):
    """Build one immutable decision snapshot from completed rows and known open.

    Keep the existing skip_paused completed-row convention: prev is iloc[-2],
    MA5 uses iloc[-4:], and five rows earlier is iloc[-6]. The optional calendar
    argument is not a qualification gate; actual row dates are always recorded.
    No quote/history calls, forward rows, yesterday-MA5 fallback, or zero imputation.
    """
    def number(value):
        try:
            value = float(value)
            return value if np.isfinite(value) else float('nan')
        except (TypeError, ValueError):
            return float('nan')
    def clean(value):
        return float(value) if np.isfinite(value) else None
    def at(position, key):
        try:
            return number(frame.iloc[position].get(key))
        except (IndexError, KeyError, AttributeError):
            return float('nan')
    opening = number(day_open)
    opening_valid = bool(np.isfinite(opening) and opening > 0)
    cutoff = str(pd.Timestamp(asof).date())
    try:
        dates = [str(pd.Timestamp(d).date()) for d in frame.index]
    except (TypeError, ValueError, AttributeError):
        dates = []
    ordered = bool(dates and len(dates) == len(set(dates)) and dates == sorted(dates)
                   and py_all(d <= cutoff for d in dates) and dates[-1] == cutoff)
    coverage = {n: bool(ordered and len(dates) >= n) for n in (2, 4, 6)}
    closes4 = [at(i, 'close') for i in range(-4, 0)]
    history_valid = bool(coverage[4] and py_all(np.isfinite(v) and v > 0 for v in closes4))
    provisional_ma5 = ((py_sum(closes4) + opening) / 5.
                       if history_valid and opening_valid else float('nan'))
    open_deviation = (opening / provisional_ma5 - 1.
                      if np.isfinite(provisional_ma5) and provisional_ma5 > 0 else float('nan'))
    previous_close, previous_ma20 = at(-2, 'close'), at(-2, 'ma20')
    previous_volume, previous_vma5 = at(-2, 'volume'), at(-2, 'volume_ma5')
    volume_valid = bool(coverage[2] and np.isfinite(previous_volume) and previous_volume >= 0
                        and np.isfinite(previous_vma5) and previous_vma5 >= 0)
    previous_volume_ratio = (previous_volume / (previous_vma5 + .0001)
                             if volume_valid else float('nan'))
    current_ma10, lag_ma10 = at(-1, 'ma10'), at(-6, 'ma10')
    ma10_slope = at(-1, 'ma10_slope')
    slope_valid = bool(coverage[6] and np.isfinite(current_ma10) and current_ma10 > 0
                       and np.isfinite(lag_ma10) and lag_ma10 > 0 and np.isfinite(ma10_slope))
    # Cross-products preserve inclusive decimal threshold semantics without epsilon.
    from decimal import Decimal
    previous_volume_pass = bool(volume_valid and
        Decimal(str(previous_volume)) >= Decimal('.60') * (Decimal(str(previous_vma5)) + Decimal('.0001')))
    checks = dict(
        g2_prev_above_ma20=bool(coverage[2] and washout_relative_compare(previous_close, previous_ma20, 0., '>=')),
        g3_open_ma5_floor=bool(washout_relative_compare(opening, provisional_ma5, -.01, '>=')),
        g3_prev_volume_floor=previous_volume_pass,
        g4_open_ma5_ceiling=bool(washout_relative_compare(opening, provisional_ma5, .02, '<=')),
        g4_ma10_slope_ceiling=bool(slope_valid and ma10_slope <= .04))
    missing = []
    if not opening_valid: missing.append('当日已知开盘缺失/非正有限值')
    if not history_valid: missing.append('此前4个已完成收盘/有序唯一日期缺证')
    if not coverage[2]: missing.append('昨日及前一完成行缺失/日期无效')
    if not (np.isfinite(previous_close) and previous_close > 0 and np.isfinite(previous_ma20) and previous_ma20 > 0):
        missing.append('前一完成行收盘/MA20缺失或非正')
    if not volume_valid: missing.append('前一完成行成交量/VMA5缺失或无效')
    if not slope_valid: missing.append('昨日/五行前MA10、缓存五行斜率或六个完成行缺证')
    return dict(schema='washout-timing/v0542', asof=cutoff, decision_row_time_valid=ordered,
        date_coverage={str(k): v for k, v in coverage.items()},
        historical_dates6=dates[-6:], historical_dates4=dates[-4:],
        historical_closes4=[clean(v) for v in closes4], historical_window_valid=history_valid,
        known_day_open=clean(opening), opening_valid=opening_valid,
        provisional_ma5_at_open=clean(provisional_ma5), open_to_provisional_ma5_minus1=clean(open_deviation),
        previous_date=dates[-2] if len(dates) >= 2 else None,
        previous_close=clean(previous_close), previous_ma20=clean(previous_ma20),
        previous_volume=clean(previous_volume), previous_vma5=clean(previous_vma5),
        previous_volume_ratio5_eps=clean(previous_volume_ratio),
        ma10_current=clean(current_ma10), ma10_lag5=clean(lag_ma10),
        ma10_lag5_date=dates[-6] if len(dates) >= 6 else None,
        ma10_five_interval_slope=clean(ma10_slope), checks=checks, missing=missing,
        future_data_used=False, source='同一冻结形态帧+信号日已知day_open；前一完成行/五行前沿用skip_paused行口径，实际日期逐项展示')


def attach_washout_timing_evidence(frame, day_open, asof):
    """Attach once before activity prefilter; final evaluation/logging reuse it."""
    if frame is None or frame.empty:
        return frame
    current = frame.iloc[-1].get('washout_timing_evidence')
    if (isinstance(current, dict) and current.get('schema') == 'washout-timing/v0542'
            and current.get('asof') == str(pd.Timestamp(asof).date())):
        return frame  # Preserve the selection-time opening snapshot.
    evidence = build_washout_timing_evidence(frame, day_open, asof)
    frame['washout_timing_evidence'] = pd.Series([None] * len(frame), index=frame.index, dtype=object)
    frame.at[frame.index[-1], 'washout_timing_evidence'] = evidence
    return frame


def historical_sell_stamp_tax(day):
    """股票出让印花税：本研究2020年起区间按实际日期；False恢复旧固定万五。"""
    if not HISTORICAL_STAMP_TAX:
        return .0005
    if isinstance(day, dt.datetime):
        day = day.date()
    elif not isinstance(day, dt.date):
        day = dt.datetime.strptime(str(day)[:10], '%Y-%m-%d').date()
    return .001 if day < dt.date(2023, 8, 28) else .0005


def configure_stock_order_cost(context, force=False):
    """初始化及每日09:24核验；只有税率变化时重设费用，实际撮合与内部估算共用税率。"""
    rate = historical_sell_stamp_tax(context.current_dt.date())
    if not force and getattr(g, 'effective_sell_stamp_tax', None) == rate:
        return False
    set_order_cost(OrderCost(open_tax=0, close_tax=rate, open_commission=.0003,
                            close_commission=.0003, close_today_commission=0, min_commission=5), type='stock')
    g.effective_sell_stamp_tax = rate
    g.effective_sell_stamp_tax_date = str(context.current_dt.date())
    log.info('【历史印花税】日期%s | 模式%s | 卖出税率%.4f | 买入税0、双向佣金0.0003最低5元' %
             (context.current_dt.date(), '按历史政策' if HISTORICAL_STAMP_TAX else '旧固定0.0005对照', rate))
    return True


def stock_fee_policy_text():
    """费用说明不隐藏对照模式；不获取行情或改变交易状态。"""
    policy = ('2023-08-28前卖出印花税0.001、当日及以后0.0005（2020年起研究区间）'
              if HISTORICAL_STAMP_TAX else '旧固定卖出印花税0.0005')
    return policy + '，佣金双向0.0003且每笔最低5元'


def export_shared_selection_snapshot():
    # 仅包含冻结行情/研究证据；绝不传播 book、pending、orders、买卖计划等账户状态。
    names = ('_micro_data_cache', '_cache_date', 'activity_asof', 'activity_evidence',
             'activity_rejection_logged', 'entry_filter_asof', 'entry_raw_history',
             'entry_adjusted_history', 'entry_calendar_cache', 'accel_daily_cache',
             'base_pool', 'concepts', 'concept_pool', 'concept_policy_valid_day',
             'concept_pool_history', 'concept_member_evidence', 'concept_evidence_asof',
             'display_names', 'selection_profile', 'shared_qualified_candidates',
             'shared_selection_asof', 'shared_selection_day', 'shared_selection_complete')
    return {name: getattr(g, name) for name in names if hasattr(g, name)}


def build_shared_candidates(context, date_str):
    """趋势股六维评估选股（基于昨日数据）"""
    if getattr(g,'shared_selection_asof',None)==str(date_str) and getattr(g,'shared_selection_day',None)==str(context.current_dt.date()):
        return list(g.shared_qualified_candidates)
    active_shapes = enabled_combo_types()
    concept_gating = use_concept_selection()
    selection_started = time.perf_counter()
    g.selection_profile = dict(seconds={}, counts={}, stack=[])
    try:
        log.info('========== 趋势股形态评估选股（启用%d种形态，基于昨日数据） ==========' % len(active_shapes))

        initial_list = selection_timed('base_pool', prepare_stock_list, date_str)

        # 获取中证1000成分股作为股票池（代码000852.XSHG）
        try:
            zz1000_stocks = selection_timed('index_query', get_index_stocks, '000852.XSHG', date_str)
            zz1000_set = set([normalize_stock_code(s) for s in zz1000_stocks])
            initial_set = set([normalize_stock_code(s) for s in initial_list])
            intersection=initial_set & zz1000_set
            candidates = list(intersection) if g.cfg.get('tie_policy')=='original_set_order' else sorted(intersection)
            for stock in g.cfg.get('signal_audit_codes',[]):
                audit('SIGNAL_TRACE',stock=stock,stage='base_index',base_member=stock in initial_set,index_member=stock in zz1000_set)
            log.info(f"【趋势股-中证1000过滤】初始{len(initial_list)}只 → 中证1000交集{len(candidates)}只")
        except Exception as e:
            log.error(f"【趋势股中证1000获取错误】{str(e)}，本日停止选股")
            raise RuntimeError("历史指数成分获取失败，禁止扩池") from e

        if concept_gating and not g.concept_pool:
            if (getattr(g,"concept_policy_valid_day",None)==str(g.day) and
                    (g.cfg.get("concept_exclude_broad",False) or g.cfg.get("concept_rolling",False))):
                log.info("【概念有效空池】完整来源核验后无合格热门，本日新增候选0；不绕过概念过滤，持仓/退出及原有突破延迟计划继续按原规则管理")
                return _selection51_complete(context,date_str,[])
            raise RuntimeError("概念池为空或数据未核验，禁止绕过过滤")
        if concept_gating:
            before_concept = len(candidates)
            candidates = filter_by_concept(candidates, g.concept_pool)
            candidates = [str(s) for s in candidates]
            log.info(f"【趋势股-概念过滤】{before_concept}只 → {len(candidates)}只")
        else:
            log.info('【趋势股-概念过滤】本对照关闭 | 中证1000基础池%d只直接进入启用形态评估；概念仅观察及独立退出使用' % len(candidates))

        if not candidates:
            log.warning("【趋势股选股】指数或概念过滤后无候选股票")
            return _selection51_complete(context,date_str,[])

        log.info('【趋势股-基础池】%s: %d只 | 启用形态:%s' %
                 ('指数+概念过滤后' if concept_gating else '指数基础过滤后（无概念门槛）', len(candidates),
                  [ComboEvaluator.COMBO_CONFIG[x]['name'] for x in active_shapes]))
        concept_codes = set(candidates)
        # Reference changes evaluation order only; thresholds/ranking stay identical to this version.
        # Compare frozen identical historical data, not different API failure outcomes or revised data.
        if g.cfg.get('selection_reference_pipeline', False):
            candidates = historical_entry_candidates(candidates, date_str, defer_r15=True)
            if not candidates: return _selection51_complete(context,date_str,[])

        if not hasattr(g, '_micro_data_cache'):
            g._micro_data_cache = {}
            g._cache_date = date_str
        if g._cache_date != date_str:
            g._micro_data_cache = {}
            g._cache_date = date_str

        # These prices are fixed day_open values at this same 09:27 callback.
        # Reuse the checked 80-day frame's final close; never substitute raw-board close.
        current_data = get_current_data()
        prefilter_rejected = set()
        perf = dict(history_seconds=0.0, micro_seconds=0.0, history_calls=0,
                    micro_calls=0, opening_rejected=0, uncertain_fallbacks=0)

        def fetch_history(*args, **kwargs):
            started = time.perf_counter()
            perf['history_calls'] += 1
            try:
                return selection_timed('daily_query', get_price, *args, **kwargs)
            finally:
                perf['history_seconds'] += time.perf_counter() - started

        def prepare_micro(stock_code, frame):
            # Only a proven finite <=1% gap may bypass indicator construction.
            # NaN, missing fields and quote errors use the unchanged full evaluation path.
            if g.cfg.get('performance_optimizations', True):
                try:
                    previous = frame.iloc[-1]['close']
                    opening = current_data[stock_code].day_open
                    if not np.isfinite(previous) or not np.isfinite(opening):
                        raise ValueError('开盘或前收非有限数值')
                    gap = (opening / previous - 1) * 100 if previous > 0 else 0
                    if gap <= 1:
                        prefilter_rejected.add(stock_code)
                        perf['opening_rejected'] = len(prefilter_rejected)
                        return None
                except Exception as exc:
                    perf['uncertain_fallbacks'] += 1
                    log.warning('【提速前置判断回退】%s | %s；继续原完整指标/选股路径，不据异常直接剔除' % (stock_code, exc))
            started = time.perf_counter()
            perf['micro_calls'] += 1
            try:
                return selection_timed('micro_compute', calculate_micro_structure, frame, private_frame=True)
            finally:
                perf['micro_seconds'] += time.perf_counter() - started

        # 【优化B】批量拉取候选股日线（每批200只），替代逐股串行请求；数据与逐股一致
        to_fetch = [str(s) for s in candidates if str(s) not in g._micro_data_cache]
        if to_fetch:
            batch_size = 200
            for j in range(0, len(to_fetch), batch_size):
                batch = to_fetch[j:j + batch_size]
                try:
                    df_all = fetch_history(batch, end_date=date_str, frequency='daily',
                                       fields=['open', 'high', 'low', 'close', 'volume', 'money'],
                                       count=80, skip_paused=True, panel=False)
                    if df_all is None or df_all.empty:
                        continue
                    for stock_code, sub in selection_groups(df_all).items():
                        stock_code = str(stock_code)
                        if len(sub) < 65:
                            continue
                        sub = checked_daily(sub, date_str)
                        mdf = prepare_micro(stock_code, sub)
                        if mdf is not None:
                            g._micro_data_cache[stock_code] = mdf
                except Exception as e:
                    log.warning(f"【优化B】批量拉取失败，回退逐股: {str(e)}")
                    for stock_code in batch:
                        if stock_code in prefilter_rejected:
                            continue  # A proven rejected batch row must not be fetched again.
                        try:
                            df_one = fetch_history(stock_code, end_date=date_str, frequency='daily',
                                               fields=['open', 'high', 'low', 'close', 'volume', 'money'],
                                               count=80, skip_paused=True)
                            if df_one is None or len(df_one) < 65:
                                continue
                            mdf = prepare_micro(stock_code, checked_daily(df_one, date_str))
                            if mdf is not None:
                                g._micro_data_cache[stock_code] = mdf
                        except Exception as shape_error:
                            # 回退发生在diagnostic/逐形态循环之前；只记录当前股行情失败并继续。
                            perf['history_errors'] = perf.get('history_errors', 0) + 1
                            log.warning('【逐股行情回退失败】%s | 阶段daily_history_fallback | %s；继续其他股票，缺失行情不当合格' % (stock_code, str(shape_error)))
                            audit('SHAPE_EVALUATION_ERROR',stock=stock_code,shape='daily_history_fallback',error=str(shape_error),traceback=traceback.format_exc())
                            continue

        prime_activity_candidates(candidates, date_str, current_data)
        selected_stocks = []
        diagnostic=dict(pool=len(candidates),evaluated=0,missing_daily=0,shakeout=0,stock_errors=0)
        evaluator = ComboEvaluator()

        with selection_stage('shape_evaluation'):
            for i, stock in enumerate(candidates):
                if str(stock) in prefilter_rejected:
                    continue
                if g.cfg.get('log_mode')=='full' and i % 100 == 0 and i > 0:
                    log.info(f"【趋势股-评估进度】已检查 {i}/{len(candidates)} 只…")

                try:
                    stock = str(stock)

                    if stock in g._micro_data_cache:
                        df = g._micro_data_cache[stock]
                    else:
                        df = fetch_history(stock, end_date=date_str, frequency='daily',
                                       fields=['open', 'high', 'low', 'close', 'volume', 'money'],
                                       count=80, skip_paused=True)
                        if df is None or len(df) < 65:
                            diagnostic['missing_daily']+=1
                            continue
                        df = prepare_micro(stock, checked_daily(df, date_str))
                        if df is None:
                            continue
                        g._micro_data_cache[stock] = df

                    diagnostic['evaluated']+=1
                    df = attach_activity_evidence(stock, df, date_str, current_data)
                    latest = df.iloc[-1]
                    prev = df.iloc[-2] if len(df) > 1 else latest
                    if identify_shakeout(df):
                        diagnostic['shakeout']+=1
                        continue

                    day_open = current_data[stock].day_open
                    pre_close = latest['close']
                    open_chg_pct = (day_open / pre_close - 1) * 100 if pre_close > 0 else 0

                    combo_checks = [
                        ('combo_2', evaluator.evaluate_combo_2),
                        ('combo_3', evaluator.evaluate_combo_3),
                        ('combo_4', evaluator.evaluate_combo_4),
                        ('combo_1', evaluator.evaluate_combo_1),
                        ('combo_5', evaluator.evaluate_combo_5)
                    ]

                    matched = False
                    for combo_type, eval_func in combo_checks:
                        if combo_type not in active_shapes:
                            continue
                        try:
                            if combo_type=='combo_3' and pd.Timestamp(df.index[-1]).date()!=pd.Timestamp(date_str).date():
                                log.warning('【突破研究日线无效】%s | 末行%s不等于昨日%s；仅拒绝突破归属' % (stock,df.index[-1],date_str))
                                continue
                            selection_details = {} if combo_type == 'combo_3' else None
                            passed, score, core_met, edge_met = eval_func(latest, prev, details=selection_details)
                            if (combo_type == 'combo_3' and selection_details.get('original_pass') and
                                    3 <= open_chg_pct <= 7):
                                log_breakout_research_hard_conditions(stock, latest, prev, selection_details, score,
                                    '原形态/开盘合格；新增六硬通过' if passed else '原形态/开盘合格；新增六硬拒绝')
                            if passed:
                                cfg = evaluator.COMBO_CONFIG[combo_type]

                                if combo_type == 'combo_3':
                                    if not (3 <= open_chg_pct <= 7):
                                        if g.cfg.get("log_mode")=="full":log.debug(f"【趋势股-Combo3开盘不符】{stock} 开盘{open_chg_pct:.2f}%")
                                        continue
                                else:
                                    if open_chg_pct <= 1:
                                        if g.cfg.get("log_mode")=="full":log.debug(f"【趋势股-开盘不符】{stock} 开盘{open_chg_pct:.2f}%")
                                        continue

                                selected_stocks.append({
                                    'stock': stock,
                                    'combo_type': combo_type,
                                    'combo_name': cfg['name'],
                                    'score': float(score),
                                    'core_met': int(core_met),
                                    'edge_met': int(edge_met),
                                    'priority': cfg['priority'],
                                    'open_chg': open_chg_pct
                                })
                                if combo_type == 'combo_2':
                                    selected_stocks[-1].update(washout_candidate_metadata(latest,prev))
                                elif combo_type == 'combo_4':
                                    selected_stocks[-1].update(main_candidate_metadata(latest,prev))
                                selected_stocks[-1]['known_day_open']=float(day_open)
                                matched = True
                                # Keep all qualified shape facts; account attribution happens later.
                        except Exception as shape_error:
                            diagnostic['stock_errors']+=1
                            audit('SHAPE_EVALUATION_ERROR',stock=stock,shape=combo_type,error=str(shape_error),traceback=traceback.format_exc())
                            continue

                    if 'combo_6' in active_shapes:  # 独立账户：标准不被其他形态先匹配遮挡
                        try:
                            ma5 = float(latest['ma5'])
                            ma10 = float(latest['ma10'])
                            ma20 = float(latest['ma20'])
                            vol_ratio = float(latest['volume_ratio'])

                            if open_chg_pct <= 1:
                                continue

                            core_checks, edge_checks = standard_bull_conditions(latest, open_chg_pct)
                            core_pass = py_all(ComboEvaluator._safe_bool(value) for value in core_checks.values())
                            if core_pass:
                                edge_met = py_sum(1 for check in edge_checks.values() if ComboEvaluator._safe_bool(check))
                                if standard_bull_edge_pass(edge_met):
                                    cfg = evaluator.COMBO_CONFIG['combo_6']
                                    selected_stocks.append({
                                        'stock': stock,
                                        'combo_type': 'combo_6',
                                        'combo_name': cfg['name'],
                                        'score': standard_bull_display_score(edge_met, len(edge_checks)),
                                        'core_met': len(core_checks),
                                        'edge_met': int(edge_met),
                                        'priority': cfg['priority'],
                                        'open_chg': open_chg_pct
                                    })
                        except:
                            pass

                except Exception as e:
                    diagnostic['stock_errors']+=1
                    if diagnostic['stock_errors']<=3:
                        audit('SIGNAL_STOCK_ERROR',stock=stock,error=str(e),traceback=traceback.format_exc())
                    continue

        diagnostic['enabled_shapes_qualified_before_history'] = len(selected_stocks)
        stage_note = '历史前置对照，已完成板型/加速排除；尚未弱阴线排除/经济次分/前N' if g.cfg.get('selection_reference_pipeline', False) else '尚未历史排除/计算经济次分/截取前N'
        log.info('【趋势股-启用形态初筛】%d种形态完整合格%d只；%s' % (len(active_shapes), len(selected_stocks), stage_note))
        if not g.cfg.get('selection_reference_pipeline', False):
            kept_codes = set(historical_entry_candidates(list(dict.fromkeys(item['stock'] for item in selected_stocks)), date_str, defer_r15=True))
            selected_stocks = [item for item in selected_stocks if item['stock'] in kept_codes]
        selected_stocks = [item for item in selected_stocks if candidate_shape_r15_allowed(item['stock'],item['combo_type'],date_str)]
        selected_stocks = filter_weak_shape_candidates(selected_stocks, date_str)
        diagnostic['opening_preexcluded'] = len(prefilter_rejected)
        audit('SIGNAL_FUNNEL',qualified=len(selected_stocks),**diagnostic)
        log.info('【选股性能】历史请求%d次/%.3f秒 | 指标计算%d次/%.3f秒 | 开盘幅度<=1%%前置排除%d只 | 不确定数据回原路径%d次；每日完整形成候选，历史排除后才进行经济排名' %
                 (perf['history_calls'], perf['history_seconds'], perf['micro_calls'], perf['micro_seconds'],
                  perf['opening_rejected'], perf['uncertain_fallbacks']))
        with selection_stage('ranking_output'):
            try:
                prime_qualified_activity_observation(selected_stocks,date_str)
            except Exception as exc:
                log.warning('【候选活跃度补全异常】%s；不改变已合格候选' % exc)
            rank_same_score(selected_stocks,g._micro_data_cache)
        counts={}
        for item in selected_stocks:
            shape=item['combo_type'];counts[shape]=counts.get(shape,0)+1
            item['shape_rank']=counts[shape]
            item['candidate_id']='%s|%s|%s'%(context.current_dt.date(),shape,item['stock'])
            item['in_shape_top5']=counts[shape]<=5
            item['in_shape_top8']=counts[shape]<=8
            item['selection_scope']='共享完整候选/形态独立排名'
        log.info('【合格形态分布】%s | 同股跨形态资格各自保留；各池按统一优先级去重后截取本池K' % counts)
        return _selection51_complete(context,date_str,selected_stocks)
    except Exception as e:
        audit("SIGNAL_ERROR", error=str(e),traceback=traceback.format_exc())
        g.signal_ok = False
        raise RuntimeError('共享形态筛选失败，禁止缓存为成功空池') from e

    finally:
        finish_selection_profile(selection_started)
        g.shared_selection_snapshot=export_shared_selection_snapshot()


def finalize_shared_candidates(context, candidates, date_str=None):
    """先按已冻结的形态内排名排队；本资金池按全局形态优先级去重，再截取K。

    不因本账户现金、旧仓或N/D变化重算次分。同股在本池只归最高优先级的
    合格形态；不同真实子账户可各自持有。已有持仓仍沿用首次成交的形态退出。
    """
    enabled = tuple(g.cfg.get('enabled_combo_types', ()))
    if not enabled or len(set(enabled)) != len(enabled) or not set(enabled) <= set(ALL_RESEARCH_SHAPES):
        raise ValueError('账户启用形态缺失、重复或超出六形态范围')
    limit = int(g.cfg['selection_count'])
    if limit <= 0:
        raise ValueError('selection_count须为正整数')
    relevant = [_ma_copy.deepcopy(item) for item in candidates if item['combo_type'] in enabled]
    keys = [(item['combo_type'], str(item['stock'])) for item in relevant]
    if len(set(keys)) != len(keys):
        raise ValueError('同一形态出现重复候选，禁止重复入围')
    priority = {shape: i for i, shape in enumerate(ALL_RESEARCH_SHAPES)}
    relevant.sort(key=lambda item: (priority[item['combo_type']], int(item['shape_rank'])))
    own, selected_shape, duplicates = [], {}, []
    for item in relevant:
        stock = str(item['stock'])
        if stock in selected_shape:
            duplicates.append('%s:%s归入%s' % (stock, item['combo_type'], selected_shape[stock]))
            continue
        selected_shape[stock] = item['combo_type']
        item['account_rank'] = len(own) + 1
        item['in_account_top_k'] = item['account_rank'] <= limit
        own.append(item)
    chosen = own[:limit]
    final_list = [str(item['stock']) for item in chosen]
    g.all_qualified_candidates = own
    g.qs_combo_info = {str(item['stock']): item for item in chosen}
    g.signal_cache = list(final_list)
    g.signal_ok = True
    log.info('【本账户选股总结】共享指纹%s | 形态记录%d/同股归属去重%d/独立合格%d/入围%d | N%d/K%d/D%d | 优先序洗盘→突破→超跌→吸筹→主升→标准，仅保留本池启用形态' %
             (getattr(g, 'shared_selection_fingerprint', '见共享候选记录'), len(relevant), len(duplicates), len(own), len(chosen),
              g.cfg['max_count'], limit, unit_budget_divisor()))
    if duplicates:
        log.info('【本池同股归属】' + '；'.join(duplicates))
    for item in chosen:
        log.info('【本账户入围】池内排名%d/形态内排名%d | %s | %s | 原分%.4f/经济次分%.6f | 候选键%s | 尚未成交' %
                 (item['account_rank'], item['shape_rank'], main_shape_display_name(item), stock_label(item['stock']),
                  item['score'], item.get('tie_score', 0.), item.get('candidate_id', '缺失')))
    if len(own) > limit:
        log.info('【本池未入围】K=%d截断；%s' % (limit, '；'.join(
            '%s/池内%d/形态内%d' % (x['candidate_id'], x['account_rank'], x['shape_rank']) for x in own[limit:])))
    audit('SIGNAL_RANKING', asof=date_str, combos=enabled, tie_policy=g.cfg.get('tie_policy'),
          qualified=own, selected=final_list)
    return list(final_list)

# Historical fee policy inherited with the v0.5.42 fee helpers.
HISTORICAL_STAMP_TAX = True


def selection_ceiling_metrics(latest):
    """v54唯一上限计算：冻结T-1数据；筛选、复核日志和研究输出共用。"""
    def finite(key):
        try:
            value = float(latest.get(key, np.nan))
            return value if np.isfinite(value) else float('nan')
        except (TypeError, ValueError):
            return float('nan')
    close, ma20 = finite('close'), finite('ma20')
    vm5, vm10, vm20 = [finite(key) for key in ('volume_ma5', 'volume_ma10', 'volume_ma20')]
    spread = finite('ma_spread_ratio')
    price_offset = close / ma20 - 1. if np.isfinite(close) and close > 0 and np.isfinite(ma20) and ma20 > 0 else float('nan')
    denominator_valid = np.isfinite(vm20) and vm20 > 0
    ratio10 = vm10 / (vm20 + .0001) if denominator_valid and np.isfinite(vm10) and vm10 >= 0 else float('nan')
    ratio5 = vm5 / (vm20 + .0001) if denominator_valid and np.isfinite(vm5) and vm5 >= 0 else float('nan')
    pass10 = bool(np.isfinite(ratio10) and ratio10 <= 1.35)
    pass5 = bool(np.isfinite(ratio5) and ratio5 <= 1.70)
    return dict(price_ma20_offset=price_offset, volume_ma10_over_ma20=ratio10,
                volume_ma5_over_ma20=ratio5, accumulation_spread=spread,
                standard_price_pass=bool(np.isfinite(price_offset) and price_offset <= .15),
                volume10_pass=pass10, volume5_pass=pass5,
                standard_volume_or_pass=bool(pass10 or pass5),
                accumulation_spread_pass=bool(np.isfinite(spread) and spread <= 1.5))


def economic_factor_spec(combo):
    """Direction-adjusted ranks are comparable only inside the declared shape/score group."""
    small_upper = combo in ('combo_1', 'combo_5')
    names = (('negative_upper_shadow' if small_upper else 'upper_shadow'),
             'negative_open_target_03_distance', 'negative_ma5_target_005_distance',
             'volume_ma5_over_ma20', 'macd_over_close')
    weights = (20., 10., 40., 20., 10.) if combo == 'combo_6' else (20., 20., 20., 20., 20.)
    labels = (('上影占比越小越优' if small_upper else '上影占比越大越优'),
              '开盘涨幅越接近+3%越优', '昨收/MA5越接近1.005越优',
              'VMA5/VMA20越大越优', 'MACD柱/昨收越大越优')
    return names, weights, labels


def _selection51_complete(context, date_str, items):
    """合法空候选也需要冻结为成功，防止第二账户重复查询。"""
    g.shared_qualified_candidates = list(items)
    g.shared_selection_asof = str(date_str)
    g.shared_selection_day = str(context.current_dt.date())
    g.shared_selection_complete = True
    g.signal_ok = True
    return list(items)


def _v54_rank_same_score(items, frame_cache):
    groups = {}
    for item in items:
        item['tie_score'] = 0.0
        score_group = None if item['combo_type'] == 'combo_6' else item['score']
        groups.setdefault((item['combo_type'], item['priority'], score_group), []).append(item)
    for key, group in groups.items():
        combo = key[0]
        names, weights, labels = economic_factor_spec(combo)
        matrix = []
        for item in group:
            row = frame_cache[item['stock']].iloc[-1]
            def ratio(a, b):
                a = float(a); b = float(b)
                return a / b if np.isfinite(a) and np.isfinite(b) and b > 0 else float('nan')
            raw = [float(row['upper_shadow_ratio']), float(item['open_chg']) / 100.,
                   ratio(row['close'], row['ma5']), ratio(row['volume_ma5'], row['volume_ma20']),
                   ratio(row['macd'], row['close'])]
            values = [-raw[0] if combo in ('combo_1', 'combo_5') else raw[0],
                      -py_abs(raw[1] - .03), -py_abs(raw[2] - 1.005), raw[3], raw[4]]
            finite = [py_round(v, 12) if np.isfinite(v) else float('nan') for v in values]
            item['tie_features'] = dict(zip(names, [v if np.isfinite(v) else None for v in finite]))
            item['tie_raw_order'] = [v if np.isfinite(v) else None for v in finite]
            item['tie_raw_values'] = dict(zip(names, [v if np.isfinite(v) else None for v in raw]))
            item['tie_weights'] = dict(zip(names, weights))
            matrix.append(finite)
        percentile = pd.DataFrame(matrix).rank(method='average', ascending=True, na_option='keep').fillna(0) / len(group)
        for i, item in enumerate(group):
            item['tie_percentiles'] = {name: float(percentile.iloc[i,k]) for k,name in enumerate(names)}
            item['tie_weighted_points'] = {name: float(percentile.iloc[i,k])*weights[k] for k,name in enumerate(names)}
            item['tie_score'] = float(py_sum(item['tie_weighted_points'].values()))
    def rank_key(item):
        vector = tuple(-v if v is not None else float('inf') for v in item['tie_raw_order'])
        primary_order = 0.0 if item['combo_type'] == 'combo_6' else -item['score']
        return (item['priority'], primary_order, -py_round(item['tie_score'], 12), vector, item['stock'])
    items.sort(key=rank_key)
    return items


def _v54_log_candidate_conditions(item, rank):
    """只读冻结形态帧；复用正式评估器，失败仅影响展示，绝不请求行情或改变候选。"""
    if not g.cfg.get('log_shape_conditions', True):
        return
    stock = str(item.get('stock', '股票缺失'))
    try:
        df = getattr(g, '_micro_data_cache', {}).get(stock)
        if df is None or len(df) < 7:
            log.warning('【形态条件不可复核】%s | 冻结形态日线缺失/不足，不能输出通过结论' % stock)
            return
        latest, prev = df.iloc[-1], df.iloc[-2]
        combo = item.get('combo_type')
        missing = set()

        def num(key, row=latest):
            try:
                value = float(row[key])
                if not np.isfinite(value):
                    missing.add(str(key))
                return value
            except Exception:
                missing.add(str(key))
                return float('nan')

        def fmt(value, percent=False):
            try:
                value = float(value)
                if not np.isfinite(value):
                    return '缺失/非有限值'
                return ('%.12g%%' % (value * 100)) if percent else ('%.12g' % value)
            except Exception:
                return '缺失/不可转换'

        def ratio(a, b):
            if not np.isfinite(a) or not np.isfinite(b) or b == 0:
                return float('nan')
            return a / b

        def truth(value):
            try:
                if pd.isna(value):
                    return '缺失，不能确认'
                return str(bool(value))
            except Exception:
                return '缺失，不能确认'

        def compare(a, op, b):
            if not np.isfinite(a) or not np.isfinite(b):
                return '缺失，不能确认'
            checks = {'>': lambda: a > b, '<': lambda: a < b,
                      '>=': lambda: a >= b, '<=': lambda: a <= b,
                      '==': lambda: a == b}
            return truth(checks[op]())

        def new_boundary_compare(a, op, b):
            # Only v53 additions use this machine-precision boundary tolerance.
            # Existing conditions retain their exact previous comparisons.
            if not np.isfinite(a) or not np.isfinite(b):
                return '缺失，不能确认'
            checks = {'>=': lambda: a >= b - 1e-12, '<=': lambda: a <= b + 1e-12,
                      '>': lambda: a > b + 1e-12}
            return truth(checks[op]())

        def date_at(pos):
            row = df.iloc[pos]
            value = row.get('time', row.get('date', df.index[pos]))
            try:
                return str(value.date())
            except Exception:
                return str(value)

        def slope(period, pos=-1):
            row, lag = df.iloc[pos], df.iloc[pos - 5]
            current, old = num('ma%d' % period, row), num('ma%d' % period, lag)
            value = num('ma%d_slope' % period, row)
            return ('MA%d[%s]=%s，MA%d[%s]=%s；(当前MA−5行前MA)/5行前MA=%s；缓存斜率=%s' %
                    (period, date_at(pos), fmt(current), period, date_at(pos - 5), fmt(old),
                     fmt(ratio(current - old, old), True), fmt(value, True)))

        def volume_ratio_text(threshold, operator='<'):
            v, vm = num('volume'), num('volume_ma5')
            return ('V/(VMA5+0.0001)%s%s；V=%s，VMA5=%s，实际量比=%s' %
                    (operator, fmt(threshold), fmt(v), fmt(vm), fmt(num('volume_ratio'))))

        def deviation_text(period):
            c, ma = num('close'), num('ma%d' % period)
            return 'C=%s，MA%d=%s，(C−MA%d)/MA%d=%s，绝对偏离=%s' % (
                fmt(c), period, fmt(ma), period, period, fmt(ratio(c - ma, ma), True),
                fmt(py_abs(ratio(c - ma, ma)), True))

        def convergence_text(threshold):
            values = [num('ma%d' % p) for p in (5, 10, 20, 60)]
            return ('std(MA5,MA10,MA20,MA60,ddof=1)/(四均线均值+0.0001)<%s；四MA=[%s]，收敛度=%s' %
                    (fmt(threshold), ','.join(fmt(x) for x in values), fmt(num('ma_convergence'))))

        def spread_text(threshold):
            ma5, ma10, ma20 = num('ma5'), num('ma10'), num('ma20')
            a = ratio(py_abs(ma5 - ma10), ma10 + 0.0001)
            b = ratio(py_abs(ma10 - ma20), ma20 + 0.0001)
            return ('[|MA5−MA10|/(MA10+0.0001)]/[|MA10−MA20|/(MA20+0.0001)+0.0001]>%s；'
                    'MA5/10/20=%s/%s/%s，分子=%s，第二间距=%s，扩散比=%s' %
                    (fmt(threshold), fmt(ma5), fmt(ma10), fmt(ma20), fmt(a), fmt(b), fmt(num('ma_spread_ratio'))))

        def rsi_text():
            changes = df['close'].diff()
            gains = changes.where(changes > 0, 0).iloc[-14:].mean()
            losses = (-changes.where(changes < 0, 0)).iloc[-14:].mean()
            return ('RSI=100−100/[1+14行平均上涨/(14行平均下跌绝对值+0.0001)]；'
                    '平均上涨=%s，平均下跌=%s，RSI=%s' % (fmt(gains), fmt(losses), fmt(num('rsi_14'))))

        c, o, h, l, v = [num(k) for k in ('close', 'open', 'high', 'low', 'volume')]
        pc, po, pv = num('close', prev), num('open', prev), num('volume', prev)
        ma5, ma10, ma20, ma60 = [num('ma%d' % p) for p in (5, 10, 20, 60)]
        body = py_abs(c - o)
        lower = py_min(c, o) - l if np.isfinite(c) and np.isfinite(o) else float('nan')
        upper = h - py_max(c, o) if np.isfinite(c) and np.isfinite(o) else float('nan')
        candle = ('O/H/L/C=%s/%s/%s/%s；实体=|C−O|=%s，下影=min(O,C)−L=%s，上影=H−max(O,C)=%s；'
                  '占比均除(H−L+0.0001)=%s；实体/下影/上影占比=%s/%s/%s' %
                  (fmt(o), fmt(h), fmt(l), fmt(c), fmt(body), fmt(lower), fmt(upper), fmt(h - l + 0.0001),
                   fmt(num('body_ratio')), fmt(num('lower_shadow_ratio')), fmt(num('upper_shadow_ratio'))))

        def close_position_text(threshold):
            return ('(C−L)/(H−L+0.0001)>%s；C=%s，L=%s，H=%s，收盘位置=%s' %
                    (fmt(threshold), fmt(c), fmt(l), fmt(h), fmt(num('close_position'))))

        def hammer_text():
            lr, ur = num('lower_shadow_ratio'), num('upper_shadow_ratio')
            return ('锤子线=(下影长度>=2×实体长度 且 下影占比>=50%% 且 上影占比<=15%%)；'
                    '下影长度=%s，2×实体长度=%s，长度条件:%s；下影占比=%s>=0.5:%s；上影占比=%s<=0.15:%s；缓存=%s' %
                    (fmt(lower), fmt(2.*body), compare(lower, '>=', 2.*body),
                     fmt(lr), compare(lr, '>=', .5), fmt(ur), compare(ur, '<=', .15), truth(latest.get('hammer'))))

        def engulfing_text():
            return ('阳包阴=(C>O 且 前C<前O 且 C>前O 且 O<前C)；'
                    '%s>%s:%s，%s<%s:%s，%s>%s:%s，%s<%s:%s；缓存阳包阴=%s' %
                    (fmt(c), fmt(o), compare(c, '>', o), fmt(pc), fmt(po), compare(pc, '<', po),
                     fmt(c), fmt(po), compare(c, '>', po), fmt(o), fmt(pc), compare(o, '<', pc),
                     truth(latest.get('engulfing'))))

        def divergence_text():
            second, lowvolume = num('close_second_low_20'), num('volume_min_20')
            return ('底背离代理=(C<=近20完整行升序第2个收盘值，重复值参与排序/并列包含，且V>最低量×1.12)；'
                    'C=%s，第2低=%s，价格条件:%s；V=%s，最低量=%s，1.12倍=%s，量条件:%s；缓存=%s；不等同真实资金吸筹' %
                    (fmt(c), fmt(second), compare(c, '<=', second), fmt(v), fmt(lowvolume),
                     fmt(lowvolume * 1.12), compare(v, '>', lowvolume * 1.12), truth(latest.get('divergence_bottom'))))

        def pulse_text():
            return ('not volume_pulse；缓存volume_pulse=%s；当前指标实现固定False，此边缘实际恒成立，不代表已完成脉冲识别' %
                    truth(latest.get('volume_pulse')))

        def volume_floor_text(multiplier):
            vm, minimum = num('volume_ma20'), num('volume_min_20')
            return ('V<%s×VMA20 或 |V−近20行最低量|<0.01；V=%s，VMA20=%s，倍数阈值=%s，分支一:%s；'
                    '最低量=%s，绝对差=%s，分支二:%s' %
                    (fmt(multiplier), fmt(v), fmt(vm), fmt(vm * multiplier), compare(v, '<', vm * multiplier),
                     fmt(minimum), fmt(py_abs(v - minimum)), compare(py_abs(v - minimum), '<', .01)))

        opening = float(item.get('open_chg', float('nan')))
        detail = {}
        if combo == 'combo_6':
            core, edge = standard_bull_conditions(latest, opening)
            core_met = py_sum(1 for value in core.values() if ComboEvaluator._safe_bool(value))
            edge_met = py_sum(1 for value in edge.values() if ComboEvaluator._safe_bool(value))
            score = standard_bull_display_score(edge_met, len(edge))
            passed = core_met == len(core) and standard_bull_edge_pass(edge_met)
        else:
            fn = getattr(ComboEvaluator, 'evaluate_' + str(combo))
            passed, score, core_met, edge_met = fn(latest, prev, details=detail)
            core, edge = detail.get('core'), detail.get('edge')
            if not isinstance(core, dict) or not isinstance(edge, dict):
                raise ValueError('正式评估器没有返回条件字典，不臆造条件通过情况')

        opening_pass = bool(np.isfinite(opening) and
                            ((3 <= opening <= 7) if combo == 'combo_3' else
                             (opening > 1.5 if combo == 'combo_6' else opening > 1)))
        names = getattr(g, 'display_names', {})
        label = stock + ('(' + str(names[stock]) + ')' if stock in names else '')
        log.info('【形态条件复核】排名%d | %s | %s | 数据截止%s，前一行%s | 原分%.8f，复核分%.8f | 硬条件%d/%d，边缘%d/%d | 形态复核合格:%s | 开盘门槛合格:%s' %
                 (rank, label, item.get('combo_name', combo), date_at(-1), date_at(-2), float(item['score']),
                  score, core_met, len(core), edge_met, len(edge), truth(passed), truth(opening_pass)))
        consistent = (bool(passed) and opening_pass and py_abs(float(item['score']) - float(score)) < 1e-8 and
                      int(item['core_met']) == int(core_met) and int(item['edge_met']) == int(edge_met))
        if not consistent:
            log.warning('【形态复核不一致】%s | 原记录分/硬/边缘=%s/%s/%s，复核=%s/%s/%s；仅告警，不改候选或委托' %
                        (stock, item.get('score'), item.get('core_met'), item.get('edge_met'), score, core_met, edge_met))
        log.info('【形态计算底稿】%s | %s' % (stock, candle))
        rows = {}
        ceilings = selection_ceiling_metrics(latest)

        if combo == 'combo_1':
            rows = {
                'ma20_shake': ('贴近MA20', '|C−MA20|/MA20<0.03；' + deviation_text(20)),
                'rsi_low': ('RSI偏低', 'RSI<40；' + rsi_text()),
                'volume_dry': ('地量', volume_floor_text(.6)),
                'previous_return_floor': ('前行跌幅限制下跌惯性', '信号日t的t-2行收盘涨幅>=-2%%；前行日期%s，实际=%s，符合:%s；避免回踩前仍有较强下跌冲击' %
                    (date_at(-2), fmt(num('returns_1d', prev), True), new_boundary_compare(num('returns_1d', prev), '>=', -.02))),
                'ma20_atr_floor': ('MA20相对波动尺度防破位', '(C/MA20-1)/(ATRP14/100+0.0001)>=-1；C=%s，MA20=%s，ATR14=%s，ATRP14=%s%%，偏离=%s，符合:%s；低位整理允许偏弱，但不宜明显跌离MA20；ATR用最后15完整行的14个TR均值' %
                    (fmt(c), fmt(ma20), fmt(num('atr14_seed_15rows')), fmt(num('atrp14_pct')), fmt(num('ma20_atr_deviation')), new_boundary_compare(num('ma20_atr_deviation'), '>=', -1.))),
                'slope_up': ('MA20斜率改善', '本行MA20斜率>前一行斜率；本行：' + slope(20) + '；前一行：' + slope(20, -2)),
                'spread_ceiling': ('均线扩散相对失衡上限', 'D=[abs(MA5-MA10)/(MA10+0.0001)]/[abs(MA10-MA20)/(MA20+0.0001)+0.0001]<=1.5；MA5/10/20=%s/%s/%s；D=%s，符合:%s；使用未舍入值' % (fmt(ma5), fmt(ma10), fmt(ma20), fmt(ceilings['accumulation_spread']), truth(ceilings['accumulation_spread_pass']))),
                'convergence': ('均线收敛', convergence_text(.03)),
                'hammer': ('锤子线', hammer_text()),
                'divergence': ('量价底背离', divergence_text()),
                'close_pos': ('收盘位置', close_position_text(.6)),
                'pv_healthy': ('价量齐升', 'C>前C 且 V>前V；%s>%s:%s，%s>%s:%s；缓存=%s' %
                               (fmt(c), fmt(pc), compare(c, '>', pc), fmt(v), fmt(pv), compare(v, '>', pv), truth(latest.get('price_volume_healthy'))))}
        elif combo == 'combo_2':
            rows = {
                'touch_ma10': ('MA10下方回调', '-0.05<(C−MA10)/MA10<-0.02；' + deviation_text(10)),
                'above_ma20': ('站上MA20', 'C>MA20；%s>%s' % (fmt(c), fmt(ma20))),
                'rsi_neutral': ('RSI中性', '45<RSI<60；' + rsi_text()),
                'ma_bull': ('短均线高于MA20', 'MA5>MA20 且 MA10>MA20；%s>%s:%s，%s>%s:%s' %
                            (fmt(ma5), fmt(ma20), compare(ma5, '>', ma20), fmt(ma10), fmt(ma20), compare(ma10, '>', ma20))),
                'volume_shrink': ('昨日缩量', volume_ratio_text(.75)),
                'long_shadow': ('下影长于实体', '下影占比>1.5×实体占比；%s>%s；实际下影长=%s，1.5×实体长=%s' %
                                (fmt(num('lower_shadow_ratio')), fmt(num('body_ratio') * 1.5), fmt(lower), fmt(body * 1.5))),
                'no_pulse': ('非量脉冲', pulse_text()),
                'close_pos': ('收盘位置', close_position_text(.5)),
                'slope_diff': ('MA5斜率强于MA10', 'MA5五行斜率>MA10五行斜率；' + slope(5) + '；' + slope(10))}
        elif combo == 'combo_3':
            angle = num('price_ma_angle')
            rows = {
                'breakout': ('昨日上涨突破', 'R1=C/前C−1>4%%；C=%s，前C=%s，R1=%s' % (fmt(c), fmt(pc), fmt(num('returns_1d'), True))),
                'volume_surge': ('放量', volume_ratio_text(1.3, '>')),
                'ma_converge': ('均线收敛', convergence_text(.025)),
                'price_angle': ('价格偏离角度', 'atan([(C−MA20)/(MA20+0.0001)]×20)×180/π>25度；C=%s，MA20=%s，角度=%s度' %
                                (fmt(c), fmt(ma20), fmt(angle))),
                'ma_spread': ('均线扩散', spread_text(1.8)),
                'body_strong': ('实体强', '|C−O|/(H−L+0.0001)>0.5；实体=%s，实际占比=%s' % (fmt(body), fmt(num('body_ratio')))),
                'engulfing': ('阳包阴', engulfing_text()),
                'close_high': ('收盘靠近高点', close_position_text(.75)),
                'vol_stack': ('近期量增堆叠', '近5行中，V[t]>V[t−1]>V[t−2]的标志求和>=2；实际缓存和=%s；日期底稿见所有指标统计' % fmt(num('volume_stack_days'))),
                'no_pump': ('非量脉冲', pulse_text())}
        elif combo == 'combo_4':
            rows = {
                'bull_arrange': ('价格与均线多头', 'C>MA5>MA10>MA20；%s>%s>%s>%s；三个子项=%s/%s/%s' %
                                 (fmt(c), fmt(ma5), fmt(ma10), fmt(ma20), compare(c, '>', ma5), compare(ma5, '>', ma10), compare(ma10, '>', ma20))),
                'touch_ma10': ('贴近MA10', '|(C−MA10)/MA10|<0.03；' + deviation_text(10)),
                'ma20_up': ('MA20向上', 'MA20五行斜率>0；' + slope(20)),
                'vol_shrink': ('昨日缩量', volume_ratio_text(.8)),
                'lower_shadow': ('下影占比', '[min(O,C)−L]/(H−L+0.0001)>0.35；下影=%s，实际占比=%s' % (fmt(lower), fmt(num('lower_shadow_ratio')))),
                'close_pos': ('收盘位置', close_position_text(.55)),
                'ma_spread': ('均线扩散', spread_text(1.1)),
                'above_ma20_safe': ('高于MA20缓冲', 'C>MA20×1.02；C=%s，MA20=%s，阈值=%s' % (fmt(c), fmt(ma20), fmt(ma20 * 1.02))),
                'vol_healthy': ('量能不过低', 'V>VMA20×0.4；V=%s，VMA20=%s，阈值=%s' % (fmt(v), fmt(num('volume_ma20')), fmt(num('volume_ma20') * .4))),
                'slope_accelerate': ('MA5与MA10偏强', 'MA5五行斜率>3%且MA10五行斜率>1.2%；' + slope(5) + '；' + slope(10))}
        elif combo == 'combo_5':
            r5, rsi = num('returns_5d'), num('rsi_14')
            r1 = num('returns_1d')
            rows = {
                'deep_fall': ('深跌或极低RSI', 'R5=C/C[5行前]−1<-6%% 或 RSI<28；C=%s，5行前C=%s，R5=%s，分支一:%s；%s，分支二:%s' %
                              (fmt(c), fmt(num('close', df.iloc[-6])), fmt(r5, True), compare(r5, '<', -.06), rsi_text(), compare(rsi, '<', 28))),
                'volume_freeze': ('量能冻结', volume_floor_text(.5)),
                'far_ma60': ('远低于MA60', '(C−MA60)/MA60<-0.06；' + deviation_text(60)),
                'previous_rsi_ceiling': ('前行RSI确认先前弱势', '信号日t的t-2行RSI<=40；前行日期%s，RSI=%s，符合:%s；避免先前尚不超跌、刚开始转弱的标的' %
                    (date_at(-2), fmt(num('rsi_14', prev)), new_boundary_compare(num('rsi_14', prev), '<=', 40.))),
                'amplitude_ceiling': ('昨日振幅检验摆动收敛', '(H-L)/(前收+0.0001)<=3.5%%；H=%s，L=%s，前收=%s，实际=%s，符合:%s；超跌后摆动应开始收敛，不把剧烈摆动等同止跌' %
                    (fmt(h), fmt(l), fmt(pc), fmt(num('amplitude_prev_close'), True), new_boundary_compare(num('amplitude_prev_close'), '<=', .035))),
                'ma_converge': ('均线收敛', convergence_text(.04)),
                'rebound': ('昨日反弹', 'R1=C/前C−1>0；C=%s，前C=%s，R1=%s' % (fmt(c), fmt(pc), fmt(r1, True))),
                'hammer_engulf': ('锤子或真实阳包阴', '锤子线 或 (真实阳包阴 且 R1>2%%)；%s；%s；R1=%s，R1>2%%:%s；锤子分支独立，无额外成交量要求' %
                                  (hammer_text(), engulfing_text(), fmt(r1, True), new_boundary_compare(r1, '>', .02))),
                'divergence': ('量价底背离', divergence_text()),
                'low_open_high': ('日内低开高收位置', '开盘位置=(O−L)/(H−L+0.0001)<0.3 且 收盘位置>0.6；开盘位置=%s，子项:%s；收盘位置=%s，子项:%s；缓存=%s' %
                                  (fmt(num('open_position')), compare(num('open_position'), '<', .3), fmt(num('close_position')), compare(num('close_position'), '>', .6), truth(latest.get('low_open_high_close')))),
                'ma_slope_recover': ('MA20斜率改善', '本行MA20斜率>前一行斜率；本行：' + slope(20) + '；前一行：' + slope(20, -2))}
        elif combo == 'combo_6':
            rows = {
                'ma_bull': ('均线多头', 'MA5>MA10>MA20；%s>%s>%s；两个子项=%s/%s' %
                            (fmt(ma5), fmt(ma10), fmt(ma20), compare(ma5, '>', ma10), compare(ma10, '>', ma20))),
                'volume_surge': ('放量', volume_ratio_text(1.2, '>')),
                'opening_strong': ('当日开盘偏强', '100×(固定当日开盘/昨收−1)>1.5；实际开盘涨幅=%s%%，昨收=%s，按该比率反算开盘=%s' %
                                   (fmt(opening), fmt(c), fmt(c * (1 + opening / 100)))),
                'opening_not_hot': ('开盘不过热', '开盘涨幅<5%%；实际=%s%%' % fmt(opening)),
                'volume_ma_bull': ('量均线多头', 'VMA5>VMA20；%s>%s' % (fmt(num('volume_ma5')), fmt(num('volume_ma20')))),
                'close_above_ma5': ('昨收高于MA5', 'C>MA5；%s>%s' % (fmt(c), fmt(ma5))),
                'upper_shadow_short': ('上影占比小', '[H−max(O,C)]/(H−L+0.0001)<0.3；上影=%s，实际占比=%s' % (fmt(upper), fmt(num('upper_shadow_ratio')))),
                'macd_positive': ('MACD柱为正', 'MACD柱=2×(DIF−DEA)>0；DIF=%s，DEA=%s，实际柱=%s；DIF=EMA12−EMA26，DEA=EMA9(DIF)' %
                                  (fmt(num('macd_dif')), fmt(num('macd_dea')), fmt(num('macd'))))}
        else:
            raise ValueError('未知形态' + str(combo))

        if combo in ('combo_2', 'combo_4'):
            threshold = .5 if combo == 'combo_2' else .55
            shadow_text = ('下影占比>1.5×实体占比；实际下影/实体=%s/%s' % (fmt(num('lower_shadow_ratio')), fmt(num('body_ratio')))
                           if combo == 'combo_2' else '下影占比>0.35；实际=%s' % fmt(num('lower_shadow_ratio')))
            rows['shadow_or_close'] = ('下影或收盘位置（仅计一项）', '(' + shadow_text + ') 或 (' + close_position_text(threshold) + ')')
        if combo in ('combo_4', 'combo_6'):
            ev = shape_activity_snapshot(stock, combo)
            rows['spread_floor'] = ('均线扩散硬门槛', spread_text(.6 if combo == 'combo_4' else .25))
            rows['activity_10d'] = ('十日两层活跃硬门槛', activity_snapshot_text(ev))
        if combo == 'combo_6':
            rows['price_ma20_ceiling'] = ('价格偏离MA20上限', 'C/MA20-1<=15%%；C=%s，MA20=%s，偏离=%s，符合:%s；避免价格明显超伸' % (fmt(c), fmt(ma20), fmt(ceilings['price_ma20_offset'], True), truth(ceilings['standard_price_pass'])))
            rows['volume_expansion_ceiling'] = ('两个量能窗口或门槛', 'VMA10/(VMA20+0.0001)<=1.35 或 VMA5/(VMA20+0.0001)<=1.70；VMA10/5/20=%s/%s/%s；比值10/5=%s/%s；两个分支=%s/%s，OR合并=%s；只约束两窗口同时超标' % (fmt(num('volume_ma10')), fmt(num('volume_ma5')), fmt(num('volume_ma20')), fmt(ceilings['volume_ma10_over_ma20']), fmt(ceilings['volume_ma5_over_ma20']), truth(ceilings['volume10_pass']), truth(ceilings['volume5_pass']), truth(ceilings['standard_volume_or_pass'])))
            rows['price_location'] = ('价格相对短均线位置', 'C>MA5 或 MA5>=C>MA10×1.02；C/MA5/MA10=%s/%s/%s；两分支=%s/%s' %
                (fmt(c), fmt(ma5), fmt(ma10), truth(c > ma5), truth(ma5 >= c > ma10 * 1.02)))
            rows['slope_strong'] = ('短均线分段斜率', '(S5>2%且S10>1%)或(S5+S10>3.2%)；S5/S10均为五行变化率；' + slope(5) + '；' + slope(10) + '；斜率和=' + fmt(num('ma5_slope') + num('ma10_slope'), True))
            rows['close_not_far_ma5'] = ('昨收距MA5不过远', 'C/(MA5+0.0001)<1.07；C=%s，MA5=%s，比值=%s' %
                (fmt(c), fmt(ma5), fmt(ratio(c, ma5 + .0001))))
        condition_parts = []
        for group_name, conditions in (('硬条件', core), ('边缘条件', edge)):
            for number, (key, raw_value) in enumerate(conditions.items(), 1):
                name, calculation = rows.get(key, ('条件说明缺失', '正式条件键=' + str(key)))
                if key not in rows:
                    log.warning('【形态字段映射缺失】%s | %s；不能仅凭名称补写公式' % (stock, key))
                condition_parts.append('%s%d[%s/%s] 要求及计算:%s，符合:%s' %
                    (group_name, number, key, name, calculation, truth(raw_value)))
        log.info('【形态条件复核】%s | 明细 | %s | 布尔取正式评估器未舍入结果；v53四硬门槛及阳包阴涨幅仍用1e-12容差，v54三个新增上限直接<=比较；冻结T-1日线与已知开盘；缺失不按0处理' %
                 (stock, '；'.join(condition_parts)))
        if combo != 'combo_6':
            qualification = '边缘至少3/6（原分>=87.5仅展示）' if combo in ('combo_1','combo_5') else ('边缘至少4/5' if combo in ('combo_2','combo_4') else '分数>=90')
            log.info('【形态评分公式】%s | 75×%d/%d+25×%d/%d=%.8f；须全部硬条件且%s；开盘额外门槛:%s，实际开盘涨幅%s%%，符合:%s' %
                     (stock, core_met, len(core), edge_met, len(edge), score, qualification,
                      '3%<=开盘涨幅<=7%' if combo == 'combo_3' else '开盘涨幅>1%', fmt(opening), truth(opening_pass)))
        else:
            log.info('【形态评分公式】%s | 展示分90+10×%d/%d=%.8f；全部硬条件且边缘至少4/5才合格；合格后统一按经济次分排序，不按展示分选优' %
                     (stock, edge_met, len(edge), score))
        if missing:
            log.warning('【形态底稿字段缺失】%s | %s；上方缺失值未替换成0；条件最终布尔仍为正式评估器返回值，须核查数据' %
                        (stock, ','.join(sorted(missing))))
    except Exception as exc:
        log.warning('【形态条件展示异常】%s | %s；只影响日志，不变更原候选/评分/交易' % (stock, str(exc)))


def _v54_candidate_all_indicators(item, rank):
    """Finite, versioned T-1 observation snapshot; no API calls or strategy mutation."""
    stock = str(item['stock'])
    frame = getattr(g, '_micro_data_cache', {}).get(stock)
    if frame is None or len(frame) < 20: raise ValueError('指标观察冻结日线不足20行')
    dates = pd.DatetimeIndex(frame.index)
    if dates.has_duplicates or not dates.is_monotonic_increasing:
        raise ValueError('指标观察日线日期重复或未排序')
    if py_any(x.date() > pd.Timestamp(g.asof).date() for x in dates):
        raise ValueError('指标观察包含信号日前一交易日之后的数据')
    if dates[-1].date() != pd.Timestamp(g.asof).date():
        raise ValueError('指标观察末日不等于昨日，不能冒充昨日数据')
    last, prev = frame.iloc[-1], frame.iloc[-2]
    def number(x):
        try:
            x = float(x)
            return x if np.isfinite(x) else None
        except Exception: return None
    def val(key, row=last): return number(row.get(key))
    def safe_ratio(a, b, eps=0.):
        a, b = number(a), number(b)
        return a / (b + eps) if a is not None and b is not None and b + eps != 0 else None
    def mean_tail(series, count):
        values = [number(x) for x in series.iloc[-count:]]
        return py_sum(values) / count if len(values) == count and py_all(x is not None for x in values) else None
    def raw(row):
        # These are the exact columns of the frozen decision frame, not a second data query.
        return {str(k): (bool(v) if isinstance(v, (bool, np.bool_)) else number(v)) for k, v in row.items()}
    c, o, h, l, v = [val(k) for k in ('close', 'open', 'high', 'low', 'volume')]
    close, volume = frame['close'], frame['volume']
    slopes, slope_inputs = {}, {}
    for period in (5, 10, 20):
        for lag in (3, 5, 10):
            key = 'MA%d_slope%d_ratio' % (period, lag)
            now = val('ma%d' % period)
            before = val('ma%d' % period, frame.iloc[-1-lag]) if len(frame) > lag else None
            result = safe_ratio(now, before)
            slopes[key] = result - 1. if result is not None else None
            slope_inputs[key] = dict(now=now, before=before, before_date=str(dates[-1-lag].date()))
    vm = {'VM%d' % n: mean_tail(volume, n) for n in (3, 5, 10, 20)}
    v_ratios = {'V_over_VM%d_eps' % n: safe_ratio(v, vm['VM%d' % n], .0001) for n in (3, 5, 10, 20)}
    mas = {n: val('ma%d' % n) for n in (5, 10, 20, 60)}
    convergence = {}
    for periods, name in (((5, 10, 20), 'ma3_convergence_ddof1'), ((5, 10, 20, 60), 'ma4_convergence_ddof1')):
        values = [mas[n] for n in periods]
        convergence[name] = float(np.std(values, ddof=1) / (np.mean(values) + .0001)) if py_all(x is not None for x in values) else None
    offset = {'C_vs_MA%d_ratio' % n: (safe_ratio(c, mas[n]) - 1. if safe_ratio(c, mas[n]) is not None else None) for n in (5, 10, 20)}
    ma_bull = mas[5] > mas[10] > mas[20] if py_all(mas[n] is not None for n in (5, 10, 20)) else None
    price_bull = c > mas[5] > mas[10] > mas[20] if c is not None and ma_bull is not None else None
    stack = {}
    for pos in range(-5, 0):
        a, b, cc = [val('volume', frame.iloc[pos-k]) for k in (0, 1, 2)]
        stack[str(dates[pos].date())] = dict(V=a, V_prev=b, V_prev2=cc,
            increasing=a > b > cc if py_all(x is not None for x in (a, b, cc)) else None)
    opening_pct = number(item.get('open_chg'))
    delta = close.diff()
    rsi_gain = delta.where(delta > 0, 0).rolling(14).mean()
    rsi_loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    ema12, ema26 = close.ewm(span=12, adjust=False).mean(), close.ewm(span=26, adjust=False).mean()
    shake_flags = (frame['ma5'].iloc[-6:] > frame['ma20'].iloc[-6:]).astype(int)
    supporting = dict(close_lag5=val('close', frame.iloc[-6]),
        rsi14_average_gain=number(rsi_gain.iloc[-1]), rsi14_average_loss=number(rsi_loss.iloc[-1]),
        ema12=number(ema12.iloc[-1]), ema26=number(ema26.iloc[-1]),
        recent6_ma5_above_ma20={str(d.date()):int(x) for d,x in shake_flags.items()},
        recent6_ma_cross_count=number(shake_flags.diff().abs().sum()),
        rsi_last5={str(d.date()):number(x) for d,x in frame['rsi_14'].iloc[-5:].items()},
        rsi_last5_std_ddof1=number(frame['rsi_14'].iloc[-5:].std(ddof=1)),
        recent10_close_range_ratio=safe_ratio(close.iloc[-10:].max()-close.iloc[-10:].min(),c,.0001),
        volume_last7={str(d.date()):number(x) for d,x in volume.iloc[-7:].items()},
        close_last20={str(d.date()):number(x) for d,x in close.iloc[-20:].items()})
    # Approved additions are observation only; compute using existing frozen rows.
    path = close.iloc[-11:]
    er_distance = number(path.iloc[-1] - path.iloc[0])
    er_length = number(path.diff().abs().iloc[1:].sum())
    er = safe_ratio(py_abs(er_distance), er_length) if er_distance is not None else None
    er_signed = safe_ratio(er_distance, er_length)
    if er_length == 0. and er_distance == 0.: er = er_signed = 0.
    if len(path) != 11 or not bool(np.isfinite(path).all()):
        er = er_signed = er_distance = er_length = None
    last15 = frame.iloc[-15:]
    tr = pd.concat([last15['high']-last15['low'],
                    (last15['high']-last15['close'].shift(1)).abs(),
                    (last15['low']-last15['close'].shift(1)).abs()], axis=1).max(axis=1).iloc[1:]
    atr_source_valid = bool(np.isfinite(last15[['high','low','close']].values).all()) and bool((last15[['high','low','close']].values > 0).all())
    atr_seed = number(tr.mean()) if len(tr) == 14 and bool(np.isfinite(tr).all()) and atr_source_valid else None
    atrp = safe_ratio(atr_seed, c)
    cmf_rows = frame.iloc[-20:]
    money_flow, cmf_volume, cmf_flat_days = [], [], 0
    for _, row in cmf_rows.iterrows():
        hh, ll, cc, vv = [val(key, row) for key in ('high','low','close','volume')]
        if not py_all(x is not None for x in (hh,ll,cc,vv)) or hh < ll or vv < 0 or not ll <= cc <= hh:
            money_flow = []; break
        multiplier = (2.*cc-hh-ll)/(hh-ll) if hh != ll else 0.
        if hh == ll: cmf_flat_days += 1
        money_flow.append(multiplier*vv); cmf_volume.append(vv)
    cmf = safe_ratio(py_sum(money_flow), py_sum(cmf_volume)) if len(money_flow) == 20 else None
    added = dict(ER10=er, ER10_signed=er_signed, ER10_net_change=er_distance, ER10_path_length=er_length, ER10_zero_path=er_length==0. if er_length is not None else None,
        ATR14_seed_15rows=atr_seed, ATRP14_pct=atrp*100. if atrp is not None else None,
        CMF20=cmf, CMF20_volume_sum=py_sum(cmf_volume) if len(money_flow)==20 else None, CMF20_flat_days=cmf_flat_days if len(money_flow)==20 else None,
        basis='ER:11收盘/10变化；ATRP:15日线后14个TR均值/昨收，与现有15根ATR初始化口径一致，不改退出ATR；ATRP用于吸筹新硬门槛；ER/CMF仅观察；CMF:H=L乘子0')
    values = dict(slopes=slopes, slope_inputs=slope_inputs, volume_means=vm, volume_ratios=v_ratios,
        convergence=convergence, price_ma_offsets=offset, ma_bull=ma_bull, price_ma_bull=price_bull,
        opening_gap_pct=opening_pct, known_opening=c*(1.+opening_pct/100.) if c is not None and opening_pct is not None else None,
        price_ma_angle_deg=val('price_ma_angle'), ma_spread_ratio=val('ma_spread_ratio'),
        rsi14_simple=val('rsi_14'), body_ratio=val('body_ratio'), upper_shadow_ratio=val('upper_shadow_ratio'),
        lower_shadow_ratio=val('lower_shadow_ratio'), close_position_ratio=val('close_position'),
        open_position_ratio=val('open_position'), macd_dif=val('macd_dif'), macd_dea=val('macd_dea'),
        macd_histogram=val('macd'), volume_stack5=val('volume_stack_days'), volume_stack_inputs=stack,
        recent20_min_close=number(close.iloc[-20:].min()), recent20_min_volume=number(volume.iloc[-20:].min()),
        recent20_second_close=val('close_second_low_20'), bottom_volume_multiple=val('bottom_volume_multiple'), bottom_volume_k=1.12,
        decision_atr14_seed_15rows=val('atr14_seed_15rows'), decision_atrp14_pct=val('atrp14_pct'),
        decision_ma20_atr_deviation=val('ma20_atr_deviation'), decision_amplitude_prev_close=val('amplitude_prev_close'),
        decision_previous_return=val('returns_1d', prev), decision_previous_rsi=val('rsi_14', prev),
        decision_v54_ceilings=selection_ceiling_metrics(last),
        previous_ma20_slope=val('ma20_slope', prev),
        real_body=py_abs(c-o) if c is not None and o is not None else None,
        lower_shadow=py_min(o,c)-l if py_all(x is not None for x in (o,c,l)) else None,
        upper_shadow=h-py_max(o,c) if py_all(x is not None for x in (o,c,h)) else None)
    return dict(schema='candidate-indicators/v0554',stock=stock,name=getattr(g,'display_names',{}).get(stock),signal_date=str(getattr(g,'day','')),
        asof=str(g.asof),shape=item.get('combo_name'),combo=item.get('combo_type'),rank=int(rank),
        score=item.get('score'),economic_score=item.get('tie_score'),observation_only=False,output_readonly=True,
        priority=item.get('priority'),in_top_n=stock in getattr(g,'qs_combo_info',{}),economic_features=item.get('tie_features'),
        history_rows=len(frame),history_start=str(dates[0].date()),price_basis='same frozen pre-adjusted selection frame',
        row_dates=dict(yesterday=str(dates[-1].date()),previous=str(dates[-2].date())),
        raw_yesterday=raw(last),raw_previous=raw(prev),metrics=values,supporting=supporting,additional_observations=added,
        units='price=元; volume=平台股量; money=元; *_ratio和斜率为小数比例; *_pct为百分数; angle=度; RSI=0..100',
        slope_basis='n行前表示shift(n)，两端相隔n行；沿用形态冻结日线，停牌跳过时不冒充连续交易所日期',
        decision_field_note='这是只读日志快照；部分原始/指标字段已被筛选使用，不是全字段仅观察；decision_*显式记录v53/v54新硬条件输入及v54分支判定',
        null_policy='缺失/非有限=JSON null，不用0代替；volume_pulse=false是沿用的常量而非实测脉冲')


def rank_same_score(items, frame_cache):
    a=[item for item in items if item['combo_type'] in ('combo_2','combo_3','combo_4')]
    b=[item for item in items if item['combo_type'] in ('combo_1','combo_5','combo_6')]
    if len(a)+len(b)!=len(items): raise ValueError('未知形态不参与排序')
    if a:_v50_rank_same_score(a,frame_cache)
    if b:_v54_rank_same_score(b,frame_cache)
    # Global shape priority is used by each pool after frozen within-shape ranking.
    ranked=a+b
    items[:]=[item for shape in ALL_RESEARCH_SHAPES for item in ranked if item['combo_type']==shape]
    return items

def log_candidate_conditions(item, rank):
    function=_v50_log_candidate_conditions if item['combo_type'] in ('combo_2','combo_3','combo_4') else _v54_log_candidate_conditions
    return function(item,rank)

def candidate_all_indicators(item, rank):
    function=_v50_candidate_all_indicators if item['combo_type'] in ('combo_2','combo_3','combo_4') else _v54_candidate_all_indicators
    result=function(item,rank)
    result['candidate_id']=item.get('candidate_id')
    result['research_account_shape']=item['combo_type']
    result['schema_merge']='five-experiments/v0556'
    return result


ALL_RESEARCH_SHAPES=("combo_2","combo_3","combo_5","combo_1","combo_4","combo_6")


# v0.5.57B 最终资金池适配；沿用已回测的订单隔离与同步选股实现。
import copy as _ma_copy
import builtins as _ma_builtins
import hashlib as _ma_hashlib
import json as _ma_json

_MA_CORE_INITIALIZE = initialize
_MA_CORE_HANDLE_DATA = handle_data
_MA_CORE_BUILD_SHARED = build_shared_candidates
_MA_CORE_BUILD_CONCEPT = build_concept_pool
_MA_NATIVE = {name: globals().get(name) for name in (
    'order', 'order_value', 'order_target', 'order_target_value',
    'cancel_order', 'get_orders', 'get_open_orders', 'get_trades',
    'run_daily', 'record', 'get_price', 'attribute_history', 'history',
    'get_security_info', 'get_index_stocks', 'get_trade_days',
    'get_all_securities', 'get_extras', 'get_call_auction')}
_MA_NATIVE_LOG = log
_MA_CORE_CALLBACKS = {name: globals()[name] for name in (
    'prepare_day', 'prepare_holdings', 'plan_sells', 'plan_buys',
    'opening_exit_session', 'opening_session', 'cancel_opening_buys',
    'finish_day', 'acceleration_session')}
_MA_SCHEDULES = {}
_MA_ROOT = None
_MA_CURRENT_INDEX = None
_MA_CURRENT_CONTEXT = None
_MA_RAW_CACHE = {}
_MA_RAW_CACHE_TIME = None
_MA_COLLECT_SCHEDULES = False
_MA_PUBLIC_LOG = False


class _MultiAccountState(object):
    """Only pickleable strategy state; no functions or native context stored here."""
    pass


class _MultiPortfolioView(object):
    def __init__(self, native, initial_cash):
        self._native = native
        self._initial_cash = initial_cash

    @property
    def positions(self):
        return self._native.long_positions

    @property
    def starting_cash(self):
        return self._initial_cash

    @property
    def returns(self):
        return self._native.total_value / self._initial_cash - 1.0

    def __getattr__(self, name):
        return getattr(self._native, name)


class _MultiContextView(object):
    def __init__(self, native, index):
        self._native = native
        self.portfolio = _MultiPortfolioView(
            native.subportfolios[index], _MA_ROOT.ma_initial_cash[index])

    def __getattr__(self, name):
        return getattr(self._native, name)


class _MultiLogView(object):
    def __getattr__(self, name):
        target = getattr(_MA_NATIVE_LOG, name)
        if name not in ('info', 'warning', 'warn', 'error', 'debug'):
            return target
        def write(message, *args, **kwargs):
            if _MA_COLLECT_SCHEDULES and _MA_CURRENT_INDEX not in (None,0) and name in ('info','debug'):
                return None
            if name == 'debug':
                return None
            if name == 'info' and str(message).startswith('【日末缓存清理】'):
                return None
            if _MA_COLLECT_SCHEDULES and _MA_CURRENT_INDEX==0:
                pass
            elif _MA_PUBLIC_LOG:
                message='【公共筛选】'+str(message)
            elif _MA_CURRENT_INDEX is not None and len(_MA_ROOT.ma_profiles) > 1:
                message='【账户%s】%s' % (_MA_ROOT.ma_profiles[_MA_CURRENT_INDEX]['label'],message)
            return target(message,*args,**kwargs)
        return write


log = _MultiLogView()


def _ma_order_key(order_id):
    if _MA_CURRENT_CONTEXT is None:
        raise RuntimeError('账户回调外禁止查询订单归属')
    return (str(_MA_CURRENT_CONTEXT.current_dt.date()), str(order_id))


def _ma_unknown_order(order_id, source):
    key = _ma_order_key(order_id)
    marker = (key, source)
    if marker not in _MA_ROOT.ma_unknown_orders:
        _MA_ROOT.ma_unknown_orders.add(marker)
        _MA_ROOT.ma_order_integrity_blocked = True
        _MA_NATIVE_LOG.error('【全局订单归属异常】日期%s 订单%s 来源%s；不分配给任一账户、不计入他账成交；暂停全局新增买入，已有持仓退出继续，需核对初始化持仓或外部订单' % (key[0], key[1], source))


def _ma_owner(order_id, source=None):
    owner = _MA_ROOT.ma_order_owners.get(_ma_order_key(order_id))
    if owner is None and source is not None:
        _ma_unknown_order(order_id, source)
    return owner


def _ma_submit(api_name, *args, **kwargs):
    if _MA_CURRENT_INDEX is None:
        raise RuntimeError('必须在真实子账户回调内下单')
    if len(args) > 4:
        raise ValueError('多账户版本的pindex必须使用命名参数，禁止第五个位置参数')
    requested = kwargs.pop('pindex', _MA_CURRENT_INDEX)
    if requested != _MA_CURRENT_INDEX:
        raise ValueError('当前账户与订单pindex不一致，禁止跨账户下单')
    security = args[0] if args else kwargs.get('security')
    amount = args[1] if len(args)>1 else kwargs.get('amount',kwargs.get('value',0.))
    is_increase = float(amount) > 0.
    if api_name in ('order_target', 'order_target_value'):
        position = _MA_CURRENT_CONTEXT.subportfolios[_MA_CURRENT_INDEX].long_positions.get(security)
        current = (total_qty(position) if api_name=='order_target' else float(position.value)) if position else 0.
        is_increase = float(amount)>current
    if getattr(_MA_ROOT,'ma_order_integrity_blocked',False) and is_increase:
        log.error('【新增委托停止】存在尚未核验的全局订单归属异常；保留真实持仓和卖出通道')
        return None
    kwargs['pindex'] = _MA_CURRENT_INDEX
    result = _MA_NATIVE[api_name](*args, **kwargs)
    if result is not None:
        key = _ma_order_key(result.order_id)
        old = _MA_ROOT.ma_order_owners.get(key)
        if old is not None and old != _MA_CURRENT_INDEX:
            raise RuntimeError('平台订单ID归属冲突，停止处理')
        _MA_ROOT.ma_order_owners[key] = _MA_CURRENT_INDEX
        _MA_ROOT.ma_order_metadata[key] = dict(
            pindex=_MA_CURRENT_INDEX,
            account=_MA_ROOT.ma_profiles[_MA_CURRENT_INDEX]['label'],
            security=str(args[0]) if args else str(kwargs.get('security', '')),
            submitted=str(_MA_CURRENT_CONTEXT.current_dt))
    return result


def order(*args, **kwargs):
    return _ma_submit('order', *args, **kwargs)


def order_value(*args, **kwargs):
    return _ma_submit('order_value', *args, **kwargs)


def order_target(*args, **kwargs):
    return _ma_submit('order_target', *args, **kwargs)


def order_target_value(*args, **kwargs):
    return _ma_submit('order_target_value', *args, **kwargs)


def _ma_filter_orders(records, source):
    if _MA_CURRENT_INDEX is None:
        return records
    return {key: item for key, item in records.items()
            if _ma_owner(getattr(item, 'order_id', key), source) == _MA_CURRENT_INDEX}


def get_orders(*args, **kwargs):
    return _ma_filter_orders(_MA_NATIVE['get_orders'](*args, **kwargs), 'get_orders')


def get_open_orders(*args, **kwargs):
    return _ma_filter_orders(_MA_NATIVE['get_open_orders'](*args, **kwargs), 'get_open_orders')


def get_trades(*args, **kwargs):
    records = _MA_NATIVE['get_trades'](*args, **kwargs)
    if _MA_CURRENT_INDEX is None:
        return records
    return {key: item for key, item in records.items()
            if _ma_owner(item.order_id, 'get_trades') == _MA_CURRENT_INDEX}


def cancel_order(native_order):
    if _MA_CURRENT_INDEX is None:
        raise RuntimeError('账户回调外禁止撤单')
    oid = getattr(native_order, 'order_id', native_order)
    if _ma_owner(oid, 'cancel_order') != _MA_CURRENT_INDEX:
        raise RuntimeError('不允许撤销其他账户或归属未知订单')
    return _MA_NATIVE['cancel_order'](native_order)


def record(**kwargs):
    if _MA_CURRENT_INDEX is None:
        return _MA_NATIVE['record'](**kwargs)
    prefix = _MA_ROOT.ma_profiles[_MA_CURRENT_INDEX]['metric'] + '_'
    return _MA_NATIVE['record'](**{prefix + key: value for key, value in kwargs.items()})


def _ma_cache_key(value):
    if isinstance(value, dict):
        return tuple(sorted((str(k), _ma_cache_key(v)) for k, v in value.items()))
    if isinstance(value, (list, tuple)):
        return tuple(_ma_cache_key(v) for v in value)
    if isinstance(value, set):
        return tuple(sorted(_ma_cache_key(v) for v in value))
    try:
        hash(value)
        return value
    except TypeError:
        return repr(value)


def _ma_query(name, args, kwargs):
    # Queries only: orders, positions, current quotes and account decisions are never cached.
    if _MA_CURRENT_CONTEXT is None:
        return _MA_NATIVE[name](*args, **kwargs)
    key = (name, _ma_cache_key(args), _ma_cache_key(kwargs))
    if key in _MA_RAW_CACHE:
        _MA_ROOT.ma_query_hits += 1
        return _ma_copy.deepcopy(_MA_RAW_CACHE[key])
    result = _MA_NATIVE[name](*args, **kwargs)
    try:
        _MA_RAW_CACHE[key] = _ma_copy.deepcopy(result)
    except Exception:
        # Failure to copy a native object must never alter selection or suppress the API result.
        return result
    _MA_ROOT.ma_query_misses += 1
    return result


def _ma_install_query_wrapper(name):
    if _MA_NATIVE.get(name) is None:
        return
    def query(*args, **kwargs):
        return _ma_query(name, args, kwargs)
    query.__name__ = name
    globals()[name] = query


for _ma_query_name in ('get_price', 'attribute_history', 'history', 'get_security_info',
                       'get_index_stocks', 'get_trade_days', 'get_all_securities', 'get_extras',
                       'get_call_auction'):
    _ma_install_query_wrapper(_ma_query_name)


_MA_CONCEPT_FIELDS = (
    'base_pool','previous_limit_cache','limit_up_count','concepts',
    'concept_evidence_asof','concept_member_evidence','concept_rank_key','concept_rank_evidence',
    'concept_pool','concept_policy_valid_day','concept_pool_history','concept_pool_legacy_shadow',
    'concept_pool_dedup_shadow','concept_pool_clean_shadow','concept_rolling_evidence','concept_replay_day')


def build_concept_pool(context):
    """One daily concept-policy snapshot; disabled entry filtering needs no popular-concept API."""
    global _MA_PUBLIC_LOG
    if _MA_ROOT is None:return _MA_CORE_BUILD_CONCEPT(context)
    policy=tuple((name,_ma_cache_key(g.cfg.get(name))) for name in (
        'use_concept_selection','concept_source','concept_deduplicate','concept_exclude_broad','concept_rolling'))
    key=(str(context.current_dt.date()),str(g.asof),policy)
    if getattr(_MA_ROOT,'ma_concept_key',None)!=key:
        _ma_shared_failure_barrier('concept',key,context)
        saved={name:(hasattr(g,name),_ma_copy.deepcopy(getattr(g,name,None))) for name in _MA_CONCEPT_FIELDS}
        old_public=_MA_PUBLIC_LOG
        try:
            _MA_PUBLIC_LOG=True
            _MA_ROOT.ma_daily_stats.setdefault(str(context.current_dt.date()),{}).setdefault('concept_attempts',0)
            _MA_ROOT.ma_daily_stats[str(context.current_dt.date())]['concept_attempts']+=1
            result=_MA_CORE_BUILD_CONCEPT(context)
            if getattr(g,'concept_policy_valid_day',None)!=str(context.current_dt.date()):
                raise RuntimeError('概念构建未核验今日政策日期，禁止复用')
            if use_concept_selection() and not {'previous','auction'}<=set(getattr(g,'concept_rank_evidence',{})):
                raise RuntimeError('概念构建缺少昨日/竞价两来源排行，禁止复用')
            _MA_ROOT.ma_concept_snapshot={name:_ma_copy.deepcopy(getattr(g,name)) for name in _MA_CONCEPT_FIELDS if hasattr(g,name)}
            _MA_ROOT.ma_concept_key=key
            _MA_ROOT.ma_concept_builds+=1
            _MA_ROOT.ma_shared_failures.pop('concept',None)
            return result
        except Exception as exc:
            _MA_ROOT.ma_shared_failures['concept']=(key,str(context.current_dt),str(exc))
            for name,(exists,value) in saved.items():
                if exists:setattr(g,name,value)
                elif hasattr(g,name):delattr(g,name)
            _MA_RAW_CACHE.clear()
            raise
        finally:_MA_PUBLIC_LOG=old_public
    for name in _MA_CONCEPT_FIELDS:
        if name in _MA_ROOT.ma_concept_snapshot:setattr(g,name,_ma_copy.deepcopy(_MA_ROOT.ma_concept_snapshot[name]))
        elif hasattr(g,name):delattr(g,name)
    _MA_ROOT.ma_concept_reuses+=1


def _ma_apply_profile():
    if _MA_CURRENT_INDEX is None or not hasattr(g, 'cfg'): return
    p = _MA_ROOT.ma_profiles[_MA_CURRENT_INDEX]
    g.cfg.update(max_count=p['slots'], selection_count=p['finalists'], unit_budget_divisor=p['divisor'],
        enabled_combo_types=p['combos'], use_concept_selection=True,
        capacity_mode='fixed_slots_scaled_unit', apply_micro_position_ratio=True,
        skip_selection_without_capacity=False, log_mode='readable', log_all_indicators=False, research_indicator_logs=False,
        concept_full_ranking_log=False, concept_source_detail_log=False, concept_diagnostic_log=False)
    g.qs_max_count = p['finalists']


def run_daily(function, *args, **kwargs):
    if not _MA_COLLECT_SCHEDULES:
        return _MA_NATIVE['run_daily'](function, *args, **kwargs)
    # initialize constructs cfg before its first registration; patch here before schedule helpers/logs.
    _ma_apply_profile()
    name = function.__name__
    _MA_CORE_CALLBACKS[name] = function
    key = (name, _ma_cache_key(args), _ma_cache_key(kwargs))
    if key not in _MA_SCHEDULES:
        _MA_SCHEDULES[key] = dict(name=name, args=args, kwargs=kwargs, accounts=[])
    if _MA_CURRENT_INDEX not in _MA_SCHEDULES[key]['accounts']:
        _MA_SCHEDULES[key]['accounts'].append(_MA_CURRENT_INDEX)


_MA_SNAPSHOT_DENY = set(('cfg', 'book', 'orders', 'seen_trades', 'fee_seen', 'closed',
    'deferred_breakouts', 'position_archive', 'halted', 'halt_reasons', 'rollover_pending',
    'position_snapshots', 'risk_cap', 'sold_today', 'open_plan', 'late_seed', 'eligibility_fills',
    'candidates', 'signal_cache', 'qs_combo_info', 'attempted_windows', 'position_ratio', 'base_ratio'))


def build_shared_candidates(context,date_str):
    global _MA_PUBLIC_LOG
    if _MA_ROOT is None:return _MA_CORE_BUILD_SHARED(context,date_str)
    key=(str(context.current_dt.date()),str(date_str),bool(g.cfg['use_concept_selection']))
    if getattr(_MA_ROOT,'ma_selection_key',None)!=key:
        _ma_shared_failure_barrier('selection',key,context)
        saved_shapes=g.cfg['enabled_combo_types'];old_public=_MA_PUBLIC_LOG
        try:
            _MA_PUBLIC_LOG=True
            g.cfg['enabled_combo_types']=ALL_RESEARCH_SHAPES
            stats=_MA_ROOT.ma_daily_stats.setdefault(str(context.current_dt.date()),{})
            stats['selection_attempts']=stats.get('selection_attempts',0)+1
            candidates=_MA_CORE_BUILD_SHARED(context,date_str)
            if not getattr(g,'signal_ok',False):raise RuntimeError('共享形态计算失败，不能缓存为有效空池')
            snapshot=getattr(g,'shared_selection_snapshot',None)
            if snapshot is None:raise RuntimeError('共享形态构建未提供冻结事实快照')
            forbidden=set(snapshot)&_MA_SNAPSHOT_DENY
            if forbidden:raise RuntimeError('公共快照混入账户状态:'+','.join(sorted(forbidden)))
            snapshot=dict(snapshot)
            qualified_codes=set(str(item['stock']) for item in candidates)
            snapshot['_micro_data_cache']={stock:frame for stock,frame in snapshot.get('_micro_data_cache',{}).items() if str(stock) in qualified_codes}
            fingerprint=_ma_candidate_fingerprint(candidates)
            # Freeze only after every required calculation completed successfully.
            _MA_ROOT.ma_selection_candidates=_ma_copy.deepcopy(candidates)
            _MA_ROOT.ma_selection_snapshot=_ma_copy.deepcopy(snapshot)
            _MA_ROOT.ma_selection_fingerprint=fingerprint
            _MA_ROOT.ma_selection_key=key
            _MA_ROOT.ma_selection_builds+=1
            stats['selection_successes']=stats.get('selection_successes',0)+1
            stats['fingerprint']=fingerprint
            _MA_ROOT.ma_shared_failures.pop('selection',None)
            g._micro_data_cache=_ma_copy.deepcopy(snapshot['_micro_data_cache'])
            g.shared_selection_snapshot=_ma_copy.deepcopy(snapshot)
            # Log presentation must never invalidate an already frozen decision pool.
            try:_ma_log_shared_candidates(candidates,fingerprint)
            except Exception as log_error:
                log.warning('【公共候选展示异常】%s；共享候选与次分已经成功冻结，不重算、不清空；账户入围与交易继续按冻结事实执行' % log_error)
            # Copy newly observed concept evidence only; frozen eligibility/order/score
            # fields stay unchanged and their selection fingerprint remains valid.
            observed_candidates={(item['combo_type'],item['stock']):item for item in candidates}
            for frozen in _MA_ROOT.ma_selection_candidates:
                observed=observed_candidates.get((frozen['combo_type'],frozen['stock']),{})
                if 'concept_evidence' in observed:
                    frozen['concept_evidence']=_ma_copy.deepcopy(observed['concept_evidence'])
            for target in (_MA_ROOT.ma_selection_snapshot,g.shared_selection_snapshot):
                target['shared_qualified_candidates']=_ma_copy.deepcopy(_MA_ROOT.ma_selection_candidates)
            for name in ('concepts','concept_member_evidence','concept_evidence_asof','display_names'):
                if hasattr(g,name):
                    observed=_ma_copy.deepcopy(getattr(g,name))
                    _MA_ROOT.ma_selection_snapshot[name]=observed
                    g.shared_selection_snapshot[name]=_ma_copy.deepcopy(observed)
        except Exception as exc:
            # No partial candidate pool is usable after a failed attempt.
            _MA_ROOT.ma_selection_key=None
            _MA_ROOT.ma_selection_candidates=[]
            _MA_ROOT.ma_selection_snapshot={}
            _MA_ROOT.ma_shared_failures['selection']=(key,str(context.current_dt),str(exc))
            g.shared_selection_asof=None;g.shared_selection_day=None;g.shared_qualified_candidates=[]
            _MA_RAW_CACHE.clear()
            raise
        finally:g.cfg['enabled_combo_types']=saved_shapes;_MA_PUBLIC_LOG=old_public
    else:
        for name,value in _MA_ROOT.ma_selection_snapshot.items():setattr(g,name,_ma_copy.deepcopy(value))
        _MA_ROOT.ma_selection_reuses+=1
    result=_ma_copy.deepcopy(_MA_ROOT.ma_selection_candidates)
    # v50 get_qs_stock_list checks this account-local success marker before finalization.
    # Set it only after a successful, current-date frozen pool is obtained (including valid empty).
    g.signal_ok=True
    g.shared_qualified_candidates=_ma_copy.deepcopy(result)
    g.shared_selection_fingerprint=_MA_ROOT.ma_selection_fingerprint
    return result


def _ma_cycle(context):
    global _MA_RAW_CACHE_TIME, _MA_RAW_CACHE
    key = context.current_dt
    if _MA_RAW_CACHE_TIME != key:
        _MA_RAW_CACHE_TIME = key
        _MA_RAW_CACHE = {}


def _ma_ensure_root():
    global _MA_ROOT
    if _MA_ROOT is None:
        if not hasattr(g,'ma_states'):
            raise RuntimeError('缺少已初始化的多账户状态，禁止用空账本恢复')
        _MA_ROOT = g


def _ma_call_account(context, index, function, *args):
    global g, _MA_CURRENT_INDEX, _MA_CURRENT_CONTEXT
    previous = (g, _MA_CURRENT_INDEX, _MA_CURRENT_CONTEXT)
    try:
        g = _MA_ROOT.ma_states[index]
        _MA_CURRENT_INDEX = index
        _MA_CURRENT_CONTEXT = context
        proxy = _MultiContextView(context, index)
        result = function(proxy, *args)
        _ma_capture_positions(context,index)
        return result
    finally:
        g, _MA_CURRENT_INDEX, _MA_CURRENT_CONTEXT = previous


def _ma_dispatch(context, name, accounts=None, *args):
    _ma_ensure_root()
    _ma_cycle(context)
    function = _MA_CORE_HANDLE_DATA if name == 'handle_data' else _MA_CORE_CALLBACKS[name]
    for index in (range(len(_MA_ROOT.ma_profiles)) if accounts is None else accounts):
        try:
            if getattr(_MA_ROOT,'ma_order_integrity_blocked',False):
                _ma_call_account(context,index,lambda c:halt_new_buys(c,'GLOBAL_ORDER_OWNERSHIP_ERROR'))
            _ma_call_account(context, index, function, *args)
        except Exception as exc:
            state = _MA_ROOT.ma_states[index]
            state.halted = True
            _MA_NATIVE_LOG.error('【账户回调异常】账户%s 回调%s %s；本账户停止新增，其余账户继续，禁止忽略异常后交易' % (_MA_ROOT.ma_profiles[index]['label'], name, exc))
            try:
                _ma_call_account(context, index, lambda c: halt_new_buys(c, 'MULTI_ACCOUNT_CALLBACK_ERROR', name))
            except Exception:
                pass
    _ma_capture_experiment_positions(context)
    if name == 'finish_day':
        _ma_report_accounts(context)
        # Large reconstructible daily facts must not remain in the persistent root pickle.
        _MA_ROOT.ma_selection_key = None
        _MA_ROOT.ma_selection_candidates = []
        _MA_ROOT.ma_selection_snapshot = {}
        _MA_ROOT.ma_concept_key = None
        _MA_ROOT.ma_concept_snapshot = {}
        for state in _MA_ROOT.ma_states:
            state.shared_selection_snapshot = {}
            state.shared_qualified_candidates = []
        _MA_RAW_CACHE.clear()


def _ma_report_accounts(context):
    values = [float(sub.total_value) for sub in context.subportfolios]
    accounts_total = _ma_builtins.sum(values)
    root_total = float(context.portfolio.total_value)
    tolerance = _ma_builtins.max(.02, _ma_builtins.abs(root_total)*1e-9)
    if _ma_builtins.abs(accounts_total-root_total) > tolerance:
        _MA_NATIVE_LOG.error('【子账户总额对账异常】资金池合计%.6f 平台总资产%.6f 差额%.6f' % (accounts_total, root_total, accounts_total-root_total))
    records = {}
    _MA_NATIVE_LOG.info('========== 日末组合净值与资金对账 ==========')
    group_total = 0.
    stats = _MA_ROOT.ma_daily_stats.get(str(context.current_dt.date()), {})
    for group in _MA_ROOT.ma_groups:
        key = group['id']
        row = _ma_group_values(context, group)
        group_total += row['value']
        nav = row['value'] / _MA_ROOT.ma_group_initial_cash[key]
        high = _ma_builtins.max(_MA_ROOT.ma_group_nav_high[key], nav)
        _MA_ROOT.ma_group_nav_high[key] = high
        dd = 1.-nav/high if high > 0 else 0.
        _MA_ROOT.ma_group_max_drawdown[key] = _ma_builtins.max(_MA_ROOT.ma_group_max_drawdown[key], dd)
        peak = stats.get('group_positions', {}).get(key, {})
        records.update({key+'_nav': nav, key+'_equity': row['value'], key+'_cash': row['cash'],
            key+'_exposure_ratio': row['exposure'], key+'_risk_ratio': row['risk_ratio'],
            key+'_position_count': row['distinct_count'], key+'_account_position_rows': row['holding_rows'],
            key+'_max_drawdown': _MA_ROOT.ma_group_max_drawdown[key],
            key+'_observed_max_count': peak.get('max_count', row['distinct_count']),
            key+'_observed_max_rows': peak.get('max_rows', row['holding_rows']),
            key+'_observed_max_exposure': peak.get('max_exposure', row['exposure'])})
        _MA_NATIVE_LOG.info('【组合汇总】%s %s | 初始%.2f/资产%.2f/现金%.2f/持仓市值%.2f | 净值%.8f/累计收益%.6f%%/收盘最大回撤%.6f%% | 独立股票%d只/持仓记录%d条/仓位%.6f%%/有效预算比例%.6f%% | 同步观测日内最多股票%d只/记录%d条/仓位%.6f%% | pindex=%s' %
            (key, group['label'], _MA_ROOT.ma_group_initial_cash[key], row['value'], row['cash'], row['positions_value'],
             nav, (nav-1)*100, _MA_ROOT.ma_group_max_drawdown[key]*100, row['distinct_count'], row['holding_rows'],
             row['exposure']*100, row['risk_ratio']*100, peak.get('max_count', row['distinct_count']),
             peak.get('max_rows', row['holding_rows']), peak.get('max_exposure', row['exposure'])*100, group['accounts']))
    if _ma_builtins.abs(group_total-accounts_total) > tolerance:
        raise RuntimeError('组合加总与资金池资产不一致，检查账户映射')
    for i, p in enumerate(_MA_ROOT.ma_profiles):
        sub = context.subportfolios[i]
        nav = values[i] / _MA_ROOT.ma_initial_cash[i]
        high = _ma_builtins.max(_MA_ROOT.ma_nav_high[i], nav)
        _MA_ROOT.ma_nav_high[i] = high
        dd = 1.-nav/high if high > 0 else 0.
        _MA_ROOT.ma_max_drawdown[i] = _ma_builtins.max(_MA_ROOT.ma_max_drawdown[i], dd)
        count = _ma_builtins.sum(1 for pos in sub.long_positions.values() if int(getattr(pos, 'total_amount', 0) or 0) > 0)
        exposure = float(sub.positions_value)/values[i] if values[i] > 0 else 0.
        ratio = _ma_call_account(context, i, lambda c: exposure_target_ratio())
        prefix = p['metric']+'_'
        peak = stats.get('account_positions', {}).get(i, {})
        records.update({prefix+'nav': nav, prefix+'exposure_ratio': exposure, prefix+'position_count': count,
            prefix+'risk_ratio': ratio, prefix+'cash': float(sub.available_cash),
            prefix+'max_drawdown': _MA_ROOT.ma_max_drawdown[i],
            prefix+'observed_max_count': peak.get('max_count', count),
            prefix+'observed_max_exposure': peak.get('max_exposure', exposure)})
        if len(_MA_ROOT.ma_profiles) > 1:
            _MA_NATIVE_LOG.info('【账户净值对账】%s | pindex=%d N%d/K%d/D%d | 资产%.2f/现金%.2f/持仓市值%.2f | 收盘%d只/仓位%.6f%%/净值%.8f/累计收益%.6f%%/收盘最大回撤%.6f%% | 观测最多%d只' %
                (p['label'], i, p['slots'], p['finalists'], p['divisor'], values[i], sub.available_cash, sub.positions_value,
                 count, exposure*100, nav, (nav-1)*100, _MA_ROOT.ma_max_drawdown[i]*100, peak.get('max_count', count)))
    distinct = set()
    holding_rows = 0
    for sub in context.subportfolios:
        held = {str(stock) for stock, pos in sub.long_positions.items() if int(getattr(pos, 'total_amount', 0) or 0) > 0}
        distinct.update(held)
        holding_rows += len(held)
    records.update(total_distinct_stocks=len(distinct), total_account_position_rows=holding_rows,
        total_exposure_ratio=_ma_builtins.sum(float(sub.positions_value) for sub in context.subportfolios)/accounts_total if accounts_total > 0 else 0.)
    _MA_NATIVE['record'](**records)


def initialize(context):
    global _MA_ROOT, _MA_COLLECT_SCHEDULES, _MA_SCHEDULES
    _MA_ROOT = g
    _MA_ROOT.ma_groups, _MA_ROOT.ma_profiles = _ma_experiment_layout()
    account_count = len(_MA_ROOT.ma_profiles)
    total_cash = float(context.portfolio.starting_cash)
    if not np.isfinite(total_cash) or total_cash <= 0:
        raise ValueError('初始资金必须为有限正数')
    group_allocations = [total_cash*group['initial_weight'] for group in _MA_ROOT.ma_groups[:-1]]
    group_allocations.append(total_cash-_ma_builtins.sum(group_allocations))
    allocations = [0.]*account_count
    _MA_ROOT.ma_group_initial_cash = {}
    for group, group_cash in zip(_MA_ROOT.ma_groups, group_allocations):
        members = group['accounts']
        assigned = 0.
        for i in members[:-1]:
            allocations[i] = group_cash*_MA_ROOT.ma_profiles[i]['group_weight']
            assigned += allocations[i]
        allocations[members[-1]] = group_cash-assigned
        _MA_ROOT.ma_group_initial_cash[group['id']] = group_cash
    set_subportfolios([SubPortfolioConfig(cash=cash, type='stock') for cash in allocations])
    if len(context.subportfolios) != account_count:
        raise RuntimeError('平台创建的资金池数量与配置不符，停止初始化')
    _MA_ROOT.ma_initial_cash = allocations
    _MA_ROOT.ma_states = [_MultiAccountState() for _ in _MA_ROOT.ma_profiles]
    _MA_ROOT.ma_order_owners = {}; _MA_ROOT.ma_order_metadata = {}; _MA_ROOT.ma_unknown_orders = set()
    _MA_ROOT.ma_order_integrity_blocked = False
    _MA_ROOT.ma_selection_key = None; _MA_ROOT.ma_selection_candidates = []; _MA_ROOT.ma_selection_snapshot = {}
    _MA_ROOT.ma_selection_fingerprint = None
    _MA_ROOT.ma_concept_key = None; _MA_ROOT.ma_concept_snapshot = {}
    _MA_ROOT.ma_query_hits = _MA_ROOT.ma_query_misses = 0
    _MA_ROOT.ma_selection_builds = _MA_ROOT.ma_selection_reuses = 0
    _MA_ROOT.ma_concept_builds = _MA_ROOT.ma_concept_reuses = 0
    _MA_ROOT.ma_shared_failures = {}; _MA_ROOT.ma_daily_stats = {}
    _MA_ROOT.ma_nav_high = [1.]*account_count; _MA_ROOT.ma_max_drawdown = [0.]*account_count
    _MA_ROOT.ma_group_nav_high = {x['id']: 1. for x in _MA_ROOT.ma_groups}
    _MA_ROOT.ma_group_max_drawdown = {x['id']: 0. for x in _MA_ROOT.ma_groups}
    _MA_SCHEDULES = {}; _MA_COLLECT_SCHEDULES = True
    try:
        for index in range(account_count):
            _ma_call_account(context, index, _MA_CORE_INITIALIZE)
            _ma_call_account(context, index, lambda c: _ma_apply_profile())
    finally:
        _MA_COLLECT_SCHEDULES = False
    _MA_ROOT.ma_schedules = list(_MA_SCHEDULES.values())
    for item in _MA_ROOT.ma_schedules:
        _MA_NATIVE['run_daily'](_MA_TIMER_CALLBACKS[item['name']], *item['args'], **item['kwargs'])
    _MA_NATIVE_LOG.info('========== 资金池配置 ==========')
    for i, p in enumerate(_MA_ROOT.ma_profiles):
        names = '/'.join(ComboEvaluator.COMBO_CONFIG[x]['name'] for x in p['combos'])
        _MA_NATIVE_LOG.info('【资金池配置】%s | pindex=%d 初始资金%.2f/占总初始资金%.2f%% | N%d/K%d/D%d | 形态:%s | 标准单笔=本池净值×有效系数÷%d' %
            (p['label'], i, allocations[i], allocations[i]/total_cash*100, p['slots'], p['finalists'], p['divisor'], names, p['divisor']))
    _MA_NATIVE_LOG.info('【选股执行】完整六形态资格和形态内排名每日共算一次，各池按启用形态及统一优先级去重后取前K；订单与持仓独立，入围不等于成交。完整研究指标日志关闭。')


def handle_data(context, data):
    return _ma_dispatch(context, 'handle_data', None, data)


def _ma_timer(context, name):
    _ma_ensure_root()
    clock = context.current_dt.strftime('%H:%M')
    accounts = set()
    for item in _MA_ROOT.ma_schedules:
        timer = item['kwargs'].get('time', item['args'][0] if item['args'] else '09:30')
        if timer == 'open': timer = '09:30'
        if item['name']==name and timer==clock:
            accounts.update(item['accounts'])
    if accounts:
        return _ma_dispatch(context,name,sorted(accounts))


def _ma_prepare_day(context): return _ma_timer(context,'prepare_day')
def _ma_prepare_holdings(context): return _ma_timer(context,'prepare_holdings')
def _ma_plan_sells(context): return _ma_timer(context,'plan_sells')
def _ma_plan_buys(context): return _ma_timer(context,'plan_buys')
def _ma_opening_exit_session(context): return _ma_timer(context,'opening_exit_session')
def _ma_opening_session(context): return _ma_timer(context,'opening_session')
def _ma_cancel_opening_buys(context): return _ma_timer(context,'cancel_opening_buys')
def _ma_finish_day(context): return _ma_timer(context,'finish_day')
def _ma_acceleration_session(context): return _ma_timer(context,'acceleration_session')


_MA_TIMER_CALLBACKS = dict(prepare_day=_ma_prepare_day,prepare_holdings=_ma_prepare_holdings,
    plan_sells=_ma_plan_sells,plan_buys=_ma_plan_buys,opening_exit_session=_ma_opening_exit_session,
    opening_session=_ma_opening_session,cancel_opening_buys=_ma_cancel_opening_buys,
    finish_day=_ma_finish_day,acceleration_session=_ma_acceleration_session)


def _ma_shared_failure_barrier(kind,key,context):
    failure=_MA_ROOT.ma_shared_failures.get(kind)
    if failure and failure[0]==key:
        # Before 09:29 every callback observes the same failed phase. At 09:29
        # a single retry is allowed; another failure blocks its peer accounts too.
        if context.current_dt.strftime('%H:%M')<'09:29' or failure[1]==str(context.current_dt):
            raise RuntimeError('共享%s本轮构建失败，禁止各账户另建快照；09:29统一重试：%s' % (kind,failure[2]))


def _ma_candidate_fingerprint(candidates):
    payload=[]
    for item in candidates:
        payload.append({key:item.get(key) for key in (
            'stock','combo_type','combo_name','priority','score','core_met','edge_met','open_chg','known_day_open',
            'tie_score','tie_raw_order','tie_percentiles','tie_weighted_points','tie_weights','tie_raw_values',
            'tie_features','shape_rank','candidate_id','in_shape_top5','in_shape_top8')})
    text=_ma_json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str)
    return _ma_hashlib.sha256(text.encode('utf-8')).hexdigest()[:20]


def _ma_log_shared_candidates(candidates,fingerprint):
    log.info('【公共完整候选】%d条形态记录 | 六形态独立判断，同股可进入不同账户 | 指纹%s' % (len(candidates),fingerprint))
    saved_info=getattr(g,'qs_combo_info',{})
    def present(label,function,*args):
        try:function(*args)
        except Exception as exc:log.warning('【公共候选观察异常】%s | %s；不改变已冻结资格和排序' % (label,exc))
    try:
        for shape in ALL_RESEARCH_SHAPES:
            rows=[item for item in candidates if item['combo_type']==shape]
            g.qs_combo_info={item['stock']:item for item in rows}
            log.info('【形态候选汇总】%s | 合格%d条；形态内排名已固定；是否入围由各资金池K和形态顺序决定' % (ComboEvaluator.COMBO_CONFIG[shape]['name'],len(rows)))
            for rank,item in enumerate(rows,1):
                key=item['candidate_id']
                log.info('【合格候选】形态排名%d | %s | %s | 原分%.4f/次分%.6f | 开盘涨幅%.4f%% | %s | candidate_id=%s' % (rank,main_shape_display_name(item),stock_label(item['stock']),item['score'],item.get('tie_score',0.),item['open_chg'],'公共合格/非账户入围/尚未成交',key))
                if shape=='combo_2':present('洗盘次分',log_washout_economic_ranking,item,rank)
                elif shape=='combo_4':present('主升次分',log_main_economic_ranking,item,rank)
                elif shape=='combo_3':present('突破次分',log_breakout_economic_score,item)
                else:
                    names,weights,labels=economic_factor_spec(shape)
                    terms=['%s:原值=%s/百分位=%s/权重%.0f/得分=%s'%(label,item.get('tie_raw_values',{}).get(name),item.get('tie_percentiles',{}).get(name),weight,item.get('tie_weighted_points',{}).get(name)) for name,weight,label in zip(names,weights,labels)]
                    log.info('【形态经济次分】candidate_id=%s | 原分优先:%s | %s | 合计%.8f' % (key,shape!='combo_6','；'.join(terms),item.get('tie_score',0.)))
                present('形态条件 '+key,log_candidate_conditions,item,rank)
                present('十日活跃 '+key,log_candidate_shape_observation,item,rank)
                present('历史统计 '+key,log_candidate_history,item['stock'])
                present('概念 '+key,log_candidate_concepts,item['stock'])
                present('全部指标 '+key,log_candidate_all_indicators,item,rank)
    finally:g.qs_combo_info=saved_info


def _ma_capture_positions(context,index):
    """Read-only real-position observations; failure cannot change trade decisions."""
    try:
        sub=context.subportfolios[index]
        held=[stock for stock,pos in sub.long_positions.items() if total_qty(pos)>0]
        nav=float(sub.total_value);exposure=float(sub.positions_value)/nav if nav>0 else 0.
        states=_MA_ROOT.ma_daily_stats.setdefault(str(context.current_dt.date()),{}).setdefault('account_positions',{})
        row=states.setdefault(index,dict(max_count=0,max_count_at=str(context.current_dt),max_exposure=0.))
        if len(held)>row['max_count']:row.update(max_count=len(held),max_count_at=str(context.current_dt))
        row['max_exposure']=py_max(row['max_exposure'],exposure)
        row['last_count']=len(held);row['last_exposure']=exposure
    except Exception as exc:
        _MA_NATIVE_LOG.warning('【持仓观测缺失】账户%d | %s；不修改本账户持仓或订单' % (index,exc))


def _ma_experiment_layout():
    """最终资金池配置；初始比例只在初始化使用，此后独立复利。沿用已验证的账户适配接口。"""
    profiles = [{'label': '六形态共享', 'metric': 'SHARED', 'group_weight': 1.0, 'combos': ('combo_2', 'combo_3', 'combo_5', 'combo_1', 'combo_4', 'combo_6'), 'slots': 8, 'finalists': 8, 'divisor': 5, 'group': 'TOTAL'}]
    groups = [dict(id='TOTAL', label='六形态共享仓位N8/K8/D5', description='单一资金池，初始资金100%，六形态共享资金和名额；N8/K8/D5。',
                   initial_weight=1., accounts=list(range(len(profiles))))]
    if len(profiles) != 1 or len(set(p['metric'] for p in profiles)) != len(profiles):
        raise ValueError('实际资金池标识必须唯一且完整')
    if _ma_builtins.abs(_ma_builtins.sum(p['group_weight'] for p in profiles)-1.) > 1e-12:
        raise ValueError('初始资金比例必须合计100%')
    for p in profiles:
        if p['group_weight'] <= 0 or not p['combos'] or _ma_builtins.any(p[k] <= 0 for k in ('slots','finalists','divisor')):
            raise ValueError('资金比例、形态或N/K/D配置不合法')
        if tuple(s for s in ALL_RESEARCH_SHAPES if s in p['combos']) != p['combos']:
            raise ValueError('资金池形态顺序不符合统一优先级')
    return groups, profiles


def _ma_group_values(context, group):
    """只加总真实子账户；同股跨子账户计多条持仓，独立股票数另列。"""
    value = cash = position_value = risk_budget = 0.
    stocks = set()
    holding_rows = 0
    for i in group['accounts']:
        sub = context.subportfolios[i]
        value += float(sub.total_value)
        cash += float(sub.available_cash)
        position_value += float(sub.positions_value)
        ratio = _ma_call_account(context, i, lambda c: exposure_target_ratio())
        risk_budget += float(sub.total_value) * float(ratio)
        held = {str(s) for s, pos in sub.long_positions.items() if int(getattr(pos, 'total_amount', 0) or 0) > 0}
        stocks.update(held)
        holding_rows += len(held)
    return dict(value=value, cash=cash, positions_value=position_value, distinct_count=len(stocks),
        holding_rows=holding_rows, exposure=position_value/value if value > 0 else 0.,
        risk_ratio=risk_budget/value if value > 0 else 0.)


def _ma_capture_experiment_positions(context):
    """整轮账户回调完成后同步读取组合，禁止将不同时刻各账户峰值相加。"""
    try:
        states = _MA_ROOT.ma_daily_stats.setdefault(str(context.current_dt.date()), {}).setdefault('group_positions', {})
        for group in _MA_ROOT.ma_groups:
            actual = _ma_group_values(context, group)
            row = states.setdefault(group['id'], dict(max_count=0, max_rows=0, max_exposure=0., max_count_at=str(context.current_dt)))
            if actual['distinct_count'] > row['max_count']:
                row.update(max_count=actual['distinct_count'], max_count_at=str(context.current_dt))
            row['max_rows'] = _ma_builtins.max(row['max_rows'], actual['holding_rows'])
            row['max_exposure'] = _ma_builtins.max(row['max_exposure'], actual['exposure'])
    except Exception as exc:
        _MA_NATIVE_LOG.warning('【组合持仓观测缺失】%s；不修改订单与持仓' % exc)
