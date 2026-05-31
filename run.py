#!/usr/bin/env python
"""Dolores 启动入口。

直接运行：  python run.py
推荐用指定环境的解释器：
  /home/dayrker/anaconda3/envs/torch2.10/bin/python run.py
"""
import os
import sys

# 确保能 import 到 dolores 包
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dolores.app import main  # noqa: E402

if __name__ == "__main__":
    main()
