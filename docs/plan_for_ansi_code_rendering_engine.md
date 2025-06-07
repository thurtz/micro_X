## **Plan: ANSI Code Rendering in micro\_X**

**Objective:** Implement rendering of basic ANSI SGR (Select Graphic Rendition) escape codes (e.g., colors, bold, italic, underline) for:

1. Output from simple commands executed directly in micro\_X.  
2. Captured output from semi\_interactive commands after they have completed their execution in tmux.

This will be achieved using a unified rendering engine within micro\_X, primarily affecting the UIManager.

### **1\. Core Component: ANSI Parser & Formatter**

* **Location:** This will be a new utility function, likely callable from UIManager. Let's call it format\_ansi\_text(text\_content: str) \-\> FormattedText.  
* **Functionality:**  
  * Input: A string (text\_content) potentially containing ANSI SGR escape codes.  
  * Output: prompt\_toolkit's FormattedText (a list of (style\_string, text\_fragment) tuples).  
  * Mechanism: Utilize prompt\_toolkit.formatted\_text.ANSI(text\_content). This class directly converts a string with ANSI codes into the required FormattedText list.  
* **Scope:** This parser will focus on SGR codes. It will not attempt to interpret cursor positioning, screen clearing, or other complex terminal control sequences.

### **2\. UIManager Modifications**

* **output\_field Refactor (Potential):**  
  * The current output\_field is a TextArea(read\_only=True). We need to verify if its buffer.document can be efficiently and correctly updated with mixed content (some parts being plain text with a micro\_X style class, other parts being FormattedText lists derived from ANSI).  
  * If TextArea proves problematic for this mixed dynamic content, output\_field might need to be refactored into a Window containing a FormattedTextControl. The FormattedTextControl is explicitly designed to display FormattedText and can be dynamically updated by providing it a callable that returns the current FormattedText list to display.  
* **output\_buffer Structure:**  
  * Currently, self.output\_buffer stores tuples of (style\_class, text\_content).  
  * We need a way to distinguish raw command output that needs ANSI parsing from micro\_X's internal styled messages.  
  * **Proposal:** Introduce a special style\_class like 'command\_output\_raw' for text that should be processed by the ANSI formatter.  
* **append\_output Method:**  
  * This method will remain the primary way to add text to the output area.  
  * It will continue to append (style\_class, text\_content) tuples to self.output\_buffer.  
* **Text Preparation for Display:**  
  * The logic that takes self.output\_buffer and prepares it for display in self.output\_field will be modified.  
  * When iterating through self.output\_buffer to build the displayable content:  
    * If an item's style\_class is 'command\_output\_raw' (and the render\_command\_ansi config is true):  
      * Pass its text\_content to format\_ansi\_text().  
      * The resulting FormattedText list will be used for this part of the output.  
    * Otherwise (for internal micro\_X messages):  
      * The existing (style\_class, text\_content) tuple will be used directly (as prompt\_toolkit can handle this format for applying styles from the Style object).  
* **Styling:**  
  * The prompt\_toolkit.formatted\_text.ANSI class translates standard ANSI SGR codes (e.g., \\x1b\[31m) into prompt\_toolkit style strings (e.g., fg:ansired).  
  * The main UIManager.style (defined via Style.from\_dict) should generally not conflict with these, as prompt\_toolkit handles standard ANSI color names. No specific changes to UIManager.style are anticipated for basic ANSI color rendering itself, but custom micro\_X styles should continue to work.

### **3\. ShellEngine Modifications**

* **execute\_shell\_command (for simple commands):**  
  * When a simple command's stdout or stderr is captured:  
    * It will be passed to UIManager.append\_output with the special style\_class (e.g., 'command\_output\_raw').  
* **execute\_command\_in\_tmux (for semi\_interactive commands):**  
  * The command will continue to be executed in tmux, and its output will be captured to the temporary log file.  
  * **After the command finishes and the log file content is read:**  
    1. The raw content from the log file will first be passed to output\_analyzer.is\_tui\_like\_output().  
    2. If is\_tui\_like\_output returns True:  
       * UIManager.append\_output will be called with the standard message: "\[Semi-interactive TUI-like output not displayed directly.\] Tip: Try: /command move ... interactive\_tui". The raw TUI output will *not* be rendered.  
    3. If is\_tui\_like\_output returns False:  
       * The raw content from the log file will be passed to UIManager.append\_output with the special style\_class (e.g., 'command\_output\_raw'), allowing UIManager to then parse it for ANSI codes.

### **4\. output\_analyzer.py Interaction**

* The role of output\_analyzer.py remains critical and unchanged for semi\_interactive commands.  
* It will always analyze the *raw, captured output* from the tmux log file *before* any ANSI rendering attempt by UIManager for display in micro\_X.  
* This ensures that full TUI applications mistakenly run as semi\_interactive are still caught and handled appropriately, preventing garbled output in the main micro\_X pane.

### **5\. Configuration**

* Add a new configuration option to config/default\_config.json (and by extension, allow in user\_config.json):  
  // ... in "ui" section ...  
  "render\_command\_ansi": true

* UIManager (specifically, the logic that prepares text for display) will check this flag. If false, it will not call format\_ansi\_text() and will display raw command output as plain text (as it does currently).

### **6\. Testing Strategy**

1. **Unit Tests for format\_ansi\_text():**  
   * Test with various SGR codes (foreground/background colors, bold, italic, underline, reset).  
   * Test with mixed ANSI and plain text.  
   * Test with malformed or unsupported ANSI codes (ensure graceful handling, e.g., they are ignored or passed through as literal text).  
   * Test with empty strings and strings without ANSI codes.  
2. **UIManager Tests:**  
   * Verify append\_output correctly passes raw command output through the formatter when the config is enabled.  
   * Verify it bypasses the formatter when the config is disabled or for internal micro\_X messages.  
   * If output\_field is refactored, test the new FormattedTextControl setup.  
3. **ShellEngine Integration Tests:**  
   * Test simple commands known to produce ANSI colored output (e.g., ls \--color=auto, grep \--color=auto "pattern" file\_with\_color\_support).  
   * Test semi\_interactive commands that produce non-TUI ANSI colored output (e.g., a script that echoes colored text). Verify output is captured and then rendered with colors.  
   * Test semi\_interactive commands that *do* produce TUI-like output. Verify output\_analyzer catches it and the "TUI-like output not displayed" message appears (no ANSI rendering attempt for the TUI itself).  
4. **Manual Testing:**  
   * Extensive manual testing with a variety of commands and tools that use ANSI codes.  
   * Test toggling the render\_command\_ansi configuration option.  
   * Check for performance impact with commands generating very large amounts of colored output.

### **7\. Documentation Updates**

* Update docs/micro\_X\_User\_Guide.md to mention the new ANSI rendering capability for simple and captured semi\_interactive outputs.  
* Document the new ui.render\_command\_ansi configuration option in relevant configuration guides or the User Guide.

### **Implementation Steps Summary:**

1. **Develop & Unit Test format\_ansi\_text() utility.**  
2. **Investigate & Refactor UIManager.output\_field** (if TextArea is insufficient for dynamic FormattedText).  
3. **Modify UIManager.append\_output** and its display logic to use format\_ansi\_text() for 'command\_output\_raw' style class.  
4. **Update ShellEngine** to use the new style\_class when appending output from simple and (non-TUI) semi\_interactive commands.  
5. **Ensure ShellEngine correctly uses output\_analyzer.py *before* attempting ANSI rendering** for semi\_interactive output.  
6. **Add the render\_command\_ansi configuration option** and integrate its checking.  
7. **Write comprehensive integration tests.**  
8. **Perform thorough manual testing.**  
9. **Update documentation.**

This plan provides a structured approach to implementing the desired ANSI rendering feature while maintaining the existing strengths of micro\_X's command execution model.