---
title: "【量化课堂】Boosting 介绍和 Python 实现"
category: 数学课堂
learners: 22128
postedAt: 2018-01-12 20:17:29
source: 量化课堂 (/study)
fetchedAt: 2026-09-12T16:28:52.055Z
notebookPath: "Max_AdaBoost.ipynb"
notebookAvailable: false   # 克隆研究 only, spends 积分
# NOTE: postId/studyId are re-minted per request and are NOT recorded —
#       title + category is this lesson's stable handle.
---

# 【量化课堂】Boosting 介绍和 Python 实现

**引言：**Boosting 是一种集成算法，经常使用[决策树（decision tree）](http://www.joinquant.net/post/10536?tag=algorithm)作为基础分类器，有些 Boosting 模型也用逻辑回归（logistic regression），SVM 等方法做分类器的，倘若读者初学机器学习，学习这部分时建议补完决策树的相关知识，帮助理解。本文主要用 Boosting 的始祖算法 AdaBoost 为例介绍其实现流程，希望了解更复杂其他 Boosting 算法的可以看本系列其他文章。

~~~
本文由 JoinQuant 量化课堂推出 。难度标签为入门，需要至少了解一种机器学习模型（决策树，逻辑回归，SVM 等），理解深度标签：level-1

作者： 大白
编辑： 肖睿
~~~
\[ \]

##**简介：**
机器学习中单一的分类器能力有限，也往往达不到充分利用计算机算力，所以多个弱学习集组合来提升总的分类效果就是改进方向之一，Boosting 就是这类集成算法中的典范。

**本章分为：**
1，	Boosting 的由来
2，	Boosting 和 AdaBoost 的思想及流程
 -                         1）	思想
                            2）	算法过程
                            3）	AdaBoosting 的产生和数学推导

3，Boosing 和AdaBoost 主要优点及数学证明：
4，AdaBoost 的 Python 应用举例
5，补充和扩展


##**1，Boosting的由来**
Boosting 是典型的集成算法，它通过结合多个弱分类器（如决策树，逻辑回归），从而形成一个强分类器。但不同于 Bagging 或者 Random Forest 等，Boosting 每个树的生成都基于上一个分类器的结果，会有针对性的将上一个分类器分错的样本提高权重，再建立新的数。这样新的综合的分类器会不断学习一次次分类错误的结果，从而提升算法的能力已达到强分类器的效果。Boosting 算法的始祖是 AdaBoost, 由于其具有 1，在训练集上的错误率上界必然会逐渐下降；2，即使训练次数很多，过拟合的情况也不明显。这些重要优点使它在机器学习中脱颖而出。

在 1990 年，Robert Schapire 构造出一种多项式级算法，可以将偌分类器组合成强分类器，及 Boosting 算法。次年，Yoav Freund 提出了一种效率更高的Boosting 算法，但这两种最初的算法都有缺陷：都需要知道弱学习算法学习正确率的下限。1995 年，Freund 和 Schapire 改进了 Boosting 算法，提出AdaBoost 算法。这一算法在效率与之前算法相同的情况下却不需要任何关于弱学习器的先验知识，适用范围大大增加。之后之后，两位创始人进一步提出AdaBoost.M1（从二分类扩展到多分类问题）、AdaBoost.M1（引入置信度的概念）等算法，在机器学习领域影响深远。Boosting 在人脸识别，文本分类，推荐算法等领域应用广泛。
\[ \]
##**2，Boosting 的思想及流程**
###**2.1思想：**
Bossting 的主要思想非常简单。首先先建立 $M$ 个模型（例如 $M$ 个决策树分类模型），这 $M$ 个模型一般都是比较简单的，被称为弱分类器（weaker learner），Boosting 模型会在每次分类后都把错误数据的权重提高，再用下一个合适的弱分类器进行分类，最后综合全部结果得到最终结果。
![aa3c5328d1cd4c2688eaebb342bd28f4.png][1]
Boosting 模仿了人类的根据错误来学习的学习流程：首先用一种方法尝试，得到结果；集中注意力与上次做错的的地方，在方法库里找一种处理旧的错误更好的方法，并用第二种方法补充第一种方法得到新的可以规避错误的方法……最后在反复衡量各个方法的错误后，归纳成一个对错误数据比较敏感，处理能力更好地综合算法。

###**2.2算法过程：**
在这我们使用 Boosting 中代表性的算法 AdaBoost 来演示 Boosting 的运行详细流程和数学参数更新。AdaBoost 是 Boosting 的鼻祖，AdaBoost 会先选择其中最好的模型进行第一次分类，得到分类结果；第二次循环再提升第一次分错的数据重要性占比，重新更新比重后选择新的最优分类器，权衡前面全部分类器（第二部时有两个）的结果得到新的最终分类器；第三次……, 如此循环，直到约束条件满足。
![281852133944754.jpg][2]

**算法过程如下：**
1, 首先，给定一些点 $(x_1, y_1), (x_2, y_2) , \dots, (x_m, y_m)\ x_i \in X$，是特征空间的坐标（可能如图A所示是二维坐标，也可能是更高维度，便于理解读者把它当做二维空间想象即可）；$y_i \in \&#123; 1, -1 \}$, 是数据属性的标签。
并初始化每个点的比重    $D_1(i) = \frac&#123;1}&#123;m}$

2，迭代开始，对于 $t= 1,2,\dots, T$, 每次迭代的步骤为：


2-1 寻找最优的弱分类器:
$h_t$ 是第 $t$ 次迭代最优的分类器,$\varepsilon$ 是分类器的误差，$y_i$ 是真实值，$H(x_i)$ 是预测值

\[ h_t=\text&#123;argmin}\varepsilon _j =\text&#123;argmin}\sum_&#123;i=1}^m D_t(i)|\&#123;y_i\neq h_j(x_i)\}|\]

2- 2 当误差 $\varepsilon _t \geq \frac&#123;1}&#123;2}$ 时，已近找不到可以提升算法的分类器，结束迭代
2-3 获取分类器权重 $\alpha _t$ （推导部分会详述如何得到这一值)

\[ \alpha _t=\frac&#123;1}&#123;2} \log \frac&#123;1-\varepsilon}&#123;\varepsilon}\]

2-4 更新每个点的权重，返回2开始，进行新一轮迭代

\[ D_&#123;t+1}(i)=\frac&#123;D_&#123;t}(i)\exp(-\alpha _t y_i h_t (x_i))}&#123;Z_t}\]

其中 $Z_t$ 是一个正则化因子，取

\[ Z_t=\sum_&#123;i=1}^m D_t(i) \exp(-\alpha _t y_i h_t (x_i))\]

3，	最后的输出结果为：

\[ H_x=\text&#123;sign}(\sum_&#123;t=1}^T \alpha _t h_t (x))\]

###**2.3AdaBoosting的产生和数学推导:**(数学原理部分，可跳过)

AdaBoosting 的流程虽然简单，但希望深入了解或改进的人肯定会问：找到第一个最优的分类器后，错误的点以多大比率提升重要程度？为什么？分类器又如何投票决出最终结果？步骤中的分类器权重 $\alpha_t=\frac&#123;1}&#123;2} \log \frac&#123;1-\varepsilon}&#123;\varepsilon}$ 是如何得到的？每个点的权重又如何更新？

上述全部问题其实就是最后两个问题的体现，在这笔者将AdaBoost生成的思路和数学推导整理并做详细介绍，提供给希望了解AdaBoost原理甚至做出改进的读者。

从基础来讲Boosting方法就是要先建立简单的弱学习器，然后一步步将其改进为强学习器，AdaBoost也一样，以决策树做基本弱学习器为例，我们从建立第一个弱学习器开始学习AdaBoost的原理。

1，	首先，给定一些点 $(x_1, y_1), (x_2, y_2) , \dots, (x_m, y_m)$; $x_i \in X$，是特征空间的坐标（可能如图A所示是二维坐标，也可能是更高维度，便于理解读者把它当做二维空间想象即可）；$y_i \in \&#123; 1, -1 \}$, 是数据属性的标签。
并初始化每个点的比重    $D_1(i) = \frac&#123;1}&#123;m}$
寻找最优的弱分类器 $h_t=\text&#123;argmin}\varepsilon _j =\text&#123;argmin}\sum_&#123;i=1}^m D_t(i)\&#123;y_i\neq h_j(x_i)\}$

![boosting1.PNG][3]    ![final1.PNG][4]
这部分比较简单，如上面两个例子所示，第一个最优的决策树被建立了起来，它大致将数据中红蓝点区分了出来。（两幅图都是 AdaBoost 第一颗决策树的划分，第二个图是本文 Python 实验里的图，及 sklearn 的示例，由于网络上第一个版本讲解的比较详细，为了更贴合部分读者的理解，笔者接下来就用第系列图来描述 AdaBoost 流程了）

接下来我们要考虑如何提高分错点的权重，如下图有五个分错点。Adaboost 的思想是提高分错点的权重，降低以及正确点的权重，由于我们目前不知道权重如何分配比较好，只知道这应该与分类器的误差相关，所以暂且假设：倘若分类错误，权重乘 $e^β$；倘若分类正确，权重乘 $e^&#123;-β}$。如下图所示
![boosting2.PNG][5]     ![boosting3.PNG][6]

假设预测结果为 $h_1(x_i)$, 真实结果为 $y_i$, 第 $t$ 轮迭代每个点的权重分别是 $D_t(i)$ 则：

\[ D_&#123;t+1}(i)=\frac&#123;D_&#123;t}(i)\exp(-\beta _t y_i h_t (x_i))}&#123;\sum_&#123;i=1}^m D_t(i) \exp(-\beta _t y_i h_t (x_i))}\]

我们将分母以 $Z_t$ 表示

\[ Z_t=\sum_&#123;i=1}^m D_t(i) \exp(-\beta _t y_i h_t (x_i))\] 

其中，当预测错误 $y_i h_t (x_i)=-1$ 时,错误的点扩大到 $e^\beta$ 倍，正确时，$y_i h_t (x_i)=1$，权重缩小比例为 $e^&#123;-\beta}$

我们还可以将 $D_&#123;t+1}(i)$ 写成与 $D_t(i)$ 无关的形式：
\begin&#123;align*}
 D_&#123;t+1}(i) &=\frac&#123;D_&#123;t}(i)\exp(-\beta _t y_i h_t (x_i))}&#123;Z_t}\\
 &=\frac&#123;\exp(- \sum_&#123;t} \beta _t y_i h_t (x_i))}&#123;m\prod_t Z_t}
\end&#123;align*}

得到新的每个点权重比例后，即可进行下一轮循环，再根据新的权重寻找最优分类器。如下图所示：

![boosting4.PNG][7]

......

......

![boosting5.PNG][8]

最后，我们综合上述全部分类器，得到综合分类器为

\[ H(x)=\text&#123;sign}(\alpha_1 h_1+\alpha_2 h_2+\alpha_3 h_3+\dots) \]

其中，sign 函数指的是倘若加权结果大于 $0$，则 $H(x)$ 为 $1$；倘若加权结果小于 $0$，则 $H(x)$ 为 $0$。$\alpha$ 代表每个分类器的投票权重。
\[ H_x= \text&#123;sign}(\sum_&#123;t=1}^T \alpha _t h_t (x))\]

咚咚咚（敲桌子）接下来重点来了，打瞌睡的别睡了，赶紧来听，铺垫结束，接下来是 AdaBoost 的核心思路了。

$\alpha$ 分别是每个分类器的投票权重，显然这个权重应该由分类器的误差决定，误差越小则理应投票权重越大。联系之前我们设的另一个与误差相关的变量 $\alpha$，倘若我们在此再设一个变量 $\beta$，那我们就有两个需要优化的变量 $\alpha$ 和 $\beta$，以及一个自变量误差?。理论上笔者现在应该列一个误差?与变量 $\alpha$ 和 $\beta$ 的公式，然后求极值求偏倒得到?最小情况下变量 $\alpha$ 和 $\beta$ 与?的公式，从而完成最优解带回最初的流程，完成 AdaBoost 流程。

但事实情况是由于?是离散的，其公式为：
\[\varepsilon  = \frac&#123;1}&#123;m}|\&#123; i:H(xi) \neq yi\}|\]

这个东西根本无法求导，所以我们必须将其转化为一个可求导的函数。由于综合函数 $ \text&#123;H}_x=sign(\sum_&#123;t=1}^T \alpha _t h_t (x))$ 与真实值 $y_i$的 误差在 $-y_i f(x_i$ 小于零时为 $1$，大于 $0$ 时为 $0$，如下图蓝线所示。对于这样的离散函数，需要找一个连续的大于它的函数来表示其上界，这样转换中虽然有一定损失，但离散的问题就可以转化为可求导的连续性问题了，我们熟悉的函数中自然数的 $n$ 此方就是这样的函数，我们可以用$\exp(-y_i f(x_i))$来代表其上界，如图，
![桌面.PNG][9]

\[[\![  H(xi) \neq y_i ]\!] \leq \exp(-y_i f(x_i)) \]

显然上式成立，上式描述了每一个离散的结论在 $-y_i f(x_i）\geq 0$ 为 $0$; 反之为 $1$，都在上界 $exp(-y_i f(x_i))$ 之下，那么总的误差的不等式为

\[ \frac&#123;1}&#123;m} \sum_&#123;i} [\![  H(x_i) \neq y_i ]\!] \leq \frac&#123;1}&#123;m} \sum_&#123;i} exp(-y_i f(x_i)) \]

推到这一步看到右边的东西是不是感到很熟悉？回想一下我们的点的权重 $D$
\begin&#123;align*}
D_&#123;t+1}(i) &=\frac&#123;D_&#123;t}(i)\exp(-\beta _t y_i h_t (x_i))}&#123;Z_t}\\
 &=\frac&#123;\exp(- \sum_&#123;t} \beta _t y_i h_t (x_i))}&#123;m\prod_&#123;t} Z_t}
\end&#123;align*}

倘若把错误点权重 $e^\beta$ 中的 $\beta$ 等于分类器权重 $\alpha$，则我们转化的误差上限可以等价于 $D_&#123;T+1}(i)$ 转换后的分母。则假设 $\beta = \alpha$

\begin&#123;align*}
D_&#123;t+1}(i) &=\frac&#123;\text&#123;D}_&#123;t}(i)exp(-\alpha _t y_i h_t (x_i))}&#123;Z_t}\\
&=\frac&#123;exp(- \sum_&#123;t} \alpha _t y_i h_t (x_i))}&#123;m\Pi_t Z_t}\\
&=\frac&#123;exp(y_i f(x_i))}&#123;m\Pi_t Z_t}
\end&#123;align*}

根据上式，我们可以得到：

\begin&#123;align*}
[\![  H(xi) \neq y_i]\!] &\leq exp(-y_i f(x_i)) \\
 \frac&#123;1}&#123;m} \sum_&#123;i} [\![  H(xi) \neq y_i]\!] &\leq \frac&#123;1}&#123;m} \sum_&#123;i} exp(-y_i f(x_i)) \\
&=\sum_&#123;i} (\prod Z_t)D_&#123;T+1}(i) \\
&=\prod Z_t 
\end&#123;align*}

于是得到了误差的上界 $\prod Z_t $ 那么我们的思路就可以转化为最小化误差上界 $\prod Z_t $ 的问题，只要保证每一步得到的 $Z_t$ 都尽量最小，则误差上界必然减小。
则下一步对Zt求导，得

\begin&#123;align*}
 \frac&#123;dZ}&#123;d \alpha}=-\sum_&#123;i=1}^m  D(i)y_ih(x_i)e^&#123;y_i \alpha_i h(x_i)} &=0\\
\sum_&#123;i: h(xi) = y_i}  D(i) e^&#123;-\alpha} + \sum_&#123;i: h(xi) \neq y_i} D(i) e^&#123;\alpha} &=0\\
(1-\epsilon) e^&#123;-\alpha} + \epsilon  e^&#123;\alpha} &=0\\
\alpha &=\frac&#123;1}&#123;2}log\frac&#123;1-\epsilon}&#123;\epsilon} \\
\end&#123;align*}

这样，我们就得到了弱分类器的投票权重和误差点该扩大的比例了。将 $\alpha$ 带回刚开始的步骤，AdaBoost 的模型就完善了。

若读者问这样做的 Boosting 达到最优求解了吗？笔者只能说不知道，也不能给出证明，因为 AdaBoost 的两位创始人大牛的确完美的绕过最优化误差的方法，得到了 AdaBoost 的解法。但倘若有人问 AdaBoost 真的有效吗？我可以肯定的回答：非常有效！因为这一算法在训练集上的误差是指数递减的！而且还不怎么过拟合！！举个例子，很多人听过盲人摸象的故事，讲得是四个盲人各自摸了大象的一部分就以为知道大象了，他们有的说大象像柱子，有的说大象像鞭子，有的说大象像管道，还有一个说大象像墙。这些盲人就像一个个弱学习集，AdaBoost 强大之处在于可以把弱学习集认识的大象组合到一起成为一只完整的大象，而且每次组合都保证可以吸收新学习集比之旧学习集的优秀部分！此外还可以做到兼顾宏观，保证学习的是大象的泛化特征，不会因为学习的大象群里有几个缺胳膊少腿的就学错！！
AdaBoost 的错误上限及防过拟合特性会在下一部分详述。
\[ \]
##**3， Boosing主要优点及解释：**
**Boosting的主要优点有：**

1，	简单且易于代码实现

2，	不需要做特征筛选

3，	极其灵活，可以与任何其他机器学习算法结合

4，	通过对分类能力稍微强于 $1/2$ 的若干弱分类器的训练，可以得到能力大大增强的强分类器(别的学习器也适用)

另外在通常意义 Boosting 的基础上，AdaBoost 的进一步优点有：

5，	无需先验知识（Adaptive Boosting 本来的含义就是自适应性 Boosting）

6，	精度很高

7，	训练得到新分类器在训练集上的误差上限必定会指数速度的下降。

8，	对过拟合（overfitting）敏感，通常迭代次数增加不会造成过拟合

（以下部分了解即可）
---------------------------------------------------------------------------------------------------------------------------
AdaBoost 最吸引人的莫过于最后两点特征，其详细解释如下：
###**1，	误差上限理论。训练集上的误差上限会指数下降**

AdaBoost 的误差上限 $\prod Z_t $为
\[\frac&#123;1}&#123;m} \sum_&#123;i} [\![  H(x_i)\neq y_i]\!] \leq  \prod Z_t \]

证明如下：

\begin&#123;align*}
D_&#123;t+1}(i) &=\frac&#123;D_&#123;t}(i)\exp(-\alpha _t y_i h_t (x_i))}&#123;Z_t}\\
&=\frac&#123;\exp(- \sum_&#123;t} \alpha _t y_i h_t (x_i))}&#123;m\Pi_t Z_t}\\
&=\frac&#123;\exp(y_i f(x_i))}&#123;m\Pi_t Z_t}
\end&#123;align*}

当$H(x_i)\ne y_i$ 时，$y_if(x_i)\leq 0$, 则 $\exp(-y_if(x_i))\gt 1$, 当 $H(x_i)=y_i$ 时，$y_if(x_i) \geq 0$, 则 $\exp(-y_if(x_i))\gt 0$

\begin&#123;align*}
[\![  H(x_i) \neq y_i ]\!] &\leq \exp(-y_i f(x_i)) \\
\frac&#123;1}&#123;m} \sum_&#123;i} [\![  H(x_i) \neq y_i ]\!] &\leq \frac&#123;1}&#123;m} \sum_&#123;i} \exp(-y_i f(x_i)) \\
&=\sum_&#123;i} (\prod Z_t)D_&#123;T+1}(i) \\
&=\prod Z_t 
\end&#123;align*}

![桌面.PNG][10]

于是可知，每添加一个分类器，Adaboost 的误差上界会乘以 $Z_t$ 然后，将$ \alpha _t=\frac&#123;1}&#123;2} \log \frac&#123;1-\varepsilon}&#123;\varepsilon}$ 带入最初假设的 $Z_t$ 中

\begin&#123;align*}
Z_t &=-\sum_&#123;i=1}^m  e^&#123;y_i \alpha_i h_t(x_i)}\\
&=\sum_&#123;i: h(xi) = y_i}  D(i) e^&#123;-\alpha} + \sum_&#123;i: h(xi) \neq y_i} D(i) e^&#123;\alpha}\\
&= (1-\epsilon _t) e^&#123;-\alpha} + \epsilon _t  e^&#123;\alpha}\\
&=2 \sqrt&#123; \varepsilon _t(1-\varepsilon _t)} 
\end&#123;align*}

![zt.PNG][11]

所以$ Z_t=2 \sqrt&#123; \varepsilon _t(1-\varepsilon _t)} $

对于任何 $0$ 到 $1$ 之间变动的 $\varepsilon$，$Z_t$ 总是小于等于 $1$ 的，所以只要可以找到新的分类效果稍微比 $1/2$ 好的分类器，总误差必然会指数下降。

###**2，	对过拟合敏感**
通常来说，根据 VC 维理论，为了提升训练集上的预测精度表现而不断将算法复杂化并不一定能使算法的性能真正提高。初始时学习器通过学习训练集上的重要而泛化的特征的确会使训练集误差和测试集（代表真实情况）误差同时下降，但当泛化的重要特征被学习完，学习器开始学习训练数据的特殊特征时，训练集误差的下降反而伴随着测试集误差的不断上升。如下图所示：

![adaboost1.PNG][12]

但 Boosting 的实验情况却并非如此，下面是一个实验情况：

![adaboost2.PNG][13]

VC 维理论虽然很好的解释了测试误差在训练误差达到一定程度时会上升，但不能很好解释误差在上升后存在下降的现象，此外比起决策树，AdaBoost 的过拟合情况改善了太多。一些博客上同样引用 Robert 在 1997年--1999年左右发表的文章借用 margin 理论来解释这一现象，但 Robert 的理论总有些自吹的味道。AdaBoost 的是否对过拟合有强壮的（robust）抵抗力这一问题到 2012 年为止在国外很多论坛上仍有人讨论（12 年到现在讨论渐渐消失，一方面大家更倾向与用更新的 Boosting 方法，另一方面新的 Boosting 方法如 XGBoosting，LightGBM 都加了很多正则项，算是默认 Boosting 本身防过拟合还不是非常好）。不过可以确定的是 Boosting 方法比起线性回归或者普通的决策树来说防止过拟合的能力已经有了极大提升。

笔者认为 VC 维理论在 AdaBoost 上也是成立的，但 AdaBoost 没有像 VC 维理论预测的一样发生大幅度过拟合的原因有二：

1，	AdaBoost 使用若干数的加权均值，而非最后单一树来进行预测，减轻了过拟合。

虽然在基于上一个分类器错误的基础上建立新的分类器必定存在过拟合状况。但是就像随机森林（random forest）一样，通过对多棵树的综合求解，会大大缓解过拟合情况。


2，	AdaBoost 要求改进的分类器正确率 $k&gt;1/2$ 的分类器。这一要求本身就类似于决策树中的后剪枝，及过拟合部分被截掉了，这注定了 AdaBoost 不会太多的过度生长。


---------------------------------------------------------------------------------------------------------------------------



##**Python 代码应用举例：**
 本部分以 scikit-learn 示例的“Two-class AdaBoost” 作为例子来介绍 AdaBoost 的 Python 应用。

首先，所需的 Python 包，本例中使用 AdaBoost 做 Boosting 方法，用决策树（decision tree）做分类器，所以这两个算法的包需要在此导入。若读者习惯用其他模型，也可以把决策树模型换成其他简单的分类模型。需要注意的是基础模型无需太过复杂，只要确保有 $1/2$ 以上的正确率，AdaBoost 就可以将这些基础模型训练成强学习器。

然后导入数据，在这虚拟产生一些二维数据作为演示，
![举例1.PNG][14]


再之后建立 AdaBoost 模型。AdaBoost 本身不需要太多参数，但基础的分类器需要调整参数。决策树基础的参数含义在上篇“决策树入门及 Python 里提到过了”，感兴趣的读者可以返回看看。在此使用最大深度为 1 的简单决策树作为基本分类器，AdaBoost 使用方法“SAMME”（一种 AdaBoost 实现方法），并迭代 200 次。

![举例2.PNG][15]


预测完成，画出预测结果图：

![举例3.PNG][16]
![final2.PNG][17]


如上图，AdaBoost 分类效果不错，基本可以将红蓝点区分。
\[ \]
##**补充和扩展：**

Boosting 是决策树的重要进阶算法之一（另一种是 Random Forest）。Boosting 算法如今在机器学习领域占有举足轻重的地位，其基础上发展的XGBoost，LightGBM 更是数据分析网站 Kaggle 上的冠军常客，对这一领域有兴趣的读者可以继续关注本系列的其他文章。

\[ \]
#####**参考文献**：
$[1]$Jan Sochman, Jiˇr´ı Matas. “AdaBoost”. Center for Machine Perception Czech Technical University, Prague http://cmp.felk.cvut.cz

$[2]$Robert E. Schapire. “Explaining AdaBoost”. http://rob.schapire.net/papers/explaining-adaboost.pdf

~~~
本文由JoinQuant量化课堂推出，版权归JoinQuant所有，商业转载请联系我们获得授权，非商业转载请注明出处。

文章更迭记录：
v1.0，2018-01-05，文章上线
~~~


  [1]: https://image.joinquant.com/6fb14a1d2832eaca455456561cbc8a2b
  [2]: https://image.joinquant.com/0f052f3a9b1c342788bca804c58de077
  [3]: https://image.joinquant.com/e0534b503f0c109931f62d31d2a7815c
  [4]: https://image.joinquant.com/6242a0a9335134c678538442b8c68d27
  [5]: https://image.joinquant.com/fee03ce8123d086c218efc8b3a126fe1
  [6]: https://image.joinquant.com/02f5c37251c24c96931f1f4d4e94d42c
  [7]: https://image.joinquant.com/e8f6c9081595fbe2ad63f7610b467f81
  [8]: https://image.joinquant.com/8d426ef5a6750375ce190a51a98c470c
  [9]: https://image.joinquant.com/4075fc2a583982071892fdb6b2339ff7
  [10]: https://image.joinquant.com/4075fc2a583982071892fdb6b2339ff7
  [11]: https://image.joinquant.com/1b05c7aac0f816815fade1d7b0974a7b
  [12]: https://image.joinquant.com/ec2001d68fa3efb03cd0239ffd754052
  [13]: https://image.joinquant.com/a3199cdf27908e649312ec63ac6117d7
  [14]: https://image.joinquant.com/ba82b8fe608948e4b3efb9533f577bde
  [15]: https://image.joinquant.com/f41342330e46cbd1ac478fb09e2dcba0
  [16]: https://image.joinquant.com/abfac688b88c8f1a5018f32cf5ab75db
  [17]: https://image.joinquant.com/6b7c529fbc099363125e835f6fb970f4
