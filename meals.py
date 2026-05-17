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
        "soup":    [ {"name": "Black bean", "ing": ["Pork Ribs", "Black bean", "Lotus root"]}, ... ],
        "fruit":   [ {"name": "Banana", "ing": ["Banana"]}, ... ],
        "carbs":   [ {"name": "Oats", "ing": ["Oats"]}, ... ],
    }
    """
    wb = load_workbook(SPREADSHEET, read_only=True, data_only=True)
    ws = wb.active

    recipes = {"protein": [], "veg": [], "soup": [], "fruit": [], "carbs": []}
    current_section = None

    # Section headers as they appear in column B of the spreadsheet
    SECTION_MAP = {
        "protein": "protein",
        "vegetable": "veg",
        "soup": "soup",
    }

    # Fruits and carbs are read from the ingredients master list (columns F and G)
    FRUITS = ["Banana", "Dragonfruit", "Blueberries", "Apple", "Pear"]
    CARBS  = ["Brown Rice", "Pasta", "Oats", "Meesua"]

    for row in ws.iter_rows(min_row=13, values_only=True):
        b = str(row[1]).strip() if row[1] else ""
        c = str(row[2]).strip() if row[2] else ""

        # Detect section header rows (e.g. "Protein", "Vegetable", "Soup")
        if b.lower() in SECTION_MAP:
            current_section = SECTION_MAP[b.lower()]
            continue

        # Skip blank rows or header rows we don't need
        if not b or b.lower() in ("recipe", "ingredient 1", "none"):
            continue

        # Skip the broken formula cell (=C31 came through as "=C31")
        if b.startswith("="):
            b = "Spinach"  # The formula references Spinach — treat it as such

        if current_section:
            # Collect up to 4 ingredients (columns C–F → index 2–5)
            ing = [str(row[i]).strip() for i in range(2, 6)
                   if row[i] and str(row[i]).strip().lower() != "none"]
            # Avoid duplicates within a section
            names = [r["name"] for r in recipes[current_section]]
            if b not in names:
                recipes[current_section].append({"name": b, "ing": ing})

    # Add fruits and carbs manually (they live in the master ingredient list, not recipe block)
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
    Auto-generates a full week of meals following the family's typical rotation:

      Monday    — Lunch: chicken breast + veg | Dinner: Dun Ji Tang + tofu minced pork + veg
      Tuesday   — Lunch: Salmon egg + veg     | Dinner: protein + veg + pork rib soup
      Wednesday — Lunch: protein + veg        | Dinner: pork rib soup + protein + veg
      Thu–Sun   — Varied rotation, no repeats within the same day

    Breakfast:
      Weekday  → 1 fruit (same fruit all week for easy shopping)
      Weekend  → Oats + same fruit

    Returns a dict keyed by day name, each value:
    {
        "out": {"Breakfast": False, "Lunch": False, "Dinner": False},
        "Breakfast": [ {"type": "fruit", "name": "Banana", "ing": ["Banana"]}, ... ],
        "Lunch":     [ ... ],
        "Dinner":    [ ... ],
    }
    """

    def rnd(pool: list, exclude: list = []) -> dict:
        """Pick a random recipe from pool, avoiding recently used ones."""
        available = [r for r in pool if r["name"] not in exclude]
        if not available:
            available = pool  # fallback: allow repeats if pool is exhausted
        return random.choice(available)

    def weighted_veg(exclude: list = []) -> dict:
        """
        Pick a veg with weighted probability.
        Broccoli gets 4x weight so it appears ~3-4 times a week.
        exclude list prevents same veg appearing more than twice in a week.
        """
        weighted = []
        for r in recipes["veg"]:
            if r["name"] not in exclude:
                weight = 4 if r["name"].lower() in ("brocoli", "broccoli") else 1
                weighted.extend([r] * weight)
        if not weighted:
            weighted = recipes["veg"]
        return random.choice(weighted)

    def dish(type_: str, name: str) -> dict:
        """Find a recipe by name and return a dish dict."""
        for r in recipes.get(type_, []):
            if r["name"] == name:
                return {"type": type_, "name": name, "ing": r["ing"]}
        # Fallback for custom/unknown names
        return {"type": type_, "name": name, "ing": []}

    # Rotate fruits: pick 3 different fruits, each lasts 2-3 days
    # e.g. Mon+Tue = Banana, Wed+Thu = Dragonfruit, Fri+Sat+Sun = Blueberries
    fruit_pool = recipes["fruit"][:]
    random.shuffle(fruit_pool)
    # Pick 3 distinct fruits
    f1, f2, f3 = fruit_pool[0], fruit_pool[1], fruit_pool[2]
    # Assign: first fruit Mon+Tue, second Wed+Thu, third Fri+Sat+Sun
    fruit_by_day = {
        "Monday":    f1,
        "Tuesday":   f1,
        "Wednesday": f2,
        "Thursday":  f2,
        "Friday":    f3,
        "Saturday":  f3,
        "Sunday":    f3,
    }

    # Pork rib soups only (for Wed/Tue dinner rotation)
    pork_soups = [r for r in recipes["soup"]
                  if "Pork Ribs" in r["ing"]]

    used_veg     = {}   # name -> count this week; veg allowed max 2 times
    used_protein = []
    used_soup    = []

    def next_veg(excl=[]):
        # Broccoli can appear up to 4x, other veg up to 2x
        over_limit = [
            name for name, cnt in used_veg.items()
            if (cnt >= 4 if name.lower() in ("brocoli","broccoli") else cnt >= 2)
        ]
        r = weighted_veg(exclude=over_limit + excl)
        used_veg[r["name"]] = used_veg.get(r["name"], 0) + 1
        return {"type": "veg", **r}

    def next_protein(excl=[]):
        r = rnd(recipes["protein"], used_protein + excl)
        used_protein.append(r["name"])
        if len(used_protein) > 3: used_protein.pop(0)
        return {"type": "protein", **r}

    def next_soup(pool=None, excl=[]):
        src = pool or recipes["soup"]
        r = rnd(src, used_soup + excl)
        used_soup.append(r["name"])
        if len(used_soup) > 2: used_soup.pop(0)
        return {"type": "soup", **r}

    def breakfast(day):
        fruit = fruit_by_day[day]
        fruit_dish = {"type": "fruit", "name": fruit["name"], "ing": fruit["ing"]}
        if IS_WEEKEND.get(day):
            oats = {"type": "carbs", "name": "Oats", "ing": ["Oats", fruit["name"]]}
            return [oats, fruit_dish]
        return [fruit_dish]

    plan = {}
    for day in DAYS:
        plan[day] = {
            "out": {"Breakfast": False, "Lunch": False, "Dinner": False},
            "Breakfast": breakfast(day),
            "Lunch": [],
            "Dinner": [],
        }

    # ── Monday ───────────────────────────────────────────────────────────────
    plan["Monday"]["Lunch"] = [
        dish("protein", "Chicken Breast"),
        next_veg(),
    ]
    plan["Monday"]["Dinner"] = [
        dish("soup", "Dun Ji Tang"),
        dish("protein", "Tofu Minced Pork"),
        next_veg(),
    ]

    # ── Tuesday ──────────────────────────────────────────────────────────────
    plan["Tuesday"]["Lunch"] = [
        dish("protein", "Salmon egg"),
        next_veg(),
    ]
    plan["Tuesday"]["Dinner"] = [
        next_protein(excl=["Salmon egg"]),
        next_veg(),
        next_soup(pool=pork_soups, excl=["Dun Ji Tang"]),
    ]

    # ── Wednesday ────────────────────────────────────────────────────────────
    plan["Wednesday"]["Lunch"] = [
        next_protein(),
        next_veg(),
    ]
    plan["Wednesday"]["Dinner"] = [
        next_soup(pool=pork_soups),
        next_protein(),
        next_veg(),
    ]

    # ── Thursday – Sunday: varied ─────────────────────────────────────────────
    for day in ["Thursday", "Friday", "Saturday", "Sunday"]:
        lp = next_protein()
        plan[day]["Lunch"]  = [lp, next_veg()]
        plan[day]["Dinner"] = [
            next_soup(),
            next_protein(excl=[lp["name"]]),
            next_veg(),
        ]

    return plan


# ── Grocery split logic ───────────────────────────────────────────────────────

MON_DAYS = ["Monday", "Tuesday", "Wednesday"]
THU_DAYS = ["Thursday", "Friday", "Saturday", "Sunday"]


def build_grocery(plan: dict) -> dict:
    """
    Returns two sorted ingredient lists:
    {
        "mon": ["Banana", "Carrot", ...],   # covers Mon–Wed meals
        "thu": ["Broccoli", "Pork Ribs", ...],  # covers Thu–Sun meals
    }
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
