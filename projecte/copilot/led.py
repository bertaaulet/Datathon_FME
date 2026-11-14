"""Pictures for the board's LED matrix: 8 rows by 13 columns, brightness 0 to 7.

Everything here is plain lists, so it runs anywhere. The App Lab app
(applab/math-matrix) reads the current picture from the tutor and sends it to
the microcontroller. Nothing flashes: a picture stays until the next one.
"""
ROWS, COLS, ON, DIM = 8, 13, 7, 1

FONT = {  # 5 columns by 7 rows
    "A": [".###.", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"],
    "B": ["####.", "#...#", "#...#", "####.", "#...#", "#...#", "####."],
    "C": [".###.", "#...#", "#....", "#....", "#....", "#...#", ".###."],
    "D": ["####.", "#...#", "#...#", "#...#", "#...#", "#...#", "####."],
    "E": ["#####", "#....", "#....", "####.", "#....", "#....", "#####"],
    "?": [".###.", "#...#", "....#", "...#.", "..#..", ".....", "..#.."],
    "0": [".###.", "#...#", "#..##", "#.#.#", "##..#", "#...#", ".###."],
    "1": ["..#..", ".##..", "..#..", "..#..", "..#..", "..#..", ".###."],
    "2": [".###.", "#...#", "....#", "...#.", "..#..", ".#...", "#####"],
    "3": ["####.", "....#", "....#", ".###.", "....#", "....#", "####."],
    "4": ["...#.", "..##.", ".#.#.", "#..#.", "#####", "...#.", "...#."],
    "5": ["#####", "#....", "####.", "....#", "....#", "#...#", ".###."],
    "6": [".###.", "#....", "#....", "####.", "#...#", "#...#", ".###."],
    "7": ["#####", "....#", "...#.", "..#..", "..#..", "..#..", "..#.."],
    "8": [".###.", "#...#", "#...#", ".###.", "#...#", "#...#", ".###."],
    "9": [".###.", "#...#", "#...#", ".####", "....#", "....#", ".###."],
}

TICK = [
    ".............",
    "...........#.",
    "..........##.",
    ".........##..",
    ".#......##...",
    ".##....##....",
    "..##..##.....",
    "...####......",
]
CROSS = [
    ".............",
    "...#.....#...",
    "....#...#....",
    ".....#.#.....",
    "......#......",
    ".....#.#.....",
    "....#...#....",
    "...#.....#...",
]


def blank():
    return [[0] * COLS for _ in range(ROWS)]


def from_art(lines):
    grid = blank()
    for r, line in enumerate(lines[:ROWS]):
        for c, ch in enumerate(line[:COLS]):
            if ch == "#":
                grid[r][c] = ON
    return grid


def tick():
    return from_art(TICK)


def cross():
    return from_art(CROSS)


def text(chars):
    """One or two characters, centred."""
    chars = [ch for ch in str(chars)[:2] if ch in FONT]
    grid = blank()
    width = 5 * len(chars) + (len(chars) - 1)
    left = (COLS - width) // 2
    for i, ch in enumerate(chars):
        for r, line in enumerate(FONT[ch]):
            for c, pixel in enumerate(line):
                if pixel == "#":
                    grid[r][left + i * 6 + c] = ON
    return grid


def bar(fraction):
    """A bar from left to right: how sure the Kangaroo is of the right answer.

    The middle column is marked, because half way is where it changes its mind.
    """
    fraction = min(1.0, max(0.0, float(fraction)))
    filled = int(round(fraction * COLS))
    grid = blank()
    for c in range(COLS):
        for r in range(2, 6):
            grid[r][c] = ON if c < filled else DIM
    for r in (0, 7):
        grid[r][COLS // 2] = 3
    return grid
