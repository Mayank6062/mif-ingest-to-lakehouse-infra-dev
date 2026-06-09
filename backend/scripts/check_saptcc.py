import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.agents.knowledge_agent import KnowledgeAgent

print(json.dumps(KnowledgeAgent().check_source_system('saptcc'), indent=2))
