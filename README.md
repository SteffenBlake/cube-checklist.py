# Cube Checklist Tools

Two small command-line scripts for planning and building a Magic: The Gathering cube.

The card-count math (creature curves, keyword ranges, spell slots, and how they scale to your
cube's size) is based on the default design skeleton described in Mark Rosewater's article
"Nuts & Bolts #13: Design Skeleton Revisited" (a 181-card baseline: 101 commons + 80 uncommons).

## The two scripts

1. `cube_checklist.py` - an interactive terminal tool that asks how big your cube is and what
   percentage should be multicolor, lands, and artifacts, then generates a markdown checklist
   template with a slot for every card you need to design.
2. `compile_decklist.py` - once you've filled in that markdown checklist with real card names,
   this script checks your work (making sure you didn't add or remove slots by accident) and
   compiles all the card names into a plain MTGO-style decklist file.

The intended workflow is: generate the checklist, fill it in with card names as you design your
cube, then compile it into a decklist you can import elsewhere.

## Step 1: Generate the checklist

```
python3 cube_checklist.py <output.md>
```

This opens a terminal UI. You'll see:

- **Total #** - how many cards are in your cube (defaults to 450).
- **Multicolor %**, **Lands %**, **Artifacts %** - what percentage of the cube those categories
  should take up. Defaults are pre-filled based on the article's numbers.
- A checkbox tree for **Multicolor**, split into Dual Color (enemy and ally color pairs, like
  Simic or Azorius) and Tri Color (enemy and ally wedges, like Temur or Bant). Check whichever
  color combinations your cube actually uses.
- **Generate** and **Cancel** buttons at the bottom.

Controls: arrow keys or `j`/`k` to move, Enter or Space to toggle a checkbox or edit a number
field, `g` to generate, `q` to cancel.

Checking or unchecking a parent box (like "Dual Color" or "Enemy Duals") automatically checks or
unchecks everything underneath it, and a parent automatically shows as checked once all of its
children are checked.

When you hit Generate, the script writes a markdown file to the path you gave it. That file has
a section for White, Blue, Black, Red, and Green, one section for each multicolor combination you
checked, one for Artifacts, and one for Lands. Every card total (`x<Count>`) has been divided up
from your Total # based on the percentages you entered, and every sub-section (mana costs,
keywords, spell types) is scaled down from the article's numbers to fit your cube's size.

Each color section has:

- **Mana Costs** - how many cards you need at each mana value, based on the article's creature
  curve.
- **Keywords** - a checklist of how many creatures should have keywords like Flying or Deathtouch.
  This is informational only; it's a different way of slicing the same cards already counted in
  Mana Costs, so it does not add to the color's total card count.
- **Spells** - the non-creature card slots (removal, card draw, combat tricks, and so on).

Every slot is represented as a blank `- ` line. Fill each one in with the name of the card you've
picked for that slot.

See [example.md](example.md) in the root of this repo for what a generated checklist actually
looks like before it's filled in. That example was generated for a 450-card cube, with all ten
two-color pairs turned on (every enemy and ally dual, like Simic and Azorius, but no three-color
wedges), and with the multicolor slice of the cube set noticeably higher than the article's
default so each of those ten color pairs gets a healthy number of cards.

### Silent Mode

You can also skip the terminal UI entirely and pass everything as command-line flags, which is
useful for scripting or quickly regenerating a checklist:

```
python3 cube_checklist.py --silent \
  --total 450 \
  --multicolor-pct 10 \
  --lands-pct 8 \
  --artifacts-pct 6 \
  --multicolor "Simic,Izzet,Golgari,Boros,Orzhov" \
  cube-checklist.md
```

Run `python3 cube_checklist.py --help` to see every flag and its default.

## Step 2: Fill in the checklist

Open the generated markdown file and replace each blank `- ` line with a card name, for example:

```
### 2 (x3)
- Llanowar Elves
- Wall of Roots
- Elvish Mystic
```

Fill in every blank `- ` line with a card name before running the compile step; a slot left as
just `- ` (blank) will cause the next step to error out rather than being skipped. Don't add or
delete lines, since the next step also checks that every section still has the exact number of
slots it started with.

## Step 3: Compile the decklist

```
python3 compile_decklist.py <checklist.md> [output.txt]
```

If you don't give an output path, it writes a `.txt` file next to the markdown file with the
same name (for example, `cube-checklist.md` becomes `cube-checklist.txt`).

This script does three things:

1. **Validates section counts.** It counts the actual `- ` lines under each heading and compares
   that to the count printed in the heading itself (the `(x<N>)` part). If anything doesn't
   match, for example because a line was accidentally deleted, it prints exactly which section
   is wrong:

   ```
   Section count validation failed:
     Artifacts (x9) -- Expected: 9, Actual: 8
   ```

   and exits without writing anything, so you can go fix the file.

2. **Checks for blank slots.** Every `- ` line (outside of a Keywords section) must have a card
   name after it. If any slots are still blank, it refuses to compile and instead prints the
   exact line number of every blank it found:

   ```
   Found blank (unfilled) slots:
     Line 8: White (x2) > Mana Costs > 2 (x1)
     Line 23: Blue (x2) > Mana Costs > 2 (x1)
   ```

   Nothing is skipped silently: the checklist has to be completely filled in before it will
   compile a decklist.

3. **Compiles** every card name into an MTGO-style decklist, one line per card:

   ```
   1 Llanowar Elves
   1 Wall of Roots
   1 Elvish Mystic
   ```

   The Keywords sections are skipped here, since they're informational only and would otherwise
   double-count cards that are already listed under Mana Costs or Spells.
