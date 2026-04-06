# Muninn Container Layer
# Skills, Python deps, and path config for Claude Code on the Web

# Fetch skills
FETCH github:oaustegard/claude-skills /mnt/skills/user

# Python dependencies
RUN uv pip install --system httpx libsql-experimental

# Path config for remembering skill
RUN echo '/mnt/skills/user/remembering' > /usr/local/lib/python3.11/dist-packages/muninn-remembering.pth

# GitHub CLI — direct binary (not in default apt repos)
RUN GH_VER=$(curl -sL https://api.github.com/repos/cli/cli/releases/latest | python3 -c "import sys,json; print(json.load(sys.stdin)['tag_name'].lstrip('v'))") && curl -fsSL "https://github.com/cli/cli/releases/download/v${GH_VER}/gh_${GH_VER}_linux_amd64.tar.gz" | tar -xz --strip-components=2 -C /usr/local/bin "gh_${GH_VER}_linux_amd64/bin/gh"

# Noop setup script to suppress "No setup script configured" message
RUN touch /home/user/setup.sh && chmod +x /home/user/setup.sh

# Snapshot pip packages and config files
SNAPSHOT /usr/local/lib/python3.11/dist-packages
SNAPSHOT /home/user/setup.sh
SNAPSHOT /usr/local/bin/gh

WORKDIR /home/user
