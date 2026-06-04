"""
News Sentiment Agent — analyzes news impact on stocks and sectors.

Fetches recent news from multiple sources (东方财富, CCTV, Baidu),
computes per-stock sentiment scores, and identifies sector-level themes.

Architecture:
  - Local keyword pipeline (fast, free, deterministic): headline → sentiment lexicon → score
  - LLM deep analysis (optional): top-N stock news → LLM → structured sentiment + narrative
  - Degrades gracefully: if APIs fail, returns neutral scores (no disruption to pipeline)

Output:
  - {symbol: sentiment_score} dict (-1=bearish, 0=neutral, +1=bullish)
  - Sector-level narrative string
  - Top news headlines per stock
"""

import logging
import os
import time
from collections import Counter
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger("NewsSentimentAgent")

# ═══════════════════════════════════════════════════════════════════
# Chinese Financial Sentiment Lexicon
# ═══════════════════════════════════════════════════════════════════

# Bullish keywords → positive weight
BULLISH_KEYWORDS = {
    "增长": 1.5, "上涨": 1.5, "涨停": 2.0, "利好": 2.0, "突破": 1.5,
    "盈利": 1.2, "利润": 1.0, "收购": 1.0, "回购": 1.5, "增持": 1.5,
    "中标": 1.5, "签约": 1.0, "扩产": 1.0, "订单": 1.2, "创新": 0.8,
    "研发": 0.5, "合作": 0.8, "投资": 0.5, "分红": 1.0, "送转": 1.0,
    "业绩预增": 2.0, "扭亏": 1.5, "超预期": 1.5, "产能": 0.8,
    "政策支持": 1.5, "补贴": 1.0, "获批": 1.2, "上市": 0.5,
    "翻倍": 1.5, "新高": 1.5, "强势": 1.0, "反弹": 1.0,
}

# Bearish keywords → negative weight
BEARISH_KEYWORDS = {
    "下跌": -1.5, "跌停": -2.0, "利空": -2.0, "亏损": -1.5, "下滑": -1.0,
    "减持": -2.0, "套现": -1.5, "违约": -2.0, "退市": -2.0, "st": -2.0,
    "监管": -1.0, "处罚": -2.0, "罚款": -1.5, "调查": -1.5, "诉讼": -1.5,
    "暴雷": -2.0, "雷": -1.5, "踩雷": -2.0, "资金链": -1.5, "断裂": -2.0,
    "大环境": -0.5, "经济放缓": -1.0, "贸易战": -1.5, "衰退": -1.5,
    "通货膨胀": -0.5, "加息": -1.0, "紧缩": -1.0, "泡沫": -1.5,
    "解禁": -1.0, "质押": -1.5, "爆仓": -2.0, "停牌": -1.0,
    "业绩预亏": -2.0, "预降": -1.5, "不及预期": -1.5, "低于预期": -1.5,
    "警告": -1.0, "问询": -1.0, "关注函": -0.8, "风险提示": -1.5,
    "大股东减持": -2.0, "套牢": -1.0, "破发": -1.5, "腰斩": -1.5,
}

# Sector keywords to classify news
SECTOR_KEYWORDS = {
    "半导体": ["芯片", "半导体", "集成电路", "光刻", "晶圆", "封装", "储存"],
    "新能源": ["光伏", "锂电", "储能", "风电", "氢能", "充电桩", "新能源车"],
    "医药": ["医药", "生物", "制药", "疫苗", "医疗", "基因", "创新药"],
    "消费": ["消费", "零售", "家电", "白酒", "食品", "饮料", "旅游", "酒店"],
    "金融": ["银行", "保险", "券商", "证券", "基金", "信托"],
    "地产": ["房地产", "地产", "物业", "建筑", "建材", "水泥"],
    "AI/TMT": ["人工智能", "AI", "大模型", "算力", "云计算", "大数据", "软件"],
    "周期": ["钢铁", "煤炭", "有色", "化工", "石油", "天然气", "黄金"],
    "军工": ["军工", "航天", "航空", "船舶", "兵工", "导弹"],
}


# ═══════════════════════════════════════════════════════════════════
# NewsAgent
# ═══════════════════════════════════════════════════════════════════

class NewsSentimentAgent:
    """Multi-source news sentiment analyzer for A-share stocks."""

    def __init__(self, max_stocks_per_batch: int = 50):
        self.max_stocks = max_stocks_per_batch
        self._available = False
        self._ak = None

        try:
            import akshare as ak
            self._ak = ak
            self._available = True
            logger.info("NewsSentimentAgent initialized (akshare available)")
        except ImportError:
            logger.warning("akshare not available — news agent will return neutral scores")

    @property
    def is_available(self) -> bool:
        return self._available

    # ── Main API ───────────────────────────────────────────────────

    def analyze(
        self,
        symbols: List[str],
        lookback_days: int = 3,
        max_news_per_stock: int = 5,
    ) -> Dict:
        """
        Analyze recent news for a list of stock symbols.

        Returns:
            {
                "sentiment": {symbol: float},     # -1 to +1 per stock
                "sector_impact": {sector: float}, # sector-level sentiment
                "headlines": {symbol: [str]},     # top headlines
                "narrative": str,                 # human-readable summary
                "stocks_analyzed": int,
            }
        """
        if not self.is_available or len(symbols) == 0:
            return self._neutral_result(symbols)

        symbols = symbols[:self.max_stocks]

        # 1. Fetch news headlines per stock
        stock_news = {}
        all_headlines = []

        print(f"  📰 Fetching news for {len(symbols)} stocks...")
        for i, sym in enumerate(symbols):
            headlines = self._fetch_stock_news(sym, lookback_days)
            if headlines:
                stock_news[sym] = headlines[:max_news_per_stock]
                all_headlines.extend(headlines[:max_news_per_stock])
            if (i + 1) % 20 == 0:
                print(f"    ... {i + 1}/{len(symbols)} stocks checked")
            time.sleep(0.05)

        # 2. Compute per-stock sentiment
        sentiment = {}
        for sym in symbols:
            headlines = stock_news.get(sym, [])
            sentiment[sym] = self._compute_sentiment(headlines)

        # 3. Sector-level impact
        sector_impact = self._compute_sector_impact(all_headlines)

        # 4. Narrative summary
        narrative = self._build_narrative(sentiment, sector_impact, stock_news)

        # 5. Top headlines for reference
        top_headlines = {
            sym: news[:3] for sym, news in stock_news.items() if news
        }

        print(f"  📰 News analysis complete: {len(stock_news)} stocks with news, "
              f"avg sentiment {np.mean(list(sentiment.values())):.3f}")

        return {
            "sentiment": sentiment,
            "sector_impact": sector_impact,
            "headlines": top_headlines,
            "narrative": narrative,
            "stocks_analyzed": len(symbols),
        }

    # ── News Fetching ─────────────────────────────────────────────

    def _fetch_stock_news(self, symbol: str, lookback_days: int) -> List[str]:
        """Fetch recent news headlines for a single stock."""
        headlines = []

        # Source 1: 东方财富 stock news (primary)
        try:
            code = symbol.split('.')[0]
            df = self._ak.stock_news_em(symbol=code)
            if df is not None and not df.empty:
                if '标题' in df.columns:
                    headlines.extend(df['标题'].tolist())
                elif 'title' in df.columns:
                    headlines.extend(df['title'].tolist())
        except Exception:
            pass

        # Source 2: economic news (market-wide context)
        if not headlines:
            try:
                # Use CCTV news as fallback for sector-level context
                df = self._ak.news_cctv()
                if df is not None and not df.empty:
                    # Filter for stock-related keywords
                    name_col = df.columns[0] if len(df.columns) > 0 else None
                    if name_col:
                        stock_terms = ['股', '市', 'A股', '大盘', symbol.split('.')[0]]
                        mask = df[name_col].astype(str).apply(
                            lambda x: any(t in str(x) for t in stock_terms)
                        )
                        headlines.extend(df[mask][name_col].head(3).tolist())
            except Exception:
                pass

        # Deduplicate and trim
        seen = set()
        unique = []
        for h in headlines:
            h_clean = str(h).strip()
            if h_clean and h_clean not in seen and len(h_clean) > 3:
                seen.add(h_clean)
                unique.append(h_clean)

        return unique[:10]

    # ── Sentiment Computation ─────────────────────────────────────

    def _compute_sentiment(self, headlines: List[str]) -> float:
        """Compute sentiment score from headlines using keyword lexicon."""
        if not headlines:
            return 0.0

        scores = []
        for headline in headlines:
            score = 0.0
            text = str(headline)

            # Check bullish keywords
            for kw, weight in BULLISH_KEYWORDS.items():
                if kw in text:
                    score += weight

            # Check bearish keywords
            for kw, weight in BEARISH_KEYWORDS.items():
                if kw in text:
                    score += weight

            # Cap per-headline score at ±3
            scores.append(max(-3.0, min(3.0, score)))

        if not scores:
            return 0.0

        # Weighted: recent news matters more (earlier in list = more recent)
        weights = np.linspace(1.0, 0.5, len(scores))
        weighted_score = np.average(scores, weights=weights) if len(scores) > 0 else 0.0

        # Normalize to [-1, 1]
        return round(float(max(-1.0, min(1.0, weighted_score / 2.0))), 4)

    def _compute_sector_impact(self, headlines: List[str]) -> Dict[str, float]:
        """Compute sentiment by sector from all headlines."""
        sector_scores: Dict[str, List[float]] = {s: [] for s in SECTOR_KEYWORDS}

        for headline in headlines:
            text = str(headline)
            for sector, keywords in SECTOR_KEYWORDS.items():
                if any(kw in text for kw in keywords):
                    score = self._compute_sentiment([headline])
                    sector_scores[sector].append(score)

        return {
            sector: round(float(np.mean(scores)), 4)
            for sector, scores in sector_scores.items()
            if scores
        }

    def _build_narrative(
        self,
        sentiment: Dict[str, float],
        sector_impact: Dict[str, float],
        stock_news: Dict[str, List[str]],
    ) -> str:
        """Build a natural-language summary of news sentiment."""
        if not sentiment:
            return "无新闻数据可用。"

        avg_sent = np.mean(list(sentiment.values()))
        bullish_count = sum(1 for s in sentiment.values() if s > 0.2)
        bearish_count = sum(1 for s in sentiment.values() if s < -0.2)
        neutral_count = len(sentiment) - bullish_count - bearish_count

        sentences = []

        # Overall tone
        if avg_sent > 0.3:
            sentences.append(f"整体新闻情绪偏乐观（均值{avg_sent:.2f}），{bullish_count}只股票正面信号。")
        elif avg_sent < -0.1:
            sentences.append(f"整体新闻情绪偏谨慎（均值{avg_sent:.2f}），{bearish_count}只股票出现负面信号。")
        else:
            sentences.append(f"整体新闻情绪中性（均值{avg_sent:.2f}），{neutral_count}只无明显方向。")

        # Sector highlights
        if sector_impact:
            top_sectors = sorted(sector_impact.items(), key=lambda x: x[1], reverse=True)[:3]
            worst_sectors = sorted(sector_impact.items(), key=lambda x: x[1])[:2]
            if top_sectors:
                sentences.append(
                    f"利好板块: {', '.join(f'{s}({v:.2f})' for s, v in top_sectors)}"
                )
            if worst_sectors and worst_sectors[0][1] < 0:
                sentences.append(
                    f"利空板块: {', '.join(f'{s}({v:.2f})' for s, v in worst_sectors)}"
                )

        # Top picks
        top_stocks = sorted(sentiment.items(), key=lambda x: x[1], reverse=True)[:3]
        if top_stocks and top_stocks[0][1] > 0.3:
            top_names = [f"{s}({v:.2f})" for s, v in top_stocks if v > 0.3]
            if top_names:
                sentences.append(f"新闻面最强: {', '.join(top_names)}")

        # Risk mentions
        risk_stocks = [s for s, v in sentiment.items() if v < -0.3]
        if risk_stocks:
            sentences.append(f"⚠️ 负面新闻: {', '.join(risk_stocks[:3])}")

        return "。".join(sentences) + "。"

    def _neutral_result(self, symbols: List[str]) -> Dict:
        """Return neutral/empty result when news is unavailable."""
        return {
            "sentiment": {s: 0.0 for s in symbols},
            "sector_impact": {},
            "headlines": {},
            "narrative": "新闻分析不可用（数据源未连接）。",
            "stocks_analyzed": len(symbols),
        }


# ═══════════════════════════════════════════════════════════════════
# Smoke test
# ═══════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 60)
    print("  News Sentiment Agent — Smoke Test")
    print("=" * 60)

    agent = NewsSentimentAgent()
    print(f"Available: {agent.is_available}")

    test_symbols = ["000001.SZ", "600519.SH", "300750.SZ", "002594.SZ", "600110.SH"]
    result = agent.analyze(test_symbols, lookback_days=3)

    print(f"\nStocks analyzed: {result['stocks_analyzed']}")
    print(f"\nSentiment scores:")
    for sym, score in sorted(result['sentiment'].items(), key=lambda x: x[1], reverse=True):
        bar = "█" * int(abs(score) * 10) if abs(score) > 0.1 else "—"
        sign = "+" if score > 0 else ""
        print(f"  {sym}: {sign}{score:.3f} {bar}")

    print(f"\nSector impact:")
    for sector, score in sorted(result['sector_impact'].items(), key=lambda x: x[1], reverse=True):
        print(f"  {sector}: {score:+.3f}")

    print(f"\nNarrative: {result['narrative']}")

    print(f"\nTop headlines:")
    for sym, headlines in list(result['headlines'].items())[:3]:
        print(f"  {sym}:")
        for h in headlines[:3]:
            print(f"    - {h[:100]}")
