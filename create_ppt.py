#!/usr/bin/env python3
"""
Generate a PPT presentation for the Lianghua (量化) Multi-Agent Trading System.
"""

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
import os

# ── Color Palette ──
DARK_BG = RGBColor(0x1a, 0x1a, 0x2e)      # Deep navy
ACCENT_BLUE = RGBColor(0x00, 0xd2, 0xff)   # Cyan accent
ACCENT_GREEN = RGBColor(0x00, 0xff, 0x88)  # Green accent
ACCENT_ORANGE = RGBColor(0xff, 0x8c, 0x00) # Orange accent
ACCENT_PURPLE = RGBColor(0xbb, 0x86, 0xfc) # Purple accent
ACCENT_RED = RGBColor(0xff, 0x55, 0x55)    # Red accent
WHITE = RGBColor(0xff, 0xff, 0xff)
LIGHT_GRAY = RGBColor(0xcc, 0xcc, 0xcc)
DARK_GRAY = RGBColor(0x2d, 0x2d, 0x44)
MEDIUM_GRAY = RGBColor(0x44, 0x44, 0x66)

def add_bg(slide, color=DARK_BG):
    """Add a solid background color to a slide."""
    background = slide.background
    fill = background.fill
    fill.solid()
    fill.fore_color.rgb = color

def add_shape_bg(slide, left, top, width, height, color):
    """Add a colored rectangle shape."""
    shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, left, top, width, height)
    shape.fill.solid()
    shape.fill.fore_color.rgb = color
    shape.line.fill.background()
    return shape

def add_text_box(slide, left, top, width, height, text, font_size=18, color=WHITE, bold=False, alignment=PP_ALIGN.LEFT):
    """Add a text box with specified formatting."""
    txBox = slide.shapes.add_textbox(left, top, width, height)
    tf = txBox.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = text
    p.font.size = Pt(font_size)
    p.font.color.rgb = color
    p.font.bold = bold
    p.alignment = alignment
    return txBox

def add_code_block(slide, left, top, width, height, lines, font_size=11):
    """Add a code-style block with monospace text."""
    add_shape_bg(slide, left, top, width, height, RGBColor(0x0d, 0x11, 0x17))
    txBox = slide.shapes.add_textbox(left + Inches(0.15), top + Inches(0.1), width - Inches(0.3), height - Inches(0.2))
    tf = txBox.text_frame
    tf.word_wrap = True
    for i, line in enumerate(lines):
        if i == 0:
            p = tf.paragraphs[0]
        else:
            p = tf.add_paragraph()
        p.text = line
        p.font.size = Pt(font_size)
        p.font.color.rgb = ACCENT_GREEN
        p.font.name = "Courier New"
        p.space_after = Pt(2)
    return txBox

# ══════════════════════════════════════════════════════════════════
# Slide Builders
# ══════════════════════════════════════════════════════════════════

def create_title_slide(prs):
    """Slide 1: Title"""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_bg(slide)
    add_shape_bg(slide, Inches(0), Inches(0), Inches(13.33), Inches(0.08), ACCENT_BLUE)

    add_text_box(slide, Inches(1), Inches(1.5), Inches(11), Inches(1.2),
                 "Lianghua (量化)", font_size=54, color=ACCENT_BLUE, bold=True, alignment=PP_ALIGN.CENTER)
    add_text_box(slide, Inches(1), Inches(2.8), Inches(11), Inches(0.8),
                 "Multi-Agent Collaborative Quantitative Investment Research System",
                 font_size=24, color=WHITE, alignment=PP_ALIGN.CENTER)
    add_text_box(slide, Inches(1), Inches(3.6), Inches(11), Inches(0.6),
                 "多 Agent 协作量化投研系统",
                 font_size=20, color=LIGHT_GRAY, alignment=PP_ALIGN.CENTER)
    add_text_box(slide, Inches(2), Inches(5.0), Inches(9), Inches(0.6),
                 "LLM-Driven  |  Neo4j Memory  |  ChromaDB RAG  |  Alpaca Trading",
                 font_size=16, color=ACCENT_GREEN, alignment=PP_ALIGN.CENTER)
    add_shape_bg(slide, Inches(0), Inches(7.42), Inches(13.33), Inches(0.08), ACCENT_GREEN)

def create_problem_slide(prs):
    """Slide 2: Problem Statement"""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_bg(slide)
    add_shape_bg(slide, Inches(0), Inches(0), Inches(13.33), Inches(0.08), ACCENT_ORANGE)
    add_text_box(slide, Inches(0.8), Inches(0.4), Inches(11), Inches(0.7),
                 "传统量化投研的痛点", font_size=36, color=ACCENT_ORANGE, bold=True)

    problems = [
        ("流程割裂", "数据获取、因子挖掘、回测、交易执行分散在多个工具中，缺乏统一编排"),
        ("知识流失", "每次策略迭代从零开始，历史经验、失败教训无法沉淀复用"),
        ("人力瓶颈", "因子挖掘依赖人工经验，难以系统性地探索海量因子空间"),
        ("响应滞后", "人工完成 数据->分析->决策->执行 循环耗时长，错过交易窗口"),
    ]
    for i, (title, desc) in enumerate(problems):
        y = 1.5 + i * 1.3
        add_shape_bg(slide, Inches(1), Inches(y), Inches(11), Inches(1.1), DARK_GRAY)
        add_text_box(slide, Inches(1.3), Inches(y + 0.15), Inches(0.6), Inches(0.6),
                     str(i + 1), font_size=28, color=ACCENT_ORANGE, bold=True, alignment=PP_ALIGN.CENTER)
        add_text_box(slide, Inches(2.2), Inches(y + 0.1), Inches(9), Inches(0.4),
                     title, font_size=22, color=WHITE, bold=True)
        add_text_box(slide, Inches(2.2), Inches(y + 0.55), Inches(9), Inches(0.4),
                     desc, font_size=15, color=LIGHT_GRAY)

def create_solution_slide(prs):
    """Slide 3: Solution Approach"""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_bg(slide)
    add_shape_bg(slide, Inches(0), Inches(0), Inches(13.33), Inches(0.08), ACCENT_GREEN)
    add_text_box(slide, Inches(0.8), Inches(0.4), Inches(11), Inches(0.7),
                 "解决思路", font_size=36, color=ACCENT_GREEN, bold=True)

    solutions = [
        ("LLM 驱动的多 Agent 协作", "每个 Agent 专注一个环节，通过 Orchestrator 统一调度", ACCENT_BLUE),
        ("图记忆系统 (Neo4j)", "策略表现、失败教训、市场规律自动沉淀为结构化知识图谱", ACCENT_PURPLE),
        ("RAG 知识库 (ChromaDB)", "量化论文（Alpha101）向量化，Agent 实时检索学术研究成果", ACCENT_ORANGE),
        ("全自动流水线", "从全市场拉取到订单执行，一键完成", ACCENT_GREEN),
    ]
    for i, (title, desc, color) in enumerate(solutions):
        y = 1.5 + i * 1.3
        add_shape_bg(slide, Inches(1), Inches(y), Inches(11), Inches(1.1), DARK_GRAY)
        add_text_box(slide, Inches(1.5), Inches(y + 0.1), Inches(10), Inches(0.4),
                     title, font_size=22, color=color, bold=True)
        add_text_box(slide, Inches(1.5), Inches(y + 0.55), Inches(10), Inches(0.4),
                     desc, font_size=15, color=LIGHT_GRAY)

def create_architecture_slide(prs):
    """Slide 4: System Architecture"""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_bg(slide)
    add_shape_bg(slide, Inches(0), Inches(0), Inches(13.33), Inches(0.08), ACCENT_BLUE)
    add_text_box(slide, Inches(0.8), Inches(0.3), Inches(11), Inches(0.6),
                 "系统架构总览", font_size=36, color=ACCENT_BLUE, bold=True)

    # Data layer
    add_shape_bg(slide, Inches(1), Inches(1.1), Inches(11.33), Inches(0.7), MEDIUM_GRAY)
    add_text_box(slide, Inches(1.2), Inches(1.15), Inches(10), Inches(0.5),
                 "Market Universe | Alpaca API 全市场股票池 (NYSE/NASDAQ) | 24h 磁盘缓存",
                 font_size=15, color=ACCENT_GREEN, bold=True)

    add_text_box(slide, Inches(6.2), Inches(1.8), Inches(1), Inches(0.4),
                 "v", font_size=24, color=ACCENT_BLUE, alignment=PP_ALIGN.CENTER)

    # Orchestrator
    add_shape_bg(slide, Inches(3), Inches(2.2), Inches(7.33), Inches(0.7), DARK_GRAY)
    add_text_box(slide, Inches(3.2), Inches(2.25), Inches(6), Inches(0.5),
                 "Orchestrator | 编排调度层 | 快照预筛 + RAG查询 + 记忆查询",
                 font_size=15, color=ACCENT_ORANGE, bold=True)

    add_text_box(slide, Inches(6.2), Inches(2.9), Inches(1), Inches(0.4),
                 "v", font_size=24, color=ACCENT_BLUE, alignment=PP_ALIGN.CENTER)

    # Agent layer
    agents = [
        ("Alpha Agent\n信号生成", ACCENT_BLUE),
        ("Risk Agent\n风险控制", ACCENT_ORANGE),
        ("Portfolio Agent\n组合优化", ACCENT_GREEN),
        ("Backtest Agent\n回测评估", ACCENT_PURPLE),
        ("Execution Agent\n订单执行", ACCENT_RED),
    ]
    for i, (name, color) in enumerate(agents):
        x = 0.8 + i * 2.5
        add_shape_bg(slide, Inches(x), Inches(3.4), Inches(2.2), Inches(0.9), DARK_GRAY)
        add_text_box(slide, Inches(x + 0.1), Inches(3.45), Inches(2), Inches(0.7),
                     name, font_size=12, color=color, bold=True, alignment=PP_ALIGN.CENTER)

    add_text_box(slide, Inches(6.2), Inches(4.3), Inches(1), Inches(0.4),
                 "v", font_size=24, color=ACCENT_BLUE, alignment=PP_ALIGN.CENTER)

    # Memory layer
    add_shape_bg(slide, Inches(2), Inches(4.7), Inches(9.33), Inches(1.1), MEDIUM_GRAY)
    add_text_box(slide, Inches(2.2), Inches(4.75), Inches(4), Inches(0.4),
                 "Neo4j 图记忆", font_size=16, color=ACCENT_PURPLE, bold=True)
    add_text_box(slide, Inches(6.5), Inches(4.75), Inches(4), Inches(0.4),
                 "ChromaDB RAG 向量库", font_size=16, color=ACCENT_ORANGE, bold=True)
    add_text_box(slide, Inches(2.2), Inches(5.2), Inches(8.5), Inches(0.4),
                 "MCP / A2A Agent 间通信协议  |  策略反思存储  |  Alpha101 论文检索",
                 font_size=13, color=LIGHT_GRAY)

    # Agent-as-Tool annotation
    add_shape_bg(slide, Inches(0.5), Inches(6.2), Inches(12.33), Inches(0.8), RGBColor(0x1e, 0x2a, 0x3a))
    add_text_box(slide, Inches(0.8), Inches(6.25), Inches(11.5), Inches(0.6),
                 "Agent-as-Tool 模式: 每个 Agent 既可独立运行，也可被 Orchestrator 作为子工具调度调用",
                 font_size=14, color=ACCENT_GREEN, alignment=PP_ALIGN.CENTER)

# ══════════════════════════════════════════════════════════════════
# Agent Detail Slides
# ══════════════════════════════════════════════════════════════════

def create_alpha_agent_slide(prs):
    """Slide 5: Alpha Agent Working Principle"""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_bg(slide)
    add_shape_bg(slide, Inches(0), Inches(0), Inches(13.33), Inches(0.08), ACCENT_BLUE)
    add_text_box(slide, Inches(0.8), Inches(0.3), Inches(11), Inches(0.6),
                 "Alpha Agent | 信号生成引擎", font_size=36, color=ACCENT_BLUE, bold=True)

    # Left: Pipeline flow
    add_text_box(slide, Inches(0.8), Inches(1.1), Inches(5.5), Inches(0.4),
                 "工作流程 (Pipeline)", font_size=20, color=ACCENT_GREEN, bold=True)

    steps = [
        ("1. 接收市场数据", "从 Orchestrator 获取 train_data + test_data"),
        ("2. 计算技术指标", "RSI(14) / MACD(12,26) / Bollinger(20,2)"),
        ("3. 准备特征矩阵", "将指标作为 X，forward return 作为 y"),
        ("4. 训练 ML 模型", "在 train_data 上 fit (Linear / RF / LightGBM)"),
        ("5. 生成预测", "在 test_data 上 predict，得到每只股票得分"),
        ("6. 转化为信号", "score > threshold -> +1 (买入), < -threshold -> -1 (卖出)"),
    ]

    for i, (title, desc) in enumerate(steps):
        y = 1.6 + i * 0.85
        # Step box
        add_shape_bg(slide, Inches(0.8), Inches(y), Inches(5.5), Inches(0.7), DARK_GRAY)
        add_text_box(slide, Inches(1.0), Inches(y + 0.02), Inches(5), Inches(0.3),
                     title, font_size=14, color=ACCENT_BLUE, bold=True)
        add_text_box(slide, Inches(1.0), Inches(y + 0.32), Inches(5), Inches(0.3),
                     desc, font_size=12, color=LIGHT_GRAY)

    # Right: Key details
    add_text_box(slide, Inches(7), Inches(1.1), Inches(5.5), Inches(0.4),
                 "核心机制", font_size=20, color=ACCENT_ORANGE, bold=True)

    # Train/Test split box
    add_shape_bg(slide, Inches(7), Inches(1.6), Inches(5.5), Inches(1.4), DARK_GRAY)
    add_text_box(slide, Inches(7.2), Inches(1.65), Inches(5), Inches(0.3),
                 "防泄漏: Train/Test 严格分离", font_size=15, color=ACCENT_RED, bold=True)
    add_text_box(slide, Inches(7.2), Inches(2.0), Inches(5), Inches(0.9),
                 "Orchestrator 提供 365 天 lookback 数据\n"
                 "train_data: 历史区间 (模型学习)\n"
                 "test_data:  当前区间 (生成信号)\n"
                 "模型只在 train 上 fit，test 上 predict",
                 font_size=12, color=LIGHT_GRAY)

    # LLM involvement box
    add_shape_bg(slide, Inches(7), Inches(3.2), Inches(5.5), Inches(1.4), DARK_GRAY)
    add_text_box(slide, Inches(7.2), Inches(3.25), Inches(5), Inches(0.3),
                 "LLM 参与方式", font_size=15, color=ACCENT_PURPLE, bold=True)
    add_text_box(slide, Inches(7.2), Inches(3.6), Inches(5), Inches(0.9),
                 "Agent 通过 OpenAI Function Calling 调度工具:\n"
                 "run_alpha_pipeline -> 一键执行全流程\n"
                 "calculate_indicators -> 单独计算指标\n"
                 "train_predict -> 单独训练预测\n"
                 "submit_signals -> 提交最终信号",
                 font_size=12, color=LIGHT_GRAY)

    # Factors box
    add_shape_bg(slide, Inches(7), Inches(4.8), Inches(5.5), Inches(1.6), DARK_GRAY)
    add_text_box(slide, Inches(7.2), Inches(4.85), Inches(5), Inches(0.3),
                 "因子体系 (Qlib Alpha158)", font_size=15, color=ACCENT_GREEN, bold=True)
    add_text_box(slide, Inches(7.2), Inches(5.2), Inches(5), Inches(1.1),
                 "158 个标准化因子，涵盖:\n"
                 "  - 动量因子 (Momentum)\n"
                 "  - 均值回复 (Mean Reversion)\n"
                 "  - 波动率因子 (Volatility)\n"
                 "  - 成交量因子 (Volume)\n"
                 "  - 技术指标 (RSI/MACD/Bollinger)",
                 font_size=12, color=LIGHT_GRAY)

def create_risk_agent_slide(prs):
    """Slide 6: Risk Agent Working Principle"""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_bg(slide)
    add_shape_bg(slide, Inches(0), Inches(0), Inches(13.33), Inches(0.08), ACCENT_ORANGE)
    add_text_box(slide, Inches(0.8), Inches(0.3), Inches(11), Inches(0.6),
                 "Risk Agent | 风险控制系统", font_size=36, color=ACCENT_ORANGE, bold=True)

    # Left: Risk dimensions
    add_text_box(slide, Inches(0.8), Inches(1.1), Inches(5.5), Inches(0.4),
                 "多维度风险评估", font_size=20, color=ACCENT_ORANGE, bold=True)

    risk_dims = [
        ("市场风险 (Volatility)", "rolling_vol = returns.rolling(20).std() * sqrt(252)\n20日滚动年化波动率，>30% 判定为 HIGH", ACCENT_RED),
        ("尾部风险 (VaR 95%)", "var = np.percentile(returns, 5)\n历史模拟法，<-3% 判定为 HIGH", ACCENT_ORANGE),
        ("综合风险评分", "score = volatility_score + var_score\n>=0.5 -> HIGH, <0.5 -> LOW", ACCENT_BLUE),
        ("风险信号输出", "overall_risk_level: HIGH / LOW\nrisk_score: 0.0 ~ 1.0", ACCENT_GREEN),
    ]

    for i, (title, desc, color) in enumerate(risk_dims):
        y = 1.6 + i * 1.35
        add_shape_bg(slide, Inches(0.8), Inches(y), Inches(5.5), Inches(1.15), DARK_GRAY)
        add_text_box(slide, Inches(1.0), Inches(y + 0.05), Inches(5), Inches(0.3),
                     title, font_size=15, color=color, bold=True)
        add_text_box(slide, Inches(1.0), Inches(y + 0.35), Inches(5), Inches(0.7),
                     desc, font_size=12, color=LIGHT_GRAY)

    # Right: Pipeline flow
    add_text_box(slide, Inches(7), Inches(1.1), Inches(5.5), Inches(0.4),
                 "工作流程", font_size=20, color=ACCENT_GREEN, bold=True)

    add_shape_bg(slide, Inches(7), Inches(1.6), Inches(5.5), Inches(5.0), DARK_GRAY)

    flow_steps = [
        ("Step 1: 接收数据", "从 Orchestrator 获取 test_data"),
        ("Step 2: 计算收益率", "if 多只股票: 按日期取平均 close\nelse: 直接计算 pct_change()"),
        ("Step 3: 波动率计算", "_calculate_volatility(returns, window=20)"),
        ("Step 4: VaR 计算", "_calculate_var(returns, confidence=0.05)"),
        ("Step 5: 生成信号", "_generate_risk_signals(metrics)"),
        ("Step 6: 输出结果", "{overall_risk_level, risk_score}"),
    ]

    for i, (title, desc) in enumerate(flow_steps):
        y = 1.7 + i * 0.8
        add_text_box(slide, Inches(7.3), Inches(y), Inches(5), Inches(0.3),
                     title, font_size=14, color=ACCENT_BLUE, bold=True)
        add_text_box(slide, Inches(7.3), Inches(y + 0.28), Inches(5), Inches(0.4),
                     desc, font_size=11, color=LIGHT_GRAY)

    # LLM fallback note
    add_shape_bg(slide, Inches(0.8), Inches(7.0), Inches(11.5), Inches(0.4), RGBColor(0x1e, 0x2a, 0x3a))
    add_text_box(slide, Inches(1.0), Inches(7.0), Inches(11), Inches(0.35),
                 "LLM 兜底: 若 LLM 调用失败，自动降级到本地 _run_risk_pipeline_impl() 直接计算",
                 font_size=13, color=ACCENT_GREEN)

def create_portfolio_agent_slide(prs):
    """Slide 7: Portfolio Agent Working Principle"""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_bg(slide)
    add_shape_bg(slide, Inches(0), Inches(0), Inches(13.33), Inches(0.08), ACCENT_GREEN)
    add_text_box(slide, Inches(0.8), Inches(0.3), Inches(11), Inches(0.6),
                 "Portfolio Agent | 组合优化引擎", font_size=36, color=ACCENT_GREEN, bold=True)

    # Left: Core algorithm
    add_text_box(slide, Inches(0.8), Inches(1.1), Inches(5.5), Inches(0.4),
                 "核心算法: 信号 x 风险 -> 权重", font_size=20, color=ACCENT_GREEN, bold=True)

    algo_steps = [
        ("1. 解析 Alpha 信号", "接收 {symbol: score} 字典\n正分数 = 看多，负分数 = 看空", ACCENT_BLUE),
        ("2. 风险资本分配", "HIGH -> 50% capital\nMODERATE -> 80% capital\nLOW -> 100% capital", ACCENT_ORANGE),
        ("3. 筛选正信号", "score > 0 的股票进入候选池\nscore <= 0 标记为 exit_candidates", ACCENT_RED),
        ("4. 排名选取 Top-K", "按 score 降序排列\n取前 max_positions 只 (默认20)", ACCENT_PURPLE),
        ("5. 等权分配", "weight = risk_allocation / N\n每只股票等权重分配", ACCENT_GREEN),
    ]

    for i, (title, desc, color) in enumerate(algo_steps):
        y = 1.6 + i * 1.05
        add_shape_bg(slide, Inches(0.8), Inches(y), Inches(5.5), Inches(0.85), DARK_GRAY)
        add_text_box(slide, Inches(1.0), Inches(y + 0.02), Inches(5), Inches(0.3),
                     title, font_size=14, color=color, bold=True)
        add_text_box(slide, Inches(1.0), Inches(y + 0.3), Inches(5), Inches(0.5),
                     desc, font_size=11, color=LIGHT_GRAY)

    # Right: Order generation
    add_text_box(slide, Inches(7), Inches(1.1), Inches(5.5), Inches(0.4),
                 "订单生成 (generate_orders)", font_size=20, color=ACCENT_ORANGE, bold=True)

    add_shape_bg(slide, Inches(7), Inches(1.6), Inches(5.5), Inches(2.5), DARK_GRAY)
    add_text_box(slide, Inches(7.2), Inches(1.65), Inches(5), Inches(0.3),
                 "从目标权重到实际订单", font_size=15, color=ACCENT_BLUE, bold=True)

    order_code = [
        "for symbol in all_symbols:",
        "    target_value = weight * total_capital",
        "    current_value = position_market_value",
        "    diff = target_value - current_value",
        "",
        "    if abs(diff) < min_trade_value:",
        "        continue  # 跳过小额调整",
        "",
        "    qty = int(abs(diff) / price)",
        "    if diff > 0:  BUY",
        "    if diff < 0:  SELL",
    ]
    add_code_block(slide, Inches(7.2), Inches(2.0), Inches(5), Inches(2.0), order_code, font_size=11)

    # Right bottom: Execution order
    add_shape_bg(slide, Inches(7), Inches(4.3), Inches(5.5), Inches(2.5), DARK_GRAY)
    add_text_box(slide, Inches(7.2), Inches(4.35), Inches(5), Inches(0.3),
                 "执行顺序: 先卖后买", font_size=15, color=ACCENT_RED, bold=True)

    add_text_box(slide, Inches(7.2), Inches(4.7), Inches(5), Inches(2.0),
                 "1. 先执行 SELL 订单 (释放现金)\n\n"
                 "2. 再执行 BUY 订单 (使用释放的现金)\n\n"
                 "3. 每笔订单经过 validate_order() 风控:\n"
                 "   - 最小订单 $50\n"
                 "   - 最大订单 $200,000\n"
                 "   - 单票不超过组合 5%",
                 font_size=12, color=LIGHT_GRAY)

def create_backtest_agent_slide(prs):
    """Slide 8: Backtest Agent Working Principle"""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_bg(slide)
    add_shape_bg(slide, Inches(0), Inches(0), Inches(13.33), Inches(0.08), ACCENT_PURPLE)
    add_text_box(slide, Inches(0.8), Inches(0.3), Inches(11), Inches(0.6),
                 "Backtest Agent | 回测评估引擎", font_size=36, color=ACCENT_PURPLE, bold=True)

    # Left: Value-based accounting
    add_text_box(slide, Inches(0.8), Inches(1.1), Inches(5.5), Inches(0.4),
                 "核心: 基于价值的会计模拟", font_size=20, color=ACCENT_PURPLE, bold=True)

    add_shape_bg(slide, Inches(0.8), Inches(1.6), Inches(5.5), Inches(5.0), DARK_GRAY)

    sim_steps = [
        ("1. 初始化", "cash = total_capital\nholdings = {sym: 0}  (每只股票0股)"),
        ("2. 每日循环", "计算持仓市值 stock_value\n总权益 equity = cash + stock_value"),
        ("3. 判断是否调仓", "if 天数 % investment_horizon == 0:\n    触发调仓逻辑"),
        ("4. 获取信号分数", "从 predictions 中读取当日各股票 score"),
        ("5. 构建目标组合", "Top-K 等权，max_position_size 约束"),
        ("6. 先卖后买", "先卖出偏离目标的持仓\n再买入目标持仓"),
        ("7. 记录历史", "每日记录 equity, cash, cost, holdings"),
        ("8. 计算绩效", "总收益、Sharpe、最大回撤、波动率"),
    ]

    for i, (title, desc) in enumerate(sim_steps):
        y = 1.65 + i * 0.62
        add_text_box(slide, Inches(1.0), Inches(y), Inches(2), Inches(0.25),
                     title, font_size=12, color=ACCENT_BLUE, bold=True)
        add_text_box(slide, Inches(1.0), Inches(y + 0.22), Inches(5), Inches(0.35),
                     desc, font_size=10, color=LIGHT_GRAY)

    # Right: Two modes
    add_text_box(slide, Inches(7), Inches(1.1), Inches(5.5), Inches(0.4),
                 "两种回测模式", font_size=20, color=ACCENT_ORANGE, bold=True)

    # Mode 1: Standard
    add_shape_bg(slide, Inches(7), Inches(1.6), Inches(5.5), Inches(2.2), DARK_GRAY)
    add_text_box(slide, Inches(7.2), Inches(1.65), Inches(5), Inches(0.3),
                 "Standard 回测 (run_pipeline)", font_size=16, color=ACCENT_BLUE, bold=True)
    add_text_box(slide, Inches(7.2), Inches(2.0), Inches(5), Inches(1.7),
                 "- 固定训练/测试区间\n"
                 "- 一次性生成所有信号\n"
                 "- 适合快速验证策略\n\n"
                 "命令: --mode backtest --start X --end Y",
                 font_size=13, color=LIGHT_GRAY)

    # Mode 2: Rolling
    add_shape_bg(slide, Inches(7), Inches(4.0), Inches(5.5), Inches(2.6), DARK_GRAY)
    add_text_box(slide, Inches(7.2), Inches(4.05), Inches(5), Inches(0.3),
                 "Rolling Weekly 回测 (--rolling)", font_size=16, color=ACCENT_GREEN, bold=True)
    add_text_box(slide, Inches(7.2), Inches(4.4), Inches(5), Inches(2.1),
                 "- 每周滚动重训模型\n"
                 "- 严格 Walk-Forward 验证\n"
                 "- 避免前视偏差 (Look-Ahead Bias)\n\n"
                 "流程:\n"
                 "  Week1: train[lookback] -> predict[week1]\n"
                 "  Week2: train[lookback+1] -> predict[week2]\n"
                 "  ...  拼接所有周信号 -> 统一回测",
                 font_size=13, color=LIGHT_GRAY)

    # Performance metrics
    add_shape_bg(slide, Inches(0.8), Inches(6.8), Inches(11.5), Inches(0.5), RGBColor(0x1e, 0x2a, 0x3a))
    add_text_box(slide, Inches(1.0), Inches(6.85), Inches(11), Inches(0.4),
                 "输出指标: Total Return | Sharpe Ratio | Max Drawdown | Volatility | Calmar Ratio",
                 font_size=14, color=ACCENT_GREEN, alignment=PP_ALIGN.CENTER)

def create_execution_agent_slide(prs):
    """Slide 9: Execution Agent Working Principle"""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_bg(slide)
    add_shape_bg(slide, Inches(0), Inches(0), Inches(13.33), Inches(0.08), ACCENT_RED)
    add_text_box(slide, Inches(0.8), Inches(0.3), Inches(11), Inches(0.6),
                 "Execution Agent | 交易执行系统", font_size=36, color=ACCENT_RED, bold=True)

    # Left: Alpaca integration
    add_text_box(slide, Inches(0.8), Inches(1.1), Inches(5.5), Inches(0.4),
                 "Alpaca API 集成", font_size=20, color=ACCENT_RED, bold=True)

    add_shape_bg(slide, Inches(0.8), Inches(1.6), Inches(5.5), Inches(2.0), DARK_GRAY)
    add_text_box(slide, Inches(1.0), Inches(1.65), Inches(5), Inches(0.3),
                 "AlpacaService 类", font_size=15, color=ACCENT_BLUE, bold=True)
    add_text_box(slide, Inches(1.0), Inches(2.0), Inches(5), Inches(1.5),
                 "- get_account()      获取账户信息\n"
                 "- get_positions()    获取当前持仓\n"
                 "- place_order()      下单 (market/limit/stop)\n"
                 "- cancel_all_orders() 撤销所有订单\n"
                 "- get_order_history() 订单历史\n\n"
                 "自动检测 API Key，无效时切换 Mock 模式",
                 font_size=12, color=LIGHT_GRAY)

    # Risk controls
    add_text_box(slide, Inches(0.8), Inches(3.8), Inches(5.5), Inches(0.4),
                 "风控约束 (validate_order)", font_size=20, color=ACCENT_ORANGE, bold=True)

    add_shape_bg(slide, Inches(0.8), Inches(4.3), Inches(5.5), Inches(2.5), DARK_GRAY)

    risk_rules = [
        ("MIN_ORDER_VALUE", "$50", "低于此金额跳过"),
        ("MAX_ORDER_VALUE", "$200,000", "单笔上限"),
        ("MAX_POSITION_PCT", "5%", "单票占组合比例"),
        ("市场状态检查", "is_market_open()", "非开盘时间不下单"),
        ("买入力校验", "buying_power", "现金不足拒绝买入"),
    ]

    for i, (rule, value, desc) in enumerate(risk_rules):
        y = 4.35 + i * 0.48
        add_text_box(slide, Inches(1.0), Inches(y), Inches(2.2), Inches(0.35),
                     rule, font_size=12, color=ACCENT_RED, bold=True)
        add_text_box(slide, Inches(3.2), Inches(y), Inches(1.2), Inches(0.35),
                     value, font_size=12, color=ACCENT_GREEN, bold=True)
        add_text_box(slide, Inches(4.4), Inches(y), Inches(1.8), Inches(0.35),
                     desc, font_size=11, color=LIGHT_GRAY)

    # Right: Execution flow
    add_text_box(slide, Inches(7), Inches(1.1), Inches(5.5), Inches(0.4),
                 "执行流程", font_size=20, color=ACCENT_GREEN, bold=True)

    exec_steps = [
        ("1. 检查市场状态", "is_market_open()\n非交易时段直接跳过"),
        ("2. 获取账户信息", "buying_power, portfolio_value\n用于风控校验"),
        ("3. 排序订单", "SELL 订单排在前面\n先卖出释放现金"),
        ("4. 逐笔风控校验", "validate_order()\n不通过则 rejected"),
        ("5. 下单执行", "alpaca_service.place_order()\nmarket / limit / stop_loss"),
        ("6. 更新买入力", "每笔 buy 成功后\n扣减 buying_power"),
        ("7. 记录 Trade Journal", "完整记录每笔交易\n保存到 trade_journals/"),
    ]

    for i, (title, desc) in enumerate(exec_steps):
        y = 1.6 + i * 0.78
        add_shape_bg(slide, Inches(7), Inches(y), Inches(5.5), Inches(0.65), DARK_GRAY)
        add_text_box(slide, Inches(7.2), Inches(y + 0.02), Inches(2.3), Inches(0.25),
                     title, font_size=13, color=ACCENT_BLUE, bold=True)
        add_text_box(slide, Inches(9.5), Inches(y + 0.02), Inches(2.8), Inches(0.55),
                     desc, font_size=11, color=LIGHT_GRAY)

    # Market hours note
    add_shape_bg(slide, Inches(7), Inches(7.0), Inches(5.5), Inches(0.4), RGBColor(0x1e, 0x2a, 0x3a))
    add_text_box(slide, Inches(7.2), Inches(7.05), Inches(5), Inches(0.3),
                 "美东时间 9:30-16:00 (周一至周五)",
                 font_size=13, color=ACCENT_ORANGE, alignment=PP_ALIGN.CENTER)

def create_agent_tools_slide(prs):
    """Slide 10: Agent Tools & Function Calling"""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_bg(slide)
    add_shape_bg(slide, Inches(0), Inches(0), Inches(13.33), Inches(0.08), ACCENT_BLUE)
    add_text_box(slide, Inches(0.8), Inches(0.3), Inches(11), Inches(0.6),
                 "Agent Tools & Function Calling", font_size=36, color=ACCENT_BLUE, bold=True)
    add_text_box(slide, Inches(0.8), Inches(0.85), Inches(11), Inches(0.4),
                 "每个 Agent 通过 @function_tool 注册工具，LLM 自动选择调用",
                 font_size=15, color=LIGHT_GRAY)

    # Table header
    header_y = 1.4
    add_shape_bg(slide, Inches(0.4), Inches(header_y), Inches(12.5), Inches(0.45), ACCENT_BLUE)
    cols_x = [0.5, 2.6, 7.2]
    cols_w = [2.0, 4.5, 5.2]
    headers = ["Agent", "Tools (函数工具)", "功能说明"]
    for x, w, txt in zip(cols_x, cols_w, headers):
        add_text_box(slide, Inches(x), Inches(header_y + 0.05), Inches(w), Inches(0.35),
                     txt, font_size=13, color=DARK_BG, bold=True, alignment=PP_ALIGN.CENTER)

    # Table rows
    rows = [
        ("Orchestrator\n编排调度", "fetch_market_data\nstore_reflection · query_lessons\nsearch_knowledge\n+ 5 个 Agent as Tool", "数据获取、记忆存/查、知识检索\n调度全部子 Agent 完成流水线"),
        ("Alpha Signal\n信号生成", "run_alpha_pipeline (Fast Path)\ncalculate_indicators_tool\ntrain_predict_tool\nsubmit_signals_tool", "技术指标 RSI/MACD/Bollinger\nML 模型训练与预测\n信号阈值过滤输出"),
        ("Risk Signal\n风险控制", "run_risk_pipeline (Fast Path)\ncalculate_volatility_tool\nsubmit_risk_assessment_tool", "20日滚动波动率 · VaR 95%\n风险等级 HIGH/LOW 划分"),
        ("Portfolio\n组合优化", "run_portfolio_pipeline (Fast Path)\nconstruct_portfolio_tool\nsubmit_portfolio_tool", "信号→权重等权分配\n风险资本比例调整\n先卖后买订单生成"),
        ("Backtest\n回测评估", "initialize_qlib_data · run_qlib_backtest\nrun_comprehensive_backtest\ntrain_qlib_model · analyze_factor_ic\noptimize_portfolio_weights\nrun_walk_forward_analysis ... (共 18 个)", "Qlib 框架回测 · 因子 IC 分析\nML 模型训练 · 组合优化\n前向分析 · 风险归因 · 交易成本"),
        ("Execution\n订单执行", "get_account_summary\nget_current_positions\nexecute_orders\ncancel_all_pending_orders\nget_order_history", "Alpaca API 账户/持仓查询\n订单执行与撤销\n风控校验 (单笔/仓位/买力)"),
    ]

    for i, (agent, tools, desc) in enumerate(rows):
        y = 1.95 + i * 0.88
        bg_color = DARK_GRAY if i % 2 == 0 else RGBColor(0x22, 0x22, 0x3a)
        add_shape_bg(slide, Inches(0.4), Inches(y), Inches(12.5), Inches(0.82), bg_color)
        add_text_box(slide, Inches(0.5), Inches(y + 0.05), Inches(2.0), Inches(0.7),
                     agent, font_size=11, color=ACCENT_GREEN, bold=True, alignment=PP_ALIGN.CENTER)
        add_text_box(slide, Inches(2.6), Inches(y + 0.05), Inches(4.5), Inches(0.7),
                     tools, font_size=9, color=ACCENT_BLUE)
        add_text_box(slide, Inches(7.2), Inches(y + 0.05), Inches(5.5), Inches(0.7),
                     desc, font_size=9, color=LIGHT_GRAY)

    # Bottom note
    add_shape_bg(slide, Inches(0.4), Inches(7.0), Inches(12.5), Inches(0.35), RGBColor(0x1e, 0x2a, 0x3a))
    add_text_box(slide, Inches(0.6), Inches(7.0), Inches(12), Inches(0.3),
                 "Fast Path = 一键全流程 (推荐)  |  Custom Path = 分步调用单个工具 (精细控制)  |  Agent.as_tool() = 子Agent注册为父Agent的工具",
                 font_size=11, color=ACCENT_GREEN, alignment=PP_ALIGN.CENTER)


def create_mcp_slide(prs):
    """Slide 11: MCP Protocol Integration"""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_bg(slide)
    add_shape_bg(slide, Inches(0), Inches(0), Inches(13.33), Inches(0.08), ACCENT_GREEN)
    add_text_box(slide, Inches(0.8), Inches(0.3), Inches(11), Inches(0.6),
                 "MCP Protocol Integration", font_size=36, color=ACCENT_GREEN, bold=True)
    add_text_box(slide, Inches(0.8), Inches(0.85), Inches(11), Inches(0.4),
                 "Model Context Protocol — 标准化 Agent ↔ 外部服务通信",
                 font_size=15, color=LIGHT_GRAY)

    # Left: MCP Server 架构
    add_shape_bg(slide, Inches(0.4), Inches(1.4), Inches(6.0), Inches(5.3), DARK_GRAY)
    add_text_box(slide, Inches(0.7), Inches(1.5), Inches(5.5), Inches(0.4),
                 "FinAgent MCP Server (FastMCP v2.0)", font_size=16, color=ACCENT_GREEN, bold=True)

    arch_lines = [
        "┌───────────────────────────────────────────────┐",
        "│            MCP Server (FastMCP)               │",
        "│                                               │",
        "│  ┌────────────┐ ┌────────────┐ ┌───────────┐  │",
        "│  │ Memory     │ │ Alpha      │ │ Agent     │  │",
        "│  │ Tools      │ │ Strategy   │ │ Management│  │",
        "│  │ • store    │ │ • signals  │ │ • start   │  │",
        "│  │ • retrieve │ │ • backtest │ │ • list    │  │",
        "│  │ • delete   │ │ • factors  │ │ • status  │  │",
        "│  └────────────┘ └────────────┘ └───────────┘  │",
        "│                                               │",
        "│  ┌─────────────────────────────────────────┐   │",
        "│  │    Unified Interface Manager            │   │",
        "│  │    MCP · HTTP · A2A 三协议统一          │   │",
        "│  └─────────────────────────────────────────┘   │",
        "│  ┌─────────────────────────────────────────┐   │",
        "│  │    Unified Database Manager             │   │",
        "│  │    Neo4j Graph + ChromaDB Vector        │   │",
        "│  └─────────────────────────────────────────┘   │",
        "└───────────────────────────────────────────────┘",
    ]
    add_code_block(slide, Inches(0.7), Inches(2.0), Inches(5.5), Inches(4.5), arch_lines, font_size=9)

    # Right: MCP Tools 列表
    add_shape_bg(slide, Inches(6.6), Inches(1.4), Inches(6.3), Inches(5.3), DARK_GRAY)
    add_text_box(slide, Inches(6.9), Inches(1.5), Inches(5.8), Inches(0.4),
                 "MCP Exposed Tools", font_size=16, color=ACCENT_GREEN, bold=True)

    mcp_tools_lines = [
        "🧠 Memory Layer (Neo4j + ChromaDB)",
        "   store_graph_memory         — 结构化记忆存储",
        "   retrieve_graph_memory      — 语义检索记忆",
        "   store_graph_memories_batch — 批量存储",
        "   search_memories_semantic   — 向量语义搜索",
        "   get_memory_statistics      — 记忆统计",
        "",
        "📊 Alpha Strategy Layer",
        "   generate_alpha_signals     — 生成 Alpha 信号",
        "   discover_alpha_factors     — 因子发现",
        "   develop_strategy_config    — 策略配置生成",
        "   run_comprehensive_backtest — 综合回测",
        "   submit_strategy_to_memory  — 策略存入记忆",
        "   validate_strategy_perf     — 策略验证",
        "",
        "🤖 Agent Management",
        "   start_agent / list_agents / get_agent_status",
        "",
        "📡 协议支持: MCP · HTTP · A2A (SSE 实时推送)",
    ]
    add_code_block(slide, Inches(6.9), Inches(2.0), Inches(5.8), Inches(4.5), mcp_tools_lines, font_size=9)

    # Bottom 3 highlight boxes
    highlights = [
        ("🔗 SSE 实时通信", "MCP Server 支持 SSE 端点\n实时推送 Agent 状态与结果", ACCENT_BLUE),
        ("🔄 三协议统一", "MCP / HTTP / A2A\n同一套 Tool 定义，统一管理", ACCENT_GREEN),
        ("📦 工具自注册", "ToolDefinition 自动注册\nOpenAI / MCP 双格式输出", ACCENT_PURPLE),
    ]
    for i, (title, desc, color) in enumerate(highlights):
        x = 0.4 + i * 4.2
        add_shape_bg(slide, Inches(x), Inches(6.85), Inches(3.9), Inches(0.55), DARK_GRAY)
        add_text_box(slide, Inches(x + 0.15), Inches(6.85), Inches(1.8), Inches(0.25),
                     title, font_size=11, color=color, bold=True)
        add_text_box(slide, Inches(x + 0.15), Inches(7.1), Inches(3.6), Inches(0.25),
                     desc.split('\n')[0], font_size=9, color=LIGHT_GRAY)


def create_data_flow_slide(prs):
    """Slide 12: Data Flow"""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_bg(slide)
    add_shape_bg(slide, Inches(0), Inches(0), Inches(13.33), Inches(0.08), ACCENT_PURPLE)
    add_text_box(slide, Inches(0.8), Inches(0.4), Inches(11), Inches(0.7),
                 "数据流时序", font_size=36, color=ACCENT_PURPLE, bold=True)

    steps = [
        ("1", "Market Universe", "拉取全市场股票 (Alpaca API)", ACCENT_GREEN),
        ("2", "Orchestrator", "快照预筛 -> RAG查询 -> 记忆查询", ACCENT_ORANGE),
        ("3", "Alpha Agent", "Qlib ML 预测 -> 因子信号输出", ACCENT_BLUE),
        ("4", "Risk Agent", "波动率/VaR/回撤 -> 风险等级", ACCENT_RED),
        ("5", "Portfolio Agent", "信号+风险 -> 权重分配 -> 订单", ACCENT_GREEN),
        ("6", "Backtest / Execution", "回测报告 / 实盘下单", ACCENT_PURPLE),
        ("7", "Memory System", "存储策略表现、教训 -> Neo4j", ACCENT_ORANGE),
    ]

    for i, (num, title, desc, color) in enumerate(steps):
        y = 1.3 + i * 0.82
        add_shape_bg(slide, Inches(1.5), Inches(y), Inches(0.5), Inches(0.5), color)
        add_text_box(slide, Inches(1.5), Inches(y + 0.05), Inches(0.5), Inches(0.4),
                     num, font_size=18, color=DARK_BG, bold=True, alignment=PP_ALIGN.CENTER)
        if i < len(steps) - 1:
            add_text_box(slide, Inches(1.6), Inches(y + 0.5), Inches(0.3), Inches(0.3),
                         "|", font_size=14, color=MEDIUM_GRAY, alignment=PP_ALIGN.CENTER)
        add_text_box(slide, Inches(2.3), Inches(y + 0.02), Inches(3), Inches(0.4),
                     title, font_size=18, color=color, bold=True)
        add_text_box(slide, Inches(5.5), Inches(y + 0.05), Inches(6), Inches(0.4),
                     desc, font_size=15, color=LIGHT_GRAY)

def create_memory_slide(prs):
    """Slide 13: Memory System"""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_bg(slide)
    add_shape_bg(slide, Inches(0), Inches(0), Inches(13.33), Inches(0.08), ACCENT_PURPLE)
    add_text_box(slide, Inches(0.8), Inches(0.4), Inches(11), Inches(0.7),
                 "记忆与知识系统", font_size=36, color=ACCENT_PURPLE, bold=True)

    # Neo4j
    add_shape_bg(slide, Inches(0.8), Inches(1.3), Inches(5.5), Inches(5.2), DARK_GRAY)
    add_text_box(slide, Inches(1.1), Inches(1.35), Inches(5), Inches(0.5),
                 "Neo4j 图记忆", font_size=24, color=ACCENT_PURPLE, bold=True)

    neo4j_items = [
        "节点类型: Agent, Strategy, Issue, Lesson",
        "关系: PROPOSED, ENCOUNTERED, LEARNED",
        "存储策略反思与失败教训",
        "下次遇到相似问题自动检索",
        "同步客户端，无需启动服务",
    ]
    for i, item in enumerate(neo4j_items):
        add_text_box(slide, Inches(1.3), Inches(2.0 + i * 0.5), Inches(4.5), Inches(0.4),
                     f">> {item}", font_size=13, color=LIGHT_GRAY)

    add_shape_bg(slide, Inches(1.1), Inches(4.6), Inches(4.8), Inches(1.6), MEDIUM_GRAY)
    add_text_box(slide, Inches(1.3), Inches(4.65), Inches(4.4), Inches(0.3),
                 "使用示例:", font_size=13, color=ACCENT_GREEN, bold=True)
    add_text_box(slide, Inches(1.3), Inches(4.95), Inches(4.4), Inches(1.2),
                 'client.store_reflection(\n'
                 '  agent="Alpha",\n'
                 '  strategy="momentum_v1",\n'
                 '  issue="overfitting",\n'
                 '  lesson="Use walk-forward")',
                 font_size=11, color=ACCENT_GREEN)

    # ChromaDB
    add_shape_bg(slide, Inches(7), Inches(1.3), Inches(5.5), Inches(5.2), DARK_GRAY)
    add_text_box(slide, Inches(7.3), Inches(1.35), Inches(5), Inches(0.5),
                 "ChromaDB RAG", font_size=24, color=ACCENT_ORANGE, bold=True)

    rag_items = [
        "Alpha101 论文 PDF 自动索引",
        "60+ 文本片段向量化存储",
        "语义搜索因子构建方法",
        "首次使用自动构建向量索引",
        "开箱即用，零配置",
    ]
    for i, item in enumerate(rag_items):
        add_text_box(slide, Inches(7.5), Inches(2.0 + i * 0.5), Inches(4.5), Inches(0.4),
                     f">> {item}", font_size=13, color=LIGHT_GRAY)

    add_shape_bg(slide, Inches(7.3), Inches(4.6), Inches(4.8), Inches(1.6), MEDIUM_GRAY)
    add_text_box(slide, Inches(7.5), Inches(4.65), Inches(4.4), Inches(0.3),
                 "使用示例:", font_size=13, color=ACCENT_GREEN, bold=True)
    add_text_box(slide, Inches(7.5), Inches(4.95), Inches(4.4), Inches(1.2),
                 'rag = get_rag_client()\n'
                 'results = rag.query(\n'
                 '  "momentum factor",\n'
                 '  n_results=3)',
                 font_size=11, color=ACCENT_GREEN)

def create_tech_stack_slide(prs):
    """Slide 14: Technical Stack"""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_bg(slide)
    add_shape_bg(slide, Inches(0), Inches(0), Inches(13.33), Inches(0.08), ACCENT_GREEN)
    add_text_box(slide, Inches(0.8), Inches(0.4), Inches(11), Inches(0.7),
                 "技术栈", font_size=36, color=ACCENT_GREEN, bold=True)

    categories = [
        ("Agent 框架", "OpenAI SDK / LangChain / LangGraph", ACCENT_BLUE),
        ("大语言模型", "GPT-4o / Claude (Poe 代理)", ACCENT_PURPLE),
        ("量化框架", "Qlib (Microsoft) - 158 因子 + ML + 回测", ACCENT_ORANGE),
        ("市场数据", "Alpaca Markets API - 美股全市场", ACCENT_GREEN),
        ("交易执行", "Alpaca Trading API - 纸交易/实盘", ACCENT_RED),
        ("图数据库", "Neo4j - 策略记忆图谱", ACCENT_PURPLE),
        ("向量数据库", "ChromaDB - RAG 语义检索", ACCENT_ORANGE),
        ("通信协议", "MCP / A2A - Agent 间标准化通信", ACCENT_BLUE),
    ]

    for i, (name, desc, color) in enumerate(categories):
        row = i // 2
        col = i % 2
        x = 0.8 + col * 6.2
        y = 1.3 + row * 1.35
        add_shape_bg(slide, Inches(x), Inches(y), Inches(5.8), Inches(1.1), DARK_GRAY)
        add_text_box(slide, Inches(x + 0.3), Inches(y + 0.1), Inches(5), Inches(0.4),
                     name, font_size=18, color=color, bold=True)
        add_text_box(slide, Inches(x + 0.3), Inches(y + 0.55), Inches(5), Inches(0.4),
                     desc, font_size=14, color=LIGHT_GRAY)

def create_usage_slide(prs):
    """Slide 15: Usage Demo"""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_bg(slide)
    add_shape_bg(slide, Inches(0), Inches(0), Inches(13.33), Inches(0.08), ACCENT_ORANGE)
    add_text_box(slide, Inches(0.8), Inches(0.3), Inches(11), Inches(0.6),
                 "快速上手", font_size=36, color=ACCENT_ORANGE, bold=True)

    commands = [
        ("回测 S&P 500", "python run_paper_trading.py --mode backtest --universe sp500 --start 2024-01-01 --end 2024-03-01"),
        ("单次实时交易", "python run_paper_trading.py --mode once --universe nasdaq100"),
        ("连续自动交易", "python run_paper_trading.py --mode continuous --universe liquid --interval 300"),
        ("滚动周回测", "python run_paper_trading.py --mode backtest --symbol AAPL,MSFT --rolling"),
        ("禁用 RAG/Memory", "python run_paper_trading.py --mode backtest --universe sp500 --no-rag --no-memory"),
    ]

    for i, (label, cmd) in enumerate(commands):
        y = 1.1 + i * 1.15
        add_shape_bg(slide, Inches(0.8), Inches(y), Inches(11.5), Inches(0.95), DARK_GRAY)
        add_text_box(slide, Inches(1.1), Inches(y + 0.05), Inches(2.5), Inches(0.35),
                     label, font_size=16, color=ACCENT_GREEN, bold=True)
        add_shape_bg(slide, Inches(1.1), Inches(y + 0.45), Inches(10.8), Inches(0.4), MEDIUM_GRAY)
        add_text_box(slide, Inches(1.3), Inches(y + 0.45), Inches(10.4), Inches(0.4),
                     cmd, font_size=12, color=ACCENT_BLUE)

    add_text_box(slide, Inches(0.8), Inches(6.8), Inches(11), Inches(0.4),
                 "--universe:  nasdaq100 (~100)  |  sp500 (~500)  |  liquid (~2000)  |  all (全部)",
                 font_size=14, color=LIGHT_GRAY)

def create_highlights_slide(prs):
    """Slide 16: Project Highlights"""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_bg(slide)
    add_shape_bg(slide, Inches(0), Inches(0), Inches(13.33), Inches(0.08), ACCENT_BLUE)
    add_text_box(slide, Inches(0.8), Inches(0.3), Inches(11), Inches(0.6),
                 "项目亮点", font_size=36, color=ACCENT_BLUE, bold=True)

    add_text_box(slide, Inches(0.8), Inches(1.1), Inches(5), Inches(0.4),
                 "技术创新", font_size=22, color=ACCENT_GREEN, bold=True)
    tech_items = [
        "LLM + 量化深度融合，非简单包装",
        "Agent-as-Tool 模式，灵活编排",
        "MCP 协议标准化 Agent 间通信",
        "图记忆系统，策略经验沉淀复用",
        "RAG 增强，理论指导实践",
        "全市场覆盖，不限于少数股票",
    ]
    for i, item in enumerate(tech_items):
        add_text_box(slide, Inches(1.2), Inches(1.6 + i * 0.55), Inches(5), Inches(0.4),
                     f"* {item}", font_size=15, color=LIGHT_GRAY)

    add_text_box(slide, Inches(7), Inches(1.1), Inches(5), Inches(0.4),
                 "工程亮点", font_size=22, color=ACCENT_ORANGE, bold=True)
    eng_items = [
        "统一入口，一个命令覆盖所有模式",
        "优雅降级，依赖不可用时自动 Mock",
        "模块解耦，每个 Agent 独立可测试",
        "40+ Function Tools 自动注册调用",
        "RAG 自动构建，首次使用零配置",
        "完整 Trade Journal 交易日志",
    ]
    for i, item in enumerate(eng_items):
        add_text_box(slide, Inches(7.4), Inches(1.6 + i * 0.55), Inches(5), Inches(0.4),
                     f"* {item}", font_size=15, color=LIGHT_GRAY)

def create_roadmap_slide(prs):
    """Slide 17: Roadmap"""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_bg(slide)
    add_shape_bg(slide, Inches(0), Inches(0), Inches(13.33), Inches(0.08), ACCENT_GREEN)
    add_text_box(slide, Inches(0.8), Inches(0.4), Inches(11), Inches(0.7),
                 "开发路线图", font_size=36, color=ACCENT_GREEN, bold=True)

    phases = [
        ("Phase 1 [DONE]", [
            "多 Agent 协作框架",
            "Orchestrator + Agent-as-Tool",
            "Neo4j 图记忆 + ChromaDB RAG",
            "全市场股票池 + 快照预筛选",
            "三种交易模式",
        ], ACCENT_GREEN),
        ("Phase 2 [WIP]", [
            "全市场 Alpha 截面排名模型",
            "行业中性化与风险因子控制",
            "多周期回测 (日/周/月频)",
        ], ACCENT_ORANGE),
        ("Phase 3 [PLAN]", [
            "TWAP / VWAP 算法执行",
            "记忆系统深度整合",
            "A 股市场接入 (Tushare)",
            "Web Dashboard 实时监控",
        ], ACCENT_PURPLE),
    ]

    for i, (title, items, color) in enumerate(phases):
        x = 0.8 + i * 4.1
        add_shape_bg(slide, Inches(x), Inches(1.3), Inches(3.8), Inches(5.0), DARK_GRAY)
        add_text_box(slide, Inches(x + 0.2), Inches(1.4), Inches(3.4), Inches(0.5),
                     title, font_size=20, color=color, bold=True)
        add_shape_bg(slide, Inches(x + 0.2), Inches(1.95), Inches(3.4), Inches(0.03), color)
        for j, item in enumerate(items):
            add_text_box(slide, Inches(x + 0.4), Inches(2.2 + j * 0.55), Inches(3.2), Inches(0.4),
                         f">> {item}", font_size=14, color=LIGHT_GRAY)

def create_closing_slide(prs):
    """Slide 18: Closing"""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_bg(slide)
    add_shape_bg(slide, Inches(0), Inches(0), Inches(13.33), Inches(0.08), ACCENT_BLUE)

    add_text_box(slide, Inches(1), Inches(2.0), Inches(11), Inches(1.0),
                 "Thank You", font_size=54, color=ACCENT_BLUE, bold=True, alignment=PP_ALIGN.CENTER)
    add_text_box(slide, Inches(1), Inches(3.2), Inches(11), Inches(0.6),
                 "Lianghua - Multi-Agent Quantitative Investment Research",
                 font_size=22, color=WHITE, alignment=PP_ALIGN.CENTER)
    add_text_box(slide, Inches(1), Inches(4.2), Inches(11), Inches(0.5),
                 "LLM-Driven  |  Memory-Augmented  |  RAG-Enhanced  |  Fully Automated",
                 font_size=16, color=ACCENT_GREEN, alignment=PP_ALIGN.CENTER)
    add_shape_bg(slide, Inches(0), Inches(7.42), Inches(13.33), Inches(0.08), ACCENT_GREEN)


def main():
    prs = Presentation()
    prs.slide_width = Inches(13.33)
    prs.slide_height = Inches(7.5)

    create_title_slide(prs)           # 1
    create_problem_slide(prs)         # 2
    create_solution_slide(prs)        # 3
    create_architecture_slide(prs)    # 4
    create_alpha_agent_slide(prs)     # 5
    create_risk_agent_slide(prs)      # 6
    create_portfolio_agent_slide(prs) # 7
    create_backtest_agent_slide(prs)  # 8
    create_execution_agent_slide(prs) # 9
    create_agent_tools_slide(prs)     # 10  Agent Tools & Function Calling
    create_mcp_slide(prs)             # 11  MCP Protocol Integration
    create_data_flow_slide(prs)       # 12
    create_memory_slide(prs)          # 13
    create_tech_stack_slide(prs)      # 14
    create_usage_slide(prs)           # 15
    create_highlights_slide(prs)      # 16
    create_roadmap_slide(prs)         # 17
    create_closing_slide(prs)         # 18

    output_path = os.path.join(os.path.dirname(__file__), "Lianghua_Introduction.pptx")
    prs.save(output_path)
    print(f"PPT saved to: {output_path}")
    print(f"Total slides: {len(prs.slides)}")


if __name__ == "__main__":
    main()
