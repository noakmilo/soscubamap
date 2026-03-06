def sort_categories_for_forms(categories):
    priority = {
        "accion-represiva": 0,
        "accion-represiva-del-gobierno": 0,
        "movimiento-tropas": 1,
        "movimiento-militar": 1,
        "desconexion-internet": 2,
    }
    return sorted(categories, key=lambda c: (priority.get(c.slug, 99), c.name))
