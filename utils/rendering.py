

class RenderSettings:
    STANDARD = {
        "border": ["layout", "peach_border"],
        "biobox": ["layout", "biobox"],
        "decor": ["layout", "decorative"],
        "colors": {"bg": (170, 68, 68),
                   "fame": "#d79686"
        }
    }
    SUPERLIKE = {
        "border": ["layout", "flame_border"],
        "biobox": ["layout", "biobox_flame"],
        "decor": [None],
        "colors":  {"bg":  (255, 102, 10),
                    "fame": "#fe9005"
        }
    }
    CROWN = {
        "border": ["layout", "king_border"],
        "biobox": ["layout", "biobox_king"],
        "decor": ["layout", "decorative_king"],
        "colors": {"bg": (170, 68, 68),
                   "fame": "#ecc625"
                   }
    }
    PEPE = {
        "border": ["layout", "dynny_border"],
        "biobox": ["layout", "biobox"],
        "decor": ["layout", "decorative"],
        "colors": {"bg": (170, 68, 68),
                   "fame": "#d79686"
        }
    }

def get_user_settings(user_id):
    # For Owner specifically
    if user_id == 394859035209498626:
        return RenderSettings.CROWN

    # For Dynny specifically
    if user_id == 214390619345387520:
        return RenderSettings.PEPE

    # If nothing is specified, return standard
    return RenderSettings.STANDARD
