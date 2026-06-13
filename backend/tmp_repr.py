from app.agents.terraform_agent import escape_hcl_string

s = "${file('/etc/passwd')}"
expected = "$${file('/etc/passwd')}"
actual = escape_hcl_string(s)
print('INTERPOLATION')
print('expected repr:', repr(expected))
print('actual   repr:', repr(actual))
print('"${" in expected ->', "${" in expected)
print('"%{" in expected ->', "%{" in expected)

s2 = "%{if true}inject%{endif}"
expected2 = "%%{if true}inject%%{endif}"
actual2 = escape_hcl_string(s2)
print('\nDIRECTIVE')
print('expected repr:', repr(expected2))
print('actual   repr:', repr(actual2))
print('"${" in expected2 ->', "${" in expected2)
print('"%{" in expected2 ->', "%{" in expected2)
