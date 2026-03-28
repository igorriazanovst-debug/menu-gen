import os

cwd = os.getcwd()
path = os.path.join(cwd, "src", "pages", "Menu", "MenuPage.tsx")

with open(path, "r", encoding="utf-8") as f:
    content = f.read()

old = "const dayItems = menu.items.filter((i) => i.day_offset === day);"
new = "const dayItems = (menu.items ?? []).filter((i) => i.day_offset === day);"

content = content.replace(old, new)

old2 = "setMenus(data.results);"
new2 = """\
const d = data as any;
      if (Array.isArray(d)) setMenus(d);
      else if (Array.isArray(d?.results)) setMenus(d.results);
      else setMenus([]);"""

content = content.replace(old2, new2)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("fixed: MenuPage.tsx")
