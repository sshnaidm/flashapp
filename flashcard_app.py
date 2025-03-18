from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.popup import Popup
from kivy.uix.filechooser import FileChooserListView
from kivy.core.window import Window
from kivy.properties import ObjectProperty, StringProperty
from kivy.uix.checkbox import CheckBox  # noqa: F401 - Used in kv file
import json
import os
from kivy.utils import platform

# Data models


class Card:
    def __init__(self, question="", answer="", status="new"):  # Changed from "unknown" to "new"
        self.question = question
        self.answer = answer
        self.status = status  # "new", "know", "dont_know"

    def to_dict(self):
        return {"question": self.question, "answer": self.answer, "status": self.status}

    @staticmethod
    def from_dict(data):
        return Card(data["question"], data["answer"], data["status"])


class Deck:
    def __init__(self, name=""):
        self.name = name
        self.cards = []

    def add_card(self, card):
        self.cards.append(card)

    def remove_card(self, index):
        if 0 <= index < len(self.cards):
            del self.cards[index]

    def to_dict(self):
        return {"name": self.name, "cards": [card.to_dict() for card in self.cards]}

    @staticmethod
    def from_dict(data):
        deck = Deck(data["name"])
        for card_data in data["cards"]:
            deck.add_card(Card.from_dict(card_data))
        return deck


class Folder:
    def __init__(self, name=""):
        self.name = name
        self.decks = []

    def add_deck(self, deck):
        self.decks.append(deck)

    def remove_deck(self, index):
        if 0 <= index < len(self.decks):
            del self.decks[index]

    def to_dict(self):
        return {"name": self.name, "decks": [deck.to_dict() for deck in self.decks]}

    @staticmethod
    def from_dict(data):
        folder = Folder(data["name"])
        for deck_data in data["decks"]:
            folder.add_deck(Deck.from_dict(deck_data))
        return folder


class DataManager:
    def __init__(self):
        self.folders = []
        self._current_deck_cache = None
        self._current_deck_key = None
        self.current_folder_index = -1
        self.current_deck_index = -1
        self.filename = "flashcards_data.json"

        # Create data directory if it doesn't exist
        os.makedirs(os.path.dirname(self.get_data_path()), exist_ok=True)

        # Load data from file if exists
        self.load_data()

    def get_data_path(self):
        if platform == "android":
            from android.storage import primary_external_storage_path

            storage_path = primary_external_storage_path()
            data_dir = os.path.join(storage_path, "flashcardapp")
        else:
            data_dir = os.path.expanduser("~/.flashcardapp")

        os.makedirs(data_dir, exist_ok=True)
        return os.path.join(data_dir, "flashcards.json")

    def load_data(self):
        try:
            with open(self.get_data_path(), "r") as f:
                data = json.load(f)
                self.folders = []
                for folder_data in data:
                    self.folders.append(Folder.from_dict(folder_data))
        except (FileNotFoundError, json.JSONDecodeError):
            # Create a default folder and deck if no data exists
            default_folder = Folder("Default Folder")
            default_deck = Deck("Default Deck")
            default_folder.add_deck(default_deck)
            self.folders = [default_folder]
            self.save_data()

    def save_data(self):
        with open(self.get_data_path(), "w") as f:
            json.dump([folder.to_dict() for folder in self.folders], f, indent=2)

    def add_folder(self, folder_name):
        folder = Folder(folder_name)
        self.folders.append(folder)
        self.save_data()
        return len(self.folders) - 1

    def add_deck(self, folder_index, deck_name):
        if 0 <= folder_index < len(self.folders):
            deck = Deck(deck_name)
            self.folders[folder_index].add_deck(deck)
            self.save_data()
            return len(self.folders[folder_index].decks) - 1
        return -1

    def add_card(self, folder_index, deck_index, question, answer):
        if 0 <= folder_index < len(self.folders) and 0 <= deck_index < len(self.folders[folder_index].decks):
            card = Card(question, answer)
            self.folders[folder_index].decks[deck_index].add_card(card)
            self.save_data()
            return len(self.folders[folder_index].decks[deck_index].cards) - 1
        return -1

    def import_cards_from_file(self, folder_index, deck_index, file_path, separator=";"):
        """Import cards from a text file with the specified separator."""
        if 0 <= folder_index < len(self.folders) and 0 <= deck_index < len(self.folders[folder_index].decks):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()

                imported_count = 0
                for line in lines:
                    line = line.strip()
                    if line and separator in line:
                        parts = line.split(separator, 1)  # Split only on the first occurrence
                        if len(parts) == 2:
                            question = parts[0].strip()
                            answer = parts[1].strip()
                            if question and answer:  # Ensure both sides have content
                                self.add_card(folder_index, deck_index, question, answer)
                                imported_count += 1

                self.save_data()
                return imported_count
            except Exception as e:
                print(f"Error importing cards: {str(e)}")
                return -1
        return -1

    def import_cards_as_new_deck(self, folder_index, deck_name, file_path, separator=";"):
        """Import cards from a text file as a new deck."""
        if 0 <= folder_index < len(self.folders):
            deck_index = self.add_deck(folder_index, deck_name)
            if deck_index >= 0:
                return self.import_cards_from_file(folder_index, deck_index, file_path, separator)
        return -1

    def set_current_folder_deck(self, folder_index, deck_index):
        self.current_folder_index = folder_index
        self.current_deck_index = deck_index

    def get_current_deck(self):
        key = (self.current_folder_index, self.current_deck_index)
        if self._current_deck_key != key:
            if 0 <= self.current_folder_index < len(self.folders) and 0 <= self.current_deck_index < len(
                self.folders[self.current_folder_index].decks
            ):
                self._current_deck_cache = self.folders[self.current_folder_index].decks[self.current_deck_index]
                self._current_deck_key = key
            else:
                self._current_deck_cache = None
                self._current_deck_key = None
        return self._current_deck_cache

    def update_card_status(self, card_index, status):
        deck = self.get_current_deck()
        if deck and 0 <= card_index < len(deck.cards):
            deck.cards[card_index].status = status
            self.save_data()

    def bulk_update_status(self, status_from, status_to):
        deck = self.get_current_deck()
        if deck:
            for card in deck.cards:
                if card.status == status_from:
                    card.status = status_to
            self.save_data()


# UI Screens
class HomeScreen(Screen):
    folder_list = ObjectProperty(None)

    def __init__(self, **kwargs):
        super(HomeScreen, self).__init__(**kwargs)
        self.data_manager = App.get_running_app().data_manager

    def on_enter(self):
        self.update_folder_list()

    def update_folder_list(self):
        self.folder_list.clear_widgets()
        for i, folder in enumerate(self.data_manager.folders):
            btn = Button(text=folder.name, size_hint_y=None, height=50)
            btn.folder_index = i
            btn.bind(on_release=self.open_folder)
            self.folder_list.add_widget(btn)

    def open_folder(self, instance):
        folder_screen = self.manager.get_screen("folder")
        folder_screen.folder_index = instance.folder_index
        folder_screen.folder_name = self.data_manager.folders[instance.folder_index].name
        self.manager.current = "folder"

    def add_new_folder(self):
        content = BoxLayout(orientation="vertical", padding=10, spacing=10)
        txt_input = TextInput(hint_text="Folder Name", multiline=False)
        btn_layout = BoxLayout(size_hint_y=None, height=50, spacing=5)

        popup = Popup(title="Add New Folder", content=content, size_hint=(0.8, 0.4))

        def on_submit(instance):
            if txt_input.text.strip():
                self.data_manager.add_folder(txt_input.text.strip())
                self.update_folder_list()
                popup.dismiss()

        btn_cancel = Button(text="Cancel")
        btn_cancel.bind(on_release=popup.dismiss)
        btn_submit = Button(text="Add")
        btn_submit.bind(on_release=on_submit)

        btn_layout.add_widget(btn_cancel)
        btn_layout.add_widget(btn_submit)
        content.add_widget(txt_input)
        content.add_widget(btn_layout)

        popup.open()


class FolderScreen(Screen):
    deck_list = ObjectProperty(None)
    folder_label = ObjectProperty(None)
    folder_index = -1
    folder_name = StringProperty("")

    def __init__(self, **kwargs):
        super(FolderScreen, self).__init__(**kwargs)
        self.data_manager = App.get_running_app().data_manager

    def on_enter(self):
        self.folder_label.text = f"Folder: {self.folder_name}"
        self.update_deck_list()

    def update_deck_list(self):
        self.deck_list.clear_widgets()
        if 0 <= self.folder_index < len(self.data_manager.folders):
            for i, deck in enumerate(self.data_manager.folders[self.folder_index].decks):
                btn = Button(text=deck.name, size_hint_y=None, height=50)
                btn.deck_index = i
                btn.bind(on_release=self.open_deck)
                self.deck_list.add_widget(btn)

    def open_deck(self, instance):
        deck_screen = self.manager.get_screen("deck")
        deck_screen.folder_index = self.folder_index
        deck_screen.deck_index = instance.deck_index
        deck_screen.deck_name = self.data_manager.folders[self.folder_index].decks[instance.deck_index].name
        self.manager.current = "deck"

    def go_back(self):
        self.manager.current = "home"

    def add_new_deck(self):
        content = BoxLayout(orientation="vertical", padding=10, spacing=10)
        txt_input = TextInput(hint_text="Deck Name", multiline=False)
        btn_layout = BoxLayout(size_hint_y=None, height=50, spacing=5)

        popup = Popup(title="Add New Deck", content=content, size_hint=(0.8, 0.4))

        def on_submit(instance):
            if txt_input.text.strip():
                self.data_manager.add_deck(self.folder_index, txt_input.text.strip())
                self.update_deck_list()
                popup.dismiss()

        btn_cancel = Button(text="Cancel")
        btn_cancel.bind(on_release=popup.dismiss)
        btn_submit = Button(text="Add")
        btn_submit.bind(on_release=on_submit)

        btn_layout.add_widget(btn_cancel)
        btn_layout.add_widget(btn_submit)
        content.add_widget(txt_input)
        content.add_widget(btn_layout)

        popup.open()

    def import_cards_to_folder(self):
        # Create a popup to import cards directly to a new deck in this folder
        content = BoxLayout(orientation="vertical", padding=10, spacing=10)
        txt_input = TextInput(hint_text="New Deck Name", multiline=False)
        sep_input = TextInput(hint_text="Separator (default: ;)", multiline=False, text=";")
        file_chooser = FileChooserListView(path=os.path.expanduser("~"))

        content.add_widget(Label(text="Select a text file to import:"))
        content.add_widget(file_chooser)
        content.add_widget(Label(text="Enter separator character:"))
        content.add_widget(sep_input)
        content.add_widget(Label(text="Enter deck name:"))
        content.add_widget(txt_input)

        btn_layout = BoxLayout(size_hint_y=None, height=50, spacing=5)

        popup = Popup(title="Import Cards to New Deck", content=content, size_hint=(0.9, 0.9))

        def on_submit(instance):
            if not file_chooser.selection:
                return

            if not txt_input.text.strip():
                return

            separator = sep_input.text.strip() or ";"

            imported = self.data_manager.import_cards_as_new_deck(
                self.folder_index, txt_input.text.strip(), file_chooser.selection[0], separator
            )

            if imported > 0:
                popup.dismiss()
                success = Popup(
                    title="Success",
                    content=Label(text=f"Successfully imported {imported} cards."),
                    size_hint=(0.7, 0.3),
                )
                success.open()
                self.update_deck_list()
            elif imported == 0:
                error = Popup(
                    title="Error", content=Label(text="No valid cards found in the file."), size_hint=(0.7, 0.3)
                )
                error.open()
            else:
                error = Popup(title="Error", content=Label(text="Error importing cards."), size_hint=(0.7, 0.3))
                error.open()

        btn_cancel = Button(text="Cancel")
        btn_cancel.bind(on_release=popup.dismiss)
        btn_submit = Button(text="Import")
        btn_submit.bind(on_release=on_submit)

        btn_layout.add_widget(btn_cancel)
        btn_layout.add_widget(btn_submit)
        content.add_widget(btn_layout)

        popup.open()


class ImportCardsScreen(Screen):
    file_chooser = ObjectProperty(None)
    folder_index = -1
    deck_index = -1

    def __init__(self, **kwargs):
        super(ImportCardsScreen, self).__init__(**kwargs)
        self.data_manager = App.get_running_app().data_manager

    def on_enter(self):
        # Set default path to user's home directory
        self.file_chooser.path = os.path.expanduser("~")

    def import_cards(self, file_path, separator, create_new_deck, deck_name):
        if not file_path:
            self.show_error("Please select a file.")
            return

        if create_new_deck and not deck_name.strip():
            self.show_error("Please enter a deck name.")
            return

        try:
            if create_new_deck:
                imported = self.data_manager.import_cards_as_new_deck(
                    self.folder_index, deck_name.strip(), file_path[0], separator
                )
            else:
                imported = self.data_manager.import_cards_from_file(
                    self.folder_index, self.deck_index, file_path[0], separator
                )

            if imported > 0:
                self.show_success(f"Successfully imported {imported} cards.")
            elif imported == 0:
                self.show_error("No valid cards found in the file.")
            else:
                self.show_error("Error importing cards.")
        except Exception as e:
            self.show_error(f"Error: {str(e)}")

    def show_error(self, message):
        popup = Popup(title="Error", content=Label(text=message), size_hint=(0.7, 0.3))
        popup.open()

    def show_success(self, message):
        content = BoxLayout(orientation="vertical", padding=10, spacing=10)
        content.add_widget(Label(text=message))
        btn = Button(text="OK", size_hint_y=None, height=50)

        popup = Popup(title="Success", content=content, size_hint=(0.7, 0.3))

        def on_btn_press(instance):
            popup.dismiss()
            self.go_back()

        btn.bind(on_release=on_btn_press)
        content.add_widget(btn)
        popup.open()

    def go_back(self):
        self.manager.current = "deck"
        # Refresh deck screen
        deck_screen = self.manager.get_screen("deck")
        deck_screen.update_card_list()


class DeckScreen(Screen):
    card_list = ObjectProperty(None)
    deck_label = ObjectProperty(None)
    folder_index = -1
    deck_index = -1
    deck_name = StringProperty("")
    _widget_cache = {}

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.data_manager = App.get_running_app().data_manager
        self.start_idx = 0  # Initialize pagination start index

    def _create_cached_widget(self, widget_type, key, **kwargs):
        """Create or get a cached widget."""
        cache_key = (widget_type, key)
        if cache_key not in self._widget_cache:
            self._widget_cache[cache_key] = widget_type(**kwargs)
        return widget_type(**kwargs)  # Always create new instance for now

    def on_enter(self):
        self.deck_label.text = f"Deck: {self.deck_name}"
        self.update_card_list()

    def update_card_list(self):
        self.card_list.clear_widgets()
        deck = self.data_manager.folders[self.folder_index].decks[self.deck_index]

        # Add deck name label
        deck_name = Label(text=f"[b]{deck.name}[/b]", markup=True, size_hint_y=None, height="40dp")
        self.card_list.add_widget(deck_name)

        # Pagination variables
        page_size = 10
        start_idx = getattr(self, "start_idx", 0)  # Get current page start index

        # Create navigation layout
        nav_layout = BoxLayout(size_hint_y=None, height="40dp", spacing=10)

        prev_btn = Button(text="Previous", disabled=(start_idx == 0), size_hint_x=0.5)

        next_btn = Button(text="Next", disabled=(start_idx + page_size >= len(deck.cards)), size_hint_x=0.5)

        def on_prev(instance):
            self.start_idx = max(0, start_idx - page_size)
            self.update_card_list()

        def on_next(instance):
            self.start_idx = min(len(deck.cards) - 1, start_idx + page_size)
            self.update_card_list()

        prev_btn.bind(on_release=on_prev)
        next_btn.bind(on_release=on_next)

        nav_layout.add_widget(prev_btn)
        nav_layout.add_widget(next_btn)
        self.card_list.add_widget(nav_layout)

        # Display cards for current page
        end_idx = min(start_idx + page_size, len(deck.cards))
        for i in range(start_idx, end_idx):
            card = deck.cards[i]

            # Create card layout with more height for buttons
            card_layout = BoxLayout(
                orientation="horizontal", size_hint_y=None, height="50dp", spacing=5, padding=[0, 5]
            )

            # Add card content
            card_label = Label(text=f"Q: {card.question[:50]}... | A: {card.answer[:50]}...", size_hint_x=0.6)

            # Create status buttons layout
            status_layout = BoxLayout(orientation="horizontal", size_hint_x=0.25, spacing=2)

            # Status indicator and buttons
            status_colors = {
                "new": [0.7, 0.7, 0.7, 1],  # Gray
                "know": [0.2, 0.8, 0.2, 1],  # Green
                "dont_know": [0.8, 0.2, 0.2, 1],  # Red
            }

            def create_status_button(status_type, card_idx):
                btn = Button(
                    text=status_type.replace("_", " ").title(),
                    size_hint_x=1 / 3,
                    background_color=status_colors[status_type],
                )

                def on_status_press(instance):
                    deck.cards[card_idx].status = status_type
                    self.data_manager.save_data()
                    self.update_card_list()

                btn.bind(on_release=on_status_press)
                return btn

            # Add status buttons
            for status in ["new", "know", "dont_know"]:
                btn = create_status_button(status, i)
                # Highlight the current status
                if card.status == status:
                    btn.bold = True
                    btn.background_normal = ""
                status_layout.add_widget(btn)

            # Add edit button
            edit_btn = Button(text="Edit", size_hint_x=0.15)
            edit_btn.card_index = i
            edit_btn.bind(on_release=self.edit_card)

            # Add all widgets to card layout
            card_layout.add_widget(card_label)
            card_layout.add_widget(status_layout)
            card_layout.add_widget(edit_btn)

            self.card_list.add_widget(card_layout)

    def edit_card(self, instance):
        card_index = instance.card_index
        deck = self.data_manager.folders[self.folder_index].decks[self.deck_index]
        card = deck.cards[card_index]

        content_layout = BoxLayout(orientation="vertical", padding=10, spacing=10)
        question_input = TextInput(text=card.question, multiline=True, size_hint_y=None, height=100)
        answer_input = TextInput(text=card.answer, multiline=True, size_hint_y=None, height=100)
        btn_layout = BoxLayout(size_hint_y=None, height=50, spacing=5)

        sv = ScrollView()
        layout = BoxLayout(orientation="vertical", spacing=10, size_hint_y=None)
        layout.bind(minimum_height=layout.setter("height"))
        layout.add_widget(Label(text="Question/Front Side:", size_hint_y=None, height=30))
        layout.add_widget(question_input)
        layout.add_widget(Label(text="Answer/Back Side:", size_hint_y=None, height=30))
        layout.add_widget(answer_input)
        layout.add_widget(btn_layout)
        sv.add_widget(layout)

        popup = Popup(title="Edit Card", content=sv, size_hint=(0.9, 0.9))

        def on_submit(instance):
            if question_input.text.strip() and answer_input.text.strip():
                # Update the card
                card.question = question_input.text.strip()
                card.answer = answer_input.text.strip()
                self.data_manager.save_data()
                self.update_card_list()
                popup.dismiss()

        btn_cancel = Button(text="Cancel")
        btn_cancel.bind(on_release=popup.dismiss)
        btn_submit = Button(text="Save")
        btn_submit.bind(on_release=on_submit)

        btn_layout.add_widget(btn_cancel)
        btn_layout.add_widget(btn_submit)

        popup.open()

    def go_back(self):
        self.manager.current = "folder"

    def add_new_card(self):
        question_input = TextInput(hint_text="Question/Front Side", multiline=True, size_hint_y=None, height=100)
        answer_input = TextInput(hint_text="Answer/Back Side", multiline=True, size_hint_y=None, height=100)
        btn_layout = BoxLayout(size_hint_y=None, height=50, spacing=5)

        sv = ScrollView()
        layout = BoxLayout(orientation="vertical", spacing=10, size_hint_y=None)
        layout.bind(minimum_height=layout.setter("height"))
        layout.add_widget(Label(text="Question/Front Side:", size_hint_y=None, height=30))
        layout.add_widget(question_input)
        layout.add_widget(Label(text="Answer/Back Side:", size_hint_y=None, height=30))
        layout.add_widget(answer_input)
        layout.add_widget(btn_layout)
        sv.add_widget(layout)

        popup = Popup(title="Add New Card", content=sv, size_hint=(0.9, 0.9))

        def on_submit(instance):
            if question_input.text.strip() and answer_input.text.strip():
                self.data_manager.add_card(
                    self.folder_index, self.deck_index, question_input.text.strip(), answer_input.text.strip()
                )
                self.update_card_list()
                popup.dismiss()

        btn_cancel = Button(text="Cancel")
        btn_cancel.bind(on_release=popup.dismiss)
        btn_submit = Button(text="Add")
        btn_submit.bind(on_release=on_submit)

        btn_layout.add_widget(btn_cancel)
        btn_layout.add_widget(btn_submit)

        popup.open()

    def start_study_session(self):
        deck = self.data_manager.folders[self.folder_index].decks[self.deck_index]
        if not deck.cards:
            popup = Popup(
                title="No Cards", content=Label(text="There are no cards in this deck to study."), size_hint=(0.7, 0.3)
            )
            popup.open()
            return

        # Set current deck in data manager
        self.data_manager.set_current_folder_deck(self.folder_index, self.deck_index)

        # Reset all cards to "unknown" before starting
        for card in deck.cards:
            card.status = "unknown"
        self.data_manager.save_data()

        # Go to study screen
        study_screen = self.manager.get_screen("study")
        study_screen.show_question_side = True  # Start with question side
        study_screen.setup_session()
        self.manager.current = "study"

    def study_dont_know(self):
        deck = self.data_manager.folders[self.folder_index].decks[self.deck_index]
        # Check ALL cards, not just the current page
        has_dont_know = any(card.status == "dont_know" for card in deck.cards)

        if not has_dont_know:
            popup = Popup(
                title="No Cards", content=Label(text='There are no "Don\'t Know" cards to study.'), size_hint=(0.7, 0.3)
            )
            popup.open()
            return

        # Set current deck in data manager
        self.data_manager.set_current_folder_deck(self.folder_index, self.deck_index)

        # Go to study screen
        study_screen = self.manager.get_screen("study")
        study_screen.show_question_side = True  # Start with question side
        study_screen.setup_session(filter_status="dont_know")
        self.manager.current = "study"

    def flip_deck(self):
        # Set current deck in data manager
        self.data_manager.set_current_folder_deck(self.folder_index, self.deck_index)

        # Go to study screen with answer side first
        study_screen = self.manager.get_screen("study")
        study_screen.show_question_side = False  # This will make it show answers first
        study_screen.show_card_side = True  # Start with showing the answer
        study_screen.setup_session()
        self.manager.current = "study"

    def bulk_reset(self):
        deck = self.data_manager.folders[self.folder_index].decks[self.deck_index]
        for card in deck.cards:
            card.status = "new"  # Changed from "unknown" to "new"
        self.data_manager.save_data()
        self.update_card_list()

    def import_cards(self):
        # Navigate to import screen and pass folder/deck info
        import_screen = self.manager.get_screen("import")
        import_screen.folder_index = self.folder_index
        import_screen.deck_index = self.deck_index
        self.manager.current = "import"

    def bulk_know(self):
        deck = self.data_manager.folders[self.folder_index].decks[self.deck_index]
        for card in deck.cards:
            if card.status == "dont_know":
                card.status = "know"
        self.data_manager.save_data()
        self.update_card_list()


class StudyScreen(Screen):
    card_display = ObjectProperty(None)
    progress_label = ObjectProperty(None)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.data_manager = App.get_running_app().data_manager
        self.cards = []
        self.current_index = 0
        self.history = []
        self.show_question_side = True  # Default side to start with
        self.show_card_side = True  # Current side being shown
        self.card_indices = []  # Store indices of cards being studied

    def edit_current_card(self):
        if not self.card_indices or self.current_index >= len(self.card_indices):
            return

        deck = self.data_manager.get_current_deck()
        card_index = self.card_indices[self.current_index]
        card = deck.cards[card_index]

        question_input = TextInput(text=card.question, multiline=True, size_hint_y=None, height=100)
        answer_input = TextInput(text=card.answer, multiline=True, size_hint_y=None, height=100)
        btn_layout = BoxLayout(size_hint_y=None, height=50, spacing=5)

        sv = ScrollView()
        layout = BoxLayout(orientation="vertical", spacing=10, size_hint_y=None)
        layout.bind(minimum_height=layout.setter("height"))
        layout.add_widget(Label(text="Question/Front Side:", size_hint_y=None, height=30))
        layout.add_widget(question_input)
        layout.add_widget(Label(text="Answer/Back Side:", size_hint_y=None, height=30))
        layout.add_widget(answer_input)
        layout.add_widget(btn_layout)
        sv.add_widget(layout)

        popup = Popup(title="Edit Card", content=sv, size_hint=(0.9, 0.9))

        def on_submit(instance):
            if question_input.text.strip() and answer_input.text.strip():
                # Update the card
                card.question = question_input.text.strip()
                card.answer = answer_input.text.strip()
                self.data_manager.save_data()
                self.update_display()
                popup.dismiss()

        btn_cancel = Button(text="Cancel")
        btn_cancel.bind(on_release=popup.dismiss)
        btn_submit = Button(text="Save")
        btn_submit.bind(on_release=on_submit)

        btn_layout.add_widget(btn_cancel)
        btn_layout.add_widget(btn_submit)

        popup.open()

    def setup_session(self, filter_status=None):
        deck = self.data_manager.get_current_deck()
        if deck:
            # Reset session state
            self.current_index = 0
            self.history = []

            # Filter cards if needed
            if filter_status:
                self.card_indices = [i for i, card in enumerate(deck.cards) if card.status == filter_status]
            else:
                self.card_indices = list(range(len(deck.cards)))

            # Set initial card side based on show_question_side
            self.show_card_side = True

            # Start with the first card
            self.update_display()

    def update_display(self):
        deck = self.data_manager.get_current_deck()
        if not deck or not self.card_indices:
            self.manager.current = "deck"
            return

        if 0 <= self.current_index < len(self.card_indices):
            card_index = self.card_indices[self.current_index]
            card = deck.cards[card_index]

            # Update the progress label
            self.progress_label.text = f"Card {self.current_index + 1} of {len(self.card_indices)}"

            # If we're in flip_deck mode (show_question_side is False),
            # we show answer first, then question when flipped
            if not self.show_question_side:
                # When show_card_side is True, show answer
                # When show_card_side is False, show question
                side_text = card.answer if self.show_card_side else card.question
                side_name = "Answer" if self.show_card_side else "Question"
            else:
                # Normal mode: show question first, then answer
                side_text = card.question if self.show_card_side else card.answer
                side_name = "Question" if self.show_card_side else "Answer"

            self.card_display.text = f"[b]{side_name}:[/b]\n\n{side_text}"

    def mark_card(self, status):
        if 0 <= self.current_index < len(self.card_indices):
            card_index = self.card_indices[self.current_index]
            self.data_manager.update_card_status(card_index, status)

            # Add to history
            self.history.append((self.current_index, status))

            # Move to next card
            self.current_index += 1
            # Reset to show the initial side based on study mode
            self.show_card_side = True

            # Check if we've reached the end
            if self.current_index >= len(self.card_indices):
                self.show_summary()
            else:
                self.update_display()

    def go_back(self):
        if self.history:
            # Get the last card we marked
            prev_index, prev_status = self.history.pop()

            # Update current index
            self.current_index = prev_index

            # Reset its status to "unknown"
            card_index = self.card_indices[self.current_index]
            self.data_manager.update_card_status(card_index, "unknown")

            # Reset to show the initial side based on study mode
            self.show_card_side = True

            # Update display
            self.update_display()

    def flip_card(self):
        self.show_card_side = not self.show_card_side
        self.update_display()

    def show_summary(self):
        # Count statuses
        deck = self.data_manager.get_current_deck()
        know_count = sum(1 for c in deck.cards if c.status == "know")
        dont_know_count = sum(1 for c in deck.cards if c.status == "dont_know")
        unknown_count = sum(1 for c in deck.cards if c.status == "unknown")

        # Create content layout
        content_layout = BoxLayout(orientation="vertical", padding=10, spacing=10)
        content_layout.add_widget(Label(text="Study Session Complete!"))
        content_layout.add_widget(Label(text=f"Cards you know: {know_count}"))
        content_layout.add_widget(Label(text=f"Cards you don't know: {dont_know_count}"))
        content_layout.add_widget(Label(text=f"Uncategorized cards: {unknown_count}"))

        # Create button layout
        btn_layout = BoxLayout(size_hint_y=None, height=50, spacing=5)
        btn_ok = Button(text="Back to Deck")

        # Create popup
        popup = Popup(title="Summary", content=content_layout, size_hint=(0.8, 0.6))

        def on_ok(instance):
            popup.dismiss()
            self.manager.current = "deck"
            # Refresh deck screen
            deck_screen = self.manager.get_screen("deck")
            deck_screen.update_card_list()

        btn_ok.bind(on_release=on_ok)
        btn_layout.add_widget(btn_ok)
        content_layout.add_widget(btn_layout)

        popup.open()


# App Layout
class FlashcardApp(App):
    def build(self):
        # Request Android permissions if needed
        if platform == "android":
            from android.permissions import request_permissions, Permission

            request_permissions([Permission.READ_EXTERNAL_STORAGE, Permission.WRITE_EXTERNAL_STORAGE])

        # Initialize data manager
        self.data_manager = DataManager()

        # Create the screen manager
        sm = ScreenManager()

        # Add screens
        sm.add_widget(HomeScreen(name="home"))
        sm.add_widget(FolderScreen(name="folder"))
        sm.add_widget(DeckScreen(name="deck"))
        sm.add_widget(StudyScreen(name="study"))
        sm.add_widget(ImportCardsScreen(name="import"))

        # Bind keyboard events for study screen
        if platform != "android":  # Only bind keyboard on desktop
            Window.bind(on_key_down=self.on_key_down)

        return sm

    def on_key_down(self, window, key, *args):
        if self.root.current == "study":
            study_screen = self.root.get_screen("study")

            # Space key to flip card
            if key == 32:  # Space key
                study_screen.flip_card()
                return True

            # K key for "know"
            elif key == 107:  # 'k' key
                study_screen.mark_card("know")
                return True

            # D key for "don't know"
            elif key == 100:  # 'd' key
                study_screen.mark_card("dont_know")
                return True

            # B key to go back
            elif key == 98:  # 'b' key
                study_screen.go_back()
                return True

        return False

    def on_pause(self):
        # This is important for Android to prevent the app from being killed when paused
        return True

    def on_resume(self):
        # Handle app resume on Android
        pass


# Add kv file content
kv_content = """
<HomeScreen>:
    folder_list: folder_list
    BoxLayout:
        orientation: 'vertical'
        padding: 10
        spacing: 10
        Label:
            text: 'Flashcard App'
            font_size: '24sp'
            size_hint_y: None
            height: '50dp'

        ScrollView:
            do_scroll_x: False
            BoxLayout:
                id: folder_list
                orientation: 'vertical'
                size_hint_y: None
                height: self.minimum_height
                spacing: 5

        Button:
            text: 'Add New Folder'
            size_hint_y: None
            height: '50dp'
            on_release: root.add_new_folder()

<FolderScreen>:
    deck_list: deck_list
    folder_label: folder_label
    BoxLayout:
        orientation: 'vertical'
        padding: 10
        spacing: 10

        BoxLayout:
            size_hint_y: None
            height: '50dp'
            spacing: 5

            Button:
                text: 'Back'
                size_hint_x: 0.2
                on_release: root.go_back()

            Label:
                id: folder_label
                text: 'Folder: ' + root.folder_name
                font_size: '20sp'

        ScrollView:
            do_scroll_x: False
            BoxLayout:
                id: deck_list
                orientation: 'vertical'
                size_hint_y: None
                height: self.minimum_height
                spacing: 5

        BoxLayout:
            size_hint_y: None
            height: '50dp'
            spacing: 5

            Button:
                text: 'Add New Deck'
                on_release: root.add_new_deck()

            Button:
                text: 'Import to New Deck'
                on_release: root.import_cards_to_folder()

<DeckScreen>:
    card_list: card_list
    deck_label: deck_label
    BoxLayout:
        orientation: 'vertical'
        padding: 10
        spacing: 10

        BoxLayout:
            size_hint_y: None
            height: '50dp'
            spacing: 5

            Button:
                text: 'Back'
                size_hint_x: 0.2
                on_release: root.go_back()

            Label:
                id: deck_label
                text: 'Deck: ' + root.deck_name
                font_size: '20sp'

        BoxLayout:
            size_hint_y: None
            height: '30dp'
            spacing: 5

            Label:
                text: 'Status'
                size_hint_x: 0.2

            Label:
                text: 'Question'
                size_hint_x: 0.4

            Label:
                text: 'Answer'
                size_hint_x: 0.4

        ScrollView:
            do_scroll_x: False
            BoxLayout:
                id: card_list
                orientation: 'vertical'
                size_hint_y: None
                height: self.minimum_height
                spacing: 5

        BoxLayout:
            size_hint_y: None
            height: '50dp'
            spacing: 5

            Button:
                text: 'Add Card'
                on_release: root.add_new_card()

            Button:
                text: 'Import Cards'
                on_release: root.import_cards()

            Button:
                text: 'Bulk Reset'
                on_release: root.bulk_reset()

            Button:
                text: 'Mark All Known'
                on_release: root.bulk_know()

        BoxLayout:
            size_hint_y: None
            height: '50dp'
            spacing: 5

            Button:
                text: 'Study Deck'
                on_release: root.start_study_session()

            Button:
                text: "Study Don't Know Cards"
                on_release: root.study_dont_know()

            Button:
                text: 'Flip Deck (Answer First)'
                on_release: root.flip_deck()

<ImportCardsScreen>:
    file_chooser: file_chooser
    BoxLayout:
        orientation: 'vertical'
        padding: 10
        spacing: 10

        BoxLayout:
            size_hint_y: None
            height: '50dp'
            spacing: 5

            Button:
                text: 'Back'
                size_hint_x: 0.2
                on_release: root.go_back()

            Label:
                text: 'Import Cards'
                font_size: '20sp'

        ScrollView:
            do_scroll_x: False
            do_scroll_y: True
            bar_width: 10
            size_hint_y: 0.7
            FileChooserListView:
                id: file_chooser
                size_hint_y: 1

        BoxLayout:
            orientation: 'vertical'
            size_hint_y: 0.4
            spacing: 5

            Label:
                text: 'Separator Character:'
                size_hint_y: None
                height: '30dp'

            TextInput:
                id: separator_input
                text: ';'
                multiline: False
                size_hint_y: None
                height: '40dp'

            BoxLayout:
                orientation: 'horizontal'
                size_hint_y: None
                height: '40dp'

                CheckBox:
                    id: create_new_deck
                    active: False

                Label:
                    text: 'Create as new deck'

            TextInput:
                id: deck_name_input
                hint_text: 'New Deck Name (if creating new deck)'
                multiline: False
                size_hint_y: None
                height: '40dp'
                disabled: not create_new_deck.active

            Button:
                text: 'Import Cards'
                size_hint_y: None
                height: '50dp'
                on_release: root.import_cards(file_chooser.selection, separator_input.text, create_new_deck.active, deck_name_input.text)

<StudyScreen>:
    card_display: card_display
    progress_label: progress_label
    BoxLayout:
        orientation: 'vertical'
        padding: 20
        spacing: 10

        BoxLayout:
            size_hint_y: None
            height: '30dp'

            Label:
                id: progress_label
                text: 'Card 0 of 0'
                size_hint_x: 0.7

            Button:
                text: 'Exit'
                size_hint_x: 0.3
                on_release: root.show_summary()

        Label:
            id: card_display
            markup: True
            text: 'Card content will appear here'
            halign: 'center'
            valign: 'middle'
            text_size: self.width, None
            size_hint_y: 0.8

        BoxLayout:
            size_hint_y: None
            height: '50dp'
            spacing: 10

            Button:
                text: 'Flip Card (Space)'
                on_release: root.flip_card()

            Button:
                text: 'Go Back (B)'
                on_release: root.go_back()

        BoxLayout:
            size_hint_y: None
            height: '50dp'
            spacing: 10

            Button:
                text: 'Know (K)'
                on_release: root.mark_card('know')

            Button:
                text: "Don't Know (D)"
                on_release: root.mark_card('dont_know')

        BoxLayout:
            size_hint_y: None
            height: '50dp'
            spacing: 10

            Button:
                text: 'Edit Card'
                on_release: root.edit_current_card()

        Label:
            size_hint_y: None
            height: '30dp'
            text: 'Shortcuts: Space to flip, K for Know, D for Don\\'t Know, B to go back'
            font_size: '12sp'
"""

# Run the app
if __name__ == "__main__":
    from kivy.lang import Builder

    Builder.load_string(kv_content)
    FlashcardApp().run()
