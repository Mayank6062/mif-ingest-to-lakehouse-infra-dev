from unittest.mock import MagicMock
from app.graph.nodes.validate_terraform import validate_terraform_node
state = {
    'source_system': 'test',
    'job_key': 'test-job',
    'locals_tf_full': 'locals { env = "dev" }',
    'glue_tf_content': 'resource "aws_glue_job" "test" {}',
    'current_step': 'collect_topic',
    'messages': [],
}
import app.graph.nodes.validate_terraform as v
v.TerraformValidator.validate = MagicMock(return_value={'status':'passed','logs':'\u2713 All validations passed','errors':'','failed_command':None})
res = validate_terraform_node(state)
import json
print(json.dumps(res, indent=2))
