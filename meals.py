"""
meals.py — Recipe and ingredient data for the Family Meal Planner bot.

Reads directly from Ingredient.xlsx. Edit the spreadsheet to update recipes.

Spreadsheet layout:
  Column B = Recipe name / section header
  Column C-F = Ingredients
  Column F = Fruits list
  Column G = Carbs list
"""

import os
import random
from openpyxl import load_workbook

SPREADSHEET = os.path.join(os.path.dirname(__file__), "Ingredient.xlsx")


def load_recipes() -> dict:
    wb = load_workbook(SPREADSHEET, read_only=True, data_only=True)
    ws = wb.active

    recipes = {"protein": [], "veg": [], "soup": [], "fruit": [], "carbs": []}
    current_section = None
    SECTION_MAP = {"protein": "protein", "vegetable": "veg", "soup": "soup"}

    fruits_seen = set()
    carbs_seen  = set()

    # Weekend-only fruits — ensure they're always available even if not in Excel
    WEEKEND_FRUITS = ["Raspberry", "Strawberry", "Avocado banana", "Blueberries"]

    for row in ws.iter_rows(min_row=3, values_only=True):
        b = str(row[1]).strip() if row[1] else ""

        # Collect fruits from column F (index 5)
        f = str(row[5]).strip() if row[5] else ""
        if f and f.lower() not in ("fruits", "none", ""):
            fruits_seen.add(f)

        # Collect carbs from column G (index 6)
        c = str(row[6]).strip() if row[6] else ""
        if c and c.lower() not in ("carbs", "carbs ", "none", ""):
            carbs_seen.add(c)

        if b.lower() in SECTION_MAP:
            current_section = SECTION_MAP[b.lower()]
            continue

        if not b or b.lower() in ("recipe", "ingredient 1", "none",
                                   "ingredients", "meat / protein"):
            continue

        if b.startswith("="):
            b = "Spinach"

        if current_section:
            ing = [str(row[i]).strip() for i in range(2, 6)
                   if row[i] and str(row[i]).strip().lower() not in ("none", "")]
            names = [r["name"] for r in recipes[current_section]]
            if b not in names:
                recipes[current_section].append({"name": b, "ing": ing})

    # Build fruit list from Excel
    for f in sorted(fruits_seen):
        f = f.strip()
        if f:
            recipes["fruit"].append({"name": f, "ing": [f]})

    # Ensure weekend fruits are always present
    existing = [r["name"] for r in recipes["fruit"]]
    for wf in WEEKEND_FRUITS:
        if wf not in existing:
            recipes["fruit"].append({"name": wf, "ing": [wf]})

    # Build carbs list
    for c in sorted(carbs_seen):
        c = c.strip()
        if c:
            recipes["carbs"].append({"name": c, "ing": [c]})

    # Ensure Pasta with prawn is always present
    carb_names = [r["name"] for r in recipes["carbs"]]
    if "Pasta with prawn" not in carb_names:
        recipes["carbs"].append({"name": "Pasta with prawn", "ing": ["Pasta", "Prawn"]})

    wb.close()
    return recipes


DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
IS_WEEKEND = {"Saturday": True, "Sunday": True}


def generate_week(recipes: dict) -> dict:
    """
    Weekly meal plan following family rotation:

    DINNER ROTATION (fixed):
      Monday    — Dun Ji Tang (chicken soup) + protein + veg
      Tuesday   — Salmon egg + veg + pork rib soup
      Wednesday — Pork/chicken dish + veg + egg dish
      Thursday  — Pork rib soup + chicken or egg protein + veg
      Friday    — Varied protein + veg
      Saturday  — Protein + veg (no soup)
      Sunday    — Protein + veg (no soup)

    LUNCH: random protein + veg every day
           Saturday lunch = Pasta with prawn (1 dish only)

    SOUP: exactly 1 Dun Ji Tang (Monday), 2 pork rib soups (Tue + Thu)

    FRUIT:
      Weekdays  — rotate 3 fruits across the week (Mon/Tue, Wed/Thu, Fri)
      Mon + Fri — never Apple
      Weekend   — Raspberry, Blueberries, Strawberry or Avocado banana only

    VEG: Broccoli 3–4x/week, other veg max 2x each
    """

    # ── Helpers ──────────────────────────────────────────────────────────────

    def rnd(pool, excl=[]):
        available = [r for r in pool if r["name"] not in excl]
        return random.choice(available if available else pool)

    def find(type_, name):
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

    used_veg     = {}
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
        if len(used_protein) > 3:
            used_protein.pop(0)
        return {"type": "protein", **r}

    # ── Fruit pools ───────────────────────────────────────────────────────────

    WEEKEND_NAMES = {"Raspberry", "Strawberry", "Avocado banana", "Blueberries"}

    weekday_fruits = [f for f in recipes["fruit"]
                      if f["name"] not in WEEKEND_NAMES]
    weekend_fruits = [f for f in recipes["fruit"]
                      if f["name"] in WEEKEND_NAMES]

    if not weekend_fruits:
        weekend_fruits = recipes["fruit"]  # fallback

    non_apple_weekday = [f for f in weekday_fruits if f["name"] != "Apple"]
    if not non_apple_weekday:
        non_apple_weekday = weekday_fruits

    # Mon/Tue fruit — no apple
    f_mon = random.choice(non_apple_weekday)
    # Wed/Thu fruit — different from Mon
    f_wed = rnd(weekday_fruits, [f_mon["name"]])
    # Fri fruit — no apple, try different from Mon
    f_fri_pool = [f for f in non_apple_weekday if f["name"] != f_mon["name"]]
    f_fri = random.choice(f_fri_pool if f_fri_pool else non_apple_weekday)
    # Weekend — from weekend pool
    f_wknd = random.choice(weekend_fruits)

    fruit_by_day = {
        "Monday": f_mon, "Tuesday": f_mon,
        "Wednesday": f_wed, "Thursday": f_wed,
        "Friday": f_fri,
        "Saturday": f_wknd, "Sunday": f_wknd,
    }

    def breakfast(day):
        fruit = fruit_by_day[day]
        fd = {"type": "fruit", "name": fruit["name"], "ing": fruit["ing"]}
        if IS_WEEKEND.get(day):
            return [{"type": "carbs", "name": "Oats",
                     "ing": ["Oats", fruit["name"]]}, fd]
        return [fd]

    # ── Soup selection ────────────────────────────────────────────────────────
    # 1x Dun Ji Tang (Monday), 2x pork rib soups (Tuesday + Thursday)

    pork_soups = [r for r in recipes["soup"] if "Pork Ribs" in r["ing"]]
    random.shuffle(pork_soups)
    pork_soup_tue = pork_soups[0]
    pork_soup_thu = pork_soups[1] if len(pork_soups) > 1 else pork_soups[0]

    # ── Egg proteins (for Wed/Thu dinner rule) ────────────────────────────────
    egg_proteins = [r for r in recipes["protein"]
                    if "Eggs" in r["ing"] or "egg" in r["name"].lower()]
    pork_proteins = [r for r in recipes["protein"]
                     if any(p in r["ing"] for p in
                            ["Minced Pork", "Pork Ribs", "Chicken Thighs",
                             "Chicken Breast", "Chicken drumstick"])]

    # ── Build plan ────────────────────────────────────────────────────────────

    plan = {}
    for day in DAYS:
        plan[day] = {
            "out": {"Breakfast": False, "Lunch": False, "Dinner": False},
            "Breakfast": breakfast(day),
            "Lunch":  [],
            "Dinner": [],
        }

    # ── Monday ────────────────────────────────────────────────────────────────
    # Dinner: Dun Ji Tang + protein + veg
    plan["Monday"]["Lunch"]  = [next_protein(excl=["Chicken Breast"]), next_veg()]
    plan["Monday"]["Dinner"] = [
        find("soup", "Dun Ji Tang"),
        find("protein", "Chicken Breast"),
        next_veg(),
    ]

    # ── Tuesday ───────────────────────────────────────────────────────────────
    # Dinner: Salmon egg + veg + pork rib soup
    plan["Tuesday"]["Lunch"]  = [next_protein(excl=["Salmon egg"]), next_veg()]
    plan["Tuesday"]["Dinner"] = [
        find("protein", "Salmon egg"),
        next_veg(),
        {"type": "soup", **pork_soup_tue},
    ]

    # ── Wednesday ─────────────────────────────────────────────────────────────
    # Dinner: pork/chicken dish + veg + egg dish
    wed_pork = rnd(pork_proteins, ["Chicken Breast", "Salmon egg"])
    wed_egg  = rnd(egg_proteins,  [wed_pork["name"]])
    plan["Wednesday"]["Lunch"]  = [next_protein(), next_veg()]
    plan["Wednesday"]["Dinner"] = [
        {"type": "protein", **wed_pork},
        next_veg(),
        {"type": "protein", **wed_egg},
    ]

    # ── Thursday ──────────────────────────────────────────────────────────────
    # Dinner: pork rib soup + chicken or egg protein + veg
    thu_protein_pool = [r for r in recipes["protein"]
                        if any(p in r["ing"] for p in
                               ["Chicken Thighs", "Chicken Breast",
                                "Chicken drumstick", "Eggs"])]
    thu_protein = rnd(thu_protein_pool, [wed_pork["name"], wed_egg["name"]])
    plan["Thursday"]["Lunch"]  = [next_protein(), next_veg()]
    plan["Thursday"]["Dinner"] = [
        {"type": "soup", **pork_soup_thu},
        {"type": "protein", **thu_protein},
        next_veg(),
    ]

    # ── Friday ────────────────────────────────────────────────────────────────
    # Dinner: varied protein + veg (no soup)
    plan["Friday"]["Lunch"]  = [next_protein(), next_veg()]
    plan["Friday"]["Dinner"] = [next_protein(), next_veg()]

    # ── Saturday ──────────────────────────────────────────────────────────────
    # Lunch: Pasta with prawn only (1 dish)
    # Dinner: protein + veg
    plan["Saturday"]["Lunch"]  = [{"type": "carbs",
                                    "name": "Pasta with prawn",
                                    "ing":  ["Pasta", "Prawn"]}]
    plan["Saturday"]["Dinner"] = [next_protein(), next_veg()]

    # ── Sunday ────────────────────────────────────────────────────────────────
    # Lunch + Dinner: protein + veg
    plan["Sunday"]["Lunch"]  = [next_protein(), next_veg()]
    plan["Sunday"]["Dinner"] = [next_protein(), next_veg()]

    return plan


# ── Grocery split ─────────────────────────────────────────────────────────────

MON_DAYS = ["Monday", "Tuesday", "Wednesday"]
THU_DAYS = ["Thursday", "Friday", "Saturday", "Sunday"]


def build_grocery(plan: dict) -> dict:
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
