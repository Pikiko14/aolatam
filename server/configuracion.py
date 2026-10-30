"""
Configuracion del Servidor y Multiplicadores de Eventos.

Aqui puedes cambiar los multiplicadores de experiencia, habilidades y drops
sin tener que modificar la logica del servidor.
"""
import datetime

# Horarios del cliente, interpretados en hora LOCAL del servidor como Totem War.
# La duracion de Angel Arena es compatibilidad, no un dato oficial verificado.
DURACION_ANGEL_ARENA_MIN = 30

# Reconstruccion de servicios Lyceum: las probabilidades no vienen en los
# XML publicos. Son parametros de compatibilidad, NO tasas oficiales IGG.
ASTRO_PESOS_NORMAL = (1, 1, 1)  # intensidades I / II / III
ASTRO_PESOS_CRISTAL = (1, 1, 4)  # el tooltip promete mayor chance de III
STRAW_DROP_PROBABILIDAD = 0.50  # provisional; usuario recuerda caida alta


# =====================================================================
# MAPAS APAGADOS
# =====================================================================
# Solo Mainland abierto: Angel Lyceum, Heart of Eden (cuatro ciudades,
# territorios de faccion y campos de Totem War), las mazmorras de Eden y los
# mapas de sistema (casas, granja, competiciones, eventos). Las regiones son
# las de setting/eng/jumpmapclass.xml; las instancias de cada region van con
# ella. Para abrir una expansion, borra su bloque.
#
# Nadie entra a estos mapas: los portales, NPC, pergaminos, Superwing y Ring
# of Angel Wings se rechazan con aviso y sin gastar nada. Quien estaba dentro
# aparece en el Angel Lyceum al conectar o al revivir.
MAPAS_APAGADOS = frozenset({
    # Atlantis
    84,  # Blue Sea
    85,  # Colorful Coral Reefs
    86,  # Golden Beach
    87,  # Puqi Village
    88,  # Palm Base
    89,  # Wave Harbor
    90,  # Blue Ocean
    91,  # Sunken Ruins
    92,  # Shining Coast
    93,  # Dream Ocean
    94,  # Raging Reefs
    95,  # Quiet Ocean
    96,  # Coral Vale
    97,  # Evil Ship
    98,  # Lost Region
    101,  # Horrible Lost Region
    # Forest
    102,  # River Valley
    103,  # Secret Den
    104,  # Waterfall Camp
    105,  # Noisy Rain Forest
    106,  # Ancient Glide River
    107,  # Half-beast Hamlet
    108,  # Clouding Forest
    109,  # Giant Wooden Stairs
    110,  # Limitless Tower
    111,  # Cloud-top Land
    # Desert
    120,  # Crescent Valley
    121,  # Desert Racetrack
    122,  # Ghost Village
    123,  # Troop Outpost
    124,  # Ancient Front
    125,  # Fantastic Sand City
    126,  # Nightmare Palace
    127,  # Leviathan's Bedroom
    128,  # Dragon Field
    # Floating
    137,  # Vine Front
    138,  # Roam Battlefield
    139,  # Sky Pumice
    140,  # Winding Flower Corridor
    145,  # Botti Palace
    146,  # Airship Station
    147,  # Bouleuterion
    148,  # Season Garden
    # Candy
    151,  # Mushroom Village
    152,  # Building Blocks County
    153,  # Building Blocks City
    154,  # Fruit Town
    155,  # Chocolate Village
    156,  # Strawberry Garden
    157,  # Chocolate Forest
    158,  # Poker Castle
    # Jurassic
    161,  # Lost Cove
    162,  # Rock Forest
    163,  # Hoca Village
    164,  # Rex Point
    165,  # Raven Riverpoint
    166,  # Hunter's Ridge
    167,  # Shilly Desert
    168,  # Dinosaur Arena
    # Pharaoh
    169,  # Karang Desert
    170,  # Pharaoh Village
    171,  # Niro River
    172,  # Dune Oasis
    173,  # Cave of Falling Sand
    174,  # Goldbrick Road
    175,  # Ancient Tombs
    176,  # Unknown Chambers
    # East Orient
    192,  # Port Cherube
    193,  # Emerald Shores
    194,  # Angelic Cave
    195,  # Hazelnut Ridge
    196,  # Gaia Valley
    197,  # Dyna City
    198,  # Butterfly Garden
    199,  # Phoenix Palace
    # Silversnow Realm
    209,  # Feather Leaf Forest
    210,  # Snowball Village
    211,  # Illusory Maze
    212,  # Radiant Cave
    213,  # Iceberg Lake
    214,  # Subzero Market
    215,  # Silver Wing Cable Car Station
    216,  # Blizarro Castle
    # Space Cowboy
    222,  # Goldhill
    223,  # Steam Town
    224,  # Yeeha Bar
    225,  # Agysical Tunnel
    226,  # Sunset Valley
    227,  # Desolate Ruins
    228,  # Forbidden Sector
    229,  # Mundo Warship
    # Sakura Festival
    231,  # Samara Woods
    232,  # Edo City
    233,  # Joy Festival
    234,  # Sakura Valley
    235,  # Hot Spring Resort
    236,  # Fox Shrine
    237,  # Ninja Land
    238,  # Jade Tassel City
    # Sequoia
    245,  # Sweet Orchard
    246,  # Fruity Village
    247,  # Jade Garden
    248,  # Luscious Grange
    249,  # Branch Way
    250,  # Lost Trail
    251,  # Buzzing Stopover
    252,  # Queen Bee Hideout
    # Shuwa
    257,  # Mariam Waterway
    258,  # Shuwa Market
    259,  # Bayan Village
    260,  # Deserted Ruins
    261,  # Siam Square
    262,  # Hell Siam Square
    263,  # Mahal Altar
    264,  # Hell Mahal Altar
    # Sylvan Chaos
    274,  # Metal Scrapyard
    275,  # Rusty Pipe Lane
    276,  # Joaquin
    277,  # Scrap Iron Works
    278,  # Sylvan Gardens
    279,  # Paua Shell Harbor
    280,  # Drip-drop Passage
    281,  # Floral Palace
    # Magma Flux
    285,  # Brilliant Boneyard
    286,  # Ivory Forest
    287,  # Razorex Temple
    288,  # Whitefang Village
    289,  # Sleepy Spring
    290,  # Transient Waters
    291,  # Fragrant Courtyard
    292,  # Flamefang Sanctum
    # Arcana
    295,  # Starglow Path
    296,  # Academia Woods
    297,  # Mana Ruins
    298,  # Coo Village
    299,  # Ethereal Garden
    300,  # Daydream Library
    301,  # Reminiscence Cloister
    302,  # Enchanted Sanctum
    # Aeternia
    306,  # Dial Desert
    307,  # Greenfield
    308,  # Rainbow Town
    309,  # Antler Mesa
    310,  # Carrotiso
    311,  # Cogsville
    312,  # Chrono Ruins
    313,  # Apocalypso
    413,  # C-Dinosaur Arena
    414,  # C-End Time
    # Goldenia
    318,  # Emerald Coast
    319,  # Whisper Lake
    320,  # Twinkle Town
    321,  # Cobalt Market
    322,  # Grove of Bliss
    323,  # Twilight Mines
    324,  # Royal Ruins
    325,  # Radiant Castle
    # Abysston
    333,  # Ancient Landing
    334,  # Forsaken Crevasse
    335,  # Specter Village
    336,  # Crystal Marsh
    337,  # Crystal Quarry
    338,  # Shrouded Haven
    339,  # Peril Chasm
    340,  # Leviathan's Domain
    # Bearscape
    345,  # Hidden Grove
    346,  # Forest of Whispers
    347,  # Teddy Amusement
    348,  # City of Dreams
    349,  # Foodie Paradise
    350,  # Forbidden Dusk
    351,  # Nightmare City
    # Astralfield
    354,  # Whispering Hill
    355,  # Galaxia Square
    356,  # Pristine Lake
    357,  # Magma Field
    358,  # Rolling Sands
    359,  # Horizon Archives
    360,  # Galaxia Palace
    # Desolate Sea
    363,  # Deep Trench
    364,  # Ancient Rift
    365,  # Desolate City
    366,  # Abyssal Arena
    367,  # Poseidon Shrine
    368,  # Deep Prison
    369,  # Hadal Lair
    # Celestia
    381,  # Spring Garden
    382,  # Silent Lakeside
    383,  # Red Desert
    384,  # Chilly Village
    385,  # Pink Woods
    386,  # Frozen Region
    387,  # Wintry Realm
    # Warring Realm
    389,  # Pier Lane
    390,  # Busy Market
    391,  # Bath Area
    392,  # Manège
    393,  # Garrison
    394,  # Champions' Arena
    395,  # Warring Realm
    # Sun Sea Maze
    397,  # Floating Station
    398,  # Floral Alley
    399,  # Majestic Mansion
    400,  # Warm Villa
    401,  # Verdant Shrine
    402,  # Seaside Grotto
    403,  # Dragon's Lair
    # Cybertronica
    405,  # Sandy Heights
    406,  # Wise Institute
    407,  # Clank Oasis
    408,  # Ironbone Works
    409,  # Machinery Ruins
    410,  # Steely Circuit
    411,  # Core Zone
    # Night City Code
    416,  # Clink Harbor
    417,  # Neon Sky Corridor
    418,  # Black Market District
    419,  # Commercial Street
    420,  # Bling Plaza
    421,  # Ultimate Arena
    422,  # Secret Peak
})
AVISO_MAPA_APAGADO = 'This area is closed for now.'


def mapa_apagado(stage) -> bool:
    try:
        return int(stage) in MAPAS_APAGADOS
    except (TypeError, ValueError):
        return False


# =====================================================================
# ADMINISTRADORES (GM)
# =====================================================================
# Cuentas (el usuario con el que se entra, sin distinguir mayusculas) que
# pueden usar los comandos GM desde el chat: /item, /level, /notice, /twstart...
# El resto recibe un aviso y el comando no se ejecuta. /emote y /guild <texto>
# son de jugador y siguen abiertos. La consola del servidor y data/gm.txt no
# pasan por esta lista.
USUARIOS_GM = frozenset({
    # 'miusuario',
    'olasanmi',
    'elezeta'
})
AVISO_SIN_PERMISO_GM = 'GM commands are not available.'


def es_gm(usuario) -> bool:
    return bool(usuario) and str(usuario).casefold() in {u.casefold() for u in USUARIOS_GM}


# =====================================================================
# TOTEM WAR
# =====================================================================
# Campos (stage) con guerra. Los otros de los ocho originales -- 8 Crashing
# Hillock, 9 South of Mirror Lake, 12 North of Mirror Lake, 15 Mysterious
# Wetland, 17 Quiet Vale -- quedan como campo normal: totem decorativo, sin
# PvP y sin territorio de liga. Para devolverle la guerra, anade su numero.
CAMPOS_TOTEM_WAR = frozenset({
    11,  # Thunder Ruins
    16,  # Thorn Wasteland
    21,  # Dragon Graveyard
})


# =====================================================================
# NPCS OCULTOS
# =====================================================================
# {mapa: {npc_type o nombre, ...}}: esos NPC no aparecen en el mapa. Vale el
# npc_type (el numero) o el nombre exacto; el nombre quita todos los que se
# llamen asi (por ejemplo los cuatro 'House Pickets' del Lyceum, el 41).
# Los NPC de cada mapa estan en server/plantillas/<mapa>.json ('spawns').
# Los de eventos (Fashionable, Party Angel...) los pinta el propio cliente
# desde sus sp_*.xml: el servidor los quita de ahi al arrancar, con el juego
# cerrado, igual que las descripciones. Para esos vale solo el numero.
NPCS_OCULTOS = {
    41: {           # Angel Lyceum
        11119,      # Hestia
        8994,       # Fashionable (evento)
        8912,       # Daily Events Clerk
        14319,      # Gear Clerk
        14419,      # Party Angel
        8814,       # Fortunia
        14888,      # Scrollmaker
        2008,       # Ticket Angel
        14701,      # Astrologer
        6883,       # Assassin Master
        2686,       # Little Exp Angel
        24516,      # Astral Angel (evento: sp_star_angel.xml, mapa 41)
        24801,      # Reissue Angel (evento: sp_reissue_angel.xml, mapa 41)
    },
}


# =====================================================================
# FICHA DEL ROBOT: VELOCIDAD DE LAS PIEZAS
# =====================================================================
# Numero de stat con el que se ensena en verde la velocidad de recoleccion y
# de fabricacion de las piezas (Fast Gear, Energy Core) en la ficha del
# robot. Poner 0 para no enviarlo; el bono se aplica igual aunque no se vea.
ID_EXTRA_RECOLECCION = 228
ID_EXTRA_FABRICACION = 232


# =====================================================================
# PREMIOS QUITADOS DE BOLSAS
# =====================================================================
# {bolsa: {objeto, ...}}: esos objetos ya no salen al abrir esa bolsa. Los
# demas premios conservan su peso, asi que su probabilidad sube en proporcion.
# La descripcion del cliente los sigue listando.
QUITAR_DE_BOLSAS = {
    11963: {3852},  # HalloweenArtisan Lucky Bag: sin Dragon Egg
    11259: {6394},  # Virgo Mage Lucky Bag (2): sin Great Orange Potion
    11257: {6394},  # Virgo Spearman Lucky Bag (2): sin Great Orange Potion
    11256: {6394},  # Virgo Axeman Lucky Bag (2): sin Great Orange Potion
    11255: {6394},  # Virgo Swordsman Lucky Bag (2): sin Great Orange Potion
}


# =====================================================================
# DESCRIPCIONES DE BUFFS
# =====================================================================
# {magia: texto}: lo que ensena el icono del buff al pasar el raton. Se
# escribe en magic.xml del cliente local igual que DESCRIPCIONES_ITEMS.
DESCRIPCIONES_MAGIAS = {
    1897: 'Increase Maximum HP by 500.',   # Recovery Notice (4297)
}


# =====================================================================
# DESCRIPCIONES DE OBJETOS
# =====================================================================
# {objeto: texto}: al arrancar, el servidor las escribe en el cliente local
# (update26.pak), con el juego cerrado. Cada jugador necesita ese .pak.
DESCRIPCIONES_ITEMS = {
    11963: ('Open to get one of the following items: Power Ring, Polar Region Penguin Robot, '
            'Universal Gift Box, Advanced Koala Robot 2, Producing Fast Gear Lvl 3, '
            'Collecting Energy Core Lvl 3, Moon Warrior Helmet, Craftsman Soul Box, Pestle, '
            'Safe Key (30 days), Stall Gold Card 3, Monster Breath (30 days), Mighty Fuel (30 days), '
            'Transform Luck Bag, Super Broadcasting x5, Spacious Bank x20, Pet Feed x10, '
            'Experience Pet Gem Lucky Bag, Recovery Notice.'),
    # Advance Lucky Bag
    14710: ('Open to get one of the following items: Angel Amulet, Monster Breath, Mighty Fuel (7 '
            'days), Breeze Woods Scroll x12, Dark City Scroll x12, Iron Castle Scroll x12, Aurora '
            'City Scroll x12, Big-2 Common Card 3, Double Skill Exp Card (30 M.) x12, Super '
            'Broadcasting x3, Flaming Beetle Bag, Hiphop Dog Warplane, Roll Kitty Warplane, Blue Evil'
            " Cat, Black Fight Lizard, Evil Cat's Staff, Ice Bow, Spear of Earth, Blood Axe of Beast "
            'God, Sword of Goddess.'),
    # Wulfie Master Lucky Bag(2)
    11776: ("Open to get one of the following items: Snow Evil Cat, Top Gown Box Lvl 35, Evil Cat's "
            'Staff, Magic Alchemic Gown, Moonnight Mantle, Magic Alchemic Cap, Autumn Fiesta Fan, '
            'Diamond Bag, Transform Luck Bag, Defend Gift Box, Attack Gift Box, City Scroll Bag, '
            "Master's Love x3, Pet Feed x4, Super Broadcasting x2, 8 Carat Exp Stone x6, Lucky Card "
            '(30 Minutes) x10, Pet Amulet x20.'),
    # Wulfie Archer Lucky Bag(2)
    11775: ('Open to get one of the following items: Flame Chariot, Top Light Armor Box Lvl 35, Ice '
            'Bow, Ice Stone Armor, Angel Wings, Icy Hard-Leather Cap, Autumn Fiesta Fan, Diamond Bag,'
            " Transform Luck Bag, Defend Gift Box, Attack Gift Box, City Scroll Bag, Master's Love "
            'x3, Pet Feed x4, Super Broadcasting x2, 8 Carat Exp Stone x6, Lucky Card (30 Minutes) '
            'x10, Pet Amulet x20.'),
    # Wulfie Spearman Lucky Bag(2)
    11774: ('Open to get one of the following items: Flame Chariot, Top Heavy Armor Box Lvl 35, Spear'
            ' of Earth, Beastman Leather Armor, Bat Wings, Beastman Viking Cap, Autumn Fiesta Fan, '
            'Diamond Bag, Transform Luck Bag, Defend Gift Box, Attack Gift Box, City Scroll Bag, '
            "Master's Love x3, Pet Feed x4, Super Broadcasting x2, 8 Carat Exp Stone x6, Lucky Card "
            '(30 Minutes) x10, Pet Amulet x20.'),
    # Wulfie Axeman Lucky Bag(2)
    11773: ('Open to get one of the following items: Moon Gerbil, Top Heavy Armor Box Lvl 35, Blood '
            'Axe of Beast God, Beastman Leather Armor, Crystal Shield, Beastman Viking Cap, Autumn '
            'Fiesta Fan, Diamond Bag, Transform Luck Bag, Defend Gift Box, Attack Gift Box, City '
            "Scroll Bag, Master's Love x3, Pet Feed x4, Super Broadcasting x2, 8 Carat Exp Stone x6, "
            'Lucky Card (30 Minutes) x10, Pet Amulet x20.'),
    # Wulfie Master Lucky Bag(1)
    11771: ('Open to get one of the following items: Night Cat, Fiery Staff, Green Beetle Bag, Magic '
            'Gown of Flame God, Devil Wings, Gloves of the Flame God, Fiery Boots, Holy Alchemic Cap,'
            ' Pearl Refining, Diamond Bag, Transform Luck Bag, Defend Gift Box, Attack Gift Box, City'
            " Scroll Bag, Master's Love x4, Pet Feed x6, Super Broadcasting x2, 8 Carat Exp Stone x8."),
    # Wulfie Archer Lucky Bag(1)
    11770: ('Open to get one of the following items: Handsome Burro, Splash Slingshot, Red Beetle '
            'Bag, Eagle Breastplate, Fighting Wings, Eagle Wristlet, Eagle Boots, Eagle Hood, Pearl '
            'Refining, Diamond Bag, Transform Luck Bag, Defend Gift Box, Attack Gift Box, City Scroll'
            " Bag, Master's Love x4, Pet Feed x6, Super Broadcasting x2, 8 Carat Exp Stone x8."),
    # Wulfie Spearman Lucky Bag(1)
    11769: ('Open to get one of the following items: Marmot, Spear of Yugo, Red Beetle Bag, Golden '
            'Chain Armor, Fighting Wings, Golden Chain Cuff, Golden Chain Boots, Eagle Hood, Curse '
            'Refining, Diamond Bag, Transform Luck Bag, Defend Gift Box, Attack Gift Box, City Scroll'
            " Bag, Master's Love x4, Pet Feed x6, Super Broadcasting x2, 8 Carat Exp Stone x8."),
    # Wulfie Axeman Lucky Bag(1)
    11768: ('Open to get one of the following items: Hell Wolf, Rainbow Axe, Green Beetle Bag, Golden'
            ' Chain Armor, Angel Knights Shield, Golden Chain Cuff, Golden Chain Boots, Eagle Hood, '
            'Curse Refining, Diamond Bag, Transform Luck Bag, Defend Gift Box, Attack Gift Box, City '
            "Scroll Bag, Master's Love x4, Pet Feed x6, Super Broadcasting x2, 8 Carat Exp Stone x8."),
    # Wulfie Swordman Lucky Bag(1)
    11767: ("Open to get one of the following items: Icy Lizard, Adas's Blade, Red Beetle Bag, Golden"
            ' Chain Armor, Angel Knights Shield, Golden Chain Cuff, Golden Chain Boots, Golden Full-'
            'face Helmet, Curse Refining, Diamond Bag, Transform Luck Bag, Defend Gift Box, Attack '
            "Gift Box, City Scroll Bag, Master's Love x4, Pet Feed x6, Super Broadcasting x2, 8 Carat"
            ' Exp Stone x8.'),
    # Virgo Mage Lucky Bag( 2 )
    11259: ("Open to get one of the following items: Elf Egg, Thunder Bird, Angel's Blessing, Night "
            'Cat, Slarm Suit Egg, Clean Diamond Bag, Necklace of Goddess, Mask Lucky Bag, Lvl 5 Lucky'
            ' Ride Feed, 5-star Lucky Piercing Hammer, 5-star Lucky Enhanced Pestle, Improved Pet '
            'Feed, Stall Gold Card 3, Surprise Lucky Bag, Pet Feed x10, 8 Carat Exp Stone x6, Super '
            'Broadcasting x4, Angel Amulet x6, Spell Attack Scroll x12.'),
    # Virgo Spearman Lucky Bag( 2 )
    11257: ('Open to get one of the following items: Elf Egg, Thunder Bird, Saw Spear, Gold Lizard, '
            'Knight Suit Egg, Clean Diamond Bag, Sage Mantle, Mask Lucky Bag, Lvl 5 Lucky Ride Feed, '
            '5-star Lucky Piercing Hammer, 5-star Lucky Enhanced Pestle, Improved Pet Feed, Stall '
            'Gold Card 3, Surprise Lucky Bag, Pet Feed x10, 8 Carat Exp Stone x6, Super Broadcasting '
            'x4, Angel Amulet x6, Attack Scroll x12.'),
    # Virgo Axeman Lucky Bag( 2 )
    11256: ('Open to get one of the following items: Elf Egg, Thunder Bird, Fish Axe, Icy Lizard, '
            'Knight Suit Egg, Clean Diamond Bag, Vein Shield, Mask Lucky Bag, Lvl 5 Lucky Ride Feed, '
            '5-star Lucky Piercing Hammer, 5-star Lucky Enhanced Pestle, Improved Pet Feed, Stall '
            'Gold Card 3, Surprise Lucky Bag, Pet Feed x10, 8 Carat Exp Stone x6, Super Broadcasting '
            'x4, Angel Amulet x6, Attack Scroll x12.'),
    # Virgo Swordsman Lucky Bag( 2 )
    11255: ('Open to get one of the following items: Elf Egg, Thunder Bird, Rose Sword, Evil Lizard, '
            'Knight Suit Egg, Clean Diamond Bag, Vein Shield, Mask Lucky Bag, Lvl 5 Lucky Ride Feed, '
            '5-star Lucky Piercing Hammer, 5-star Lucky Enhanced Pestle, Improved Pet Feed, Stall '
            'Gold Card 3, Surprise Lucky Bag, Pet Feed x10, 8 Carat Exp Stone x6, Super Broadcasting '
            'x4, Angel Amulet x6, Attack Scroll x12.'),
}


# =====================================================================
# MULTIPLICADORES BASE (Valores por defecto del servidor)
# =====================================================================
# 1.0 = Experiencia normal oficial
# 2.0 = Doble experiencia, etc.
TASA_EXP_BASE = 2.0         # Multiplicador de EXP de personaje
TASA_SKILL_EXP_BASE = 2     # Multiplicador de EXP de habilidades (stamina/skills)
TASA_DROP_BASE = 0.1         # Multiplicador de probabilidad de drop de items
TASA_ORO_BASE = 2.0           # Multiplicador de oro obtenido de monstruos

# =====================================================================
# CONFIGURACION DE CASAS, BAILES Y PET ROOM
# =====================================================================
MULTIPLICADOR_EXP_PET = 10.0           # Multiplicador de EXP para mascotas en el patio de crianza (477..486)
EXP_BASE_PET_ROOM_TICK = 20           # EXP base por tick (~5 segundos) para mascotas entrenando en casa
COOLDOWN_BAILE_SEGUNDOS = 172800          # Cooldown en segundos para volver a usar un Ball Ticket (por defecto 60s para testing rapido)
TIEMPO_PREPARACION_BAILE_SEGUNDOS = 180 # Tiempo de preparacion antes del baile (oficial 180s = 3 minutos)
DURACION_BAILE_SEGUNDOS = 10         # Duracion del baile una vez iniciado (por defecto 60s)

# =====================================================================
# CONFIGURACION DE EVENTOS DE FIN DE SEMANA / SEMANALES
# =====================================================================
# Si es True, activa automaticamente el bono de fin de semana (Viernes, Sabado y Domingo)
EVENTO_FIN_DE_SEMANA_AUTOMATICO = True

# Si prefieres forzar el evento encendido o apagado manualmente:
# Pon True para forzar evento activo siempre, o False para desactivarlo.
EVENTO_DOBLE_EXP_FORZADO = False

# Multiplicador adicional que se aplica durante el evento
BONUS_EVENTO_EXP = 2.0
BONUS_EVENTO_SKILL = 2.0


def es_fin_de_semana() -> bool:
    """Devuelve True si hoy es viernes (4), sabado (5) o domingo (6)."""
    if EVENTO_DOBLE_EXP_FORZADO:
        return True
    if not EVENTO_FIN_DE_SEMANA_AUTOMATICO:
        return False
    dia = datetime.datetime.now().weekday()
    return dia in (4, 5, 6)


# LOS BONOS DE EXP DE LOS BUFFS SE SUMAN AL MULTIPLICADOR, NO LO MULTIPLICAN
# (pedido del usuario, 21/10/2026). Con TASA_SKILL_EXP_BASE = 1000 el golpe da
# 1000 de skill exp; el Astro Pisces III (+300 % de skill exp) lo deja en
# x1003, no en x4000. Igual con la EXP: una carta de doble EXP (100 en su
# hechizo) es +1 y una x5 (400) es +4. El % sale del propio buff (los del
# Lyceum lo traen en exp_extra_pct / skill_exp_extra_pct) o, si no, de las
# columnas 經驗加倍 / 技能經驗加倍 de su hechizo en magic.
_PCT_MAGIA = {}


def _pct_de_magia(mid, columna):
    clave = (int(mid), columna)
    if clave not in _PCT_MAGIA:
        v = 0
        try:
            import pathlib, sqlite3
            con = sqlite3.connect(pathlib.Path(__file__).parent.parent / 'corpus' / 'content.db')
            r = con.execute('select "%s" from magic where id=?' % columna, (str(int(mid)),)).fetchone()
            con.close()
            v = int(r[0]) if r and str(r[0] or '').isdigit() else 0
        except Exception:
            v = 0
        _PCT_MAGIA[clave] = v
    return _PCT_MAGIA[clave]


def pct_buffs(buffs, campo, columna):
    """Suma de los % de EXP (o skill exp) de los buffs activos."""
    import time
    ahora = time.time()
    total = 0.0
    for clave, e in (buffs or {}).items():
        if not isinstance(e, dict) or e.get('fin', 0) <= ahora:
            continue
        if e.get(campo):
            total += float(e[campo])
            continue
        mid = e.get('id') or (e.get('mag') or {}).get('id') or clave
        if str(mid).isdigit():
            total += _pct_de_magia(mid, columna)
    return total


def multiplicador_exp(buffs: dict = None) -> float:
    """EXP de personaje: tasa base (x evento de fin de semana) + los % de los buffs."""
    m = TASA_EXP_BASE
    if es_fin_de_semana():
        m *= BONUS_EVENTO_EXP
    if buffs:
        if buffs.get('doble_exp'):
            m += 1.0
        if buffs.get('triple_exp'):
            m += 2.0
        # House cleanliness belongs to the house magic index. Eilian's
        # 2292..2295 affect equipment enhancement, never character EXP.
        m += pct_buffs(buffs, 'exp_extra_pct', '經驗加倍') / 100
    return m


def multiplicador_skill_exp(buffs: dict = None) -> float:
    """Skill EXP: tasa base (x evento de fin de semana) + los % de los buffs."""
    m = TASA_SKILL_EXP_BASE
    if es_fin_de_semana():
        m *= BONUS_EVENTO_SKILL
    if buffs:
        if buffs.get('doble_skill_exp'):
            m += 1.0
        m += pct_buffs(buffs, 'skill_exp_extra_pct', '技能經驗加倍') / 100
    return m


def multiplicador_drop(buffs: dict = None) -> float:
    """Calcula el multiplicador total de drops."""
    m = TASA_DROP_BASE
    if es_fin_de_semana():
        m *= 1.5
    m += pct_buffs(buffs, 'drop_extra_pct', '\u6389\u5bf6\u52a0\u500d') / 100
    return m


# =====================================================================
# MODO PRUEBAS / DEBUG
# =====================================================================
# Si es True, cualquier compra en tiendas NPC cuesta solo 1 de oro por item.
# Si es False, se cobra el precio normal de item.xml.
FLAG_ORO = False
COMPRAS_1_DE_ORO = FLAG_ORO

# Creditos de rango con los que entra el personaje.
#
# La ficha muestra "Credit:" y, encima, el rango: son los nombres 1700 a 1719
# de string.xml, de "Growing Power" a "God's Mouthpiece". En la captura del
# 28/09/2026 el personaje tenia 4.610.115 creditos y la ficha decia "Order
# founder", que es el 1716, o sea el rango 17 contando "Growing Power" como
# el 1.
#
# ENCONTRADOS (05/10/2026): los cortes entre un rango y otro SI estan en el
# cliente. Son la columna 功勳 de setting/level.xml, y hay exactamente 20
# valores, uno por rango:
#
#   1:0        2:1000      3:2400      4:4500      5:8500
#   6:17000    7:33000     8:60000     9:103000   10:170000
#  11:280000  12:457000   13:730000   14:1130000  15:1690000
#  16:2745000 17:4250000  18:6380000  19:9370000  20:15750000
#
# Cuadran con lo medido: 4.610.115 cae entre el 17 y el 18, y la ficha de la
# captura decia "Order founder", que es el 17. La tabla la lee
# combate.creditos_de_rango() del propio xml, no esta copiada a mano, y al
# subir de rango el servidor pone los creditos que le tocan.
#
# En cero no se manda nada y la ficha queda como estaba.
CREDITOS_INICIALES = 0

# Objetos con los que empieza el almacen del banco, como {ranura: item_id}.
#
# Esto esta aqui por una duda que no se ha podido resolver leyendo: el paquete
# del almacen (0x004E) lleva el mismo cuerpo que el inventario -- un LE32 con
# el numero de entradas y detras las entradas, de 86 bytes las corrientes y
# 119 las equipables -- y en la captura del servidor real llevaba OCHO. El
# nuestro sale con cero porque el personaje no tiene nada guardado, y la
# ventana no se abre.
#
# Las dos funciones del cliente que crean la ventana del banco solo lo hacen
# cuando el primer LE32 dividido por 1000 vale 2 o 3, pero en la captura vale
# 8, que da 0 por esa cuenta. Asi que la ventana no la abre ese numero: o la
# abre el cliente solo al elegir la opcion del dialogo, y entonces necesita
# tener contenido que mostrar, o hay un camino que todavia no se ha visto.
#
# Con esto se prueba lo primero. Si con un objeto dentro el almacen abre, era
# la lista vacia; en cuanto se sepa, esto sobra y se quita.
ALMACEN_INICIAL = {}

# =====================================================================
# REGENERACION DE HP Y MP
# =====================================================================
# Antes era plana: +6 MP y +12 HP por tick, vinieran de donde vinieran. A
# nivel bajo se nota, pero a nivel 300, con 121.440 de MP, llenar la barra a
# seis por segundo son CINCO HORAS Y MEDIA.
#
# Ahora es un porcentaje del maximo, y el porcentaje sube con el nivel. Se
# mantiene el minimo plano de antes para que a nivel 1 no regenere menos de
# lo que regeneraba.
#
# De pie hay que llevar dos segundos quieto y fuera de combate; sentado
# (tecla Insert) el tick es cada segundo y el porcentaje mucho mayor.
#
#   por tick = maximo * (base + nivel * por_nivel) / 100
#
# A nivel 1 de pie sale 0,5% cada dos segundos y sentado 2% cada segundo. A
# nivel 300, 2% y 8%: la barra de MP se llena en unos 70 segundos de pie y en
# unos 13 sentado.
REGEN_PIE_BASE = 0.5          # % del maximo, a nivel 1
REGEN_PIE_POR_NIVEL = 0.005   # % que se suma por cada nivel
REGEN_SENTADO_BASE = 2.0
REGEN_SENTADO_POR_NIVEL = 0.02
REGEN_MINIMO_HP_PIE = 6       # los valores planos de antes, como suelo
REGEN_MINIMO_MP_PIE = 6
REGEN_MINIMO_HP_SENTADO = 12
# Sentado el MP tenia el mismo suelo que de pie, seis, asi que a nivel 1
# sentarse no servia de nada para el mana. Se sube a doce, como el HP.
REGEN_MINIMO_MP_SENTADO = 12


def regenera(maximo: int, nivel: int, sentado: bool, es_hp: bool) -> int:
    """Cuanto se recupera en un tick."""
    if sentado:
        pct = REGEN_SENTADO_BASE + nivel * REGEN_SENTADO_POR_NIVEL
        piso = REGEN_MINIMO_HP_SENTADO if es_hp else REGEN_MINIMO_MP_SENTADO
    else:
        pct = REGEN_PIE_BASE + nivel * REGEN_PIE_POR_NIVEL
        piso = REGEN_MINIMO_HP_PIE if es_hp else REGEN_MINIMO_MP_PIE
    return max(piso, int(round(maximo * pct / 100.0)))

# =====================================================================
# MEJORAS DE EQUIPO (morteros, martillos, piensos y gemas)
# =====================================================================
# Si es True, TODA mejora sale bien: morteros, piensos de montura y de
# mascota, y martillos de perforar. Es para probar sin gastar cien objetos.
#
# Con ella en False se usa mejoras.probabilidad(), que NO esta medida: no hay
# ninguna captura de un fallo. Es una curva inventada que empieza segura y
# baja hasta el 20% en la ultima mejora. En cuanto haya numeros de verdad se
# cambia ahi.
MEJORAS_SIEMPRE_EXITO = False

# Si es True, el martillo verde da el MAXIMO de todos los stats que puede dar
# en vez de sortear cada uno dentro de su rango. El cuadro del juego enseña
# esos rangos: "Attack 0 (0-210), Rigor 3 (0-54), Movement Speed 37 (0-40)".
MARTILLO_VERDE_TODOS_LOS_STATS = False

# El rango con el que entra el personaje: 1 es "Growing Power" y 20 "God's
# Mouthpiece". Viaja en el byte 93 del 0x0002, pegado a los creditos, y NO se
# calcula de ellos: los cortes entre un rango y otro no estan en los datos del
# cliente, asi que lo decide el servidor.
RANGO_INICIAL = 1

# ID del consumible custom (Rank Promotion Medal, basado en el sprite 8921 de
# la General's Medal 5873, agregado al final de item9.xml del update26) que
# sube +1 rango automaticamente por cada uso (hasta el rango maximo 20).
ITEM_MEDALLA_RANGO = 83266


# =====================================================================
# MUNICION DE ARQUEROS (Arcos + Flechas / Hondas + Bolitas)
# =====================================================================
# Si es True (como en el servidor Global actual), las flechas y bolitas/balas
# equipadas en la mano izquierda (ranura 4) son infinitas y no se gastan al atacar.
# Si es False, cada disparo con arco u honda consume 1 unidad de municion.
FLECHAS_INFINITAS = False


# =====================================================================
# LOGROS (Achievements)
# =====================================================================
# Con False se apaga server/app.py:_logros_actualizar() entero: no se evalua ni se otorga
# ningun logro nuevo (ranking, los ampliados ni los de matar/puntos), no sale el aviso de
# "Achievement completed", no se reparte el Super BC del primer titulo y el panel de logros
# (0x0155) no se refresca con nada nuevo. Los contadores (_logros_contar) se siguen sumando
# igual -- no se pierde progreso -- para que al volver a poner esto en True los logros que ya
# se cumplieron entre tanto se otorguen de una vez.
LOGROS_ACTIVOS = True


# =====================================================================
# MODO ESTACIONAL DEL CLIENTE Y ACTUALIZADOR LOCAL (START.EXE)
# =====================================================================
# Controla el tema visual del Angel Lyceum (map041.mpc) que el servidor
# sincroniza automaticamente con el cliente local:
#   - 'normal'    : Angel Lyceum clasico sin nieve (update25/map041.mpc)
#   - 'navidad'   : Angel Lyceum nevado de Navidad (update26/map041.mpc)
#   - 'halloween' : Angel Lyceum de Halloween (041halloween.mpc)
#   - 'sakura'    : Angel Lyceum de cerezos en flor (041sakura.mpc)
#   - 'verano'    : Angel Lyceum de festival de verano / Matsuri (041matsuri.mpc)
MODO_ESTACION = 'halloween'

# Ruta local del cliente para sincronizar el modo estacional y el launcher START.EXE
# Donde esta el cliente. Es solo una PISTA: si no esta ahi, el servidor lo
# busca solo (cliente_local.ruta_cliente). Da por bueno cualquier directorio
# que tenga Angel.exe y al menos un .pak, y mira en este orden: la variable
# de entorno AO_CLIENTE, esta ruta, los sitios habituales de instalacion, y
# los vecinos del propio repo -- que es lo normal, el cliente al lado del
# servidor. Dejarla vacia tambien vale.
RUTA_CLIENTE = r'C:\AO\Angels Online'
PUERTO_UPDATE_FTP = 2121

# EL PARCHE PARA LOS JUGADORES (server/parche.py). Al arrancar se genera
# parches/update27.pak con todo lo que el servidor cambia en el cliente.
#   PARCHE_EN_LAUNCHER: si el update3.ini lo anuncia al launcher. Apagado
#     hasta probar con START.EXE que lo descarga bien.
#   PARCHE_HOST: la IP o el dominio que se le da al launcher (y la del modo
#     pasivo del FTP). En local 127.0.0.1; al subir, la publica.
#   PARCHE_ESCUCHAR: donde escucha el servidor de actualizaciones. 127.0.0.1
#     solo atiende a esta maquina; '0.0.0.0' a todos (al subir).
#   PARCHE_PASV_PUERTOS: rango de puertos TCP para las conexiones de datos del
#     FTP (modo pasivo). (0, 0) = cualquiera (vale en local); en un VPS con
#     firewall hay que fijarlo y abrirlo, p. ej. (40000, 40050).
# Las tres se pueden fijar sin tocar este archivo con variables de entorno
# (AO_PARCHE_HOST, AO_PARCHE_ESCUCHAR, AO_PARCHE_PASV=40000-40050,
# AO_PARCHE_EN_LAUNCHER=1): asi el servidor de un VPS y el de tu PC usan el
# mismo codigo. Con ESCUCHAR distinto de 127.0.0.1 el HTTP solo sirve las
# paginas de noticias (/news.htm): el panel de control (/p.htm) es solo local.
import os as _os
PARCHE_EN_LAUNCHER = _os.environ.get('AO_PARCHE_EN_LAUNCHER', '0') == '1'
# Golpe de quien pelea con dos armas: True = tipo y animacion del arma de la mano derecha (el ataque automatico se ve); False = (0, 0), como antes.
DUALES_GOLPE_COMO_ARMA = _os.environ.get('AO_DUALES_GOLPE', '1') != '0'
PARCHE_HOST = _os.environ.get('AO_PARCHE_HOST', '127.0.0.1')
# Pak donde el launcher del cliente guarda el parche (sin .pak). Vacio = update27, el de siempre. El launcher falla al fusionar
# entradas que ya existen en el pak de destino (solo instalaba bien la primera vez), asi que cada entrega que cambie archivos
# va a un pak nuevo (update28..update31: el juego carga hasta el 31 y gana el de numero mas alto).
PARCHE_PAK_LAUNCHER = _os.environ.get('AO_PARCHE_PAK_LAUNCHER', '')
PARCHE_ESCUCHAR = _os.environ.get('AO_PARCHE_ESCUCHAR', '127.0.0.1')
try:
    _a, _b = _os.environ.get('AO_PARCHE_PASV', '0-0').split('-')
    PARCHE_PASV_PUERTOS = (int(_a), int(_b))
except ValueError:
    PARCHE_PASV_PUERTOS = (0, 0)
# 8080 cae dentro de un intervalo TCP reservado por Windows en algunas
# instalaciones (por ejemplo 8067-8166), lo que produce WinError 10013 aun
# cuando ningun proceso lo este escuchando. 8280 conserva el mismo largo en
# la URL parcheada de START.EXE y queda fuera de ese intervalo.
PUERTO_UPDATE_HTTP = 8280


# A que nivel sale una mascota nueva. Los stats los saca de petattrib con su
# clase y este nivel, y estan comprobados: una Battlemaid (item 20012) a
# nivel 246 da 12100 de ataque, 15755 de defensa, 3137 de ataque magico,
# 4431 de defensa magica, 1947 de rigor, 1127 de agilidad, 18775 de vida y
# 9074 de mana, que es exactamente la ficha que enseñaba el juego.
#
# A nivel 1 la mascota es inservible, asi que aqui se pone a que nivel
# quieres que aparezcan las que da el comando /item.
MASCOTA_NIVEL_INICIAL = 1

# Deja en blanco la pantalla del logo que sale al abrir el cliente.
# Solo toca UPDATE21.PAK, y siempre deja un .bak antes.
QUITAR_LOGO_ARRANQUE = False

# Quita las once reglas de exclusion entre ramas de habilidad (Life<->Wraith,
# Chaos<->Earth, Meditate<->Enhance, Grapple<->Snipe y el trio
# Mantle/Garment/Vestment). Son el atributo 互斥N de setting/eng/skill.xml;
# el servidor nunca las comprobo, quien se negaba era el selector del
# cliente. Se deja un skill.xml suelto en el cliente, y para deshacerlo
# basta borrarlo.
RAMAS_SIN_EXCLUSION = True

# Espera entre dos consumibles de HP/MP (pociones y comida). El cliente la lee de magic.xml
# (後置時間, parche de tools/parche_pociones.py); el servidor la exige tambien, por si alguien
# edita sus archivos. TOLERANCIA absorbe la irregularidad de la red entre dos usos legitimos.
COOLDOWN_POCION_S = 1.0
COOLDOWN_POCION_TOLERANCIA_S = 0.15


# Extra (en %) sobre la velocidad de las cartas de recoleccion y fabricacion (Collection / Facture Speedup Card
# y sus variantes): una carta de +50% da 50 * 1.30 = 65. Pedido del usuario, 29/10/2026. 0 = el valor del xml.
BONO_CARTAS_VELOCIDAD_PCT = 30
