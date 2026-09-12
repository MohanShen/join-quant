---
title: "pandas.dataframe 专题使用指南"
category: Python编程
learners: 44337
postedAt: 2017-10-16 09:29:03
source: 量化课堂 (/study)
fetchedAt: 2026-09-12T16:27:16.891Z
# NOTE: postId/studyId are re-minted per request and are NOT recorded —
#       title + category is this lesson's stable handle.
---

# pandas.dataframe 专题使用指南

取用数据的时候有时候会取用dataframe的格式，很多人都不熟，本篇重点整理了相关的的内容，以便大家查阅和学习。

**蓝字是文章链接，大家都知道吧**

##[选取数据][1]
- 选取行名、列名、值
- 以标签（行、列的名字）为索引选择数据—— x.loc[行标签,列标签]
- 以位置（第几行、第几列）为索引选择数据—— x.iloc[行位置,列位置]
- 同时根据标签和位置选择数据——x.ix[行,列]
- 选择连续的多行多列——切片
- 选择不连续的某几行或某几列
- 简便地获取行或列
- 如何返回一个dataframe的单列或单行
- 按条件选取数据——df[逻辑条件]

##[转置、排序][2]
- 转置 df.T
- 按行名或列名排序——df.sort_index
- 按值排序——df.sort_index

##[增删行或列][3]
- 增加一列
- 增加一行
- 删除行或列——df.drop

##[连接多个dataframe][4]
- 横向连接
- 纵向连接
- 按索引链接

## [组建dataframe][5]
- 组建方法——pd.DataFrame
- 用字典型数据组建——pd.DataFrame
- 简便地获得聚宽数据中的时间索引

## [缺失值处理][6]
- 去掉缺失值——df.dropna
- 对缺失值进行填充——df.fillna
- 判断数据是否为缺失——df.isnull

## [常用统计函数][7]
- 常用统计函数
    - describe 针对Series或个DataFrame列计算汇总统计
    - count 非na值的数量
    - min、max 计算最小值和最大值
    - idxmin、idxmax 计算能够获取到最大值和最小值的索引值
    - quantile 计算样本的分位数（0到1）
    - sum 值的总和
    - mean 值的平均数
    - median 值的算术中位数（50%分位数）
    - mad 根据平均值计算平均绝对离差
    - var 样本值的方差
    - std 样本值的标准差
    - skew 样本值的偏度（三阶矩）
    - kurt 样本值的峰度（四阶矩）
    - cumsum 样本值的累计和
    - cummin，cummax 样本值的累计最大值和累计最小值
    - cumprod 样本值的累计积
    - diff 计算一阶差分
    - pct_change 计算百分数变化
- 查看函数的详细信息
- 更多的函数

## [panel类型数据分解成dataframe][8]
- panel类型数据分解成dataframe方法
- 更多panel操作指路

## [研究内存取dataframe][9]
- 把dataframe存成csv文件——df.to_csv()
- 读取被存成csv文件的dataframe——pd.read_csv()

欢迎反馈建议：）


  [1]: https://www.joinquant.com/post/9328
  [2]: https://www.joinquant.com/post/9330
  [3]: https://www.joinquant.com/post/9333
  [4]: https://www.joinquant.com/post/9329
  [5]: https://www.joinquant.com/post/9369
  [6]: https://www.joinquant.com/post/9373
  [7]: https://www.joinquant.com/post/9374
  [8]: https://www.joinquant.com/post/9375
  [9]: https://www.joinquant.com/post/9401
