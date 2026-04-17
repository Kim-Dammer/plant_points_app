import os
import pymysql
import threading
from datetime import date, timedelta
from dotenv import load_dotenv

from kivy.app import App
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.textinput import TextInput
from kivy.uix.dropdown import DropDown
from kivy.uix.scrollview import ScrollView
from kivy.properties import ListProperty
from kivy.core.window import Window
from kivy.clock import Clock

Window.clearcolor = (0.92, 0.97, 0.92, 1)

# Load the variables from the .env file
load_dotenv()

DB_HOST = os.getenv('DB_HOST')
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_NAME = os.getenv('DB_NAME')
DB_PORT = 3306

class SearchableDropDown(TextInput):
    options = ListProperty([])

    def __init__(self, on_plant_selected, **kwargs):
        super().__init__(**kwargs)
        self.multiline = False
        self.dropdown = DropDown()
        self.bind(text=self.on_text)
        self.bind(focus=self.on_focus)
        self.on_plant_selected = on_plant_selected

        self.background_color = (1, 1, 1, 1)
        self.foreground_color = (0.1, 0.1, 0.1, 1)
        self.cursor_color = (0.2, 0.6, 0.2, 1)
        self.padding = [10, 10]

    def on_text(self, _instance, value):
        self.dropdown.clear_widgets()
        if value:
            filtered_options = [
                opt for opt in self.options 
                if value.lower() in str(opt[0]).lower()
            ]
        else:
            filtered_options = self.options
        
        for option in filtered_options:
            btn = Button(
                text=f"{option[0]}", 
                size_hint_y=None, 
                height=50,
                background_color=(0.6, 0.9, 0.6, 1), 
                color=(0.92, 0.97, 0.92, 1)
            )
            btn.bind(on_release=lambda _, opt=option: self.select_option(opt))
            self.dropdown.add_widget(btn)

        if filtered_options and self.focus:
            if self.dropdown.attach_to is None:
                self.dropdown.open(self)
        else:
            self.dropdown.dismiss()

    def select_option(self, selected_item):
        self.text = "" 
        self.dropdown.dismiss()
        self.on_plant_selected(selected_item)
    
    def on_focus(self, _instance, is_focused):
        if is_focused:
            self.on_text(self, self.text)
        else:
            self.dropdown.dismiss()


class PlantTrackerLayout(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'vertical'
        self.spacing = 10
        self.padding = 10
        self.first_load = True

        self.ensure_tables_exist()
        plant_list = self.get_all_plants()
        self.build_ui(plant_list)

    def get_db_connection(self):
        return pymysql.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            port=DB_PORT,
            autocommit=True 
        )

    def ensure_tables_exist(self):
        with self.get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute('''CREATE TABLE IF NOT EXISTS plants (
                                    name VARCHAR(255) PRIMARY KEY, 
                                    category VARCHAR(255)
                                )''')
                cursor.execute('''CREATE TABLE IF NOT EXISTS eaten_log (
                                    id INT AUTO_INCREMENT PRIMARY KEY, 
                                    log_date DATE, 
                                    plant_name VARCHAR(255),
                                    FOREIGN KEY(plant_name) REFERENCES plants(name)
                                )''')

    def get_all_plants(self):
        with self.get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT name, category FROM plants ORDER BY name")
                return cursor.fetchall()
            
    def delete_last(self, instance):
        """Immediately frees UI, tells DB to delete latest log in background."""
        threading.Thread(target=self._delete_last_thread, daemon=True).start()

    def _delete_last_thread(self):
        """Executes the deletion and refreshes the UI."""
        try:
            with self.get_db_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("DELETE FROM eaten_log ORDER BY id DESC LIMIT 1")
            self.update_ui()
        except Exception as e:
            print(f"Database error on delete: {e}")

    def build_ui(self, plant_list):
        self.score_label = Label(
            text="Plant Points: Loading...", 
            font_size=38, 
            bold=True,
            color=(0.15, 0.45, 0.15, 1),
            size_hint_y=0.15
        )
        self.add_widget(self.score_label)

        self.search_input = SearchableDropDown(
            options=plant_list,
            on_plant_selected=self.save_plant, 
            size_hint_y=None,
            height=44,
            hint_text="Search for a plant..."
        )
        self.add_widget(self.search_input)


        self.list_title = Label(
            text="Eaten this week:",
            font_size=20,
            bold=True,
            color=(0.3, 0.4, 0.3, 1),
            size_hint_y=None,
            height=30,
            halign="left",
            valign="middle"
        )
        self.list_title.bind(size=self.list_title.setter('text_size'))
        self.add_widget(self.list_title)

        self.scroll_view = ScrollView(size_hint_y=0.45) 
        
        self.list_container = BoxLayout(orientation='horizontal', size_hint_y=None)
        self.list_container.bind(minimum_height=self.list_container.setter('height'))
        
        self.daily_label = Label(
            text="", font_size=16, color=(0.1, 0.1, 0.1, 1),
            halign="left", valign="top", size_hint_y=None, markup=True,
            pos_hint={'top': 1}
        )
        self.daily_label.bind(
            width=lambda *args: self.daily_label.setter('text_size')(self.daily_label, (self.daily_label.width, None)),
            texture_size=lambda *args: self.daily_label.setter('height')(self.daily_label, self.daily_label.texture_size[1])
        )
        
        self.totals_label = Label(
            text="", font_size=16, color=(0.1, 0.1, 0.1, 1),
            halign="left", valign="top", size_hint_y=None, markup=True,
            pos_hint={'top': 1}
        )
        self.totals_label.bind(
            width=lambda *args: self.totals_label.setter('text_size')(self.totals_label, (self.totals_label.width, None)),
            texture_size=lambda *args: self.totals_label.setter('height')(self.totals_label, self.totals_label.texture_size[1])
        )
        
        self.list_container.add_widget(self.daily_label)
        self.list_container.add_widget(self.totals_label)
        self.scroll_view.add_widget(self.list_container)
        self.add_widget(self.scroll_view)

        # --- HEATMAP UI ---
        self.heatmap_title = Label(
            text="Activity Heatmap :",
            font_size=16,
            bold=True,
            color=(0.3, 0.4, 0.3, 1),
            size_hint_y=None,
            height=30,
            halign="left",
            valign="middle"
        )
        self.heatmap_title.bind(size=self.heatmap_title.setter('text_size'))
        self.add_widget(self.heatmap_title)

        self.heatmap_scroll = ScrollView(
                    size_hint_y=0.2, 
                    do_scroll_y=False, 
                    do_scroll_x=True
                )

        self.heatmap_container = BoxLayout(
            orientation='horizontal', 
            spacing=2, 
            size_hint_x=None,
        )

        self.heatmap_container.bind(minimum_width=self.heatmap_container.setter('width'))
        self.heatmap_scroll.add_widget(self.heatmap_container) 
        self.add_widget(self.heatmap_scroll)


        bottom_bar = BoxLayout(orientation='horizontal', size_hint_y=None, height=30)

        bottom_bar.add_widget(Label()) 
        
        self.delete_btn = Button(
            text="Undo Last Entry",
            size_hint_x=None,
            width=120,
            background_normal='',
            background_color=(0, 0, 0, 0),
            color=(0.6, 0.6, 0.6, 1),      
            font_size=14
        )
        self.delete_btn.bind(on_release=self.delete_last)
        
        bottom_bar.add_widget(self.delete_btn)
        self.add_widget(bottom_bar)



        self.update_ui()

    def save_plant(self, plant_tuple):
        """Immediately frees the UI, saves to DB in the background."""
        plant_name = plant_tuple[0]
        today_str = date.today().isoformat() 
        
        # Start a background thread so the app doesn't freeze
        threading.Thread(target=self._save_plant_thread, args=(plant_name, today_str), daemon=True).start()

    def _save_plant_thread(self, plant_name, today_str):
        """Actually talks to the remote database."""
        try:
            with self.get_db_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("INSERT INTO eaten_log (log_date, plant_name) VALUES (%s, %s)", 
                                   (today_str, plant_name))
            # After saving, trigger a UI update
            self.update_ui()
        except Exception as e:
            print(f"Database error: {e}")

    def update_ui(self):
        """Starts a background thread to fetch data."""
        threading.Thread(target=self._fetch_data_thread, daemon=True).start()

    def _fetch_data_thread(self):
        """Talks to the remote database to pull the latest stats."""
        today = date.today()
        monday = today - timedelta(days=today.weekday())
        sunday = monday + timedelta(days=6)
        total_weeks = 12 
        start_date = monday - timedelta(weeks=total_weeks - 1)
        
        try:
            with self.get_db_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute('''SELECT plant_name, COUNT(*) FROM eaten_log 
                                      WHERE log_date BETWEEN %s AND %s 
                                      GROUP BY plant_name''', (monday.isoformat(), sunday.isoformat()))
                    weekly_data = cursor.fetchall()
                    
                    cursor.execute('''SELECT log_date, plant_name, COUNT(*) FROM eaten_log 
                                      WHERE log_date BETWEEN %s AND %s 
                                      GROUP BY log_date, plant_name''', (monday.isoformat(), sunday.isoformat()))
                    daily_data = cursor.fetchall()
                    
                    cursor.execute('''SELECT log_date, COUNT(*) FROM eaten_log 
                                      WHERE log_date >= %s 
                                      GROUP BY log_date''', (start_date.isoformat(),))
                    heatmap_data = {row[0].isoformat(): row[1] for row in cursor.fetchall()}

            # Safely hand the fetched data back to the main UI thread using Kivy's Clock
            Clock.schedule_once(lambda dt: self._apply_ui_updates(weekly_data, daily_data, heatmap_data, start_date, total_weeks, today), 0)
        except Exception as e:
            print(f"Database error: {e}")

    def _apply_ui_updates(self, weekly_data, daily_data, heatmap_data, start_date, total_weeks, today):
        """Runs on the main thread. Safely updates the Kivy widgets."""
        # Update UI: Points
        self.score_label.text = f"Plant Points: {len(weekly_data)}"

        # Update UI: Weekly Totals
        totals_list = ["[b]Weekly Totals:[/b]"]
        for plant_name, count in weekly_data:
            totals_list.append(f"• {plant_name} ({count}x)")
            
        # Update UI: Daily Breakdown
        days_order = [(today - timedelta(days=i)).strftime('%A') for i in range(7)]
        daily_breakdown = {day: [] for day in days_order}
        daily_totals = {day: 0 for day in days_order}
        
        for log_date, plant_name, count in daily_data:
            day_name = log_date.strftime('%A')
            daily_breakdown[day_name].append(f"  • {plant_name} ({count}x)")
            daily_totals[day_name] += count
                    
        daily_list = []
        for day in days_order:
            if daily_breakdown[day]:
                daily_list.append(f"[b]{day} ({daily_totals[day]})[/b]")
                daily_list.extend(daily_breakdown[day])
                daily_list.append("") 

        self.daily_label.text = "\n".join(daily_list)
        self.totals_label.text = "\n".join(totals_list)

        needs_rebuild = False
        if not hasattr(self, 'heatmap_buttons'):
            needs_rebuild = True
        elif not hasattr(self, 'heatmap_start_date') or self.heatmap_start_date != start_date:
            needs_rebuild = True

        if needs_rebuild:
            self.heatmap_container.clear_widgets()
            self.heatmap_buttons = {}
            self.heatmap_start_date = start_date

            for week in range(total_weeks):
                week_col = BoxLayout(
                    orientation='vertical', 
                    spacing=3, 
                    size_hint_x=None, 
                    width=20
                )     

                for day in range(7):
                    current_day = start_date + timedelta(weeks=week, days=day)
                    day_str = current_day.isoformat()
                    
                    box = Button(background_normal='', border=(0, 0, 0, 0))
                    week_col.add_widget(box)
                    self.heatmap_buttons[day_str] = box
                    
                self.heatmap_container.add_widget(week_col)

        for week in range(total_weeks):
            for day in range(7):
                current_day = start_date + timedelta(weeks=week, days=day)
                day_str = current_day.isoformat()
                
                box = self.heatmap_buttons.get(day_str)
                if not box:
                    continue

                count = heatmap_data.get(day_str, 0)
                
                if current_day > today:
                    color = (1, 1, 1, 0) 
                elif count == 0:
                    color = (0.85, 0.9, 0.85, 1) 
                elif count >= 12:
                    color = (0.0, 0.81, 0.82, 1) 
                else:
                    fraction = count / 11.0
                    r = 0.7 + (0.1 - 0.7) * fraction
                    g = 0.9 + (0.5 - 0.9) * fraction
                    b = 0.7 + (0.1 - 0.7) * fraction
                    color = (r, g, b, 1)

                box.background_color = color

class MyApp(App):
    def build(self):
        return PlantTrackerLayout()


if __name__ == '__main__':
    MyApp().run()