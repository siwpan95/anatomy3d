# -*- coding: utf-8 -*-
"""anatomy3d —— 开放数据人体解剖 3D 教育查看器。

分层（依赖只能自上而下）::

    cli  ->  viewer / knowledge / pipeline  ->  contracts

contracts 是零依赖的协议层：结构清单（structure manifest）的形状与校验在这里，
资产管线（pipeline）、查看器（viewer）、知识层（knowledge）都以它为对接面。
"""

__version__ = "1.0.0"
