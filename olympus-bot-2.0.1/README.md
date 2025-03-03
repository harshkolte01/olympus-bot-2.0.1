<h1 align="center">
 <br>
  <a href="https://github.com/sonujana26"><img src="https://cdn.discordapp.com/avatars/1144179659735572640/a_8d3bbc050480bc9157fe71c9334d8213.png?size=128"></a>
  <br>
  Olympus the Ultimate Discord Bot
  <br>
</h1>

<h3 align=center>An advanced multipurpose bot built with 400+ commands & 15 categories.</h3>

<div align=center>

  <a href="https://github.com/Rapptz/discord.py">
    <img src="https://img.shields.io/badge/discord.py-v2.4.0-blue.svg?&style=for-the-badge&logo=python" alt="discordpy">
  </a>
  
  <a href="https://github.com/EvieePy/Wavelink">
    <img src="https://img.shields.io/badge/Wavelink-v3.4.1-blue.svg?&style=for-the-badge&logo=data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAUAAAAFCAYAAACNbyblAAAAHElEQVQI12P4//8/w38GIAXDIBKE0DHxgljNBAAO9TXL0Y4OHwAAAABJRU5ErkJggg==" alt="wavelink" style="color:yellow;">
  </a>

  <a href="https://github.com/omnilib/aiosqlite">
    <img src="https://img.shields.io/badge/aiosqlite-%23003B57.svg?&style=for-the-badge&logo=sqlite&logoColor=white" alt="aiosqlite">
  </a>

  <a href="https://github.com/peterhanania/Pogy/blob/main/LICENSE">
    <img src="https://img.shields.io/badge/license-Apache%202-blue?&style=for-the-badge" alt="license">
  </a>

</div>

<p align="center">
  <a href="#about">About</a>
  •
  <a href="#features">Features</a>
  •
  <a href="#installation">Installation</a>
  •
  <a href="#setting-up">Setting Up</a>
  •
  <a href="#license">License</a>
  •
  <a href="#donate">Donate</a>
  •
  <a href="#credits">Credits</a>
</p>

## 🔗 [Invite the Public Bot (Olympus) by clicking here!](https://discord.com/oauth2/authorize?client_id=1144179659735572640&permissions=2113268958&scope=bot)

## About

Olympus is a powerful, easy-to-use Discord bot designed to enhance your server experience with an extensive suite of features. Built with advanced security, automoderation, moderation, music systems, welcoming features, and more at its core, Olympus ensures your community stays safe and well-managed, giving you peace of mind and control.

## Features

| Feature                 | Description                                                      |
|-------------------------|------------------------------------------------------------------|
| ![Security](https://img.shields.io/badge/Security-Antinuke%20%26%20Emergency-red?style=for-the-badge) | Protect your server with Antinuke and emergency features. |
| ![Automoderation](https://img.shields.io/badge/Automoderation-Advanced-red?style=for-the-badge) | Automatically moderate your server to prevent spam and abuse. |
| ![Moderation](https://img.shields.io/badge/Moderation-Essential%20Tools-red?style=for-the-badge) | Manage your community with powerful moderation commands. |
| ![Music System](https://img.shields.io/badge/Music%20System-High%20Quality-red?style=for-the-badge) | Stream music with advanced controls and great sound quality. |
| ![Welcoming](https://img.shields.io/badge/Welcoming-Customizable-red?style=for-the-badge) | Greet members with personalized welcome messages. |
| ![Utilities](https://img.shields.io/badge/Utilities-Efficient%20Tools-red?style=for-the-badge) | Access tools that simplify server management. |
| ![Giveaway](https://img.shields.io/badge/Giveaway-Easy%20Management-red?style=for-the-badge) | Host and manage giveaways effortlessly. |
| ![Games](https://img.shields.io/badge/Games-Fun%20%26%20Interactive-red?style=for-the-badge) | Enjoy interactive games with your community. |
| ![Customrole](https://img.shields.io/badge/Customrole-Role%20Management-red?style=for-the-badge) | Easily assign and manage custom roles. |
| ![Fun](https://img.shields.io/badge/Fun-Entertainment%20Commands-red?style=for-the-badge) | Liven up your server with engaging fun commands. |
| ![Voice](https://img.shields.io/badge/Voice-Channel%20Control-red?style=for-the-badge) | Manage voice channels with advanced utilities. |
| ![AI Image Generator](https://img.shields.io/badge/AI%20Image%20Generator-Stunning%20Visuals-red?style=for-the-badge) | Create AI-powered images directly from Discord. |


## Installation

1. First, clone the repository:  
   ```bash
   git clone https://github.com/sonujana26/olympus-bot
   ```
2. After cloning, run the bot:
   ```bash
   python main.py
   ```
## Setting Up

1. Rename `example.env` to `.env` and replace the bot token value:
   ```env
   TOKEN=YOUR_BOT_TOKEN_HERE
   ```
   • Replace the Owner ID(s) [here](https://github.com/sonujana26/olympus-bot/blob/main/utils/config.py#L7) (in `utils/config.py`).
2. **Prefix:**
   Default Prefix: `$`
   > You can change prefix **[here](https://github.com/sonujana26/olympus-bot/blob/main/utils/Tools.py#L84)**.
   
4. **For Music:**  
   A public Lavalink is used, hosted by [Winkle Music](https://discord.gg/winklemusic) by [Ujjwal](https://github.com/UjjwalxD). For better audio quality, it is recommended to set up your private Lavalink v4.  
   > Update your Lavalink URL, password, and other configurations [by clicking here](https://github.com/sonujana26/olympus-bot/blob/main/cogs/commands/music.py#L339).
- If you are using your private lavalink & have youtube plugin enabled/working but the Spotify plugin is not working, than you can Uncomment Lines `(445 - 452)` in `(cogs/commands/music.py)`, this will convert a Spotify track to YouTube Track.

5. **Logging & Notifications:**  
   - **Command Logs:** Get a channel webhook URL and update it [here](https://github.com/sonujana26/olympus-bot/blob/main/main.py#L75) (in `main.py`).  
   - **Guild Joins:** Add the channel ID [here](https://github.com/sonujana26/olympus-bot/blob/main/cogs/events/on_guild.py#L25) (in `cogs/events/on_guild.py`).  
   - **Guild Leaves:** Add the channel ID [here](https://github.com/sonujana26/olympus-bot/blob/main/cogs/events/on_guild.py#L109) (in `cogs/events/on_guild.py`).

6. **No Prefix Commands:**  
   There are several `np` commands like `np add`, `np remove`, `auto np add`, `auto np remove`, `auto np role`, etc. Check and modify them as needed in `cogs/commands/np.py`.

7. **Emojis & Colors:**  
   Unfortunately, there is no centralized setup for emojis & embed colors. You need to manually update emojis in all files where they are used.

## License
Released under the [Apache License](http://www.apache.org/licenses/LICENSE-2.0) license.

## Donate
Coming Soon

## Credits
**Author:**  
Sonu Jana - *Head Developer* - **[GitHub](https://github.com/sonujana26)**

**Team:**
<div align="center">
  <a href="https://discord.com/invite/odx">
    <img src="https://discordapp.com/api/guilds/699587669059174461/widget.png?style=banner2">
  </a>
</div>
