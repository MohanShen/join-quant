# Clone from JoinQuant
# postId: ba4ba214f4c1465fdb24dad6da8a5404
# backtestId: 3382719fcd4afeea6245c61daaa04b01
# title: png文件无法写入到研究环境的根目录下面

from jqdata import *
import datetime
# 导入批数估值模块
from test import *
from kuanke.user_space_api import *
import matplotlib.pyplot as plt
import pandas as pd
import warnings
import numpy as np
import io
from PIL import Image
import cv2
from jqdata import *
fig, axPeriod = plt.subplots() 
fig = plt.gcf()
canvas = fig.canvas
buffer = io.BytesIO()
canvas.print_png(buffer)
data = buffer.getvalue()
buffer.write(data)
img = Image.open(buffer)
img = np.asarray(img)
#write_file('./1.png', img, append=False)
print("准备输出文件")
cv2.imwrite("./龙头周期.png", img)
print("输出完成")
buffer.close()
