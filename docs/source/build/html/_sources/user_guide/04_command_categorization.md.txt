# **4. Command Categorization**

When micro_X encounters a command it hasn't seen before, it will prompt you to categorize it. This helps micro_X run the command in the most appropriate way, especially for interactive or long-running tasks.

## **Categories**

* **simple**: For commands that run quickly and produce non-interactive output (e.g., ls, echo, cat). They are executed directly, and their output is captured in the main UI.  
* **semi_interactive**: For commands that might run for a while, produce a lot of output, or have minimal interactivity (e.g., apt update, ping google.com). These are run in a new tmux window, and their output is displayed after the command finishes.  
* **interactive_tui**: For fully interactive terminal applications (e.g., nano, vim, htop, ssh). These are run in a new tmux window that takes over the screen until you exit the application.

## **Categorization Prompt**

When an unknown command is entered, you will see a prompt like this:  
Command 'my_script.sh' is not categorized. Choose an action:  
1: simple (Direct output in micro_X)  
2: semi_interactive (Output in micro_X after tmux run)  
3: interactive_tui (Full interactive tmux session)  
M: Modify command before categorizing  
D: Execute as default 'semi_interactive' (once, no save)  
C: Cancel categorization & execution  
\[Categorize\] Action (1-3/M/D/C):

Your choice will be saved in your user configuration for future use.

## **Managing Categories (/command subsystem)**

You can manage your saved command categorizations using the /command utility.

* **/command list**: Shows all categorized commands.  
* **/command add "\<command\>" \<category\>**: Adds or updates a command's category.  
  * *Example*: /command add "htop" interactive_tui  
* **/command remove "\<command\>"**: Removes a command from your user settings.  
* **/command move "\<command\>" \<new_category\>**: Moves a command to a different category.  
* **/command help**: Shows detailed usage instructions.