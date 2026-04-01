import csv
import json
import os
from datetime import date, timedelta
from kivy.app import App
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.textinput import TextInput
from kivy.uix.dropdown import DropDown
from kivy.uix.scrollview import ScrollView
from kivy.properties import ListProperty
from kivy.core.window import Window

Window.clearcolor = (0.92, 0.97, 0.92, 1)

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
        self.padding_y = [10, 10]

    def on_text(self, instance, value):
        self.dropdown.clear_widgets()
        if value:
            filtered_options = [opt for opt in self.options if value.lower() in str(opt[0]).lower()]
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
            btn.bind(on_release=lambda btn_instance, opt=option: self.select_option(opt))
            self.dropdown.add_widget(btn)

        if filtered_options and self.focus:
            if self.dropdown.attach_to is None:
                self.dropdown.open(self)
        else:
            self.dropdown.dismiss()

    def select_option(self, selected_item):
        self.text = str("") 
        self.dropdown.dismiss()
        self.on_plant_selected(selected_item)
    
    def on_focus(self, instance, is_focused):
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

        self.save_file = 'eaten_plants_data.json'

        self.current_week_key = self.get_current_week_string()
        self.all_history = self.load_progress()

        if self.current_week_key not in self.all_history:
            self.all_history[self.current_week_key] = {}
            
        if "daily_counts" not in self.all_history:
            self.all_history["daily_counts"] = {}

        self.eaten_plants = self.all_history[self.current_week_key]
        plant_list = self.load_plants_from_csv('plant_database.csv')

        # --- UI BUILD ---
        self.score_label = Label(
            text="Plant Points: 0", 
            font_size=42, 
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

        self.scroll_view = ScrollView(size_hint_y=0.45) # Reduced size to fit heatmap
        
        self.list_label = Label(
            text="", 
            font_size=18,
            color=(0.1, 0.1, 0.1, 1),
            halign="left", 
            valign="top",
            size_hint_y=None
        )
        self.list_label.bind(
            width=lambda *x: self.list_label.setter('text_size')(self.list_label, (self.list_label.width, None)),
            texture_size=lambda *x: self.list_label.setter('height')(self.list_label, self.list_label.texture_size[1])
        )
        
        self.scroll_view.add_widget(self.list_label)
        self.add_widget(self.scroll_view)

        # --- HEATMAP UI ---
        self.heatmap_title = Label(
            text="Activity Heatmap (Last 12 Weeks):",
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

        self.heatmap_container = BoxLayout(orientation='horizontal', spacing=2, size_hint_y=0.2)
        self.add_widget(self.heatmap_container)

        self.update_ui()

    def get_current_week_string(self):
        year, week, weekday = date.today().isocalendar()
        return f"{year}-W{week:02d}"

    def load_plants_from_csv(self, filename):
        data = []
        try:
            with open(filename, mode='r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    data.append((row['plant_name'].strip(), row['category'].strip()))
        except FileNotFoundError:
            print(f"Error: {filename} not found.")
        return data

    def load_progress(self):
        if os.path.exists(self.save_file):
            with open(self.save_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
                if data and not any("-W" in k for k in data.keys()) and "daily_counts" not in data:
                    return {self.current_week_key: data, "daily_counts": {}}
                    
                return data
        return {}

    def save_progress(self):
        self.all_history[self.current_week_key] = self.eaten_plants
        with open(self.save_file, 'w', encoding='utf-8') as f:
            json.dump(self.all_history, f, indent=4)

    def save_plant(self, plant_tuple):
        plant_name = plant_tuple[0]
        category = plant_tuple[1]
        
        if plant_name not in self.eaten_plants:
            self.eaten_plants[plant_name] = {'count': 1, 'category': category}
        else:
            self.eaten_plants[plant_name]['count'] += 1

        # 2. Save to daily total for the heatmap
        today_str = date.today().isoformat() # Gets string like '2026-03-31'
        if today_str not in self.all_history["daily_counts"]:
            self.all_history["daily_counts"][today_str] = 0
            
        self.all_history["daily_counts"][today_str] += 1

        self.save_progress()
        self.update_ui()
        
    def update_ui(self):
        self.score_label.text = f"Plant Points: {len(self.eaten_plants)}"
        history_list = [f"• {name} ({info['count']}x)" for name, info in self.eaten_plants.items()]
        self.list_label.text = "\n".join(history_list)

        self.heatmap_container.clear_widgets()
        today = date.today()
        monday = today - timedelta(days=today.weekday())
        start_date = monday - timedelta(weeks=11)

        for week in range(12):
            week_col = BoxLayout(orientation='vertical', spacing=2)
            
            for day in range(7):
                current_day = start_date + timedelta(weeks=week, days=day)
                day_str = current_day.isoformat()
                
                count = self.all_history.get("daily_counts", {}).get(day_str, 0)
                
                if current_day > today:
                    color = (1, 1, 1, 0)  # Future days are fully transparent
                elif count == 0:
                    color = (0.85, 0.9, 0.85, 1) # Empty / Lightest Green
                elif count <= 2:
                    color = (0.6, 0.85, 0.6, 1)  # Light Green
                elif count <= 4:
                    color = (0.3, 0.7, 0.3, 1)   # Medium Green
                else:
                    color = (0.1, 0.5, 0.1, 1)   # Dark Green (5+ items)

                box = Button(background_normal='', background_color=color)
                week_col.add_widget(box)
                
            self.heatmap_container.add_widget(week_col)

class MyApp(App):
    def build(self):
        return PlantTrackerLayout()

if __name__ == '__main__':
    MyApp().run()