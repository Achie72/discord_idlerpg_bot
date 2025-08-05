import os
import discord
import shutil
import json
import random
import constants
from functools import wraps
from datetime import datetime, timedelta
from dotenv import load_dotenv
from discord.ext import commands


load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
GUILD = os.getenv('DISCORD_GUILD')
client = discord.Client(intents=discord.Intents.default())
bot = commands.Bot(command_prefix='$', intents=discord.Intents.all())

#########
# HELPERS
#########

def check_if_user_registered(user_data_path: str):
    return os.path.exists(constants.CHARACTER_DIR + user_data_path)

def fetch_user_data(user_data_path):
    data = None
    with open(constants.CHARACTER_DIR + user_data_path, 'r') as file:
        data = json.load(file)
    return data

def check_if_already_active(user_data_path: str):
    data = None
    with open(constants.CHARACTER_DIR + user_data_path, 'r') as file:
        data = json.load(file)
    return constants.JSON_ACTIVITY in data
        
def fetch_user_data_path(name, id):
    return name +"_"+str(id)+".json"

def add_to_inventory(user_data_path, item, number):
    data = None
    with open(constants.CHARACTER_DIR + user_data_path, 'r') as file:
        data = json.load(file)
    inventory = data['inventory']
    if item in inventory:
        inventory[item] = inventory[item] + number
    else:
        inventory[item] = number
    with open(constants.CHARACTER_DIR + user_data_path, "w") as file:
                json.dump(data, file)

def remove_current_activity(user_data_path):
    data = None
    with open(constants.CHARACTER_DIR + user_data_path, 'r') as file:
        data = json.load(file)
    del data[constants.JSON_ACTIVITY]
    with open(constants.CHARACTER_DIR + user_data_path, "w") as file:
                json.dump(data, file)


def resolve_activity(activity, duration, user_data, user_data_path):
    activity_level = user_data[constants.JSON_SKILLS][activity]['current_level']
    loot_text = "Caught: "
    looted = dict()
    for i in range(0, duration):
        match activity:
            case constants.ACTIVITY_FISHING | constants.ACTIVITY_MINING:
                
                # grab loot table
                loot_table = fetch_loot_table_for_activity(activity)
                # roll for loot type
                drop_rarity = fetch_rolled_loot_rarity(bonus=activity_level)
                items = loot_table[drop_rarity]
                drops = fetch_drop_table_name_weight_pairs(items)
                drop_name = fetch_weighted_loot(drops)
                drop_amount = fetch_loot_ammount_by_weights(loot_items=loot_table, rarity=drop_rarity, loot=drop_name)
                looted[drop_name] = looted.get(drop_name, 0) + drop_amount
            case _:
                print("non valid activity")

    for key,value in looted.items():
        loot_text += f"\n{value} {key}"
        add_to_inventory(user_data_path, key, value)
    return loot_text


def fetch_loot_table_for_activity(activity) -> dict:
    table = None
    table_path = f"{constants.LOOT_TABLE_DIR}/{activity}.json"
    with open(table_path, 'r') as loot_table_file:
        table = json.load(loot_table_file)
    return table

def fetch_rolled_loot_rarity(chances = constants.DEFAULT_RARITY_CHANCES, bonus = 0):
    rarity_table = [ ("common",chances[0]), ("rare",chances[1]+bonus), ("epic",chances[2]+bonus),("legendary",chances[3]+bonus) ]
    choices = []
    for item, weight in rarity_table:
        choices.extend([item]*weight)

    return random.choice(choices)

def fetch_weighted_loot(drops):
    choices = []
    for item, weight in drops:
        choices.extend([item]*weight)

    return random.choice(choices)

def fetch_drop_table_name_weight_pairs(items: dict) -> list:
    drops = list()
    for key,value in items.items():
        drop_item = (key, value['weight'])
        drops.append(drop_item)
    return drops

def fetch_loot_ammount_by_weights(loot_items: dict, rarity: str, loot: str) -> int:
    roll_low = loot_items[rarity][loot]['range']['low']
    roll_high = roll_low = loot_items[rarity][loot]['range']['high']
    return random.randint(roll_low, roll_high)

############
# DECORATORS
############

def requires_character_registered():
    def decorator(func):
        @wraps(func)
        async def wrapper(ctx, *args, **kwargs):
            user_data_path = fetch_user_data_path(ctx.author.name, ctx.author.id)
            if not check_if_user_registered(user_data_path):
                await ctx.send(constants.CHARACTER_NOT_CREATED)
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
                activity = data[constants.JSON_ACTIVITY]
                time_converted_back = datetime.fromisoformat(activity['end_time'])
                ## current activity ended already
                if time_converted_back <= datetime.now():
                    return await func(ctx, *args, **kwargs)
                ## character not ready
                else:
                    constants.JSON_ACTIVITY = " with: " + activity['activity'] + " until: " + str(activity['end_time'])
                    await ctx.send(constants.CHARACTER_OCCUPIED+constants.JSON_ACTIVITY)
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
        await ctx.send(constants.CHARACTER_ALREADY_CREATED)
    else:
        shutil.copyfile("./temp.json","./character_data/"+user_data_path)
        await ctx.send(constants.CHARACTER_CREATED)

@bot.command(name='stats')
@requires_character_registered()
async def stats_command(ctx):
    user_data_path = fetch_user_data_path(ctx.author.name, ctx.author.id)
    data = fetch_user_data(user_data_path)
    stat_text = ""
    for key,val in data[constants.JSON_STATS].items():
        stat_text += key+": "+str(val)+"\n"

    await ctx.send(stat_text)


@bot.command(name="status")
@requires_character_registered()
async def status_command(ctx):
    user_data_path = fetch_user_data_path(ctx.author.name, ctx.author.id)
    data = fetch_user_data(user_data_path)
    if check_if_already_active(user_data_path):
        activity = data[constants.JSON_ACTIVITY]
        time_converted_back = datetime.fromisoformat(activity['end_time'])
        if time_converted_back <= datetime.now():
            looted = resolve_activity(activity['activity'], activity.get('duration', 1), data, user_data_path)
            remove_current_activity(user_data_path)
            await ctx.send(constants.CHARACTER_FINISHED+constants.JSON_ACTIVITY+looted)
        else:
            constants.JSON_ACTIVITY = " with: " + activity['activity'] + " until: " + str(activity['end_time'])
            await ctx.send(constants.CHARACTER_OCCUPIED+constants.JSON_ACTIVITY)
    else:
        await ctx.send(constants.CHARACTER_IDLE)



@bot.command(name='fishing')
@requires_character_registered()
@required_idle_character()
async def fishing_command(ctx, arg1: int = commands.parameter(default=1, description="Minutes to spend fishing")):
    user_data_path = fetch_user_data_path(ctx.author.name, ctx.author.id)
    data = fetch_user_data(user_data_path)
    start_time = datetime.now()
    end_time = start_time + timedelta(minutes=arg1)
    activity = {"activity":"fishing","end_time":end_time.isoformat(),"duration":arg1}
    data[constants.JSON_ACTIVITY] = activity
    with open(constants.CHARACTER_DIR + user_data_path, "w") as file:
        json.dump(data, file)
    await ctx.send(f"Went fishing hopefully, until: {end_time.isoformat()}")

@bot.command(name='mining')
@requires_character_registered()
@required_idle_character()
async def mining_command(ctx, arg1: int = commands.parameter(default=1, description="Minutes to spend mining")):
    user_data_path = fetch_user_data_path(ctx.author.name, ctx.author.id)
    data = fetch_user_data(user_data_path)
    start_time = datetime.now()
    end_time = start_time + timedelta(minutes=arg1)
    activity = {"activity":"mining","end_time":end_time.isoformat(),"duration":arg1}
    data[constants.JSON_ACTIVITY] = activity
    with open(constants.CHARACTER_DIR + user_data_path, "w") as file:
        json.dump(data, file)
    await ctx.send(f"Went mining hopefully, until: {end_time.isoformat()}")

@bot.command(name='inventory')
@requires_character_registered()
async def inventory_command(ctx):
    user_data_path = fetch_user_data_path(ctx.author.name, ctx.author.id)
    data = fetch_user_data(user_data_path)
    stat_text = ""
    for key,val in data[constants.JSON_INVENTORY].items():
        stat_text += key+": "+str(val)+"\n"
    if stat_text == "":
        await ctx.send(constants.INVENTORY_EMPTY)
    else:
        await ctx.send(stat_text)

bot.run(TOKEN)