# Family Meal Planner Bot 🍱

A Telegram bot that automatically sends your family's weekly meal plan every Monday morning, lets anyone mark meals as dining out, and generates a grocery list split by your Monday and Thursday shopping days.

---

## Files in this folder

```
meal_planner_bot/
├── bot.py              ← The Telegram bot (main program)
├── meals.py            ← Recipe logic, reads from the spreadsheet
├── Ingredient.xlsx     ← Your ingredient & recipe spreadsheet (keep this here)
├── current_plan.json   ← Auto-created: saves the current week's plan
├── .env                ← Your secret credentials (you create this)
├── .env.example        ← Template showing what .env should look like
├── requirements.txt    ← Python packages needed
└── .gitignore          ← Keeps secrets out of GitHub
```

---

## Setup (one time only)

### Step 1 — Install the required packages

Open a terminal in VS Code (Terminal → New Terminal) and run:

```bash
pip install -r requirements.txt
```

### Step 2 — Create your Telegram Bot

1. Open Telegram and search for **@BotFather**
2. Send it `/newbot`
3. Give your bot a name (e.g. `Tan Family Meals`) and a username (e.g. `tanfamilymeals_bot`)
4. BotFather replies with a **token** — it looks like `7123456789:AAFxxxxxxxxxxxxxxxx`
5. Copy that token

### Step 3 — Add the bot to your family group

1. Open your family group chat on Telegram
2. Tap the group name → Add Members → search for your bot's username
3. Make the bot an **Admin** (so it can post messages)

### Step 4 — Find your group's Chat ID

1. Add **@userinfobot** to the group
2. It will immediately print a message showing the group's Chat ID
3. It looks like `-1001234567890` (negative number, that's normal for groups)
4. Remove @userinfobot from the group after

### Step 5 — Create your .env file

In the `meal_planner_bot` folder, create a new file called `.env` (no extension):

```
BOT_TOKEN=7123456789:AAFxxxxxxxxxxxxxxxx
CHAT_ID=-1001234567890
```

Replace the values with your actual token and chat ID.

### Step 6 — Place your spreadsheet

Make sure `Ingredient.xlsx` is in the same folder as `bot.py` and `meals.py`.

### Step 7 — Run the bot

```bash
python bot.py
```

You should see:
```
Starting Family Meal Planner Bot...
Bot is running. Press Ctrl+C to stop.
```

Test it by opening Telegram and typing `/plan` in your family group. The bot should reply with this week's meal plan.

---

## Commands

| Command | What it does |
|---|---|
| `/plan` | Show this week's meal plan |
| `/out Tuesday dinner` | Mark Tuesday dinner as dining out |
| `/back Tuesday dinner` | Undo — back to cooking at home |
| `/grocery` | Shopping list (Monday + Thursday shops) |
| `/regenerate` | Generate a fresh plan for this week |
| `/help` | Show all commands |

---

## Automatic Monday send

The bot automatically sends a fresh meal plan every **Monday at 8am Singapore time**. You don't need to do anything — just keep the bot running.

---

## Deploying to the cloud (so it runs 24/7)

Right now the bot only works while your laptop is on. To run it permanently for free:

### Option A — Railway (recommended, free tier)

1. Create a free account at [railway.app](https://railway.app)
2. Push your code to GitHub (excluding `.env` — it's in `.gitignore`)
3. On Railway: New Project → Deploy from GitHub → select your repo
4. Go to Variables and add `BOT_TOKEN` and `CHAT_ID` (same values as your `.env`)
5. Railway will detect `requirements.txt` and deploy automatically
6. Done — your bot runs 24/7 in the cloud

### Option B — Render (also free)

Similar to Railway. Create account at [render.com](https://render.com), connect GitHub, add environment variables, deploy.

---

## Updating your recipes

Just edit `Ingredient.xlsx` — add or remove rows in the recipe section. The bot reads the spreadsheet fresh every time it generates a new plan, so no code changes are needed.

---

## Troubleshooting

**Bot doesn't respond**
- Check that the bot is an Admin in the group
- Make sure `.env` has the correct `BOT_TOKEN`

**Wrong Chat ID**
- Group Chat IDs are negative numbers starting with `-100`
- Double-check using @userinfobot

**`ModuleNotFoundError`**
- Run `pip install -r requirements.txt` again

**Time zone — plan sends at wrong time**
- The bot uses UTC+8 (Singapore time). Monday 8am SGT = Monday 00:00 UTC.
- If you're in a different timezone, adjust `hour=0` in `bot.py` line ~145.
