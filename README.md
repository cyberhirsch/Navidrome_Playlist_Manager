# Navidrome Playlist Repair Tool

A powerful graphical utility designed to repair, match, and sync your local M3U playlists with your Navidrome music server.

Ever tried to import an old M3U playlist into Navidrome, only to find half the tracks are missing due to slightly different file paths or metadata? This tool solves that problem by intelligently matching your local tracks against your full Navidrome library, allowing you to fix broken playlists with ease.

![Application Screenshot](https://i.imgur.com/your-screenshot-url.png)
*(Replace the URL above with a link to a screenshot of the application in action)*

## Key Features

*   **Smart Matching Engine:**
    *   **Server-Side Cache:** On first run, builds a fast, persistent local cache of your entire Navidrome library for instant lookups.
    *   **Multi-Stage Checking:** Uses a 3-stage process to find tracks: perfect path matching, weighted fuzzy matching (Artist/Album/Title), and a title-only deep search.
    *   **Color-Coded Results:** Instantly see the status of every track:
        *   `[OK]` (Blue): Perfect match found.
        *   `[FOUND]` (Green): High-confidence match found automatically.
        *   `[SUGGESTION]` (Orange): Low-confidence match found, requires user approval.
        *   `[MISSING]` (Red): No suitable match could be found.

*   **Interactive Editing & Repair:**
    *   **Accept Suggestions:** Quickly approve machine suggestions with `Accept` and `Accept All` buttons.
    *   **Manual Search & Replace:** Use the integrated search bar to manually find and replace missing tracks.
    *   **Toggle Confidence:** `Shift+Click` a track to toggle its status between `[FOUND]` and `[SUGGESTION]`.

*   **Powerful Playlist Management:**
    *   **Sync & Upload:** Two-way synchronization with your Navidrome server. `Sync from Server` to download all playlists, and `Upload Selected` to send a fixed playlist back.
    *   **Merge Playlists:** Combine a local playlist and a cached Navidrome playlist in three different ways.
    *   **Bulk Processing:** `Check All` and `Save All` to process your entire playlist collection in one go.
    *   **File Management:** Add, Delete, and Clear playlists in both the local and cache directories directly from the UI.

*   **Reporting:**
    *   **Export Report:** Generate a detailed `.txt` report with overall statistics and a list of every missing track, organized by playlist.

## Prerequisites

*   Python 3.6+
*   pip

## Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/your-username/your-repo-name.git
    cd your-repo-name
    ```

2.  **Install the required dependencies:**
    A `requirements.txt` file is included for easy installation.
    ```bash
    pip install -r requirements.txt
    ```

## Configuration

1.  **Run the application for the first time:**
    ```bash
    python gui_app.py
    ```

2.  **Set up your connection:**
    *   A `config.json` file will be created in the same directory.
    *   Click the **`⚙️ Settings`** button in the application.
    *   Fill in your Navidrome URL, Username, and Password.
    *   The playlist paths will default to `local_playlists` and `navidrome_playlists` subdirectories, but you can change them if you wish.
    *   Click **`Test Connection`** to verify your credentials.
    *   Click **`Save & Close`**.

## Workflow: How to Use

The core workflow is designed to be simple: **Check -> Repair -> Save**.

#### 1. Load Your Playlists
Place your broken or unsynced `.m3u` playlists into the `local_playlists` folder. They will appear in the "Playlists (Local)" panel on the right.

#### 2. Check Your Playlists
*   **Build the Cache:** The first time you run an operation like `Check`, the app will build a local cache of your server's songs. This may take a moment but only happens once per session (or when you click `Refresh Cache`).
*   **Check a Single Playlist:** Select a playlist from the "Local Playlists" list and click **`Check`**.
*   **Check All Playlists:** Click **`Check All`** to analyze every playlist in your local folder. A summary report will be shown upon completion.

#### 3. Repair the Results
Review the "Check Results" panel.
*   For **`[SUGGESTION]`** or **`[FOUND]`** tracks that are correct, select them and click **`Accept`**. Use **`Accept All`** to approve every suggestion in the current playlist at once.
*   For **`[MISSING]`** tracks, select the track, type a search query into the **Search bar** at the top, and press Enter. Select the correct result from the "Search Results" panel and click **`Replace`**.
*   If you disagree with a **`[FOUND]`** match, **`Shift+Click`** it to demote it to a **`[SUGGESTION]`**. You can then search for a better replacement.

#### 4. Save Your Work
*   **Save a Single Playlist:** After making your corrections, click **`Save`**. This will overwrite the original local playlist file with a new version containing the corrected paths. All unaccepted suggestions and missing tracks will be removed.
*   **Save All Playlists:** Click **`Save All`** to save all playlists that have been checked and modified during the session.

#### 5. (Optional) Sync with Navidrome
*   **Download:** Use **`Sync from Server`** to download all your current Navidrome playlists to the "Navidrome Cache" folder for viewing or merging.
*   **Upload:** To upload a fixed local playlist, first `Add` it to the cache, then select it in the "Playlists (Navidrome Cache)" list and click **`Upload Selected`**. This will create or update the playlist on your Navidrome server.

## License

This project is licensed under the MIT License.
