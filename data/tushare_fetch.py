import sys
import os
# Ensure the directory containing this script is not on sys.path so local files like
# data/tushare.py or compiled bytecode won't shadow the installed 'tushare' package.
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir in sys.path:
    try:
        sys.path.remove(script_dir)
    except ValueError:
        pass

import tushare as ts
import pandas as pd

# 1. 设置你的tushare token
ts.set_token('779ba1df8ba0642bfba19abd13f4de125693cdca6d49e1840e91121d')
pro = ts.pro_api()

# 2. 获取全部A股股票基础信息
df = pro.stock_basic(
    exchange='',    # 所有交易所
    list_status='L' # 上市状态：L上市 D退市 P暂停
)

# 3. 导出到CSV文件
# 可以直接存到D盘 git_project 文件夹
df.to_csv("./data/AAA.csv", index=False, encoding='utf-8-sig')

print("导出完成！")
print(f"共获取 {len(df)} 只A股")
print(df.head())
import tushare as ts
import pandas as pd

# 1. 设置你的tushare token
ts.set_token('779ba1df8ba0642bfba19abd13f4de125693cdca6d49e1840e91121d')
pro = ts.pro_api()

# 2. 获取全部A股股票基础信息
df = pro.stock_basic(
    exchange='',    # 所有交易所
    list_status='L' # 上市状态：L上市 D退市 P暂停
)

# 3. 导出到CSV文件
# 可以直接存到D盘 git_project 文件夹
df.to_csv("./data/AAA.csv", index=False, encoding='utf-8-sig')

print("导出完成！")
print(f"共获取 {len(df)} 只A股")
print(df.head())
