# Olympus Discord Bot

Olympus is a multipurpose Discord bot with tools for server moderation, security, music, community management, games, and AI-powered features.

[Invite Olympus](https://discord.com/oauth2/authorize?client_id=1144179659735572640&permissions=2113268958&scope=bot) · [Support server](https://discord.gg/odx)

## Features

- **Server protection:** antinuke, automoderation, and moderation tools.
- **Community tools:** welcome messages, giveaways, role utilities, and server management.
- **Entertainment:** music, games, voice utilities, and fun commands.
- **AI tools:** chat and image-generation features.
- **Tournament tools:** tournament commands and related functionality.

Features and integrations may require additional configuration or external services.

## Run your own instance

### Requirements

- Python
- Git
- A Discord application and bot token from the [Discord Developer Portal](https://discord.com/developers/applications)

### Installation

```bash
git clone https://github.com/harshkolte01/olympus-bot-2.0.1.git
cd olympus-bot-2.0.1
python -m venv .venv
```

Activate the virtual environment, then install dependencies:

```bash
# macOS / Linux
source .venv/bin/activate
pip install -r requirements.txt
```

On Windows PowerShell, activate the environment with `.venv\Scripts\Activate.ps1`, then run `pip install -r requirements.txt`.

### Configure and start

The bot reads its Discord token from the `TOKEN` environment variable. Keep this token private and never commit it to Git.

```bash
# macOS / Linux
export TOKEN="your-discord-bot-token"
python main.py
```

On Windows PowerShell:

```powershell
$env:TOKEN = "your-discord-bot-token"
python main.py
```

Enable the privileged intents required by the bot in the Discord Developer Portal. The bot requests all Discord intents, including **Server Members**, **Presence**, and **Message Content**. Invite it with only the permissions needed for the features you plan to use. Regenerate the token immediately if it is exposed.

## Configuration notes

- The default command prefix is `$`. Guild prefixes are stored locally in SQLite.
- Music playback requires a reachable Lavalink server and valid connection settings.
- Tournament functionality uses MongoDB. Configure its connection securely before enabling it; never commit database credentials.
- Some features may require their own API keys or external services.

## Project layout

```text
cogs/       Bot commands, moderation, security, and event modules
core/       Bot class and shared Discord helpers
db/         SQLite data files
utils/      Configuration and shared utilities
games/      Game modules and assets
main.py     Application entry point
config.yml  Bot and integration settings
```

## License

This project is licensed under the [Apache License 2.0](LICENSE).

## Credits and support

Olympus builds on the work of its contributors and the Discord.py ecosystem. For community support, join the [Olympus support server](https://discord.gg/odx).
