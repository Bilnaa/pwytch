import subprocess

name = "{{ cookiecutter.service_name }}"

subprocess.run(["uv", "init", "--bare", "--name", name], check=True)
subprocess.run(["uv", "add", "fastapi[standard]"], check=True)
subprocess.run(["uv", "add", "--dev", "pytest", "httpx"], check=True)
