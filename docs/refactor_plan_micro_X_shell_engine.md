## **Refactoring Plan: Centralizing Command Handling in ShellEngine**

This document outlines a phased approach to refactor the micro\_X project, specifically focusing on centralizing command parsing, routing, and the handling of built-in commands and top-level AI/categorization orchestration from main.py into the ShellEngine class.

The primary goal is to enhance modularity, testability, and maintainability by making main.py primarily responsible for UI initialization and event loop management, while ShellEngine becomes the authoritative component for all command-related logic.

**Constraint:** This plan is designed to minimize impact, ensuring no changes to existing features or code logic outside the direct scope of the moved functionality within main.py and modules/shell\_engine.py. Existing modules (ai\_handler.py, category\_manager.py, ollama\_manager.py, output\_analyzer.py, ui\_manager.py) will remain untouched by this refactoring, and ShellEngine will continue to utilize their public interfaces.

#### **Phase 0: Preparation & Baseline**

This phase ensures a stable starting point and sets up the development environment.

1. **Verify Current State:**  
   * Open your terminal in the micro\_X project root directory.  
   * Run all existing pytest tests:  
     pytest

   * **Ensure all tests pass (e.g., "104 passed in X.XXs").** If any tests fail, address them before proceeding.  
   * Manually launch micro\_X and perform a quick smoke test of core functionalities (e.g., ls, /ai list files, /ollama status, cd .., /command list) to confirm current behavior.  
2. **Create a New Git Branch:**  
   * This is crucial for isolating changes and allowing easy rollback if issues arise.  
   *   git checkout \-b feature/shell-engine-refactor

#### **Phase 1: Migrate Built-in Command Dispatching**

This phase moves the top-level routing for /help, exit/quit, /update, /utils, and /ollama into ShellEngine.

1. **Update modules/shell\_engine.py:**  
   * **Add Necessary Imports:**  
     \# In modules/shell\_engine.py  
     import asyncio \# Already present  
     import os \# Already present  
     import shlex  
     import subprocess \# Already present  
     import uuid \# Already present  
     import re \# Already present  
     import logging \# Already present  
     import time  
     import shutil \# Already present  
     import sys \# New import for sys.modules references

     from modules import ollama\_manager \# New import for direct access to ollama\_manager functions  
     \# Other existing imports like output\_analyzer

   * **Modify ShellEngine.\_\_init\_\_ signature and storage:**  
     \# In modules/shell\_engine.py, inside the ShellEngine class  
     def \_\_init\_\_(self, config, ui\_manager, category\_manager\_module=None, ai\_handler\_module=None, ollama\_manager\_module=None, main\_exit\_app\_ref=None, main\_restore\_normal\_input\_ref=None):  
         \# ... existing init ...  
         self.ollama\_manager\_module \= ollama\_manager\_module  
         self.main\_exit\_app\_ref \= main\_exit\_app\_ref \# Callback to main's exit function  
         self.main\_restore\_normal\_input\_ref \= main\_restore\_normal\_input\_ref \# Callback to main's restore\_normal\_input\_handler

         logger.info("ShellEngine initialized.")

   * **Move \_display\_general\_help:**  
     * Cut the display\_general\_help function from main.py.  
     * Paste into modules/shell\_engine.py as a private method of ShellEngine:  
       \# In modules/shell\_engine.py, inside the ShellEngine class  
       def \_display\_general\_help(self):  
           if not self.ui\_manager: logger.error("display\_general\_help: UIManager not initialized."); return  
           \# ... rest of the original display\_general\_help content ...  
           \# Ensure all calls to append\_output\_func become self.ui\_manager.append\_output

   * **Move \_display\_ollama\_help:**  
     * Cut the display\_ollama\_help function from main.py.  
     * Paste into modules/shell\_engine.py as a private method of ShellEngine:  
       \# In modules/shell\_engine.py, inside the ShellEngine class  
       def \_display\_ollama\_help(self):  
           if not self.ui\_manager: logger.error("display\_ollama\_help: UIManager not initialized."); return  
           \# ... rest of the original display\_ollama\_help content ...  
           \# Ensure all calls to append\_output\_func become self.ui\_manager.append\_output

   * **Move \_handle\_update\_command:**  
     * Cut the handle\_update\_command function from main.py.  
     * Paste into modules/shell\_engine.py as an async private method of ShellEngine:  
       \# In modules/shell\_engine.py, inside the ShellEngine class  
       async def \_handle\_update\_command(self):  
           if not self.ui\_manager: logger.error("handle\_update\_command: UIManager not initialized."); return  
           \# ... rest of the original handle\_update\_command content ...  
           \# Ensure all calls to ui\_manager\_instance.append\_output become self.ui\_manager.append\_output  
           \# Ensure all calls to ui\_manager\_instance.get\_app\_instance() become self.ui\_manager.get\_app\_instance()

   * **Move \_handle\_utils\_command\_async:**  
     * Cut the handle\_utils\_command\_async function from main.py.  
     * Paste into modules/shell\_engine.py as an async private method of ShellEngine:  
       \# In modules/shell\_engine.py, inside the ShellEngine class  
       async def \_handle\_utils\_command\_async(self, full\_command\_str: str):  
           if not self.ui\_manager: logger.error("handle\_utils\_command\_async: UIManager not initialized."); return  
           \# ... rest of the original handle\_utils\_command\_async content ...  
           \# Ensure all calls to ui\_manager\_instance.append\_output become self.ui\_manager.append\_output  
           \# Ensure all calls to ui\_manager\_instance.get\_app\_instance() become self.ui\_manager.get\_app\_instance()

   * **Move \_handle\_ollama\_command\_async:**  
     * Cut the handle\_ollama\_command\_async function from main.py.  
     * Paste into modules/shell\_engine.py as an async private method of ShellEngine:  
       \# In modules/shell\_engine.py, inside the ShellEngine class  
       async def \_handle\_ollama\_command\_async(self, user\_input\_parts: list):  
           if not self.ui\_manager: logger.error("handle\_ollama\_command\_async: UIManager not initialized."); return  
           append\_output\_func \= self.ui\_manager.append\_output \# Update this line

           \# Replace all direct calls to ollama\_manager functions with self.ollama\_manager\_module.function\_name  
           if len(user\_input\_parts) \< 2: self.\_display\_ollama\_help(); return \# Update internal call  
           subcommand \= user\_input\_parts\[1\].lower()

           if subcommand \== "start":  
               success \= await self.ollama\_manager\_module.explicit\_start\_ollama\_service(self.config, append\_output\_func)  
               \# The \`ollama\_service\_ready\` global in main.py is removed; ShellEngine directly uses ollama\_manager calls  
               \# when needed, or checks status dynamically. The initial check in main\_async\_runner is for welcome.  
           elif subcommand \== "stop":  
               success \= await self.ollama\_manager\_module.explicit\_stop\_ollama\_service(self.config, append\_output\_func)  
           elif subcommand \== "restart":  
               success \= await self.ollama\_manager\_module.explicit\_restart\_ollama\_service(self.config, append\_output\_func)  
           elif subcommand \== "status":  
               await self.ollama\_manager\_module.get\_ollama\_status\_info(self.config, append\_output\_func)  
           elif subcommand \== "help":  
               self.\_display\_ollama\_help() \# Update internal call  
           \# ... rest of the original function ...

   * **Add handle\_built\_in\_command Method:** This will be the new entry point for built-in command routing.  
     \# In modules/shell\_engine.py, inside the ShellEngine class  
     async def handle\_built\_in\_command(self, user\_input: str) \-\> bool:  
         """  
         Handles built-in shell commands like /help, /exit, /update, /utils, /ollama.  
         Returns True if a built-in command was handled, False otherwise.  
         """  
         user\_input\_stripped \= user\_input.strip()  
         logger.info(f"ShellEngine.handle\_built\_in\_command received: '{user\_input\_stripped}'")

         if user\_input\_stripped.lower() in {"/help", "help"}:  
             self.\_display\_general\_help()  
             return True  
         elif user\_input\_stripped.lower() in {"exit", "quit", "/exit", "/quit"}:  
             self.ui\_manager.append\_output("Exiting micro\_X Shell 🚪", style\_class='info')  
             logger.info("Exit command received from built-in handler.")  
             if self.main\_exit\_app\_ref: \# Use the passed callback  
                 self.main\_exit\_app\_ref()  
             else:  
                 \# Fallback if callback wasn't set, though it should be.  
                 app\_instance \= self.ui\_manager.get\_app\_instance()  
                 if app\_instance and app\_instance.is\_running:  
                     app\_instance.exit()  
             return True  
         elif user\_input\_stripped.lower() \== "/update":  
             await self.\_handle\_update\_command()  
             return True  
         elif user\_input\_stripped.startswith("/utils"):  
             await self.\_handle\_utils\_command\_async(user\_input\_stripped)  
             return True  
         elif user\_input\_stripped.startswith("/ollama"):  
             try:  
                 parts \= user\_input\_stripped.split()  
                 await self.\_handle\_ollama\_command\_async(parts)  
             except Exception as e:  
                 self.ui\_manager.append\_output(f"❌ Error processing /ollama command: {e}", style\_class='error')  
                 logger.error(f"Error in /ollama command '{user\_input\_stripped}': {e}", exc\_info=True)  
             return True

         return False \# Not a built-in command handled by this method

2. **Update main.py:**  
   * **Remove Global ollama\_service\_ready:** Delete the line ollama\_service\_ready \= False and any other assignments to this global variable. ShellEngine will now query the ollama\_manager\_module directly for service status.  
   * **Update main\_async\_runner's ShellEngine Initialization:**  
     \# In main.py, inside main\_async\_runner  
     \# ... other initializations ...  
     ui\_manager\_instance \= UIManager(config)  
     ui\_manager\_instance.main\_exit\_app\_ref \= \_exit\_app\_main  
     \# \`restore\_normal\_input\_handler\` is a global function in main.py.  
     \# It's better passed as a reference to UIManager and then to ShellEngine.  
     ui\_manager\_instance.main\_restore\_normal\_input\_ref \= restore\_normal\_input\_handler

     \# Initialize ShellEngine with all necessary module references and callbacks  
     shell\_engine\_instance \= ShellEngine(config, ui\_manager\_instance,  
                                         category\_manager\_module=sys.modules\['modules.category\_manager'\],  
                                         ai\_handler\_module=sys.modules\['modules.ai\_handler'\],  
                                         ollama\_manager\_module=sys.modules\['modules.ollama\_manager'\], \# New: pass the ollama\_manager module  
                                         main\_exit\_app\_ref=\_exit\_app\_main, \# New: pass the exit callback  
                                         main\_restore\_normal\_input\_ref=restore\_normal\_input\_handler) \# New: pass the restore input callback

   * **Modify handle\_input\_async (preliminary change):**  
     * Locate the block of if conditions that check for /help, exit/quit, /update, /utils, /ollama.  
     * Replace the entire block with a single call to the new ShellEngine method:  
       \# In main.py, inside handle\_input\_async  
       \# ... existing input stripping ...  
       if await shell\_engine\_instance.handle\_built\_in\_command(user\_input\_stripped):  
           return  
       \# ... rest of handle\_input\_async ...

   * **Remove Old Global Functions from main.py:** Delete the following global functions (their logic is now in ShellEngine):  
     * def display\_general\_help():  
     * def display\_ollama\_help():  
     * async def handle\_update\_command():  
     * async def handle\_utils\_command\_async(full\_command\_str: str):  
     * async def handle\_ollama\_command\_async(user\_input\_parts: list):  
3. **Intermediate Testing (Phase 1):**  
   * **Run Automated Tests:** Execute pytest. Pay close attention to any new failures, especially in test\_shell\_engine.py (which might need updates) or any regressions in other modules.  
   * **Manual Testing:**  
     * Launch micro\_X.  
     * Test all variations of: /help, exit, quit, /exit, /quit.  
     * Test /update.  
     * Test /utils list, /utils help, /utils generate\_tree.  
     * Test /ollama status, /ollama start, /ollama stop, /ollama restart, /ollama help.  
     * Verify that these built-in commands work exactly as they did before the refactoring.

#### **Phase 2: Migrate Core Command Processing Orchestration**

This phase moves the main command dispatching logic, including AI interaction and the central process\_command function, into ShellEngine.

1. **Update modules/shell\_engine.py:**  
   * **Move process\_command:**  
     * Cut the entire async def process\_command(...) function from main.py.  
     * Paste it into modules/shell\_engine.py as a method of ShellEngine:  
       \# In modules/shell\_engine.py, inside the ShellEngine class  
       async def process\_command(self, command\_str\_original: str, original\_user\_input\_for\_display: str,  
                                 ai\_raw\_candidate: str | None \= None,  
                                 original\_direct\_input\_if\_different: str | None \= None,  
                                 forced\_category: str | None \= None,  
                                 is\_ai\_generated: bool \= False):  
           if not self.ui\_manager: logger.error("process\_command: UIManager not initialized."); return  
           \# shell\_engine\_instance is now 'self' in this method  
           if not self: logger.error("process\_command: ShellEngine not initialized."); return \# Defensive check

           append\_output\_func \= self.ui\_manager.append\_output  
           confirmation\_result \= None

           \# Update all internal calls within this method:  
           \# ui\_manager\_instance becomes self.ui\_manager  
           \# get\_validated\_ai\_command becomes self.ai\_handler\_module.get\_validated\_ai\_command  
           \# is\_valid\_linux\_command\_according\_to\_ai becomes self.ai\_handler\_module.is\_valid\_linux\_command\_according\_to\_ai  
           \# classify\_command becomes self.category\_manager\_module.classify\_command  
           \# cm\_add\_command\_to\_category becomes self.category\_manager\_module.add\_command\_to\_category  
           \# restore\_normal\_input\_handler() (if called here) becomes self.main\_restore\_normal\_input\_ref()  
           \# Ensure the calls to self.execute\_shell\_command and self.execute\_command\_in\_tmux are already \`self.method\_name\`

           \# Example of change:  
           \# linux\_command, ai\_raw\_candidate \= await get\_validated\_ai\_command(human\_query, config, append\_output\_func, app\_getter)  
           \# \-\> linux\_command, ai\_raw\_candidate \= await self.ai\_handler\_module.get\_validated\_ai\_command(human\_query, self.config, append\_output\_func, app\_getter)

           \# The \`ollama\_service\_ready\` check needs to be updated. It should now query self.ollama\_manager\_module.is\_ollama\_server\_running()  
           \# For instance:  
           \# if not ollama\_service\_ready:  
           \# \-\> if not await self.ollama\_manager\_module.is\_ollama\_server\_running():

   * **Add submit\_user\_input Method (main entry point for non-built-in user input):**  
     * Cut the *remaining* code inside main.py's handle\_input\_async (after the handle\_built\_in\_command check).  
     * Paste this logic into modules/shell\_engine.py as an async method of ShellEngine:  
       \# In modules/shell\_engine.py, inside the ShellEngine class  
       async def submit\_user\_input(self, user\_input: str):  
           """  
           Processes a user's input, orchestrating AI validation, translation,  
           categorization flows, and command execution.  
           This is the main entry point for user commands to the ShellEngine.  
           """  
           if not self.ui\_manager: logger.error("submit\_user\_input: UIManager not initialized."); return  
           append\_output\_func \= self.ui\_manager.append\_output

           user\_input\_stripped \= user\_input.strip()  
           logger.info(f"ShellEngine.submit\_user\_input received: '{user\_input\_stripped}'")  
           if not user\_input\_stripped: return

           current\_app\_inst \= self.ui\_manager.get\_app\_instance()

           \# \`cd\` command handling: Already in ShellEngine, but called from main.py's old handle\_input\_async.  
           \# Now, it must be handled here explicitly if it reaches this point.  
           if user\_input\_stripped \== "cd" or user\_input\_stripped.startswith("cd "):  
               logger.info(f"ShellEngine handling 'cd' command directly: {user\_input\_stripped}")  
               await self.handle\_cd\_command(user\_input\_stripped)  
               return

           \# AI query handling (\`/ai\`):  
           if user\_input\_stripped.startswith("/ai "):  
               \# The \`ollama\_service\_ready\` check needs to be updated.  
               \# It should now query self.ollama\_manager\_module.is\_ollama\_server\_running()  
               ollama\_is\_ready \= await self.ollama\_manager\_module.is\_ollama\_server\_running()  
               if not ollama\_is\_ready:  
                   append\_output\_func("⚠️ Ollama service is not available.", style\_class='warning')  
                   append\_output\_func("   Try '/ollama status' or '/ollama start'.", style\_class='info')  
                   logger.warning("Attempted /ai command while Ollama service is not ready.")  
                   return

               human\_query \= user\_input\_stripped\[len("/ai "):\].strip()  
               \# ... rest of /ai logic, ensuring all calls to \`get\_validated\_ai\_command\` become \`self.ai\_handler\_module.get\_validated\_ai\_command\`  
               \# and calls to \`process\_command\` become \`self.process\_command\`.  
               \# Ensure \`app\_getter\` is passed as \`self.ui\_manager.get\_app\_instance\`.  
               linux\_command, ai\_raw\_candidate \= await self.ai\_handler\_module.get\_validated\_ai\_command(human\_query, self.config, append\_output\_func, self.ui\_manager.get\_app\_instance)  
               if linux\_command:  
                   await self.process\_command(linux\_command, f"/ai {human\_query} \-\> {linux\_command}", ai\_raw\_candidate, None, is\_ai\_generated=True)  
               else:  
                   append\_output\_func("🤔 AI could not produce a validated command.", style\_class='warning')  
               return

           \# /command subsystem handling:  
           if user\_input\_stripped.startswith("/command"):  
               \# handle\_command\_subsystem\_input needs self.category\_manager\_module.handle\_command\_subsystem\_input  
               command\_action \= self.category\_manager\_module.handle\_command\_subsystem\_input(user\_input\_stripped)  
               if isinstance(command\_action, dict) and command\_action.get('action') \== 'force\_run':  
                   cmd\_to\_run \= command\_action\['command'\]  
                   forced\_cat \= command\_action\['category'\]  
                   display\_input \= f"/command run {forced\_cat} \\"{cmd\_to\_run}\\""  
                   append\_output\_func(f"⚡ Forcing execution of '{cmd\_to\_run}' as '{forced\_cat}'...", style\_class='info')  
                   await self.process\_command(cmd\_to\_run, display\_input, None, None, forced\_category=forced\_cat, is\_ai\_generated=False)  
               return

           \# Direct command processing:  
           logger.debug(f"ShellEngine.submit\_user\_input: Classifying direct command: '{user\_input\_stripped}'")  
           \# classify\_command needs self.category\_manager\_module.classify\_command  
           category \= self.category\_manager\_module.classify\_command(user\_input\_stripped)  
           logger.debug(f"ShellEngine.submit\_user\_input: classify\_command returned: '{category}' for command '{user\_input\_stripped}'")

           if category \!= self.category\_manager\_module.UNKNOWN\_CATEGORY\_SENTINEL:  
               logger.debug(f"Direct input '{user\_input\_stripped}' is known: '{category}'.")  
               await self.process\_command(user\_input\_stripped, user\_input\_stripped, None, None, is\_ai\_generated=False)  
           else:  
               logger.debug(f"Direct input '{user\_input\_stripped}' unknown. Validating with AI.")  
               \# The \`ollama\_service\_ready\` check needs to be updated.  
               ollama\_is\_ready \= await self.ollama\_manager\_module.is\_ollama\_server\_running()  
               if not ollama\_is\_ready:  
                   \# ... message handling ...  
                   logger.warning(f"Ollama service not ready. Skipping AI validation for '{user\_input\_stripped}'.")  
                   await self.process\_command(user\_input\_stripped, user\_input\_stripped, None, None, is\_ai\_generated=False)  
                   return  
               \# ... rest of direct command logic, ensuring all calls to \`is\_valid\_linux\_command\_according\_to\_ai\`  
               \# and \`get\_validated\_ai\_command\` become \`self.ai\_handler\_module.method\_name\`  
               \# and calls to \`process\_command\` become \`self.process\_command\`.

2. **Update main.py:**  
   * **Remove ollama\_service\_ready local initial assignment:** ollama\_service\_ready \= await ensure\_ollama\_service(...) in main\_async\_runner can remain as it influences the initial welcome message, but subsequent checks should be removed.  
   * **Modify normal\_input\_accept\_handler:**  
     * Replace asyncio.create\_task(handle\_input\_async(buff.text)) with:  
       \# In main.py, inside normal\_input\_accept\_handler  
       \# This calls the new entry point in ShellEngine  
       asyncio.create\_task(shell\_engine\_instance.submit\_user\_input(buff.text))

   * **Remove Old Global Functions from main.py:** Delete the following global functions (their logic is now in ShellEngine):  
     * async def handle\_input\_async(user\_input: str): (the entire function)  
     * async def process\_command(...) (the entire function)  
     * def restore\_normal\_input\_handler(): (This function is now effectively replaced by the callback ui\_manager\_instance.main\_restore\_normal\_input\_ref pointing to ShellEngine's own \_restore\_normal\_input\_mode or similar. Since ui\_manager holds the reference, it can remain for ui\_manager to call it. However, if ShellEngine needs to directly restore the prompt after an internal operation, it should call self.main\_restore\_normal\_input\_ref(). For this refactoring, it's safer to keep restore\_normal\_input\_handler in main.py and ensure ui\_manager and shell\_engine correctly reference it.)  
3. **Intermediate Testing (Phase 2):**  
   * **Run Automated Tests:** Execute pytest. This will require significant updates to test\_shell\_engine.py to cover the newly moved and integrated logic. Ensure existing tests for other modules (especially test\_ui\_manager.py's flow tests) continue to pass.  
   * **Manual Testing:**  
     * Launch micro\_X.  
     * Test all command types extensively:  
       * Direct commands (ls, pwd, echo, cd).  
       * /ai queries (all confirmation choices, explanations, modifications).  
       * Typing an unknown command (check AI validation, translation, categorization flow).  
       * /command subcommands (add, remove, list, move, run).  
       * Ensure semi\_interactive and interactive\_tui commands behave correctly in tmux.  
     * Verify proper error handling and messages.

#### **Phase 3: Final Review & Cleanup**

1. **Review main.py:**  
   * Confirm it now solely handles:  
     * Initial directory and path setup.  
     * Logging configuration.  
     * Loading of overall config.  
     * Initialization of UIManager and ShellEngine (passing necessary module references and callbacks).  
     * Initial Ollama service check for the welcome message.  
     * Running the main prompt\_toolkit application loop.  
   * Verify there are no remnants of complex command logic or direct global state manipulation (other than config itself) that should be in ShellEngine.  
2. **Review modules/shell\_engine.py:**  
   * Confirm all command-related logic (parsing, built-ins, AI interaction, categorization, execution) is centralized here.  
   * Ensure all methods correctly use self.ui\_manager, self.config, self.category\_manager\_module, self.ai\_handler\_module, self.ollama\_manager\_module, and self.main\_restore\_normal\_input\_ref/self.main\_exit\_app\_ref.  
   * Clean up any redundant module imports (e.g., if a module was imported at the top of main.py but is now only used within a moved ShellEngine method, move the import to modules/shell\_engine.py).  
3. **Automated Test Expansion:**  
   * Thoroughly review and expand tests/test\_shell\_engine.py to achieve high test coverage for all ShellEngine methods (especially the newly moved process\_command and submit\_user\_input). This is crucial for long-term stability.  
4. **Comprehensive Manual Testing:**  
   * Execute the full docs/micro\_X\_testing\_guide.md checklist from start to finish. This will be the ultimate validation that the refactoring has not introduced any regressions.  
5. **Commit Changes:**  
   * Once all automated tests pass and comprehensive manual verification is complete, commit the changes to your feature/shell-engine-refactor branch.  
   * Consider a squashed commit or logical commits for the entire refactoring to maintain a clean Git history.

This detailed plan provides a structured, step-by-step approach to the refactoring, reducing the risk of introducing new bugs and ensuring existing functionality remains intact. Each phase builds upon the previous one, making it easier to isolate and debug any issues that may arise.