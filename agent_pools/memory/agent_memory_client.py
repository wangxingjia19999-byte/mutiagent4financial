"""
Agent Memory Client - Synchronous Neo4j memory client for trading agents.

Provides store_reflection / retrieve_lessons / store_memory / retrieve_memory
using the memory module's TradingGraphMemory schema. Agents import this directly
without needing the MCP server running.
"""

import os
import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
dotenv_path = os.path.join(project_root, '.env')
load_dotenv(dotenv_path=dotenv_path)

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "finagent123")


def _run_async(coro):
    """Helper to run async code from sync context."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import nest_asyncio
            nest_asyncio.apply()
            return loop.run_until_complete(coro)
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


class AgentMemoryClient:
    """
    Synchronous memory client for trading agents.
    Wraps the memory module's TradingGraphMemory for direct Neo4j access.
    """

    def __init__(self, uri=None, user=None, password=None):
        self.uri = uri or NEO4J_URI
        self.user = user or NEO4J_USER
        self.password = password or NEO4J_PASSWORD
        self._db = None

    def _get_db(self):
        if self._db is None:
            from agent_pools.memory.database import TradingGraphMemory
            self._db = TradingGraphMemory(self.uri, self.user, self.password)
        return self._db

    def close(self):
        if self._db:
            _run_async(self._db.close())
            self._db = None

    # ── Reflection API (mirrors old knowledge/neo4j_memory.py) ──────────

    def store_reflection(self, agent_name: str, strategy_name: str,
                         issue: str, lesson_learned: str) -> str:
        """Store a learned lesson into Neo4j long-term memory."""
        db = self._get_db()
        if not db or not db.driver:
            return "Neo4j is not connected."

        summary = f"[{agent_name}] {strategy_name}: {lesson_learned}"
        keywords = [agent_name, strategy_name] + issue.split()
        try:
            result = _run_async(db.store_memory(
                query=f"Reflection: {issue}",
                keywords=keywords,
                summary=summary,
                agent_id=agent_name,
                event_type="AGENT_ACTION",
                log_level="INFO",
            ))
            return f"Successfully stored reflection for {strategy_name} by {agent_name}."
        except Exception as e:
            return f"Memory store failed: {e}"

    def retrieve_lessons_by_issue(self, keyword: str) -> List[str]:
        """Retrieve past lessons matching a keyword."""
        db = self._get_db()
        if not db or not db.driver:
            return ["Neo4j is not connected."]

        try:
            results = _run_async(db.retrieve_memory(keyword, limit=5))
            if not results:
                return []
            lessons = []
            for r in results:
                mem = r.get('memory', {})
                meta = mem.get('metadata', {})
                lessons.append(
                    f"[{meta.get('timestamp', 'unknown')}] {meta.get('agent_id', 'unknown')} "
                    f"Summary: '{mem.get('summary', '')}'"
                )
            return lessons
        except Exception as e:
            return [f"Memory query failed: {e}"]

    # ── General memory API ──────────────────────────────────────────────

    def store_memory(self, query: str, keywords: List[str], summary: str,
                     agent_id: str, event_type: str = "USER_QUERY",
                     log_level: str = "INFO", session_id: str = None,
                     correlation_id: str = None) -> Optional[Dict]:
        """Store a general memory entry."""
        db = self._get_db()
        if not db or not db.driver:
            return None
        return _run_async(db.store_memory(
            query=query, keywords=keywords, summary=summary,
            agent_id=agent_id, event_type=event_type, log_level=log_level,
            session_id=session_id, correlation_id=correlation_id,
        ))

    def retrieve_memory(self, search_query: str, limit: int = 5) -> List[Dict]:
        """Retrieve memories by full-text search."""
        db = self._get_db()
        if not db or not db.driver:
            return []
        return _run_async(db.retrieve_memory(search_query, limit))

    def retrieve_with_expansion(self, search_query: str, limit: int = 10) -> List[Dict]:
        """Retrieve memories with relationship expansion."""
        db = self._get_db()
        if not db or not db.driver:
            return []
        return _run_async(db.retrieve_memory_with_expansion(search_query, limit))

    def filter_memories(self, filters: Dict, limit: int = 100, offset: int = 0) -> List[Dict]:
        """Filter memories by structured criteria."""
        db = self._get_db()
        if not db or not db.driver:
            return []
        return _run_async(db.filter_memories(filters, limit, offset))

    def get_statistics(self) -> Dict:
        """Get memory graph statistics."""
        db = self._get_db()
        if not db or not db.driver:
            return {}
        return _run_async(db.get_statistics())
