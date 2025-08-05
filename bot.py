import os
import discord
import shutil
import json
import random
from functools import wraps
from datetime import datetime, timedelta
from dotenv import load_dotenv
from discord.ext import commands


load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
GUILD = os.getenv('DISCORD_GUILD')
client = discord.Client(intents=discord.Intents.default())
bot = commands.Bot(command_prefix='$', intents=discord.Intents.all())

CHARACTER_NOT_CREATED = "Character not created yet. use init command."
CHARACTER_DIR = "./character_data/"
CHARACTER_OCCUPIED = "Character already occupied"
CHARACTER_IDLE = "Character is idle"
CHARACTER_FINISHED = "Character finished"
ACTIVITY_TEXT = "current_activity"

#########
# HELPERS
#########

def check_if_user_registered(user_data_path: str):
    return os.path.exists(CHARACTER_DIR + user_data_path)

def fetch_user_data(user_data_path):
    data = None
    with open(CHARACTER_DIR + user_data_path, 'r') as file:
        data = json.load(file)
    return data

def check_if_already_active(user_data_path: str):
    data = None
    with open(CHARACTER_DIR + user_data_path, 'r') as file:
        data = json.load(file)
    return ACTIVITY_TEXT in data
        
def fetch_user_data_path(name, id):
    return name +"_"+str(id)+".json"

def add_to_inventory(user_data_path, item, number):
    data = None
    with open(CHARACTER_DIR + user_data_path, 'r') as file:
        data = json.load(file)
    inventory = data['inventory']
    if item in inventory:
        inventory[item] = inventory[item] + number
    else:
        inventory[item] = number
    with open(CHARACTER_DIR + user_data_path, "w") as file:
                json.dump(data, file)

def remove_current_activity(user_data_path):
    data = None
    with open(CHARACTER_DIR + user_data_path, 'r') as file:
        data = json.load(file)
    del data[ACTIVITY_TEXT]
    with open(CHARACTER_DIR + user_data_path, "w") as file:
                json.dump(data, file)

############
# DECORATORS
############

def requires_character_registered():
    def decorator(func):
        @wraps(func)
        async def wrapper(ctx, *args, **kwargs):
            user_data_path = fetch_user_data_path(ctx.author.name, ctx.author.id)
            if not check_if_user_registered(user_data_path):
                await ctx.send(CHARACTER_NOT_CREATED)
                return
            return await func(ctx, *args, **kwargs)
        return wrapper
    return decorator
            
def required_idle_character():
    def decorator(func):
        @wraps(func)
        async def wrapper(ctx, *args, **kwargs):
            user_data_path = fetch_user_data_path(ctx.author.name, ctx.author.id)
            data = fetch_user_data(user_data_path)  
            if check_if_already_active(user_data_path):
                activity = data[ACTIVITY_TEXT]
                time_converted_back = datetime.fromisoformat(activity['end_time'])
                ## current activity ended already
                if time_converted_back <= datetime.now():
                    return await func(ctx, *args, **kwargs)
                ## character not ready
                else:
                    activity_text = " with: " + activity['activity'] + " until: " + str(activity['end_time'])
                    await ctx.send(CHARACTER_OCCUPIED+activity_text)
                    return
            else:
                return await func(ctx, *args, **kwargs)
        return wrapper
    return decorator

############
# COMMANDS
############

@bot.event
async def on_ready():
    print(f'{bot.user.name} has connected to Discord!')

# id and name should be unique enough
@bot.command(name='hello')
async def hello_command(ctx):
    response = f'hello world {ctx.author.display_name}'
    print(ctx)
    await ctx.send(response)

@bot.command(name='init')
async def init_command(ctx):
    # check if user already started
    user_data_path = fetch_user_data_path(ctx.author.name, ctx.author.id)
    if check_if_user_registered(user_data_path):
        await ctx.send("Character already created")
    else:
        shutil.copyfile("./temp.json","./character_data/"+user_data_path)
        await ctx.send("Character created")

@bot.command(name='stats')
@requires_character_registered()
async def stats_command(ctx):
    user_data_path = fetch_user_data_path(ctx.author.name, ctx.author.id)
    data = fetch_user_data(user_data_path)
    stat_text = ""
    for key,val in data["stats"].items():
        stat_text += key+": "+str(val)+"\n"

    await ctx.send(stat_text)


@bot.command(name="status")
@requires_character_registered()
async def status_command(ctx):
    user_data_path = fetch_user_data_path(ctx.author.name, ctx.author.id)
    data = fetch_user_data(user_data_path)
    if check_if_already_active(user_data_path):
        activity = data[ACTIVITY_TEXT]
        time_converted_back = datetime.fromisoformat(activity['end_time'])
        if time_converted_back <= datetime.now():
            loot = random.randint(1, 6)
            add_to_inventory(user_data_path, "fish", loot)
            activity_text = f" with: {activity['activity']} and caught {loot} fish"
            remove_current_activity(user_data_path)
            await ctx.send(CHARACTER_FINISHED+activity_text)
        else:
            activity_text = " with: " + activity['activity'] + " until: " + str(activity['end_time'])
            await ctx.send(CHARACTER_OCCUPIED+activity_text)
    else:
        await ctx.send(CHARACTER_IDLE)



@bot.command(name='fishing')
@requires_character_registered()
@required_idle_character()
async def fishing_command(ctx, arg1: int = commands.parameter(default=1, description="Minutes to spend fishing")):
    user_data_path = fetch_user_data_path(ctx.author.name, ctx.author.id)
    data = fetch_user_data(user_data_path)
    start_time = datetime.now()
    end_time = start_time + timedelta(minutes=arg1)
    activity = {"activity":"fishing","end_time":end_time.isoformat()}
    data[ACTIVITY_TEXT] = activity
    with open(CHARACTER_DIR + user_data_path, "w") as file:
        json.dump(data, file)
    await ctx.send(f"Went fishing hopefully, until: {end_time.isoformat()}")


@bot.command(name='inventory')
@requires_character_registered()
async def inventory_command(ctx):
    user_data_path = fetch_user_data_path(ctx.author.name, ctx.author.id)
    data = fetch_user_data(user_data_path)
    stat_text = ""
    for key,val in data["inventory"].items():
        stat_text += key+": "+str(val)+"\n"
    if stat_text == "":
        await ctx.send("Inventory Empty")
    else:
        await ctx.send(stat_text)

bot.run(TOKEN)