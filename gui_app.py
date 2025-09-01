# gui_app.py
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import shutil
import json
from datetime import datetime

import navidrome_api

try:
    from thefuzz import fuzz
except ImportError:
    messagebox.showerror("Dependency Missing", "The 'thefuzz' library is required.\n\nPlease install it by running:\npip install thefuzz python-Levenshtein")
    exit()

class SettingsWindow(tk.Toplevel):
    # This class is unchanged and correct
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("Settings")
        self.geometry("600x250")
        self.transient(parent)
        self.grab_set()
        
        self.url, self.user, self.pwd, self.local_path, self.navi_path = (
            tk.StringVar(value=parent.config.get('navidrome_url')),
            tk.StringVar(value=parent.config.get('navidrome_user')),
            tk.StringVar(value=parent.config.get('navidrome_password')),
            tk.StringVar(value=parent.config.get('local_playlists_path')),
            tk.StringVar(value=parent.config.get('navidrome_playlists_path'))
        )
        frame = ttk.Frame(self, padding="10")
        frame.pack(fill=tk.BOTH, expand=True)
        ttk.Label(frame, text="Navidrome URL:").grid(row=0, column=0, sticky=tk.W, pady=2)
        ttk.Entry(frame, textvariable=self.url).grid(row=0, column=1, columnspan=2, sticky=tk.EW)
        ttk.Label(frame, text="Navidrome User:").grid(row=1, column=0, sticky=tk.W, pady=2)
        ttk.Entry(frame, textvariable=self.user).grid(row=1, column=1, columnspan=2, sticky=tk.EW)
        ttk.Label(frame, text="Navidrome Password:").grid(row=2, column=0, sticky=tk.W, pady=2)
        ttk.Entry(frame, textvariable=self.pwd, show="*").grid(row=2, column=1, columnspan=2, sticky=tk.EW)
        ttk.Label(frame, text="Local Playlists Folder:").grid(row=3, column=0, sticky=tk.W, pady=5)
        ttk.Entry(frame, textvariable=self.local_path).grid(row=3, column=1, sticky=tk.EW)
        ttk.Button(frame, text="...", command=lambda: self.browse_folder(self.local_path), width=3).grid(row=3, column=2)
        ttk.Label(frame, text="Navidrome Cache Folder:").grid(row=4, column=0, sticky=tk.W, pady=2)
        ttk.Entry(frame, textvariable=self.navi_path).grid(row=4, column=1, sticky=tk.EW)
        ttk.Button(frame, text="...", command=lambda: self.browse_folder(self.navi_path), width=3).grid(row=4, column=2)
        frame.columnconfigure(1, weight=1)
        button_frame = ttk.Frame(self, padding="10")
        button_frame.pack(fill=tk.X)
        ttk.Button(button_frame, text="Save & Close", command=self.save_settings).pack(side=tk.RIGHT)
        ttk.Button(button_frame, text="Test Connection", command=self.test_connection).pack(side=tk.LEFT)

    def browse_folder(self, path_var):
        folder = filedialog.askdirectory()
        if folder: path_var.set(folder)

    def test_connection(self):
        config = {'navidrome_url': self.url.get(), 'navidrome_user': self.user.get(), 'navidrome_password': self.pwd.get()}
        success, message = navidrome_api.verify_connection(config)
        messagebox.showinfo("Connection Test", message)

    def save_settings(self):
        config = {'navidrome_url': self.url.get(), 'navidrome_user': self.user.get(), 'navidrome_password': self.pwd.get(),
                  'local_playlists_path': self.local_path.get(), 'navidrome_playlists_path': self.navi_path.get()}
        navidrome_api.save_config(config)
        self.parent.config = config
        self.parent.song_cache = None
        self.parent.last_check_results = {}
        self.parent.refresh_all_playlists()
        self.destroy()

class PlaylistToolApp(tk.Tk):
    CACHE_FILE = "song_cache.json"

    def __init__(self):
        super().__init__()
        self.title("Navidrome Playlist Tool")
        self.geometry("1400x800")

        self.config = navidrome_api.load_config()
        self.last_check_results = {}
        self.last_search_results = []
        self.song_cache = self._load_song_cache()
        self.protocol("WM_DELETE_WINDOW", self._on_closing)

        top_frame = ttk.Frame(self, padding="5")
        top_frame.pack(fill=tk.X)
        search_controls_frame = ttk.Frame(top_frame)
        search_controls_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        ttk.Button(search_controls_frame, text="⚙️ Settings", command=self.open_settings).pack(side=tk.LEFT)
        self.search_entry = ttk.Entry(search_controls_frame)
        self.search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=20)
        self.search_entry.bind("<Return>", self.on_search_click)
        ttk.Button(search_controls_frame, text="Search", command=self.on_search_click).pack(side=tk.LEFT, padx=(0,2))
        ttk.Button(search_controls_frame, text="Replace", command=self.on_replace_click).pack(side=tk.LEFT)
        self.search_results_frame = self._create_listbox_frame(top_frame, "Search Results")
        self.search_results_listbox = self._add_listbox(self.search_results_frame, single_selection=True)
        self.search_results_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        main_paned_window = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        main_paned_window.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        navidrome_pane = ttk.PanedWindow(main_paned_window, orient=tk.HORIZONTAL)
        main_paned_window.add(navidrome_pane, weight=1)
        navi_playlist_frame = self._create_listbox_frame(navidrome_pane, "Playlists (Navidrome Cache)")
        self.navi_playlists_listbox = self._add_listbox(navi_playlist_frame)
        self.navi_playlists_listbox.bind("<<ListboxSelect>>", self.on_playlist_select)
        ttk.Button(navi_playlist_frame, text="Refresh Cache", command=self.on_refresh_cache_click).pack(side=tk.BOTTOM, fill=tk.X, pady=(2,0))
        ttk.Button(navi_playlist_frame, text="Upload Selected", command=self.on_upload_click).pack(side=tk.BOTTOM, fill=tk.X, pady=(2,0))
        ttk.Button(navi_playlist_frame, text="Sync from Server", command=self.sync_navidrome_playlists).pack(side=tk.BOTTOM, fill=tk.X, pady=(5,0))
        navidrome_pane.add(navi_playlist_frame, weight=1)
        self.navi_tracks_frame = self._create_listbox_frame(navidrome_pane, "Tracks (Navidrome)")
        self.navi_tracks_listbox = self._add_listbox(self.navi_tracks_frame)
        navidrome_pane.add(self.navi_tracks_frame, weight=2)
        local_pane = ttk.PanedWindow(main_paned_window, orient=tk.HORIZONTAL)
        main_paned_window.add(local_pane, weight=1)
        self.local_tracks_frame = self._create_listbox_frame(local_pane, "Tracks (Local)")
        self.local_tracks_listbox = self._add_listbox(self.local_tracks_frame)
        self.local_tracks_listbox.bind("<Shift-Button-1>", self.on_toggle_suggestion_click)
        local_pane.add(self.local_tracks_frame, weight=2)
        local_playlist_frame = self._create_listbox_frame(local_pane, "Playlists (Local)")
        self.local_playlists_listbox = self._add_listbox(local_playlist_frame)
        self.local_playlists_listbox.bind("<<ListboxSelect>>", self.on_playlist_select)
        ttk.Button(local_playlist_frame, text="Refresh Folder", command=self.refresh_all_playlists).pack(side=tk.BOTTOM, fill=tk.X, pady=(5,0))
        local_pane.add(local_playlist_frame, weight=1)
        
        bottom_frame = ttk.Frame(self, padding="5")
        bottom_frame.pack(fill=tk.X, side=tk.BOTTOM)
        left_button_frame = ttk.Frame(bottom_frame)
        left_button_frame.pack(side=tk.LEFT)
        ttk.Button(left_button_frame, text="Export Report", command=self.on_export_report_click).pack(side=tk.LEFT, padx=(5,0))
        ttk.Button(left_button_frame, text="Add", command=self.on_add_click).pack(side=tk.LEFT, padx=5)
        ttk.Button(left_button_frame, text="Delete", command=self.on_delete_click).pack(side=tk.LEFT, padx=0)
        ttk.Button(left_button_frame, text="Clear", command=self.on_clear_click).pack(side=tk.LEFT, padx=5)
        middle_button_frame = ttk.Frame(bottom_frame)
        middle_button_frame.pack(side=tk.LEFT, expand=True)
        ttk.Button(middle_button_frame, text="< Merge", command=lambda: self.on_merge_click('left')).pack(side=tk.LEFT, padx=2)
        ttk.Button(middle_button_frame, text="< Merge >", command=lambda: self.on_merge_click('new')).pack(side=tk.LEFT, padx=2)
        ttk.Button(middle_button_frame, text="Merge >", command=lambda: self.on_merge_click('right')).pack(side=tk.LEFT, padx=2)
        right_button_frame = ttk.Frame(bottom_frame)
        right_button_frame.pack(side=tk.RIGHT)
        ttk.Button(right_button_frame, text="Check", command=self.on_check_click).pack(side=tk.LEFT, padx=0)
        ttk.Button(right_button_frame, text="Check All", command=self.on_check_all_click).pack(side=tk.LEFT, padx=5)
        ttk.Button(right_button_frame, text="Accept", command=self.on_accept_click).pack(side=tk.LEFT, padx=0)
        ttk.Button(right_button_frame, text="Accept All", command=self.on_accept_all_click).pack(side=tk.LEFT, padx=5)
        ttk.Button(right_button_frame, text="Save", command=self.on_save_click).pack(side=tk.LEFT, padx=0)
        ttk.Button(right_button_frame, text="Save All", command=self.on_save_all_click).pack(side=tk.LEFT, padx=5)
        
        self._link_listbox_events()
        self.refresh_all_playlists()
        if not self.config.get('navidrome_url'): messagebox.showinfo("Welcome", "Please configure your Navidrome server via the '⚙️ Settings' button.")

    def _create_listbox_frame(self, parent, title):
        frame = ttk.Frame(parent, padding=5)
        label = ttk.Label(frame, text=title)
        label.pack(fill=tk.X)
        frame.label = label
        return frame

    def _add_listbox(self, parent_frame, single_selection=False):
        listbox_frame = ttk.Frame(parent_frame)
        listbox_frame.pack(fill=tk.BOTH, expand=True, pady=(5,0))
        select_mode = tk.SINGLE if single_selection else tk.BROWSE
        listbox = tk.Listbox(listbox_frame, selectbackground="#0078D7", selectforeground="white", exportselection=False, selectmode=select_mode)
        scrollbar = ttk.Scrollbar(listbox_frame, orient=tk.VERTICAL, command=listbox.yview)
        listbox['yscrollcommand'] = scrollbar.set
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        return listbox

    def _link_listbox_events(self):
        listboxes = [self.navi_tracks_listbox, self.local_tracks_listbox]
        def sync_scroll(*args):
            for lb in listboxes: lb.yview(*args)
        def sync_mousewheel(event):
            for lb in listboxes: lb.yview_scroll(int(-1*(event.delta/120)), "units")
            return "break"
        def sync_selection(event):
            widget = event.widget
            if not widget.curselection(): return
            selected_index = widget.curselection()[0]
            for lb in listboxes:
                if lb is not widget:
                    lb.selection_clear(0, tk.END)
                    lb.selection_set(selected_index)
                    lb.activate(selected_index)
                    lb.see(selected_index)
        for lb in listboxes:
            scrollbar = lb.master.winfo_children()[1] 
            scrollbar.config(command=sync_scroll)
            lb.config(yscrollcommand=scrollbar.set)
            lb.bind("<MouseWheel>", sync_mousewheel)
            lb.bind("<<ListboxSelect>>", sync_selection)

    def _load_song_cache(self):
        try:
            with open(self.CACHE_FILE, 'r', encoding='utf-8') as f: return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError): return None

    def _save_song_cache(self):
        if self.song_cache:
            try:
                with open(self.CACHE_FILE, 'w', encoding='utf-8') as f: json.dump(self.song_cache, f)
            except Exception: pass
    
    def _on_closing(self):
        self._save_song_cache()
        self.destroy()

    def _ensure_song_cache_exists(self, force_refresh=False):
        if self.song_cache is None or force_refresh:
            if not self.config.get('navidrome_url'):
                messagebox.showerror("Error", "Please configure Navidrome in Settings first.")
                return False
            status_label = self.local_tracks_frame.label
            original_text = status_label.cget("text")
            status_label.config(text="Building server song cache (this may take a moment)...")
            self.update_idletasks()
            self.song_cache = navidrome_api.get_all_songs_cache(self.config)
            status_label.config(text=original_text)
            if self.song_cache is None or not self.song_cache:
                messagebox.showerror("Error", "Could not build song cache. Check connection/permissions.")
                self.song_cache = None
                return False
        return True

    def _write_m3u_file(self, filepath, tracks):
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write("#EXTM3U\n")
                for track in tracks:
                    if track and track.get('path'): f.write(f"{track['path']}\n")
            return True, ""
        except Exception as e:
            return False, str(e)

    def _display_check_results(self, playlist_name, results):
        self.local_tracks_listbox.delete(0, tk.END)
        self.navi_tracks_listbox.delete(0, tk.END)
        for i, item in enumerate(results):
            track = item['original_track']
            prefix = f"[{item['status'].upper()}]"
            score = f"({item['score']:.0f}%)" if item['status'] != 'missing' else ""
            local_display_text = f"{prefix} {track['artist']} - {track['title']} {score}"
            self.local_tracks_listbox.insert(tk.END, local_display_text)
            color = {'ok': 'blue', 'found': 'green', 'suggestion': 'orange', 'missing': 'red'}.get(item['status'], 'black')
            self.local_tracks_listbox.itemconfig(i, {'fg': color})
            if item['navidrome_song']:
                navi_display_text = f"{item['navidrome_song']['artist']} - {item['navidrome_song']['title']}"
                self.navi_tracks_listbox.insert(tk.END, navi_display_text)
            else:
                self.navi_tracks_listbox.insert(tk.END, "")
        self.local_tracks_frame.label.config(text=f"Check Results for '{playlist_name}'")
        self.navi_tracks_frame.label.config(text=f"Matched/Suggested Navidrome Tracks")

    def open_settings(self): SettingsWindow(self)

    def refresh_all_playlists(self):
        self.populate_playlist_listbox(self.local_playlists_listbox, self.config['local_playlists_path'])
        self.populate_playlist_listbox(self.navi_playlists_listbox, self.config['navidrome_playlists_path'])
        self.local_tracks_listbox.delete(0, tk.END)
        self.navi_tracks_listbox.delete(0, tk.END)
        self.search_results_listbox.delete(0, tk.END)
        self.local_tracks_frame.label.config(text="Tracks (Local)")
        self.navi_tracks_frame.label.config(text="Tracks (Navidrome)")
        self.search_results_frame.label.config(text="Search Results")

    def populate_playlist_listbox(self, listbox, folder_path):
        listbox.delete(0, tk.END)
        try:
            playlists = [f for f in os.listdir(folder_path) if f.lower().endswith('.m3u')]
            for p in sorted(playlists): listbox.insert(tk.END, p)
        except FileNotFoundError: listbox.insert(tk.END, "Folder not found.")

    def on_playlist_select(self, event):
        widget = event.widget
        if not widget.curselection(): return
        playlist_name = widget.get(widget.curselection()[0])
        if widget == self.local_playlists_listbox and playlist_name in self.last_check_results:
            self._display_check_results(playlist_name, self.last_check_results[playlist_name])
            return
        if widget == self.local_playlists_listbox:
            folder, target_listbox, target_frame = self.config['local_playlists_path'], self.local_tracks_listbox, self.local_tracks_frame
            self.navi_tracks_listbox.delete(0, tk.END)
            self.navi_tracks_frame.label.config(text="Tracks (Navidrome)")
        else:
            folder, target_listbox, target_frame = self.config['navidrome_playlists_path'], self.navi_tracks_listbox, self.navi_tracks_frame
            self.local_tracks_listbox.delete(0, tk.END)
            self.local_tracks_frame.label.config(text="Tracks (Local)")
        target_frame.label.config(text=f"Tracks in '{playlist_name}'")
        tracks = navidrome_api.parse_m3u(os.path.join(folder, playlist_name))
        target_listbox.delete(0, tk.END)
        for track in tracks:
            target_listbox.insert(tk.END, f"{track['artist']} - {track['title']}")
            
    def sync_navidrome_playlists(self):
        if not self.config.get('navidrome_url'): messagebox.showerror("Error", "Please configure Navidrome in Settings."); return
        self.update()
        success, total, err = navidrome_api.download_all_playlists(self.config)
        if err: messagebox.showerror("Sync Error", f"Error: {err}")
        else: messagebox.showinfo("Sync Complete", f"Downloaded {success} of {total} playlists.")
        self.refresh_all_playlists()

    def on_search_click(self, event=None):
        query = self.search_entry.get()
        if not query: messagebox.showwarning("Search", "Please enter a search term."); return
        self.search_results_frame.label.config(text=f"Searching for '{query}'...")
        self.search_results_listbox.delete(0, tk.END)
        self.update()
        self.last_search_results = navidrome_api.search_tracks(self.config, query)
        self.search_results_frame.label.config(text=f"Search Results ({len(self.last_search_results)} found)")
        if not self.last_search_results:
            self.search_results_listbox.insert(tk.END, "No tracks found.")
        else:
            for track in self.last_search_results:
                self.search_results_listbox.insert(tk.END, f"{track['artist']} - {track['title']}")

    def on_replace_click(self):
        if not self.local_playlists_listbox.curselection():
            messagebox.showwarning("Replace", "Please select a checked playlist first."); return
        if not self.local_tracks_listbox.curselection() or not self.search_results_listbox.curselection():
            messagebox.showwarning("Replace", "Please select a track from 'Check Results' AND a track from 'Search Results'."); return
        local_playlist_name = self.local_playlists_listbox.get(self.local_playlists_listbox.curselection()[0])
        if local_playlist_name not in self.last_check_results:
            messagebox.showerror("Replace Error", "Please run a 'Check' on this playlist first."); return
        local_idx = self.local_tracks_listbox.curselection()[0]
        navi_idx = self.search_results_listbox.curselection()[0]
        check_item = self.last_check_results[local_playlist_name][local_idx]
        if check_item['status'] not in ['missing', 'suggestion', 'found']:
            messagebox.showinfo("Replace", "This track is already OK. No action needed."); return
        matched_song_data = self.last_search_results[navi_idx]
        check_item['status'] = 'ok'
        check_item['navidrome_song'] = matched_song_data
        check_item['score'] = 100
        track = check_item['original_track']
        display_text = f"[OK] {track['artist']} - {track['title']} (100%)"
        self.local_tracks_listbox.delete(local_idx)
        self.local_tracks_listbox.insert(local_idx, display_text)
        self.local_tracks_listbox.itemconfig(local_idx, {'fg': 'blue'})
        self.navi_tracks_listbox.delete(local_idx)
        self.navi_tracks_listbox.insert(local_idx, f"{matched_song_data['artist']} - {matched_song_data['title']}")
        messagebox.showinfo("Success", f"Successfully linked '{track['title']}'.\n\nClick 'Save' to save this change.")

    def on_check_click(self, show_summary=True):
        if not self.local_playlists_listbox.curselection():
            messagebox.showwarning("Check", "Please select a local playlist to check."); return
        if not self._ensure_song_cache_exists(): return
        playlist_name = self.local_playlists_listbox.get(self.local_playlists_listbox.curselection()[0])
        full_path = os.path.join(self.config['local_playlists_path'], playlist_name)
        local_tracks = navidrome_api.parse_m3u(full_path)
        if not local_tracks:
            messagebox.showinfo("Check", f"'{playlist_name}' is empty or could not be read."); return
        self.local_tracks_frame.label.config(text=f"Checking '{playlist_name}'...")
        self.update()
        results = navidrome_api.run_playlist_check(self.config, local_tracks, self.song_cache)
        self.last_check_results[playlist_name] = results
        self._display_check_results(playlist_name, results)
        if show_summary:
            messagebox.showinfo("Check Complete", f"Finished checking '{playlist_name}'.")

    def on_check_all_click(self):
        if not messagebox.askyesno("Confirm Check All", "This will check every playlist in your local folder and may take some time. Continue?"):
            return
        if not self._ensure_song_cache_exists(): return
        playlists_to_check = self.local_playlists_listbox.get(0, tk.END)
        if not playlists_to_check:
            messagebox.showinfo("Check All", "No local playlists to check.")
            return
        summary = {'found': 0, 'suggestion': 0, 'missing': 0, 'ok': 0, 'fixed': 0, 'total': 0}
        progress_popup = tk.Toplevel(self)
        progress_popup.title("Checking Playlists...")
        progress_popup.geometry("400x100")
        ttk.Label(progress_popup, text="Checking all playlists, please wait...").pack(pady=10)
        progress_bar = ttk.Progressbar(progress_popup, orient='horizontal', mode='determinate', length=380)
        progress_bar.pack(pady=10)
        progress_bar['maximum'] = len(playlists_to_check)
        self.update()
        for i, playlist_name in enumerate(playlists_to_check):
            full_path = os.path.join(self.config['local_playlists_path'], playlist_name)
            local_tracks = navidrome_api.parse_m3u(full_path)
            if not local_tracks: continue
            results = navidrome_api.run_playlist_check(self.config, local_tracks, self.song_cache)
            self.last_check_results[playlist_name] = results
            for item in results:
                summary.setdefault(item['status'], 0)
                summary[item['status']] += 1
                summary['total'] += 1
            progress_bar['value'] = i + 1
            self.update()
        progress_popup.destroy()
        ok_total = summary.get('ok', 0) + summary.get('fixed', 0)
        summary_message = f"Finished checking {len(playlists_to_check)} playlists.\n\n"
        summary_message += f"Total Tracks: {summary['total']}\n"
        summary_message += f"--------------------\n"
        summary_message += f"OK: {ok_total}\n"
        summary_message += f"Found: {summary['found']}\n"
        summary_message += f"Suggestions: {summary['suggestion']}\n"
        summary_message += f"Missing: {summary['missing']}"
        messagebox.showinfo("Check All Complete", summary_message)
        if self.local_playlists_listbox.curselection():
            playlist_name = self.local_playlists_listbox.get(self.local_playlists_listbox.curselection()[0])
            self._display_check_results(playlist_name, self.last_check_results[playlist_name])
    
    def on_accept_click(self):
        if not self.local_playlists_listbox.curselection():
            messagebox.showwarning("Accept", "Please select a checked playlist first."); return
        if not self.local_tracks_listbox.curselection():
            messagebox.showwarning("Accept", "Please select a track from the 'Check Results' list to accept."); return
        playlist_name = self.local_playlists_listbox.get(self.local_playlists_listbox.curselection()[0])
        if playlist_name not in self.last_check_results:
            messagebox.showerror("Accept Error", "Please run a 'Check' on this playlist first."); return
        selected_index = self.local_tracks_listbox.curselection()[0]
        check_item = self.last_check_results[playlist_name][selected_index]
        if check_item['status'] in ['suggestion', 'found']:
            check_item['status'] = 'ok'
            check_item['score'] = 100
            track = check_item['original_track']
            display_text = f"[OK] {track['artist']} - {track['title']} (100%)"
            self.local_tracks_listbox.delete(selected_index)
            self.local_tracks_listbox.insert(selected_index, display_text)
            self.local_tracks_listbox.itemconfig(selected_index, {'fg': 'blue'})
            messagebox.showinfo("Suggestion Accepted", f"'{track['title']}' has been accepted.\n\nClick 'Save' to save this change.")
        elif check_item['status'] == 'ok':
            messagebox.showinfo("Accept", "This track is already OK.")
        else:
            messagebox.showwarning("Accept", "This track is marked as missing and has no suggestion to accept.")
    
    def on_save_click(self):
        if not self.local_playlists_listbox.curselection():
            messagebox.showwarning("Save", "Please select a local playlist that has been checked."); return
        playlist_name = self.local_playlists_listbox.get(self.local_playlists_listbox.curselection()[0])
        if playlist_name not in self.last_check_results:
            messagebox.showerror("Save Error", "Please run a 'Check' on this playlist first."); return
        
        results = self.last_check_results[playlist_name]
        tracks_to_write = [item['navidrome_song'] for item in results if item['status'] in ['ok', 'found']]
        
        if not tracks_to_write and all(item['status'] != 'ok' for item in results):
             messagebox.showinfo("Save", "No tracks were found or accepted. Nothing to save."); return
             
        warning_message = (f"This will overwrite the playlist file:\n'{playlist_name}'\n\nIt will contain {len(tracks_to_write)} validated tracks.\nAre you sure?")
        if not messagebox.askyesno("Confirm Save", warning_message): return
        
        output_path = os.path.join(self.config['local_playlists_path'], playlist_name)
        success, error = self._write_m3u_file(output_path, tracks_to_write)
        if success:
            messagebox.showinfo("Save Complete", f"Successfully overwrote '{playlist_name}'.")
            self.on_check_click(show_summary=False)
        else:
            messagebox.showerror("File Error", f"Could not write to file.\n\nError: {error}")

    def on_add_click(self):
        if not self.local_playlists_listbox.curselection():
            messagebox.showwarning("Add", "Please select a local playlist to add to the cache."); return
        playlist_name = self.local_playlists_listbox.get(self.local_playlists_listbox.curselection()[0])
        source_path = os.path.join(self.config['local_playlists_path'], playlist_name)
        dest_path = os.path.join(self.config['navidrome_playlists_path'], playlist_name)
        if os.path.exists(dest_path):
            if not messagebox.askyesno("Overwrite", f"'{playlist_name}' already exists in the cache.\nOverwrite?"): return
        try:
            shutil.copy2(source_path, dest_path)
            messagebox.showinfo("Success", f"'{playlist_name}' was added to the cache.")
            self.populate_playlist_listbox(self.navi_playlists_listbox, self.config['navidrome_playlists_path'])
        except Exception as e:
            messagebox.showerror("Error", f"Could not copy file.\n\n{e}")

    def on_delete_click(self):
        if not self.navi_playlists_listbox.curselection():
            messagebox.showwarning("Delete", "Please select a playlist from the Navidrome Cache to delete."); return
        playlist_name = self.navi_playlists_listbox.get(self.navi_playlists_listbox.curselection()[0])
        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to permanently delete from the cache:\n'{playlist_name}'?"):
            try:
                os.remove(os.path.join(self.config['navidrome_playlists_path'], playlist_name))
                self.refresh_all_playlists()
            except Exception as e:
                messagebox.showerror("Delete Error", f"Could not delete file.\n\n{e}")

    def on_clear_click(self):
        if not messagebox.askyesno("Confirm Clear", "Are you sure you want to permanently delete ALL playlists from the Navidrome Cache folder?"):
            return
        try:
            folder = self.config['navidrome_playlists_path']
            for filename in os.listdir(folder):
                if filename.lower().endswith('.m3u'):
                    os.remove(os.path.join(folder, filename))
            self.refresh_all_playlists()
        except Exception as e:
            messagebox.showerror("Clear Error", f"Could not clear playlists.\n\n{e}")

    def on_upload_click(self):
        if not self.navi_playlists_listbox.curselection():
            messagebox.showwarning("Upload", "Please select a playlist from the cache to upload."); return
        if not self._ensure_song_cache_exists(): return
        playlist_name = self.navi_playlists_listbox.get(self.navi_playlists_listbox.curselection()[0])
        full_path = os.path.join(self.config['navidrome_playlists_path'], playlist_name)
        if not messagebox.askyesno("Confirm Upload", f"This will create or overwrite the playlist '{os.path.splitext(playlist_name)[0]}' on your Navidrome server.\n\nProceed?"):
            return
        original_label_text = self.navi_tracks_frame.label.cget("text")
        self.navi_tracks_frame.label.config(text=f"Uploading '{playlist_name}'...")
        self.update_idletasks()
        success, message = navidrome_api.upload_playlist(self.config, full_path, self.song_cache)
        if success:
            messagebox.showinfo("Upload Complete", message)
            self.sync_navidrome_playlists()
        else:
            messagebox.showerror("Upload Failed", message)
        self.navi_tracks_frame.label.config(text=original_label_text)
    
    def on_refresh_cache_click(self):
        if messagebox.askyesno("Confirm Refresh", "This will re-download all track data from the server and may take a moment. Are you sure?"):
            if self._ensure_song_cache_exists(force_refresh=True):
                messagebox.showinfo("Success", f"Song cache refreshed successfully.\nFound {len(self.song_cache)} tracks.")

    def on_merge_click(self, mode):
        if not self.navi_playlists_listbox.curselection() or not self.local_playlists_listbox.curselection():
            messagebox.showwarning("Merge", "Please select one playlist from the Navidrome Cache (left) AND one from Local Playlists (right) to merge.")
            return
        navi_name = self.navi_playlists_listbox.get(self.navi_playlists_listbox.curselection()[0])
        local_name = self.local_playlists_listbox.get(self.local_playlists_listbox.curselection()[0])
        navi_path = os.path.join(self.config['navidrome_playlists_path'], navi_name)
        local_path = os.path.join(self.config['local_playlists_path'], local_name)
        navi_tracks = navidrome_api.parse_m3u(navi_path)
        local_tracks = navidrome_api.parse_m3u(local_path)
        if mode == 'left':
            merged_tracks = navidrome_api.merge_playlists(navi_tracks, local_tracks)
            dest_path = navi_path
            if not messagebox.askyesno("Confirm Overwrite", f"This will merge '{local_name}' into '{navi_name}' and overwrite it in the Navidrome Cache. Proceed?"): return
        elif mode == 'right':
            merged_tracks = navidrome_api.merge_playlists(local_tracks, navi_tracks)
            dest_path = local_path
            if not messagebox.askyesno("Confirm Overwrite", f"This will merge '{navi_name}' into '{local_name}' and overwrite it in the Local Playlists. Proceed?"): return
        else:
            merged_tracks = navidrome_api.merge_playlists(navi_tracks, local_tracks)
            dest_path = filedialog.asksaveasfilename(
                initialdir=self.config['local_playlists_path'], title="Save Merged Playlist As",
                defaultextension=".m3u", filetypes=[("M3U Playlist", "*.m3u")]
            )
            if not dest_path: return
        success, error = self._write_m3u_file(dest_path, merged_tracks)
        if success:
            messagebox.showinfo("Merge Complete", f"Successfully saved merged playlist to:\n{os.path.basename(dest_path)}")
            self.refresh_all_playlists()
        else:
            messagebox.showerror("Merge Error", f"Could not save the merged playlist.\n\nError: {error}")

    def on_export_report_click(self):
        if not self.last_check_results:
            messagebox.showwarning("Export Report", "No check results to export. Please run 'Check' or 'Check All' first.")
            return
        report_content = []
        summary = {'found': 0, 'suggestion': 0, 'missing': 0, 'ok': 0, 'fixed': 0, 'total': 0}
        missing_tracks_by_playlist = {}
        for playlist_name, results in self.last_check_results.items():
            if not results: continue
            missing_tracks_by_playlist[playlist_name] = []
            for item in results:
                summary.setdefault(item['status'], 0)
                summary[item['status']] += 1
                summary['total'] += 1
                if item['status'] == 'missing':
                    missing_tracks_by_playlist[playlist_name].append(item['original_track'])
        if summary['total'] == 0:
            messagebox.showwarning("Export Report", "No tracks have been checked yet.")
            return
        ok_total = summary.get('ok', 0) + summary.get('fixed', 0)
        report_content.append(f"Navidrome Playlist Report - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        report_content.append("="*40)
        report_content.append("\n--- Overall Statistics ---\n")
        report_content.append(f"Total Tracks Checked: {summary['total']}")
        report_content.append(f"OK: {ok_total} ({ok_total/summary['total']:.1%})")
        report_content.append(f"Found: {summary['found']} ({summary['found']/summary['total']:.1%})")
        report_content.append(f"Suggestions: {summary['suggestion']} ({summary['suggestion']/summary['total']:.1%})")
        report_content.append(f"Missing: {summary['missing']} ({summary['missing']/summary['total']:.1%})\n")
        report_content.append("="*40)
        report_content.append("\n--- Detailed List of Missing Tracks ---\n")
        any_missing = False
        for playlist_name, missing_tracks in missing_tracks_by_playlist.items():
            if missing_tracks:
                any_missing = True
                report_content.append(f"\nPlaylist: {playlist_name}\n" + "-"*len(f"Playlist: {playlist_name}"))
                for track in missing_tracks:
                    report_content.append(f"  - {track['artist']} - {track['title']}")
        if not any_missing:
            report_content.append("\nNo missing tracks found in any checked playlists!")
        filepath = filedialog.asksaveasfilename(
            initialdir=".", title="Save Report As", defaultextension=".txt",
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")]
        )
        if not filepath: return
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write("\n".join(report_content))
            messagebox.showinfo("Report Exported", f"Successfully saved report to:\n{filepath}")
        except Exception as e:
            messagebox.showerror("Export Error", f"Could not save report file.\n\nError: {e}")

    def on_accept_all_click(self):
        if not self.local_playlists_listbox.curselection():
            messagebox.showwarning("Accept All", "Please select a checked playlist first.")
            return
        playlist_name = self.local_playlists_listbox.get(self.local_playlists_listbox.curselection()[0])
        if playlist_name not in self.last_check_results:
            messagebox.showerror("Accept All Error", "Please run a 'Check' on this playlist first.")
            return
        if not messagebox.askyesno("Confirm Accept All", f"This will accept all [FOUND] and [SUGGESTION] tracks in '{playlist_name}'.\n\nAre you sure?"):
            return
        results = self.last_check_results[playlist_name]
        for item in results:
            if item['status'] in ['found', 'suggestion']:
                item['status'] = 'ok'
                item['score'] = 100
        self._display_check_results(playlist_name, results)

    def on_save_all_click(self):
        if not self.last_check_results:
            messagebox.showwarning("Save All", "No check results to save. Please run 'Check' or 'Check All' first.")
            return
        if not messagebox.askyesno("Confirm Save All", f"This will overwrite ALL {len(self.last_check_results)} checked local playlists with their updated track lists.\n\nThis action cannot be undone. Are you absolutely sure?"):
            return
        
        saved_count = 0
        for playlist_name, results in self.last_check_results.items():
            tracks_to_write = [item['navidrome_song'] for item in results if item['status'] in ['ok', 'found']]
            # Only save if there are changes to be made.
            if tracks_to_write and any(item['status'] in ['found', 'suggestion'] for item in results):
                output_path = os.path.join(self.config['local_playlists_path'], playlist_name)
                success, _ = self._write_m3u_file(output_path, tracks_to_write)
                if success:
                    saved_count += 1
        
        messagebox.showinfo("Save All Complete", f"Successfully saved {saved_count} updated playlist(s).")
        self.on_check_all_click()

    def on_toggle_suggestion_click(self, event):
        if not self.local_playlists_listbox.curselection(): return
        playlist_name = self.local_playlists_listbox.get(self.local_playlists_listbox.curselection()[0])
        if playlist_name not in self.last_check_results: return
        
        selected_index = self.local_tracks_listbox.nearest(event.y)
        self.local_tracks_listbox.selection_clear(0, tk.END)
        self.local_tracks_listbox.selection_set(selected_index)
        
        check_item = self.last_check_results[playlist_name][selected_index]
        
        new_status = None
        if check_item['status'] == 'found': new_status = 'suggestion'
        elif check_item['status'] == 'suggestion': new_status = 'found'
        
        if new_status:
            check_item['status'] = new_status
            track = check_item['original_track']
            prefix = f"[{new_status.upper()}]"
            score = f"({check_item['score']:.0f}%)"
            display_text = f"{prefix} {track['artist']} - {track['title']} {score}"
            color = 'orange' if new_status == 'suggestion' else 'green'
            
            self.local_tracks_listbox.delete(selected_index)
            self.local_tracks_listbox.insert(selected_index, display_text)
            self.local_tracks_listbox.itemconfig(selected_index, {'fg': color})

if __name__ == "__main__":
    app = PlaylistToolApp()
    app.mainloop()