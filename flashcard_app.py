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
from kivy.properties import ObjectProperty, StringProperty, BooleanProperty
from kivy.uix.checkbox import CheckBox  # noqa: F401 - Used in kv file
import json
import os
import re
from kivy.utils import platform
from kivy.clock import mainthread

# Android Helpers
if platform == "android":
    from jnius import autoclass, cast
    from android import activity

    def android_get_file_from_content_uri(content_uri):
        """
        Copies a file from a content URI (content://...) to a local file in the app's private storage.
        This bypasses issues with direct file access and 'msf:' style IDs on newer Androids.
        """
        try:
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            Context = autoclass("android.content.Context")
            current_activity = cast("android.app.Activity", PythonActivity.mActivity)
            content_resolver = current_activity.getContentResolver()

            # Open input stream
            input_stream = content_resolver.openInputStream(content_uri)
            if not input_stream:
                return None

            # Try to get the filename
            file_name = "imported_file"
            cursor = content_resolver.query(content_uri, None, None, None, None)
            if cursor:
                if cursor.moveToFirst():
                    idx = cursor.getColumnIndex("_display_name")
                    if idx != -1:
                        file_name = cursor.getString(idx)
                cursor.close()

            # Ensure safe filename
            file_name = os.path.basename(file_name)

            # Define destination path in app's private storage
            app_root = App.get_running_app().user_data_dir
            dest_path = os.path.join(app_root, file_name)

            # Copy data
            output_stream = open(dest_path, "wb")
            buffer_size = 4096
            buffer = bytearray(buffer_size)

            while True:
                bytes_read = input_stream.read(buffer)
                if bytes_read == -1:
                    break
                output_stream.write(buffer[:bytes_read])

            output_stream.close()
            input_stream.close()

            return dest_path
        except Exception as e:
            print(f"Error resolving Android URI: {e}")
            return None

    class AndroidFilePicker:
        """
        Custom file picker to replace plyer which crashes on some Samsung/Android 11+ devices
        due to NumberFormatException in URI parsing.
        """

        def __init__(self, callback):
            self.callback = callback
            self.RESULT_CODE = 12345
            activity.bind(on_activity_result=self.on_activity_result)

        def open_picker(self):
            Intent = autoclass("android.content.Intent")
            intent = Intent(Intent.ACTION_GET_CONTENT)
            intent.setType("*/*")
            intent.addCategory(Intent.CATEGORY_OPENABLE)

            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            current_activity = cast("android.app.Activity", PythonActivity.mActivity)
            current_activity.startActivityForResult(intent, self.RESULT_CODE)

        def on_activity_result(self, request_code, result_code, intent):
            if request_code == self.RESULT_CODE:
                activity.unbind(on_activity_result=self.on_activity_result)
                if result_code == -1:  # Activity.RESULT_OK
                    uri = intent.getData()
                    if uri:
                        file_path = android_get_file_from_content_uri(uri)
                        if file_path:
                            self.callback([file_path])
                        else:
                            self.callback([])  # Failed to resolve
                    else:
                        self.callback([])
                else:
                    self.callback([])  # Cancelled
                return True
            return False


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
            # Use app-specific storage (works with scoped storage on Android 11+)
            # This doesn't require any storage permissions
            from kivy.app import App

            data_dir = App.get_running_app().user_data_dir
        else:
            data_dir = os.path.expanduser("~/.flashcardapp")

        os.makedirs(data_dir, exist_ok=True)
        return os.path.join(data_dir, "flashcards.json")

    def load_data(self):
        try:
            with open(self.get_data_path(), "r") as f:
                data = json.load(f)
                # Check if data is a dict (new format with settings) or list (old format)
                if isinstance(data, dict):
                    self.folders = []
                    for folder_data in data.get("folders", []):
                        self.folders.append(Folder.from_dict(folder_data))
                    self.card_font_size = data.get("card_font_size", 28)
                else:
                    # Old format: data is just a list of folders
                    self.folders = []
                    for folder_data in data:
                        self.folders.append(Folder.from_dict(folder_data))
                    self.card_font_size = 28
        except (FileNotFoundError, json.JSONDecodeError):
            # Create a default folder and deck if no data exists
            default_folder = Folder("Default Folder")
            default_deck = Deck("Default Deck")
            default_folder.add_deck(default_deck)
            self.folders = [default_folder]
            self.card_font_size = 28
            self.save_data()

    def save_data(self):
        with open(self.get_data_path(), "w") as f:
            data = {"folders": [folder.to_dict() for folder in self.folders], "card_font_size": self.card_font_size}
            json.dump(data, f, indent=2)

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

    def export_deck_to_json(self, folder_index, deck_index, filename):
        """Export a deck to a JSON file."""
        if 0 <= folder_index < len(self.folders) and 0 <= deck_index < len(self.folders[folder_index].decks):
            deck = self.folders[folder_index].decks[deck_index]
            data = deck.to_dict()

            # Determine export path
            if platform == "android":
                # Save to Downloads folder on Android
                export_dir = "/storage/emulated/0/Download"
            else:
                export_dir = os.path.join(os.path.expanduser("~"), "Documents", "FlashcardsExports")

            os.makedirs(export_dir, exist_ok=True)

            if not filename.endswith(".json"):
                filename += ".json"

            file_path = os.path.join(export_dir, filename)

            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                return file_path
            except Exception as e:
                print(f"Export error: {str(e)}")
                return None
        return None

    def import_deck_from_json(self, folder_index, file_path, as_new_deck=True, deck_name=None):
        """Import a deck from a JSON file."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Validate JSON structure
            if "cards" not in data:
                return -1

            if as_new_deck:
                # Use provided name or name from JSON
                name = deck_name if deck_name else data.get("name", "Imported Deck")
                deck = Deck(name)
                for card_data in data["cards"]:
                    deck.add_card(Card.from_dict(card_data))

                if 0 <= folder_index < len(self.folders):
                    self.folders[folder_index].add_deck(deck)
                    self.save_data()
                    return len(deck.cards)
            else:
                # Import into current deck (which implies we need deck_index or get current)
                # But this method signature takes folder_index.
                # For simplicity, if not as_new_deck, we assume the caller handles merging or we need deck_index.
                # Let's adjust the signature or logic.
                pass
            return -1
        except Exception as e:
            print(f"Import JSON error: {str(e)}")
            return -1

    def import_json_to_deck(self, folder_index, deck_index, file_path):
        """Import cards from JSON into an existing deck."""
        if 0 <= folder_index < len(self.folders) and 0 <= deck_index < len(self.folders[folder_index].decks):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                if "cards" in data:
                    deck = self.folders[folder_index].decks[deck_index]
                    count = 0
                    for card_data in data["cards"]:
                        deck.add_card(Card.from_dict(card_data))
                        count += 1
                    self.save_data()
                    return count
            except Exception as e:
                print(f"Import JSON to deck error: {str(e)}")
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

    def open_settings(self):
        content = BoxLayout(orientation="vertical", padding=10, spacing=10)

        # Font size setting
        font_size_layout = BoxLayout(orientation="horizontal", size_hint_y=None, height=50, spacing=10)
        font_size_layout.add_widget(Label(text="Card Font Size:", size_hint_x=0.5))

        font_size_input = TextInput(
            text=str(self.data_manager.card_font_size), multiline=False, input_filter="int", size_hint_x=0.3
        )
        font_size_layout.add_widget(font_size_input)
        font_size_layout.add_widget(Label(text="sp", size_hint_x=0.2))

        content.add_widget(Label(text="Settings", size_hint_y=None, height=30))
        content.add_widget(font_size_layout)

        # Buttons
        btn_layout = BoxLayout(size_hint_y=None, height=50, spacing=5)

        popup = Popup(title="Settings", content=content, size_hint=(0.8, 0.4))

        def on_save(instance):
            try:
                new_size = int(font_size_input.text)
                if 12 <= new_size <= 72:  # Reasonable limits
                    self.data_manager.card_font_size = new_size
                    self.data_manager.save_data()
                    popup.dismiss()
                else:
                    error_popup = Popup(
                        title="Error", content=Label(text="Font size must be between 12 and 72"), size_hint=(0.7, 0.3)
                    )
                    error_popup.open()
            except ValueError:
                error_popup = Popup(
                    title="Error", content=Label(text="Please enter a valid number"), size_hint=(0.7, 0.3)
                )
                error_popup.open()

        btn_cancel = Button(text="Cancel")
        btn_cancel.bind(on_release=popup.dismiss)
        btn_save = Button(text="Save")
        btn_save.bind(on_release=on_save)

        btn_layout.add_widget(btn_cancel)
        btn_layout.add_widget(btn_save)
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
        sep_label = Label(text="Enter separator character:", size_hint_y=None, height="30dp")

        # Container to hold selected file path (list to allow modification in closure)
        selected_file_holder = [None]
        file_chooser = None  # Will be used only on desktop

        def update_ui_for_file(filepath):
            if not filepath:
                return
            is_json = filepath.lower().endswith(".json")

            # Show/hide separator inputs based on file type
            if is_json:
                sep_label.height = 0
                sep_label.opacity = 0
                sep_input.height = 0
                sep_input.opacity = 0
                sep_input.disabled = True
            else:
                sep_label.height = 30  # 30dp
                sep_label.opacity = 1
                sep_input.height = 40  # 40dp (default TextInput height)
                sep_input.opacity = 1
                sep_input.disabled = False

        if platform == "android":
            # Android: Use native file picker
            file_label = Label(text="No file selected", size_hint_y=None, height="40dp")

            def on_android_selection(selection):
                if selection:
                    selected_file_holder[0] = selection[0]

                    # Update UI on main thread
                    @mainthread
                    def update_label():
                        try:
                            filepath = selection[0]
                            file_label.text = f"Selected: {os.path.basename(filepath)}"
                            update_ui_for_file(filepath)
                        except Exception:
                            file_label.text = "File selected"

                    update_label()

            def open_picker(instance):
                try:
                    # Use custom AndroidFilePicker instead of plyer
                    # We define the picker instance here
                    picker = AndroidFilePicker(on_android_selection)
                    picker.open_picker()
                    # Keep reference to prevent GC until callback
                    instance.picker_ref = picker
                except Exception as e:
                    file_label.text = "Error opening file picker"
                    print(f"Error: {e}")

            btn_select = Button(text="Select File", size_hint_y=None, height="50dp")
            btn_select.bind(on_release=open_picker)

            content.add_widget(Label(text="Select a text/JSON file:", size_hint_y=None, height="30dp"))
            content.add_widget(btn_select)
            content.add_widget(file_label)
        else:
            # Desktop: Use FileChooserListView
            file_chooser = FileChooserListView(path=os.path.expanduser("~"), filters=["*.txt", "*.json", "*"])
            content.add_widget(Label(text="Select a text file to import:"))
            content.add_widget(file_chooser)

            # Bind desktop selection
            def on_desktop_selection(instance, selection):
                if selection:
                    update_ui_for_file(selection[0])

            file_chooser.bind(selection=on_desktop_selection)

        content.add_widget(sep_label)
        content.add_widget(sep_input)
        content.add_widget(Label(text="Enter deck name:", size_hint_y=None, height="30dp"))
        content.add_widget(txt_input)

        btn_layout = BoxLayout(size_hint_y=None, height=50, spacing=5)

        popup = Popup(title="Import Cards to New Deck", content=content, size_hint=(0.9, 0.9))

        def on_submit(instance):
            file_path = None
            if platform == "android":
                file_path = selected_file_holder[0]
            elif file_chooser and file_chooser.selection:
                file_path = file_chooser.selection[0]

            if not file_path:
                return

            if not txt_input.text.strip():
                return

            separator = sep_input.text.strip() or ";"

            imported = self.data_manager.import_cards_as_new_deck(
                self.folder_index, txt_input.text.strip(), file_path, separator
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
    is_android = BooleanProperty(platform == "android")
    is_json_selected = BooleanProperty(False)

    def __init__(self, **kwargs):
        super(ImportCardsScreen, self).__init__(**kwargs)
        self.data_manager = App.get_running_app().data_manager
        self.selected_file_path = None

    def on_enter(self):
        # Reset selection
        self.selected_file_path = None
        self.is_json_selected = False

        # Set default path based on platform
        if not self.is_android:
            # On desktop, start at user's home directory
            if self.file_chooser:
                self.file_chooser.path = os.path.expanduser("~")
        else:
            # On Android, update UI to show file selection status
            if hasattr(self, "ids") and "selected_file_label" in self.ids:
                self.ids.selected_file_label.text = "No file selected - Tap 'Select File' button"

    def on_desktop_selection(self, selection):
        """Handle desktop file selection change"""
        if selection:
            self.is_json_selected = selection[0].lower().endswith(".json")
        else:
            self.is_json_selected = False

    def open_file_picker_android(self):
        """Open native Android file picker"""
        try:
            # Use custom AndroidFilePicker instead of plyer
            self.android_picker = AndroidFilePicker(self.handle_android_selection)
            self.android_picker.open_picker()
        except Exception as e:
            self.show_error(f"Error opening file picker: {str(e)}")

    @mainthread
    def handle_android_selection(self, selection):
        """Handle file selection from Android native picker"""
        if not selection:
            # Debugging: let user know if we got an empty selection
            self.show_error("File picker returned no selection. Try picking a file from internal storage.")
            return

        if selection:
            # plyer returns a list of paths
            self.selected_file_path = selection[0]

            # Check if it is a JSON file
            self.is_json_selected = self.selected_file_path.lower().endswith(".json")

            # Update the label to show selected file
            try:
                filename = os.path.basename(self.selected_file_path)
                if hasattr(self, "ids") and "selected_file_label" in self.ids:
                    self.ids.selected_file_label.text = f"Selected: {filename}"
            except Exception as e:
                self.show_error(f"Error processing file selection: {str(e)}")

    def import_cards(self, file_path, separator, create_new_deck, deck_name):
        # On Android, use the selected file from native picker
        if platform == "android":
            if not self.selected_file_path:
                self.show_error("Please select a file first.")
                return
            selected_file = self.selected_file_path
        else:
            # On desktop, use file_chooser selection
            if not file_path:
                self.show_error("Please select a file.")
                return
            selected_file = file_path[0]

        is_json = selected_file.lower().endswith(".json")

        if create_new_deck and not deck_name.strip() and not is_json:
            self.show_error("Please enter a deck name.")
            return

        try:
            imported = 0
            if is_json:
                if create_new_deck:
                    imported = self.data_manager.import_deck_from_json(
                        self.folder_index, selected_file, as_new_deck=True, deck_name=deck_name.strip()
                    )
                else:
                    imported = self.data_manager.import_json_to_deck(self.folder_index, self.deck_index, selected_file)
            else:
                if create_new_deck:
                    imported = self.data_manager.import_cards_as_new_deck(
                        self.folder_index, deck_name.strip(), selected_file, separator
                    )
                else:
                    imported = self.data_manager.import_cards_from_file(
                        self.folder_index, self.deck_index, selected_file, separator
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

    def export_deck(self):
        content = BoxLayout(orientation="vertical", padding=10, spacing=10)
        # Suggest filename based on deck name, sanitized
        safe_name = re.sub(r"[^\w\-_\. ]", "_", self.deck_name)
        txt_input = TextInput(hint_text="Filename", multiline=False, text=safe_name)
        btn_layout = BoxLayout(size_hint_y=None, height=50, spacing=5)

        popup = Popup(title="Export Deck", content=content, size_hint=(0.8, 0.45))

        def on_submit(instance):
            if txt_input.text.strip():
                filename = txt_input.text.strip()
                path = self.data_manager.export_deck_to_json(self.folder_index, self.deck_index, filename)
                popup.dismiss()

                if path:
                    # Show path in a copy-friendly way or just a message
                    msg = f"Exported to:\n{path}"
                    success = Popup(title="Success", content=Label(text=msg, halign="center"), size_hint=(0.9, 0.4))
                    success.open()
                else:
                    error = Popup(title="Error", content=Label(text="Export failed."), size_hint=(0.7, 0.3))
                    error.open()

        btn_cancel = Button(text="Cancel")
        btn_cancel.bind(on_release=popup.dismiss)
        btn_submit = Button(text="Export")
        btn_submit.bind(on_release=on_submit)

        btn_layout.add_widget(btn_cancel)
        btn_layout.add_widget(btn_submit)

        content.add_widget(Label(text="Enter filename for export (JSON):", size_hint_y=None, height=30))
        content.add_widget(txt_input)
        content.add_widget(btn_layout)

        popup.open()


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

    def on_touch_down(self, touch):
        # Allow buttons and other controls to handle touch first
        if super().on_touch_down(touch):
            return True

        # Check if touch is within card_display bounds
        if self.card_display and self.card_display.collide_point(*touch.pos):
            # Calculate relative position
            width = self.card_display.width
            if width <= 0:
                return False

            relative_x = touch.x - self.card_display.x
            pct = relative_x / width

            # Define zones:
            # Left 30%: Don't Know
            # Middle 40%: Flip
            # Right 30%: Know
            if pct < 0.3:
                # Left side - Don't Know
                self.mark_card("dont_know")
            elif pct > 0.7:
                # Right side - Know
                self.mark_card("know")
            else:
                # Middle - Flip
                self.flip_card()

            return True

        return False

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

            # Update font size from settings
            self.card_display.font_size = f"{self.data_manager.card_font_size}sp"

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

    def increase_font_size(self):
        if self.data_manager.card_font_size < 72:
            self.data_manager.card_font_size += 2
            self.data_manager.save_data()
            self.update_display()

    def decrease_font_size(self):
        if self.data_manager.card_font_size > 12:
            self.data_manager.card_font_size -= 2
            self.data_manager.save_data()
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
        # Load the KV layout before building the UI
        from kivy.lang import Builder

        Builder.load_string(kv_content)

        # Window.size = (1600, 1400)  # DISABLED: Causes threading/mutex crash on Android
        # Fixed window size only works on desktop, on Android it causes rendering issues
        if platform != "android":
            Window.size = (1600, 1400)  # Only set window size on desktop

        # Request READ_EXTERNAL_STORAGE permission for file import functionality
        if platform == "android":
            from android.permissions import request_permissions, Permission

            # Only request READ (not WRITE) - write operations use app-specific storage
            request_permissions([Permission.READ_EXTERNAL_STORAGE])

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
# Platform-specific button text
if platform == "android":
    btn_flip = "Flip Card"
    btn_go_back = "Go Back"
    btn_know = "Know"
    btn_dont_know = "Don't Know"
    btn_study_dont_know = "Study Don't Know"
    btn_flip_deck = "Flip Deck"
    hint_text = "Tap center to flip, left for Don't Know, right for Know"
else:
    btn_flip = "Flip Card (Space)"
    btn_go_back = "Go Back (B)"
    btn_know = "Know (K)"
    btn_dont_know = "Don't Know (D)"
    btn_study_dont_know = "Study Don't Know Cards"
    btn_flip_deck = "Flip Deck (Answer First)"
    hint_text = "Shortcuts: Space to flip, K for Know, D for Don't Know, B to go back"

kv_content = f"""
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

        BoxLayout:
            size_hint_y: None
            height: '50dp'
            spacing: 5

            Button:
                text: 'Add New Folder'
                on_release: root.add_new_folder()

            Button:
                text: 'Settings'
                size_hint_x: 0.4
                on_release: root.open_settings()

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
                text: 'Export Deck'
                on_release: root.export_deck()

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
                text: "{btn_study_dont_know}"
                on_release: root.study_dont_know()

            Button:
                text: "{btn_flip_deck}"
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

        BoxLayout:
            orientation: 'vertical'
            size_hint_y: 0.7
            spacing: 5
            
            # Android: Show file picker button
            Button:
                text: 'Select File'
                size_hint_y: None
                height: '60dp' if root.is_android else 0
                opacity: 1 if root.is_android else 0
                disabled: not root.is_android
                on_release: root.open_file_picker_android() if root.is_android else None
            
            Label:
                id: selected_file_label
                text: 'No file selected'
                size_hint_y: None
                height: '40dp' if root.is_android else 0
                opacity: 1 if root.is_android else 0
            
                # Desktop: Show file chooser in ScrollView
            ScrollView:
                do_scroll_x: False
                do_scroll_y: True
                bar_width: 10
                size_hint_y: 1 if not root.is_android else 0
                opacity: 1 if not root.is_android else 0
                
                FileChooserListView:
                    id: file_chooser
                    size_hint_y: None
                    height: 400
                    dirselect: False
                    filters: ['*.txt', '*.json', '*']
                    on_selection: root.on_desktop_selection(self.selection)

        BoxLayout:
            orientation: 'vertical'
            size_hint_y: 0.4
            spacing: 5

            # Separator input - only visible if NOT a JSON file
            Label:
                text: 'Separator Character:'
                size_hint_y: None
                height: '30dp' if not root.is_json_selected else 0
                opacity: 1 if not root.is_json_selected else 0
                disabled: root.is_json_selected

            TextInput:
                id: separator_input
                text: ';'
                multiline: False
                size_hint_y: None
                height: '40dp' if not root.is_json_selected else 0
                opacity: 1 if not root.is_json_selected else 0
                disabled: root.is_json_selected
            
            # JSON Info label - only visible if JSON IS selected
            Label:
                text: 'JSON Deck Import Selected'
                color: 0, 1, 0, 1  # Green color
                size_hint_y: None
                height: '30dp' if root.is_json_selected else 0
                opacity: 1 if root.is_json_selected else 0

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
                size_hint_x: 0.5

            Button:
                text: 'A-'
                size_hint_x: 0.15
                on_release: root.decrease_font_size()

            Button:
                text: 'A+'
                size_hint_x: 0.15
                on_release: root.increase_font_size()

            Button:
                text: 'Exit'
                size_hint_x: 0.2
                on_release: root.show_summary()

        Label:
            id: card_display
            markup: True
            text: 'Card content will appear here'
            halign: 'center'
            valign: 'middle'
            text_size: self.width, None
            size_hint_y: 0.8
            font_size: '28sp'

        BoxLayout:
            size_hint_y: None
            height: '50dp'
            spacing: 10

            Button:
                text: "{btn_flip}"
                on_release: root.flip_card()

            Button:
                text: "{btn_go_back}"
                on_release: root.go_back()

        BoxLayout:
            size_hint_y: None
            height: '50dp'
            spacing: 10

            Button:
                text: "{btn_know}"
                on_release: root.mark_card('know')

            Button:
                text: "{btn_dont_know}"
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
            text: "{hint_text}"
            font_size: '12sp'
"""

# Run the app
if __name__ == "__main__":
    FlashcardApp().run()
