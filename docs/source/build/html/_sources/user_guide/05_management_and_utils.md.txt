# **5. Management & Utilities**

micro_X includes several built-in commands for managing the shell, its dependencies, and the underlying AI service.

## **Managing the Ollama Service (/ollama)**

You can control the Ollama service directly from within micro_X.

* **/ollama status**: Shows the current status of the Ollama service.  
* **/ollama start**: Starts the managed ollama serve process.  
* **/ollama stop**: Stops the managed ollama serve process.  
* **/ollama restart**: Restarts the managed ollama serve process.  
* **/ollama help**: Displays help information for these subcommands.

## **Managing Runtime AI Configuration (/config)**

You can view and modify parts of the AI configuration without restarting micro_X.

* **/config list**: Shows the current models and options for each AI role.  
* **/config get \<key.path\>**: Displays the value of a specific configuration key.  
* **/config set \<key.path\> \<value\>**: Sets a new value for a configuration key at runtime.  
* **/config save**: Saves the current runtime AI model configurations to your user_config.json file.  
* **/config help**: Shows usage instructions.

## **Updating micro_X (/update)**

The /update command checks for and downloads the latest changes for micro_X from its official Git repository.  
/update

If changes are downloaded, you will be prompted to restart micro_X for them to take effect.

## **Using Utility Scripts (/utils)**

micro_X comes with helpful utility scripts located in the utils/ directory.

* **/utils list**: Displays a list of available utility scripts.  
* **/utils \<script_name\> \[args...\]**: Executes the specified utility script.  
  * *Example*: /utils generate_tree  
  * **Web Config Manager**: A key utility is the web-based configuration manager. Launch it with:  
    /utils config_manager --start

    This will start a local web server and open a page in your browser for editing your configuration files.