"""
Alpha Research Agent - 基于OpenAI Agents SDK构建
集成AlphaAnalysisToolkit和AlphaVisualizationToolkit
"""
import os
import asyncio
import json
from typing import Dict, List, Any, Optional
from datetime import datetime
import pandas as pd
import numpy as np
from pydantic import BaseModel

# Local Agents SDK imports
from local_agents import Agent, function_tool

# Toolkit imports (optional, with stubs for offline use)
try:
    from alpha_analysis_toolkit import AlphaAnalysisToolkit
except ImportError:
    class AlphaAnalysisToolkit:
        @staticmethod
        def load_asset_data(path, data_format="csv"):
            return pd.read_csv(path)
        @staticmethod
        def preprocess_data(data, qlib_format=False):
            return data
        @staticmethod
        def calculate_technical_indicators(data):
            return {"rsi": 50, "macd": 0, "bollinger_position": 0.5}
        @staticmethod
        def generate_alpha_signals(data):
            return {"momentum_signal": 0.1, "reversal_signal": -0.05}
        @staticmethod
        def calculate_risk_metrics(data):
            return {"volatility": 0.2, "sharpe_ratio": 0.8, "max_drawdown": -0.15}

try:
    from alpha_visualization_toolkit import AlphaVisualizationToolkit
except ImportError:
    class AlphaVisualizationToolkit:
        pass


# ============================================================================
# Data Structure Definitions
# ============================================================================

class FactorPerformance(BaseModel):
    """Expected factor performance"""
    model_config = {"extra": "forbid"}

    market_regime: str
    confidence_level: float
    expected_sharpe: float


class FactorProposal(BaseModel):
    """Single factor proposal"""
    model_config = {"extra": "forbid"}

    factor_name: str
    description: str
    formula: str
    justification: str
    expected_performance: FactorPerformance


class AlphaFactorResponse(BaseModel):
    """Structured response for factor proposals"""
    model_config = {"extra": "forbid"}

    factor_proposals: List[FactorProposal]
    market_summary: str
    risk_assessment: str


# ============================================================================
# Context Class
# ============================================================================

class AlphaResearchContext:
    """Alpha research execution context"""
    def __init__(self):
        self.current_asset: Optional[str] = None
        self.market_data: Optional[pd.DataFrame] = None
        self.analysis_results: Dict[str, Any] = {}
        self.visualizations: Dict[str, Any] = {}
        self.factor_proposals: List[Dict] = []
        self.iteration_count: int = 0
        self.execution_log: List[Dict[str, Any]] = []
        self.session_id: str = datetime.now().strftime("%Y%m%d_%H%M%S")

    def log_function_call(self, name: str, args: Dict, result: str, execution_time: float = 0):
        self.execution_log.append({
            'timestamp': datetime.now().isoformat(),
            'function_name': name,
            'arguments': args,
            'result_preview': result[:500],
            'result_length': len(result),
            'execution_time': execution_time,
            'step_number': len(self.execution_log) + 1
        })

    def save_session_log(self, output_dir="agent_logs"):
        os.makedirs(output_dir, exist_ok=True)
        log_path = os.path.join(output_dir, f"session_{self.session_id}.json")
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump({
                "session_id": self.session_id,
                "execution_log": self.execution_log,
                "summary": {
                    "steps": len(self.execution_log),
                    "asset": self.current_asset,
                    "data_loaded": self.market_data is not None,
                    "factor_count": len(self.factor_proposals)
                }
            }, f, ensure_ascii=False, indent=2)
        return log_path


# ============================================================================
# Tool Functions (decorated with @function_tool)
# ============================================================================

@function_tool
def store_agent_reflection(ctx: AlphaResearchContext, strategy_name: str, issue: str, lesson: str):
    """Store a learned lesson into the Neo4j Long-term memory graph."""
    start = datetime.now()
    try:
        from agent_pools.memory.agent_memory_client import AgentMemoryClient

        client = AgentMemoryClient()
        result = client.store_reflection(agent_name="AlphaResearchAgent", strategy_name=strategy_name, issue=issue, lesson_learned=lesson)
        client.close()

        ctx.log_function_call("store_agent_reflection", {"strategy": strategy_name}, result, (datetime.now() - start).total_seconds())
        return result
    except Exception as e:
        return f"Neo4j Memory store failed: {e}"

@function_tool
def query_past_agent_lessons(ctx: AlphaResearchContext, keyword: str):
    """Query past lessons from Neo4j Long-term memory using a keyword like 'overfitting'."""
    start = datetime.now()
    try:
        from agent_pools.memory.agent_memory_client import AgentMemoryClient

        client = AgentMemoryClient()
        lessons = client.retrieve_lessons_by_issue(keyword)
        client.close()

        if not lessons:
            result = f"No past lessons found for keyword: {keyword}"
        else:
            result = "Past lessons:\n" + "\n".join(lessons)

        ctx.log_function_call("query_past_agent_lessons", {"keyword": keyword}, result, (datetime.now() - start).total_seconds())
        return result
    except Exception as e:
        return f"Neo4j Memory query failed: {e}"

@function_tool
def retrieve_alpha_factors_from_kb(ctx: AlphaResearchContext, query: str, top_k: int = 3):
    """Retrieve relevant alpha factor research from the Alpha101 paper using RAG/VectorDB."""
    start = datetime.now()
    try:
        from agent_pools.memory.agent_rag_client import get_rag_client

        rag = get_rag_client()
        results = rag.query(query, n_results=top_k)

        if not results:
            summary = "No matching research found in the knowledge base."
        else:
            summary = f"Found {len(results)} relevant passages from Alpha101 paper:\n\n" + "\n\n".join(results)

        ctx.log_function_call("retrieve_alpha_factors_from_kb", {"query": query, "top_k": top_k}, summary,
                              (datetime.now() - start).total_seconds())
        return summary
    except ImportError as e:
        return f"RAG Client dependencies missing. Ensure chromadb is installed: {e}"
    except Exception as e:
        return f"RAG Query failed: {e}"

@function_tool
def load_and_analyze_data(ctx: AlphaResearchContext, csv_path: str, qlib_format: bool = False):
    """Load and analyze asset data, compute technical indicators and signals"""
    start = datetime.now()
    try:
        print(f"Loading data: {csv_path}")
        data = AlphaAnalysisToolkit.load_asset_data(csv_path, data_format="csv")
        data = AlphaAnalysisToolkit.preprocess_data(data, qlib_format=qlib_format)
        indicators = AlphaAnalysisToolkit.calculate_technical_indicators(data)
        signals = AlphaAnalysisToolkit.generate_alpha_signals(data)
        risk = AlphaAnalysisToolkit.calculate_risk_metrics(data)

        ctx.current_asset = csv_path
        ctx.market_data = data
        ctx.analysis_results = {
            "technical_indicators": indicators,
            "signals": signals,
            "risk_metrics": risk
        }

        summary = (
            f"Data loaded successfully: {csv_path}\n"
            f"Rows={len(data)} | Indicators={len(indicators)} | Signals={len(signals)}\n"
            f"Volatility={risk.get('volatility', 0):.2%} | Sharpe={risk.get('sharpe_ratio', 0):.2f}"
        )

        ctx.log_function_call("load_and_analyze_data", {"csv_path": csv_path}, summary,
                              (datetime.now() - start).total_seconds())
        return summary
    except Exception as e:
        return f"Data loading failed: {e}"


@function_tool
def load_qlib_factors(ctx: AlphaResearchContext,
                      top_n: int = 30,
                      start_date: str = "2022-08-16",
                      end_date: str = "2024-12-31"):
    """
    Compute and evaluate IC/IR using Alpha158 handler
    """
    from qlib.data.dataset import DatasetH
    from qlib.contrib.data.handler import Alpha158

    start_time = datetime.now()
    try:
        provider_uri = os.getenv("QLIB_PROVIDER_URI", os.path.expanduser("~/qlib_data/stock_custom_day"))
        feats_dir = os.path.join(provider_uri, "features")
        inst_list = sorted([d for d in os.listdir(feats_dir)
                            if os.path.isdir(os.path.join(feats_dir, d))])
        print(f"Detected {len(inst_list)} stocks: {inst_list[:5]} ...")

        # === 1) Build DatasetH ===
        handler_cfg = {
            "class": "Alpha158",
            "module_path": "qlib.contrib.data.handler",
            "kwargs": {
                "start_time": start_date,
                "end_time": end_date,
                "fit_start_time": start_date,
                "fit_end_time": end_date,
                "instruments": inst_list,
            },
        }
        ds = DatasetH(handler=handler_cfg, segments={"all": (start_date, end_date)})

        feat_df = ds.prepare("all", col_set="feature")
        valid_cols = [c for c in feat_df.columns
                      if feat_df[c].dropna().std() > 0 and feat_df[c].notna().sum() > 50]
        feat_df = feat_df[valid_cols]
        print(f"Valid factors: {len(valid_cols)}")

        # === 2) Next-day return ===
        close = (D.features(instruments=inst_list, fields=["$close"],
                            start_time=start_date, end_time=end_date, freq="day")
                 .reset_index().set_index(["datetime", "instrument"]))
        ret_fwd = close["$close"].groupby(level=1).pct_change().shift(-1).rename("ret_fwd")

        panel = feat_df.join(ret_fwd, how="inner").replace([np.inf, -np.inf], np.nan).dropna(subset=["ret_fwd"])
        gb = panel.groupby(level=0)

        # === 3) Compute IC/IR ===
        records = []
        for f in valid_cols:
            ic_by_day = gb.apply(lambda g: g[f].corr(g["ret_fwd"], method="spearman")).dropna()
            if len(ic_by_day) < 10:
                continue
            ic_mean, ic_std = ic_by_day.mean(), ic_by_day.std(ddof=1)
            ir = ic_mean / ic_std if ic_std > 0 else np.nan
            records.append({"factor": f, "IC": float(ic_mean), "IR": float(ir), "days": len(ic_by_day)})

        perf_df = pd.DataFrame(records).dropna().sort_values("IR", ascending=False)
        ctx.analysis_results["qlib_factors"] = perf_df

        summary = f"""
Successfully computed {len(perf_df)} Alpha158 factor performances
Top 5 (by IR):
{perf_df.head(5).to_string(index=False)}
"""
        ctx.log_function_call("load_qlib_factors",
                              {"provider": provider_uri, "top_n": top_n},
                              summary, (datetime.now() - start_time).total_seconds())
        print(summary)
        return summary

    except Exception as e:
        error_msg = f"Failed to load Alpha158 factors: {e}"
        ctx.log_function_call("load_qlib_factors", {}, error_msg, 0)
        print(error_msg)
        return error_msg


@function_tool
def propose_alpha_factors(ctx: AlphaResearchContext):
    """Propose alpha factors based on Qlib results"""
    perf_df = ctx.analysis_results.get("qlib_factors")
    if perf_df is None or perf_df.empty:
        return "Please run load_qlib_factors() first."
    ctx.factor_proposals = perf_df.head(5).to_dict("records")
    result = "\n".join(
        [f"{i+1}. {r['factor']} | IC={r['IC']:.3f} | IR={r['IR']:.2f}"
         for i, r in enumerate(ctx.factor_proposals)]
    )
    ctx.log_function_call("propose_alpha_factors", {}, result, 0)
    return result


@function_tool
def generate_iteration_report(ctx: AlphaResearchContext, iteration_number: int = 1):
    """Generate iteration report"""
    ctx.iteration_count = iteration_number
    report = f"""
Research Report #{iteration_number}
Asset: {ctx.current_asset}
Analysis results: {len(ctx.analysis_results)}
Visualizations: {len(ctx.visualizations)}
Factor proposals: {len(ctx.factor_proposals)}
Execution steps: {len(ctx.execution_log)}
"""
    path = ctx.save_session_log()
    report += f"Log saved: {path}"
    ctx.log_function_call("generate_iteration_report", {"iteration_number": iteration_number}, report, 0)
    return report


# ============================================================================
# Alpha Research Agent
# ============================================================================

class AlphaResearchAgent:
    """Alpha Research Agent - executes a full alpha analysis workflow"""

    def __init__(self):
        self.context = AlphaResearchContext()
        self.agent = Agent(
            name="AlphaResearchAgent",
            model="gpt-4o-mini",
            instructions="""
You are a professional quantitative research assistant. You can call the following tools:
- load_and_analyze_data
- load_qlib_factors
- propose_alpha_factors
- generate_iteration_report
- store_agent_reflection (save lessons learned to long-term memory)
- query_past_agent_lessons (search past lessons by keyword)
- retrieve_alpha_factors_from_kb (search the Alpha101 paper via RAG)
Please perform a full alpha research workflow. Use the memory tools to persist insights and the RAG tool to reference the Alpha101 paper.
""",
            tools=[
                load_and_analyze_data,
                load_qlib_factors,
                propose_alpha_factors,
                generate_iteration_report,
                store_agent_reflection,
                query_past_agent_lessons,
                retrieve_alpha_factors_from_kb,
            ],
        )

    async def run_analysis(self, user_request: str):
        """Run the analysis asynchronously"""
        print(f"\nStarting Alpha Research Analysis | Session {self.context.session_id}\n")
        result_text = self.agent.run(user_request, context=self.context)
        log_path = self.context.save_session_log()
        print(f"\nAnalysis complete | Log: {log_path}\n")
        return result_text

    def run_analysis_sync(self, user_request: str):
        """Synchronous execution"""
        return asyncio.run(self.run_analysis(user_request))

    def summarize_with_llm(self):
        """
        Use the LLM to summarize current analysis results.
        """
        risk = self.context.analysis_results.get("risk_metrics", {})
        factor_df = self.context.analysis_results.get("qlib_factors")

        # Construct the LLM prompt
        text_prompt = f"""
You are a quantitative research assistant. Below are the results from an alpha research session.

[1] Data Analysis Results
Volatility: {risk.get('volatility', 'Unknown')}
Sharpe Ratio: {risk.get('sharpe_ratio', 'Unknown')}
Other metrics: {risk}

[2] Alpha Factor Performance (Top 10)
{factor_df.head(10).to_string(index=False) if factor_df is not None else 'No factor data available'}

Please provide:
- A short summary of market characteristics
- Analysis of what these factors represent
- Which combinations may be useful
- Suggestions for improvement or further research
"""

        print("\nCalling LLM for analysis summary ...")

        try:
            response = self.agent.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a professional quantitative analyst specializing in alpha factor research."},
                    {"role": "user", "content": text_prompt},
                ],
            )
            summary_text = response.choices[0].message.content
            print("\nLLM Summary:\n", summary_text[:1500])
            return summary_text
        except Exception as e:
            print(f"LLM call failed: {e}")
            return f"LLM call failed: {e}"

    def run_complete_workflow(self, csv_path: str, user_input: str = ""):
        """
        Execute a full alpha research workflow:
        1. Run analysis tools
        2. Use LLM for summarization
        3. Generate a final combined report
        """
        prompt = f"""
Perform a complete alpha research on {csv_path}, including:
1. Call load_and_analyze_data
2. Call load_qlib_factors
3. Call propose_alpha_factors
4. Generate the first iteration report
{user_input}
"""

        # Step 1: Run analysis
        base_result = self.run_analysis_sync(prompt)

        # Step 2: Summarize with LLM
        llm_summary = self.summarize_with_llm()

        # Step 3: Combine results
        final_report = base_result + "\n\n======\nLLM Summary:\n" + llm_summary
        print("\nFinal report generated successfully.")
        return final_report


# ============================================================================
# Main Entry Point
# ============================================================================

SAMPLE_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sample_data")


def _ensure_sample_data() -> str:
    """Create sample OHLCV data for demo purposes if no real data available."""
    os.makedirs(SAMPLE_DATA_DIR, exist_ok=True)
    sample_path = os.path.join(SAMPLE_DATA_DIR, "sample_stock.csv")

    if not os.path.exists(sample_path):
        print("Creating sample stock data for demo...")
        dates = pd.date_range("2023-01-01", periods=252, freq="B")
        np.random.seed(42)
        returns = np.random.normal(0.0005, 0.015, len(dates))
        prices = 100 * np.cumprod(1 + returns)
        volume = np.random.lognormal(10, 0.8, len(dates)).astype(int)

        df = pd.DataFrame({
            "date": dates,
            "open": prices * (1 + np.random.normal(0, 0.003, len(dates))),
            "high": prices * (1 + np.abs(np.random.normal(0, 0.008, len(dates)))),
            "low": prices * (1 - np.abs(np.random.normal(0, 0.008, len(dates)))),
            "close": prices,
            "volume": volume,
        })
        df.to_csv(sample_path, index=False)
        print(f"Sample data saved to {sample_path}")

    return sample_path


def demo_rag():
    """Demo RAG retrieval from the Alpha101 paper."""
    print("\n" + "=" * 60)
    print("Demo: RAG Knowledge Base (Alpha101 Paper)")
    print("=" * 60)
    try:
        from agent_pools.memory.agent_rag_client import get_rag_client
        rag = get_rag_client()
        queries = [
            "How to construct alpha factors from price and volume data?",
            "What is the Sharpe ratio of the top performing factors?",
        ]
        for q in queries:
            print(f"\nQuery: {q}")
            results = rag.query(q, n_results=2)
            for i, r in enumerate(results, 1):
                print(f"  Result {i}: {r[:200]}...")
    except Exception as e:
        print(f"  RAG demo skipped: {e}")


def demo_memory():
    """Demo Neo4j memory storage and retrieval."""
    print("\n" + "=" * 60)
    print("Demo: Agent Memory System (Neo4j)")
    print("=" * 60)
    try:
        from agent_pools.memory.agent_memory_client import AgentMemoryClient
        client = AgentMemoryClient()
        client.store_reflection(
            agent_name="AlphaResearchAgent",
            strategy_name="momentum_factor_v1",
            issue="overfitting on small sample",
            lesson_learned="Use walk-forward validation and require at least 500 data points",
        )
        print("  Stored reflection: momentum_factor_v1 overfitting lesson")

        lessons = client.retrieve_lessons_by_issue("overfitting")
        print(f"  Retrieved {len(lessons)} lessons about 'overfitting':")
        for l in lessons:
            print(f"    - {l[:150]}...")
        client.close()
    except Exception as e:
        print(f"  Memory demo skipped (Neo4j not running): {e}")


def demo_agent_workflow(csv_path: str):
    """Demo the full AlphaResearchAgent workflow."""
    print("\n" + "=" * 60)
    print("Demo: Alpha Research Agent Workflow")
    print("=" * 60)
    agent = AlphaResearchAgent()
    result = agent.run_analysis_sync(
        f"Load data from {csv_path}, analyze it, "
        f"query the knowledge base for 'momentum factor construction', "
        f"and store a reflection about what you learned."
    )
    print(f"\nAgent result:\n{result[:1000]}")


def main():
    """Main entry point - runs demos of the full system with memory and RAG."""
    print("=" * 60)
    print("  Lianghua - Alpha Research Agent Demo")
    print("  Memory + RAG Integration")
    print("=" * 60)

    csv_path = _ensure_sample_data()

    # Demo 1: RAG from Alpha101 paper
    demo_rag()

    # Demo 2: Memory system (requires Neo4j, will skip gracefully)
    demo_memory()

    # Demo 3: Full agent workflow
    demo_agent_workflow(csv_path)

    print("\n" + "=" * 60)
    print("  Demo complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
