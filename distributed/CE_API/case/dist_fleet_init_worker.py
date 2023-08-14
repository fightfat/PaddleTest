#!/bin/env python
# -*- coding: utf-8 -*-
# encoding=utf-8 vi:ts=4:sw=4:expandtab:ft=python
# ======================================================================
#
# Copyright (c) 2017 Baidu.com, Inc. All Rights Reserved
#
# ======================================================================
"""
/***************************************************************************
  *
  * Copyright (c) 2019 Baidu.com, Inc. All Rights Reserved
  * @file dist_fleet_worker_index.py
  * @author liujie44@baidu.com
  * @date 2021-11-20 13:07
  * @brief
  *
  **************************************************************************/
"""
import sys
import paddle.distributed.fleet as fleet
from utils import run_priority


fleet.init()
# fleet_base.py:51: UserWarning: init_worker() function doesn't work when use non_distributed fleet.
@run_priority(level="P0")
def test_init_worker():
    """test_barrier_worker"""
    assert fleet.init_worker() is None
    print("{} ... ok".format(sys._getframe().f_code.co_name))


if __name__ == "__main__":
    test_init_worker()
