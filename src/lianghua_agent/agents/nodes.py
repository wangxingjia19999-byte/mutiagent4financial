from lianghua_agent.agents.state import AgentGraphState
from lianghua_agent.models.schema import (
    ConflictResolution,
    FinalDecisionResult,
    NewsAnalysisResult,
    TechnicalAnalysisResult,
)
from lianghua_agent.tools.alpha101_rag import retrieve_alpha101_factors


def technical_node(state: AgentGraphState) -> AgentGraphState:
    input_state = state["input_state"]
    candles = input_state.candles
    indicators = input_state.indicators

    if not candles:
        return {
            "technical": TechnicalAnalysisResult(
                success=False,
                message="No candle data provided",
                signal="watch",
                confidence=0.0,
                reason_codes=["missing_candles"],
            )
        }

    trend = _analyze_trend(candles, indicators)
    key_levels = _detect_key_levels(candles)
    confidence = _score_technical_confidence(candles, indicators)
    factor_matches = _retrieve_factor_matches(input_state.symbol, input_state.timeframe, trend, indicators)

    signal = "watch"
    if trend == "bullish":
        signal = "buy"
    elif trend == "bearish":
        signal = "sell"

    reason_codes = [f"trend_{trend}"]
    factor_refs = [item["alpha_id"] for item in factor_matches]
    factor_formulas = [item["formula"] for item in factor_matches]
    if factor_refs:
        reason_codes.extend([f"factor_{factor_ref.lower()}" for factor_ref in factor_refs[:3]])

    return {
        "technical": TechnicalAnalysisResult(
            success=True,
            message="Technical analysis completed",
            trend=trend,
            signal=signal,
            key_levels=key_levels,
            confidence=confidence,
            factor_refs=factor_refs,
            factor_formulas=factor_formulas,
            reason_codes=reason_codes,
        )
    }


def _retrieve_factor_matches(symbol: str, timeframe: str, trend: str, indicators: dict) -> list[dict]:
    indicator_terms = " ".join(sorted(indicators.keys()))
    query = f"{symbol} {timeframe} trend {trend} close open high low volume vwap {indicator_terms}"
    return retrieve_alpha101_factors(query)


def news_node(state: AgentGraphState) -> AgentGraphState:
    input_state = state["input_state"]
    news_items = input_state.news_items

    if not news_items:
        return {
            "news": NewsAnalysisResult(
                success=True,
                message="No news data provided",
                sentiment="neutral",
                signal="watch",
                confidence=0.2,
                reason_codes=["missing_news"],
            )
        }

    event_tags = _classify_events(news_items)
    sentiment = _analyze_sentiment(news_items)
    impact_horizon = _estimate_impact_horizon(event_tags)
    confidence = _score_news_confidence(news_items)

    signal = "watch"
    if sentiment == "positive":
        signal = "buy"
    elif sentiment == "negative":
        signal = "sell"

    return {
        "news": NewsAnalysisResult(
            success=True,
            message="News analysis completed",
            sentiment=sentiment,
            signal=signal,
            event_tags=event_tags,
            impact_horizon=impact_horizon,
            confidence=confidence,
            reason_codes=[f"sentiment_{sentiment}"],
        )
    }


def synthesis_node(state: AgentGraphState) -> AgentGraphState:
    input_state = state["input_state"]
    technical = state["technical"]
    news = state["news"]

    conflict = _resolve_conflict(technical, news)
    action, confidence = _fuse_signals(technical, news, conflict)
    recommendation = _build_recommendation(action, confidence, input_state.risk_profile)

    return {
        "final_decision": FinalDecisionResult(
            success=True,
            message="Synthesis completed",
            action=action,
            confidence=confidence,
            reason_codes=[
                f"technical_{technical.signal}",
                f"news_{news.signal}",
                f"conflict_{str(conflict.has_conflict).lower()}",
            ],
            risk_warnings=recommendation["risk_warnings"],
            position_hint=recommendation["position_hint"],
            ttl=recommendation["ttl"],
            summary=recommendation["summary"],
            conflict_info=conflict,
        )
    }


def _analyze_trend(candles: list[dict], indicators: dict) -> str:
    if len(candles) < 2:
        return "sideways"

    latest_close = float(candles[-1].get("close", 0))
    prev_close = float(candles[-2].get("close", latest_close))

    ma_short = indicators.get("ma_short")
    ma_long = indicators.get("ma_long")
    if ma_short is not None and ma_long is not None:
        if ma_short > ma_long:
            return "bullish"
        if ma_short < ma_long:
            return "bearish"

    if latest_close > prev_close:
        return "bullish"
    if latest_close < prev_close:
        return "bearish"
    return "sideways"


def _detect_key_levels(candles: list[dict]) -> list[float]:
    window = candles[-20:] if len(candles) >= 20 else candles
    highs = [float(item.get("high", 0)) for item in window]
    lows = [float(item.get("low", 0)) for item in window]
    if not highs or not lows:
        return []
    return [min(lows), max(highs)]


def _score_technical_confidence(candles: list[dict], indicators: dict) -> float:
    if len(candles) < 2:
        return 0.3

    latest_close = float(candles[-1].get("close", 0))
    prev_close = float(candles[-2].get("close", latest_close))
    move_strength = abs(latest_close - prev_close) / (prev_close + 1e-9)

    bonus = 0.0
    if indicators.get("ma_short") is not None and indicators.get("ma_long") is not None:
        bonus += 0.2

    score = 0.4 + min(move_strength * 10, 0.4) + bonus
    return round(max(0.0, min(score, 1.0)), 2)


def _classify_events(news_items: list[dict]) -> list[str]:
    tags: set[str] = set()
    keywords = {
        "earnings": "财报",
        "policy": "政策",
        "rate": "利率",
        "upgrade": "上调",
        "downgrade": "下调",
        "geopolitics": "地缘",
    }

    for item in news_items:
        text = f"{item.get('title', '')} {item.get('content', '')}".lower()
        for tag, key in keywords.items():
            if key in text or tag in text:
                tags.add(tag)

    if not tags:
        tags.add("general")
    return sorted(tags)


def _analyze_sentiment(news_items: list[dict]) -> str:
    score = 0
    positive_words = ["上涨", "增长", "利好", "上调", "突破", "beat"]
    negative_words = ["下跌", "衰退", "利空", "下调", "风险", "miss"]

    for item in news_items:
        text = f"{item.get('title', '')} {item.get('content', '')}".lower()
        score += sum(1 for word in positive_words if word in text)
        score -= sum(1 for word in negative_words if word in text)

    if score > 0:
        return "positive"
    if score < 0:
        return "negative"
    return "neutral"


def _estimate_impact_horizon(event_tags: list[str]) -> str:
    if "policy" in event_tags or "rate" in event_tags:
        return "mid"
    if "earnings" in event_tags:
        return "short"
    return "short"


def _score_news_confidence(news_items: list[dict]) -> float:
    count = len(news_items)
    if count == 0:
        return 0.2
    score = 0.35 + min(count * 0.1, 0.45)
    return round(max(0.0, min(score, 1.0)), 2)


def _resolve_conflict(
    technical: TechnicalAnalysisResult,
    news: NewsAnalysisResult,
) -> ConflictResolution:
    if technical.signal == news.signal:
        return ConflictResolution(has_conflict=False, strategy="align", notes="signals aligned")

    if "watch" in [technical.signal, news.signal]:
        return ConflictResolution(has_conflict=False, strategy="conservative", notes="one side neutral")

    return ConflictResolution(has_conflict=True, strategy="de_risk", notes="direction conflict")


def _fuse_signals(
    technical: TechnicalAnalysisResult,
    news: NewsAnalysisResult,
    conflict: ConflictResolution,
) -> tuple[str, float]:
    tech_weight = 0.6
    news_weight = 0.4

    mapping = {"buy": 1, "sell": -1, "hold": 0, "watch": 0}
    score = (
        mapping[technical.signal] * technical.confidence * tech_weight
        + mapping[news.signal] * news.confidence * news_weight
    )

    if conflict.has_conflict:
        score *= 0.5

    if score > 0.2:
        return "buy", round(min(abs(score), 1.0), 2)
    if score < -0.2:
        return "sell", round(min(abs(score), 1.0), 2)
    if abs(score) <= 0.05:
        return "watch", round(1 - min(abs(score), 1.0), 2)
    return "hold", round(1 - min(abs(score), 1.0), 2)


def _build_recommendation(action: str, confidence: float, risk_profile: str) -> dict:
    risk_warnings: list[str] = []
    position_hint = "no_position"
    ttl = "1d"

    if action in ["buy", "sell"]:
        if risk_profile == "conservative":
            position_hint = "small"
            risk_warnings.append("conservative_profile_limit_position")
        elif risk_profile == "aggressive":
            position_hint = "medium"
        else:
            position_hint = "small_to_medium"

    if confidence < 0.45:
        risk_warnings.append("low_confidence")

    summary = f"Action={action}, confidence={confidence}, risk_profile={risk_profile}"
    return {
        "risk_warnings": risk_warnings,
        "position_hint": position_hint,
        "ttl": ttl,
        "summary": summary,
    }
