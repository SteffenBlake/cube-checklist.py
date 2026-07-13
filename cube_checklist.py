#!/usr/bin/env python3
"""
cube_checklist.py

Interactive TUI (curses) that computes a Magic: The Gathering cube design
checklist, based on the default design skeleton described in Mark
Rosewater's "Nuts & Bolts #13: Design Skeleton Revisited" article
(101 commons + 80 uncommons = 181-card baseline set).

Usage:
    python3 cube_checklist.py <output_path.md>

All arithmetic (summing common+uncommon ranges, applying the Y/X
multiplier, rounding, splitting multicolor budgets, etc.) is performed by
Python itself -- never estimated by hand -- to guarantee correctness.
"""

import argparse
import curses
import sys
import textwrap

BASELINE_SET_SIZE = 181  # 101 commons + 80 uncommons, per the article

# ---------------------------------------------------------------------------
# Article data
# ---------------------------------------------------------------------------
# Each color entry contains:
#   creature_curve: list of (mv_label_or_list, count) at common, and uncommon
#       where mv_label is either an int (fixed MV) or a list of ints
#       (ambiguous "1 or 2 MV" -> [1, 2]); "Any MV" -> None (Flexible bucket)
#   keywords: dict keyword -> (low, high) combined range description pieces
#       stored separately per rarity, combined by summation later
#   spells: list of spell slot descriptions (each is one card slot)

COLORS = {
    "White": {
        "common_creatures": [
            (1, "CW01"), ([1, 2], "CW02"), (2, "CW03"), (2, "CW04"), (2, "CW05"),
            ([2, 3], "CW06"), (3, "CW07"), (3, "CW08"), (4, "CW09"), (4, "CW10"),
            (5, "CW11"), ([5, 6], "CW12"),
        ],
        "uncommon_creatures": [
            (1, "UW01"), (2, "UW02"), ([2, 3], "UW03"), (3, "UW04"), (4, "UW05"),
            (5, "UW06"), (None, "UW07"), (None, "UW08"),
        ],
        "keywords_common": {
            "Defender": (0, 1), "First Strike": (1, 1), "Flash": (0, 1),
            "Flying": (2, 3), "Indestructible": (0, 1), "Lifelink": (1, 1),
            "Vigilance": (1, 1),
        },
        "keywords_uncommon": {
            "Defender": (0, 1), "Double Strike": (0, 1), "First Strike": (0, 1),
            "Flash": (0, 1), "Flying": (2, 2), "Indestructible": (0, 1),
            "Lifelink": (1, 1), "Vigilance": (1, 1),
        },
        "common_spells": [
            "Small removal (usually damage to an attacker or blocker)",
            "Can't attack or block (sometimes also stops activated abilities, usually an Aura)",
            "Destroy large/tapped creature",
            "Combat trick (usually +2/+2 or smaller)",
            "Positive Aura/Equipment",
            "Go-wide team-pump effect",
            "Destroy artifact/enchantment",
        ],
        "uncommon_spells": [
            "Creature removal (usually very efficient)",
            "Non-creature",
            "Non-creature",
            "Non-creature",
            "Non-creature",
        ],
    },
    "Blue": {
        "common_creatures": [
            (1, "CU01"), (2, "CU02"), (2, "CU03"), (3, "CU04"), (3, "CU05"),
            (4, "CU06"), (4, "CU07"), (5, "CU08"), (None, "CU09"),
        ],
        "uncommon_creatures": [
            ([1, 2], "UU01"), (2, "UU02"), (3, "UU03"), (4, "UU04"), (5, "UU05"),
            (None, "UU06"), (None, "UU07"),
        ],
        "keywords_common": {
            "Defender": (0, 1), "Flash": (1, 1), "Flying": (3, 3),
            "Hexproof": (0, 1),
        },
        "keywords_uncommon": {
            "Defender": (0, 1), "Flash": (0, 1), "Flying": (2, 3),
            "Hexproof": (0, 1),
        },
        "common_spells": [
            "Either 0 power creature, creature with defender, or non-creature",
            "Counterspell that can counter anything (hard counter)",
            "Counterspell with some restriction (soft counter)",
            "Lockdown Aura",
            "Card drawing (usually no more than three cards)",
            "Cantrip/card filtering",
            "Bounce spell (usually returning a creature to hand)",
            "Positive Aura or combat trick",
            "Disrupt opposing creatures (freezing, tapping, lowering power, etc.)",
            "Anything",
        ],
        "uncommon_spells": [
            "Card draw",
            "Counterspell",
            "Non-creature",
            "Non-creature",
            "Non-creature",
            "Non-creature",
        ],
    },
    "Black": {
        "common_creatures": [
            (1, "CB01"), (2, "CB02"), (2, "CB03"), ([2, 3], "CB04"), (3, "CB05"),
            (3, "CB06"), (4, "CB07"), (4, "CB08"), (5, "CB09"), (None, "CB10"),
        ],
        "uncommon_creatures": [
            ([1, 2], "UB01"), (2, "UB02"), (3, "UB03"), (4, "UB04"), (5, "UB05"),
            (None, "UB06"), (None, "UB07"),
        ],
        "keywords_common": {
            "Deathtouch": (1, 1), "Defender": (0, 1), "Flash": (1, 1),
            "Flying": (1, 1), "Haste": (0, 1), "Indestructible": (0, 1),
            "Lifelink": (1, 1), "Menace": (1, 1),
        },
        "keywords_uncommon": {
            "Deathtouch": (1, 1), "Defender": (0, 1), "Flash": (0, 1),
            "Flying": (1, 1), "Indestructible": (0, 1), "Lifelink": (1, 1),
            "Menace": (1, 1),
        },
        "common_spells": [
            "Removal spell, can kill anything",
            "Removal spell, can kill small things",
            "Removal spell, edict/forced sacrifice, or conditional",
            "Removal spell, limitations, different from the others, usually weaker",
            "Card draw (for some resource in addition to mana, usually life)",
            "Return creature card from graveyard to hand (one or two creatures)",
            "Discard (one or two cards, if you choose what gets discarded)",
            "Positive Aura or combat trick",
            "Anything",
        ],
        "uncommon_spells": [
            "Removal",
            "Reanimation",
            "Non-creature",
            "Non-creature",
            "Non-creature",
            "Non-creature",
        ],
    },
    "Red": {
        "common_creatures": [
            (1, "CR01"), (2, "CR02"), (2, "CR03"), (2, "CR04"), (3, "CR05"),
            (3, "CR06"), (4, "CR07"), (4, "CR08"), (5, "CR09"), (None, "CR10"),
        ],
        "uncommon_creatures": [
            ([1, 2], "UR01"), (2, "UR02"), (3, "UR03"), (4, "UR04"), (None, "UR05"),
            (None, "UR06"), (None, "UR07"),
        ],
        "keywords_common": {
            "Defender": (0, 1), "First Strike": (1, 1), "Haste": (1, 2),
            "Menace": (1, 1), "Reach": (0, 1), "Trample": (1, 1),
        },
        "keywords_uncommon": {
            "Defender": (0, 1), "Double Strike": (0, 1), "Haste": (1, 1),
            "First Strike": (0, 1), "Menace": (1, 1), "Reach": (0, 1),
            "Trample": (1, 2),
        },
        "common_spells": [
            "Efficient direct-damage spell",
            "Other direct-damage spell",
            "Steal effect/inefficient direct damage",
            "Team pump (power greater than toughness)/land destruction",
            "Cantrip/card filtering (usually rummaging)",
            "Positive Aura or Equipment",
            "Combat trick",
            "Can't block/destroy artifact/direct damage to player",
            "Anything",
        ],
        "uncommon_spells": [
            "Direct damage (most often any target)",
            "Small sweeper/multi-target direct damage",
            "Non-creature",
            "Non-creature",
            "Non-creature",
            "Non-creature",
        ],
    },
    "Green": {
        "common_creatures": [
            (1, "CG01"), (2, "CG02"), (2, "CG03"), (3, "CG04"), (3, "CG05"),
            ([3, 4], "CG06"), (4, "CG07"), (4, "CG08"), (5, "CG09"), ([5, 6], "CG10"),
            (None, "CG11"),
        ],
        "uncommon_creatures": [
            ([1, 2], "UG01"), (2, "UG02"), (3, "UG03"), (4, "UG04"), (5, "UG05"),
            (None, "UG06"), (None, "UG07"), (None, "UG08"),
        ],
        "keywords_common": {
            "Deathtouch": (1, 1), "Defender": (0, 1), "Flash": (0, 1),
            "Haste": (1, 1), "Hexproof": (0, 1), "Reach": (1, 1),
            "Trample": (1, 2), "Vigilance": (1, 1),
        },
        "keywords_uncommon": {
            "Deathtouch": (0, 1), "Defender": (0, 1), "Flash": (0, 1),
            "Haste": (1, 1), "Indestructible": (0, 1), "Hexproof": (0, 1),
            "Reach": (0, 1), "Trample": (1, 1), "Vigilance": (1, 1),
        },
        "common_spells": [
            "Fight or bite (dealing damage equal to power)",
            "Power/toughness pumping (usually on an instant)",
            "Another combat trick",
            "Cantrip/card filtering",
            "Positive Aura or Equipment",
            "Anti-flying",
            "Mana ramp (usually fetching land, but sometimes an Aura)",
            "Artifact or enchantment destruction",
        ],
        "uncommon_spells": [
            "Mana ramp (usually creating more mana than common)",
            "Non-creature",
            "Non-creature",
            "Non-creature",
            "Non-creature",
        ],
    },
}

# Colorless artifact section (kept separate, always generated if selected)
ARTIFACTS = {
    "common_creatures": [([1, 2], "CA01"), ([3, 4], "CA02"), ([5, 6], "CA03")],
    "uncommon_creatures": [([1, 2], "UA01"), ([3, 4], "UA02"), ([5, 6], "UA03")],
    "keywords_common": {
        "Defender": (0, 1), "Flash": (0, 1), "Flying": (1, 1),
        "Haste": (0, 1), "Trample": (0, 1), "Vigilance": (0, 1),
    },
    "keywords_uncommon": {
        "Defender": (0, 1), "Flash": (0, 1), "Flying": (1, 1),
        "Haste": (0, 1), "Trample": (0, 1), "Vigilance": (0, 1),
    },
    "common_spells": ["Equipment", "Land fetching/color fixing", "Mana production"],
    "uncommon_spells": [
        "Removal (often conditional and usually costed somewhat inefficiently)",
        "Non-creature",
        "Non-creature",
    ],
}

# Counts baked into the article, used only to derive default percentages.
ARTIFACT_CARD_COUNT = 6 + 5          # common + uncommon artifact total
MULTICOLOR_CARD_COUNT = 10           # uncommon signpost cycle

DEFAULT_MULTICOLOR_PCT = round(MULTICOLOR_CARD_COUNT / BASELINE_SET_SIZE * 100)  # -> 6
DEFAULT_ARTIFACT_PCT = round(ARTIFACT_CARD_COUNT / BASELINE_SET_SIZE * 100)      # -> 6
DEFAULT_LAND_PCT = 8
DEFAULT_TOTAL = 450

ENEMY_DUALS = ["Simic", "Izzet", "Golgari", "Boros", "Orzhov"]
ALLY_DUALS = ["Azorius", "Dimir", "Rakdos", "Gruul", "Selesnya"]
ENEMY_TRIS = ["Abzan", "Jeskai", "Sultai", "Mardu", "Temur"]
ALLY_TRIS = ["Bant", "Esper", "Grixis", "Naya", "Jund"]


# ---------------------------------------------------------------------------
# Arithmetic helpers -- Python does ALL the counting, never estimated by hand
# ---------------------------------------------------------------------------

def multiplier(total, baseline=BASELINE_SET_SIZE):
    return total / baseline


def scale_round(value, mult):
    """Multiply then round half-away-from-zero (classic rounding)."""
    scaled = value * mult
    return int(scaled + 0.5) if scaled >= 0 else -int(-scaled + 0.5)


def scale_range(low, high, mult):
    return scale_round(low, mult), scale_round(high, mult)


def combine_ranges(r1, r2):
    """Sum two (low, high) ranges -- the common+uncommon combination step."""
    return r1[0] + r2[0], r1[1] + r2[1]


def raw_creature_bucket_totals(common_slots, uncommon_slots):
    """
    Combine common+uncommon creature slots into raw (pre-scale) float counts
    per MV bucket (int, or 'Flexible' for "Any MV"), splitting ambiguous
    "X or Y MV" slots evenly across their listed options. No scaling or
    rounding happens here -- this is the article's literal slot count.
    """
    raw_totals = {}

    def add_slots(slots):
        for mv, _code in slots:
            if mv is None:
                raw_totals["Flexible"] = raw_totals.get("Flexible", 0.0) + 1.0
            elif isinstance(mv, list):
                share = 1.0 / len(mv)
                for m in mv:
                    raw_totals[m] = raw_totals.get(m, 0.0) + share
            else:
                raw_totals[mv] = raw_totals.get(mv, 0.0) + 1.0

    add_slots(common_slots)
    add_slots(uncommon_slots)
    return raw_totals


def raw_spell_counts(common_spells, uncommon_spells):
    """
    Combine common+uncommon spell slots into raw (pre-scale) integer counts
    per description, preserving first-seen order.
    """
    counts = {}
    order = []
    for desc in common_spells + uncommon_spells:
        if desc not in counts:
            counts[desc] = 0
            order.append(desc)
        counts[desc] += 1
    return counts, order


def distribute_to_target(raw_values, target):
    """
    Proportionally scale a dict of raw (unrounded) counts so that the
    resulting INTEGER counts sum to EXACTLY `target`. Uses the largest-
    remainder method: floor every scaled value, then hand out the leftover
    units one at a time to the entries with the largest fractional
    remainder. This is what guarantees the "inner" totals (creature curve +
    spells) always add up perfectly to the "outer" total already carved out
    for that color/section -- nesting the math inward instead of letting
    each piece round independently and drift.
    """
    keys = list(raw_values.keys())
    if target <= 0 or not keys:
        return {k: 0 for k in keys}

    raw_total = sum(raw_values.values())
    if raw_total <= 0:
        return {k: 0 for k in keys}

    scale = target / raw_total
    scaled = {k: raw_values[k] * scale for k in keys}
    floors = {k: int(scaled[k]) for k in keys}
    remainder = target - sum(floors.values())

    # Hand out leftover units to the largest fractional remainders first.
    order_by_frac = sorted(keys, key=lambda k: (scaled[k] - floors[k]), reverse=True)
    result = dict(floors)
    for k in order_by_frac[:remainder]:
        result[k] += 1
    return result


def combine_keywords(kw_common, kw_uncommon, scale_factor):
    """Combine common+uncommon keyword ranges, then scale/round each bound."""
    keys = set(kw_common) | set(kw_uncommon)
    result = {}
    for k in sorted(keys):
        c = kw_common.get(k, (0, 0))
        u = kw_uncommon.get(k, (0, 0))
        combined = combine_ranges(c, u)
        result[k] = scale_range(combined[0], combined[1], scale_factor)
    return result


def build_color_section(raw_creature, raw_spell_map, spell_order, target):
    """
    Nest the "inner" creature-curve + spell slot counts inside the "outer"
    color/section total: combine both raw pools into ONE distribution pass
    against `target`, so creatures + spells always sum to exactly `target`
    (never drift from independent rounding).
    """
    combined_raw = {}
    for bucket, val in raw_creature.items():
        combined_raw[("creature", bucket)] = val
    for desc, val in raw_spell_map.items():
        combined_raw[("spell", desc)] = float(val)

    distributed = distribute_to_target(combined_raw, target)

    curve = {}
    for bucket in raw_creature:
        n = distributed[("creature", bucket)]
        if n > 0:
            curve[bucket] = n

    spells = []
    for desc in spell_order:
        n = distributed[("spell", desc)]
        if n > 0:
            spells.append((desc, n))

    return curve, spells


def total_creature_slots(bucket_dict):
    return sum(bucket_dict.values())


def total_keyword_card_count(bucket_dict):
    # Keywords are informational only; not counted toward color totals.
    return 0


def total_spell_slots(spell_list):
    return sum(count for _desc, count in spell_list)


# ---------------------------------------------------------------------------
# Main computation
# ---------------------------------------------------------------------------

class ChecklistResult:
    def __init__(self):
        self.color_data = {}       # color name -> dict of computed sections
        self.color_counts = {}     # color name -> final card count
        self.multicolor_sections = []  # list of (name, count)
        self.artifact_count = 0
        self.artifact_data = None
        self.land_count = 0


def compute_checklist(total, multicolor_pct, land_pct, artifact_pct, selected_multicolor):
    mult = multiplier(total)

    artifact_count = int(round(total * artifact_pct / 100.0))
    land_count = int(round(total * land_pct / 100.0))

    # Multicolor: split the multicolor % evenly across the N selected
    # sections FIRST, then compute each section's count from that reduced
    # percentage, and multiply back by N. This guarantees every selected
    # section gets the exact same count (no "6 for A, 7 for B" mismatches).
    n_multicolor = len(selected_multicolor) if selected_multicolor else 0
    if n_multicolor > 0:
        per_section_pct = multicolor_pct / n_multicolor
        per_section_count = int(round(total * per_section_pct / 100.0))
        multicolor_count = per_section_count * n_multicolor
    else:
        per_section_count = 0
        multicolor_count = 0

    remainder = total - artifact_count - multicolor_count - land_count
    if remainder < 0:
        remainder = 0

    n_colors = 5
    # Colors must divide evenly by 5. Find the nearest multiple of 5 to
    # remainder (never more than 2 away), then push the difference onto
    # artifact_count so the five colors come out perfectly even.
    remainder_mod = remainder % n_colors
    if remainder_mod <= n_colors - remainder_mod:
        nearest_multiple = remainder - remainder_mod
    else:
        nearest_multiple = remainder + (n_colors - remainder_mod)
    adjustment = nearest_multiple - remainder  # amount remainder needs to gain
    artifact_count -= adjustment
    remainder = nearest_multiple

    per_color_share = remainder // n_colors
    color_names = ["White", "Blue", "Black", "Red", "Green"]
    per_color_count = {cname: per_color_share for cname in color_names}

    result = ChecklistResult()
    result.artifact_count = artifact_count
    result.land_count = land_count

    for cname in color_names:
        cdata = COLORS[cname]
        target = per_color_count[cname]

        raw_creature = raw_creature_bucket_totals(cdata["common_creatures"], cdata["uncommon_creatures"])
        raw_spell_map, spell_order = raw_spell_counts(cdata["common_spells"], cdata["uncommon_spells"])
        raw_total = sum(raw_creature.values()) + sum(raw_spell_map.values())
        scale_factor = (target / raw_total) if raw_total > 0 else 0.0

        curve, spells = build_color_section(raw_creature, raw_spell_map, spell_order, target)
        keywords = combine_keywords(cdata["keywords_common"], cdata["keywords_uncommon"], scale_factor)

        result.color_data[cname] = {
            "curve": curve,
            "keywords": keywords,
            "spells": spells,
        }
        result.color_counts[cname] = target

    if artifact_count > 0:
        raw_creature = raw_creature_bucket_totals(ARTIFACTS["common_creatures"], ARTIFACTS["uncommon_creatures"])
        raw_spell_map, spell_order = raw_spell_counts(ARTIFACTS["common_spells"], ARTIFACTS["uncommon_spells"])
        raw_total = sum(raw_creature.values()) + sum(raw_spell_map.values())
        scale_factor = (artifact_count / raw_total) if raw_total > 0 else 0.0

        curve, spells = build_color_section(raw_creature, raw_spell_map, spell_order, artifact_count)
        keywords = combine_keywords(ARTIFACTS["keywords_common"], ARTIFACTS["keywords_uncommon"], scale_factor)

        result.artifact_data = {"curve": curve, "keywords": keywords, "spells": spells}

    if selected_multicolor:
        for name in selected_multicolor:
            result.multicolor_sections.append((name, per_section_count))

    return result


# ---------------------------------------------------------------------------
# Markdown generation
# ---------------------------------------------------------------------------

def slots_lines(n):
    return ["- " for _ in range(n)]


def render_color_section(lines, name, count, data):
    lines.append(f"# {name} (x{count})")
    lines.append("")
    lines.append("## Mana Costs")
    lines.append("")
    curve = data["curve"]
    numeric_buckets = sorted(b for b in curve if isinstance(b, int))
    for b in numeric_buckets:
        n = curve[b]
        lines.append(f"### {b} (x{n})")
        lines.extend(slots_lines(n))
        lines.append("")
    if "Flexible" in curve:
        n = curve["Flexible"]
        lines.append(f"### Flexible (x{n})")
        lines.extend(slots_lines(n))
        lines.append("")

    lines.append("## Keywords")
    lines.append("")
    for kw, (lo, hi) in data["keywords"].items():
        if lo == 0 and hi == 0:
            continue
        label = f"{lo}-{hi}" if lo != hi else f"{lo}"
        lines.append(f"### {kw} ({label})")
        lines.extend(slots_lines(hi))
        lines.append("")

    total_spells = total_spell_slots(data["spells"])
    lines.append(f"## Spells (x{total_spells})")
    lines.append("")
    for desc, n in data["spells"]:
        lines.append(f"### {desc} (x{n})")
        lines.extend(slots_lines(n))
        lines.append("")


def render_simple_section(lines, name, count, data=None):
    lines.append(f"# {name} (x{count})")
    lines.append("")
    if data is None or count <= 0:
        lines.extend(slots_lines(count))
        lines.append("")
        return
    lines.extend(slots_lines(count))
    lines.append("")


def generate_markdown(result, total):
    lines = []
    lines.append(f"# Cube Checklist (Total: {total})")
    lines.append("")

    for cname in ["White", "Blue", "Black", "Red", "Green"]:
        render_color_section(lines, cname, result.color_counts[cname], result.color_data[cname])
        lines.append("")

    for name, count in result.multicolor_sections:
        render_simple_section(lines, name, count)
        lines.append("")

    if result.artifact_count > 0:
        lines.append(f"# Artifacts (x{result.artifact_count})")
        lines.append("")
        if result.artifact_data:
            lines.append("## Mana Costs")
            lines.append("")
            curve = result.artifact_data["curve"]
            for b in sorted(k for k in curve if isinstance(k, int)):
                n = curve[b]
                lines.append(f"### {b} (x{n})")
                lines.extend(slots_lines(n))
                lines.append("")
            if "Flexible" in curve:
                n = curve["Flexible"]
                lines.append(f"### Flexible (x{n})")
                lines.extend(slots_lines(n))
                lines.append("")
            lines.append("## Keywords")
            lines.append("")
            for kw, (lo, hi) in result.artifact_data["keywords"].items():
                if lo == 0 and hi == 0:
                    continue
                label = f"{lo}-{hi}" if lo != hi else f"{lo}"
                lines.append(f"### {kw} ({label})")
                lines.extend(slots_lines(hi))
                lines.append("")
            total_spells = total_spell_slots(result.artifact_data["spells"])
            lines.append(f"## Spells (x{total_spells})")
            lines.append("")
            for desc, n in result.artifact_data["spells"]:
                lines.append(f"### {desc} (x{n})")
                lines.extend(slots_lines(n))
                lines.append("")
        lines.append("")

    if result.land_count > 0:
        lines.append(f"# Lands (x{result.land_count})")
        lines.append("")
        lines.extend(slots_lines(result.land_count))
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


# ---------------------------------------------------------------------------
# Checkbox tree model
# ---------------------------------------------------------------------------

class Node:
    def __init__(self, label, children=None):
        self.label = label
        self.children = children or []
        self.checked = False
        self.parent = None
        for c in self.children:
            c.parent = self

    def all_nodes(self):
        yield self
        for c in self.children:
            yield from c.all_nodes()

    def set_checked(self, value):
        self.checked = value
        for c in self.children:
            c.set_checked(value)
        self._update_ancestors()

    def toggle(self):
        self.set_checked(not self.checked)

    def _update_ancestors(self):
        node = self.parent
        while node is not None:
            states = [c.checked for c in node.children]
            node.checked = all(states) if states else node.checked
            node = node.parent

    def leaves_selected(self):
        if not self.children:
            return [self.label] if self.checked else []
        out = []
        for c in self.children:
            out.extend(c.leaves_selected())
        return out


def build_multicolor_tree():
    def leafset(names):
        return [Node(n) for n in names]

    tree = Node("Multicolor", [
        Node("Dual Color", [
            Node("Enemy Duals", leafset(ENEMY_DUALS)),
            Node("Ally Duals", leafset(ALLY_DUALS)),
        ]),
        Node("Tri Color", [
            Node("Enemy Tris", leafset(ENEMY_TRIS)),
            Node("Ally Tris", leafset(ALLY_TRIS)),
        ]),
    ])
    return tree


# ---------------------------------------------------------------------------
# curses TUI
# ---------------------------------------------------------------------------

class FieldSpec:
    def __init__(self, label, value):
        self.label = label
        self.value = value


def flatten_tree(node, depth=0):
    rows = [(node, depth)]
    for c in node.children:
        rows.extend(flatten_tree(c, depth + 1))
    return rows


def run_tui(stdscr, initial_total=None, initial_multicolor_pct=None,
            initial_land_pct=None, initial_artifact_pct=None,
            initial_multicolor_selection=None):
    curses.curs_set(0)
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_WHITE)

    fields = [
        FieldSpec("Total #", str(initial_total if initial_total is not None else DEFAULT_TOTAL)),
        FieldSpec("Multicolor %", str(initial_multicolor_pct if initial_multicolor_pct is not None else DEFAULT_MULTICOLOR_PCT)),
        FieldSpec("Lands %", str(initial_land_pct if initial_land_pct is not None else DEFAULT_LAND_PCT)),
        FieldSpec("Artifacts %", str(initial_artifact_pct if initial_artifact_pct is not None else DEFAULT_ARTIFACT_PCT)),
    ]

    tree = build_multicolor_tree()
    tree_rows = flatten_tree(tree)

    if initial_multicolor_selection:
        wanted = set(initial_multicolor_selection)
        for node, _depth in tree_rows:
            if not node.children and node.label in wanted:
                node.toggle()

    # Menu items: fields, then tree rows, then Generate/Cancel
    FIELD_COUNT = len(fields)
    TREE_START = FIELD_COUNT
    TREE_END = TREE_START + len(tree_rows)
    GENERATE_IDX = TREE_END
    CANCEL_IDX = TREE_END + 1
    TOTAL_ITEMS = CANCEL_IDX + 1

    cursor = 0
    action = None

    while True:
        stdscr.erase()
        h, w = stdscr.getmaxyx()
        row = 0
        stdscr.addstr(row, 0, "Cube Checklist Generator".ljust(w - 1)[:w - 1], curses.A_BOLD)
        row += 1
        stdscr.addstr(row, 0, "Arrows/j/k: move  Enter/Space: toggle/edit  g: generate  q: cancel")
        row += 2

        for i, f in enumerate(fields):
            attr = curses.A_REVERSE if cursor == i else curses.A_NORMAL
            text = f"{f.label}: {f.value}"
            if row < h - 1:
                stdscr.addstr(row, 2, text[:w - 3], attr)
            row += 1

        row += 1
        if row < h - 1:
            stdscr.addstr(row, 0, "Multicolor Selection:", curses.A_UNDERLINE)
        row += 1

        for idx, (node, depth) in enumerate(tree_rows):
            i = TREE_START + idx
            box = "[x]" if node.checked else "[ ]"
            attr = curses.A_REVERSE if cursor == i else curses.A_NORMAL
            text = ("  " * depth) + box + " " + node.label
            if row < h - 1:
                stdscr.addstr(row, 2, text[:w - 3], attr)
            row += 1

        row += 1
        gen_attr = curses.A_REVERSE if cursor == GENERATE_IDX else curses.A_NORMAL
        can_attr = curses.A_REVERSE if cursor == CANCEL_IDX else curses.A_NORMAL
        if row < h - 1:
            stdscr.addstr(row, 2, "[ Generate ]", gen_attr)
        row += 1
        if row < h - 1:
            stdscr.addstr(row, 2, "[ Cancel ]", can_attr)

        stdscr.refresh()
        key = stdscr.getch()

        if key in (curses.KEY_UP, ord('k')):
            cursor = (cursor - 1) % TOTAL_ITEMS
        elif key in (curses.KEY_DOWN, ord('j')):
            cursor = (cursor + 1) % TOTAL_ITEMS
        elif key in (curses.KEY_ENTER, 10, 13, ord(' ')):
            if cursor < FIELD_COUNT:
                f = fields[cursor]
                edited = edit_field(stdscr, f.label, f.value)
                if edited is not None:
                    f.value = edited
            elif cursor < TREE_END:
                node, _depth = tree_rows[cursor - TREE_START]
                node.toggle()
            elif cursor == GENERATE_IDX:
                action = "generate"
                break
            elif cursor == CANCEL_IDX:
                action = "cancel"
                break
        elif key in (ord('g'), ord('G')):
            action = "generate"
            break
        elif key in (ord('q'), ord('Q')):
            action = "cancel"
            break

    selected = tree.leaves_selected()
    return action, fields, selected


def edit_field(stdscr, label, current):
    curses.curs_set(1)
    h, w = stdscr.getmaxyx()
    prompt = f"Edit {label} (Enter to confirm, Esc to cancel): "
    buf = list(current)
    win_row = h - 2

    while True:
        stdscr.move(win_row, 0)
        stdscr.clrtoeol()
        text = prompt + "".join(buf)
        stdscr.addstr(win_row, 0, text[:w - 1])
        stdscr.refresh()
        key = stdscr.getch()
        if key in (curses.KEY_ENTER, 10, 13):
            curses.curs_set(0)
            return "".join(buf)
        elif key == 27:  # Esc
            curses.curs_set(0)
            return None
        elif key in (curses.KEY_BACKSPACE, 127, 8):
            if buf:
                buf.pop()
        elif 32 <= key <= 126:
            buf.append(chr(key))


ALL_MULTICOLOR_LEAVES = ENEMY_DUALS + ALLY_DUALS + ENEMY_TRIS + ALLY_TRIS


def build_arg_parser():
    parser = argparse.ArgumentParser(
        description="Compute a Magic: The Gathering cube design checklist as a markdown template."
    )
    parser.add_argument("output_path", help="Path to write the generated markdown checklist to.")
    parser.add_argument("--total", type=int, default=None, help=f"Total card count (default {DEFAULT_TOTAL}).")
    parser.add_argument("--multicolor-pct", type=float, default=None, help=f"Multicolor %% (default {DEFAULT_MULTICOLOR_PCT}).")
    parser.add_argument("--lands-pct", type=float, default=None, help=f"Lands %% (default {DEFAULT_LAND_PCT}).")
    parser.add_argument("--artifacts-pct", type=float, default=None, help=f"Artifacts %% (default {DEFAULT_ARTIFACT_PCT}).")
    parser.add_argument(
        "--multicolor", type=str, default=None,
        help="Comma-separated list of multicolor archetypes to select, e.g. 'Simic,Izzet,Azorius'. "
             f"Valid values: {', '.join(ALL_MULTICOLOR_LEAVES)}."
    )
    parser.add_argument(
        "--silent", action="store_true",
        help="Skip the TUI entirely and generate immediately using the provided/default values."
    )
    return parser


def main():
    parser = build_arg_parser()
    args = parser.parse_args()

    output_path = args.output_path

    requested_multicolor = None
    if args.multicolor:
        requested_multicolor = [name.strip() for name in args.multicolor.split(",") if name.strip()]
        invalid = [n for n in requested_multicolor if n not in ALL_MULTICOLOR_LEAVES]
        if invalid:
            print(f"Error: unknown multicolor archetype(s): {', '.join(invalid)}", file=sys.stderr)
            print(f"Valid values: {', '.join(ALL_MULTICOLOR_LEAVES)}", file=sys.stderr)
            sys.exit(1)

    if args.silent:
        total = args.total if args.total is not None else DEFAULT_TOTAL
        multicolor_pct = args.multicolor_pct if args.multicolor_pct is not None else DEFAULT_MULTICOLOR_PCT
        land_pct = args.lands_pct if args.lands_pct is not None else DEFAULT_LAND_PCT
        artifact_pct = args.artifacts_pct if args.artifacts_pct is not None else DEFAULT_ARTIFACT_PCT
        selected = requested_multicolor if requested_multicolor is not None else []
    else:
        action, fields, selected = curses.wrapper(
            run_tui,
            initial_total=args.total,
            initial_multicolor_pct=args.multicolor_pct,
            initial_land_pct=args.lands_pct,
            initial_artifact_pct=args.artifacts_pct,
            initial_multicolor_selection=requested_multicolor,
        )

        if action != "generate":
            print("Cancelled. No file written.")
            sys.exit(0)

        try:
            total = int(fields[0].value)
            multicolor_pct = float(fields[1].value)
            land_pct = float(fields[2].value)
            artifact_pct = float(fields[3].value)
        except ValueError:
            print("Error: Total #, Multicolor %, Lands %, and Artifacts % must be numbers.", file=sys.stderr)
            sys.exit(1)

    result = compute_checklist(total, multicolor_pct, land_pct, artifact_pct, selected)
    markdown = generate_markdown(result, total)

    with open(output_path, "w", encoding="utf-8") as fh:
        fh.write(markdown)

    print(f"Wrote checklist to {output_path}")


if __name__ == "__main__":
    main()
