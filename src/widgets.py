from kivy.properties import ListProperty
from kivy.uix.button import Button
from kivy.uix.dropdown import DropDown
from kivy.uix.textinput import TextInput

from kivy.logger import Logger

class SearchableDropDown(TextInput):
    """
    A TextInput that shows a filtered DropDown as the user types.

    Constructor args:
        on_plant_selected: callable that receives the selected (name, category) tuple.
        options:           list of (name, category) tuples to search through.
    """

    options = ListProperty([])

    def __init__(self, _plant_selected, **kwargs):
        super().__init__(**kwargs)
        self.multiline = False
        self.background_color = (1, 1, 1, 1)
        self.cursor_color = (0.2, 0.6, 0.2, 1)
        self.padding = [10, 10]

        self._plant_selected = _plant_selected
        self.dropdown = DropDown()
        self.dropdown.max_height = 400

        self.bind(text=self._select_text, focus=self._focus)

        Logger.info("SearchableDropDown: __init__ complete")

    # ------------------------------------------------------------------
    # Internal handlers
    # ------------------------------------------------------------------

    def _select_text(self, _instance, value):
        Logger.info(f"SearchableDropDown: _select_text fired, value={repr(value)}")
        self.dropdown.clear_widgets()

        if value:
            v = value.lower()
            starts   = [o for o in self.options if str(o[0]).lower().startswith(v)]
            contains = [o for o in self.options if v in str(o[0]).lower() and not str(o[0]).lower().startswith(v)]
            filtered = starts + contains
        else:
            filtered = self.options

        for opt in filtered:
            btn = Button(
                text=str(opt[0]),
                size_hint_y=None,
                height='45dp',
                font_size='15sp',
                background_color=(0.6, 0.9, 0.6, 1),
            )
            btn.bind(on_release=lambda _, o=opt: self._select_option(o))
            self.dropdown.add_widget(btn)

        if filtered and self.focus:
            if self.dropdown.attach_to is None:
                self.dropdown.open(self)
        else:
            self.dropdown.dismiss()

    def _select_option(self, item):
        self.text = ''
        self.dropdown.dismiss()
        self._plant_selected(item)

    def _focus(self, _inst, is_focused):
        Logger.info(f"SearchableDropDown: focus changed → {is_focused}")
        if is_focused:
            self._select_text(self, self.text)
        else:
            self.dropdown.dismiss()