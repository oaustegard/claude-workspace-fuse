# Test Container Layer
# Validates: FETCH from GitHub, pip install, path config

# Fetch skills
FETCH github:oaustegard/claude-skills /mnt/skills/user

# Install a test package
RUN uv pip install --system httpx

# Path config for remembering skill
RUN echo '/mnt/skills/user/remembering' > /usr/local/lib/python3.11/dist-packages/muninn-remembering.pth

# Snapshot all pip-installed packages (httpx + deps) and the .pth file
SNAPSHOT /usr/local/lib/python3.11/dist-packages

WORKDIR /home/user
