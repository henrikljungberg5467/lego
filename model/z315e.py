#!/usr/bin/env python3
"""John Deere Z315E ZTrak zero-turn mower in LEGO (Technic + System), scale ~1:8.

Generates model/z315e.mpd. Coordinates in LDU (1 stud = 20, plate = 8, -Y is up).
Machine axes: front = -Z, left = +X, right (discharge side) = -X. Rear axle at z=0.

Grids: the rear frame, body and deck use studs at x,z = 10 (mod 20) ("grid A"); the
front frame is Technic (holes at multiples of 20) and the operator floor sits on studs
at multiples of 20 ("grid B"), reached from grid A through 2x2 jumper plates.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from builder import (Model, rot, I, box, fill, BLACK, GREEN, YELLOW, DBG, LBG, RED, BLUE, ORANGE, TAN)  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "z315e.mpd")

# ------------------------------------------------------------------ key dimensions
REAR_AXLE_Y = -70          # 56145 rim + 55976 tyre, radius 71
REAR_WHEEL_X = 140
CROSSBAR_Z = -420          # front cross tube / caster pivots
CROSSBAR_Y = -130
PIVOT_X = 140
HANGER_Z = (-220, -160)    # deck hanger rods (x = +-140)
BODY_Z1 = 120              # rear end of the body

# common orientations
R_ALONG_Z = rot(x="+Z", y="+Y")          # brick/plate long side along Z
R_BEAM_X = rot(z="+X", y="+Y")           # thick beam length along X, holes vertical
R_AXLE_Y = rot(x="+Y", y="+Z")           # axle/pin along Y
R_PIN_Y = rot(x="+Y", z="+X")
R_BUSH_X = rot(z="+X", y="+Y")           # bush / wheel axis along X
R_BUSH_Y = rot(z="+Y", x="+X")           # bush / connector axis along Y

BEAM = {2: "43857", 3: "32523", 5: "32316", 7: "32524", 9: "40490", 11: "32525", 13: "41239", 15: "32278"}
AXLE = {2: "32062", 3: "4519", 4: "3705", 5: "32073", 6: "3706", 7: "44294", 8: "3707", 10: "3737", 12: "3708"}
AXLE_COLOR = {2: RED, 3: LBG, 4: BLACK, 5: LBG, 6: BLACK, 7: LBG, 8: BLACK, 10: BLACK, 12: BLACK}

m = Model("z315e.ldr", "John Deere Z315E ZTrak - LEGO 1:8")


def sgn_axis(s, axis):
    return ("+" if s > 0 else "-") + axis


# ================================================================== rear frame (grid A)
def rear_frame():
    s = m.sub("rear_frame", "Rear frame with axle bearings")
    for x in (-1, 1):
        for xx in (70, 90):
            s.add("3702", BLACK, (x * xx, -80, 0), R_ALONG_Z, "axle bearing")
            box(s, "brick", BLACK, x * xx - 10, x * xx + 10, 80, BODY_Z1, -80)
    s.step()
    box(s, "plate", BLACK, -100, 100, -80, 40, -88)
    box(s, "plate", BLACK, -100, 100, 40, BODY_Z1, -88)
    s.step()
    # second layer: levels the engine bay and reaches forward over the deck
    box(s, "plate", BLACK, -100, 100, -160, -40, -96)
    box(s, "plate", BLACK, -100, 100, -40, 0, -96)
    box(s, "plate", BLACK, -100, 100, 0, BODY_Z1, -96)
    for x in (-1, 1):
        box(s, "plate", BLACK, *sorted((x * 100, x * 140)), -140, -80, -96)
        box(s, "plate", BLACK, *sorted((x * 140, x * 160)), -140, -80, -96)
    s.step()
    # adapter to the floor grid: 2x16 plate + jumpers (half-stud offset in x and z)
    box(s, "plate", BLACK, -160, 160, -140, -100, -104)
    for x in (-140, -100, -60, -20, 20, 60, 100, 140):
        s.add("87580", BLACK, (x, -112, -120), I)
    return s


def rear_wheel(s, side):
    """side=+1 left, -1 right"""
    x = side
    s.add(AXLE[5], AXLE_COLOR[5], (x * 90, REAR_AXLE_Y, 0), I)
    s.add("3713", LBG, (x * 50, REAR_AXLE_Y, 0), R_BUSH_X)
    s.add("32123b", LBG, (x * 105, REAR_AXLE_Y, 0), R_BUSH_X)
    s.step()
    Rw = rot(z=sgn_axis(x, "X"), y="+Y")
    s.add("56145", YELLOW, (x * REAR_WHEEL_X, REAR_AXLE_Y, 0), Rw)
    s.add("55976", BLACK, (x * REAR_WHEEL_X, REAR_AXLE_Y, 0), Rw)


def rear_wheels():
    s = m.sub("rear_wheels", "Rear drive wheels")
    rear_wheel(s, 1)
    s.step()
    rear_wheel(s, -1)
    return s


# ================================================================== front frame (Technic)
def front_frame():
    s = m.sub("front_frame", "Front frame with cross tube")
    s.add(BEAM[15], GREEN, (0, CROSSBAR_Y, CROSSBAR_Z), R_BEAM_X, "front cross tube")
    for x in (-1, 1):
        s.add(BEAM[15], GREEN, (x * PIVOT_X, CROSSBAR_Y, -240), I, "side member")
    s.step()
    for x in (-1, 1):
        px = x * PIVOT_X
        Rl = rot(x="-X", z="-Z") if x > 0 else rot(x="+X", z="-Z")
        for dx in (20, 40):
            s.add("2780", BLACK, (px - x * dx, -140, CROSSBAR_Z), R_PIN_Y)
        for z in (-380, -360, -340):
            s.add("2780", BLACK, (px, -140, z), R_PIN_Y)
        s.add("32526", GREEN, (px, -150, -340), Rl, "corner")
    return s


def caster(s, side):
    px, pz = side * PIVOT_X, CROSSBAR_Z
    s.add("6536", GREEN, (px, -110, pz + 20), rot(x="+X", y="-Z"), "fork block")
    s.add(AXLE[4], AXLE_COLOR[4], (px, -110, pz + 20), I)
    Rarm = rot(z="+Y", x="+Z")
    for dx in (-30, 30):
        s.add("32140", GREEN, (px + dx, -110, pz + 20), Rarm, "fork arm")
    s.step()
    s.add(AXLE[5], AXLE_COLOR[5], (px, -50, pz + 40), I)
    Rw = rot(z=sgn_axis(-side, "X"), y="+Y")
    s.add("55981", YELLOW, (px, -50, pz + 40), Rw)
    s.add("58090", BLACK, (px, -50, pz + 40), Rw)
    for dx in (-45, 45):
        s.add("32123b", LBG, (px + dx, -50, pz + 40), R_BUSH_X)
    s.step()
    s.add(AXLE[6], AXLE_COLOR[6], (px, -150, pz), R_AXLE_Y, "caster pivot")
    s.add("32123b", LBG, (px, -95, pz), R_BUSH_Y)
    for y in (-184, -208):
        s.add("3941", GREEN, (px, y, pz), I, "pivot housing")
    s.add("15535", BLACK, (px, -216, pz), I, "cap")


def casters():
    s = m.sub("casters", "Front caster wheels")
    caster(s, 1)
    s.step()
    caster(s, -1)
    return s


# ================================================================== operator floor (grid B)
def floor():
    s = m.sub("floor", "Operator floor pan and footrest")
    holes = [(x, z) for x in (-140, 140) for z in HANGER_Z]
    # floor plates: studs at multiples of 20; outer columns plug into the side members
    fill(s, "plate", GREEN, -150, 150, -330, -90, -120, avoid=holes, prefer="z")
    s.step()
    # forward extension under the footrest, one plate lower so it locks under the floor;
    # kept within x=+-70 so the swivelling caster forks clear it
    fill(s, "plate", GREEN, -70, 70, -410, -290, -112, prefer="z")
    s.step()
    fill(s, "tile", GREEN, -130, 130, -330, -90, -128, prefer="z",
         avoid=[(x, -320) for x in range(-100, 101, 20)])
    s.step()
    # footrest: base plate under the front, a wide raised toe board rising to the front.
    # Everything at y > -120 stays within x=+-70 so the swivelling caster forks clear it.
    fill(s, "plate", GREEN, -70, 70, -410, -330, -120)
    fill(s, "plate", GREEN, -110, 110, -410, -310, -128, prefer="x")
    s.step()
    R_back = rot(x="-X", z="-Z")
    fill(s, "brick", GREEN, -110, 110, -410, -390, -152)
    for x0, x1 in ((-110, -70), (-70, -30), (-30, -10), (-10, 10), (10, 30), (30, 70), (70, 110)):
        s.add("3298" if x1 - x0 == 40 else "4286", GREEN, ((x0 + x1) / 2, -152, -380), R_back, "toe board")
    s.step()
    fill(s, "brick", GREEN, -110, 110, -410, -390, -176)
    for x in range(-100, 101, 20):
        s.add("3040b", GREEN, (x, -176, -380), R_back)
    fill(s, "tile", GREEN, -110, 110, -410, -370, -184, avoid=[(-20, -400), (0, -400), (20, -400)])
    box(s, "tile", BLACK, -30, 30, -410, -390, -184, "John Deere badge")
    return s


# ================================================================== mower deck (grid A)
DECK_X = 180
DECK_Z0, DECK_Z1 = -320, -120


R_CORNER_R = rot(x="-Z", z="+X")         # round-corner parts for the right (-X) front corner


def deck():
    s = m.sub("deck", "42 in. mower deck")
    import numpy as np
    used = []
    # hanger plates (Technic plates with holes, hidden under the top tiles)
    for x in (-1, 1):
        x0, x1 = sorted((x * 120, x * 160))
        s.add("32001", BLACK, ((x0 + x1) / 2, -72, -180), R_ALONG_Z, "hanger plate")
        used += [(xx, zz) for xx in (x0 + 10, x0 + 30) for zz in range(-230, -129, 20)]
    # rounded front corners
    corner_missing = []
    for x in (-1, 1):
        R = I if x > 0 else R_CORNER_R
        c = np.array([x * 140, 0, -280])
        s.add("30565", GREEN, (c[0], -72, c[2]), R, "deck corner")
        for lx, lz in [(-30, -30), (-10, -30), (10, -30), (30, -30), (-30, -10), (-10, -10), (10, -10), (30, -10),
                       (-30, 10), (-10, 10), (10, 10), (30, 10), (-30, 30), (-10, 30), (10, 30), (30, 30)]:
            w = c + R @ np.array([lx, 0, lz])
            used.append((w[0], w[2]))
            if (lx, lz) in [(-10, -30), (10, -30), (30, -30), (30, -10), (30, 10)]:
                corner_missing.append((w[0], w[2]))
    edge = [(x, DECK_Z0 + 10) for x in range(-90, 91, 20)]
    fill(s, "plate", GREEN, -DECK_X, DECK_X, DECK_Z0, DECK_Z1, -72, avoid=used + edge, prefer="z")
    s.step()
    # skirt: brick + two plates under the edge; macaroni corners at the front
    sk = [(1, 1), (1, 2), (1, 3), (1, 4), (1, 6), (1, 8), (1, 10), (1, 12)]
    for x in (-1, 1):
        R = I if x > 0 else R_CORNER_R
        for y in (-64, -40):
            s.add("48092", GREEN, (x * 100, y, -240), R, "deck corner skirt")
    for kind, y in (("brick", -64), ("brick", -40)):
        fill(s, kind, GREEN, -100, 100, DECK_Z0, DECK_Z0 + 20, y, sizes=sk)
        fill(s, kind, GREEN, -DECK_X, DECK_X, DECK_Z1 - 20, DECK_Z1, y, sizes=sk)
        fill(s, kind, GREEN, DECK_X - 20, DECK_X, -240, DECK_Z1 - 20, y, sizes=sk, prefer="z")
        fill(s, kind, GREEN, -DECK_X, -DECK_X + 20, -160, DECK_Z1 - 20, y, sizes=sk, prefer="z")
        s.step()
    # discharge chute on the right side
    box(s, "plate", BLACK, -240, -160, -240, -160, -64, "discharge chute")
    for z in (-220, -180):
        s.add("3298", BLACK, (-190, -88, z), rot(z="+X", y="+Y"))
    for z0 in (-240, -180):
        box(s, "brick", BLACK, -240, -180, z0, z0 + 20, -56)
    box(s, "brick", BLACK, -240, -220, -220, -180, -56)
    s.step()
    # top tiles, leaving studs free around the hanger rods and for the belt cover
    free = list(corner_missing)
    for x in (-140, 140):
        for z in HANGER_Z:
            free += [(x + dx, z + dz) for dx in (-10, 10) for dz in (-10, 10)]
    dome = (-90, -250)
    free.append(dome)
    free += edge + [(x, DECK_Z0 + 30) for x in range(-90, 91, 20)]
    fill(s, "tile", GREEN, -DECK_X, DECK_X, DECK_Z0, DECK_Z1, -80, avoid=free, prefer="z")
    for x in range(-90, 91, 20):
        s.add("11477", GREEN, (x, -64, DECK_Z0 + 20), I, "rounded front edge")
    s.add("6141", BLACK, (dome[0], -80, dome[1]), I)
    s.add("3960", BLACK, (dome[0], -96, dome[1]), I, "belt cover")
    s.step()
    # hanger rods
    for x in (-140, 140):
        for z in HANGER_Z:
            s.add(AXLE[5], AXLE_COLOR[5], (x, -100, z), R_AXLE_Y, "deck hanger")
            s.add("3713", LBG, (x, -54, z), R_BUSH_Y)
            s.add("32123b", LBG, (x, -145, z), R_BUSH_Y)
    return s

# ================================================================== body (grid A)
def body():
    """Side panels sit above the rear tyres; the black front corners reach down in front of them."""
    s = m.sub("body", "Rear body: engine bay, side panels, fender boxes")
    Z0, Z1 = -80, BODY_Z1
    # engine bay walls on the second frame layer (top y=-96)
    for x in (-1, 1):
        for y in (-120, -144):
            box(s, "brick", BLACK, x * 90 - 10, x * 90 + 10, Z0, Z1, y, "engine bay wall")
    for y in (-120, -144):
        box(s, "brick", DBG, -80, 80, Z0, Z0 + 20, y)
        box(s, "brick", BLACK, -80, 80, Z1 - 20, Z1, y)
    s.step()
    # body floor, lies above the rear tyres (tyre top y=-141)
    fill(s, "plate", BLACK, -140, 140, Z0, Z1, -152)
    s.step()
    for x in (-1, 1):
        o0, o1 = sorted((x * 120, x * 140))     # outer wall (side panel)
        i0, i1 = sorted((x * 80, x * 120))      # fender box inside
        c0, c1 = sorted((x * 80, x * 140))      # front corner block
        # front corner block reaches down in front of the tyre (hangs under the body floor)
        box(s, "brick", BLACK, *sorted((x * 100, x * 140)), Z0, Z0 + 20, -144)
        box(s, "plate", BLACK, *sorted((x * 100, x * 140)), Z0, Z0 + 20, -120)
        # green side panel with the yellow stripe
        fill(s, "brick", GREEN, o0, o1, -40, Z1 - 20, -176, prefer="z")
        fill(s, "plate", GREEN, o0, o1, -40, Z1 - 20, -184, prefer="z")
        fill(s, "plate", YELLOW, o0, o1, -40, Z1 - 20, -192, prefer="z")
        fill(s, "plate", GREEN, o0, o1, -40, Z1 - 20, -200, prefer="z")
        fill(s, "plate", GREEN, o0, o1, -40, Z1 - 20, -208, prefer="z")
        # fender box inner walls
        for y in (-176, -200):
            fill(s, "brick", BLACK, i0, i1, -40, Z1, y, prefer="z")
        fill(s, "plate", BLACK, i0, i1, -40, Z1, -208, prefer="z")
        # rear corner
        fill(s, "brick", BLACK, o0, o1, Z1 - 20, Z1, -176)
        for y in (-184, -192, -200, -208):
            fill(s, "plate", BLACK, o0, o1, Z1 - 20, Z1, y)
        # front corner block with the lap bar pivot
        s.add("3700", BLACK, (x * 120, -176, -70), I, "lap bar pivot")
        box(s, "brick", BLACK, *sorted((x * 80, x * 100)), Z0, Z0 + 20, -176)
        fill(s, "brick", BLACK, c0, c1, Z0 + 20, -40, -176)
        fill(s, "brick", BLACK, c0, c1, Z0, -40, -200)
        fill(s, "plate", BLACK, c0, c1, Z0, -40, -208)
    s.step()
    # rear engine hood behind the seat
    for y in (-176, -200):
        fill(s, "brick", BLACK, -80, 80, 80, Z1, y)
    fill(s, "plate", BLACK, -80, 80, 80, Z1, -208)
    s.step()
    # box tops: plate, rounded outer edge, tiles; rounded rear edge on the hood
    for x in (-1, 1):
        c0, c1 = sorted((x * 80, x * 140))
        fill(s, "plate", BLACK, c0, c1, Z0, Z1, -216, prefer="z")
        fill(s, "plate", BLACK, *sorted((x * 80, x * 100)), Z0, Z1, -224, prefer="z")
        fill(s, "tile", BLACK, *sorted((x * 80, x * 100)), Z0, Z1, -232, prefer="z",
             avoid=[(x * 90, -70), (x * 90, -50)] if x < 0 else [(x * 90, 30)])
        for z in range(Z0 + 10, Z1, 20):
            s.add("11477", BLACK, (x * 120, -216, z), rot(z=sgn_axis(-x, "X"), y="+Y"), "rounded box edge")
    fill(s, "plate", BLACK, -80, 80, 80, Z1, -216)
    fill(s, "plate", BLACK, -80, 80, 80, Z1 - 20, -224)
    for x in range(-70, 71, 20):
        s.add("11477", BLACK, (x, -216, Z1 - 20), rot(z="-Z", y="+Y"), "rear edge")
    s.step()
    s.add("98138", DBG, (90, -232, 30), I, "fuel cap")
    s.add("2432", ORANGE, (-90, -256, -60), rot(x="+Z", y="+Y"), "control lever")
    # front face below the seat (dark grey "Z" panel)
    box(s, "brick", DBG, -80, 80, Z0, Z0 + 20, -176)
    return s


# ================================================================== seat (grid A)
def seat():
    s = m.sub("seat", "Operator seat")
    fill(s, "brick", BLACK, -60, 60, -60, 80, -176)
    s.step()
    fill(s, "plate", YELLOW, -80, 80, -80, 80, -184)
    s.step()
    # cushion
    fill(s, "brick", YELLOW, -80, 80, -40, 40, -208)
    fill(s, "tile", YELLOW, -80, 80, -40, 40, -216, avoid=[(-70, 30), (70, 30)])
    fill(s, "plate", YELLOW, -80, 80, -80, -40, -192)
    fill(s, "plate", YELLOW, -80, 80, -80, -40, -200)
    for x in range(-70, 71, 20):
        s.add("11477", YELLOW, (x, -200, -60), I, "cushion front roll")
    s.step()
    # backrest: 5 bricks + 2 plates; side bolsters reach forward over the cushion
    for k, y in enumerate((-208, -232, -256, -280, -304)):
        bolster = k in (1, 2, 3)
        xa, xb = (-60, 60) if bolster else (-80, 80)
        if k == 3:
            box(s, "brick", YELLOW, xa, -20, 40, 60, y)
            s.add("11211", YELLOW, (0, y, 50), I, "logo mount")
            box(s, "brick", YELLOW, 20, xb, 40, 60, y)
        else:
            box(s, "brick", YELLOW, xa, xb, 40, 60, y)
        box(s, "brick", YELLOW, -80, 80, 60, 80, y)
        if bolster:
            for x in (-70, 70):
                box(s, "brick", YELLOW, x - 10, x + 10, 20, 60, y)
    for x in (-70, 70):
        s.add("54200", YELLOW, (x, -280, 30), I, "bolster top")
    fill(s, "plate", YELLOW, -80, 80, 40, 80, -312)
    fill(s, "plate", YELLOW, -40, 40, 40, 80, -320)
    fill(s, "tile", YELLOW, -40, 40, 40, 80, -328)
    for z in (50, 70):
        s.add("11477", YELLOW, (60, -312, z), rot(z="-X", y="+Y"))
        s.add("11477", YELLOW, (-60, -312, z), rot(z="+X", y="+Y"))
    s.add("14769", GREEN, (0, -280, 32), rot(x="+X", y="+Z"), "John Deere logo")
    return s

# ================================================================== lap bars
def lap_bar(s, side, park_deg=0.0):
    """Steering lever. side=+1 left, -1 right. park_deg swings it outward about its pivot."""
    import numpy as np
    from builder import rot_axis
    px, py, pz = side * 120, -166, -70
    Rp = rot_axis("+Z", side * park_deg)

    def put(part, color, pos, R, note=None):
        p = np.array(pos, dtype=float) - np.array([px, py, pz])
        s.add(part, color, np.array([px, py, pz]) + Rp @ p, Rp @ R, note)

    put(AXLE[2], BLACK, (px, py, -80), rot(x="+Z", y="+Y"))
    put("32039", BLACK, (px, py, -90), rot(z="+Z", x="+Y"), "lap bar hub")
    put(AXLE[8], BLACK, (px, -240, -110), R_AXLE_Y, "lap bar")
    put("32014", BLACK, (px, -330, -110), rot(y="-Y", z=("+X" if side > 0 else "-X")))
    put(AXLE[4], BLACK, (px - side * 50, -330, -110), I)
    put("59443", BLACK, (px - side * 70, -330, -110), R_BUSH_X, "grip")


def lap_bars():
    s = m.sub("lap_bars", "Steering levers (lap bars)")
    lap_bar(s, 1, 30)
    s.step()
    lap_bar(s, -1, 30)
    return s


# ================================================================== assemble
subs = [rear_frame(), rear_wheels(), front_frame(), casters(), floor(), deck(), body(), seat(), lap_bars()]
for sub in subs:
    m.main.place(sub)
    m.main.step()
m.write(OUT)
print("wrote", OUT, sum(s.count for s in subs), "parts")
