"""
Agent Memory Client - Synchronous Neo4j memory client for trading agents.

Provides store_reflection / retrieve_lessons / store_memory / retrieve_memory
using the memory module's TradingGraphMemory schema. Agents import this directly
without needing the MCP server running.
"""

import os
from datetime import datetime
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
dotenv_path = os.path.join(project_root, '.env')
load_dotenv(dotenv_path=dotenv_path)

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "finagent123")


class AgentMemoryClient:
    """
    Synchronous memory client for trading agents.
    Uses direct synchronous Neo4j driver to avoid async lock issues.
    """

    def __init__(self, uri=None, user=None, password=None):
        self.uri = uri or NEO4J_URI
        self.user = user or NEO4J_USER
        self.password = password or NEO4J_PASSWORD
        self._driver = None

    def _get_driver(self):
        if self._driver is None:
            from neo4j import GraphDatabase
            try:
                self._driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
                self._driver.verify_connectivity()
                # Ensure indexes exist
                with self._driver.session() as s:
                    s.run("CREATE INDEX memory_agent_id IF NOT EXISTS FOR (m:Memory) ON (m.agent_id)")
                    s.run("CREATE INDEX memory_timestamp IF NOT EXISTS FOR (m:Memory) ON (m.timestamp)")
            except Exception as e:
                print(f"  [Memory] Neo4j connect failed: {e}")
                self._driver = None
        return self._driver

    def close(self):
        if self._driver:
            self._driver.close()
            self._driver = None

    # ── Reflection API ──────────────────────────────────────────────

    def store_reflection(self, agent_name: str, strategy_name: str,
                         issue: str, lesson_learned: str) -> str:
        """Store a learned lesson into Neo4j long-term memory."""
        driver = self._get_driver()
        if not driver:
            return "Neo4j is not connected."

        import uuid
        memory_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()
        summary = f"[{agent_name}] {strategy_name}: {lesson_learned}"
        keywords = [agent_name, strategy_name] + issue.split()

        try:
            with driver.session() as session:
                session.run("""
                    CREATE (m:Memory {
                        memory_id: $memory_id, timestamp: $timestamp,
                        search_query: $search_query, keywords: $keywords, summary: $summary,
                        agent_id: $agent_id, event_type: $event_type,
                        log_level: $log_level, lookup_count: 0
                    })
                """, parameters={
                    "memory_id": memory_id, "timestamp": timestamp,
                    "search_query": f"Reflection: {issue}", "keywords": keywords,
                    "summary": summary, "agent_id": agent_name,
                    "event_type": "AGENT_ACTION", "log_level": "INFO",
                })
            return f"Stored: {summary[:100]}..."
        except Exception as e:
            return f"Memory store failed: {e}"

    def retrieve_lessons_by_issue(self, keyword: str) -> List[str]:
        """Retrieve past lessons matching a keyword."""
        driver = self._get_driver()
        if not driver:
            return []

        try:
            with driver.session() as session:
                result = session.run("""
                    MATCH (m:Memory)
                    WHERE toLower(m.summary) CONTAINS toLower($kw)
                       OR any(k IN m.keywords WHERE toLower(k) CONTAINS toLower($kw))
                    RETURN m.summary as summary, m.timestamp as ts, m.agent_id as agent
                    ORDER BY m.timestamp DESC LIMIT 5
                """, parameters={"kw": keyword})
                records = list(result)
                if not records:
                    return []
                return [
                    f"[{r['ts'][:10]}] {r['agent']}: {r['summary'][:150]}"
                    for r in records
                ]
        except Exception as e:
            return [f"Query failed: {e}"]

    # ── General memory API (delegates to sync driver) ──────────────────

    def store_memory(self, query: str, keywords: List[str], summary: str,
                     agent_id: str, event_type: str = "USER_QUERY",
                     log_level: str = "INFO", session_id: str = None,
                     correlation_id: str = None) -> Optional[Dict]:
        """Store a general memory entry (delegates to store_reflection)."""
        result = self.store_reflection(agent_id, "general", query, summary)
        return {"status": "stored", "message": result} if "Stored" in result else None

    def retrieve_memory(self, search_query: str, limit: int = 5) -> List[Dict]:
        """Retrieve memories by keyword search."""
        lessons = self.retrieve_lessons_by_issue(search_query)
        return [{"memory": {"summary": l}} for l in lessons if not l.startswith("Query failed")]

    def retrieve_with_expansion(self, search_query: str, limit: int = 10) -> List[Dict]:
        """Retrieve memories with relationship expansion (same as retrieve_memory)."""
        return self.retrieve_memory(search_query, limit)

    def filter_memories(self, filters: Dict, limit: int = 100, offset: int = 0) -> List[Dict]:
        """Filter memories by structured criteria."""
        keyword = filters.get('keyword', filters.get('agent_id', ''))
        return self.retrieve_memory(keyword, limit) if keyword else []

    def get_statistics(self) -> Dict:
        """Get memory graph statistics."""
        driver = self._get_driver()
        if not driver:
            return {}
        try:
            with driver.session() as s:
                r = s.run('MATCH (m:Memory) RETURN count(m) as cnt')
                return {"total_memories": r.single()["cnt"]}
        except Exception:
            return {"total_memories": 0}
