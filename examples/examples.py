#!/usr/bin/env python3
"""
使用示例 - 展示如何使用极简 API
从这些示例中选择一个适合你的用法
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from dotenv import load_dotenv
load_dotenv()


def example_1_most_simple():
    """示例 1: 最简单的用法"""
    print("\n" + "="*70)
    print("示例 1: 最简单 - 只需要提示词")
    print("="*70 + "\n")
    
    from lianghua_agents.simple_api import analyze_quick
    
    # 就这一行！
    result = analyze_quick("这支股票的技术面怎么样？")
    print(result)


def example_2_with_stock_code():
    """示例 2: 指定股票代码"""
    print("\n" + "="*70)
    print("示例 2: 指定股票代码")
    print("="*70 + "\n")
    
    from lianghua_agents.simple_api import analyze_quick
    
    # 指定要分析的股票
    result = analyze_quick(
        prompt="目标价位在哪里？",
        ts_code="600519.SH"  # 贵州茅台
    )
    print(result)


def example_3_detailed():
    """示例 3: 更详细的使用"""
    print("\n" + "="*70)
    print("示例 3: 详细参数 - 如果需要自定义")
    print("="*70 + "\n")
    
    from lianghua_agents.simple_api import analyze
    
    result = analyze(
        prompt="风险评估",
        ts_code="000001.SZ",        # 招商银行
        horizon="1-3个月",           # 投资周期
        risk_level="保守",           # 风险偏好
        days_back=60,               # 使用 60 天历史数据
    )
    
    # 检查结果
    print(f"分析状态: {result['status']}\n")
    print(result['output'])


def example_4_check_result_status():
    """示例 4: 检查结果状态"""
    print("\n" + "="*70)
    print("示例 4: 检查结果是否成功")
    print("="*70 + "\n")
    
    from lianghua_agents.simple_api import analyze
    
    result = analyze("价值评估")
    
    # 检查状态
    if result['status'] == 'success':
        print("✓ 分析成功！")
        print(result['output'])
    elif result['status'] == 'partial':
        print("⚠️ 部分成功（有些 Agent 出错）")
        print(result['output'])
        print("\n错误信息:")
        for agent_name, error in result['errors'].items():
            print(f"  {agent_name}: {error}")
    else:
        print("✗ 分析失败")
        print(result['errors'])


def example_5_multiple_stocks():
    """示例 5: 分析多支股票"""
    print("\n" + "="*70)
    print("示例 5: 分析多支股票")
    print("="*70 + "\n")
    
    from lianghua_agents.simple_api import analyze_quick
    
    stocks = [
        "000001.SZ",  # 平安银行
        "600519.SH",  # 贵州茅台
        "300750.SZ",  # 宁德时代
    ]
    
    question = "这支股票值得建仓吗？"
    
    for stock in stocks:
        print(f"\n分析 {stock}...")
        result = analyze_quick(question, ts_code=stock)
        # 只输出前 500 个字符作为演示
        print(result[:500] + "..." if len(result) > 500 else result)
        print()


def example_6_save_result():
    """示例 6: 保存结果"""
    print("\n" + "="*70)
    print("示例 6: 保存分析结果")
    print("="*70 + "\n")
    
    import json
    from lianghua_agents.simple_api import analyze
    
    result = analyze("完整分析")
    
    # 保存为 JSON 文件
    output_file = Path(__file__).parent.parent / "analysis_result.json"
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    print(f"✓ 已保存到: {output_file}")
    print(f"\n结果包含:")
    print(f"  - status: {result['status']}")
    print(f"  - output: {len(result['output'])} 字符")
    print(f"  - 错误: {len(result['errors'])} 个")


def main():
    """主函数"""
    print("""
╔═══════════════════════════════════════════════════════════════════════╗
║                 lianghua 极简使用示例                                 ║
║                                                                       ║
║  选择一个示例来运行。你可以复制这些代码到自己的程序中使用            ║
╚═══════════════════════════════════════════════════════════════════════╝
    """)
    
    examples = {
        "1": ("最简单 - 只需提示词", example_1_most_simple),
        "2": ("指定股票代码", example_2_with_stock_code),
        "3": ("详细参数", example_3_detailed),
        "4": ("检查结果状态", example_4_check_result_status),
        "5": ("分析多支股票", example_5_multiple_stocks),
        "6": ("保存结果", example_6_save_result),
    }
    
    print("可用示例:\n")
    for key, (desc, _) in examples.items():
        print(f"  {key}. {desc}")
    
    # 询问用户
    choice = input("\n👉 选择示例 (1-6): ").strip()
    
    if choice in examples:
        desc, func = examples[choice]
        print(f"\n运行: {desc}\n")
        try:
            func()
            print("\n✓ 示例运行完成")
        except Exception as e:
            print(f"\n✗ 运行出错: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("无效选择")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 已取消")
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
