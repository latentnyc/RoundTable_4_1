from app.models import Enemy, Player
e = Enemy(id="1", name="Goblin", type="Goblin", hp_current=15, hp_max=15, position={"q":0,"r":0,"s":0}, is_ai=False)
print("ENEMY:", type(e), getattr(e, 'hp_current', -1))
p = Player(id="2", name="Jenath", role="Wizard", hp_current=17, hp_max=17, position={"q":0,"r":0,"s":0}, is_ai=False)
print("PLAYER:", type(p), getattr(p, 'hp_current', -1))
