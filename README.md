A WIP very simple Idle RPG bot for discord 

# Commands

Atm supports the following:


- $hello  - Simple Hello World
- $init - Create Character
- $help - Command helps
- $status - Character status, this resolves previous actions
- $inventory - Character inventory
- $fishing arg1 - Sends the character to fish for arg1 (default 1) minutes
- $smithing arg1 - Sends the character to smith for arg1 (default 1) minutes
  - Creates a dropdown with recipes the character has ingredients for
- $cooking arg1 - Sends the character to cook for arg1 (default 1) minutes
  - Creates a dropdown with recipes the character has ingredients for
- $Heal arg1 - Heals the character with arg1 (default 1) amount of healing items
  - Creates a dropdown with healing items that have at least arg1 amount in inventory
- $resolve debugger command to resolve current activity ingoring timestamps
- $adventure $arg1 - Sends the character to adventure for arg1 (default 1) minutes
  - Creates an emote based choosing system.
  - ATM only "forest" work and data is not fully fetched from the json
- $train - POC, only creates a choose emote prompt


# Customization

## Recipes

Recipes follow a simple pattern_
- `name` name of the item we are creating
- `Cost` can be an array of simple item of items to consume upon each craft.
- Items follow the pattern of `name`: `<number>`
- `amount`: `<number>` number of items to create per `cost` consumption
- `level_required`:`<number>` Not used yet
```json
{
    "name" : {
        "cost" : {
            "item1": 1,
            "item2": 1
        },
        "amount" : 1,
        "level_required": 0
    }
}
```
These need to be placed in their respection `activity.son` inside `/crafting`.

## Adding a new crafting activity

Follow the existing template of:

Create your crafting activity recipe table in `/crafing/your_new_activity.json` by following the above given instructions.

```py
@bot.command(name='your_new_activity')
@requires_character_registered()
@required_idle_character()
async def your_new_activity_command(ctx)
```

Add activity constants in constants. Replace the constant in these two places:
```python
recipies = fetch_crafting_recipies_for_activity(constants.ACTIVITY_COOKING)
view = DropdownView(craft_options, constants.ACTIVITY_COOKING, arg1)
```

Add new activity to the craftin case:
```python

case constants.ACTIVITY_SMITHING | constants.ACTIVITY_COOKING | constants.YOUR_NEW_ACTIVITY:
```

Now `$your_new_activity` can be called.

## Add new loot

Loot tables follow a simple structure. They can hold `common`, `rare`, `epic` and `legendary` fields:
```json
{
    "common" : {
        "fish": {
            "weight": 5,
            "range":{
                "low": 1,
                "high": 3
            }
        },
        "junk": {
            "weight": 1,
            "range":{
                "low": 1,
                "high": 3
            }
        }
    },
    "rare" : {
        "coins": {
            "weight": 1,
            "range":{
                "low": 1,
                "high": 3
            }
        }
    },
    "epic" : {
        "coins": {
            "weight": 1,
            "range":{
                "low": 3,
                "high": 10
            }
        }
    },
    "legendary" : {
        "kraken": {
            "weight": 1,
            "range":{
                "low": 1,
                "high": 1
            }
        }
    }
    
}
```

inside each rarity slot, you can define the drops and their stats:
- `weight`: weight of the item in random, see later on how we generate
- `range` : holds `low` and `high`, which hold the minimum to maximum amount we can loot with one action.
```json
    "fish": {
        "weight": 5,
        "range":{
            "low": 1,
            "high": 3
        }
    },
```

First we roll for rarity:

```python
DEFAULT_RARITY_CHANCES = [70, 20, 9, 1]

# then we fetch the items in given rarity

def fetch_rolled_loot_rarity(chances = constants.DEFAULT_RARITY_CHANCES, bonus = 0):
    rarity_table = [ ("common",chances[0]), ("rare",chances[1]+bonus), ("epic",chances[2]+bonus),("legendary",chances[3]+bonus) ]
    choices = []
    for item, weight in rarity_table:
        choices.extend([item]*weight)

# basically we create a collection that has each rarity "rarity chances" times + the bonus which comes from
# skill levels

drop_rarity = fetch_rolled_loot_rarity(bonus=activity_level)

# then we crate a collection the same way we do for rarity, and roll what item we get
items = loot_table[drop_rarity]
drops = fetch_drop_table_name_weight_pairs(items)
drop_name = fetch_weighted_loot(drops)

# with

def fetch_weighted_loot(drops):
    choices = []
    for item, weight in drops:
        choices.extend([item]*weight)

    return random.choice(choices)

# and 
drop_amount = fetch_loot_ammount_by_weights(loot_items=loot_table, rarity=drop_rarity, loot=drop_name)

# with

def fetch_loot_ammount_by_weights(loot_items: dict, rarity: str, loot: str) -> int:
    roll_low = loot_items[rarity][loot]['range']['low']
    roll_high = roll_low = loot_items[rarity][loot]['range']['high']
    return random.randint(roll_low, roll_high)
```


## Adding new loot activity

Create your new activity const `ACTIVITY_YOUR_ACTIVITY = "your_activity"`

Create the command function:

```python
@bot.command(name='your_activity')
@requires_character_registered()
@required_idle_character()
async def your_activity_command(ctx, arg1: int = commands.parameter(default=1, description="Minutes to spend your_activity")):
    user_data_path = fetch_user_data_path(ctx.author.name, ctx.author.id)
    data = fetch_user_data(user_data_path)
    start_time = datetime.now()
    end_time = start_time + timedelta(minutes=arg1)
    set_activity(constants.ACTIVITY_YOUR_ACTIVITY,end_time,arg1,data,user_data_path)
    await ctx.send(f"Went your_activity hopefully, until: {end_time.isoformat()}")
```

Lastly expand the normal looting activity:

```python
 case constants.ACTIVITY_FISHING | constants.ACTIVITY_MINING | constants.ACTIVITY_YOUR_ACTIVITY:
```

If you want custom drop table, you can do that by if-in in the looting activity and sending your own `DEFAULT_RARITY_CHANCES` table to it.