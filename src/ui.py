from cProfile import label
import threading
from datetime import date, timedelta

from kivy.clock import Clock
from kivy.core.window import Window
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput

import db
from config import resolve_sqlite_path
from widgets import SearchableDropDown


# ---------------------------------------------------------------------------
# Small helpers used only inside this module
# ---------------------------------------------------------------------------

class _TapBox(ButtonBehavior, BoxLayout):
    """A BoxLayout that fires on_release like a Button."""
    pass


def _make_icon_btn(icon_path, label_text, color, bold, callback, halign='left'):
    """Icon + text side by side, tappable."""
    tap = _TapBox(orientation='horizontal', spacing='6dp', padding=['8dp', '4dp'])
    icon_img = Image(source=icon_path, size_hint=(None, 1), width='28dp',
                     allow_stretch=True, keep_ratio=True)
    txt_lbl = Label(text=label_text, font_size='13sp', bold=bold, color=color,
                    halign=halign, valign='middle', size_hint_x=None)
    txt_lbl.bind(texture_size=lambda inst, val: setattr(inst, 'width', val[0]))
    tap.add_widget(icon_img)
    tap.add_widget(txt_lbl)
    tap.bind(on_release=callback)
    return tap


def _make_text_btn(label_text, color, bold, callback):
    """Text-only tappable button that fills its slot."""
    tap = _TapBox(orientation='horizontal', padding=['8dp', '4dp'])
    txt_lbl = Label(text=label_text, font_size='13sp', bold=bold, color=color,
                    halign='center', valign='middle')
    txt_lbl.bind(size=txt_lbl.setter('text_size'))
    tap.add_widget(txt_lbl)
    tap.bind(on_release=callback)
    return tap


# ---------------------------------------------------------------------------
# Main layout
# ---------------------------------------------------------------------------

class PlantTrackerLayout(BoxLayout):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'vertical'
        self.spacing = 10
        self.padding = 10
        self.tracking_date = date.today()

        self.sqlite_path = resolve_sqlite_path()
        db.init_local_sqlite(self.sqlite_path)

        plant_list = db.get_all_plants(self.sqlite_path)
        threading.Thread(
            target=db.backup_to_sqlite, args=(self.sqlite_path,), daemon=True
        ).start()

        self._build_ui(plant_list)

    # -----------------------------------------------------------------------
    # UI construction
    # -----------------------------------------------------------------------

    def _build_ui(self, plant_list):
        self._build_date_indicator()
        self._build_heading()
        self._build_search_bar(plant_list)
        self._build_list_area()
        self._build_heatmap()
        self._build_bottom_bar()

        Window.bind(on_resize=self._adjust_layout)
        Clock.schedule_once(
            lambda dt: self._adjust_layout(None, Window.width, Window.height), 0
        )
        self.update_ui()

    def _build_date_indicator(self):
        anchor = AnchorLayout(anchor_x='left', anchor_y='top', size_hint_y=None, height='30dp')
        self.date_indicator = Label(
            text=f"Tracking: {self.tracking_date.strftime('%b %d, %Y')}",
            font_size='12sp', bold=True,
            size_hint=(None, 1), width='180dp',
            halign='right', valign='middle',
        )
        self._update_date_color()
        anchor.add_widget(self.date_indicator)
        self.add_widget(anchor)

    def _build_heading(self):
        heading = BoxLayout(
            orientation='horizontal', size_hint=(None, None),
            height='60dp', spacing='15dp', pos_hint={'center_x': 0.5},
        )
        heading.bind(minimum_width=heading.setter('width'))

        self.plant_icon_left  = Image(source='icons/black_white_plant.png', size_hint=(None, 1), width='35dp')
        self.score_label      = Label(text='Plant Points: ...', font_size='30sp', bold=True,
                                      color=(0.15, 0.45, 0.15, 1), size_hint=(None, 1))
        self.score_label.bind(texture_size=lambda inst, s: setattr(inst, 'width', s[0]))
        self.plant_icon_right = Image(source='icons/black_white_plant.png', size_hint=(None, 1), width='35dp')

        heading.add_widget(self.plant_icon_left)
        heading.add_widget(self.score_label)
        heading.add_widget(self.plant_icon_right)
        self.add_widget(heading)

    def _build_search_bar(self, plant_list):
        self.search_input = SearchableDropDown(
            options=plant_list,
            _plant_selected=self._on_plant_selected,
            size_hint_y=None, height='45dp',
            hint_text='Search for a plant...', font_size='16sp',
        )
        self.add_widget(self.search_input)

    def _build_list_area(self):
        self.list_title = Label(
            text='Weekly Overview:', font_size='18sp', bold=True,
            color=(0.3, 0.4, 0.3, 1), size_hint_y=None, height='35dp',
            halign='left', padding=['10dp', 0],
        )
        self.list_title.bind(size=self.list_title.setter('text_size'))
        self.add_widget(self.list_title)

        self.scroll_view   = ScrollView(size_hint_y=0.45)
        self.list_container = BoxLayout(
            orientation='horizontal', size_hint_y=None,
            spacing='20dp', padding=['15dp', 0],
        )
        self.list_container.bind(minimum_height=self.list_container.setter('height'))

        label_defaults = dict(font_size='14sp', color=(0.1, 0.1, 0.1, 1),
                              halign='left', valign='top', size_hint_y=None, markup=True)

        self.daily_label  = Label(**label_defaults)
        self.totals_label = Label(**label_defaults)

        for lbl in (self.daily_label, self.totals_label):
            lbl.bind(
                width=lambda *a, l=lbl: l.setter('text_size')(l, (l.width, None)),
                texture_size=lambda *a, l=lbl: l.setter('height')(l, l.texture_size[1]),
            )

        self.daily_anchor  = AnchorLayout(anchor_x='left', anchor_y='top', size_hint_y=None, height=1)
        self.totals_anchor = AnchorLayout(anchor_x='left', anchor_y='top', size_hint_y=None, height=1)
        self.daily_anchor.add_widget(self.daily_label)
        self.totals_anchor.add_widget(self.totals_label)

        self.daily_label.bind(height=lambda *_: self._sync_anchor_heights())
        self.totals_label.bind(height=lambda *_: self._sync_anchor_heights())

        self.list_container.add_widget(self.daily_anchor)
        self.list_container.add_widget(self.totals_anchor)
        self.scroll_view.add_widget(self.list_container)
        self.add_widget(self.scroll_view)

    def _build_heatmap(self):
        self.add_widget(Label(
            text='Activity Heatmap:', font_size='16sp', bold=True,
            color=(0.3, 0.4, 0.3, 1), size_hint_y=None, height='30dp',
            halign='left', padding=['10dp', 0],
        ))

        h_row = BoxLayout(orientation='horizontal', size_hint_y=0.2,
                          spacing='8dp', padding=['0dp', 0, '8dp', 0])

        self.h_scroll = ScrollView(do_scroll_y=False, do_scroll_x=True, size_hint_x=None)
        self.h_cont   = BoxLayout(orientation='horizontal', spacing='2dp', size_hint=(None, 1))
        self.h_cont.bind(minimum_width=self.h_cont.setter('width'))
        self.h_cont.bind(width=lambda inst, val: setattr(
            self.h_scroll, 'width', min(val, Window.width * 0.62)
        ))
        self.h_scroll.add_widget(self.h_cont)
        h_row.add_widget(self.h_scroll)

        self.h_info_label = Label(
            text='Tap a square\nto see details', markup=True,
            font_size='13sp', color=(0.35, 0.45, 0.35, 1),
            halign='left', valign='middle', size_hint_x=None, width='130dp',
        )
        self.h_info_label.bind(size=self.h_info_label.setter('text_size'))
        h_row.add_widget(self.h_info_label)
        self.add_widget(h_row)

    def _build_bottom_bar(self):
        b_bar = BoxLayout(orientation='horizontal', size_hint_y=None, height='55dp', padding='5dp')

        left_anchor   = AnchorLayout(anchor_x='left',   anchor_y='center')
        centre_anchor = AnchorLayout(anchor_x='center', anchor_y='center')
        right_anchor  = AnchorLayout(anchor_x='right',  anchor_y='center')

        left_anchor.add_widget(
            _make_icon_btn('icons/calendar.png', 'Date', (0.4, 0.4, 0.4, 1), False, self.open_date_picker)
        )
        centre_anchor.add_widget(
            _make_text_btn('Manage Database', (0, 0, 0, 1), False, self.open_manage_db_menu)
        )

        right_btn = _make_icon_btn(
            'icons/trash.png', 'Delete', (0.4, 0.4, 0.4, 1), False,
            self.open_delete_menu, halign='right',
        )
        right_btn.size_hint_x = None
        right_btn.bind(minimum_width=right_btn.setter('width'))
        right_anchor.add_widget(right_btn)

        b_bar.add_widget(left_anchor)
        b_bar.add_widget(centre_anchor)
        b_bar.add_widget(right_anchor)
        self.add_widget(b_bar)

    # -----------------------------------------------------------------------
    # Layout helpers
    # -----------------------------------------------------------------------

    def _update_date_color(self):
        if self.tracking_date < date.today():
            self.date_indicator.color = (0.8, 0.2, 0.2, 1)
        else:
            self.date_indicator.color = (0.15, 0.45, 0.15, 1)

    def _sync_anchor_heights(self):
        h = max(self.daily_label.height, self.totals_label.height)
        self.daily_anchor.height  = h
        self.totals_anchor.height = h

    def _adjust_layout(self, _instance, width, height):
        if width < height:
            self.daily_anchor.size_hint_x  = 0.55
            self.totals_anchor.size_hint_x = 0.45
        else:
            self.daily_anchor.size_hint_x  = 0.6
            self.totals_anchor.size_hint_x = 0.4

    # -----------------------------------------------------------------------
    # Date navigation
    # -----------------------------------------------------------------------

    def change_date(self, shift):
        if shift == 0:
            self.tracking_date = date.today()
        else:
            self.tracking_date += timedelta(days=shift)

        self.date_indicator.text = f"Tracking: {self.tracking_date.strftime('%b %d, %Y')}"
        self._update_date_color()

        if hasattr(self, 'p_date_label'):
            self.p_date_label.text = self.tracking_date.strftime('%A, %b %d, %Y')

        self.update_ui()

    # -----------------------------------------------------------------------
    # Data refresh
    # -----------------------------------------------------------------------

    def update_ui(self):
        threading.Thread(target=self._fetch_data_thread, daemon=True).start()

    def _fetch_data_thread(self):
        start_date = (
            date.today() - timedelta(days=date.today().weekday())
        ) - timedelta(weeks=11)

        weekly, daily, heatmap_total, heatmap_distinct = db.fetch_ui_data(
            self.sqlite_path, self.tracking_date, start_date
        )
        Clock.schedule_once(
            lambda dt: self._apply_ui_updates(
                weekly, daily, heatmap_total, heatmap_distinct, start_date, self.tracking_date
            ),
            0,
        )

    def _apply_ui_updates(self, weekly_data, daily_data, heatmap_data, heatmap_distinct,
                           start_date, anchor_date):
        self.h_distinct = heatmap_distinct
        self.h_total    = heatmap_data

        # Score + icons
        count = len(weekly_data)
        self.score_label.text = f"Plant Points: {count}"
        icon = 'icons/plant.png' if count >= 30 else 'icons/black_white_plant.png'
        self.plant_icon_left.source  = icon
        self.plant_icon_right.source = icon

        # Weekly totals (right column)
        total_servings = sum(c for _, c in weekly_data)
        totals_lines = [f"[b]Weekly Totals ({total_servings})[/b]"]
        totals_lines += [f"• {n} ({c}x)" for n, c in weekly_data]
        self.totals_label.text = "\n".join(totals_lines)

        # Daily breakdown (left column)
        days_since_monday = anchor_date.weekday()
        days = [
            (anchor_date - timedelta(days=i)).strftime('%A')
            for i in range(days_since_monday + 1)
        ]
        day_plants = {d: [] for d in days}
        day_totals = {d: 0   for d in days}

        for log_date, plant_name, count in daily_data:
            day_name = (
                log_date.strftime('%A')
                if hasattr(log_date, 'strftime')
                else date.fromisoformat(log_date).strftime('%A')
            )
            if day_name in day_plants:
                day_plants[day_name].append(f"  • {plant_name} ({count}x)")
                day_totals[day_name] += count

        daily_lines = []
        for d in days:
            daily_lines.append(f"[b]{d} ({day_totals[d]})[/b]")
            daily_lines.extend(day_plants[d])
            daily_lines.append('')

        self.daily_label.text = "\n".join(daily_lines)

        # Heatmap grid — only rebuild if start date changed
        if not hasattr(self, 'h_btns') or self.h_start != start_date:
            self.h_cont.clear_widgets()
            self.h_btns  = {}
            self.h_start = start_date
            for w in range(12):
                col = BoxLayout(orientation='vertical', spacing='2dp', size_hint=(None, 1), width='15dp')
                for d in range(7):
                    ds  = (start_date + timedelta(weeks=w, days=d)).isoformat()
                    box = Button(background_normal='', border=(0, 0, 0, 0))
                    box.bind(on_release=lambda btn, ds=ds: self._on_heatmap_tap(ds))
                    col.add_widget(box)
                    self.h_btns[ds] = box
                self.h_cont.add_widget(col)

        today = date.today()
        for ds, box in self.h_btns.items():
            cell_date = date.fromisoformat(ds)
            c = heatmap_data.get(ds, 0)
            if cell_date > today:
                box.background_color = (1, 1, 1, 0)
            elif c == 0:
                box.background_color = (0.85, 0.9, 0.85, 1)
            elif c >= 12:
                box.background_color = (0.0, 0.81, 0.82, 1)
            else:
                f = c / 11.0
                box.background_color = (
                    0.7 + (0.1 - 0.7) * f,
                    0.9 + (0.5 - 0.9) * f,
                    0.7 + (0.1 - 0.7) * f,
                    1,
                )

    def _on_heatmap_tap(self, ds):
        tapped_date = date.fromisoformat(ds)
        if tapped_date > date.today():
            return

        total    = getattr(self, 'h_total',    {}).get(ds, 0)
        distinct = getattr(self, 'h_distinct', {}).get(ds, 0)

        self.tracking_date = tapped_date
        self.date_indicator.text = f"Tracking: {self.tracking_date.strftime('%b %d, %Y')}"
        self._update_date_color()
        if hasattr(self, 'p_date_label'):
            self.p_date_label.text = self.tracking_date.strftime('%A, %b %d, %Y')
        self.update_ui()

        friendly = tapped_date.strftime('%b %d').replace(' 0', ' ')
        if total == 0:
            self.h_info_label.text = f"[b]{friendly}[/b]\n\nNo plants\nlogged"
        else:
            self.h_info_label.text = (
                f"[b]{friendly}[/b]\n\n"
                f"Total: [b]{total}[/b]\n"
                f"Unique: [b]{distinct}[/b]"
            )

    # -----------------------------------------------------------------------
    # Plant logging
    # -----------------------------------------------------------------------

    def _on_plant_selected(self, plant_tuple):
        threading.Thread(
            target=self._save_thread,
            args=(plant_tuple[0], self.tracking_date.isoformat()),
            daemon=True,
        ).start()

    def _save_thread(self, name, date_str):
        db.save_plant_log(self.sqlite_path, name, date_str)
        self.update_ui()

    # -----------------------------------------------------------------------
    # Popups — Date picker
    # -----------------------------------------------------------------------

    def open_date_picker(self, _inst):
        content = BoxLayout(orientation='vertical', spacing=10, padding=10)

        self.p_date_label = Label(
            text=self.tracking_date.strftime('%A, %b %d, %Y'),
            font_size=24, bold=True,
        )
        content.add_widget(self.p_date_label)

        nav_row = BoxLayout(orientation='horizontal', spacing=10, size_hint_y=None, height='60dp')
        for label, shift in [('< Prev', -1), ('Today', 0), ('Next >', 1)]:
            btn = Button(text=label, font_size='16sp')
            btn.bind(on_release=lambda _, s=shift: self.change_date(s))
            nav_row.add_widget(btn)
        content.add_widget(nav_row)

        done = Button(text='Done', size_hint_y=None, height='60dp', font_size='18sp')
        content.add_widget(done)

        self.date_popup = Popup(title='Select Date', content=content, size_hint=(0.85, 0.4))
        done.bind(on_release=self.date_popup.dismiss)
        self.date_popup.open()

    # -----------------------------------------------------------------------
    # Popups — Manage database
    # -----------------------------------------------------------------------

    def open_manage_db_menu(self, _inst):
        content = BoxLayout(orientation='vertical', spacing=20, padding=20)
        add_btn = Button(text='Add Plant',    background_color=(0.15, 0.45, 0.15, 1), height='65dp', font_size='18sp')
        rem_btn = Button(text='Remove Plant', background_color=(0.6,  0.2,  0.2,  1), height='65dp', font_size='18sp')
        content.add_widget(add_btn)
        content.add_widget(rem_btn)

        self.m_pop = Popup(title='Database', content=content, size_hint=(0.8, None), height='280dp')
        add_btn.bind(on_release=lambda _: (self.m_pop.dismiss(), self._open_add_menu()))
        rem_btn.bind(on_release=lambda _: (self.m_pop.dismiss(), self._open_rem_menu()))
        self.m_pop.open()

    def _open_add_menu(self):
        content = BoxLayout(orientation='vertical', spacing=10, padding=15)
        self.new_name     = TextInput(hint_text='Name', size_hint_y=None, height='45dp')
        self.new_category = Spinner(
            text='Category...',
            values=('Vegetable', 'Fruit', 'Legume', 'Nut/Seed', 'Whole Grain', 'Herb/Spice'),
            size_hint_y=None, height='45dp',
        )
        
        self.preview_label = Label(
            text="Adding ... as ... in database",
            font_size='14sp', color=(0.7, 0.7, 0.7, 1), markup=True,
            size_hint_y=None, height='30dp', halign='center', valign='middle'
        )
        self.preview_label.bind(size=self.preview_label.setter('text_size'))

        self.new_name.bind(text=self._update_add_preview)
        self.new_category.bind(text=self._update_add_preview)

        save_btn = Button(text='Save', size_hint_y=None, height='60dp', font_size='18sp')
        save_btn.bind(on_release=self._save_new_plant)
        
        content.add_widget(self.new_name)
        content.add_widget(self.new_category)
        content.add_widget(self.preview_label)  
        content.add_widget(save_btn)

        self.a_pop = Popup(title='Add Species', content=content, size_hint=(0.8, None), height='320dp')
        self.a_pop.open()

    def _update_add_preview(self, *args):
        name = self.new_name.text.strip().title()
        if not name:
            name = "..."
            
        cat = self.new_category.text
        if cat == 'Category...':
            cat = "..."
            
        self.preview_label.text = f"Adding [b]{name}[/b] as [b]{cat}[/b] in database"

    def _save_new_plant(self, _inst):
        name = self.new_name.text.strip().title()
        cat  = self.new_category.text
        if name and cat != 'Category...':
            db.add_plant(name, cat)
            self.search_input.options = db.get_all_plants(self.sqlite_path)
            self.a_pop.dismiss()

    def open_delete_menu(self, _inst):
        ds    = self.tracking_date.isoformat()
        items = db.get_log_entries_for_date(self.sqlite_path, ds)
        if not items:
            return

        content = BoxLayout(orientation='vertical', spacing=5)
        scroll  = ScrollView()
        lv      = BoxLayout(orientation='vertical', size_hint_y=None, spacing='5dp') # added spacing so buttons don't touch
        lv.bind(minimum_height=lv.setter('height'))

        for lid, plant_name in items:
            btn = Button(
                text=plant_name, size_hint_y=None, height='60dp', font_size='18sp',
                background_color=(0.9, 0.4, 0.4, 1),
            )
            btn.bind(on_release=lambda _, i=lid: self._del_log(i))
            lv.add_widget(btn)

        scroll.add_widget(lv)
        content.add_widget(scroll)

        self.dl_pop = Popup(title='Delete Entry', content=content, size_hint=(0.8, 0.6))
        self.dl_pop.open()

    def _on_remove_selected(self, plant):
        self.sel_remove = plant[0]
        self.r_btn.disabled = False

    def _do_remove(self, _inst):
        db.remove_plant(self.sel_remove)
        self.update_ui()
        self.r_pop.dismiss()

    # -----------------------------------------------------------------------
    # Popups — Delete log entries
    # -----------------------------------------------------------------------

    def open_delete_menu(self, _inst):
        ds    = self.tracking_date.isoformat()
        items = db.get_log_entries_for_date(self.sqlite_path, ds)
        if not items:
            return

        content = BoxLayout(orientation='vertical', spacing=5)
        scroll  = ScrollView()
        lv      = BoxLayout(orientation='vertical', size_hint_y=None)
        lv.bind(minimum_height=lv.setter('height'))

        for lid, plant_name in items:
            btn = Button(
                text=plant_name, size_hint_y=None, height=45,
                background_color=(0.9, 0.4, 0.4, 1),
            )
            btn.bind(on_release=lambda _, i=lid: self._del_log(i))
            lv.add_widget(btn)

        scroll.add_widget(lv)
        content.add_widget(scroll)

        self.dl_pop = Popup(title='Delete Entry', content=content, size_hint=(0.8, 0.6))
        self.dl_pop.open()

    def _del_log(self, lid):
        db.delete_log_entry(lid)
        self.update_ui()
        self.dl_pop.dismiss()