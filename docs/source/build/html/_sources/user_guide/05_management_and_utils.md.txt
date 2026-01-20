# **5. Management & Utilities**

micro_X includes several built-in commands for managing the shell, its dependencies, and the underlying AI service.

## **Managing the Ollama Service (/ollama)**

You can control the Ollama service directly from within micro_X.

* **/ollama status**: Shows the current status of the Ollama service.
* **/ollama start**: Starts the managed ollama serve process.
* **/ollama stop**: Stops the managed ollama serve process.
* **/ollama restart**: Restarts the managed ollama serve process.
* **/ollama help**: Displays help information for these subcommands.

## **Web-Based Configuration Manager (/config)**

For an easy way to view and edit your user configuration files, you can use the web-based configuration manager.

*   **/config --start**: Starts a local web server and opens a page in your browser for editing `user_config.json` and `user_command_categories.json`.
*   **/config --stop**: Stops the configuration manager's web server.

## **Updating micro_X (/update)**

The `/update` command checks for and downloads the latest changes for micro_X from its official Git repository.
If changes are downloaded, you will be prompted to restart micro_X.

## **Documentation (/docs)**

Accessing the documentation is easy:

*   **/docs**: Opens the full HTML documentation in your system's default web browser.
*   **Ctrl+D**: Shortcut key to open documentation instantly.
*   **Shortcut File**: A `view_docs.html` file is available in the `docs/` directory for quick access from a file manager.

**Advanced Queries:**
*   **/docs --query <question>**: Queries the documentation knowledge base using AI.

## **Using Utility Scripts (/utils)**

micro_X comes with helpful utility scripts located in the utils/ directory.

* **/utils list**: Displays a list of available utility scripts.
* **/utils \<script_name\> \[args...\]**: Executes the specified utility script.
  * *Example*: `/utils generate_tree`

**Note:** While you can run utility scripts directly, it is recommended to use their corresponding aliases (e.g., `/tree` instead of `/utils generate_tree`) for a better experience.
