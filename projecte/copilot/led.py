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


def bar(fraction, previous=None):
    """One road that lights up from left to right: how sure the Kangaroo is of the right answer.

    The same picture the web page draws (13 lamps). A little arrow above the road
    points at the last lit lamp, which is where the Kangaroo stands. A faint dot
    marks where it stood before the last hint, so the picture shows how far it moved
    (nothing blinks: a picture stays until the next one).
    """
    fraction = min(1.0, max(0.0, float(fraction)))
    pos = int(round(fraction * (COLS - 1)))
    grid = blank()
    for c in range(COLS):
        for r in (3, 4):
            grid[r][c] = ON if c <= pos else DIM
    if previous is not None:
        was = int(round(min(1.0, max(0.0, float(previous))) * (COLS - 1)))
        if was != pos:
            grid[2][was] = 2
    grid[2][pos] = ON
    for c in (pos - 1, pos, pos + 1):
        if 0 <= c < COLS:
            grid[1][c] = ON
    return grid
