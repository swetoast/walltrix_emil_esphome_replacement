"""Applies a design to a clock: sends it straight to Home Assistant, then checks that it works.

Home Assistant needs one thing per clock: a template sensor that works out the ring colours. Applying a
design creates that sensor, or updates it when the clock showed another design before, so a clock only
ever has one. It is made as a template sensor helper (Settings > Devices & services > Helpers) through the
same API the Helpers page uses, so it needs only a long-lived token from an administrator account and no
access to Home Assistant's files. Brightness is not part of this: the clock's firmware dims it.

Nothing is replaced that Ring Studio did not make: an entity with the same ID from somewhere else, for
example a YAML package from an earlier export, is reported instead of being duplicated.
"""

import time

from . import generate
from .model import Clock, ha_slug

OLD_AUTOMATION = "ring_studio_adaptive_brightness"  # earlier versions dimmed the clocks from Home Assistant
HEX = set("0123456789abcdef")


def helper_name(clock):
    """A helper name whose entity ID is the one the clock listens to, sensor.<device name>_ring_colors."""
    base = clock.friendly if ha_slug(clock.friendly) == clock.name else clock.name.replace("_", " ").title()
    return f"{base} Ring Colors"


def apply(ha, clock: Clock, say=lambda ok, line: None, wait=12.0, updated=True):
    """Puts `clock.design` on the clock and checks it. `say(ok, line)` reports each step as it happens.
    Returns True when the clock's sensor is in Home Assistant and shows the design's colours.

    After a rename, the helper made under an earlier name is removed, but only once the clock runs firmware with
    the new name (`updated`): until then it still reads the old sensor."""
    try:
        user = ha.current_user()
        if not user.get("is_admin"):
            say(False, f"The token belongs to {user.get('name') or 'a user'}, who is not an administrator. Home "
                       "Assistant lets only administrators add helpers. Make a long-lived token while logged in "
                       "as an administrator (your profile, Security tab) and paste it in Connect Home Assistant.")
            return False
        helpers = ha.template_helpers()
        states = {s["entity_id"]: s for s in ha.states()}
        name, entity, template = helper_name(clock), clock.colors_entity, generate.jinja(clock)
        if name in helpers:
            ha.update_template_sensor(helpers[name], template)
            say(True, f"Updated the helper {name}")
        elif entity in states and not _left_over(ha, states[entity], f"{clock.name}_ring_colors", "template"):
            say(False, f"{entity} already exists and is not a Ring Studio helper. If it comes from a Ring Studio "
                       "YAML file added earlier, remove that file and restart Home Assistant, then apply again.")
            return False
        else:
            if entity in states:  # left behind by a removed Ring Studio YAML file: free its entity ID
                ha.remove_registry_entry(entity)
                say(True, f"Removed the old {entity} left by an earlier YAML file")
            ha.add_template_sensor(name, template)
            say(True, f"Added the helper {name}")
        _forget_old_names(ha, clock, helpers, states, say, updated)
    except RuntimeError as err:
        say(False, str(err))
        return False
    return check(ha, clock, say, wait)


def _forget_old_names(ha, clock, helpers, states, say, updated):
    """Removes the helpers a renamed clock had under earlier names. Only helpers Ring Studio made: the entity's
    registry entry must belong to a template helper whose title ends in Ring Colors."""
    titles = {entry: title for title, entry in helpers.items()}
    for old in clock.previous_names:
        entity = f"sensor.{old}_ring_colors"
        if old == clock.name or entity not in states:
            continue
        entry = (ha.registry_entry(entity) or {}).get("config_entry_id")
        if not (entry in titles and titles[entry].endswith(" Ring Colors")):
            continue
        if not updated:
            say(True, f"Kept {entity} for now: the clock reads it until you update it with its new name")
            continue
        ha.remove_helper(entry)
        say(True, f"Removed {entity}, the helper from before the rename")


def check(ha, clock: Clock, say, wait):
    """Waits until the sensor shows the colours Home Assistant renders for the design."""
    n, last = clock.hw.leds, ""
    deadline = time.monotonic() + wait
    while True:
        try:
            value = str((ha.state(clock.colors_entity) or {}).get("state", ""))
            if len(value) == n * 6 and set(value) <= HEX and value == ha.render(generate.jinja(clock)):
                say(True, f"{clock.colors_entity} shows the design, {n} LED colours")
                return True
            last = value
        except RuntimeError as err:
            last = str(err)
        if time.monotonic() > deadline:
            shown = (last[:40] + "...") if len(last) > 40 else last or "no state"
            say(False, f"{clock.colors_entity} does not show the design yet ({shown}). Open it in Home Assistant "
                       "to see why.")
            return False
        time.sleep(1)


def old_automation(ha):
    """True when the brightness automation from earlier versions is still in the automation editor."""
    return ha.automation(OLD_AUTOMATION) is not None


def remove_old_automation(ha):
    ha.delete_automation(OLD_AUTOMATION)


def _left_over(ha, state, unique_id, platform):
    """True when the entity is only a leftover of a Ring Studio YAML file that is no longer installed: nothing
    provides it (Home Assistant restored it), and its registry entry is the one that file made."""
    if not (state.get("attributes") or {}).get("restored"):
        return False
    entry = ha.registry_entry(state["entity_id"]) or {}
    return (entry.get("platform") == platform and entry.get("unique_id") == unique_id
            and not entry.get("config_entry_id"))
