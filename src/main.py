from kivy.app import App
from kivy.core.window import Window
from kivy.resources import resource_add_path
from pathlib import Path

Window.clearcolor = (0.92, 0.97, 0.92, 1)

from ui import PlantTrackerLayout  # noqa: E402 — import after Window config


class MyApp(App):
    def build(self):
        return PlantTrackerLayout()

def main():
    resource_add_path(str(Path(__file__).parent))
    MyApp().run()

if __name__ == '__main__':
    main()