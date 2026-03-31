from pathlib import Path
import sys

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from lianghua_agents.config import AgentSettings
from lianghua_agents.rag_indexer import build_or_update_rag_index


def main() -> None:
    load_dotenv()
    settings = AgentSettings.from_env()

    rebuilt = build_or_update_rag_index(settings=settings, force_rebuild=False)
    if rebuilt:
        print("RAG 索引已构建/更新完成。")
    else:
        print("知识库无变化，跳过重建。")


if __name__ == "__main__":
    main()
