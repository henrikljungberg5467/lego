"""Rebrickable inventory lookups: in how many official sets has a part appeared in a colour."""
import os
import sqlite3
import sys

DB = os.environ.get("REBRICKABLE_DB", "/home/user/data-dl/lego-oracle/package/dist/data/lego.sqlite")
_c = None


def conn():
    global _c
    if _c is None:
        _c = sqlite3.connect(DB)
    return _c


def sets_with(part, color):
    return conn().execute("""select count(distinct i.set_num) from inventory_parts ip join inventories i on i.id=ip.inventory_id
                             where ip.part_num=? and ip.color_id=?""", (part, color)).fetchone()[0]


def name(part):
    r = conn().execute("select name from parts where part_num=?", (part,)).fetchone()
    return r[0] if r else None


def colors_of(part):
    return conn().execute("""select ip.color_id, c.name, count(distinct i.set_num) n from inventory_parts ip join inventories i on i.id=ip.inventory_id
                             join colors c on c.id=ip.color_id where ip.part_num=? group by ip.color_id order by n desc""", (part,)).fetchall()


if __name__ == "__main__":
    cols = [2, 14, 0, 72, 71, 25]
    print(f"{'part':10s} {'Grn':>4s} {'Yel':>4s} {'Blk':>4s} {'DBG':>4s} {'LBG':>4s} {'Org':>4s}  name")
    for p in sys.argv[1:]:
        print(f"{p:10s} " + " ".join(f"{sets_with(p, c):4d}" for c in cols) + f"  {name(p)}")
