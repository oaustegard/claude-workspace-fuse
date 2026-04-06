# Muninn Container Layer
# Skills, Python deps, and path config for Claude Code on the Web

# Fetch skills
FETCH github:oaustegard/claude-skills /mnt/skills/user

# Python dependencies
RUN uv pip install --system httpx libsql-experimental

# Path config for remembering skill
RUN echo '/mnt/skills/user/remembering' > /usr/local/lib/python3.11/dist-packages/muninn-remembering.pth

# Noop setup script to suppress "No setup script configured" message
RUN touch /home/user/setup.sh && chmod +x /home/user/setup.sh

# Snapshot pip packages and config files
SNAPSHOT /usr/local/lib/python3.11/dist-packages
SNAPSHOT /home/user/setup.sh

WORKDIR /home/user
