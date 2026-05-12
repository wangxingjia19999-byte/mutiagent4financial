import os
from neo4j import GraphDatabase
from datetime import datetime

class Neo4jMemoryClient:
    """
    Neo4j Client for Agent Long-term Memory and Reflections.
    """
    def __init__(self, uri=None, user=None, password=None):
        self.uri = uri or os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.user = user or os.getenv("NEO4J_USER", "neo4j")
        self.password = password or os.getenv("NEO4J_PASSWORD", "password")
        
        try:
            self.driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
        except Exception as e:
            print(f"Warning: Could not connect to Neo4j. {e}")
            self.driver = None

    def close(self):
        if self.driver:
            self.driver.close()

    def store_reflection(self, agent_name: str, strategy_name: str, issue: str, lesson_learned: str):
        """
        Store a reflection from an agent about a strategy failure or issue.
        Creates nodes for Agent, Strategy, Issue, and connects them with the Lesson.
        """
        if not self.driver:
            return "Neo4j is not connected."

        query = """
        MERGE (a:Agent {name: $agent_name})
        MERGE (s:Strategy {name: $strategy_name})
        MERGE (i:Issue {description: $issue})
        MERGE (l:Lesson {content: $lesson_learned, timestamp: $timestamp})
        
        MERGE (a)-[:PROPOSED]->(s)
        MERGE (s)-[:ENCOUNTERED]->(i)
        MERGE (a)-[:LEARNED]->(l)
        MERGE (l)-[:RESOLVES]->(i)
        
        RETURN l
        """
        with self.driver.session() as session:
            session.run(query, 
                        agent_name=agent_name, 
                        strategy_name=strategy_name, 
                        issue=issue, 
                        lesson_learned=lesson_learned,
                        timestamp=datetime.now().isoformat())
            return f"Successfully stored reflection for {strategy_name} by {agent_name}."

    def retrieve_lessons_by_issue(self, keyword: str):
        """
        Retrieve past lessons when encountering a similar issue (e.g., 'overfitting').
        """
        if not self.driver:
            return "Neo4j is not connected."

        query = """
        MATCH (i:Issue)<-[:RESOLVES]-(l:Lesson)<-[:LEARNED]-(a:Agent)
        WHERE i.description CONTAINS $keyword OR l.content CONTAINS $keyword
        RETURN a.name AS agent, i.description AS issue, l.content AS lesson, l.timestamp AS time
        ORDER BY l.timestamp DESC LIMIT 5
        """
        results = []
        with self.driver.session() as session:
            records = session.run(query, keyword=keyword)
            for record in records:
                results.append(
                    f"[{record['time']}] {record['agent']} encountered issue: '{record['issue']}'. "
                    f"Lesson learned: '{record['lesson']}'"
                )
        return results

