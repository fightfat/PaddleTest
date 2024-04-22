#!/bin/env python3
# -*- coding: utf-8 -*-
# @author Zeref996
# encoding=utf-8 vi:ts=4:sw=4:expandtab:ft=python
"""
常用tools
"""
import numpy as np
import torch


def reset(seed):
    """
    重置模型图
    :param seed: 随机种子
    :return:
    """
    torch.random.manual_seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed(seed)
    np.random.seed(seed)
    np.set_printoptions(threshold=5, edgeitems=3)
