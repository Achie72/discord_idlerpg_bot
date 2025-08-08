import os
import discord
import shutil
import json
import random
import constants
import asyncio
import math
import pytz
from functools import wraps
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from discord.ext import commands
from discord.ui.select import BaseSelect
from typing import Union


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
    

def remove_from_inventory(user_data_path, item, number):
    data = None
    with open(constants.CHARACTER_DIR + user_data_path, 'r') as file:
        data = json.load(file)
    inventory = data['inventory']
    if item in inventory:
        inventory[item] = inventory[item] - number
        if inventory[item] <= 0:
            del inventory[item]
    with open(constants.CHARACTER_DIR + user_data_path, "w") as file:
                json.dump(data, file)


def fetch_user_inventory(user_data_path):
    data = None
    with open(constants.CHARACTER_DIR + user_data_path, 'r') as file:
        data = json.load(file)
    return data['inventory']


def remove_current_activity(user_data_path):
    data = None
    with open(constants.CHARACTER_DIR + user_data_path, 'r') as file:
        data = json.load(file)
    del data[constants.JSON_ACTIVITY]
    with open(constants.CHARACTER_DIR + user_data_path, "w") as file:
        json.dump(data, file)

def set_activity(activity, end_time, duration, data, user_data_path, subtype = None):
    activity = {"activity":activity,"end_time":end_time,"duration":duration,"subtype":subtype}
    data[constants.JSON_ACTIVITY] = activity
    with open(constants.CHARACTER_DIR + user_data_path, "w") as file:
        json.dump(data, file)

def fetch_crafting_recipies_for_activity(activity: str):
    table = None
    table_path = f"{constants.CRAFTING_RECIPE_DIR}/{activity}.json"
    with open(table_path, 'r') as loot_table_file:
        table = json.load(loot_table_file)
    return table

def fetch_encounter_table_for_adventure(subtype) -> dict:
    table = None
    table_path = f"{constants.ADVENTURE_DIR}/{subtype}.json"
    with open(table_path, 'r') as loot_table_file:
        table = json.load(loot_table_file)
    return table

def init_new_skill(user_data_path, activity):
    data = None
    with open(constants.CHARACTER_DIR + user_data_path, 'r') as file:
        data = json.load(file)
    data[constants.JSON_SKILLS][activity] = {
        "current_level": 0,
        "current_xp": 0,
    }
    with open(constants.CHARACTER_DIR + user_data_path, "w") as file:
        json.dump(data, file)

def add_experience_to_activity(activity: str, experience: int, user_data_path: str):
    data = None
    with open(constants.CHARACTER_DIR + user_data_path, 'r') as file:
        data = json.load(file)
    data[constants.JSON_SKILLS][activity]['current_xp'] = data[constants.JSON_SKILLS][activity].get('current_xp') + experience
    with open(constants.CHARACTER_DIR + user_data_path, "w") as file:
        json.dump(data, file)

def set_stat(stat: str, value: int, user_data_path: str):
    data = None
    with open(constants.CHARACTER_DIR + user_data_path, 'r') as file:
        data = json.load(file)
    data[constants.JSON_STATS][stat] = value
    with open(constants.CHARACTER_DIR + user_data_path, "w") as file:
        json.dump(data, file)

def resolve_adventure(user_data: dict, user_data_path: str):
    player_stats = user_data.get('stats')
    duration = user_data.get(constants.JSON_ACTIVITY).get('duration')
    sub_type = user_data.get(constants.JSON_ACTIVITY).get('subtype')
    combat_log = dict()
    combat_loot_log = dict()
    peaceful_log = dict()
    died_on_adventure = False
    #grab encoutner table for adventure type
    encounter_table = fetch_encounter_table_for_adventure(subtype=sub_type)
   
    chance_for_combat = encounter_table.get('combat_ratio', 0.5)
    roll = random.random()
    if roll :
        combat_encounters = encounter_table['combat']
        encounter = fetch_weighted_encounter(combat_encounters)
        encounter_data_stats = combat_encounters.get(encounter).get('stats')
        won, hp_left = simulate_combat(player_stats, encounter_data_stats)
        player_stats['health'] = hp_left
        if won:
            # fetch and roll loot
            # combat_encounters[encounter].get('loot')
            loot_table = combat_encounters[encounter].get('loot')
            drops = fetch_drop_table_name_weight_pairs(loot_table)
            drop_name = fetch_weighted_loot(drops)
            drop_amount = fetch_drop_ammount_by_weights(loot_items=loot_table, loot=drop_name)
            combat_loot_log[drop_name] = combat_loot_log.get(drop_name, 0) + drop_amount
            combat_log[encounter] = combat_log.get(encounter, 0) + 1
        else:
            died_on_adventure = True
    else:
        peacful_encounters = encounter_table['peaceful']
        drops = fetch_drop_table_name_weight_pairs(peacful_encounters)
        drop_name = fetch_weighted_loot(drops)
        drop_amount = fetch_drop_ammount_by_weights(loot_items=peacful_encounters, loot=drop_name)
        peaceful_log[drop_name] = peaceful_log.get(drop_name, 0) + drop_amount
    # now that encounters are resolved, let's find everything
    
    if len(peaceful_log) > 0:
        for key,value in peaceful_log.items():
            add_to_inventory(user_data_path, key, value)

    if len(combat_log) > 0:
        for key,value in combat_loot_log.items():
            add_to_inventory(user_data_path, key, value)
    set_stat('health', player_stats['health'], user_data_path)
    return combat_log, combat_loot_log, peaceful_log, died_on_adventure

def simulate_combat(obj1: dict, obj2: dict):
    health1 = obj1.get('health')
    health2 = obj2.get('health')
    while health1 > 0 and health2 > 0:
        health2 -= obj1.get('strength') - obj2.get('armor', 0)
        health1 -= obj2.get('strength') - obj2.get('armor', 0)

    # we have a winner
    return health1 > 0, health1

def resolve_activity(activity, duration, user_data: dict, user_data_path):
    #check if user has the skill or not (handle new skills)
    if not activity in user_data[constants.JSON_SKILLS]:
        init_new_skill(user_data_path, activity)
        user_data = fetch_user_data(user_data_path)
    activity_level = user_data[constants.JSON_SKILLS][activity]['current_level']
    loot_text = f"You finished your {activity}! Acquired the following: "
    adventure_peace_log = dict()
    adventure_combat_log = dict()
    adventure_combat_loot_log = dict()
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
            case constants.ACTIVITY_SMITHING | constants.ACTIVITY_COOKING:
                recipies = fetch_crafting_recipies_for_activity(activity)
                #fetch currently processed recipe
                current_rec = user_data[constants.JSON_ACTIVITY][constants.JSON_CRAFTING_RECIPE]
                # figure out which materials we have less to process
                inventory = fetch_user_inventory(user_data_path=user_data_path)
                current_ingredients = recipies.get(current_rec).get('cost')
                if can_craft(current_ingredients, inventory):
                    for item, cost in current_ingredients.items():
                        if item in inventory:
                            remove_from_inventory(user_data_path, item, cost)
                            inventory[item] = inventory[item] - cost
                            if inventory[item] <= 0:
                                del inventory[item]
                    crafted_items = recipies.get(current_rec).get('amount')
                    looted[current_rec] = looted.get(current_rec, 0) + crafted_items
                else:
                    break
            case constants.ACTIVITY_ADVENTURE:
                combat_log, combat_loot_log, peaceful_log, died_on_adventure = resolve_adventure(user_data=user_data, user_data_path=user_data_path)
                merge_dicts(adventure_combat_log, combat_log)
                merge_dicts(adventure_combat_loot_log, combat_loot_log)
                merge_dicts(adventure_peace_log, peaceful_log)
                
                if died_on_adventure:
                    break
            case _:
                print("non valid activity")
    experience = 0
    if activity == constants.ACTIVITY_ADVENTURE:
        if died_on_adventure:
            loot_text = f"**You were found unconscious in the {user_data[constants.JSON_ACTIVITY]['subtype']}**.\nThey healed you back and returned your items:\n"
            set_stat('health', 10, user_data_path)
        else:
            loot_text = f"**You were successful on your {user_data[constants.JSON_ACTIVITY]['subtype']} adventure!**\nObtained the following:\n"

        if len(adventure_peace_log) > 0:
            for key,value in adventure_peace_log.items():
                loot_text += f"\n- {value} {key}"

        if len(adventure_combat_log) > 0:
            loot_text += "\n**You defeated:**\n"
            for key,value in adventure_combat_log.items():
                loot_text += f"\n- {value} {key}"
            loot_text += "\nand claimed:"
            for key,value in adventure_combat_loot_log.items():
                loot_text += f"\n- {value} {key}"
    else:
        for key,value in looted.items():
            loot_text += f"\n- {value} {key}"
            add_to_inventory(user_data_path, key, value)
            add_experience_to_activity(activity=activity, experience=value, user_data_path=user_data_path)
            experience += value
        loot_text += f"\nAnd gained **{experience}** XP in your {activity} skill!"
    return loot_text

def merge_dicts(dict1: dict, dict2: dict):
    for key, value in dict2.items():
        dict1[key] = dict1.get(key, 0) + value
    

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

def fetch_weighted_encounter(encounters):
    choices = []
    for item, data in encounters.items():
        weight = data['weight']
        choices.extend([item] * weight)
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

def fetch_drop_ammount_by_weights(loot_items: dict, loot: str) -> int:
    roll_low = loot_items[loot]['range']['low']
    roll_high = roll_low = loot_items[loot]['range']['high']
    return random.randint(roll_low, roll_high)

def can_craft(ingredients, inventory):
    for item, cost in ingredients.items():
        if item in inventory:
            if (inventory[item] < cost) and (inventory[item] >= 0):
                return False
        else:
            return False
    return True

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
                time_stamp = activity['end_time']
                ## current activity ended already
                if time_stamp <= datetime.now().timestamp():
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
# CLASSES
############

# Defines a custom Select containing colour options
# that the user can choose. The callback function
# of this class is called when the user changes their choice
class Dropdown(discord.ui.Select):
    def __init__(self, options_sent, craft_type, duration, user_who_called):

        # Set the options that will be presented inside the dropdown
        options = []
        for opt in options_sent:
            options.append(discord.SelectOption(label=opt['name'],emoji="🛠️",description=opt['desc']))

        # The placeholder is what will be shown when no option is chosen
        # The min and max values indicate we can only pick one of the three options
        # The options parameter defines the dropdown options. We defined this above
        self.craft_type = craft_type
        self.duration = duration
        self.user = user_who_called
        super().__init__(placeholder='Choose what to craft ...', min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        # Use the interaction object to send a response message containing
        # the user's favourite colour or choice. The self object refers to the
        # Select object, and the values attribute gets a list of the user's
        # selected options. We only want the first one.
        if interaction.user.id == self.user:
            self.disabled = True
            await interaction.response.send_message(f'You selected {self.values[0]}')
            user_name = interaction.user.name
            user_id = interaction.user.id
            user_data_path = fetch_user_data_path(user_name, user_id)
            data = fetch_user_data(user_data_path)
            start_time = datetime.now()
            end_time = start_time + timedelta(minutes=self.duration)
            value_to_json = self.values[0].lower().replace(" ","_")
            set_activity(self.craft_type,end_time.timestamp(),self.duration,data,user_data_path, value_to_json)

            #set_activity('fishing',end_time.timestamp(),arg1,data,user_data_path)

            await interaction.message.edit(view=self.view)
        else:
            await interaction.response.send_message('✋ **Not you, you pesky 🐦**')


class DropdownView(discord.ui.View):
    def __init__(self, options_sent, craft_type, duration, user_who_called):
        super().__init__()
        # Adds the dropdown to our view object.
        self.add_item(Dropdown(options_sent, craft_type, duration, user_who_called))


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

@bot.command(name='skills')
@requires_character_registered()
async def stats_command(ctx, *args):
    user_data_path = fetch_user_data_path(ctx.author.name, ctx.author.id)
    data = fetch_user_data(user_data_path)
    skill_text = ""
    if args:
        skill_text += f"**Your {args[0]} level is the following**:\n"
        skill = data[constants.JSON_SKILLS].get(args[0])
        skill_text += f"\n- **{skill.capitalize()}** on Level **{skill.get('current_level')}** with **{skill.get('current_xp')}** experience"
    else:
        skill_text += "**Your skill levels are the following**:\n"
        for key,val in data[constants.JSON_SKILLS].items():
            skill_text += f"\n- **{key.capitalize()}** on Level **{val.get('current_level')}** with **{val.get('current_xp')}** experience"

    await ctx.send(skill_text)


@bot.command(name="status")
@requires_character_registered()
async def status_command(ctx):
    user_data_path = fetch_user_data_path(ctx.author.name, ctx.author.id)
    data = fetch_user_data(user_data_path)
    if check_if_already_active(user_data_path):
        activity = data[constants.JSON_ACTIVITY]
        time_when_ends = data[constants.JSON_ACTIVITY].get('end_time')
        discord_timestamp = f"<t:{int(time_when_ends)}:F>"
        if time_when_ends <= datetime.now().timestamp():
            looted = resolve_activity(activity['activity'], activity.get('duration', 1), data, user_data_path)
            remove_current_activity(user_data_path)
            await ctx.send(looted)
        else:
            # activity = " with: " + activity['activity'] + " until: " + str(activity['end_time'])
            #await ctx.send(constants.CHARACTER_OCCUPIED+activity)
            await ctx.send(f"{constants.CHARACTER_OCCUPIED}With **{str(activity['activity']).capitalize()}** until **{discord_timestamp}**")
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
    set_activity('fishing',end_time.timestamp(),arg1,data,user_data_path)
    discord_timestamp = f"<t:{int(end_time.timestamp())}:F>"
    await ctx.send(f"Went fishing hopefully, until: {discord_timestamp}")


@bot.command(name='mining')
@requires_character_registered()
@required_idle_character()
async def mining_command(ctx, arg1: int = commands.parameter(default=1, description="Minutes to spend mining")):
    user_data_path = fetch_user_data_path(ctx.author.name, ctx.author.id)
    data = fetch_user_data(user_data_path)
    start_time = datetime.now()
    end_time = start_time + timedelta(minutes=arg1)
    set_activity('mining',end_time.timestamp(),arg1,data,user_data_path)
    discord_timestamp = f"<t:{int(end_time.timestamp())}:F>"
    await ctx.send(f"Went mining hopefully, until: {discord_timestamp}")


@bot.command(name='adventure')
@requires_character_registered()
@required_idle_character()
async def adventure_command(ctx, arg1: int = commands.parameter(default=1, description="Minutes to spend on adventuring")):
    adventure_text = """Choose where to spend your time:
    🌳 - Forest
    ⛰️ - Mountains
    ⛏️ - Mines
    🏜️ - Desert
    """
    message = await ctx.send(adventure_text)
    options = ("🌳","⛰️","⛏️","🏜️")
    for opt in options:
        await message.add_reaction(opt)

    def check(r: discord.Reaction, u: Union[discord.Member, discord.User]):  # r = discord.Reaction, u = discord.Member or discord.User.
        return u.id == ctx.author.id and r.message.channel.id == ctx.channel.id and \
               str(r.emoji) in options
        # checking author, channel and only having the check become True when detecting a ✅ or ❌
        # else, it will timeout.

    try:
        #                         event = on_reaction_add without on_
        reaction, user = await bot.wait_for('reaction_add', check = check, timeout = 60.0)
        # reaction = discord.Reaction, user = discord.Member or discord.User.
    except asyncio.TimeoutError:
        # at this point, the check didn't become True.
        await ctx.send(f"**{ctx.author}**, you didnt react in 60 seconds.")
        return
    else:
        # at this point, the check has become True and the wait_for has done its work, now we can do ours.
        # here we are sending some text based on the reaction we detected.
        
        for emoji in options:
            if str(reaction.emoji) == emoji:
                user_data_path = fetch_user_data_path(ctx.author.name, ctx.author.id)
                data = fetch_user_data(user_data_path)
                start_time = datetime.now()
                end_time = start_time + timedelta(minutes=arg1)
                set_activity('adventure',end_time.timestamp(),arg1,data,user_data_path, "forest")
                return await ctx.send(f"{ctx.author} adventured into {emoji} for {arg1} minutes.")

@bot.command(name='smithing')
@requires_character_registered()
@required_idle_character()
async def smithing_options(ctx, arg1: int = commands.parameter(default=1, description="Minutes to spend on Smithing")):
    craft_options = []
    recipies = fetch_crafting_recipies_for_activity(constants.ACTIVITY_SMITHING)
    #fetch currently processed recipe
    user_data_path = fetch_user_data_path(ctx.author.name, ctx.author.id)
    inventory = fetch_user_inventory(user_data_path=user_data_path)
    for current_rec in recipies:
        current_ingredients = recipies.get(current_rec).get('cost')
        if can_craft(current_ingredients, inventory):
            option_desc = { "name": recipies.get(current_rec).get('display_name'), "desc": recipies.get(current_rec).get('desc')}
            craft_options.append(option_desc)
    view = DropdownView(craft_options, 'smithing', arg1, ctx.author.id)
    if len(craft_options) > 0:
    # Sending a message containing our view
        await ctx.send('What are we smithing:', view=view)
    else:
        await ctx.send(constants.NO_INGREDIENTS_FOR_CRAFT)

@bot.command(name='cooking')
@requires_character_registered()
@required_idle_character()
async def cooking_options(ctx, arg1: int = commands.parameter(default=1, description="Minutes to spend on Cooking")):
    craft_options = []
    recipies = fetch_crafting_recipies_for_activity(constants.ACTIVITY_COOKING)
    #fetch currently processed recipe
    user_data_path = fetch_user_data_path(ctx.author.name, ctx.author.id)
    inventory = fetch_user_inventory(user_data_path=user_data_path)
    for current_rec in recipies:
        current_ingredients = recipies.get(current_rec).get('cost')
        if can_craft(current_ingredients, inventory):
            option_desc = { "name": recipies.get(current_rec).get('display_name'), "desc": recipies.get(current_rec).get('desc')}
            craft_options.append(option_desc)

    view = DropdownView(craft_options, constants.ACTIVITY_COOKING, arg1, ctx.author.id)
    if len(craft_options) > 0:
    # Sending a message containing our view
        await ctx.send('What are we cooking:', view=view)
    else:
        await ctx.send(constants.NO_INGREDIENTS_FOR_CRAFT)


@bot.command(name='resolve')
@requires_character_registered()
async def resolve_command(ctx):
    user_data_path = fetch_user_data_path(ctx.author.name, ctx.author.id)
    data = fetch_user_data(user_data_path)
    activity = data[constants.JSON_ACTIVITY]
    looted = resolve_activity(activity['activity'], activity.get('duration', 1), data, user_data_path)
    remove_current_activity(user_data_path)
    await ctx.send(looted)
  


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