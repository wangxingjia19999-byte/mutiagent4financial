import os
import sys
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from agent_pools.poe_config import setup_poe_env, resolve_poe_model

setup_poe_env()

# Import OpenAI Agents SDK
import nest_asyncio
nest_asyncio.apply()

# Add parent directory to path for local imports
parent_dir = Path(__file__).parent.parent
alpha_agent_pool_path = parent_dir / "alpha_agent_pool"
sys.path.append(str(alpha_agent_pool_path))

from local_agents import Agent, function_tool

# Import Qlib utilities
try:
    qlib_path = alpha_agent_pool_path / "qlib_local"
    if not qlib_path.exists():
        qlib_path = alpha_agent_pool_path / "qlib"
    sys.path.insert(0, str(qlib_path))
    from utils import QlibConfig, DataProcessor
    from data_interfaces import FactorInput
    from standard_factor_calculator import StandardFactorCalculator
except ImportError as e:
    print(f"Warning: Qlib modules not found: {e}. Some features may be limited.")
    from dataclasses import dataclass, field
    from typing import List
    
    @dataclass
    class QlibConfig:
        provider_uri: str = ""
        instruments: List[str] = field(default_factory=list)
    
    class DataProcessor:
        def __init__(self, config):
            self.config = config
        def add_returns(self, data):
            return data
        def create_technical_features(self, data):
            return data
    
    @dataclass
    class FactorInput:
        factor_name: str = ""
        factor_type: str = ""
        calculation_method: str = ""
        expression: str = None
        function_name: str = None
        lookback_period: int = 20
    
    class StandardFactorCalculator:
        def calculate(self, data, factor_input):
            return pd.Series(dtype=float)

# Import ML libraries
try:
    from sklearn.linear_model import LinearRegression
    from sklearn.ensemble import RandomForestRegressor
    import lightgbm as lgb
    from sklearn.preprocessing import StandardScaler
    from sklearn.model_selection import train_test_split
except ImportError:
    print("Warning: ML libraries not found. Install sklearn and lightgbm for full functionality.")


# ==============================
# Internal Implementation (Pure Logic)
# ==============================

def _calculate_technical_indicators(data: pd.DataFrame, indicators: List[str]) -> Dict[str, Any]:
    """Internal technical indicator calculation."""
    try:
        # Identify price columns
        close_col = None
        for col in ['$close', 'close', 'Close']:
            if col in data.columns:
                close_col = col
                break
        if close_col is None:
            return {"status": "error", "message": "No close price column found"}
        
        results = {}
        
        if 'RSI' in indicators:
            delta = data[close_col].diff()
            gain = delta.where(delta > 0, 0).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / (loss + 1e-10)
            results['RSI'] = (100 - (100 / (1 + rs))).to_dict()
            
        if 'MACD' in indicators:
            ema_fast = data[close_col].ewm(span=12).mean()
            ema_slow = data[close_col].ewm(span=26).mean()
            macd = ema_fast - ema_slow
            results['MACD'] = macd.to_dict()
            
        if 'Bollinger' in indicators:
            ma = data[close_col].rolling(window=20).mean()
            std = data[close_col].rolling(window=20).std()
            results['Bollinger_upper'] = (ma + 2*std).to_dict()
            results['Bollinger_lower'] = (ma - 2*std).to_dict()
            
        return {"status": "success", "indicators": results}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def _prepare_features_targets(
    data: pd.DataFrame,
    indicators: Optional[List[str]] = None,
    use_alpha158: bool = True,
) -> Tuple[pd.DataFrame, Optional[pd.Series]]:
    """
    Calculate features and targets from raw data.

    Two modes:
      - Alpha158 (default): 200+ factors via Alpha158Calculator (pure pandas, no Qlib)
      - Legacy: RSI/MACD/Bollinger technical indicators (if use_alpha158=False)

    Features are winsorized at 1%/99% and standardized (z-score) for stable model training.
    """
    # 1. Preprocessing
    if isinstance(data.index, pd.MultiIndex):
        data = data.reset_index()
    data = data.reset_index(drop=True)

    # Normalize columns
    col_map = {c: c.lower() for c in data.columns}
    data = data.rename(columns=col_map)
    if 'instrument' in data.columns:
        data = data.rename(columns={'instrument': 'symbol'})
    if 'datetime' in data.columns:
        data = data.rename(columns={'datetime': 'date'})

    if 'close' not in data.columns:
        raise ValueError("Missing close column")

    # Check for required columns for Alpha158
    has_ohlcv = all(c in data.columns for c in ['open', 'high', 'low', 'close', 'volume'])

    if use_alpha158 and has_ohlcv:
        features = _prepare_alpha158_features(data)
    else:
        if use_alpha158:
            print("WARNING: Missing OHLCV columns for Alpha158, falling back to legacy indicators.")
        # Legacy: RSI/MACD/Bollinger
        ind_res = _calculate_technical_indicators(data, indicators or ['RSI', 'MACD'])
        features = pd.DataFrame(index=data.index)
        if ind_res['status'] == 'success':
            for name, vals in ind_res['indicators'].items():
                features[name] = pd.Series(vals)
        else:
            raise ValueError(f"Indicator calc failed: {ind_res.get('message')}")

    # 2b. Feature preprocessing: winsorize + standardize
    features = _preprocess_features(features)

    # 3. Target (Forward Return)
    if 'symbol' in data.columns:
        targets = data.groupby('symbol')['close'].pct_change().shift(-1)
    else:
        targets = data['close'].pct_change().shift(-1)

    return features, targets


def _prepare_alpha158_features(data: pd.DataFrame) -> pd.DataFrame:
    """Compute Alpha158 factors (200+ features) via pure-pandas calculator."""
    from agent_pools.alpha_agent_demo.alpha158_calculator import Alpha158Calculator
    calc = Alpha158Calculator()
    features = calc.compute(data)
    return features


def _preprocess_features(features: pd.DataFrame) -> pd.DataFrame:
    """
    Winsorize (clip at 1%/99%) + standardize (z-score) for stable model training.
    Keeps a copy of original column names.
    """
    df = features.copy()
    # Winsorize: clip extreme values
    for col in df.columns:
        lo = df[col].quantile(0.01)
        hi = df[col].quantile(0.99)
        if hi > lo:
            df[col] = df[col].clip(lo, hi)

    # Standardize: z-score
    for col in df.columns:
        mean = df[col].mean()
        std = df[col].std()
        if std > 1e-8:
            df[col] = (df[col] - mean) / std

    # Replace any remaining NaN/Inf
    df = df.fillna(0.0).replace([np.inf, -np.inf], 0.0)

    return df.astype(np.float32)


def _select_top_features(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_test: pd.DataFrame,
    top_k: int = 60,
) -> tuple:
    """
    Select top-k most important features using a quick LightGBM fit.

    Returns (X_train_selected, X_test_selected, selected_count).
    Falls back to returning all features if LightGBM is unavailable.
    """
    if len(X_train.columns) <= top_k:
        return X_train, X_test, len(X_train.columns)

    try:
        import lightgbm as lgb

        # Align and drop NaN
        aligned = pd.concat([X_train, y_train.rename('_target')], axis=1).dropna()
        if len(aligned) < 50:
            return X_train, X_test, len(X_train.columns)

        X = aligned.drop(columns=['_target'])
        y = aligned['_target']

        # Quick model for importance scoring
        model = lgb.LGBMRegressor(
            n_estimators=80, max_depth=5, num_leaves=31,
            learning_rate=0.1, subsample=0.8, colsample_bytree=0.8,
            random_state=42, verbose=-1, n_jobs=-1,
        )
        model.fit(X, y)

        # Get feature importances (gain-based)
        importances = pd.Series(model.feature_importances_, index=X.columns)
        importances = importances.sort_values(ascending=False)

        # Select top-k and log the top 5
        selected_cols = importances.head(top_k).index.tolist()
        top5 = importances.head(5)
        print(f"  Top features: {', '.join(f'{n}({v:.4f})' for n, v in top5.items())}")

        return X_train[selected_cols], X_test[selected_cols], len(selected_cols)

    except ImportError:
        return X_train, X_test, len(X_train.columns)
    except Exception as e:
        raise e


def _train_model_and_predict(
    X_train: pd.DataFrame, 
    y_train: pd.Series, 
    X_test: pd.DataFrame, 
    model_type: str
) -> Dict[str, Any]:
    """
    Train on X_train/y_train, Predict on X_test.
    NO LEAKAGE: Model sees only train data.
    """
    try:
        # Align Train Data
        train_aligned = pd.concat([X_train, y_train], axis=1).dropna()
        if len(train_aligned) < 10: # Allow small samples for demo
             # If train is empty, maybe fallback to random or error?
             pass
        
        if train_aligned.empty:
             return {"status": "error", "message": "Insufficient training data (after alignment/drop na)"}

        X_train_full = train_aligned.iloc[:, :-1]
        y_train_full = train_aligned.iloc[:, -1]

        # Validation holdout: last 20% of training data for early stopping
        n_val = max(int(len(X_train_full) * 0.2), 10)
        X_val, y_val = X_train_full.iloc[-n_val:], y_train_full.iloc[-n_val:]
        X_train_clean, y_train_clean = X_train_full.iloc[:-n_val], y_train_full.iloc[:-n_val]

        # Handle Test Data (fill NaNs in features with 0 or drop?)
        X_test_clean = X_test.fillna(0)

        preds_series = pd.Series(index=X_test.index, dtype=float)

        # ── Ensemble: blend LightGBM + RandomForest + Ridge for robustness ──
        if model_type == "ensemble":
            try:
                import lightgbm as lgb
                # LightGBM with early stopping on validation set
                lgbm_model = lgb.LGBMRegressor(
                    n_estimators=200, max_depth=6, num_leaves=31,
                    learning_rate=0.05, subsample=0.8, colsample_bytree=0.8,
                    random_state=42, verbose=-1, n_jobs=-1,
                )
                lgbm_model.fit(
                    X_train_clean, y_train_clean,
                    eval_set=[(X_val, y_val)],
                    eval_metric='l2',
                    callbacks=[lgb.early_stopping(20), lgb.log_evaluation(0)],
                )
                best_iter = lgbm_model.best_iteration_
                models = {
                    'lgbm': lgbm_model,
                    'rf': RandomForestRegressor(
                        n_estimators=100, max_depth=8, random_state=42, n_jobs=-1,
                    ),
                    'ridge': LinearRegression(),
                }
                all_preds = []
                for name, m in models.items():
                    if name != 'lgbm':  # already trained
                        m.fit(X_train_full, y_train_full)  # full train for non-LGBM
                    all_preds.append(m.predict(X_test_clean))
                preds = np.mean(all_preds, axis=0)
                preds_series.loc[X_test_clean.index] = preds
                return {
                    "status": "success",
                    "predictions": preds_series,  # keep as Series, avoid dict round-trip
                    "model_info": {
                        "type": "ensemble",
                        "members": list(models.keys()),
                        "lgbm_best_iter": best_iter,
                    },
                }
            except ImportError:
                print("WARNING: lightgbm not installed for ensemble, falling back to random_forest.")
                model = RandomForestRegressor(n_estimators=100, max_depth=8, random_state=42, n_jobs=-1)
                model.fit(X_train_clean, y_train_clean)
                preds = model.predict(X_test_clean)
                preds_series.loc[X_test_clean.index] = preds
                return {
                    "status": "success",
                    "predictions": preds_series,  # keep as Series, avoid dict round-trip
                    "model_info": {"type": "random_forest"},
                }

        model = None
        if model_type == "linear":
            model = LinearRegression()
        elif model_type == "random_forest":
            model = RandomForestRegressor(n_estimators=100, max_depth=8, random_state=42, n_jobs=-1)
        elif model_type == "lightgbm":
            try:
                import lightgbm as lgb
                model = lgb.LGBMRegressor(
                    n_estimators=100, max_depth=6, num_leaves=31,
                    learning_rate=0.05, subsample=0.8, colsample_bytree=0.8,
                    random_state=42, verbose=-1, n_jobs=-1,
                )
            except ImportError:
                print("WARNING: lightgbm not installed, falling back to random_forest.")
                model = RandomForestRegressor(n_estimators=100, max_depth=8, random_state=42, n_jobs=-1)
        else:
            return {"status": "error", "message": f"Unknown model {model_type}"}
            
        # FIT on TRAIN
        model.fit(X_train_clean, y_train_clean)
        
        # PREDICT on TEST
        preds = model.predict(X_test_clean)
        preds_series.loc[X_test_clean.index] = preds
        
        return {
            "status": "success",
            "predictions": preds_series,  # keep as Series, avoid dict round-trip
            "model_info": {"type": model_type}
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

def _run_alpha_pipeline_impl(
    test_data: pd.DataFrame,
    train_data: Optional[pd.DataFrame],
    factors: List[Dict],
    indicators: Optional[List[str]],
    model_type: str,
    signal_threshold: float,
    data_processor: Any
) -> Dict[str, Any]:
    """Full pipeline implementation (Macro) — uses Alpha158 factors by default."""
    try:
        # If no train data provided, fallback to In-Sample (Old behavior) or Error?
        # For backwards compatibility, if train_data is None, split test_data or use it as both (with warning)
        if train_data is None or train_data.empty:
            print("WARNING: No training data provided. Using In-Sample training (Leakage Risk).")
            train_data = test_data

        # 1. Prepare Features & Targets — Alpha158 by default
        use_alpha158 = (indicators is None)  # If no legacy indicators specified, use Alpha158
        try:
            X_train, y_train = _prepare_features_targets(
                train_data, indicators=indicators, use_alpha158=use_alpha158
            )
            X_test, _ = _prepare_features_targets(
                test_data, indicators=indicators, use_alpha158=use_alpha158
            )
        except Exception as e:
            return {"status": "error", "message": f"Feature Prep Failed: {str(e)}"}

        # 1b. Feature selection — pick top-N factors by LightGBM importance
        #      Reduces 203 factors → ~60 most predictive, filtering out noise.
        if use_alpha158 and len(X_train.columns) > 80:
            try:
                X_train, X_test, selected_count = _select_top_features(
                    X_train, y_train, X_test, top_k=60
                )
                print(f"DEBUG: Feature selection: {X_train.shape[1]} factors retained (from {X_train.shape[1] + len(set())} original)")
            except Exception as e:
                print(f"WARNING: Feature selection failed ({e}), using all {X_train.shape[1]} factors.")

        # 2. Train & Predict
        model_res = _train_model_and_predict(X_train, y_train, X_test, model_type)
        if model_res['status'] != 'success':
            return model_res

        # 3. Signals — cross-sectional ranking (continuous, no discretization)
        #    Standard quant approach: rank predictions within each date to remove
        #    market beta and focus on relative outperformance. Signal strength
        #    is the rank percentile (0=worst, 1=best), centered to [-0.5, 0.5].
        preds = model_res['predictions']
        if not isinstance(preds, pd.Series):
            preds = pd.Series(preds)  # backward compat with old .to_dict() format

        # Restore index to (date, symbol) for cross-sectional ranking
        data_norm = test_data.copy()
        if isinstance(data_norm.index, pd.MultiIndex):
            data_norm = data_norm.reset_index()
        col_map = {c: c.lower() for c in data_norm.columns}
        data_norm = data_norm.rename(columns=col_map)
        if 'instrument' in data_norm.columns:
            data_norm = data_norm.rename(columns={'instrument': 'symbol'})
        if 'datetime' in data_norm.columns:
            data_norm = data_norm.rename(columns={'datetime': 'date'})
        data_norm = data_norm.reset_index(drop=True)

        # Build a DataFrame with predictions + date for cross-sectional ranking
        preds.index = data_norm.index
        pred_df = pd.DataFrame({'prediction': preds})
        if 'date' in data_norm.columns:
            pred_df['date'] = data_norm['date'].values

        # Cross-sectional rank within each date (0=worst → 1=best)
        if 'date' in pred_df.columns and len(pred_df['date'].unique()) > 1:
            pred_df['signal'] = pred_df.groupby('date')['prediction'].rank(pct=True)
        else:
            # Single date or no date column — rank globally
            pred_df['signal'] = pred_df['prediction'].rank(pct=True)

        # Center around 0 for natural long/short split: [-0.5, 0.5]
        pred_df['signal'] = pred_df['signal'] - 0.5

        # Build MultiIndex output
        signals = pred_df['signal']
        signals.index = data_norm.index
        if 'date' in data_norm.columns and 'symbol' in data_norm.columns:
            signals.index = pd.MultiIndex.from_frame(data_norm[['date', 'symbol']])

            # ── Sector neutrality: remove sector-level biases from signals ──
            #     Groups signals by date, then within each date subtracts the
            #     sector-mean from each stock. This ensures we bet on stock-specific
            #     alpha rather than sector momentum (e.g., 'all tech looks good').
            try:
                from agent_pools.portfolio_agent_demo.portfolio_agent import apply_sector_neutrality
                neutralized = {}
                for dt, grp in signals.groupby(level=0):
                    # Convert to {symbol: signal} dict — use droplevel to avoid .get(s, 0) false zeros
                    day_signals = grp.droplevel(0).to_dict()
                    day_neut = apply_sector_neutrality(day_signals)
                    for sym, val in day_neut.items():
                        neutralized[(dt, sym)] = val
                if neutralized:
                    signals = pd.Series(neutralized)
                    signals.index = pd.MultiIndex.from_tuples(signals.index, names=['date', 'symbol'])
            except Exception as e:
                pass  # sector neutrality is best-effort; skip if it fails

        elif 'date' in data_norm.columns:
            signals.index = pd.Index(data_norm['date'])

        return {
            "status": "success",
            "signals": signals.to_dict(),
            "model_performance": model_res.get('model_info'),
            "signal_type": "cross_sectional_rank_sector_neutral",
            "signal_range": [-0.5, 0.5],
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": str(e)}


# ==============================
# Tool Definitions (Context-Aware)
# ==============================

@function_tool
def run_alpha_pipeline(ctx: dict) -> str:
    """
    Execute the complete standard alpha pipeline (Alpha158 Factors -> Train Model -> Generate Signals).
    Uses 200+ Alpha158 factors by default with LightGBM model.
    """
    print("DEBUG: 🛠️ run_alpha_pipeline (Macro) INVOKED")
    try:
        data = ctx.get('data')      # This is TEST data (current year)
        train_data = ctx.get('train_data') # This is TRAIN data (prev year)

        factors = ctx.get('factors', [])
        indicators = ctx.get('indicators', None)  # None → Alpha158 mode
        model_type = ctx.get('model_type', 'ensemble')
        threshold = ctx.get('signal_threshold', 0.0)
        data_processor = ctx.get('data_processor')

        if data is None: return "Error: No test data in context."

        result = _run_alpha_pipeline_impl(data, train_data, factors, indicators, model_type, threshold, data_processor)
        ctx['result'] = result
        return f"Pipeline completed. Status: {result.get('status')}"
    except Exception as e:
        return f"Error: {e}"

@function_tool
def calculate_indicators_tool(ctx: dict, indicators: List[str]) -> str:
    """
    Calculate specific technical indicators on the current data (Test Data).
    """
    print(f"DEBUG: 🛠️ calculate_indicators_tool INVOKED with {indicators}")
    try:
        data = ctx.get('data')
        if data is None: return "Error: No data in context."
        
        res = _calculate_technical_indicators(data, indicators)
        if res['status'] == 'success':
            # Store features in context
            if 'features' not in ctx:
                ctx['features'] = pd.DataFrame(index=data.index)
            
            features = ctx['features']
            for name, vals in res['indicators'].items():
                features[name] = pd.Series(vals)
            ctx['features'] = features
            return f"Calculated {len(res['indicators'])} indicators for Test Set."
        return f"Failed: {res.get('message')}"
    except Exception as e:
        return f"Error: {e}"

@function_tool
def train_predict_tool(ctx: dict, model_type: str = "lightgbm") -> str:
    """
    Train a model using TRAINING data and predict on CURRENT features.
    Requires 'train_data' in context.
    """
    print(f"DEBUG: 🛠️ train_predict_tool INVOKED with {model_type}")
    try:
        test_data = ctx.get('data')
        test_features = ctx.get('features')
        train_data = ctx.get('train_data')
        indicators = ctx.get('indicators', None)  # None → Alpha158 mode

        if test_features is None or test_features.empty:
            return "Error: Calculate indicators for test data first."

        if train_data is None or train_data.empty:
            return "Error: No training data provided for rolling window."

        # Prepare Train Features (Alpha158 by default)
        use_alpha158 = (indicators is None)
        try:
            X_train, y_train = _prepare_features_targets(
                train_data, indicators=indicators, use_alpha158=use_alpha158
            )
        except Exception as e:
            return f"Error preparing training data: {e}"
            
        # Train & Predict
        res = _train_model_and_predict(X_train, y_train, test_features, model_type)
        
        if res['status'] == 'success':
            ctx['raw_predictions'] = res['predictions']
            return "Model trained on historical data and predictions generated for current period."
        return f"Training failed: {res.get('message')}"
    except Exception as e:
        return f"Error: {e}"

@function_tool
def submit_signals_tool(ctx: dict, threshold: float = 0.0) -> str:
    """
    Convert predictions to trading signals and finalize the task.
    """
    print(f"DEBUG: 🛠️ submit_signals_tool INVOKED")
    try:
        preds_dict = ctx.get('raw_predictions')
        if not preds_dict: return "Error: No predictions found."
        
        data = ctx.get('data')
        preds = pd.Series(preds_dict)
        
        signals = preds.apply(lambda x: 1.0 if x > threshold else (-1.0 if x < -threshold else 0.0))
        
        # Format index
        if 'date' in data.columns and 'symbol' in data.columns:
            # Re-normalize if needed
            # Assuming data hasn't changed order since indicator calc
            # Ideally we use index alignment but data usually has RangeIndex or original
            # We trust the order matches if preds_dict came from same process
            pass
        
        # Robust Index Alignment
        # If preds index is integer (from reset_index), we map it back?
        # Or we just trust that 'data' is the source of truth
        
        # Simple approach:
        signals.index = data.index # Align with original data index if preserved
        
        # If data columns need normalizing to find date/symbol
        data_copy = data.copy()
        if isinstance(data_copy.index, pd.MultiIndex): data_copy = data_copy.reset_index()
        data_copy.columns = [str(c).lower() for c in data_copy.columns]
        if 'datetime' in data_copy.columns: data_copy = data_copy.rename(columns={'datetime': 'date'})
        if 'instrument' in data_copy.columns: data_copy = data_copy.rename(columns={'instrument': 'symbol'})
        
        if 'date' in data_copy.columns and 'symbol' in data_copy.columns:
             signals.index = pd.MultiIndex.from_frame(data_copy[['date', 'symbol']])
        elif 'date' in data_copy.columns:
             signals.index = pd.Index(data_copy['date'])
            
        ctx['result'] = {
            "status": "success",
            "signals": signals.to_dict()
        }
        return "Signals generated and submitted. Task complete."
    except Exception as e:
        return f"Error: {e}"


# ==============================
# Alpha Signal Agent
# ==============================

class AlphaSignalAgent:
    def __init__(
        self,
        name: str = "AlphaSignalAgent",
        model: str = resolve_poe_model("openai/gpt-4o-mini"),
        qlib_config: Optional[QlibConfig] = None
    ):
        self.name = name
        self.model = model
        self.qlib_config = qlib_config or QlibConfig()
        self.data_processor = DataProcessor(self.qlib_config)
        
        # Register context-aware tools
        self.tools = [
            run_alpha_pipeline,          # Macro tool (easy mode)
            calculate_indicators_tool,   # Granular tool
            train_predict_tool,          # Granular tool
            submit_signals_tool          # Granular tool
        ]
        
        self.agent = Agent(
            name=name,
            instructions="""
            You are an Alpha Signal Agent. Generate trading signals using Alpha158 factors (200+ features)
            with LightGBM model.

            CRITICAL RULES:
            1. Call 'run_alpha_pipeline' EXACTLY ONCE. This computes everything automatically.
            2. After run_alpha_pipeline returns, you are DONE. Do NOT call it again.
            3. Do NOT use calculate_indicators_tool or train_predict_tool unless run_alpha_pipeline fails.
            4. Respond with ONLY the word "DONE" after a successful pipeline run.
            """,
            model=model,
            tools=self.tools
        )
    
    def run(self, user_request: str, context: Optional[Dict[str, Any]] = None) -> str:
        return self.agent.run(user_request, context=context, max_turns=10)
    
    def generate_signals_from_data(
        self,
        data: pd.DataFrame,
        factors: Optional[List[Dict[str, Any]]] = None,
        indicators: Optional[List[str]] = None,
        model_type: str = "ensemble",
        signal_threshold: float = 0.0,
        train_data: Optional[pd.DataFrame] = None
    ) -> Dict[str, Any]:
        """
        Generate alpha signals using Alpha158 factors (200+) + ML model.

        Runs the pipeline directly — no LLM round-trip needed. The pipeline is
        fully deterministic: compute factors → preprocess → train model → predict.

        Falls back to legacy RSI/MACD/Bollinger if indicators are explicitly specified.
        """
        use_alpha158 = (indicators is None)
        feature_label = "Alpha158" if use_alpha158 else "legacy"
        print(f"DEBUG: 🤖 Alpha Agent running pipeline directly... (features: {feature_label}, model: {model_type})")

        return _run_alpha_pipeline_impl(
            test_data=data,
            train_data=train_data,
            factors=factors or [],
            indicators=indicators,
            model_type=model_type,
            signal_threshold=signal_threshold,
            data_processor=self.data_processor,
        )

if __name__ == "__main__":
    print("Alpha Signal Agent Initialized")
