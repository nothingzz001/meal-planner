"""
meals.py — Recipe and ingredient data for the Family Meal Planner bot.

This file reads directly from Ingredient.xlsx (placed in the same folder).
To update recipes or ingredients, just edit the spreadsheet — no code changes needed.

Spreadsheet columns expected (from row 13 onwards):
  B = Recipe name
  C = Ingredient 1
  D = Ingredient 2
  E = Ingredient 3
  F = Ingredient 4
"""

import os
import random
from openpyxl import load_workbook

# ── Path to the spreadsheet (same folder as this file) ──────────────────────
SPREADSHEET = os.path.join(os.path.dirname(__file__), "Ingredient.xlsx")


def load_recipes() -> dict:
    """
    Reads Ingredient.xlsx and returns a dict structured as:
    {
        "protein": [ {"name": "Soy sauce Chicken", "ing": ["Chicken Thighs"]}, ... ],
        "veg":     [ {"name": "Spinach", "ing": ["Spinach", "Carrot", "Mushrooms"]}, ... ],
        "soup":    [ {"name": "Black bean", "ing": ["Pork Ribs", ...]}, ... ],
        "fruit":   [ {"name": "Banana", "ing": ["Banana"]}, ... ],
        "carbs":   [ {"name": "Oats", "ing": ["Oats"]}, ... ],
    }
    """
    wb = load_workbook(SPREADSHEET, read_only=True, data_only=True)
    ws = wb.active

    recipes = {"protein": [], "veg": [], "soup": [], "fruit": [], "carbs": []}
    current_section = None

    SECTION_MAP = {
        "protein":  "protein",
        "vegetable": "veg",
        "soup":     "soup",
    }

    # Fruits — weekday pool and weekend pool are defined separately in generate_week
    # but we still load them all here so the HTML planner can display them
    FRUITS = [
        "Banana", "Dragonfruit", "Blueberries", "Apple", "Pear",
        "Raspberry", "Strawberry", "Avocado banana",
    ]
    CARBS = ["Brown Rice", "Pasta", "Oats", "Meesua", "Pasta with prawn"]

    for row in ws.iter_rows(min_row=13, values_only=True):
        b = str(row[1]).strip() if row[1] else ""
        c = str(row[2]).strip() if row[2] else ""

        if b.lower() in SECTION_MAP:
            current_section = SECTION_MAP[b.lower()]
            continue

        if not b or b.lower() in ("recipe", "ingredient 1", "none"):
            continue

        if b.startswith("="):
            b = "Spinach"

        if current_section:
            ing = [str(row[i]).strip() for i in range(2, 6)
                   if row[i] and str(row[i]).strip().lower() != "none"]
            names = [r["name"] for r in recipes[current_section]]
            if b not in names:
                recipes[current_section].append({"name": b, "ing": ing})

    for f in FRUITS:
        recipes["fruit"].append({"name": f, "ing": [f]})
    for c_ in CARBS:
        recipes["carbs"].append({"name": c_, "ing": [c_]})

    wb.close()
    return recipes


# ── Weekly rotation logic ────────────────────────────────────────────────────

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
IS_WEEKEND = {"Saturday": True, "Sunday": True}


def generate_week(recipes: dict) -> dict:
    """
    Generates a full week of meals following family rules:

    SOUP RULE: exactly 1 chicken drumstick soup (Dun Ji Tang) on Monday,
               exactly 2 pork rib soups spread across Tue–Sun.

    FIXED DAYS:
      Monday  — Lunch: Chicken Breast + veg
                Dinner: Dun Ji Tang (chicken drumstick soup) + protein + veg
      Tuesday — Lunch: Salmon egg + veg
                Dinner: protein + veg + 1st pork rib soup
      Wednesday — Lunch: protein + veg
                  Dinner: 2nd pork rib soup + protein + veg
      Thu–Fri — Lunch + Dinner: varied protein + veg, no soup
      Sat/Sun — Lunch: one of them gets Pasta with prawn (1 dish only)
                Dinner: protein + veg (no soup on weekends)

    FRUIT RULES:
      Mon+Tue  → fruit from weekday pool (NO apple on Monday)
      Wed+Thu  → different fruit from weekday pool
      Fri      → fruit from weekday pool (NO apple on Friday)
      Sat+Sun  → weekend fruits only: Raspberry, Blueberries, Strawberry, Avocado banana
      Weekend breakfast: Oats + weekend fruit

    VEG: Broccoli 3–4x per week (weighted), other veg max 2x each.
    """

    # ── Helpers ──────────────────────────────────────────────────────────────

    def rnd(pool, excl=[]):
        available = [r for r in pool if r["name"] not in excl]
        return random.choice(available if available else pool)

    def dish(type_, name):
        for r in recipes.get(type_, []):
            if r["name"] == name:
                return {"type": type_, "name": name, "ing": r["ing"]}
        return {"type": type_, "name": name, "ing": []}

    def weighted_veg(excl=[]):
        pool = []
        for r in recipes["veg"]:
            if r["name"] not in excl:
                w = 4 if r["name"].lower() in ("brocoli", "broccoli") else 1
                pool.extend([r] * w)
        return random.choice(pool if pool else recipes["veg"])

    used_veg     = {}  # name → count; broccoli up to 4x, others up to 2x
    used_protein = []

    def next_veg(excl=[]):
        over = [n for n, c in used_veg.items()
                if (c >= 4 if n.lower() in ("brocoli", "broccoli") else c >= 2)]
        r = weighted_veg(excl=over + excl)
        used_veg[r["name"]] = used_veg.get(r["name"], 0) + 1
        return {"type": "veg", **r}

    def next_protein(excl=[]):
        r = rnd(recipes["protein"], used_protein + excl)
        used_protein.append(r["name"])
        if len(used_protein) > 3: used_protein.pop(0)
        return {"type": "protein", **r}

    # ── Fruit rotation ───────────────────────────────────────────────────────

    WEEKDAY_FRUITS = [f for f in recipes["fruit"]
                      if f["name"] not in ("Raspberry", "Strawberry",
                                           "Avocado banana", "Blueberries")]
    WEEKEND_FRUITS = [f for f in recipes["fruit"]
                      if f["name"] in ("Raspberry", "Blueberries",
                                       "Strawberry", "Avocado banana")]

    # Weekday: 3 slots — Mon/Tue, Wed/Thu, Fri
    # Mon and Fri cannot be Apple
    non_apple = [f for f in WEEKDAY_FRUITS if f["name"] != "Apple"]
    random.shuffle(non_apple)

    f_mon = non_apple[0]                          # Mon/Tue — no apple
    f_wed = rnd(WEEKDAY_FRUITS, [f_mon["name"]])  # Wed/Thu — any weekday fruit
    # Fri — no apple, different from Mon fruit if possible
    f_fri = rnd(non_apple, [f_mon["name"]])

    # Weekend — pick 1 from weekend pool for Sat+Sun
    f_wknd = random.choice(WEEKEND_FRUITS)

    fruit_by_day = {
        "Monday":    f_mon,
        "Tuesday":   f_mon,
        "Wednesday": f_wed,
        "Thursday":  f_wed,
        "Friday":    f_fri,
        "Saturday":  f_wknd,
        "Sunday":    f_wknd,
    }

    def breakfast(day):
        fruit = fruit_by_day[day]
        fd = {"type": "fruit", "name": fruit["name"], "ing": fruit["ing"]}
        if IS_WEEKEND.get(day):
            oats = {"type": "carbs", "name": "Oats",
                    "ing": ["Oats", fruit["name"]]}
            return [oats, fd]
        return [fd]

    # ── Soup rotation ────────────────────────────────────────────────────────
    # Rule: 1x Dun Ji Tang (Monday), 2x pork rib soups (Tue + Wed)

    pork_soups = [r for r in recipes["soup"] if "Pork Ribs" in r["ing"]]
    random.shuffle(pork_soups)
    pork_soup_1 = pork_soups[0]   # Tuesday dinner
    pork_soup_2 = pork_soups[1]   # Wednesday dinner

    # ── Pasta with prawn weekend lunch ───────────────────────────────────────
    # Randomly assign to Saturday or Sunday lunch (only 1 day)
    pasta_day = random.choice(["Saturday", "Sunday"])

    # ── Build plan ───────────────────────────────────────────────────────────

    plan = {}
    for day in DAYS:
        plan[day] = {
            "out": {"Breakfast": False, "Lunch": False, "Dinner": False},
            "Breakfast": breakfast(day),
            "Lunch":  [],
            "Dinner": [],
        }

    # Monday
    plan["Monday"]["Lunch"]  = [dish("protein", "Chicken Breast"), next_veg()]
    plan["Monday"]["Dinner"] = [dish("soup", "Dun Ji Tang"),
                                next_protein(excl=["Chicken Breast"]),
                                next_veg()]

    # Tuesday — Salmon egg lunch, pork rib soup 1 at dinner
    plan["Tuesday"]["Lunch"]  = [next_protein(excl=["Salmon egg"]), next_veg()]
    plan["Tuesday"]["Dinner"] = [dish("protein", "Salmon egg"),
                                 next_veg(),
                                 {"type": "soup", **pork_soup_1}]

    # Wednesday — pork rib soup 2 at dinner
    plan["Wednesday"]["Lunch"]  = [next_protein(), next_veg()]
    plan["Wednesday"]["Dinner"] = [{"type": "soup", **pork_soup_2},
                                   next_protein(),
                                   next_veg()]

    # Thursday + Friday — no soup
    for day in ["Thursday", "Friday"]:
        lp = next_protein()
        plan[day]["Lunch"]  = [lp, next_veg()]
        plan[day]["Dinner"] = [next_protein(excl=[lp["name"]]), next_veg()]

    # Saturday + Sunday
    for day in ["Saturday", "Sunday"]:
        if day == pasta_day:
            # Pasta with prawn — single dish lunch
            plan[day]["Lunch"] = [{"type": "carbs",
                                   "name": "Pasta with prawn",
                                   "ing":  ["Pasta", "Prawn"]}]
        else:
            lp = next_protein()
            plan[day]["Lunch"] = [lp, next_veg()]

        # Weekend dinner — protein + veg, no soup
        dp = next_protein()
        plan[day]["Dinner"] = [dp, next_veg()]

    return plan


# ── Grocery split logic ───────────────────────────────────────────────────────

MON_DAYS = ["Monday", "Tuesday", "Wednesday"]
THU_DAYS = ["Thursday", "Friday", "Saturday", "Sunday"]


def build_grocery(plan: dict) -> dict:
    """
    Returns two sorted ingredient lists split by shopping day.
    Dining-out meals are excluded.
    """
    def collect(days):
        items = set()
        for day in days:
            data = plan[day]
            for meal in ["Breakfast", "Lunch", "Dinner"]:
                if data["out"].get(meal):
                    continue
                for dish_ in data.get(meal, []):
                    ings = dish_.get("ing") or [dish_["name"]]
                    for i in ings:
                        if i:
                            items.add(i.strip())
        return sorted(items)

    return {"mon": collect(MON_DAYS), "thu": collect(THU_DAYS)}
