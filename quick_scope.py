import re
import string

import sublime
import sublime_plugin

from .utils import JumperLabel, get_word_separators, setting

_input_panel_opened = {}


class JumperQuickScopeCommand(sublime_plugin.TextCommand):
    """Go to the word labelled by a character."""

    def run(self, edit, character, extend=False, included=True):
        self.regions = {
            selection.to_tuple(): _quick_scope_get_labels(self.view, selection)
            for selection in self.view.sel()
        }

        if character in " \t":
            _input_panel_opened[self.view.id()] = True
            self.view.window().show_input_panel(
                "Select to",
                character,
                self.on_cancel,
                self.on_change,
                self.on_cancel,
            )
            return

        character = character.lower()

        if character in "'`\"":
            character = "'"

        for selection in self.view.sel():
            if character in self.regions[selection.to_tuple()]:
                self.view.sel().subtract(selection)
                self.regions[selection.to_tuple()][character].jump_to(
                    self.view, selection, extend, included
                )

    def on_cancel(self):
        self.view.window().run_command("hide_panel", {"cancel": True})
        _input_panel_opened.pop(self.view.id(), None)
        _quick_scope_show_labels(self.view)

    def on_change(self, value):
        value = value.lower()
        extend = 0
        if value and value[0] == " ":
            extend = 1
            _quick_scope_show_labels(self.view, 1)
            value = value[1:]
        elif value and value[0] == "\t":
            extend = 2
            _quick_scope_show_labels(self.view, 2)
            value = value[1:]
        else:
            _quick_scope_show_labels(self.view, 0)

        for selection in self.view.sel():
            if value in self.regions[selection.to_tuple()]:
                self.view.sel().subtract(selection)
                self.regions[selection.to_tuple()][value].jump_to(
                    self.view, selection, bool(extend), extend == 2
                )
                self.on_cancel()


class SelectionShowQuickScopeWordListener(sublime_plugin.EventListener):
    """Add a line bellow the characters for which we can do a quick scope."""

    def on_activated_async(self, view):
        self.on_selection_modified_async(view)

    def on_deactivated(self, view):
        if not _input_panel_opened.get(view.id()):
            view.add_regions("jumper_quick_scope", [])

    def on_selection_modified_async(self, view):
        if _input_panel_opened.get(view.id()):
            view.window().run_command("hide_panel", {"cancel": True})
            del _input_panel_opened[self.view.id()]

        if setting("jumper_quick_scope", view):
            _quick_scope_show_labels(view)


def _quick_scope_show_labels(view, extend=0):
    scope = ({1: "region.yellowish", 2: "region.bluish"}).get(int(extend), "white")

    flags = 512 | 32 | 256 if extend != 2 else sublime.DRAW_SOLID_UNDERLINE | 32 | 256
    view.add_regions(
        "jumper_quick_scope",
        [
            r.label_region
            for selection in view.sel()
            for r in _quick_scope_get_labels(view, selection).values()
        ],
        scope=scope,
        flags=flags,
    )


def _quick_scope_get_labels(view, selection) -> "dict[str, JumperLabel]":
    if len(view.sel()) == 0:
        return {}

    if len(view.sel()) > 1:
        target = "line"
    else:
        target = setting("jumper_quick_scope", view)

    a, b = sorted(selection.to_tuple())
    line_region = view.line(selection)

    word_bounds = re.escape(get_word_separators(view))

    search_re = f"^[^{word_bounds}\\s\\n]+|(?<=[{word_bounds}\\s\\n])[^{word_bounds}\\s\\n]+|[{word_bounds}]"
    result = view.find_all(search_re, within=line_region)
    if target == "line":
        # Do not make the label depending on the cursor if in line mode
        # Start with small word to show more label statistically
        aa = (line_region.a + line_region.b) // 2
        result = sorted(result, key=lambda r: (abs(r.b - r.a), abs(r.a - aa)))
    else:
        result = sorted(result, key=lambda r: abs(r.a - a))

    regions = {}
    for r in result:
        # TODO: single quote and double quote should be the same
        s = view.substr(r).lower()

        for i, c in enumerate(s):
            if c in "'`\"":
                c = "'"
            if c.strip() and c not in regions:
                break
        else:
            # Can not find a label
            # TODO: better algorithm
            continue

        if min(selection) == min(r):
            # Do not highlight the current cursor position
            # And try to use the caracter for a missong region if possible
            regions[c] = JumperLabel(r, c, sublime.Region(r.a, r.a))
            continue
        regions[c] = JumperLabel(r, c, sublime.Region(r.a + i, r.a + 1 + i))

    if target == "line":
        return regions

    # Add label on rows
    lines = view.find_all(r"[^\s].*\n", within=view.visible_region())
    mid_region = (line_region.a + line_region.b) // 2
    lines = sorted(lines, key=lambda l: (abs(mid_region - l.a), mid_region > l.a))
    for r in lines:
        s = view.substr(r).lower()

        for i, c in enumerate(s):
            if c.strip() and c not in regions and c in string.ascii_letters:
                break
        else:
            for i, c in enumerate(s):
                if c in "'`\"":
                    c = "'"
                if c.strip() and c not in regions and c not in string.ascii_letters:
                    break
            else:
                continue

        regions[c] = JumperLabel(r, c, sublime.Region(r.a + i, r.a + 1 + i))

    return regions
