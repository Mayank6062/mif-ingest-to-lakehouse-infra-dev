import json
from app.agents.validation_agent import ValidationAgent

agent = ValidationAgent()
for test in ["", "emea", 'apac"\ninjected', 'invalid-region']:
    results = agent.validate_all({"subgroup": test})
    sgr = next((r for r in results if r["rule_id"] == "SGR-001"), None)
    print('input:', repr(test))
    print('SGR result:', json.dumps(sgr, indent=2))
    print('has_failures:', agent.has_failures(results))
    print('---')
