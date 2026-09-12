---
title: "【量化课堂】决策树及其主要Ensemble算法的区别和联系"
category: 数学课堂
learners: 7662
postedAt: 2018-01-12 20:07:01
source: 量化课堂 (/study)
fetchedAt: 2026-09-12T16:28:53.469Z
# NOTE: postId/studyId are re-minted per request and are NOT recorded —
#       title + category is this lesson's stable handle.
---

# 【量化课堂】决策树及其主要Ensemble算法的区别和联系

**引言：**本文大致讲讲决策树和它的两种主要优化分支--Bagging和Boosting下的一些重要算法，对于各个算法的详细知识感兴趣的可以看论坛其他文章：[《【量化课堂】随机森林入门》](http://www.joinquant.net/post/1571?f=study&m=math)，[《【量化课堂】决策树入门及Python应用》](http://www.joinquant.net/post/10536?tag=algorithm)。本文是小编随笔， 例子不恰当之处请大家不要打小编。$\text&#123;-\_-#}$

~~~
本文由 JoinQuant 量化课堂推出 。难度标签为入门，理解深度标签：level-0

作者： 大白
编辑： 肖睿
~~~


关键词：[决策树（Decision tree）](http://www.joinquant.net/post/10536?tag=algorithm)，[随机森林（Randomforest）](http://www.joinquant.net/post/1571?f=study&m=math)，Boosting, Bootstrap, Bagging, AdaBoost（自适应性Boosting）, Gradient Boosting（梯度提升boosting） ,GBDT（梯度提升决策树）， XGBoost,  LightGBM
\[ \]
####**本章分为：**

**1，这些家伙是什么，有什么区别？**
决策树Decision tree
Boostrap
套袋法（Bagging）
Boosting
Gradient Boosting
XGBoosting
LightGBM

**2，举个栗子说明一下**
**3，补充和扩展**
\[ \]
##**1，这些家伙是什么，有什么区别？**
####**1，家族关系谱：**

首先直接放图，这是这一家子的大致关系
![比较.PNG][1]


####**决策树Decision tree：**
决策树是一种非参的，监督式的学习方法；是在已知各种情况发生概率的基础上，通过构成决策树来求取净现值期望值大于零的概率，判断其是否会发生的分析方法，是直观运用概率分析的一种图解法。由于这种决策树分支的图形很像树的枝干，故称决策树。下面是一个决策树的例子：
![决策树，兔.PNG][2]

####**Boostrap：**

Boostrap是一个应用广泛且超级实用的统计工具，boostrap在英文里原意“靴带”，现意味不靠他人的帮助，自己取得成功。正如其含义，boostrap是一种通过有放回的抽样方式生成更多样本集，从而达到扩大样本集，来更好研究样本的目的。其过程如下图所示：

![33.PNG][3]

####**套袋法（Bagging）：**
Bagging是一种有效的降低学习器结果方差的方法。其原理是通过boostrap的方式生成更多样本的样本，在每个样本的样本上用学习器学习，最后投票得出最终结果。
其流程如下：

![22.PNG][4]

####**Randomforest：**
随机森林其实就是Bagging在决策树上的实现，只不过新加入一个特色及用boostrap取样本时不仅随机抽样，还限定了特征的数量，丰富了森林里的树木种类。

####**Boosting：**


Boosting方法（代表是Adaboost）是一种用来提高弱分类算法准确度的方法,这种方法通过构造一个预测函数系列,（在这个系列里每个新的学习器都是针对对上一个学习器不足的补充）然后以一定的方式将他们组合成一个预测函数。Boosting是一种提高任意给定学习算法准确度的方法。

与Random Forest不同的是：Random Forest是随机生成新树的，Boosting每一个新的学习器却都是针对性提升上一棵树不足的。Random forest每棵树对最终结果影响相同，Boosting根据使用方法不同，投票比例也不同。

![11.PNG][5]
（图片来自prml p660）


####**Gradient Boosting：**
Gradient Boosting是Boosting方法的一种。不同于boosting代表性的Adaboost，Gradient Boosting每一次的计算是为了减少上一次学习器的残差，从而在残差减少梯度方向上建立新的模型。Gradient Boosting是沿着残差减小的方向一步步优化算法的，和初始的boosting方法中放大错误分类数据比重以求新学习集更加关注错误分类点的方法有明显不同。

####**GBDT（Gradient Boosting Decision Tree）：**
Gradient Boosting 应用于决策树的结果

####**XGBoosting：**
XGboost是Gradient Boosting的改进，其改进的方面包括：
1，	使用了2阶泰勒展开寻找梯度，比之前的一阶效率更高，结果更好
2，	叶节点方面XGboost一方面限制了叶节点总数，另一方面加入了L2正则项，用来防止过拟合
3，	不仅支持基于CART的决策树支持线性分类器作为基本学习器
4，	改进了（弱化了？）划分点查找算法，过去一般直接用遍历或贪心算法寻找最优分割点。XGboost使用候选分割点；分布式加权直方图等方法解决了数据无法一次载入内存导致效率低的问题。此外分布式直方图的方法也使多线程运行成为可能。（据说会损耗一些精度，但不多）
5，	对缺失值的处理—稀疏感知算法
6，	使用了交叉验证（cross validation）
7，	并行化处理提高速度，并使用一些C/C++代码进一步提高运行速度

####**LightGBM：**

微软做的boosting包，开源至今差不多有1年零两个月了，算是目前最优秀的boosting算法之一。和XGBoost类似，改进如下：

1，最最重要的就是深度约束（level-wise）变为叶约束（leaf-wise）的改变了，大大提升了速度和精度。
![LGBM1.PNG][6]

![LGBM2.PNG][7]

2，并行也是一个重点，实现了：
1）特征并行（feature parallel）
2）数据并行（data parallel）
3）投票并行（voting parallel）

这三种并行都是加速数据交互的，对精度没有影响。换句话说处理大数据量时使用它们会变得非常快，小数据量体验不明显。

3，其他的提升
   其他部分的提升就和XGboost差别不大了，包括：
1，	DART: Dropouts meet Multiple Additive Regression Trees
2，	L1/L2 正则
3，	Bagging
4，	Column(feature) 子分类（和随机森林干的一样）
5，	接着已有的GBDT 模型输入继续训练
6，	接着已有的打分结果继续训练
7，	权重训练
8，	训练与评价结果输出并行
9，	多重数据验证（Multi validation data）
10，	多指标（Multi metrics）
11，	Early stopping (both training and prediction)
12，	叶系数的预测Prediction for leaf index

\[ \]
##**2，举个栗子**

最后举个栗子把这些东西串起来吧。


有一个医学专（砖）家，他看过很多很多病人，还记了小本本来归类这些病人的特征和病情来方便以后诊断。有一天来了个病人，这个专家就问病人了，“大爷您贵姓？多少岁，哪不舒服，病情怎么样？”大爷说 “我姓李，48，最近老吐痰，老咳嗽，还发烧…”。这个专家拿出他的小本本一查“”属性：“姓李”，“年龄48”，“吐痰”，“咳嗽”，“发烧”…,根据我的小本本以前这样的病例有80个，有76个是感冒，成，就诊断他是感冒了！”这个专家就是棵**决策树** （专家大呼：“我不是树，我是人”但小编并不理会）

镜头一转，来到医院A，同样的病人来医院A治病。医院有很大的病例数据库，有100个医学专家通过学习数据库的一部分知识形成了自己的诊断方案。医院想：“我财大气粗，为了提供更好的医疗服务，我让100个专家做诊断，然后他们投票决出最后的判断”。**随机森林**完成

医院B就不爽了，你这治疗方案太受欢迎，把客户都抢走了，我要用科学的治疗方案来击败你。医院B想了想，大家投票不一定针对到用户情况，我先从我的100个专家里找一个最好的先给病人做一个诊疗方案，再根据第一个专家的不足找第二个，根据第二个再找第三个…… 最后不同专家再根据他们诊断的表现以不同权重投票。这样岂不是更针对病人痛点？**Boosting**方法就被这群人建立起来了

到了医院C想搞差异化，你医院B根据上一个专家的全部不足找新专家，那我就根据上一个专家判断最偏颇的方向找专家，虽然听起来差不多，但我的差异化说不定就能更好。**Gradient Boosting**产生了

更加财大气粗的医院D来了，他觉得虽然整个市场的大格调基本确定，但我可以通过提升整个诊疗的流程大大小小的细节来取胜啊！于是医院D在C的基础上改进了很多，于是找偏颇的方向更快更准，纠结专家，诊疗的速度也大大加快，整个医院的硬件设施也前所未有的提高。这差不多就是**XGBoost**了

突然有股叫大数据的潮流吹来，本来医院D已经在医院C一分钟治疗10000人的基础上提升了10多倍速度，但新的要求是：一分钟不行，最多给你3秒，10万人也不行，我现在有全世界的数据，你得分秒内召集几百几千个专家，这些专家每一个的知识得相当于以前一个医院那没多，还得分秒内服务数10倍的病人，最后治疗的精度不能下降。**LightGBM**出场了，虽然精度提高不多，但速度大大加快了。
\[ \]
##**3，补充和扩展**

故事讲完了，决策树家族的恩恩怨怨纠纠葛葛也就到这了，对这方面感兴趣的读者可以看看[《【量化课堂】随机森林入门》](http://www.joinquant.net/post/1571?f=study&m=math)，[《【量化课堂】决策树入门及Python应用》](http://www.joinquant.net/post/10536?tag=algorithm)，针对每一部分的原理和python实现有特别的讲解。
\[ \]
~~~
本文由JoinQuant量化课堂推出，版权归JoinQuant所有，商业转载请联系我们获得授权，非商业转载请注明出处。

文章更迭记录：
v1.0，2018-01-12，文章上线
~~~

  [1]: https://image.joinquant.com/9583d4f089e63f9e31aa51d93ee40428
  [2]: https://image.joinquant.com/879ebf0ced92887d6048d83f827a7971
  [3]: https://image.joinquant.com/b7ba740a68560d884a94bc3ff08a772a
  [4]: https://image.joinquant.com/b129abf02ed8117ad9cca4c6bf3783e2
  [5]: https://image.joinquant.com/3621c833becbf7ce04f670f591d9934e
  [6]: https://image.joinquant.com/2bd809ef1ea66545aa0c3da5ae8be641
  [7]: https://image.joinquant.com/60f5226f944d4d4dcaaee06709f33758
