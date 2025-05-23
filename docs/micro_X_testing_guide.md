### **Comprehensive Testing List for micro\_X**

This list covers core functionality, UI interactions, AI features, and recent refactoring changes.

**I. Core Shell Functionality & Basic Commands:**

1. **Startup & Exit:**  
   * \[ \] Launch micro\_X successfully.  
   * \[ \] Exit micro\_X using exit command.  
   * \[ \] Exit micro\_X using quit command.  
   * \[ \] Exit micro\_X using Ctrl+D (from normal input mode).  
   * \[ \] Exit micro\_X using Ctrl+C (from normal input mode).  
2. **cd Command (Thorough Check):**  
   * \[ \] cd (should go to home directory, prompt updates).  
   * \[ \] cd .. (should go to parent directory, prompt updates).  
   * \[ \] cd \<existing\_directory\_name\> (e.g., cd logs, prompt updates).  
   * \[ \] cd /tmp (absolute path, prompt updates).  
   * \[ \] cd \~ (home directory, prompt updates).  
   * \[ \] cd non\_existent\_folder (should show error, directory/prompt should not change).  
   * \[ \] cd with multiple arguments (e.g., cd foo bar) \- should likely fail or take the first argument. Verify behavior.  
   * \[ \] **Verify no AI validation/categorization is triggered for any cd variant.**  
3. **Simple Direct Commands (Verify execution and output):**  
   * \[ \] ls  
   * \[ \] ls \-l  
   * \[ \] pwd  
   * \[ \] echo "hello world"  
   * \[ \] echo $SHELL (or other environment variables)  
   * \[ \] clear (should clear the output screen effectively).  
4. **Command History:**  
   * \[ \] Enter several commands.  
   * \[ \] Navigate history using Up Arrow.  
   * \[ \] Navigate history using Down Arrow.  
   * \[ \] Edit a command from history and execute.  
5. **Multi-line Input:**  
   * \[ \] Use Ctrl+N to create multi-line input.  
   * \[ \] Execute a simple multi-line command (e.g., echo "line1"; echo "line2").  
   * \[ \] Navigate within multi-line input using Up/Down/Ctrl+Up/Ctrl+Down arrows.

**II. UI Manager & Keybindings (Post-Refactor):**

1. **Flow Cancellation (Ctrl+C / Ctrl+D):**  
   * **Categorization Flow:**  
     * \[ \] Trigger categorization (e.g., type unknown\_command\_for\_cat\_test).  
     * \[ \] At "Which version to categorize?" prompt, press Ctrl+C. (Should cancel, return to normal prompt).  
     * \[ \] Trigger again. Choose "1". At "How to categorize?" prompt, press Ctrl+C. (Should cancel, return to normal prompt).  
     * \[ \] Trigger again. Choose "3" (Modify/Enter new). At "New command:" prompt, press Ctrl+C.  
     * \[ \] Trigger again. Choose "M" (Modify). At "Modified Cmd:" prompt, press Ctrl+C.  
   * **Command Confirmation Flow:**  
     * \[ \] Trigger confirmation (e.g., /ai list files).  
     * \[ \] At "Action: \[Y\]es..." prompt, press Ctrl+C. (Should cancel, return to normal prompt).  
     * \[ \] Trigger again. Choose "E" (Explain). After explanation, at "Action: \[Y\]es..." prompt, press Ctrl+C.  
   * **Edit Mode (from Confirmation Flow):**  
     * \[ \] Trigger confirmation (e.g., /ai show current date).  
     * \[ \] Choose "M" (Modify). Input field should show the command.  
     * \[ \] Press Ctrl+C. (Should cancel edit mode, print "Command editing cancelled", return to normal prompt).  
2. **Input Field Behavior:**  
   * \[ \] Verify prompt updates correctly after cd.  
   * \[ \] Verify prompt changes for categorization flow.  
   * \[ \] Verify prompt changes for confirmation flow.  
   * \[ \] Verify prompt changes for edit mode.  
   * \[ \] Verify input field switches between single-line (flows) and multi-line (normal/edit) correctly.  
3. **Output Area:**  
   * \[ \] Test PgUp / PgDn for scrolling.  
   * \[ \] Verify auto-scroll behavior (scrolls to bottom for new output, stops if user scrolls up, resumes if user scrolls back to bottom).  
   * \[ \] Verify auto-scroll is forced during active flows (categorization, confirmation, edit mode messages).

**III. AI Features & Flows:**

1. **/ai Command Translation & Confirmation Flow:**  
   * \[ \] /ai list text files  
     * \[ \] Choose "Y" (Yes). If command is new, proceed to categorization.  
     * \[ \] /ai find python files \-\> Choose "Ys" (Simple & Run). Verify execution and categorization.  
     * \[ \] /ai show running processes \-\> Choose "Ym" (Semi-Interactive & Run). Verify.  
     * \[ \] /ai open a text editor \-\> Choose "Yi" (TUI & Run). Verify.  
     * \[ \] /ai what is my ip \-\> Choose "E" (Explain). Review explanation. Then choose "Y" to execute.  
     * \[ \] /ai delete all .tmp files \-\> Choose "M" (Modify). Change command in input field (e.g., to ls \*.tmp). Press Enter. (Should execute modified command, potentially trigger categorization).  
     * \[ \] /ai format my hard drive \-\> Choose "C" (Cancel). Verify command is not executed.  
   * \[ \] /ai with an empty query (should show warning).  
   * \[ \] /ai with a query the AI might refuse (e.g., /ai tell me a secret). Observe behavior.  
2. **Direct Unknown Command \-\> AI Validation \-\> Potential Translation/Categorization:**  
   * \[ \] Type a plausible but unknown command (e.g., list\_large\_files \--size 10M).  
     * Verify "Validating with AI..." message.  
     * If AI validates as command: Verify it goes to categorization.  
     * If AI validates as not a command / phrase: Verify it attempts NL translation.  
       * If translation successful, verify confirmation flow is triggered.  
       * If translation fails, verify it attempts to run original as direct command (leading to categorization).  
   * \[ \] Type a natural language phrase directly (e.g., show me disk space).  
     * Verify AI validation (likely fails as command).  
     * Verify it attempts NL translation.  
     * Verify confirmation flow if translation successful.  
3. **Ollama Service Not Ready:**  
   * \[ \] Stop Ollama service manually.  
   * \[ \] Try /ai list files. Verify "Ollama service is not available" message and guidance.  
   * \[ \] Try typing an unknown command. Verify message about Ollama not being available for validation/translation and that it proceeds to categorization.

**IV. Command Categorization & Execution:**

1. **Trigger Categorization Flow (Unknown Command):**  
   * \[ \] Type my\_very\_unique\_script \--option value  
   * **Step 0.5 (Confirm Command Base \- if applicable, e.g., if input was slightly modified by a pre-parser, though not currently the case for direct input):**  
     * \[ \] Test choosing "Processed".  
     * \[ \] Test choosing "Original" (if different).  
     * \[ \] Test choosing "Modify/Enter new command" \-\> Enter a new command \-\> Verify it goes to Step 1 for the new command.  
     * \[ \] Test choosing "Cancel".  
   * **Step 1 (Main Action):**  
     * \[ \] Choose "1" (simple). Verify command is added to user\_command\_categories.json and executed as simple.  
     * \[ \] Choose "2" (semi\_interactive). Verify and check tmux execution.  
     * \[ \] Choose "3" (interactive\_tui). Verify and check tmux execution.  
     * \[ \] Choose "M" (Modify). Modify the command. Then categorize the modified command.  
     * \[ \] Choose "D" (Default). Verify it runs with default category and is NOT saved.  
     * \[ \] Choose "C" (Cancel). Verify no execution, no save.  
2. **/command Subsystem:**  
   * \[ \] /command list (verify output format, presence of default and user commands).  
   * \[ \] /command add "mytestcmd \--verbose" simple  
   * \[ \] /command add "myinteractivecmd" 3  
   * \[ \] Verify newly added commands appear in /command list and are classified correctly when typed directly.  
   * \[ \] /command move "mytestcmd \--verbose" interactive\_tui  
   * \[ \] Verify mytestcmd \--verbose is now interactive\_tui.  
   * \[ \] /command remove "myinteractivecmd"  
   * \[ \] Verify myinteractivecmd is removed from user settings (may revert to default or unknown).  
   * \[ \] /command run simple "echo forced simple" (verify execution method).  
   * \[ \] /command run 3 "nano test\_force.txt" (verify tmux interactive).  
   * \[ \] /command help (verify help message).  
   * \[ \] Invalid /command usage (e.g., /command add\_typo, /command add "cmd") \- verify error messages.  
3. **Execution Types:**  
   * \[ \] Execute a known "simple" command.  
   * \[ \] Execute a known "semi\_interactive" command (e.g., sleep 5 && echo done from tmux). Check for output capture and TUI-like output detection if applicable.  
   * \[ \] Execute a known "interactive\_tui" command (e.g., nano). Verify tmux session.

**V. Ollama Service Management (/ollama):**

1. **Pre-test:** Ensure Ollama is running independently.  
2. \[ \] /ollama status (verify output reflects running state).  
3. \[ \] /ollama stop (if micro\_X started it, verify it stops. If external, verify message).  
4. \[ \] /ollama status (verify output reflects stopped state if applicable).  
5. \[ \] /ollama start (verify it attempts to start, check status again).  
6. \[ \] /ollama restart (verify stop then start sequence).  
7. \[ \] /ollama help (verify help message).  
8. **Test with Ollama initially stopped:**  
   * \[ \] Manually stop Ollama service.  
   * \[ \] Launch micro\_X. Observe auto-start behavior (if enabled in config).  
   * \[ \] /ollama status.  
   * \[ \] /ollama start.

**VI. Miscellaneous:**

1. **/update command:**  
   * \[ \] Run /update (requires git setup). Observe output.  
   * \[ \] If changes are pulled, verify message about restarting and requirements.txt.  
2. **/utils command:**  
   * \[ \] /utils list (or /utils help).  
   * \[ \] If generate\_tree.py exists in utils, try /utils generate\_tree. Verify output.  
   * \[ \] Try /utils non\_existent\_script. Verify error.  
3. **Configuration Loading:**  
   * \[ \] Verify fallback, default, and user configs are loaded as per logs.  
   * \[ \] Try making a change in user\_config.json (e.g., input\_field\_height) and restart to see if it takes effect.  
4. **Error Handling:**  
   * \[ \] Try commands that produce errors (e.g., ls /nonexistent\_path). Verify stderr is displayed.  
   * \[ \] Try to break input parsing with unusual characters (though shlex should be robust).

This list is quite extensive. Go through it systematically, and let me know of any issues you find or any areas that seem unclear\!