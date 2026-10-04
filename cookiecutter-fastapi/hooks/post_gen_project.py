import subprocess

name = "{{ cookiecutter.service_name }}"

subprocess.run(["uv", "init", "--bare", "--name", name], check=True)
subprocess.run(["uv", "add", "fastapi[standard]"], check=True)
subprocess.run(["uv", "add", "--dev", "pytest", "httpx"], check=True)

# Same ruff config as the other services
with open("pyproject.toml", "a") as pyproject:
    pyproject.write('\n[tool.ruff]\nline-length = 100\n\n[tool.ruff.lint]\nselect = ["E", "F", "I", "UP", "B"]\n')
