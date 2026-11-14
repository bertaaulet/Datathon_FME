"""Elo ratings for the student and the problems, and the choice of the next problem.

A problem has five options, so a student who knows nothing is still right one
time in five. The chance of a right answer is:

    P = 0.2 + 0.8 / (1 + 10 ** ((R_problem - R_student) / 400))

After each answer, the student's rating moves by K * (result - P), and the
problem's rating moves the other way, more slowly.

K starts large and shrinks: a new student's rating should move fast, a settled
one shouldn't jump on every answer. The schedule was chosen with simulated
students (sim/students.py): with a constant K of 32, a student who starts 300
points off is still about 170 points off after 20 answers; with this schedule,
about 70.
"""
GUESS = 0.2
K_START, K_END, K_HALF = 160.0, 40.0, 8.0
K_PROBLEM = 8.0
TARGET = 0.7  # hard enough to learn from, easy enough to keep going


def expected(r_student, r_problem):
    return GUESS + (1 - GUESS) / (1 + 10 ** ((r_problem - r_student) / 400.0))


def k_student(answers):
    """How far one answer moves the rating, after `answers` earlier answers."""
    return max(K_END, K_START / (1 + answers / K_HALF))


def update(r_student, r_problem, correct, answers=0):
    """Return the new (student, problem) ratings after one answer.

    answers is how many answers this rating has already seen.
    """
    surprise = (1.0 if correct else 0.0) - expected(r_student, r_problem)
    return r_student + k_student(answers) * surprise, r_problem - K_PROBLEM * surprise


def initial_problem(level, tram):
    """A first guess from the Kangaroo level (0 to 7) and the third of the paper (0 to 2).

    Kangaroo papers go from 3-point to 5-point questions, so later questions
    are meant to be harder. Check it on your data before you rely on it.
    """
    return 1000.0 + 150.0 * int(level or 0) + 100.0 * int(tram or 0)


def initial_student(level):
    return 1000.0 + 150.0 * int(level or 0)


def tram(number, last):
    """Which third of the paper question `number` is in, when the paper has `last` questions."""
    if not number or not last:
        return 1
    return min(2, max(0, (int(number) - 1) * 3 // int(last)))


def pick(candidates, r_student, topic=None, target=TARGET):
    """Choose from [(id, elo, topic), ...] the problem whose P is closest to the target.

    With a topic, problems of that topic win when one is close enough to the target.
    Ties go to the smaller id, so the choice repeats.
    """
    if not candidates:
        return None

    def distance(candidate):
        return (round(abs(expected(r_student, candidate[1]) - target), 6), candidate[0])

    if topic:
        same = [c for c in candidates if c[2] == topic]
        if same:
            best = min(same, key=distance)
            if distance(best)[0] <= 0.1:
                return best
    return min(candidates, key=distance)
