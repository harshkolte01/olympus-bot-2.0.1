import os


import asyncio
import traceback
from threading import Thread
from datetime import datetime

import aiohttp
import discord
from discord.ext import commands


from core import Context
from core.Cog import Cog
from core.Olympus import Olympus
from utils.Tools import *
from utils.config import *
from discord.ext import commands

import jishaku

from cogs import *


#Configuring Jishaku behavior
os.environ["JISHAKU_NO_DM_TRACEBACK"] = "False"
os.environ["JISHAKU_HIDE"] = "True"
os.environ["JISHAKU_NO_UNDERSCORE"] = "True"
os.environ["JISHAKU_FORCE_PAGINATOR"] = "True"


client = Olympus()
tree = client.tree
TOKEN = os.getenv("TOKEN")




@client.event
async def on_ready():
    await client.wait_until_ready()
    print("Loaded & Online!")
    print(f"Logged in as: {client.user}")
    print(f"Connected to: {len(client.guilds)} guilds")
    print(f"Connected to: {len(client.users)} users")
    try:
        synced = await client.tree.sync()
        all_commands = list(client.commands)
        print(f"Synced Total {len(all_commands)} Client Commands and {len(synced)} Slash Commands")
    except Exception as e:
        print(e)




from flask import Flask
from threading import Thread

app = Flask(__name__)


@app.route('/')
def home():
    return f"P Development 2024"


def run():
    app.run(host='0.0.0.0', port=8080)


def keep_alive():
    server = Thread(target=run)
    server.start()


keep_alive()

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

# MongoDB connection
MONGO_URI = "mongodb+srv://harshop12241:harshop12241@cluster0.68hrt.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"  # Replace with your MongoDB URI
mongo_client = AsyncIOMotorClient(MONGO_URI)
print("Connected to MongoDB")
db = mongo_client["tournament_db"]  # Replace with your database name

async def main():
    async with client:
        os.system("clear")
        #await client.load_extension("cogs")
        await client.load_extension("jishaku")
        await client.load_extension("cogs.commands.tournament")
        await client.start(TOKEN)
        


if __name__ == "__main__":
    asyncio.run(main())
