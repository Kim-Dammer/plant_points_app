import glob
import os
import pymysql
import sqlite3
import threading
from datetime import date, timedelta

from kivy.app import App
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.popup import Popup
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.image import Image
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.textinput import TextInput
from kivy.uix.spinner import Spinner
from kivy.uix.dropdown import DropDown
from kivy.uix.scrollview import ScrollView
from kivy.properties import ListProperty
from kivy.core.window import Window
from kivy.clock import Clock
from kivy.utils import platform

Window.clearcolor = (0.92, 0.97, 0.92, 1)

def load_dotenv_manual():
    possible_paths = [
        os.path.join(os.getcwd(), 'config.env'),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.env'),
    ]
    for env_path in possible_paths:
        if os.path.exists(env_path):
            with open(env_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, _, value = line.partition('=')
                        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
            return
load_dotenv_manual()

DB_HOST = os.getenv('DB_HOST')
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_NAME = os.getenv('DB_NAME')
DB_PORT = 3306

# Dynamic Pathing for Laptop vs Android
SQLITE_PATH = None  

def _resolve_sqlite_path():
    if platform == 'android':
        app = App.get_running_app()
        if app is not None:
            return os.path.join(app.user_data_dir, "local_PlantBackup.db")
        return os.path.join(os.getcwd(), "local_PlantBackup.db")
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "local_PlantBackup.db")


class SearchableDropDown(TextInput):
    options = ListProperty([])

    def __init__(self, on_plant_selected, **kwargs):
        super().__init__(**kwargs)
        self.multiline = False
        self.dropdown = DropDown()
        self.dropdown.max_height = 150
        self.bind(text=self.on_text, focus=self.on_focus)
        self.on_plant_selected = on_plant_selected
        self.background_color = (1, 1, 1, 1)
        self.cursor_color = (0.2, 0.6, 0.2, 1)
        self.padding = [10, 10]

    def on_text(self, _instance, value):
        self.dropdown.clear_widgets()
        filtered = [opt for opt in self.options if value.lower() in str(opt[0]).lower()] if value else self.options
        for opt in filtered:
            btn = Button(text=f"{opt[0]}", size_hint_y=None, height=50, background_color=(0.6, 0.9, 0.6, 1))
            btn.bind(on_release=lambda _, o=opt: self.select_option(o))
            self.dropdown.add_widget(btn)
        if filtered and self.focus:
            if self.dropdown.attach_to is None: self.dropdown.open(self)
        else: self.dropdown.dismiss()

    def select_option(self, item):
        self.text = ""; self.dropdown.dismiss(); self.on_plant_selected(item)
    
    def on_focus(self, _inst, is_focused):
        if is_focused: self.on_text(self, self.text)
        else: self.dropdown.dismiss()


class PlantTrackerLayout(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'vertical'
        self.spacing = 10
        self.padding = 10
        self.tracking_date = date.today()

        global SQLITE_PATH
        SQLITE_PATH = _resolve_sqlite_path()

        self.init_local_sqlite()
        plant_list = self.get_all_plants()
        threading.Thread(target=self.backup_to_sqlite, daemon=True).start()
        
        self.build_ui(plant_list)

    def get_db_connection(self):
        return pymysql.connect(host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=DB_NAME, port=DB_PORT, autocommit=True, connect_timeout=5)
    
    def init_local_sqlite(self):
        conn = sqlite3.connect(SQLITE_PATH)
        conn.execute('CREATE TABLE IF NOT EXISTS plants (name TEXT PRIMARY KEY, category TEXT)')
        conn.execute('CREATE TABLE IF NOT EXISTS eaten_log (id INTEGER PRIMARY KEY, log_date TEXT, plant_name TEXT)')
        conn.close()

    def backup_to_sqlite(self):
        try:
            with self.get_db_connection() as remote:
                with remote.cursor() as cur:
                    cur.execute("SELECT name, category FROM plants"); plants = cur.fetchall()
                    cur.execute("SELECT id, log_date, plant_name FROM eaten_log"); logs = cur.fetchall()
            conn = sqlite3.connect(SQLITE_PATH)
            conn.execute("DELETE FROM plants"); conn.execute("DELETE FROM eaten_log")
            conn.executemany("INSERT INTO plants VALUES (?,?)", plants)
            conn.executemany("INSERT INTO eaten_log VALUES (?,?,?)", [(l[0], l[1].isoformat() if hasattr(l[1], 'isoformat') else l[1], l[2]) for l in logs])
            conn.commit(); conn.close()
            print("Sync complete.")
        except: pass

    def get_all_plants(self):
        try:
            with self.get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT name, category FROM plants ORDER BY name"); return cur.fetchall()
        except:
            conn = sqlite3.connect(SQLITE_PATH); data = conn.execute("SELECT name, category FROM plants ORDER BY name").fetchall(); conn.close(); return data

    def build_ui(self, plant_list):
        # 1. Date Indicator (Top Right Corner)
        date_anchor = AnchorLayout(anchor_x='left', anchor_y='top', size_hint_y=None, height='30dp')
        self.date_indicator = Label(
            text=f"Tracking: {self.tracking_date.strftime('%b %d, %Y')}",
            font_size='12sp', bold=True,
            size_hint=(None, 1), width='180dp',
            halign="right", valign="middle"
        )
        self.update_date_color()
        date_anchor.add_widget(self.date_indicator)
        self.add_widget(date_anchor)

        # 2. Heading
        heading = BoxLayout(orientation='horizontal', size_hint=(None, None), height='60dp', spacing='15dp', pos_hint={'center_x': 0.5})
        heading.bind(minimum_width=heading.setter('width'))
        self.plant_icon_left = Image(source='icons/black_white_plant.png', size_hint=(None, 1), width='35dp')
        self.score_label = Label(text="Plant Points: ...", font_size='30sp', bold=True, color=(0.15, 0.45, 0.15, 1), size_hint=(None, 1))
        self.score_label.bind(texture_size=lambda inst, s: setattr(inst, 'width', s[0]))
        self.plant_icon_right = Image(source='icons/black_white_plant.png', size_hint=(None, 1), width='35dp')
        heading.add_widget(self.plant_icon_left); heading.add_widget(self.score_label); heading.add_widget(self.plant_icon_right)
        self.add_widget(heading)

        # 3. Search Bar
        self.search_input = SearchableDropDown(options=plant_list, on_plant_selected=self.save_plant, size_hint_y=None, height='44dp', hint_text="Search for a plant...")
        self.add_widget(self.search_input)

        # 4. List Area
        self.list_title = Label(text="Weekly Overview:", font_size='18sp', bold=True, color=(0.3, 0.4, 0.3, 1), 
                               size_hint_y=None, height='35dp', halign="left", padding=['10dp', 0])
        self.list_title.bind(size=self.list_title.setter('text_size'))
        self.add_widget(self.list_title)

        self.scroll_view = ScrollView(size_hint_y=0.45) 
        # list_container holds the Daily (Left) and Weekly (Right) columns
        self.list_container = BoxLayout(orientation='horizontal', size_hint_y=None, spacing='20dp', padding=['15dp', 0])
        self.list_container.bind(minimum_height=self.list_container.setter('height'))
        
        # Daily Label
        self.daily_label = Label(text="", font_size='14sp', color=(0.1, 0.1, 0.1, 1), 
                                halign="left", valign="top", size_hint_y=None, markup=True)
        self.daily_label.bind(width=lambda *args: self.daily_label.setter('text_size')(self.daily_label, (self.daily_label.width, None)), 
                             texture_size=lambda *args: self.daily_label.setter('height')(self.daily_label, self.daily_label.texture_size[1]))
        
        # Totals Label
        self.totals_label = Label(text="", font_size='14sp', color=(0.1, 0.1, 0.1, 1), 
                                 halign="left", valign="top", size_hint_y=None, markup=True)
        self.totals_label.bind(width=lambda *args: self.totals_label.setter('text_size')(self.totals_label, (self.totals_label.width, None)), 
                              texture_size=lambda *args: self.totals_label.setter('height')(self.totals_label, self.totals_label.texture_size[1]))

        self.daily_anchor = AnchorLayout(anchor_x='left', anchor_y='top', size_hint_y=None, height=1)
        self.daily_anchor.add_widget(self.daily_label)
        self.daily_label.bind(height=lambda inst, val: self._sync_anchor_heights())

        self.totals_anchor = AnchorLayout(anchor_x='left', anchor_y='top', size_hint_y=None, height=1)
        self.totals_anchor.add_widget(self.totals_label)
        self.totals_label.bind(height=lambda inst, val: self._sync_anchor_heights())

        self.list_container.add_widget(self.daily_anchor)
        self.list_container.add_widget(self.totals_anchor)
        self.scroll_view.add_widget(self.list_container)
        self.add_widget(self.scroll_view)  

        # 5. Heatmap
        self.add_widget(Label(text="Activity Heatmap:", font_size='16sp', bold=True, color=(0.3, 0.4, 0.3, 1), size_hint_y=None, height='30dp', halign="left", padding=['10dp', 0]))
        h_anchor = AnchorLayout(anchor_x='left', size_hint_y=0.2)
        self.h_scroll = ScrollView(do_scroll_y=False, do_scroll_x=True, size_hint_x=None)
        self.h_cont = BoxLayout(orientation='horizontal', spacing='2dp', size_hint=(None, 1))
        self.h_cont.bind(minimum_width=self.h_cont.setter('width'))
        self.h_cont.bind(width=lambda inst, val: setattr(self.h_scroll, 'width', min(val, Window.width - 20)))
        self.h_scroll.add_widget(self.h_cont); h_anchor.add_widget(self.h_scroll); self.add_widget(h_anchor)

        # 6. Bottom Bar — Date (left), Database (centre, text only), Delete Entries (right)
        from kivy.uix.behaviors import ButtonBehavior
        class TapBox(ButtonBehavior, BoxLayout): pass

        def make_icon_btn(icon_path, label_text, color, bold, callback, halign='left'):
            """Icon + text, horizontally arranged, anchored per halign."""
            tap = TapBox(orientation='horizontal', spacing='6dp', padding=['8dp', '4dp'])
            icon_img = Image(source=icon_path, size_hint=(None, 1), width='28dp', allow_stretch=True, keep_ratio=True)
            txt_lbl  = Label(text=label_text, font_size='13sp', bold=bold, color=color,
                             halign=halign, valign='middle', size_hint_x=None)
            txt_lbl.bind(texture_size=lambda inst, val: setattr(inst, 'width', val[0]))
            tap.add_widget(icon_img)
            tap.add_widget(txt_lbl)
            tap.bind(on_release=callback)
            return tap

        def make_text_btn(label_text, color, bold, callback):
            """Text-only button, fills its slot and centres text."""
            tap = TapBox(orientation='horizontal', padding=['8dp', '4dp'])
            txt_lbl = Label(text=label_text, font_size='13sp', bold=bold, color=color,
                            halign='center', valign='middle')
            txt_lbl.bind(size=txt_lbl.setter('text_size'))
            tap.add_widget(txt_lbl)
            tap.bind(on_release=callback)
            return tap

 # 6. Bottom Bar — Date (left), Database (centre, text only), Delete Entries (right)
        b_bar = BoxLayout(orientation='horizontal', size_hint_y=None, height='55dp', padding='5dp')

        # Left: Date icon + label, anchored left
        left_anchor = AnchorLayout(anchor_x='left', anchor_y='center')
        left_anchor.add_widget(make_icon_btn('icons/calendar.png', 'Date', (0.4,0.4,0.4,1), False, self.open_date_picker))

        # Centre: Database text only
        centre_anchor = AnchorLayout(anchor_x='center', anchor_y='center')
        centre_anchor.add_widget(make_text_btn('Manage Database', (0,0,0,1), False, self.open_manage_db_menu))

        # Right: Delete Entries icon + label, anchored right
        right_anchor = AnchorLayout(anchor_x='right', anchor_y='center')
        right_btn = make_icon_btn('icons/trash.png', 'Delete', (0.4,0.4,0.4,1), False, self.open_delete_menu, halign='right')
        
        right_btn.size_hint_x = None
        right_btn.bind(minimum_width=right_btn.setter('width'))
        
        right_anchor.add_widget(right_btn)

        b_bar.add_widget(left_anchor)
        b_bar.add_widget(centre_anchor)
        b_bar.add_widget(right_anchor)
        self.add_widget(b_bar)
        
        Window.bind(on_resize=self.adjust_layout)
        Clock.schedule_once(lambda dt: self.adjust_layout(None, Window.width, Window.height), 0)
        self.update_ui()

    def update_date_color(self):
        # Red if past, Green if Today or Future
        if self.tracking_date < date.today():
            self.date_indicator.color = (0.8, 0.2, 0.2, 1) 
        else:
            self.date_indicator.color = (0.15, 0.45, 0.15, 1)

    def _sync_anchor_heights(self):
        h = max(self.daily_label.height, self.totals_label.height)
        self.daily_anchor.height = h
        self.totals_anchor.height = h

    def adjust_layout(self, instance, width, height):
        # Adjust ratios for mobile vs laptop
        if width < height:
            self.daily_anchor.size_hint_x = 0.55
            self.totals_anchor.size_hint_x = 0.45
        else:
            self.daily_anchor.size_hint_x = 0.6
            self.totals_anchor.size_hint_x = 0.4

    def change_date(self, shift):
        self.tracking_date = date.today() if shift == 0 else self.tracking_date + timedelta(days=shift)
        self.date_indicator.text = f"Tracking: {self.tracking_date.strftime('%b %d, %Y')}"
        self.update_date_color()
        if hasattr(self, 'p_date_label'): self.p_date_label.text = self.tracking_date.strftime('%A, %b %d, %Y')
        self.update_ui()

    def update_ui(self):
        threading.Thread(target=self._fetch_data_thread, daemon=True).start()

    def _fetch_data_thread(self):
        anchor = self.tracking_date; mon = anchor - timedelta(days=anchor.weekday()); sun = mon + timedelta(days=6)
        start = (date.today() - timedelta(days=date.today().weekday())) - timedelta(weeks=11)
        try:
            with self.get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT plant_name, COUNT(*) FROM eaten_log WHERE log_date BETWEEN %s AND %s GROUP BY plant_name", (mon, sun)); w = cur.fetchall()
                    cur.execute("SELECT log_date, plant_name, COUNT(*) FROM eaten_log WHERE log_date BETWEEN %s AND %s GROUP BY log_date, plant_name", (mon, sun)); d = cur.fetchall()
                    cur.execute("SELECT log_date, COUNT(*) FROM eaten_log WHERE log_date >= %s GROUP BY log_date", (start,)); h = {r[0].isoformat(): r[1] for r in cur.fetchall()}
            Clock.schedule_once(lambda dt: self._apply_ui_updates(w, d, h, start, anchor), 0)
        except:
            conn = sqlite3.connect(SQLITE_PATH); cur = conn.cursor()
            w = cur.execute("SELECT plant_name, COUNT(*) FROM eaten_log WHERE log_date BETWEEN ? AND ? GROUP BY plant_name", (mon.isoformat(), sun.isoformat())).fetchall()
            d = [(date.fromisoformat(r[0]), r[1], r[2]) for r in cur.execute("SELECT log_date, plant_name, COUNT(*) FROM eaten_log WHERE log_date BETWEEN ? AND ? GROUP BY log_date, plant_name", (mon.isoformat(), sun.isoformat())).fetchall()]
            h = {r[0]: r[1] for r in cur.execute("SELECT log_date, COUNT(*) FROM eaten_log WHERE log_date >= ? GROUP BY log_date", (start.isoformat(),)).fetchall()}; conn.close()
            Clock.schedule_once(lambda dt: self._apply_ui_updates(w, d, h, start, anchor), 0)

    def _apply_ui_updates(self, weekly_data, daily_data, heatmap_data, start_date, anchor_date):
        self.score_label.text = f"Plant Points: {len(weekly_data)}"
        icon = 'icons/plant.png' if len(weekly_data) >= 30 else 'icons/black_white_plant.png'
        self.plant_icon_left.source = icon; self.plant_icon_right.source = icon
        
        # Weekly Totals (Right side)
        t = [f"[b]Weekly Totals ({sum(c for _, c in weekly_data)})[/b]"]
        for n, c in weekly_data: t.append(f"• {n} ({c}x)")
        self.totals_label.text = "\n".join(t)

        # Daily List (Left side)
        days_since_monday = anchor_date.weekday()

        days = [(anchor_date - timedelta(days=i)).strftime('%A') for i in range(days_since_monday + 1)]

        db = {day: [] for day in days}; dt = {day: 0 for day in days}

        for ld, pn, c in daily_data:
            dn = ld.strftime('%A') if hasattr(ld, 'strftime') else date.fromisoformat(ld).strftime('%A')
            if dn in db: 
                db[dn].append(f"  • {pn} ({c}x)")
                dt[dn] += c

        dl = []
        for d in days:
            dl.append(f"[b]{d} ({dt[d]})[/b]")
            if db[d]:
                dl.extend(db[d])
            dl.append("") 

        self.daily_label.text = "\n".join(dl)

        # Heatmap update
        if not hasattr(self, 'h_btns') or self.h_start != start_date:
            self.h_cont.clear_widgets(); self.h_btns = {}; self.h_start = start_date
            for w in range(12):
                col = BoxLayout(orientation='vertical', spacing='2dp', size_hint=(None, 1), width='15dp')
                for d in range(7):
                    ds = (start_date + timedelta(weeks=w, days=d)).isoformat()
                    box = Button(background_normal='', border=(0, 0, 0, 0)); col.add_widget(box); self.h_btns[ds] = box
                self.h_cont.add_widget(col)
        for ds, box in self.h_btns.items():
            cd = date.fromisoformat(ds); c = heatmap_data.get(ds, 0)
            if cd > date.today(): box.background_color = (1, 1, 1, 0)
            elif c == 0: box.background_color = (0.85, 0.9, 0.85, 1)
            elif c >= 12: box.background_color = (0.0, 0.81, 0.82, 1)
            else: f = c / 11.0; box.background_color = (0.7 + (0.1-0.7)*f, 0.9 + (0.5-0.9)*f, 0.7 + (0.1-0.7)*f, 1)

    def save_plant(self, plant_tuple):
        threading.Thread(target=self._save_thread, args=(plant_tuple[0], self.tracking_date.isoformat()), daemon=True).start()

    def _save_thread(self, name, dt_str):
        try:
            with self.get_db_connection() as conn:
                with conn.cursor() as cur: cur.execute("INSERT INTO eaten_log (log_date, plant_name) VALUES (%s, %s)", (dt_str, name))
        except:
            conn = sqlite3.connect(SQLITE_PATH); conn.execute("INSERT INTO eaten_log (log_date, plant_name) VALUES (?, ?)", (dt_str, name)); conn.commit(); conn.close()
        self.update_ui()

    # Popups (Standard Logic)
    def open_date_picker(self, inst):
        c = BoxLayout(orientation='vertical', spacing=10, padding=10); self.p_date_label = Label(text=self.tracking_date.strftime('%A, %b %d, %Y'), font_size=24, bold=True); c.add_widget(self.p_date_label)
        b = BoxLayout(orientation='horizontal', spacing=10, size_hint_y=None, height=50); p = Button(text="< Prev"); p.bind(on_release=lambda x: self.change_date(-1)); t = Button(text="Today"); t.bind(on_release=lambda x: self.change_date(0)); n = Button(text="Next >"); n.bind(on_release=lambda x: self.change_date(1)); b.add_widget(p); b.add_widget(t); b.add_widget(n); c.add_widget(b); d = Button(text="Done", size_hint_y=None, height=44); c.add_widget(d)
        self.date_popup = Popup(title="Select Date", content=c, size_hint=(0.85, 0.4)); d.bind(on_release=self.date_popup.dismiss); self.date_popup.open()

    def open_manage_db_menu(self, inst):
        c = BoxLayout(orientation='vertical', spacing=20, padding=20); a = Button(text="Add Plant", background_color=(0.15,0.45,0.15,1), height=50); r = Button(text="Remove Plant", background_color=(0.6,0.2,0.2,1), height=50); c.add_widget(a); c.add_widget(r)
        self.m_pop = Popup(title="Database", content=c, size_hint=(0.8, None), height=200); a.bind(on_release=self._open_add); r.bind(on_release=self._open_rem); self.m_pop.open()

    def _open_add(self, i): self.m_pop.dismiss(); self.open_add_menu()
    def _open_rem(self, i): self.m_pop.dismiss(); self.open_rem_menu()

    def open_add_menu(self):
        c = BoxLayout(orientation='vertical', spacing=10, padding=15); self.new_n = TextInput(hint_text="Name", size_hint_y=None, height=40); self.new_c = Spinner(text="Category...", values=('Vegetable', 'Fruit', 'Legume', 'Nut/Seed', 'Whole Grain', 'Herb/Spice'), size_hint_y=None, height=44); b = Button(text="Save", size_hint_y=None, height=45); b.bind(on_release=self._save_new_sp); c.add_widget(self.new_n); c.add_widget(self.new_c); c.add_widget(b)
        self.a_pop = Popup(title="Add Species", content=c, size_hint=(0.8, None), height=250); self.a_pop.open()

    def _save_new_sp(self, i):
        n = self.new_n.text.strip().title(); cat = self.new_c.text
        if n and cat != "Category...":
            try:
                with self.get_db_connection() as conn: conn.cursor().execute("INSERT IGNORE INTO plants VALUES (%s, %s)", (n, cat))
            except: pass
            self.search_input.options = self.get_all_plants(); self.a_pop.dismiss()

    def open_rem_menu(self):
        c = BoxLayout(orientation='vertical', spacing=10, padding=15); self.r_in = SearchableDropDown(options=self.get_all_plants(), on_plant_selected=self._on_r_sel, size_hint_y=None, height=44); self.r_btn = Button(text="Delete", disabled=True, background_color=(0.8,0.2,0.2,1), size_hint_y=None, height=45); self.r_btn.bind(on_release=self._do_rem); c.add_widget(Label(text="Select plant:")); c.add_widget(self.r_in); c.add_widget(self.r_btn)
        self.r_pop = Popup(title="Remove Species", content=c, size_hint=(0.8, None), height=250); self.r_pop.open()

    def _on_r_sel(self, p): self.sel_r = p[0]; self.r_btn.disabled = False
    def _do_rem(self, i):
        try:
            with self.get_db_connection() as conn:
                with conn.cursor() as cur: cur.execute("DELETE FROM eaten_log WHERE plant_name=%s",(self.sel_r,)); cur.execute("DELETE FROM plants WHERE name=%s",(self.sel_r,))
        except: pass
        self.update_ui(); self.r_pop.dismiss()

    def open_delete_menu(self, inst):
        ds = self.tracking_date.isoformat()
        try:
            with self.get_db_connection() as conn:
                with conn.cursor() as cur: cur.execute("SELECT id, plant_name FROM eaten_log WHERE log_date=%s",(ds,)); items=cur.fetchall()
        except:
            conn=sqlite3.connect(SQLITE_PATH); items=conn.execute("SELECT id, plant_name FROM eaten_log WHERE log_date=?",(ds,)).fetchall(); conn.close()
        if not items: return
        c=BoxLayout(orientation='vertical', spacing=5); s=ScrollView(); lv=BoxLayout(orientation='vertical', size_hint_y=None); lv.bind(minimum_height=lv.setter('height'))
        for lid, n in items:
            b=Button(text=n, size_hint_y=None, height=45, background_color=(0.9,0.4,0.4,1)); b.bind(on_release=lambda x, i=lid: self._del_log(i)); lv.add_widget(b)
        s.add_widget(lv); c.add_widget(s); self.dl_pop=Popup(title="Delete Entry", content=c, size_hint=(0.8, 0.6)); self.dl_pop.open()

    def _del_log(self, lid):
        try:
            with self.get_db_connection() as conn: conn.cursor().execute("DELETE FROM eaten_log WHERE id=%s",(lid,))
        except: pass
        self.update_ui(); self.dl_pop.dismiss()

class MyApp(App):
    def build(self): return PlantTrackerLayout()

if __name__ == '__main__': MyApp().run()