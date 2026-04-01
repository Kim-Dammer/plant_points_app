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

    # Prefixing 'instance' with '_' tells the linter we are ignoring it on purpose
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
            # Used '_' for the unused button instance warning
            btn.bind(on_release=lambda _, opt=option: self.select_option(opt))
            self.dropdown.add_widget(btn)

        if filtered_options and self.focus:
            if self.dropdown.attach_to is None:
                self.dropdown.open(self)
        else:
            self.dropdown.dismiss()

    def select_option(self, selected_item):
        self.text = ""  # Removed the redundant str()
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

        self.save_file = 'eaten_plants_data.json'
        self.current_week_key = self.get_current_week_string()
        self.all_history = self.load_progress()

        if self.current_week_key not in self.all_history:
            self.all_history[self.current_week_key] = {}
            
        if "daily_counts" not in self.all_history:
            self.all_history["daily_counts"] = {}

        self.eaten_plants = self.all_history[self.current_week_key]
        plant_list = self.load_plants_from_csv('plant_database.csv')

        self.build_ui(plant_list)

    def build_ui(self, plant_list):
        """Modularized method to handle all UI widget creation."""
        self.score_label = Label(
            text="Plant Points: 0", 
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
        
        #Two columns
        self.list_container = BoxLayout(orientation='horizontal', size_hint_y=None)
        self.list_container.bind(minimum_height=self.list_container.setter('height'))
        
        # Left column: Daily breakdown
        self.daily_label = Label(
            text="", font_size=16, color=(0.1, 0.1, 0.1, 1),
            halign="left", valign="top", size_hint_y=None, markup=True,
            pos_hint={'top': 1}
        )
        self.daily_label.bind(
            width=lambda *args: self.daily_label.setter('text_size')(self.daily_label, (self.daily_label.width, None)),
            texture_size=lambda *args: self.daily_label.setter('height')(self.daily_label, self.daily_label.texture_size[1])
        )
        
        # Right column: Totals
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
            text="Activity Heatmap (Scroll for history):",
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


        self.update_ui()

    def get_current_week_string(self):
        # Replaced the unused 'weekday' variable with '_'
        year, week, _ = date.today().isocalendar()
        return f"{year}-W{week:02d}"

    def load_plants_from_csv(self, filename):
        data = []
        if not os.path.exists(filename):
            print(f"Error: {filename} not found.")
            return data

        with open(filename, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                data.append((row['plant_name'].strip(), row['category'].strip()))
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
        
        day_name = date.today().strftime('%A')

        if plant_name not in self.eaten_plants:
            self.eaten_plants[plant_name] = {'count': 1, 'category': category, 'daily': {day_name: 1}}
        else:
            self.eaten_plants[plant_name]['count'] += 1


            if 'daily' not in self.eaten_plants[plant_name]:
                self.eaten_plants[plant_name]['daily'] = {}
                
            if day_name not in self.eaten_plants[plant_name]['daily']:
                self.eaten_plants[plant_name]['daily'][day_name] = 0
                
            self.eaten_plants[plant_name]['daily'][day_name] += 1

        today_str = date.today().isoformat() 
        if today_str not in self.all_history.get("daily_counts", {}):
            self.all_history["daily_counts"][today_str] = 0
            
        self.all_history["daily_counts"][today_str] += 1

        self.save_progress()
        self.update_ui()
        
    def update_ui(self):
        self.score_label.text = f"Plant Points: {len(self.eaten_plants)}"

        totals_list = ["[b]Weekly Totals:[/b]"]
        for name, info in self.eaten_plants.items():
            totals_list.append(f"• {name} ({info.get('count', 0)}x)")
            
        # 2. Build the left column (Daily breakdown)
        days_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        daily_breakdown = {day: [] for day in days_order}
        
        for name, info in self.eaten_plants.items():
            for day, count in info.get('daily', {}).items():
                if day in daily_breakdown:
                    daily_breakdown[day].append(f"  • {name} ({count}x)")
                    
        daily_list = []
        for day in days_order:
            if daily_breakdown[day]:
                daily_list.append(f"[b]{day}[/b]")
                daily_list.extend(daily_breakdown[day])
                daily_list.append("") # Add a blank line between days
                
        # Fallback for old data logged before this update
        if not daily_list and self.eaten_plants:
            daily_list.append("[i]Old data: No daily breakdown available.[/i]")

        self.daily_label.text = "\n".join(daily_list)
        self.totals_label.text = "\n".join(totals_list)


        self.heatmap_container.clear_widgets()
        today = date.today()
        monday = today - timedelta(days=today.weekday())
        start_date = monday - timedelta(weeks=11)

        total_weeks = 12 
        start_date = monday - timedelta(weeks=total_weeks - 1)

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
                
                count = self.all_history.get("daily_counts", {}).get(day_str, 0)
                
                if current_day > today:
                    color = (1, 1, 1, 0)  # Future days are transparent
                elif count == 0:
                    color = (0.85, 0.9, 0.85, 1) # Empty state color
                elif count >= 12:
                    color = (0.0, 0.81, 0.82, 1) # Turquoise victory color!
                else:
                    # Continuous green scale for 1 to 11 items
                    fraction = count / 11.0
                    
                    # Start Green (Light): R=0.7, G=0.9, B=0.7
                    # End Green (Dark): R=0.1, G=0.5, B=0.1
                    r = 0.7 + (0.1 - 0.7) * fraction
                    g = 0.9 + (0.5 - 0.9) * fraction
                    b = 0.7 + (0.1 - 0.7) * fraction
                    
                    color = (r, g, b, 1)

                box = Button(background_normal='', background_color=color, border=(0, 0, 0, 0))
                week_col.add_widget(box)
                
            self.heatmap_container.add_widget(week_col)

        self.heatmap_scroll.scroll_x = 1.0

class MyApp(App):
    def build(self):
        return PlantTrackerLayout()


if __name__ == '__main__':
    MyApp().run()