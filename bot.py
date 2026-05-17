"""
bot.py — Family Meal Planner Telegram Bot

What this bot does:
  • Every Monday at 8am SGT — automatically sends the week's meal plan to the group
  • /plan          — show the current week's meal plan (anyone can trigger this)
  • /out <day> <meal> — mark a meal as dining out, e.g. /out Tuesday dinner
  • /back <day> <meal> — undo a dining-out mark, e.g. /back Tuesday dinner
  • /grocery       — show the shopping list split by Monday and Thursday shop
  • /regenerate    — generate a fresh meal plan for the week (replaces current)
  • /help          — show available commands

Setup (do this once):
  1. Message @BotFather on Telegram → /newbot → copy your token
  2. Create a .env file in this folder with:
       BOT_TOKEN=your_token_here
       CHAT_ID=your_family_group_chat_id
  3. To find your CHAT_ID: add @userinfobot to your group, it will print the ID
  4. Run:  python bot.py
"""

import logging
import os
import json
from datetime import time, datetime

from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)
from telegram.constants import ParseMode

from meals import load_recipes, generate_week, build_grocery, DAYS

# ── Config ───────────────────────────────────────────────────────────────────

load_dotenv()  # reads BOT_TOKEN and CHAT_ID from .env file

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID   = int(os.getenv("CHAT_ID", "0"))

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN missing — add it to your .env file")
if not CHAT_ID:
    raise ValueError("CHAT_ID missing — add it to your .env file")

# File where the current week's plan is saved (same folder)
PLAN_FILE = os.path.join(os.path.dirname(__file__), "current_plan.json")

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
log = logging.getLogger(__name__)

# ── Plan persistence ──────────────────────────────────────────────────────────

def save_plan(plan: dict):
    """Save the current plan to a JSON file so it survives bot restarts."""
    with open(PLAN_FILE, "w") as f:
        json.dump(plan, f, indent=2)


def load_plan() -> dict | None:
    """Load the saved plan, or return None if none exists yet."""
    if os.path.exists(PLAN_FILE):
        with open(PLAN_FILE) as f:
            return json.load(f)
    return None


def get_or_create_plan() -> dict:
    """Return the saved plan if it exists, otherwise generate a new one."""
    plan = load_plan()
    if plan is None:
        recipes = load_recipes()
        plan = generate_week(recipes)
        save_plan(plan)
        log.info("Generated fresh meal plan")
    return plan

# ── Message formatting ────────────────────────────────────────────────────────

MEAL_EMOJI = {"Breakfast": "🌅", "Lunch": "☀️", "Dinner": "🌙"}
TYPE_EMOJI = {"protein": "🥩", "veg": "🥦", "soup": "🍲", "fruit": "🍎", "carbs": "🌾"}


def format_dish(dish: dict) -> str:
    """Format a single dish: 'Spinach - Spinach + Carrot + Mushrooms'"""
    name = dish["name"]
    ing  = dish.get("ing", [])
    if ing:
        return f"{name} — {' + '.join(ing)}"
    return name


def format_plan(plan: dict) -> str:
    """Format the full week plan as a Telegram message (Markdown)."""
    today   = datetime.now()
    monday  = today - __import__("datetime").timedelta(days=today.weekday())
    week_of = monday.strftime("%d %b %Y").lstrip("0")

    lines = [f"📅 *Meal Plan — Week of {week_of}*\n"]

    for day in DAYS:
        data = plan[day]
        lines.append(f"*{day}*")
        for meal in ["Breakfast", "Lunch", "Dinner"]:
            if data["out"].get(meal):
                lines.append(f"  {MEAL_EMOJI[meal]} _{meal}_ — 🍽 dining out")
                continue
            dishes = data.get(meal, [])
            if not dishes:
                continue
            lines.append(f"  {MEAL_EMOJI[meal]} _{meal}_")
            for d in dishes:
                emoji = TYPE_EMOJI.get(d["type"], "•")
                lines.append(f"    {emoji} {format_dish(d)}")
        lines.append("")

    lines.append("_Tap a button below to mark a meal as dining out._")
    return "\n".join(lines)


def build_keyboard(plan: dict) -> InlineKeyboardMarkup:
    """
    Build an inline keyboard with one button per meal per day.
    Each button shows the day+meal and toggles dining-out status.
    Buttons are arranged: one row per day, three buttons (B / L / D).

    Callback data format:  toggle:Monday:Lunch
    """
    rows = []
    for day in DAYS:
        row = []
        for meal, short in [("Breakfast","B"), ("Lunch","L"), ("Dinner","D")]:
            is_out = plan[day]["out"].get(meal, False)
            label = f"{'✅' if is_out else '🍽'} {day[:3]} {short}"
            callback = f"toggle:{day}:{meal}"
            row.append(InlineKeyboardButton(label, callback_data=callback))
        rows.append(row)

    # Bottom row: regenerate + grocery shortcuts
    rows.append([
        InlineKeyboardButton("🔄 New plan", callback_data="action:regenerate"),
        InlineKeyboardButton("🛒 Grocery list", callback_data="action:grocery"),
    ])
    return InlineKeyboardMarkup(rows)


def format_grocery(plan: dict) -> str:
    """Format the grocery list as a Telegram message."""
    grocery = build_grocery(plan)
    today   = datetime.now()
    monday  = today - __import__("datetime").timedelta(days=today.weekday())
    week_of = monday.strftime("%d %b %Y").lstrip("0")

    lines = [f"🛒 *Grocery List — Week of {week_of}*\n"]

    lines.append("*Monday shop* _(covers Mon – Wed)_")
    if grocery["mon"]:
        for item in grocery["mon"]:
            lines.append(f"  • {item}")
    else:
        lines.append("  _(all dining out)_")

    lines.append("")
    lines.append("*Thursday shop* _(covers Thu – Sun)_")
    if grocery["thu"]:
        for item in grocery["thu"]:
            lines.append(f"  • {item}")
    else:
        lines.append("  _(all dining out)_")

    lines.append("\n_Family Meal Planner Bot_")
    return "\n".join(lines)

# ── Command handlers ──────────────────────────────────────────────────────────

async def cmd_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/plan — show this week's meal plan with interactive buttons"""
    plan = get_or_create_plan()
    await update.message.reply_text(
        format_plan(plan),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=build_keyboard(plan),
    )


async def cmd_out(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /out <day> <meal> — mark a meal as dining out
    Example: /out Tuesday dinner
    """
    args = context.args
    if len(args) < 2:
        await update.message.reply_text(
            "Usage: `/out <day> <meal>`\nExample: `/out Tuesday dinner`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    day  = args[0].capitalize()
    meal = args[1].capitalize()

    if day not in DAYS:
        await update.message.reply_text(
            f"Day not recognised: `{args[0]}`\nUse: Monday, Tuesday, Wednesday, Thursday, Friday, Saturday, Sunday",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    if meal not in ("Breakfast", "Lunch", "Dinner"):
        await update.message.reply_text(
            f"Meal not recognised: `{args[1]}`\nUse: Breakfast, Lunch, or Dinner",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    plan = get_or_create_plan()
    plan[day]["out"][meal] = True
    save_plan(plan)

    await update.message.reply_text(
        f"✅ Marked *{day} {meal}* as dining out. "
        f"Use /plan to see the updated plan, or /grocery for the updated shopping list.",
        parse_mode=ParseMode.MARKDOWN,
    )
    log.info(f"Marked {day} {meal} as dining out")


async def cmd_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /back <day> <meal> — undo a dining-out mark
    Example: /back Tuesday dinner
    """
    args = context.args
    if len(args) < 2:
        await update.message.reply_text(
            "Usage: `/back <day> <meal>`\nExample: `/back Tuesday dinner`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    day  = args[0].capitalize()
    meal = args[1].capitalize()

    if day not in DAYS:
        await update.message.reply_text(f"Day not recognised: `{args[0]}`", parse_mode=ParseMode.MARKDOWN)
        return
    if meal not in ("Breakfast", "Lunch", "Dinner"):
        await update.message.reply_text(f"Meal not recognised: `{args[1]}`", parse_mode=ParseMode.MARKDOWN)
        return

    plan = get_or_create_plan()
    plan[day]["out"][meal] = False
    save_plan(plan)

    await update.message.reply_text(
        f"↩️ *{day} {meal}* is back on — cooking at home. Use /plan to see the updated plan.",
        parse_mode=ParseMode.MARKDOWN,
    )


async def cmd_grocery(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/grocery — show this week's shopping list split by Mon and Thu shops"""
    plan = get_or_create_plan()
    await update.message.reply_text(
        format_grocery(plan),
        parse_mode=ParseMode.MARKDOWN,
    )


async def cmd_regenerate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/regenerate — generate a fresh meal plan for this week"""
    recipes = load_recipes()
    plan    = generate_week(recipes)
    save_plan(plan)
    await update.message.reply_text(
        "🔄 Fresh meal plan generated!\n\n" + format_plan(plan),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=build_keyboard(plan),
    )
    log.info("Meal plan regenerated on demand")


async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles all inline button taps.
    - toggle:Monday:Lunch  → flips dining-out for that meal, updates the message
    - action:regenerate    → generates fresh plan, updates the message
    - action:grocery       → sends grocery list as a new message
    """
    query = update.callback_query
    await query.answer()  # removes the loading spinner

    data = query.data
    plan = get_or_create_plan()

    if data.startswith("toggle:"):
        _, day, meal = data.split(":")
        current = plan[day]["out"].get(meal, False)
        plan[day]["out"][meal] = not current
        save_plan(plan)
        log.info(f"Button: {day} {meal} toggled to {'out' if not current else 'home'}")
        await query.edit_message_text(
            text=format_plan(plan),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=build_keyboard(plan),
        )

    elif data == "action:regenerate":
        recipes = load_recipes()
        plan    = generate_week(recipes)
        save_plan(plan)
        await query.edit_message_text(
            text="🔄 Fresh plan generated!\n\n" + format_plan(plan),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=build_keyboard(plan),
        )

    elif data == "action:grocery":
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=format_grocery(plan),
            parse_mode=ParseMode.MARKDOWN,
        )



async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/help — show all available commands"""
    text = (
        "👨‍🍳 *Family Meal Planner Bot*\n\n"
        "Here's what I can do:\n\n"
        "/plan — Show this week's full meal plan\n"
        "/out <day> <meal> — Mark a meal as dining out\n"
        "    _e.g._ `/out Tuesday dinner`\n"
        "/back <day> <meal> — Undo a dining-out mark\n"
        "    _e.g._ `/back Tuesday dinner`\n"
        "/grocery — Shopping list (Mon shop + Thu shop)\n"
        "/regenerate — Generate a fresh plan for this week\n"
        "/help — Show this message\n\n"
        "_The plan is sent automatically every Monday at 8am._"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

# ── Scheduled Monday send ─────────────────────────────────────────────────────

async def send_weekly_plan(context: ContextTypes.DEFAULT_TYPE):
    """
    Called automatically every Monday at 8am SGT.
    Generates a fresh plan and sends it to the family group.
    """
    log.info("Sending Monday weekly plan")
    recipes = load_recipes()
    plan    = generate_week(recipes)
    save_plan(plan)

    message = (
        "🌟 *Good morning! Here's your meal plan for the week.*\n"
        "_Tap any button below to mark a meal as dining out._\n\n"
        + format_plan(plan)
    )
    await context.bot.send_message(
        chat_id=CHAT_ID,
        text=message,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=build_keyboard(plan),
    )

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    log.info("Starting Family Meal Planner Bot...")

    app = Application.builder().token(BOT_TOKEN).build()

    # Register commands
    app.add_handler(CommandHandler("plan",       cmd_plan))
    app.add_handler(CommandHandler("out",        cmd_out))
    app.add_handler(CommandHandler("back",       cmd_back))
    app.add_handler(CommandHandler("grocery",    cmd_grocery))
    app.add_handler(CommandHandler("regenerate", cmd_regenerate))
    app.add_handler(CommandHandler("help",       cmd_help))
    app.add_handler(CallbackQueryHandler(handle_button))

    # Schedule Monday 8am SGT (SGT = UTC+8, so 00:00 UTC)
    app.job_queue.run_daily(
        send_weekly_plan,
        time=time(hour=0, minute=0),   # 00:00 UTC = 08:00 SGT
        days=(0,),                     # 0 = Monday
        name="weekly_plan",
    )

    log.info("Bot is running. Press Ctrl+C to stop.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
