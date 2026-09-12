---
title: "【有用功】Query的简单教程及TTM/同比/环比算法示例"
category: Python编程
learners: 37008
postedAt: 2019-06-04 18:21:51
source: 量化课堂 (/study)
fetchedAt: 2026-09-12T16:27:12.964Z
notebookPath: "/query及ttm数据教程.ipynb"
notebookAvailable: false   # 克隆研究 only, spends 积分
# NOTE: postId/studyId are re-minted per request and are NOT recorded —
#       title + category is this lesson's stable handle.
---

# 【有用功】Query的简单教程及TTM/同比/环比算法示例

大家刚接触平台可能对于一些数据的提取方式不甚明了,尤其是对query对象的使用。可能将简单问题复杂化,以下整理了大家使用过程中一般能用到的操作方式以及一些常用的数据获取方式。如果大家对于query对象的使用或者某些数据的提取存在疑问,可以在此贴下留言讨论。

关于query对象和sqlalchemy库: https://docs.sqlalchemy.org/en/rel_1_0/orm/query.html
由于这个网站总是抽风,所以下载文档上传到了百度网盘
链接: https://pan.baidu.com/s/1LvWbDXywHTYv_gP0BLkgsA 提取码: 18vu


### 涉及到使用数据库操作的数据有:  
* get_fundamentals  (股票单季度财务数据)
* finance           (股票数据,基金数据等)
* opt               (期权数据)  
* macro             (宏观数据)   
* bond      (债券数据)  

### 基本的查询方式
* query()  填写需要查询的对象,可以是整张表,也可以是表中的多个字段或计算出的结果
* filter 填写过滤条件,多个过滤条件可以用逗号隔开,或者用and_,or_这样的语法  
* order_by  填写排序条件  
  *  .desc()  降序排列
  *  .asc()   升序排列
* limit   限制返回的个数  
* group_by  分组统计

### 其他常用数据获取方式整理
1. 单季度财务数据和报告期财务数据
2. 获取旧的申万指数列表和新的申万指数列表(14年有过改动)
3. 查询申万行情( 包含行业pe/pb)
4. 查询中证行情( 包含指数市值/市盈率/股息率以及红利等指数)
5. 查询股息率(近12个月)
6. 获取期货合约的基本信息（合约乘数、商品报价的计数单位、最小变动单位）  
7. 多个dataframe的合并 (数据拼接) 获取多份财务报表  
8. 利用offset多次查询以跳过限制

###   获取截至目前 前N季度的单季度财务指标
可以通过因子分析模块取到数据,https://www.joinquant.com/help/api/help?name=factor#如何理解dependencies中的财务因子 
相关代码参考TTM计算方法(推荐直接在factor类中计算合并获取到的数据)

###  计算/获取TTM/同比/环比数据(示例代码放在研究后半部分)
各种指标算法多式多样,我们提供的财务数据中最主要的还是单季度和报告期的财务指标,具体算法以及含义在文档中有详细说明
https://www.joinquant.com/help/api/help?name=Stock#获取单季度年度财务数据  
关于两者的区别可以参看这篇帖子理解:  
https://www.joinquant.com/view/community/detail/fcb3baa6f926259c4caac3bce7c12b1c?type=2

TTM/同比/环比数据有些在聚宽因子库中可以直接获取(对于一些指标的算法以及口径有多种方式,所以各平台可能存在不一致)  
https://www.joinquant.com/help/api/help?name=factor_values  
没有提供的可以借助因子分析进行计算  
https://www.joinquant.com/help/api/help?name=factor#示例-计算TTM数据  
https://www.joinquant.com/help/api/help?name=factor#在研究与回测中计算因子
