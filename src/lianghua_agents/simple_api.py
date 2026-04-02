"""
极简 API - 只需要提供提示词，其他自动处理
"""
from datetime import datetime, timedelta

from .multi_agent_system import WorkflowRequest, WorkflowMode, get_multi_agent_system


def analyze(
    prompt: str,
    ts_code: str = "000001.SZ",
    horizon: str = "1-3个月",
    risk_level: str = "中等",
    days_back: int = 30,
) -> dict:
    """
    极简分析 API - 只需要提示词
    
    使用方法极其简单：
    
    >>> from lianghua_agents.simple_api import analyze
    >>> result = analyze("这支股票值得投资吗？")
    >>> print(result['output'])
    
    Args:
        prompt: 分析提示词（必填）- 你想问什么问题
        ts_code: 股票代码（默认 000001.SZ）
        horizon: 投资周期（默认 1-3个月）
        risk_level: 风险偏好（默认 中等）
        days_back: 历史数据天数（默认 30）
    
    Returns:
        字典，包含：
        - status: 'success' / 'partial' / 'failed'
        - output: 完整的分析结果（多Agent输出）
        - results: dict，每个 Agent 的输出
        - errors: dict，错误信息（如有）
    
    示例:
        # 基本使用
        result = analyze("技术面怎么样？")
        
        # 指定股票
        result = analyze("值得买吗？", ts_code="600519.SH")
        
        # 指定风险偏好
        result = analyze("风险大吗？", risk_level="保守")
        
        # 访问结果
        if result['status'] == 'success':
            print(result['output'])
        else:
            print(f"有错误: {result['errors']}")
    """
    
    # 计算日期
    today = datetime.now()
    start_date_dt = today - timedelta(days=days_back)
    start_date = start_date_dt.strftime("%Y%m%d")
    end_date = today.strftime("%Y%m%d")
    
    # 创建工作流请求
    request = WorkflowRequest(
        mode=WorkflowMode.COMPREHENSIVE,  # 自动使用综合分析
        ts_code=ts_code,
        user_prompt=prompt,
        start_date=start_date,
        end_date=end_date,
        horizon=horizon,
        risk_level=risk_level,
        use_rag=True,
        rag_top_k=4,
    )
    
    # 运行工作流
    engine = get_multi_agent_system()
    workflow_result = engine.run(request)
    
    # 构建输出
    output_lines = []
    
    # Agent 输出
    if workflow_result.results:
        for agent_name, agent_output in workflow_result.results.items():
            output_lines.append(f"【{agent_name.upper()}】")
            output_lines.append(agent_output)
            output_lines.append("")
    
    # 错误信息
    if workflow_result.errors:
        output_lines.append("【错误信息】")
        for agent_name, error in workflow_result.errors.items():
            output_lines.append(f"  {agent_name}: {error}")
    
    return {
        "status": workflow_result.status,
        "output": "\n".join(output_lines),
        "results": workflow_result.results,
        "errors": workflow_result.errors,
    }


def analyze_quick(prompt: str, ts_code: str = "000001.SZ") -> str:
    """
    最极简的 API - 直接返回文本结果
    
    >>> from lianghua_agents.simple_api import analyze_quick
    >>> print(analyze_quick("这支股票怎么样？"))
    
    Args:
        prompt: 分析提示词
        ts_code: 股票代码
    
    Returns:
        分析结果文本（字符串）
    """
    result = analyze(prompt=prompt, ts_code=ts_code)
    return result['output']
